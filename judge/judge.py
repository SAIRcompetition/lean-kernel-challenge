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
  4. Performance (the score): correctness is now proved, so we time the COMPUTATION, not the
     proof. For each judge-chosen input n: reduce `impl n` to a literal v via a kernel-side
     oracle, confirm the Submission is byte-unchanged from step 2, build+export
     `perf_check : impl n = v := by decide +kernel`, re-audit THAT export's axioms, then time
     the official kernel replaying it (which forces reduction of `impl n`), N reps. The result
     is a scaling curve: a too-slow input truncates it (still accepted); an oracle/build/kernel
     fault errors with no score. metric=wall_time (dev) or perf_instructions (Linux host).
     With TIMING_EXECUTOR_URLS set the replays run on a remote KTP/1 executor with real PMU
     hardware; each per-input export is uploaded with its SHA-256. An unreachable executor is
     NOT a verdict: the run exits 3 with a "retry" verdict so the caller can requeue losslessly.

Exit codes: 0 = judged (verdict JSON, accepted OR rejected); 2 = infrastructure error;
3 = timing executor unreachable (verdict status "retry" — requeue and try again later).
Every infra failure still writes an error JSON and exits 2, never a traceback.

ISOLATION (not the judge's job): killing EVERY process a submission spawns (incl. setsid
escapes), resource caps, and non-root execution are enforced by the container/cgroup, not
this process — see the Dockerfile `docker run` flags. The bundled process-group kill and
read-only freeze here are defense in depth, not a security boundary.
"""
import argparse
import hashlib
import json
import os
import re
import resource
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
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
DEFAULT_REPS = _J["timing_reps"]
MAX_SUBMISSION_BYTES = _J["max_submission_bytes"]
MAX_SUBMISSION_FILES = _J["max_submission_files"]
# Timing metric + sandbox mode; env overrides let the Docker host switch to perf.
TIMING_METRIC = os.environ.get("TIMING_METRIC", _CFG.get("timing", {}).get("metric", "wall_time"))
SANDBOX_MODE = os.environ.get("SANDBOX_MODE", _CFG.get("sandbox", {}).get("mode", "none"))
# Remote timing executor (KTP/1, lean-timer-executor). Comma-separated URLs in
# active-standby order; used only when metric=perf_instructions. The secret is
# the executor's bearer token and never appears in verdicts or logs.
TIMING_EXECUTOR_URLS = [u.strip().rstrip("/") for u in
                        os.environ.get("TIMING_EXECUTOR_URLS", "").split(",") if u.strip()]
TIMING_EXECUTOR_SECRET = os.environ.get("TIMING_EXECUTOR_SECRET", "")
# Dispatch attempts across the URL list before giving up with a "retry"
# verdict: sleep, then walk every URL again. Short and bounded — long
# outages are the CALLER's requeue loop, not ours.
_EXECUTOR_ATTEMPT_SLEEPS = [0, 10, 30]
# Once one executor serves a point, PIN it for the rest of this submission so a mid-curve
# failover cannot mix PMU data from different machines under one label. If the pinned node
# later goes unreachable, that raises TimingRetry and the whole submission is requeued (never
# silently continued on another node). One judge process = one submission, so this is per-job.
_PINNED_EXECUTOR = [None]

# Tool locations. Default to the local `repro/` checkout; override via env on the
# Docker/Linux eval host, where the tools are built at fixed image paths.
REPRO = ROOT.parent / "repro"
COMPARATOR = Path(os.environ.get("COMPARATOR_BIN", REPRO / "comparator/.lake/build/bin/comparator"))
LEAN4EXPORT_BIN = Path(os.environ.get("LEAN4EXPORT_BIN", REPRO / "lean4export/.lake/build/bin"))
TIMER = Path(os.environ.get("TIMER_BIN", ROOT / "judge/timer-kernel/.lake/build/bin/kernel"))
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

SLUG = re.compile(r"^[A-Za-z0-9_.-]+$")   # no slashes, no "..", no whitespace

# The scaling-axis inputs are a CONFIGURED POLICY, never hardcoded: each problem's config.json
# declares `perf` {min, max, count?, spacing?, jitter?}, with global fallbacks in
# pipeline/config.json `perf_defaults`. The judge samples `count` geometrically-spaced inputs in
# [min, max] (even coverage in log-space, for a stable log-log slope), clamped to distinct
# integers. When PERF_SEED is set (the hidden OFFICIAL inputs) each point is jittered by ±jitter
# from a seed-derived hash, so contestants know the scale but not the exact n (defeats hardcoding);
# with no seed the points are deterministic (local dev). See rules/evaluation.md.
_PERF_DEFAULTS = _CFG.get("perf_defaults", {"count": 10, "spacing": "geometric", "jitter": 0.15})
PERF_SEED = os.environ.get("PERF_SEED", "")


def _perf_jitter(x, lo, hi, frac, problem, idx):
    """Deterministic per-point jitter in [1-frac, 1+frac], derived from PERF_SEED so the hidden
    official inputs are unpredictable yet reproducible. No seed / no jitter → unchanged."""
    if not PERF_SEED or frac <= 0:
        return x
    h = hashlib.sha256(f"{PERF_SEED}:{problem}:{idx}".encode()).digest()
    u = int.from_bytes(h[:8], "big") / 2.0 ** 64          # uniform in [0, 1)
    return min(hi, max(lo, x * (1.0 + (2.0 * u - 1.0) * frac)))


def perf_inputs(cfg, problem):
    """Distinct increasing integer inputs from the problem's `perf` policy (⊕ global defaults),
    geometric in [min, max], seed-jittered when PERF_SEED is set. Returns None if unconfigured."""
    perf = cfg.get("perf")
    if not (isinstance(perf, dict) and "min" in perf and "max" in perf):
        return None
    lo, hi = int(perf["min"]), int(perf["max"])
    if hi < lo:
        return None
    # PERF_COUNT env overrides the point count (e.g. the dev green gate uses fewer points for
    # speed); the official run leaves it unset and uses the config/default count. Bad env value
    # falls back to the default rather than crashing the judge.
    try:
        count = max(1, int(os.environ.get("PERF_COUNT") or perf.get("count", _PERF_DEFAULTS.get("count", 10))))
    except (TypeError, ValueError):
        count = int(_PERF_DEFAULTS.get("count", 10))
    frac = float(perf.get("jitter", _PERF_DEFAULTS.get("jitter", 0.15)))
    if count == 1 or hi == lo:
        raw = [float(lo)]
    else:
        raw = [lo * (hi / lo) ** (i / (count - 1)) for i in range(count)]  # geometric
    pts = set()
    for idx, x in enumerate(raw):
        n = int(round(_perf_jitter(x, lo, hi, frac, problem, idx)))
        pts.add(min(hi, max(lo, n)))
    return sorted(pts)


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


def has_real_landrun(env):
    return shutil.which("landrun", path=env.get("PATH", "")) not in (None, str(SHIM_DIR / "landrun"))


def tool_env():
    env = os.environ.copy()
    parts = [str(LEAN4EXPORT_BIN)]
    # Prepend the bundled shim only if no real landrun is on PATH (dev machine).
    if shutil.which("landrun", path=env.get("PATH", "")) is None:
        parts.insert(0, str(SHIM_DIR))
    env["PATH"] = os.pathsep.join(parts + [env["PATH"]])
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
    `impl n` for large n, or elaborating `decide +kernel`) doesn't overflow the default
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


def assemble(job_dir: Path, problem, submission_dir):
    prob_dir = PROBLEMS / problem
    if not (prob_dir / "config.json").exists():
        raise InfraError(f"unknown problem '{problem}'")
    sd = Path(submission_dir)
    if (sd / "Submission.lean").is_symlink() or not (sd / "Submission.lean").is_file():
        raise SubmissionError(f"submission '{submission_dir}' has no regular Submission.lean")

    work = job_dir / "workspace"
    # Copy the locked template (preserve any symlink AS a symlink; there are none, but
    # never silently follow one).
    shutil.copytree(prob_dir, work, symlinks=True,
                    ignore=shutil.ignore_patterns(".lake", "lake-manifest.json"))
    # Overlay contestant files, preserving symlinks as symlinks (do NOT follow them).
    shutil.copy(sd / "Submission.lean", work / "Submission.lean", follow_symlinks=False)
    if (sd / "Submission").exists():
        shutil.rmtree(work / "Submission", ignore_errors=True)
        shutil.copytree(sd / "Submission", work / "Submission", symlinks=True)
    # Re-audit the ASSEMBLED contestant files (closes validate→copy TOCTOU).
    roots = [work / "Submission.lean"]
    if (work / "Submission").exists():
        roots.append(work / "Submission")
    _audit_tree(work, roots)
    return work


def _time_replay(export_file, work, env, timeout):
    """One timed kernel replay of the export. Returns (rc, out, sample_dict)."""
    if TIMING_METRIC == "perf_instructions":
        perf = shutil.which("perf", path=env.get("PATH", ""))
        if not perf:
            raise InfraError("metric=perf_instructions but `perf` not found — requires the Linux eval host")
        perf_out = export_file.parent / "perf.txt"
        cmd = [perf, "stat", "-o", str(perf_out), "-x", ",",
               "-e", "instructions,task-clock", "--", str(TIMER), str(export_file)]
        rc, out = run(cmd, work, env, timeout)
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
        if rc == 0 and insns is None:
            raise InfraError("perf produced no instruction count (PMU unavailable in this container?)")
        return rc, out, {"instructions": insns, "task_clock_ms": task_clock}
    else:
        t0 = time.monotonic()
        rc, out = run([str(TIMER), str(export_file)], work, env, timeout)
        return rc, out, {"wall_s": round(time.monotonic() - t0, 3)}


def _time_remote(export_file, reps):
    """Run all timing reps on a remote KTP/1 executor (lean-timer-executor).

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
            url = f"{base}/ktp/v1/time?reps={reps}&timeout_secs={TIMING_TIMEOUT}"
            req = urllib.request.Request(url, data=export_bytes, method="POST", headers={
                "Authorization": f"Bearer {TIMING_EXECUTOR_SECRET}",
                "Content-Type": "application/octet-stream",
                "X-Export-SHA256": digest,
            })
            try:
                with urllib.request.urlopen(req, timeout=request_timeout) as resp:
                    body = resp.read()
                data = json.loads(body)
                if data.get("status") in ("ok", "timeout", "failed"):
                    _PINNED_EXECUTOR[0] = base       # pin this node for the rest of the submission
                    data["executor_url"] = base
                    return data
                last_err = f"{base}: unrecognized executor response"
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
# cannot mis-score: `decide +kernel` in _perf_export would then fail to build.
_VALUE_META = r"""import Submission
import Lean
open Lean Meta
set_option maxRecDepth 4000000
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


def _too_slow(out):
    """True when a non-wall-clock Lean failure still means 'too big to evaluate at this n' —
    a deterministic heartbeat/`whnf` timeout, or a recursion-depth / stack blow-up — rather
    than a genuine fault. Such a failure truncates the scaling curve (the submission is just
    too slow here); it must NOT be an error. A wrong value, by contrast, makes `decide +kernel`
    fail *deterministically* (type mismatch, not a heartbeat timeout), so it is not caught here
    and is surfaced as an error below."""
    return any(m in out for m in (
        "(deterministic) timeout", "maximum number of heartbeats", "maximum recursion depth",
        "maxRecDepth", "stack overflow", "deep recursion"))


def _eval_impl_value(work, env, n, timeout):
    """Reduce `impl n` to a literal via the kernel-side oracle above. Returns (kind, payload):
    ('ok', v) with v a decimal string; ('timeout', None) when the reduction is too slow/deep (a
    legitimate curve truncation, not a fault); ('error', tail) when Lean errored for a non-resource
    reason or the oracle produced no literal (an unexpected condition that must NOT yield a score)."""
    (work / "EvalVal.lean").write_text(_VALUE_META.replace("__N__", str(n)))
    rc, out = run(["lake", "env", "lean", "EvalVal.lean"], work, env, timeout)
    if rc == "timeout":
        return "timeout", None
    if rc != 0:
        return ("timeout", None) if _too_slow(out) else ("error", last_line(out))
    for line in out.splitlines():
        if line.startswith("VALUE="):
            return "ok", line[6:].strip()
    return "error", "value oracle produced no literal (NONLIT)"


def _perf_export(work, env, n, v, out_path, timeout):
    """Build `perf_check : impl n = v := by decide +kernel` and export just that theorem.

    The kernel replay of this export re-checks `decide (impl n = v) = true` by reduction,
    which forces the kernel to reduce `impl n` at this specific n — so timing the replay
    times the COMPUTATION at n, not the ∀n correctness proof. Returns (kind, error): 'ok';
    'timeout' when the build/export is too slow (a curve truncation); or 'error' for a
    non-timeout build/export failure — which includes a wrong reference `v` (`decide +kernel`
    then fails to prove `impl n = v` *deterministically*, so it is errored, not scored). The
    caller only truncates on a wall-clock timeout; a wrong value fails deterministically far
    inside the timing budget, so it never reaches that truncation path in practice."""
    (work / "Perf.lean").write_text(
        f"import Submission\ntheorem perf_check : Submission.impl {n} = {v} := by decide +kernel\n")
    lf = work / "lakefile.toml"
    s = lf.read_text()
    if 'name = "Perf"' not in s:
        lf.write_text(s.rstrip() + '\n\n[[lean_lib]]\nname = "Perf"\n')
    rc, out = run(["lake", "build", "Perf"], work, env, timeout)
    if rc == "timeout":
        return "timeout", None      # kernel reduction of a CORRECT value genuinely too slow → truncate
    if rc != 0:
        # The oracle already produced a value, so the build should succeed. Any DETERMINISTIC
        # failure is a fault, never a truncation: a wrong value makes `decide` false (and its deep
        # Decidable comparison of a huge literal blows maxRecDepth), while a correct value reduces
        # in the kernel without hitting maxRecDepth. So a wrong oracle value can never be scored —
        # it surfaces here as an error, even at large n (closing the maxRecDepth-masking hole).
        return "error", f"perf build failed at n={n}: {last_line(out)}"
    rc, out = run(["lake", "env", str(LEAN4EXPORT_BIN / "lean4export"), "Perf", "--", "perf_check"],
                  work, env, timeout, stdout_path=out_path)
    if rc == "timeout":
        return "timeout", None
    if rc != 0:
        return "error", f"perf export failed at n={n}: {last_line(out)}"
    if not out_path.exists() or out_path.stat().st_size == 0:
        return "error", f"perf export produced no output at n={n}"
    return "ok", None


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


def judge(job_dir: Path, problem, submission_dir, reps, tag):
    sub_name = tag or Path(submission_dir).name
    result = {"problem": problem, "submission": sub_name,
              "status": None, "reason": None, "metric": TIMING_METRIC, "stages": {}}

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

    # Fail-closed sandbox policy: production must have a real sandbox.
    env = tool_env()
    if SANDBOX_MODE == "container" and not has_real_landrun(env):
        raise InfraError("sandbox.mode=container but no real landrun on PATH (refusing to run unsandboxed)")

    work = assemble(job_dir, problem, submission_dir)
    cfg = json.loads((PROBLEMS / problem / "config.json").read_text())
    axioms = cfg["permitted_axioms"]

    # Identity binding (1/2): pin the submission bytes BEFORE comparator reads them, so the
    # baseline is exactly what gets correctness-verified — not some post-verification state.
    verified_digest = _submission_digest(work)

    # ---- Comparator: correctness gate (statement match + axioms + kernel replay of ∀n) ----
    # The patched comparator writes the exact export it just verified (COMPARATOR_SOLUTION_EXPORT).
    # That export is the correctness artifact; the perf phase separately builds and times per-input
    # `impl n` exports, bound back to this verification by the digest checks below.
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
    freeze_readonly(work)


    # ---- Axiom re-audit (R4): whitelisted axioms only, on the comparator-verified correctness
    # export (the per-input timed exports are separately re-audited in the perf loop below) ----
    rc, out = run([str(TIMER), "--check-axioms", ",".join(axioms), str(export_file)],
                  work, env, AUDIT_TIMEOUT)
    result["stages"]["axioms"] = {"exit": rc, "tail": last_line(out)}
    if rc == "timeout":
        result["status"], result["reason"] = "error", "axiom re-audit timed out"
        return finish()
    if rc != 0:
        result["status"], result["reason"] = "rejected", f"axiom audit: {last_line(out)}"
        return finish()

    # ---- Performance: time the kernel reducing `impl n` at judge-chosen inputs ----
    # Correctness (the ∀n proof) was verified by comparator above. Here we time the
    # COMPUTATION, not the proof: for each input n we export `impl n = v` (decide+kernel)
    # and time the kernel replaying THAT export — which forces reduction of `impl n` at
    # this n. That is what makes a better ALGORITHM win, and yields a scaling curve.
    thaw(work)  # comparator froze the workspace; the perf phase rebuilds Perf.lean in it
    # Force a rebuild of the submission from the digest-verified source, so the timed impl cannot
    # come from a compiled artifact (or forged lake trace) swapped in after verification: nuke the
    # build and recompile impl from the source bytes we re-check (per input) against verified_digest.
    shutil.rmtree(work / ".lake" / "build", ignore_errors=True)
    rc, out = run(["lake", "build", "Submission"], work, env, COMPARATOR_TIMEOUT)
    if rc != 0:
        result["status"], result["reason"] = "error", \
            f"submission failed to rebuild from verified source: {last_line(out)}"
        return finish()
    inputs = perf_inputs(cfg, problem)
    if not inputs:
        result["status"], result["reason"] = "error", f"no perf policy configured for '{problem}'"
        return finish()
    result["stages"]["perf_inputs"] = inputs

    def time_export(export_path):
        """(status, payload): status in {'ok','timeout','failed'}; payload = samples on ok,
        error tail on failed. Reuses the exact local/remote timing machinery."""
        if TIMING_METRIC == "perf_instructions" and TIMING_EXECUTOR_URLS:
            remote = _time_remote(export_path, reps)      # may raise TimingRetry
            result["stages"].setdefault("timing_executor", {
                "executor": remote.get("executor"), "version": remote.get("version")})
            if remote["status"] == "timeout":
                return "timeout", None
            if remote["status"] == "failed":
                return "failed", last_line(remote.get("output_tail", ""))
            samples = [{"instructions": s.get("instructions"),
                        "task_clock_ms": s.get("task_clock_ms")} for s in remote["samples"]]
            if len(samples) != reps or any(s["instructions"] is None for s in samples):
                raise InfraError("timing executor returned an incomplete sample set")
            return "ok", samples
        samples = []
        for i in range(reps):
            rc, out, sample = _time_replay(export_path, work, env, TIMING_TIMEOUT)
            if rc == "timeout":
                return "timeout", None
            if rc != 0:
                return "failed", f"rep {i}: {last_line(out)}"
            samples.append(sample)
        return "ok", samples

    def summarize(samples):
        if TIMING_METRIC == "perf_instructions":
            insns = [s["instructions"] for s in samples if s.get("instructions") is not None]
            # round, not truncate: an even number of reps gives a .5 median we must not floor
            return {"median_instructions": round(statistics.median(insns)) if insns else None}
        return {"median_s": round(statistics.median([s["wall_s"] for s in samples]), 3)}

    # A genuine timeout truncates the curve (the submission is too slow at this n — still
    # accepted); any non-timeout failure (oracle error, wrong value, build/export/audit/kernel
    # failure) is an `error` verdict with NO score, so a fault can never be misread as "the
    # algorithm only scales this far".
    scaling = []
    perf_error = None
    for n in inputs:
        vkind, v = _eval_impl_value(work, env, n, TIMING_TIMEOUT)
        if vkind == "timeout":
            scaling.append({"n": n, "result": "value-eval-timeout"}); break
        if vkind == "error":
            perf_error = f"value oracle failed at n={n}: {v}"; break
        # Identity binding: the impl we are about to build/time must be byte-identical to the
        # one comparator verified `impl_correct` against. A mismatch means the Submission was
        # modified after verification — a fault, never a score.
        if _submission_digest(work) != verified_digest:
            perf_error = f"submission changed after correctness verification (at n={n})"; break
        perf_export = job_dir / f"perf_{n}.export.ndjson"
        pkind, err = _perf_export(work, env, n, v, perf_export, TIMING_TIMEOUT)
        if pkind == "timeout":
            scaling.append({"n": n, "result": "timeout"}); break
        if pkind == "error":
            perf_error = err; break
        # Re-check the source digest AFTER the build too: impl was recompiled during it, so a
        # mutation in that window must be caught before we trust and time the export.
        if _submission_digest(work) != verified_digest:
            perf_error = f"submission changed during perf build (at n={n})"; break
        # Pin the exact export bytes and freeze the file, so the axiom audit and the (separate)
        # timing process provably run identical bytes — not different ones swapped in between.
        perf_bytes = perf_export.read_bytes()
        try:
            perf_export.chmod(0o444)
        except OSError:
            pass
        arc, aout = run([str(TIMER), "--check-axioms", ",".join(axioms), str(perf_export)],
                        work, env, AUDIT_TIMEOUT)
        if arc != 0:
            perf_error = f"perf export axiom audit failed at n={n}: {last_line(aout)}"; break
        if perf_export.read_bytes() != perf_bytes:
            perf_error = f"perf export changed after axiom audit (at n={n})"; break
        status, payload = time_export(perf_export)
        if perf_export.read_bytes() != perf_bytes:
            perf_error = f"perf export changed during timing (at n={n})"; break
        if status == "failed":
            perf_error = f"official kernel rejected perf export at n={n}: {payload}"; break
        if status == "timeout":
            scaling.append({"n": n, "result": "timeout"}); break
        scaling.append({"n": n, "result": "ok", **summarize(payload)})

    if perf_error is not None:
        result["timing"] = {"metric": TIMING_METRIC, "reps": reps, "scaling": scaling,
                            "checker": "official-kernel-replay v4.32.0-rc1"}
        result["status"], result["reason"] = "error", perf_error
        return finish()

    # Correctness already passed, so the submission is ACCEPTED regardless of speed; the
    # scaling curve only determines the score. A submission too slow to complete even the
    # smallest input is accepted-but-unscored — slow is not a rejection (only incorrect,
    # illegal-axiom, or kernel-rejected exports are rejected, above).
    result["timing"] = {"metric": TIMING_METRIC, "reps": reps, "scaling": scaling,
                        "checker": "official-kernel-replay v4.32.0-rc1"}
    result["status"] = "accepted"
    ok_rows = [r for r in scaling if r.get("result") == "ok"]
    if not ok_rows:
        result["reason"] = "unscored: did not complete the smallest judge input in time"
    else:
        top = ok_rows[-1]  # headline = largest input that completed
        result["timing"]["headline_n"] = top["n"]
        if TIMING_METRIC == "perf_instructions":
            result["timing"]["median_instructions"] = top.get("median_instructions")
            result["score"] = f"{top.get('median_instructions')} instr @ n={top['n']} (median of {reps})"
        else:
            result["timing"]["median_s"] = top.get("median_s")
            result["score"] = f"median {top.get('median_s')}s @ n={top['n']} over {reps} reps"
    return finish()


def md_cell(s) -> str:
    """Escape an untrusted value for a single Markdown table cell."""
    s = str(s if s is not None else "")
    s = s.replace("\\", "\\\\").replace("|", "\\|")
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"[`<>\[\]]", "", s)
    return s[:160]


def _score_key(r):
    # Rank by how far the submission scales first (largest completed input n, further is
    # better), then by cost at that input (lower is better). Comparing raw medians across
    # different n would rank a naive submission that only reached a tiny input ABOVE a fast
    # one that scaled far — the scaling reach is the primary signal.
    t = r.get("timing", {})
    n = t.get("headline_n")
    med = t.get("median_instructions") if r.get("metric") == "perf_instructions" else t.get("median_s")
    if n is None or med is None:
        return None
    return (-n, med)


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
            # scripts/perf_eval.py output lacks "stages" and is skipped; requiring every field also
            # prevents a KeyError on a malformed file.
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
        # Rank within each metric separately — never mix seconds and instruction counts.
        metrics = sorted({r.get("metric", "wall_time") for r in accepted})
        for metric in metrics:
            grp = [r for r in accepted if r.get("metric", "wall_time") == metric]
            scored = sorted((r for r in grp if _score_key(r) is not None), key=_score_key)
            unscored = [r for r in grp if _score_key(r) is None]
            label = _METRIC_LABEL.get(metric, metric)
            lines.append(f"**ranked by scaling reach, then {label}** "
                         f"(furthest completed input first; ties broken by lower {label})")
            lines.append("")
            lines.append("| rank | submission | score |")
            lines.append("|---|---|---|")
            for i, r in enumerate(scored, 1):
                lines.append(f"| {i} | {md_cell(r['submission'])} | {md_cell(r.get('score'))} |")
            lines.append("")
            if unscored:
                lines.append("_accepted but unscored (did not complete even the smallest judge input):_")
                lines.append("")
                for r in unscored:
                    lines.append(f"- {md_cell(r['submission'])} — {md_cell(r.get('reason') or 'unscored')}")
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
    try:
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
