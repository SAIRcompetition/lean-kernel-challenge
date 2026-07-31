#!/usr/bin/env python3
"""Lean Kernel Challenge judge.

Pipeline per submission (each contestant job runs in a unique temp workspace):
  1. Validate + assemble: copy the locked problem template, then overlay the contestant's
     Submission.lean (+ Submission/). Contestant files are re-audited ON THE ASSEMBLED
     tree (regular files, no symlinks, size/count caps, containment) to close the
     validate-then-copy TOCTOU window.
  2. Correctness gate: run comparator (statement match, axiom whitelist, kernel replay of
     the ∀n proof). Sandboxed via landrun on Linux; on macOS the pass-through shim strips
     sandboxing. The SHA-256 of the verified Submission bytes is pinned for step 4.
  3. Axiom re-audit of the comparator-emitted solution export (whitelisted axioms only).
  4. Scored replay: time the comparator-verified correctness export, then for each
     judge-chosen input n reduce `impl n` to a literal v via a kernel-side oracle, confirm the
     Submission is byte-unchanged from step 2, build+export a uniquely named
     `impl n = v` theorem whose direct proof forces kernel reduction, re-audit THAT export,
     and time the official kernel replaying it, N reps. A too-slow input occupies
     its explicit slot and later slots are still attempted; a deterministic oracle/build/kernel
     fault errors with no score. metric=wall_time (dev) or perf_instructions (Linux host).
     With TIMING_EXECUTOR_URLS set the replays run on a remote KTP/2 executor with real PMU
     hardware; each per-input export is uploaded with its SHA-256. An unreachable executor is
     NOT a verdict: the run exits 3 with a "retry" verdict so the caller can requeue losslessly.

Exit codes: 0 = judged (verdict JSON, accepted OR rejected); 2 = infrastructure error;
3 = timing executor unreachable (verdict status "retry" — requeue and try again later).
Every infra failure still writes an error JSON and exits 2, never a traceback.

ISOLATION (not the judge's job): killing EVERY process a submission spawns (incl. setsid
escapes), resource caps, and non-root execution are enforced by the container/cgroup, not
this process — use scripts/run_isolated.sh. The bundled process-group kill and read-only
freeze here are defense in depth, not a security boundary.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import resource
import shutil
import signal
import stat
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent            # lean-kernel-challenge/
PROBLEMS = ROOT / "problems"
RESULTS = ROOT / "results"

# Judge budgets + timing/sandbox policy live in pipeline/config.json (SAIR convention).
_CFG = json.loads((ROOT / "pipeline" / "config.json").read_text())
_J = _CFG["judge"]
COMPARATOR_TIMEOUT = _J["comparator_timeout_seconds"]
AUDIT_TIMEOUT = _J["audit_timeout_seconds"]
TIMING_TIMEOUT = _J["timing_timeout_seconds"]
# Whole-performance-phase ceiling. Per-step timeouts do not bound a submission's total: with every
# slot probed and each failure able to burn the full timing budget, one job could hold a judge for
# hours. On exhaustion the remaining slots are marked and a normal verdict is still emitted.
PERF_PHASE_BUDGET = _J.get("perf_phase_budget_seconds", 10800)
DEFAULT_REPS = _J["timing_reps"]
MAX_SUBMISSION_BYTES = _J["max_submission_bytes"]
MAX_SUBMISSION_FILES = _J["max_submission_files"]
# Timing metric + sandbox mode; env overrides let the Docker host switch to perf.
TIMING_METRIC = os.environ.get("TIMING_METRIC", _CFG.get("timing", {}).get("metric", "wall_time"))
SANDBOX_MODE = os.environ.get("SANDBOX_MODE", _CFG.get("sandbox", {}).get("mode", "none"))
OFFICIAL_EVAL = os.environ.get("OFFICIAL_EVAL", "") == "1"
# Remote timing executor (KTP/2, lean-timer-executor). Comma-separated URLs in
# active-standby order; used only when metric=perf_instructions. The secret is
# the executor's bearer token and never appears in verdicts or logs.
TIMING_EXECUTOR_URLS = [u.strip().rstrip("/") for u in
                        os.environ.get("TIMING_EXECUTOR_URLS", "").split(",") if u.strip()]
TIMING_EXECUTOR_SECRET = os.environ.pop("TIMING_EXECUTOR_SECRET", "")
# Dispatch attempts across the URL list before giving up with a "retry"
# verdict: sleep, then walk every URL again. Short and bounded — long
# outages are the CALLER's requeue loop, not ours.
_EXECUTOR_ATTEMPT_SLEEPS = [0, 10, 30]
# Once one executor serves a point, PIN it for the rest of this submission so a mid-curve
# failover cannot mix PMU data from different machines under one label. If the pinned node
# later goes unreachable, that raises TimingRetry and the whole submission is requeued (never
# silently continued on another node). One judge process = one submission, so this is per-job.
_PINNED_EXECUTOR = [None]
_PINNED_EXECUTOR_IDENTITY = [None]

# Tool locations. Default to the local `repro/` checkout; override via env on the
# Docker/Linux eval host, where the tools are built at fixed image paths.
REPRO = ROOT.parent / "repro"
COMPARATOR = Path(os.environ.get("COMPARATOR_BIN", REPRO / "comparator/.lake/build/bin/comparator"))
LEAN4EXPORT_BIN = Path(os.environ.get("LEAN4EXPORT_BIN", REPRO / "lean4export/.lake/build/bin"))
TIMER = Path(os.environ.get("TIMER_BIN", ROOT / "judge/timer-kernel/.lake/build/bin/kernel"))
# Versioned measurement protocol shared by this judge, timer-kernel, and KTP/2 executors.
# Changing any boundary semantics must change at least one of these strings so the cohort hash
# prevents old and new samples from being ranked together.
MEASUREMENT_CONTRACT = "kernel-replay-v2"
FULL_REPLAY_BOUNDARY = "full-closure-replay-v1"
TARGET_REPLAY_BOUNDARY = "target-declaration-replay-v1"
TARGET_PROOF_ENCODING = "direct-of-decide-eq-true-rfl-v1"
CHECKER_ID = f"official-kernel-replay v4.32.0-rc1 ({MEASUREMENT_CONTRACT})"
_TIMER_TIMING_PREFIX = "KERNEL_TIMING="
# There is no READY/ACK channel in v2. The process watchdog therefore bounds untimed
# parse/dependency preparation plus the measured replay. Record that limitation explicitly
# whenever it fires; a normal nonzero exit remains a deterministic failure, never a timeout.
PROCESS_TIMEOUT_SCOPE = "whole-timer-process-including-untimed-preparation"
# Bundled pass-through shims for `landrun`/`timeout` so the package is self-contained on
# dev machines. Used ONLY when a real `landrun` isn't on PATH (Docker/Linux ships the
# real Landlock sandbox, which must win). See tool_env().
SHIM_DIR = Path(os.environ.get("SHIM_DIR", ROOT / "scripts" / "shims"))

# Kernel-builtin constants comparator always exports alongside the targets.
PRIMITIVES = [
    "Nat.add", "Nat.sub", "Nat.mul", "Nat.pow", "Nat.gcd", "Nat.div", "Nat.mod",
    "Nat.beq", "Nat.ble", "Nat.land", "Nat.lor", "Nat.xor",
    "Nat.shiftLeft", "Nat.shiftRight", "String.ofList",
]

# No slashes, no "..", no whitespace — and no leading dash, so a name like "--reps" can never be
# mistaken for an option when it is passed through argv (self-inflicted DoS, not an injection).
SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")

# The scaling-axis inputs are a CONFIGURED POLICY, never hardcoded: each problem's config.json
# declares `perf` {min, max, count?, spacing?, jitter?}, with global fallbacks in
# pipeline/config.json `perf_defaults`. The judge samples `count` geometrically-spaced inputs in
# [min, max] (even coverage in log-space, for a stable log-log slope), clamped to distinct
# integers. Every submission in one evaluation cohort receives the same seed-jittered schedule,
# so raw kernel work remains comparable. The operator rotates the hidden seed between cohorts;
# with no seed the points are deterministic (local dev). See rules/evaluation.md.
_PERF_DEFAULTS = _CFG.get("perf_defaults", {"count": 10, "spacing": "geometric", "jitter": 0.15})
PERF_SEED = os.environ.pop("PERF_SEED", "")
_PERF_SEED_SOURCE = ["environment" if PERF_SEED else None]
EVALUATION_COHORT = os.environ.get("EVALUATION_COHORT", "")


def _official_eval():
    return TIMING_METRIC == "perf_instructions" or OFFICIAL_EVAL


def _perf_policy_error(problem, detail):
    raise InfraError(f"invalid perf policy for '{problem}': {detail}")


def _policy_int(value, problem, field):
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value.strip()):
        return int(value)
    _perf_policy_error(problem, f"{field} must be an integer (got {value!r})")


def _perf_jitter(x, lo, hi, frac, problem, idx):
    """Deterministic per-point jitter in [1-frac, 1+frac].

    One hidden rotation token yields one shared schedule per problem. Submission-specific
    jitter is deliberately forbidden: comparing raw work at different n is not a fair score,
    especially for factorial/exponential problems.
    """
    if not PERF_SEED or frac <= 0:
        return x
    material = json.dumps([PERF_SEED, problem, idx],
                          ensure_ascii=True, separators=(",", ":")).encode()
    h = hashlib.sha256(material).digest()
    u = int.from_bytes(h[:8], "big") / 2.0 ** 64          # uniform in [0, 1)
    return min(hi, max(lo, x * (1.0 + (2.0 * u - 1.0) * frac)))


def perf_inputs(cfg, problem):
    """Return exactly `count` strictly increasing Nat inputs from the configured policy.

    Official evaluation requires a nonempty, operator-supplied rotation seed. Invalid or
    impossible policies fail explicitly instead of silently returning fewer points.
    """
    perf = cfg.get("perf")
    if not (isinstance(perf, dict) and "min" in perf and "max" in perf):
        return None
    if _official_eval() and not PERF_SEED:
        raise InfraError("official evaluation requires a nonempty PERF_SEED")

    lo = _policy_int(perf["min"], problem, "min")
    hi = _policy_int(perf["max"], problem, "max")
    if lo < 0:
        _perf_policy_error(problem, f"min must be >= 0 for Nat inputs (got {lo})")
    if hi < lo:
        _perf_policy_error(problem, f"max ({hi}) is smaller than min ({lo})")

    configured_count = _policy_int(
        perf.get("count", _PERF_DEFAULTS.get("count", 10)), problem, "count")
    count_override = os.environ.get("PERF_COUNT")
    if count_override not in (None, "") and re.fullmatch(r"[+-]?[0-9]+", count_override.strip()):
        count = int(count_override)
    else:
        # PERF_COUNT is an operator convenience, not part of the problem policy. Preserve the
        # established forgiving behavior for a malformed override, while still rejecting an
        # invalid configured count below.
        count = configured_count
    if count < 1:
        _perf_policy_error(problem, f"count must be >= 1 (got {count})")
    capacity = hi - lo + 1
    if count > capacity:
        _perf_policy_error(
            problem, f"count {count} exceeds the {capacity} distinct integers in [{lo}, {hi}]")

    spacing = perf.get("spacing", _PERF_DEFAULTS.get("spacing", "geometric"))
    if spacing not in ("geometric", "linear"):
        _perf_policy_error(problem, f"spacing must be 'geometric' or 'linear' (got {spacing!r})")

    frac_value = perf.get("jitter", _PERF_DEFAULTS.get("jitter", 0.15))
    if isinstance(frac_value, bool) or not isinstance(frac_value, (int, float)):
        _perf_policy_error(problem, f"jitter must be a finite number (got {frac_value!r})")
    frac = float(frac_value)
    if not math.isfinite(frac) or not 0 <= frac < 1:
        _perf_policy_error(problem, f"jitter must satisfy 0 <= jitter < 1 (got {frac_value!r})")
    if _official_eval() and frac == 0:
        _perf_policy_error(problem, "official evaluation requires positive jitter")

    if count == 1:
        raw = [float(lo)]
    elif spacing == "linear":
        raw = [lo + (hi - lo) * i / (count - 1) for i in range(count)]
    elif lo == 0:
        # Log spacing is undefined at zero. Keep zero as the first slot and distribute the
        # remaining slots geometrically over the positive part of the interval.
        if count == 2:
            raw = [0.0, float(hi)]
        else:
            positive_count = count - 1
            raw = [0.0] + [
                hi ** (i / (positive_count - 1)) for i in range(positive_count)
            ]
    else:
        raw = [lo * (hi / lo) ** (i / (count - 1)) for i in range(count)]  # geometric

    # Project the possibly-colliding/locally-reordered rounded targets onto feasible integer
    # slots. The per-index bounds leave exactly enough room for all later points, so this
    # produces `count` points without retry loops or silent set-based collapse.
    pts = []
    for idx, x in enumerate(raw):
        target = int(round(_perf_jitter(x, lo, hi, frac, problem, idx)))
        lower = lo + idx
        upper = hi - (count - 1 - idx)
        if pts:
            lower = max(lower, pts[-1] + 1)
        pts.append(min(upper, max(lower, target)))
    if len(pts) != count or any(a >= b for a, b in zip(pts, pts[1:])):
        _perf_policy_error(problem, "could not construct the requested distinct input slots")
    return pts


class InfraError(Exception):
    """Raised for any infrastructure failure; caught at top level → error JSON + exit 2."""


class SubmissionError(Exception):
    """Raised for a contestant-side format error (missing / oversized / symlinked / non-.lean
    Submission). It is the submission's fault, so the top level writes a REJECTED verdict
    (exit 0) — not an infra error, which (exit 2) would requeue an invalid submission forever."""


class TimingRetry(Exception):
    """Raised when every timing executor is unreachable. NOT a judgement: the top
    level writes a 'retry' verdict and exits 3 so the caller requeues the
    submission losslessly (never an error verdict for an executor outage)."""


def _consume_perf_seed_stdin():
    """Read the official seed once, before any untrusted process is started.

    The production wrapper sends it on stdin instead of Docker env/argv, then the pipe is
    exhausted. This keeps the secret out of the elaborator environment and out of the parent
    process's initial `/proc/.../environ` image.
    """
    global PERF_SEED
    marker = os.environ.pop("PERF_SEED_STDIN", "")
    if not marker:
        return
    if marker != "1":
        raise InfraError("PERF_SEED_STDIN must be exactly '1'")
    if PERF_SEED:
        raise InfraError("ambiguous PERF_SEED sources (environment and stdin)")
    raw = sys.stdin.buffer.readline(1026)
    if not raw.endswith(b"\n") or len(raw) > 1025:
        raise InfraError("official PERF_SEED stdin record is missing or too long")
    try:
        seed = raw[:-1].decode("utf-8")
    except UnicodeDecodeError:
        raise InfraError("official PERF_SEED must be valid UTF-8")
    if not seed or "\x00" in seed:
        raise InfraError("official PERF_SEED must be nonempty and contain no NUL")
    PERF_SEED = seed
    _PERF_SEED_SOURCE[0] = "stdin"


def valid_slug(s: str) -> bool:
    return bool(s) and s != ".." and SLUG.match(s) is not None


def _write_infra_verdict(problem, sub_name, reason, status="error"):
    """Best-effort error verdict so the contract 'always a verdict file, never a
    traceback' holds even for unexpected failures."""
    try:
        outdir = RESULTS / (problem if valid_slug(problem or "") else "_infra")
        outdir.mkdir(parents=True, exist_ok=True)
        name = sub_name if valid_slug(sub_name or "") else "_invalid"
        (outdir / f"{name}.json").write_text(json.dumps(
            {"problem": problem, "submission": sub_name,
             "status": status, "reason": reason, "stages": {}}, indent=2))
    except Exception:
        pass


def _network_is_reachable():
    """Probe whether outbound networking works, as evidence the container envelope was applied.

    Under `--network none` a connect() fails immediately with ENETUNREACH/EHOSTUNREACH, so this is
    a fast, dependency-free check that the sandbox is REAL rather than merely configured. Any
    successful connection (or a timeout, which implies a routable-but-filtered network) counts as
    reachable and must fail the job."""
    import socket
    for addr in (("192.0.2.1", 80), ("8.8.8.8", 53)):        # TEST-NET-1, then a public resolver
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            s.connect(addr)
            return True                                       # connected → not isolated
        except (socket.timeout, TimeoutError):
            return True                                       # routable but filtered → not isolated
        except OSError:
            continue                                          # unreachable → consistent with isolation
        finally:
            s.close()
    return False


def has_real_landrun(env):
    return shutil.which("landrun", path=env.get("PATH", "")) not in (None, str(SHIM_DIR / "landrun"))


def tool_env():
    # Keep every untrusted Lean/comparator process on a small, stable environment.
    # In particular, PERF_SEED and executor credentials must never cross this boundary.
    env = {}
    for key in ("HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR"):
        if key in os.environ:
            env[key] = os.environ[key]
    env["HOME"] = env.get("HOME", str(Path.home()))
    env["ELAN_HOME"] = os.environ.get("ELAN_HOME", str(Path.home() / ".elan"))
    env["LEAN_ABORT_ON_PANIC"] = "1"
    parts = [str(LEAN4EXPORT_BIN)]
    # Prepend the bundled shim only if no real landrun is on PATH (dev machine).
    host_path = os.environ.get("PATH", os.defpath)
    if shutil.which("landrun", path=host_path) is None:
        parts.insert(0, str(SHIM_DIR))
    env["PATH"] = os.pathsep.join(parts + [host_path])
    return env


def _kill_group(pgid):
    """Kill a saved process-group id. NOTE: this reaps descendants that stayed in the
    group; it is NOT a security boundary — a descendant can `setsid()` out of the group,
    and same-UID processes can race files. Real isolation (kill-all, resource caps) is
    the container/cgroup + non-root user's job (see Dockerfile). This is defense in depth."""
    if pgid is None:
        return
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _raise_stack():
    """Raise the child's stack rlimit before exec so deep kernel/Meta reduction (reducing
    `impl n` for large n, or elaborating the generated kernel proof) doesn't overflow the default
    ~8 MB stack. macOS refuses `soft == hard` for RLIMIT_STACK, so try a descending set of
    targets and keep the largest that sticks (Linux's infinite hard limit takes 512 MB on
    the first try; a raise that doesn't stick just leaves the default in place)."""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    except (ValueError, OSError):
        return
    cap = (512 * 1024 * 1024) if hard == resource.RLIM_INFINITY else hard
    for target in (cap, cap - (1 << 20), 256 * 1024 * 1024, 64 * 1024 * 1024):
        if target <= soft:
            return
        try:
            resource.setrlimit(resource.RLIMIT_STACK, (target, hard))
            return
        except (ValueError, OSError):
            continue


def run(cmd, cwd, env, timeout, stdout_path=None):
    """Run a command in its own process group. The saved pgid is killed on timeout AND on
    normal exit (pgid captured at spawn, not via getpgid on an already-exited child).
    Returns (exit_code | 'timeout', output_tail)."""
    popen_kw = dict(cwd=cwd, env=env, start_new_session=True, preexec_fn=_raise_stack)
    p = None
    pgid = None
    try:
        if stdout_path:
            with open(stdout_path, "wb") as f:
                p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.PIPE, **popen_kw)
                pgid = p.pid  # start_new_session=True → child is its own group leader
                try:
                    _, err = p.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    _kill_group(pgid); p.wait()
                    return "timeout", f"timed out after {timeout}s"
            out = (err or b"").decode(errors="replace")
        else:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **popen_kw)
            pgid = p.pid
            try:
                out_b, _ = p.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_group(pgid); p.wait()
                return "timeout", f"timed out after {timeout}s"
            out = (out_b or b"").decode(errors="replace")
        return p.returncode, out
    except FileNotFoundError as e:
        raise InfraError(f"tool not found: {e}")
    finally:
        # Reap any descendants left in the group (dev boxes without landrun). Uses the
        # pgid captured at spawn, so it works even though the direct child has exited.
        _kill_group(pgid)


def last_line(out):
    lines = [l for l in out.strip().splitlines() if l.strip()]
    return lines[-1] if lines else "(no output)"


def _died_by_signal(rc):
    """True if a trusted tool was killed by a signal rather than exiting on its own verdict.

    A SIGSEGV in the comparator or an OOM SIGKILL is an INFRASTRUCTURE fault; blaming it on the
    contestant ("your proof is invalid") would put a false rejection on the leaderboard. Python
    reports a raw negative code, while `lake env` launders it into the shell's 128+N convention."""
    if not isinstance(rc, int):
        return False
    return rc < 0 or 128 < rc <= 192


def _resolve_lean_runtime(work, env):
    """Resolve the pinned Lean binary/sysroot before any contestant elaboration runs."""
    rc, out = run(["lake", "env", "lean", "--print-prefix"], work, env, AUDIT_TIMEOUT)
    if rc == "timeout":
        raise InfraError("timed out while resolving the pinned Lean runtime")
    if rc != 0:
        raise InfraError(f"cannot resolve the pinned Lean runtime: {last_line(out)}")
    prefix = Path(last_line(out))
    lean_bin = prefix / "bin" / "lean"
    core_lib = prefix / "lib" / "lean"
    if not (prefix.is_absolute() and lean_bin.is_file() and core_lib.is_dir()):
        raise InfraError(f"invalid Lean runtime prefix returned by toolchain: {prefix}")
    return lean_bin, prefix, core_lib


def _verified_runtime_env(base_env, artifact_lib, lean_prefix, core_lib):
    """Environment for judge-owned modules importing the pinned comparator artifacts."""
    env = dict(base_env)
    env["LEAN_SYSROOT"] = str(lean_prefix)
    env["LEAN_PATH"] = os.pathsep.join((str(artifact_lib), str(core_lib)))
    env["PATH"] = os.pathsep.join((str(lean_prefix / "bin"), env["PATH"]))
    return env


def _audit_tree(base: Path, roots):
    """Audit `roots` (files/dirs) under `base`: no symlinks, regular .lean files only,
    within `base`, under size/count caps. Used on the assembled workspace so a symlink
    swapped in after the pre-copy check cannot survive."""
    base_real = base.resolve(strict=True)
    total = count = 0
    stack = list(roots)
    while stack:
        p = stack.pop()
        if not p.exists() and not p.is_symlink():
            continue
        if p.is_symlink():
            raise SubmissionError(f"submission: symlinks are not allowed ({p.name})")
        rp = p.resolve(strict=True)
        if rp != base_real and not str(rp).startswith(str(base_real) + os.sep):
            raise SubmissionError(f"submission: path escapes workspace ({p})")
        if p.is_dir():
            stack.extend(p.iterdir())
            continue
        if not p.is_file():
            raise SubmissionError(f"submission: not a regular file ({p.name})")
        if p.suffix not in ("", ".lean"):
            raise SubmissionError(f"submission: only .lean files allowed ({p.name})")
        count += 1
        total += p.stat().st_size
        if count > MAX_SUBMISSION_FILES:
            raise SubmissionError(f"submission: too many files (> {MAX_SUBMISSION_FILES})")
        if total > MAX_SUBMISSION_BYTES:
            raise SubmissionError(f"submission: payload too large (> {MAX_SUBMISSION_BYTES} bytes)")


def _chmod_tree(path, dir_mode, file_mode):
    for root, dirs, files in os.walk(path):
        for name in files:
            try: os.chmod(os.path.join(root, name), file_mode)
            except OSError: pass
        for name in dirs:
            try: os.chmod(os.path.join(root, name), dir_mode)
            except OSError: pass
    try: os.chmod(path, dir_mode)
    except OSError: pass


def freeze_readonly(path):
    _chmod_tree(path, 0o555, 0o444)


def thaw(path):
    _chmod_tree(path, 0o755, 0o644)


def _preflight_payload(sd: Path):
    """Validate the contestant's SOURCE payload before a single byte is copied.

    Two reasons this runs on the source rather than (only) the assembled tree:
      * a special file (FIFO/socket/device) makes `shutil.copytree` raise a bare `shutil.Error`
        that escapes as an infra `error` + exit 2, so the caller requeues a submission that can
        never succeed. It is the contestant's payload → SubmissionError → `rejected`.
      * the size/count caps otherwise apply only AFTER the whole tree is on disk, so the copy cost
        is proportional to whatever was supplied instead of to the configured cap.
    """
    total = count = 0
    stack = [sd / "Submission.lean"]
    sub = sd / "Submission"
    if sub.exists() or sub.is_symlink():
        stack.append(sub)
    while stack:
        p = stack.pop()
        try:
            if p.is_symlink():                    # audited later on the assembled tree
                continue
            if not p.exists():
                continue
            st = p.stat()
            if p.is_dir():
                stack.extend(p.iterdir())
                continue
            if not stat.S_ISREG(st.st_mode):
                raise SubmissionError(
                    f"submission: only regular files are allowed ({p.name} is a special file)")
            count += 1
            total += st.st_size
            if count > MAX_SUBMISSION_FILES:
                raise SubmissionError(f"submission: too many files (> {MAX_SUBMISSION_FILES})")
            if total > MAX_SUBMISSION_BYTES:
                raise SubmissionError(
                    f"submission: payload too large (> {MAX_SUBMISSION_BYTES} bytes)")
        except OSError as e:
            raise SubmissionError(f"submission: unreadable payload entry ({e})")


def assemble(job_dir: Path, problem, submission_dir):
    prob_dir = PROBLEMS / problem
    if not (prob_dir / "config.json").exists():
        raise InfraError(f"unknown problem '{problem}'")
    sd = Path(submission_dir)
    if (sd / "Submission.lean").is_symlink() or not (sd / "Submission.lean").is_file():
        raise SubmissionError(f"submission '{submission_dir}' has no regular Submission.lean")

    # Pre-flight the SOURCE payload before writing anything: reject special files (FIFO/socket/
    # device — a bare shutil.Error would otherwise escape as an infra `error`, i.e. exit 2, and the
    # caller would requeue a submission that can never succeed) and stop at the caps instead of
    # copying an arbitrarily large tree first and only then rejecting it.
    _preflight_payload(sd)

    work = job_dir / "workspace"
    # Copy the locked template (preserve any symlink AS a symlink; there are none, but
    # never silently follow one).
    shutil.copytree(prob_dir, work, symlinks=True,
                    ignore=shutil.ignore_patterns(".lake", "lake-manifest.json"))
    # Overlay contestant files, preserving symlinks as symlinks (do NOT follow them).
    try:
        shutil.copy(sd / "Submission.lean", work / "Submission.lean", follow_symlinks=False)
        if (sd / "Submission").exists():
            shutil.rmtree(work / "Submission", ignore_errors=True)
            shutil.copytree(sd / "Submission", work / "Submission", symlinks=True)
    except (shutil.Error, OSError) as e:
        # Contestant's payload is at fault → rejected (exit 0), never an infra retry loop.
        raise SubmissionError(f"submission: unreadable or special file in payload ({e})")
    # Re-audit the ASSEMBLED contestant files (closes validate→copy TOCTOU).
    roots = [work / "Submission.lean"]
    if (work / "Submission").exists():
        roots.append(work / "Submission")
    _audit_tree(work, roots)
    return work


def _measurement_boundary(target):
    if target is None:
        return FULL_REPLAY_BOUNDARY
    if not isinstance(target, str) or not target or any(ch.isspace() for ch in target):
        raise InfraError(f"invalid timer target {target!r}")
    return TARGET_REPLAY_BOUNDARY


def _measurement_contract_record():
    """Machine-readable contract committed into verdicts and evaluation cohorts."""
    return {
        "id": MEASUREMENT_CONTRACT,
        "correctness_boundary": FULL_REPLAY_BOUNDARY,
        "performance_boundary": TARGET_REPLAY_BOUNDARY,
        "target_proof_encoding": TARGET_PROOF_ENCODING,
        "wall_clock_source": "timer-internal-monotonic-ns",
        "perf_counter_control": "perf-delay-minus-one+timer-prctl",
        "local_protocol": "local-v2",
        "remote_protocol": "KTP/2",
        "timeout_scope": PROCESS_TIMEOUT_SCOPE,
    }


def _timeout_measurement(target, source):
    return {
        "measurement_contract": MEASUREMENT_CONTRACT,
        "measurement_boundary": _measurement_boundary(target),
        "measurement_target": target,
        "timeout_scope": PROCESS_TIMEOUT_SCOPE,
        "timeout_source": source,
    }


def _parse_timer_measurement(out, target):
    """Parse the one fail-closed timer-kernel v2 measurement record."""
    records = [
        line[len(_TIMER_TIMING_PREFIX):]
        for line in out.splitlines()
        if line.startswith(_TIMER_TIMING_PREFIX)
    ]
    if len(records) != 1:
        raise InfraError(
            f"timer emitted {len(records)} measurement records (expected exactly one)")
    try:
        data = json.loads(records[0])
    except json.JSONDecodeError as e:
        raise InfraError(f"timer emitted malformed measurement JSON: {e.msg}")
    expected_keys = {
        "measurement_contract", "boundary", "target", "wall_ns", "phase",
    }
    if not isinstance(data, dict) or set(data) != expected_keys:
        raise InfraError("timer measurement record has an incompatible schema")
    if data["measurement_contract"] != MEASUREMENT_CONTRACT:
        raise InfraError(
            f"timer measurement contract mismatch ({data['measurement_contract']!r})")
    expected_boundary = _measurement_boundary(target)
    if data["boundary"] != expected_boundary:
        raise InfraError(
            f"timer measurement boundary mismatch ({data['boundary']!r})")
    if data["target"] != target:
        raise InfraError(f"timer measurement target mismatch ({data['target']!r})")
    if data["phase"] != "complete":
        raise InfraError(f"timer measurement did not complete ({data['phase']!r})")
    if type(data["wall_ns"]) is not int or data["wall_ns"] <= 0:
        raise InfraError("timer measurement wall_ns must be a positive integer")
    return data


def _timer_command(export_file, target):
    cmd = [str(TIMER)]
    if target is not None:
        _measurement_boundary(target)  # validate before it reaches argv
        cmd += ["--target", target]
    return cmd + [str(export_file)]


def _time_replay(export_file, work, env, timeout, target=None):
    """One full-closure or explicit-target replay.

    The trusted timer emits the replay-only monotonic wall duration. On Linux, `perf -D -1`
    starts counters disabled and timer-kernel enables them only around the selected replay.
    The outer watchdog still includes untimed preparation; timeout metadata says so explicitly.
    Returns (rc, out, sample_dict).
    """
    timer_cmd = _timer_command(export_file, target)
    if TIMING_METRIC == "perf_instructions":
        perf = shutil.which("perf", path=env.get("PATH", ""))
        if not perf:
            raise InfraError("metric=perf_instructions but `perf` not found — requires the Linux eval host")
        perf_out = export_file.parent / "perf.txt"
        try:
            perf_out.unlink(missing_ok=True)
        except OSError as e:
            raise InfraError(f"cannot clear stale perf output: {e}")
        cmd = [perf, "stat", "-D", "-1", "-o", str(perf_out), "-x", ",",
               "-e", "instructions,task-clock", "--", *timer_cmd]
        rc, out = run(cmd, work, env, timeout)
        if rc == "timeout":
            return rc, out, _timeout_measurement(target, "local-process-watchdog")
        if rc != 0:
            return rc, out, {}
        measured = _parse_timer_measurement(out, target)
        insns = task_clock = None
        try:
            for line in perf_out.read_text().splitlines():
                f = line.split(",")
                if len(f) >= 3 and f[0] not in ("", "<not counted>", "<not supported>"):
                    if f[2] == "instructions":
                        insns = int(float(f[0]))
                    elif f[2] == "task-clock":
                        task_clock = float(f[0])  # msec
        except OSError:
            pass
        if insns is None:
            raise InfraError("perf produced no instruction count (PMU unavailable in this container?)")
        return rc, out, {
            "instructions": insns,
            "task_clock_ms": task_clock,
            "wall_ns": measured["wall_ns"],
            "wall_s": measured["wall_ns"] / 1_000_000_000,
            "measurement_contract": MEASUREMENT_CONTRACT,
            "measurement_boundary": measured["boundary"],
            "measurement_target": target,
        }
    else:
        rc, out = run(timer_cmd, work, env, timeout)
        if rc == "timeout":
            return rc, out, _timeout_measurement(target, "local-process-watchdog")
        if rc != 0:
            return rc, out, {}
        measured = _parse_timer_measurement(out, target)
        return rc, out, {
            "wall_ns": measured["wall_ns"],
            "wall_s": measured["wall_ns"] / 1_000_000_000,
            "measurement_contract": MEASUREMENT_CONTRACT,
            "measurement_boundary": measured["boundary"],
            "measurement_target": target,
        }


def _remote_response_error(data, reps, target=None):
    """Return None for a usable KTP/2 response, otherwise a concise schema error."""
    if not isinstance(data, dict):
        return "response is not a JSON object"
    expected_boundary = _measurement_boundary(target)
    if data.get("measurement_contract") != MEASUREMENT_CONTRACT:
        return "missing/mismatched measurement contract"
    if data.get("boundary") != expected_boundary:
        return "missing/mismatched measurement boundary"
    if "target" not in data or data["target"] != target:
        return "missing/mismatched measurement target"
    status = data.get("status")
    if status not in ("ok", "timeout", "failed"):
        return f"unrecognized status {status!r}"
    executor = data.get("executor")
    version = data.get("version")
    if not isinstance(executor, str) or not executor.strip():
        return "missing/invalid executor identity"
    if not isinstance(version, str) or not version.strip():
        return "missing/invalid executor version"
    if status != "ok":
        return None
    samples = data.get("samples")
    if not isinstance(samples, list) or len(samples) != reps:
        return f"expected exactly {reps} samples"
    for idx, sample in enumerate(samples):
        if not isinstance(sample, dict):
            return f"sample {idx} is not an object"
        instructions = sample.get("instructions")
        if type(instructions) is not int or instructions <= 0:
            return f"sample {idx} instructions must be a positive integer"
        wall_ns = sample.get("wall_ns")
        if wall_ns is not None and (type(wall_ns) is not int or wall_ns <= 0):
            return f"sample {idx} wall_ns must be a positive integer"
        task_clock = sample.get("task_clock_ms")
        if (task_clock is not None
                and (isinstance(task_clock, bool)
                     or not isinstance(task_clock, (int, float))
                     or not math.isfinite(task_clock)
                     or task_clock <= 0)):
            return f"sample {idx} task_clock_ms must be a positive finite number"
    return None


def _time_remote(export_file, reps, target=None):
    """Run all timing reps on a remote KTP/2 executor (lean-timer-executor).

    Returns the executor's decoded 200 response: {"status": "ok", "samples":
    [{"instructions": …, "task_clock_ms": …}, …]} or a terminal
    {"status": "timeout"|"failed", …}. Anything that prevents obtaining a 200
    (connection failure, 5xx, auth/param 4xx, undecodable body) is treated as
    "executor unavailable": every URL is tried per attempt, attempts are
    separated by short sleeps, and exhaustion raises TimingRetry — never an
    error verdict, so an executor outage can only delay a score, not destroy
    a submission."""
    export_bytes = export_file.read_bytes()
    digest = hashlib.sha256(export_bytes).hexdigest()
    # Budget: the executor holds the connection for the whole job.
    request_timeout = reps * TIMING_TIMEOUT + 120
    last_err = "no executor URLs configured"
    # Restrict to the pinned node once one has served this submission (else the full list).
    urls = [_PINNED_EXECUTOR[0]] if _PINNED_EXECUTOR[0] else TIMING_EXECUTOR_URLS
    for sleep_s in _EXECUTOR_ATTEMPT_SLEEPS:
        if sleep_s:
            time.sleep(sleep_s)
        for base in urls:
            boundary = _measurement_boundary(target)
            query = urllib.parse.urlencode({
                "reps": reps,
                "timeout_secs": TIMING_TIMEOUT,
                "measurement_contract": MEASUREMENT_CONTRACT,
                "boundary": boundary,
                "target": target or "",
            })
            url = f"{base}/ktp/v2/time?{query}"
            req = urllib.request.Request(url, data=export_bytes, method="POST", headers={
                "Authorization": f"Bearer {TIMING_EXECUTOR_SECRET}",
                "Content-Type": "application/octet-stream",
                "X-Export-SHA256": digest,
                "X-Measurement-Contract": MEASUREMENT_CONTRACT,
                "X-Measurement-Boundary": boundary,
                "X-Measurement-Target": target or "",
            })
            try:
                with urllib.request.urlopen(req, timeout=request_timeout) as resp:
                    body = resp.read()
                data = json.loads(body)
                schema_error = _remote_response_error(data, reps, target)
                if schema_error is not None:
                    last_err = f"{base}: invalid executor response ({schema_error})"
                    continue
                identity = (data["executor"], data["version"])
                pinned_identity = _PINNED_EXECUTOR_IDENTITY[0]
                if pinned_identity is not None and identity != pinned_identity:
                    last_err = (
                        f"{base}: executor identity changed from "
                        f"{pinned_identity[0]}/{pinned_identity[1]} to "
                        f"{identity[0]}/{identity[1]}")
                    continue
                # Pin only after the entire response is validated. A malformed `status=ok`
                # therefore cannot capture the submission and suppress a healthy standby.
                _PINNED_EXECUTOR[0] = base
                _PINNED_EXECUTOR_IDENTITY[0] = identity
                data["executor_url"] = base
                return data
            except urllib.error.HTTPError as e:
                # Auth/param 4xx and executor 5xx alike: a misconfiguration is
                # an operator problem to fix, not a reason to void the
                # submission — keep it queued and visible in logs.
                detail = ""
                try:
                    detail = e.read(300).decode(errors="replace")
                except Exception:
                    pass
                last_err = f"{base}: HTTP {e.code} {detail}".strip()
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                last_err = f"{base}: {e}"
            print(f"timing executor unavailable: {last_err}", file=sys.stderr)
    raise TimingRetry(f"all timing executors unavailable (last: {last_err})")


# Reference value v = impl n by KERNEL-side reduction (Meta `whnf`), NOT compiled `#eval`.
# `#eval` runs codegen output, which can be exponential even when the kernel reduction is
# cheap (the naive fib spec compiles to an exponential tree but reduces via `brecOn` in
# linear kernel time) — so a submission fast in the kernel could be un-evaluable by #eval.
# whnf reduces the same way the timed replay will, handling Nat and Int results. A wrong v
# cannot mis-score: the kernel-reduced proof in _perf_export would then fail to build.
_VALUE_META = r"""import Submission
import Lean
open Lean Meta
set_option maxRecDepth 4000000
set_option maxHeartbeats 0
run_meta do
  let e0 ← whnf (mkApp (mkConst ``Submission.impl) (mkNatLit __N__))
  match e0 with
  | .lit (.natVal v) => IO.println s!"VALUE={v}"
  | .app (.const ``Int.ofNat _) a =>
    match (← whnf a) with
    | .lit (.natVal v) => IO.println s!"VALUE={v}"
    | _ => IO.println "NONLIT"
  | .app (.const ``Int.negSucc _) a =>
    match (← whnf a) with
    | .lit (.natVal v) => IO.println s!"VALUE=-{v + 1}"
    | _ => IO.println "NONLIT"
  | _ => IO.println "NONLIT"
"""


def _eval_impl_value(work, env, n, timeout, lean_bin="lean"):
    """Reduce `impl n` to a literal via the kernel-side oracle above. Returns (kind, payload):
    ('ok', v) with v a decimal string; ('timeout', None) only when the real wall-clock budget
    expires; ('error', tail) for every deterministic Lean/oracle failure. Heartbeats are disabled
    in _VALUE_META so the process timeout is the oracle's sole computation budget."""
    (work / "EvalVal.lean").write_text(_VALUE_META.replace("__N__", str(n)))
    rc, out = run([str(lean_bin), "EvalVal.lean"], work, env, timeout)
    if rc == "timeout":
        return "timeout", None
    if rc != 0:
        return "error", last_line(out)
    for line in out.splitlines():
        if line.startswith("VALUE="):
            value = line[6:].strip()
            if re.fullmatch(r"-?(0|[1-9][0-9]*)", value):
                return "ok", value
            return "error", f"value oracle produced an invalid integer literal ({value!r})"
    return "error", "value oracle produced no literal (NONLIT)"


def _perf_theorem_source(n, v, nonce):
    """Return (Lean source, fully-qualified theorem name) for one generated timing theorem.

    The namespace suffix includes a per-job nonce (normally the random export path), so an
    imported contestant declaration cannot collide with the generated theorem's global name.
    """
    token = hashlib.sha256(f"{nonce}\0{n}\0{v}".encode()).hexdigest()[:24]
    namespace = f"LeanKernelChallengeJudge.Generated_{token}"
    theorem = f"{namespace}.check"
    source = (
        "import Submission\n"
        "set_option maxRecDepth 4000000\n"
        "set_option maxHeartbeats 0\n"
        f"namespace {namespace}\n"
        f"theorem check : Submission.impl {n} = {v} :=\n"
        f"  of_decide_eq_true "
        f"(rfl : decide (Submission.impl {n} = {v}) = true)\n"
        f"end {namespace}\n"
    )
    return source, theorem


def _perf_export(work, env, n, v, out_path, timeout, artifact_lib, lean_bin):
    """Build and export a uniquely namespaced, directly reducible `impl n = v` theorem.

    The direct `of_decide_eq_true rfl` term deliberately avoids tactic proof extraction:
    the exported target declaration itself contains the computation instead of merely
    referring to an untimed private `_proof_...` theorem. Its kernel replay re-checks
    `decide (impl n = v) = true` by reduction,
    which forces the kernel to reduce `impl n` at this specific n — so timing the replay
    times the COMPUTATION at n, not the ∀n correctness proof. Returns
    (kind, error, fully_qualified_theorem): 'ok';
    'timeout' when this slot's build/export is too slow; or 'error' for a
    non-timeout build/export failure — which includes a wrong reference `v` (the direct proof
    then fails to prove `impl n = v` *deterministically*, so it is errored, not scored). The
    caller records only wall-clock timeouts as unsuccessful slots and continues with later
    slots; a wrong value fails deterministically far inside the timing budget, so it never
    reaches that timeout path in practice."""
    source, theorem = _perf_theorem_source(n, v, out_path)
    (work / "Perf.lean").write_text(source)
    perf_olean = artifact_lib / "Perf.olean"
    if perf_olean.exists():
        try:
            perf_olean.chmod(0o644)
            perf_olean.unlink()
        except OSError as e:
            return "error", f"cannot replace generated Perf.olean at n={n}: {e}", theorem
    # Compile only the judge-owned theorem. `import Submission` resolves to the byte-pinned
    # comparator artifact; no contestant source is re-elaborated in the performance phase.
    rc, out = run(
        [str(lean_bin), "-o", str(perf_olean), "Perf.lean"],
        work, env, timeout)
    if rc == "timeout":
        # This build timeout is distinct from the later timer process watchdog.
        return "timeout", None, theorem
    if rc != 0:
        # The oracle already produced a value, so the build should succeed. Any DETERMINISTIC
        # failure is a fault, never a timeout: a wrong value makes `decide` false (and its deep
        # Decidable comparison of a huge literal blows maxRecDepth), while a correct value reduces
        # in the kernel without hitting maxRecDepth. So a wrong oracle value can never be scored —
        # it surfaces here as an error, even at large n (closing the maxRecDepth-masking hole).
        return "error", f"perf build failed at n={n}: {last_line(out)}", theorem
    rc, out = run([str(LEAN4EXPORT_BIN / "lean4export"), "Perf", "--", theorem],
                  work, env, timeout, stdout_path=out_path)
    if rc == "timeout":
        return "timeout", None, theorem
    if rc != 0:
        return "error", f"perf export failed at n={n}: {last_line(out)}", theorem
    if not out_path.exists() or out_path.stat().st_size == 0:
        return "error", f"perf export produced no output at n={n}", theorem
    return "ok", None, theorem


def _submission_digest(work):
    """SHA-256 over the contestant's Submission.lean and Submission/ contents (by relative
    path), so the perf phase can prove the `impl` it times is byte-identical to the one
    comparator verified `impl_correct : ∀n` against — an axiom-clean but different impl,
    swapped in after verification, has a different digest and is rejected as a fault."""
    h = hashlib.sha256()
    paths = [work / "Submission.lean"]
    subdir = work / "Submission"
    if subdir.is_dir():
        paths += sorted((p for p in subdir.rglob("*") if p.is_file()),
                        key=lambda p: p.relative_to(work).as_posix())
    for p in paths:
        h.update(p.relative_to(work).as_posix().encode() + b"\0")
        try:
            h.update(p.read_bytes())
        except OSError as e:
            # Fail closed: an unreadable submission file cannot be bound, so it must not hash
            # to a fixed sentinel that a mutated tree could reproduce.
            raise InfraError(f"cannot read submission file '{p.name}' for identity binding: {e}")
        h.update(b"\0")
    return h.hexdigest()


def _pin_export_bytes(path):
    """Read and make an export read-only; callers compare these exact bytes after each consumer."""
    try:
        pinned = path.read_bytes()
        path.chmod(0o444)
        return pinned
    except OSError as e:
        raise InfraError(f"cannot pin export '{path.name}': {e}")


def _export_matches(path, pinned):
    try:
        return path.read_bytes() == pinned
    except OSError as e:
        raise InfraError(f"cannot re-read pinned export '{path.name}': {e}")


def _snapshot_verified_artifacts(work):
    """Pin the `.olean` graph that produced the comparator-verified export.

    Performance checks import this graph directly; they never re-elaborate Submission source.
    That matters because elaboration can depend on environment, time, or filesystem state even
    when the source digest is unchanged.
    """
    lib = work / ".lake" / "build" / "lib" / "lean"
    if not lib.is_dir():
        raise InfraError("comparator accepted but produced no Lean build artifact directory")
    # These names are judge-owned scratch modules, never contestant modules.
    for name in ("Perf.olean", "EvalVal.olean"):
        path = lib / name
        if path.exists():
            try:
                path.chmod(0o644)
                path.unlink()
            except OSError as e:
                raise InfraError(f"cannot clear stale generated artifact '{name}': {e}")

    files = sorted(lib.rglob("*.olean"), key=lambda p: p.relative_to(lib).as_posix())
    if not files or not (lib / "Submission.olean").is_file():
        raise InfraError("comparator accepted but emitted no Submission.olean")
    snapshot = {}
    digest = hashlib.sha256()
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise InfraError(f"invalid verified build artifact '{path.name}'")
        rel = path.relative_to(lib).as_posix()
        try:
            payload = path.read_bytes()
            path.chmod(0o444)
        except OSError as e:
            raise InfraError(f"cannot pin verified build artifact '{rel}': {e}")
        snapshot[rel] = payload
        digest.update(rel.encode() + b"\0" + payload + b"\0")
    return lib, snapshot, digest.hexdigest()


def _artifacts_match(lib, snapshot):
    for rel, payload in snapshot.items():
        path = lib / rel
        try:
            if path.is_symlink() or path.read_bytes() != payload:
                return False
        except OSError:
            return False
    return True


def _prepare_generated_workspace(work, artifact_lib):
    """Open only the directories/files needed for judge-generated modules.

    Verified `.olean` files stay read-only and byte-pinned. The root and artifact directory
    must be writable so Lean can receive EvalVal.lean/Perf.lean and the generated Perf.olean.
    """
    for path in (
        work,
        work / ".lake",
        work / ".lake" / "build",
        work / ".lake" / "build" / "lib",
        artifact_lib,
    ):
        try:
            path.chmod(0o755)
        except OSError as e:
            raise InfraError(f"cannot prepare generated-module directory '{path.name}': {e}")
    for name in ("EvalVal.lean", "Perf.lean"):
        path = work / name
        if path.exists():
            try:
                path.chmod(0o644)
            except OSError as e:
                raise InfraError(f"cannot prepare generated source '{name}': {e}")


def _summarize_samples(samples, metric=None):
    metric = metric or TIMING_METRIC
    if metric == "perf_instructions":
        insns = [s["instructions"] for s in samples]
        median = statistics.median(insns)
        # Instruction counts are integral. Round .5 upward instead of Python's banker's round.
        return {"median_instructions": int(math.floor(median + 0.5))}
    # Preserve the timer's nanosecond resolution. Target-only checks can complete well below
    # one millisecond, so the old three-decimal rounding could turn valid samples into score 0.
    median_ns = statistics.median([s["wall_ns"] for s in samples])
    return {
        "median_wall_ns": median_ns,
        "median_s": median_ns / 1_000_000_000,
    }


def _coverage_fields(inputs, scaling):
    completed = [row for row in scaling if row.get("result") == "ok"]
    total = len(inputs)
    return {
        "successful_slots": len(completed),
        "total_slots": total,
        "coverage": (len(completed) / total) if total else 0.0,
    }


def _headline_row(scaling):
    completed = [row for row in scaling if row.get("result") == "ok"]
    return max(completed, key=lambda row: row["n"]) if completed else None


def _collect_perf_slots(inputs, probe, deadline=None):
    """Probe every configured slot unless a deterministic fatal error is returned.

    `probe(n)` returns `(row, error)`. Timeout rows carry no error and therefore never suppress
    later inputs; a deterministic fault returns an error and terminates the curve.

    `deadline` (monotonic seconds) bounds the WHOLE performance phase. Per-step timeouts alone let
    one submission hold a judge slot for hours, because every failing slot may burn the full timing
    budget and every slot is probed. On exhaustion the remaining slots are recorded as
    `budget-exhausted` and the verdict is still emitted normally (a partial curve, not an error).
    """
    scaling = []
    for slot, n in enumerate(inputs):
        if deadline is not None and time.monotonic() >= deadline:
            for later_slot, later_n in enumerate(inputs[slot:], start=slot):
                scaling.append({"slot": later_slot, "n": later_n, "result": "budget-exhausted"})
            return scaling, None
        row, error = probe(n)
        if row is not None:
            row = {"slot": slot, **row}
            scaling.append(row)
        if error is not None:
            for later_slot, later_n in enumerate(inputs[slot + 1:], start=slot + 1):
                scaling.append({"slot": later_slot, "n": later_n, "result": "not-run"})
            return scaling, error
    return scaling, None


def _canonical_work(correctness_timing, scaling, metric=None):
    """Structured work components; ranking/aggregation is intentionally left to scoring."""
    metric = metric or TIMING_METRIC
    key = "median_instructions" if metric == "perf_instructions" else "median_s"
    if correctness_timing.get("result") != "ok" or correctness_timing.get(key) is None:
        return None
    curve_values = [
        row[key] for row in scaling
        if row.get("result") == "ok" and row.get(key) is not None
    ]
    correctness = correctness_timing[key]
    curve_sum = sum(curve_values)
    return {
        "metric": metric,
        "correctness_median": correctness,
        "completed_curve_sum": curve_sum,
        "total": correctness + curve_sum,
        "completed_slots": len(curve_values),
    }


def _evaluation_cohort(problem, cfg, inputs, reps, result):
    """Return the public comparison cohort recorded in every current verdict.

    The round label is operator supplied. The derived id additionally commits to the exact
    schedule, metric, repetitions, budgets, toolchain, and timing executor identity, preventing
    the scorer from silently mixing results that were not measured under one contract.
    """
    round_id = EVALUATION_COHORT or "local-dev"
    executor = result.get("stages", {}).get("timing_executor") or {
        "executor": "local",
        "version": "fixed-host",
    }
    policy = {
        "round": round_id,
        "problem": problem,
        "perf": cfg.get("perf"),
        "perf_defaults": _PERF_DEFAULTS,
        "inputs": inputs,
        "metric": TIMING_METRIC,
        "reps": reps,
        "timing_timeout_seconds": TIMING_TIMEOUT,
        "toolchain": _CFG.get("toolchain"),
        "checker": CHECKER_ID,
        "timing_protocol": result.get("timing_protocol"),
        "measurement_contract": _measurement_contract_record(),
        "executor": executor,
    }
    encoded = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()
    return {
        "id": hashlib.sha256(encoded).hexdigest()[:24],
        "round": round_id,
        "executor": executor,
        "policy_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def judge(job_dir: Path, problem, submission_dir, reps, tag):
    sub_name = tag or Path(submission_dir).name
    timing_protocol = (
        "KTP/2"
        if TIMING_METRIC == "perf_instructions" and TIMING_EXECUTOR_URLS
        else "local-v2"
    )
    result = {"problem": problem, "submission": sub_name,
              "status": None, "reason": None, "metric": TIMING_METRIC, "stages": {},
              "timing_protocol": timing_protocol,
              "measurement_contract": _measurement_contract_record()}

    def finish():
        outdir = RESULTS / problem
        outdir.mkdir(parents=True, exist_ok=True)
        # atomic write so a concurrent reader never sees a half-written verdict
        fd, tmp = tempfile.mkstemp(dir=outdir, suffix=".json.tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(result, f, indent=2)
        os.replace(tmp, outdir / f"{sub_name}.json")
        icon = {"accepted": "✅", "rejected": "❌", "error": "💥"}[result["status"]]
        sc = result.get("score")
        print(f"{icon} {problem}/{sub_name}: {result['status']}"
              + (f" — {result['reason']}" if result["reason"] else "")
              + (f" — {sc}" if sc else ""))
        return 0 if result["status"] in ("accepted", "rejected") else 2

    # A process normally judges one submission, but resetting here also makes repeated in-process
    # invocations safe: executor identity must never leak from a prior job.
    _PINNED_EXECUTOR[0] = None
    _PINNED_EXECUTOR_IDENTITY[0] = None
    if _official_eval() and not PERF_SEED:
        raise InfraError("official evaluation requires a nonempty PERF_SEED")
    if OFFICIAL_EVAL and _PERF_SEED_SOURCE[0] != "stdin":
        raise InfraError("official evaluation requires one-shot PERF_SEED stdin injection")
    if OFFICIAL_EVAL and not EVALUATION_COHORT:
        raise InfraError("official evaluation requires a nonempty EVALUATION_COHORT")

    # Fail-closed sandbox policy: production must have a real sandbox.
    env = tool_env()
    if SANDBOX_MODE == "container":
        # Tool presence proves nothing: `landrun` and SANDBOX_MODE=container are both baked into
        # the image, so a bare `docker run IMAGE judge.py ...` (no isolation flags at all) used to
        # pass this check. Demand EVIDENCE of the envelope instead.
        if not has_real_landrun(env):
            raise InfraError("sandbox.mode=container but no real landrun on PATH "
                             "(refusing to run unsandboxed)")
        reachable = _network_is_reachable()
        if reachable:
            raise InfraError("sandbox.mode=container but the network is reachable — the container "
                             "was started without --network none (refusing to run unsandboxed)")
        result["stages"]["sandbox"] = {"mode": SANDBOX_MODE, "network_reachable": reachable}
        if _official_eval() and not os.environ.get("ISOLATION_ATTESTATION"):
            # scripts/run_isolated.sh injects this after applying the full docker envelope; its
            # absence means the official job was not launched through the wrapper.
            raise InfraError("official evaluation must be launched via scripts/run_isolated.sh "
                             "(missing ISOLATION_ATTESTATION)")

    work = assemble(job_dir, problem, submission_dir)
    cfg = json.loads((PROBLEMS / problem / "config.json").read_text())
    axioms = cfg["permitted_axioms"]
    lean_bin, lean_prefix, core_lib = _resolve_lean_runtime(work, env)

    # Identity binding (1/2): pin the submission bytes BEFORE comparator reads them, so the
    # baseline is exactly what gets correctness-verified — not some post-verification state.
    verified_digest = _submission_digest(work)

    # ---- Comparator: correctness gate (statement match + axioms + kernel replay of ∀n) ----
    # The patched comparator writes the exact export it just verified (COMPARATOR_SOLUTION_EXPORT).
    # That export is the correctness artifact. The perf phase imports the exact byte-pinned
    # `.olean` graph that produced it, then separately builds and times judge-owned per-input
    # `impl n` exports. Source digests remain an additional mutation check.
    # A missing/uninstalled comparator is a DEPLOYMENT fault (→ infra error/exit 2), not a
    # contestant rejection: check explicitly so a nonzero exit isn't misread as "proof invalid".
    if not Path(COMPARATOR).exists():
        raise InfraError(f"comparator binary not found at {COMPARATOR} (run scripts/setup.sh)")
    export_file = job_dir / "solution.export.ndjson"
    cenv = dict(env, COMPARATOR_SOLUTION_EXPORT=str(export_file))
    t0 = time.monotonic()
    rc, out = run(["lake", "env", str(COMPARATOR), "config.json"], work, cenv, COMPARATOR_TIMEOUT)
    result["stages"]["comparator"] = {"exit": rc, "seconds": round(time.monotonic() - t0, 1),
                                      "tail": out[-3000:]}
    if rc == "timeout":
        result["status"], result["reason"] = "rejected", f"comparator timed out (> {COMPARATOR_TIMEOUT}s)"
        return finish()
    if _died_by_signal(rc):
        result["status"], result["reason"] = "error", \
            f"comparator killed by signal (exit {rc}) — infrastructure fault, not a proof failure"
        return finish()
    if rc != 0:
        result["status"], result["reason"] = "rejected", f"comparator: {last_line(out)}"
        return finish()
    if not export_file.exists() or export_file.stat().st_size == 0:
        result["status"], result["reason"] = "error", "comparator accepted but emitted no export (patched comparator required)"
        return finish()
    # Identity binding (2/2): the submission must be byte-identical to what comparator just
    # verified — catch any mutation a submission-spawned process (elaboration-time IO) made
    # DURING the build, before we freeze and reuse the workspace for timing.
    if _submission_digest(work) != verified_digest:
        result["status"], result["reason"] = "error", "submission changed during correctness verification"
        return finish()
    result["stages"]["export"] = {"source": "comparator-verified", "bytes": export_file.stat().st_size}
    correctness_export_bytes = _pin_export_bytes(export_file)
    artifact_lib, verified_artifacts, artifact_digest = _snapshot_verified_artifacts(work)
    verified_env = _verified_runtime_env(env, artifact_lib, lean_prefix, core_lib)
    result["stages"]["verified_artifacts"] = {
        "source": "comparator-build",
        "olean_files": len(verified_artifacts),
        "sha256": artifact_digest,
    }
    freeze_readonly(work)


    # ---- Axiom re-audit (R4): whitelisted axioms only, on the comparator-verified correctness
    # export (the per-input timed exports are separately re-audited in the perf loop below) ----
    rc, out = run([str(TIMER), "--check-axioms", ",".join(axioms), str(export_file)],
                  work, env, AUDIT_TIMEOUT)
    result["stages"]["axioms"] = {"exit": rc, "tail": last_line(out)}
    if not _export_matches(export_file, correctness_export_bytes):
        result["status"], result["reason"] = "error", "correctness export changed during axiom audit"
        return finish()
    if not _artifacts_match(artifact_lib, verified_artifacts):
        result["status"], result["reason"] = "error", \
            "comparator-verified build artifacts changed during axiom audit"
        return finish()
    if rc == "timeout":
        result["status"], result["reason"] = "error", "axiom re-audit timed out"
        return finish()
    if _died_by_signal(rc):
        result["status"], result["reason"] = "error", \
            f"axiom auditor killed by signal (exit {rc}) — infrastructure fault, not a rule violation"
        return finish()
    if rc != 0:
        result["status"], result["reason"] = "rejected", f"axiom audit: {last_line(out)}"
        return finish()

    def time_export(export_path, target=None):
        """Replay one export through the authoritative full or target-only boundary."""
        if TIMING_METRIC == "perf_instructions" and TIMING_EXECUTOR_URLS:
            remote = _time_remote(export_path, reps, target)      # may raise TimingRetry
            result["stages"].setdefault("timing_executor", {
                "executor": remote["executor"], "version": remote["version"]})
            if remote["status"] == "timeout":
                timeout_meta = _timeout_measurement(target, "remote-process-watchdog")
                if isinstance(remote.get("timeout_phase"), str):
                    timeout_meta["executor_timeout_phase"] = remote["timeout_phase"]
                return "timeout", timeout_meta
            if remote["status"] == "failed":
                return "failed", last_line(remote.get("output_tail", ""))
            samples = []
            for remote_sample in remote["samples"]:
                sample = {
                    "instructions": remote_sample["instructions"],
                    "task_clock_ms": remote_sample.get("task_clock_ms"),
                }
                if "wall_ns" in remote_sample:
                    sample["wall_ns"] = remote_sample["wall_ns"]
                    sample["wall_s"] = remote_sample["wall_ns"] / 1_000_000_000
                samples.append(sample)
            return "ok", samples

        samples = []
        for i in range(reps):
            trc, tout, sample = _time_replay(
                export_path, work, env, TIMING_TIMEOUT, target=target)
            if trc == "timeout":
                return "timeout", sample
            if trc != 0:
                return "failed", f"rep {i}: {last_line(tout)}"
            samples.append(sample)
        if TIMING_METRIC == "perf_instructions":
            if any(type(s.get("instructions")) is not int or s["instructions"] <= 0
                   for s in samples):
                raise InfraError("local perf produced a non-positive/non-integral instruction sample")
        return "ok", samples

    # Score the proof work too. This prevents a specialization table from appearing free merely
    # because its expensive closed-value proofs live in the already-verified correctness export.
    correctness_status, correctness_payload = time_export(export_file, target=None)
    if not _export_matches(export_file, correctness_export_bytes):
        result["status"], result["reason"] = "error", "correctness export changed during timing"
        return finish()
    if not _artifacts_match(artifact_lib, verified_artifacts):
        result["status"], result["reason"] = "error", \
            "comparator-verified build artifacts changed during correctness timing"
        return finish()
    correctness_timing = {
        "metric": TIMING_METRIC, "reps": reps, "result": correctness_status,
        "checker": CHECKER_ID,
        "measurement_contract": MEASUREMENT_CONTRACT,
        "measurement_boundary": FULL_REPLAY_BOUNDARY,
        "measurement_target": None,
    }
    if correctness_status == "ok":
        correctness_timing.update(_summarize_samples(correctness_payload))
    elif correctness_status == "timeout" and isinstance(correctness_payload, dict):
        correctness_timing.update(correctness_payload)
    elif correctness_status == "failed":
        result["correctness_timing"] = correctness_timing
        result["status"], result["reason"] = (
            "error", f"official kernel rejected correctness export: {correctness_payload}")
        return finish()
    result["correctness_timing"] = correctness_timing

    # ---- Performance: time the kernel reducing `impl n` at judge-chosen inputs ----
    # Correctness (the ∀n proof) was verified by comparator above. Here we time the
    # COMPUTATION, not the ∀n proof: for each input n we export `impl n = v` with a direct
    # `of_decide_eq_true rfl` proof, then time the kernel replaying THAT declaration. This
    # forces reduction of `impl n` at this n and yields the algorithm's scaling curve.
    # Reuse the exact comparator build graph. Re-elaborating identical source is not an identity
    # proof: run_meta/run_elab can depend on environment or filesystem state. Only judge-owned
    # EvalVal/Perf modules are compiled below, importing the pinned Submission.olean.
    _prepare_generated_workspace(work, artifact_lib)
    inputs = perf_inputs(cfg, problem)
    if not inputs:
        result["status"], result["reason"] = "error", f"no perf policy configured for '{problem}'"
        return finish()
    result["stages"]["perf_inputs"] = inputs
    result["evaluation_cohort"] = _evaluation_cohort(problem, cfg, inputs, reps, result)

    # A timeout occupies only its own configured slot. We still probe every later slot because a
    # valid implementation's reduction cost need not be monotone in n. Deterministic failures
    # remain fatal and can never be misread as a slow-but-valid point.
    def probe_point(n):
        if not _artifacts_match(artifact_lib, verified_artifacts):
            return {"n": n, "result": "identity-error"}, \
                f"comparator-verified build artifacts changed before n={n}"
        vkind, v = _eval_impl_value(work, verified_env, n, TIMING_TIMEOUT, lean_bin)
        if not _artifacts_match(artifact_lib, verified_artifacts):
            return {"n": n, "result": "identity-error"}, \
                f"comparator-verified build artifacts changed during value evaluation at n={n}"
        if vkind == "timeout":
            return {"n": n, "result": "value-eval-timeout"}, None
        if vkind == "error":
            return {"n": n, "result": "value-eval-error"}, f"value oracle failed at n={n}: {v}"
        # Identity binding: the impl we are about to build/time must be byte-identical to the
        # one comparator verified `impl_correct` against. A mismatch means the Submission was
        # modified after verification — a fault, never a score.
        if _submission_digest(work) != verified_digest:
            return {"n": n, "result": "identity-error"}, \
                f"submission changed after correctness verification (at n={n})"
        perf_export = job_dir / f"perf_{n}.export.ndjson"
        pkind, err, perf_target = _perf_export(
            work, verified_env, n, v, perf_export, TIMING_TIMEOUT, artifact_lib, lean_bin)
        if not _artifacts_match(artifact_lib, verified_artifacts):
            return {"n": n, "result": "identity-error"}, \
                f"comparator-verified build artifacts changed during perf build at n={n}"
        if pkind == "timeout":
            return {"n": n, "result": "build-timeout"}, None
        if pkind == "error":
            return {"n": n, "result": "build-error"}, err
        # Source is not re-elaborated, but a mutation during the generated theorem build is still
        # a fault and must be caught before the export is trusted and timed.
        if _submission_digest(work) != verified_digest:
            return {"n": n, "result": "identity-error"}, \
                f"submission changed during perf build (at n={n})"
        # Pin the exact export bytes and freeze the file, so the axiom audit and the (separate)
        # timing process provably run identical bytes — not different ones swapped in between.
        perf_bytes = _pin_export_bytes(perf_export)
        arc, aout = run([str(TIMER), "--check-axioms", ",".join(axioms), str(perf_export)],
                        work, env, AUDIT_TIMEOUT)
        if not _export_matches(perf_export, perf_bytes):
            return {"n": n, "result": "identity-error"}, \
                f"perf export changed during axiom audit (at n={n})"
        if not _artifacts_match(artifact_lib, verified_artifacts):
            return {"n": n, "result": "identity-error"}, \
                f"comparator-verified build artifacts changed during perf audit at n={n}"
        if arc == "timeout":
            return {"n": n, "result": "axiom-audit-timeout"}, None
        if arc != 0:
            return {"n": n, "result": "axiom-audit-error"}, \
                f"perf export axiom audit failed at n={n}: {last_line(aout)}"
        status, payload = time_export(perf_export, target=perf_target)
        if not _export_matches(perf_export, perf_bytes):
            return {"n": n, "result": "identity-error"}, \
                f"perf export changed during timing (at n={n})"
        if not _artifacts_match(artifact_lib, verified_artifacts):
            return {"n": n, "result": "identity-error"}, \
                f"comparator-verified build artifacts changed during perf timing at n={n}"
        if status == "failed":
            return {"n": n, "result": "timing-error"}, \
                f"official kernel rejected perf export at n={n}: {payload}"
        if status == "timeout":
            return {
                "n": n,
                "result": "timeout",
                "measurement_boundary": TARGET_REPLAY_BOUNDARY,
                "measurement_target": perf_target,
                **(payload if isinstance(payload, dict) else {}),
            }, None
        return {
            "n": n,
            "result": "ok",
            "measurement_contract": MEASUREMENT_CONTRACT,
            "measurement_boundary": TARGET_REPLAY_BOUNDARY,
            "measurement_target": perf_target,
            **_summarize_samples(payload),
        }, None

    perf_deadline = (time.monotonic() + PERF_PHASE_BUDGET) if PERF_PHASE_BUDGET else None
    scaling, perf_error = _collect_perf_slots(inputs, probe_point, perf_deadline)

    timing = {"metric": TIMING_METRIC, "reps": reps, "scaling": scaling,
              "checker": CHECKER_ID,
              "measurement_contract": MEASUREMENT_CONTRACT,
              "measurement_boundary": TARGET_REPLAY_BOUNDARY,
              **_coverage_fields(inputs, scaling)}
    canonical_work = _canonical_work(correctness_timing, scaling)
    if canonical_work is not None:
        result["canonical_work"] = canonical_work
    if perf_error is not None:
        result["timing"] = timing
        result["status"], result["reason"] = "error", perf_error
        return finish()

    # Correctness already passed, so the submission is ACCEPTED regardless of speed; the
    # scaling curve only determines the score. A submission too slow to complete even the
    # smallest input is accepted-but-unscored — slow is not a rejection (only incorrect,
    # illegal-axiom, or kernel-rejected exports are rejected, above).
    result["timing"] = timing
    result["status"] = "accepted"
    ok_rows = [r for r in scaling if r.get("result") == "ok"]
    if correctness_timing["result"] != "ok":
        result["reason"] = "unscored: correctness export did not complete in time"
    elif not ok_rows:
        result["reason"] = "unscored: did not complete any judge input in time"
    else:
        top = _headline_row(scaling)
        result["timing"]["headline_n"] = top["n"]
        if TIMING_METRIC == "perf_instructions":
            result["timing"]["median_instructions"] = top.get("median_instructions")
            result["score"] = (
                f"{len(ok_rows)}/{len(inputs)} slots; "
                f"{canonical_work['total']} total instructions")
        else:
            result["timing"]["median_s"] = top.get("median_s")
            result["score"] = (
                f"{len(ok_rows)}/{len(inputs)} slots; "
                f"{canonical_work['total']:.3f}s total replay")
    return finish()


def md_cell(s) -> str:
    """Escape an untrusted value for a single Markdown table cell."""
    s = str(s if s is not None else "")
    s = s.replace("\\", "\\\\").replace("|", "\\|")
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"[`<>\[\]]", "", s)
    return s[:160]


_SCORER_MODULE = [None]


def _canonical_scorer():
    """Load the one scoring implementation used by both CLI reports.

    Keeping the leaderboard on scripts/score.py's validator and rank key prevents a
    second, subtly different interpretation of the verdict schema from drifting in here.
    """
    if _SCORER_MODULE[0] is None:
        path = ROOT / "scripts" / "score.py"
        spec = importlib.util.spec_from_file_location("lean_kernel_challenge_score", path)
        if spec is None or spec.loader is None:
            raise InfraError(f"cannot load canonical scorer at {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SCORER_MODULE[0] = module
    return _SCORER_MODULE[0]


def _score_view(r):
    scorer = _canonical_scorer()
    metric = r.get("metric")
    if metric not in scorer.METRICS:
        return None
    view = scorer._score_row(r, metric)
    return view if view["scoreable"] else None


def _score_key(r):
    view = _score_view(r)
    return _canonical_scorer()._rank_key(view) if view is not None else None


# Human label + sort order for each metric; scores of different metrics are NOT comparable
# (wall seconds vs instruction counts), so the leaderboard ranks within a metric only.
_METRIC_LABEL = {"perf_instructions": "instructions", "wall_time": "wall seconds (dev)"}


def leaderboard():
    rows = []
    if not RESULTS.is_dir():          # fresh clone with no results/ yet — empty board, no crash
        print(f"no results yet at {RESULTS}")
        return
    for pdir in sorted(RESULTS.iterdir()):
        if not pdir.is_dir() or pdir.name in ("work", "plots"):
            continue
        for f in sorted(pdir.glob("*.json")):
            try:
                r = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            # Only rank official judge verdicts, identified by STRUCTURE (a legitimate submission
            # may be named e.g. "x.perf", so a filename-suffix filter would wrongly drop it).
            # Requiring every field prevents a KeyError on malformed or legacy diagnostic files.
            # Current perf_eval output delegates to this judge and is therefore canonical.
            if not (isinstance(r, dict)
                    and isinstance(r.get("problem"), str) and isinstance(r.get("submission"), str)
                    and isinstance(r.get("status"), str) and isinstance(r.get("stages"), dict)):
                continue
            rows.append(r)
    lines = ["# Lean Kernel Challenge — leaderboard (local dev)", ""]
    for problem in sorted({r["problem"] for r in rows}):
        lines.append(f"## {md_cell(problem)}")
        lines.append("")
        prows = [r for r in rows if r["problem"] == problem]
        accepted = [r for r in prows if r["status"] == "accepted"]

        # Coerce to a single sortable type: `.get(k, default)` only fills a MISSING key, so an
        # explicit "metric": null / cohort id null would leak None into a set that is later
        # sorted() alongside strings, raising TypeError. Force every key to a str.
        def _metric_key(r):
            m = r.get("metric")
            return m if isinstance(m, str) else "wall_time"

        def _cohort_key(r):
            c = r.get("evaluation_cohort")
            cid = c.get("id") if isinstance(c, dict) else None
            return cid if isinstance(cid, str) else "<missing>"

        # Rank within each metric separately — never mix seconds and instruction counts.
        metrics = sorted({_metric_key(r) for r in accepted})
        for metric in metrics:
            metric_rows = [r for r in accepted if _metric_key(r) == metric]
            cohort_ids = sorted({_cohort_key(r) for r in metric_rows})
            for cohort_id in cohort_ids:
                grp = [r for r in metric_rows if _cohort_key(r) == cohort_id]
                scorer = _canonical_scorer()
                ranked = []
                unscored = []
                for r in grp:
                    view = scorer._score_row(r, metric)
                    if view["scoreable"]:
                        ranked.append((r, view))
                    else:
                        unscored.append((r, view["reason"]))
                ranked.sort(key=lambda pair: scorer._rank_key(pair[1]))
                label = _METRIC_LABEL.get(metric, metric)
                lines.append(
                    f"**canonical {label} ranking — cohort `{md_cell(cohort_id)}`:** "
                    f"completed slots, coverage, harder-slot profile, then lower total replay work")
                lines.append("")
                lines.append("| rank | submission | coverage | total work | score |")
                lines.append("|---|---|---|---|---|")
                for i, (r, view) in enumerate(ranked, 1):
                    coverage = f"{view['completed_slots']}/{view['planned_slots']}"
                    total = scorer._format_work(view["total_work"], metric)
                    lines.append(
                        f"| {i} | {md_cell(r['submission'])} | {coverage} | "
                        f"{md_cell(total)} | {md_cell(r.get('score'))} |")
                lines.append("")
                if unscored:
                    lines.append("_accepted but unscored under the current scoring contract:_")
                    lines.append("")
                    for r, reason in unscored:
                        lines.append(
                            f"- {md_cell(r['submission'])} — "
                            f"{md_cell(reason or r.get('reason') or 'unscored')}")
                    lines.append("")
        other = [r for r in prows if r["status"] != "accepted"]
        if other:
            icons = {"rejected": "❌ rejected", "error": "💥 error", "retry": "⏳ retry"}
            lines.append("| submission | status | note |")
            lines.append("|---|---|---|")
            for r in other:
                icon = icons.get(r["status"], f"? {r['status']}")
                lines.append(f"| {md_cell(r['submission'])} | {icon} | {md_cell(r.get('reason'))} |")
            lines.append("")
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "leaderboard.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--problem", required=True)
    r.add_argument("--submission", required=True)
    r.add_argument("--reps", type=int, default=DEFAULT_REPS)
    r.add_argument("--tag")
    r.add_argument("--keep-workspace", action="store_true", help="don't delete the temp job dir (debug)")
    sub.add_parser("leaderboard")
    args = ap.parse_args()

    if args.cmd == "leaderboard":
        leaderboard()
        return

    problem, tag, sub_name = args.problem, args.tag, (args.tag or Path(args.submission).name)
    job_dir = None

    # An external kill (CI timeout, k8s eviction, operator SIGTERM) must not break the "always a
    # verdict" contract nor leak the job workspace: turn the signal into an exception so the
    # existing handler writes a `retry` verdict and `finally` thaws + removes the job dir.
    def _on_signal(signum, _frame):
        raise TimingRetry(f"judge terminated by signal {signum} before completing")

    for _sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(_sig, _on_signal)
        except (ValueError, OSError):
            pass

    try:
        _consume_perf_seed_stdin()
        if not valid_slug(problem):
            raise InfraError(f"invalid --problem slug '{problem}'")
        if not (PROBLEMS / problem / "config.json").exists():
            raise InfraError(f"unknown problem '{problem}' (not in problems/)")
        if tag is not None and not valid_slug(tag):
            raise InfraError(f"invalid --tag slug '{tag}'")
        if not valid_slug(sub_name):
            raise InfraError(f"submission name '{sub_name}' is not a safe slug; pass --tag")
        if args.reps < 1:
            raise InfraError(f"--reps must be >= 1 (got {args.reps})")
        if TIMING_METRIC not in ("wall_time", "perf_instructions"):
            raise InfraError(f"invalid TIMING_METRIC '{TIMING_METRIC}' "
                             "(must be 'wall_time' or 'perf_instructions')")
        (RESULTS / "work").mkdir(parents=True, exist_ok=True)
        job_dir = Path(tempfile.mkdtemp(dir=RESULTS / "work", prefix=f"{problem}__{sub_name}__"))
        sys.exit(judge(job_dir, problem, args.submission, args.reps, tag))
    except SubmissionError as e:
        # Contestant's fault (bad submission format) → a REJECTED verdict (exit 0), not an
        # infra error/retry, so an invalid submission is not requeued forever.
        _write_infra_verdict(problem, sub_name, f"submission format: {e}", status="rejected")
        print(f"❌ rejected: {e}", file=sys.stderr)
        sys.exit(0)
    except TimingRetry as e:
        _write_infra_verdict(problem, sub_name, f"retry: {e}", status="retry")
        print(f"⏳ timing deferred: {e}", file=sys.stderr)
        sys.exit(3)
    except InfraError as e:
        _write_infra_verdict(problem, sub_name, f"infra: {e}")
        print(f"💥 infra error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        # Catch-all: any unexpected error (OSError, ValueError from perf parsing,
        # schema issues, …) still yields a verdict + exit 2, never a bare traceback.
        _write_infra_verdict(problem, sub_name, f"unexpected {type(e).__name__}: {e}")
        print(f"💥 unexpected infra error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)
    finally:
        if job_dir is not None and job_dir.exists() and not args.keep_workspace:
            thaw(job_dir)                     # workspace was frozen read-only
            shutil.rmtree(job_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
