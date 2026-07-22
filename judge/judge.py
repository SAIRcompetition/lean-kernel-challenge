#!/usr/bin/env python3
"""Lean Kernel Challenge judge.

Pipeline per submission (each contestant job runs in a unique temp workspace):
  1. Validate + assemble: copy the locked problem template, then overlay the contestant's
     Submission.lean (+ Submission/). Contestant files are re-audited ON THE ASSEMBLED
     tree (regular files, no symlinks, size/count caps, containment) to close the
     validate-then-copy TOCTOU window.
  2. Correctness: run comparator (statement match, axiom whitelist, kernel replay).
     Sandboxed via landrun on Linux; on macOS the pass-through shim strips sandboxing.
     The patched comparator EMITS the exact export it just verified (via
     COMPARATOR_SOLUTION_EXPORT); we time that immutable file. The judge never
     re-exports, so there is no comparator→timed-export TOCTOU: what is audited and
     timed is byte-for-byte what comparator statement-matched and kernel-replayed.
  3. R3 re-audit: the timed export declares only whitelisted axioms.
  4. Timing (the score): official-kernel replay of the export, N reps.
       metric=wall_time         → median wall seconds (dev only)
       metric=perf_instructions → perf instruction count (Linux eval host; fail-closed)
     With TIMING_EXECUTOR_URLS set (and metric=perf_instructions), the replays run on a
     remote KTP/1 timing executor with real PMU hardware (lean-timer-executor) instead
     of local perf; the export is uploaded with its SHA-256 so the comparator→timing
     TOCTOU closure survives the network hop. An unreachable executor is NOT a verdict:
     the run exits 3 with a "retry" verdict so the caller can requeue losslessly.

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


class InfraError(Exception):
    """Raised for any infrastructure failure; caught at top level → error JSON + exit 2."""


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


def run(cmd, cwd, env, timeout, stdout_path=None):
    """Run a command in its own process group. The saved pgid is killed on timeout AND on
    normal exit (pgid captured at spawn, not via getpgid on an already-exited child).
    Returns (exit_code | 'timeout', output_tail)."""
    popen_kw = dict(cwd=cwd, env=env, start_new_session=True)
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
            raise InfraError(f"submission: symlinks are not allowed ({p.name})")
        rp = p.resolve(strict=True)
        if rp != base_real and not str(rp).startswith(str(base_real) + os.sep):
            raise InfraError(f"submission: path escapes workspace ({p})")
        if p.is_dir():
            stack.extend(p.iterdir())
            continue
        if not p.is_file():
            raise InfraError(f"submission: not a regular file ({p.name})")
        if p.suffix not in ("", ".lean"):
            raise InfraError(f"submission: only .lean files allowed ({p.name})")
        count += 1
        total += p.stat().st_size
        if count > MAX_SUBMISSION_FILES:
            raise InfraError(f"submission: too many files (> {MAX_SUBMISSION_FILES})")
        if total > MAX_SUBMISSION_BYTES:
            raise InfraError(f"submission: payload too large (> {MAX_SUBMISSION_BYTES} bytes)")


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
        raise InfraError(f"submission '{submission_dir}' has no regular Submission.lean")

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
    for sleep_s in _EXECUTOR_ATTEMPT_SLEEPS:
        if sleep_s:
            time.sleep(sleep_s)
        for base in TIMING_EXECUTOR_URLS:
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

    # ---- Comparator: correctness gate (statement match + axioms + kernel replay) ----
    # The patched comparator writes the EXACT export it just verified to this file
    # (see patches/comparator-emit-export.patch). We time that immutable file rather
    # than re-exporting the workspace, which closes the comparator→timed-export TOCTOU:
    # there is no window in which a submission-spawned process could swap the .olean
    # between what comparator verified and what we measure.
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
    result["stages"]["export"] = {"source": "comparator-verified", "bytes": export_file.stat().st_size}
    # The workspace is no longer read after this point; freeze it anyway as belt-and-suspenders.
    freeze_readonly(work)


    # ---- R3 re-audit: only whitelisted axioms in the exact timed export ----
    rc, out = run([str(TIMER), "--check-axioms", ",".join(axioms), str(export_file)],
                  work, env, AUDIT_TIMEOUT)
    result["stages"]["axioms"] = {"exit": rc, "tail": last_line(out)}
    if rc == "timeout":
        result["status"], result["reason"] = "error", "axiom re-audit timed out"
        return finish()
    if rc != 0:
        result["status"], result["reason"] = "rejected", f"axiom audit: {last_line(out)}"
        return finish()

    # ---- Timing: kernel replay of the export, N reps (the scored event) ----
    samples = []
    if TIMING_METRIC == "perf_instructions" and TIMING_EXECUTOR_URLS:
        remote = _time_remote(export_file, reps)          # may raise TimingRetry
        result["stages"]["timing_executor"] = {"executor": remote.get("executor"),
                                               "version": remote.get("version")}
        if remote["status"] == "timeout":
            result["status"], result["reason"] = "rejected", f"kernel replay timed out (> {TIMING_TIMEOUT}s)"
            return finish()
        if remote["status"] == "failed":
            rep = remote.get("rep", "?")
            tail_txt = last_line(remote.get("output_tail", ""))
            result["status"], result["reason"] = "error", \
                f"official kernel rejected an export comparator accepted (rep {rep}): {tail_txt}"
            return finish()
        samples = [{"instructions": s.get("instructions"),
                    "task_clock_ms": s.get("task_clock_ms")} for s in remote["samples"]]
        if len(samples) != reps or any(s["instructions"] is None for s in samples):
            raise InfraError("timing executor returned an incomplete sample set")
    else:
        for i in range(reps):
            rc, out, sample = _time_replay(export_file, work, env, TIMING_TIMEOUT)
            if rc == "timeout":
                result["status"], result["reason"] = "rejected", f"kernel replay timed out (> {TIMING_TIMEOUT}s)"
                return finish()
            if rc != 0:
                result["status"], result["reason"] = "error", \
                    f"official kernel rejected an export comparator accepted (rep {i}): {last_line(out)}"
                return finish()
            samples.append(sample)

    timing = {"reps": samples, "checker": "official-kernel-replay v4.32.0-rc1", "metric": TIMING_METRIC}
    if TIMING_METRIC == "perf_instructions":
        insns = [s["instructions"] for s in samples if s.get("instructions") is not None]
        timing["median_instructions"] = int(statistics.median(insns)) if insns else None
        result["score"] = f"{timing['median_instructions']} instr (median of {reps})"
    else:
        walls = [s["wall_s"] for s in samples]
        timing["median_s"] = round(statistics.median(walls), 3)
        result["score"] = f"median {timing['median_s']}s over {reps} reps"
    result["timing"] = timing
    result["status"] = "accepted"
    return finish()


def md_cell(s) -> str:
    """Escape an untrusted value for a single Markdown table cell."""
    s = str(s if s is not None else "")
    s = s.replace("\\", "\\\\").replace("|", "\\|")
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"[`<>\[\]]", "", s)
    return s[:160]


def _score_key(r):
    t = r.get("timing", {})
    return t.get("median_instructions") if r.get("metric") == "perf_instructions" else t.get("median_s")


# Human label + sort order for each metric; scores of different metrics are NOT comparable
# (wall seconds vs instruction counts), so the leaderboard ranks within a metric only.
_METRIC_LABEL = {"perf_instructions": "instructions", "wall_time": "wall seconds (dev)"}


def leaderboard():
    rows = []
    for pdir in sorted(RESULTS.iterdir()):
        if not pdir.is_dir() or pdir.name == "work":
            continue
        for f in sorted(pdir.glob("*.json")):
            try:
                rows.append(json.loads(f.read_text()))
            except (json.JSONDecodeError, OSError):
                continue
    lines = ["# Lean Kernel Challenge — leaderboard (local dev)", ""]
    for problem in sorted({r["problem"] for r in rows}):
        lines.append(f"## {md_cell(problem)}")
        lines.append("")
        prows = [r for r in rows if r["problem"] == problem]
        accepted = [r for r in prows if r["status"] == "accepted"]
        # Rank within each metric separately — never mix seconds and instruction counts.
        metrics = sorted({r.get("metric", "wall_time") for r in accepted})
        for metric in metrics:
            grp = sorted([r for r in accepted if r.get("metric", "wall_time") == metric],
                         key=lambda r: (_score_key(r) is None, _score_key(r)))
            lines.append(f"**ranked by {_METRIC_LABEL.get(metric, metric)}** (lower is better)")
            lines.append("")
            lines.append("| rank | submission | score |")
            lines.append("|---|---|---|")
            for i, r in enumerate(grp, 1):
                lines.append(f"| {i} | {md_cell(r['submission'])} | {md_cell(r.get('score'))} |")
            lines.append("")
        rejected = [r for r in prows if r["status"] != "accepted"]
        if rejected:
            lines.append("| submission | status | note |")
            lines.append("|---|---|---|")
            for r in rejected:
                icon = "❌ rejected" if r["status"] == "rejected" else "💥 error"
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
