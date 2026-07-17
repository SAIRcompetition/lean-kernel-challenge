#!/usr/bin/env python3
"""Lean Competition judge.

Pipeline per submission:
  1. Assemble workspace: locked problem template + contestant's Submission.lean (+ Submission/).
     Contestant files are validated first: regular files only, no symlinks, inside the
     submission dir, under a size/count cap.
  2. Correctness: run comparator (statement match, axiom whitelist, kernel replay). Sandboxed
     via landrun on Linux; on macOS the landrun shim strips sandboxing (local dev only).
  3. Rule R2 audit: every definition hole (e.g. Submission.answer) must export as a raw literal.
  4. Axiom re-audit: the exact timed export must declare only whitelisted axioms (second line of
     defense over comparator; rejects sorryAx / native_decide even if the export diverged).
  5. Timing: replay the exported Solution through the pinned official kernel, N reps, median wall
     time. (On Linux, perf instruction counting can wrap this step; wall time is the macOS fallback.)

Exit codes: 0 = judged (verdict in JSON, accepted OR rejected); 2 = infrastructure error.
Judgement outcomes and infrastructure failures are deliberately separate channels: every
infra failure still writes an error JSON and exits 2, never crashes with a traceback.

NOTE (documented, not a bug): full sandboxing, perf instruction counting, and cgroup limits
require the Linux evaluation host. Locally the landrun shim is a pass-through — do not run
untrusted submissions on a dev machine.
"""
import argparse
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent            # lean-kernel-challenge/
PROBLEMS = ROOT / "problems"
RESULTS = ROOT / "results"

# Judge budgets live in pipeline/config.json (SAIR convention); load them here.
_CFG = json.loads((ROOT / "pipeline" / "config.json").read_text())
_J = _CFG["judge"]
COMPARATOR_TIMEOUT = _J["comparator_timeout_seconds"]
EXPORT_TIMEOUT = _J["export_timeout_seconds"]
AUDIT_TIMEOUT = _J["audit_timeout_seconds"]
TIMING_TIMEOUT = _J["timing_timeout_seconds"]
DEFAULT_REPS = _J["timing_reps"]
MAX_SUBMISSION_BYTES = _J["max_submission_bytes"]
MAX_SUBMISSION_FILES = _J["max_submission_files"]

# Tool locations. Default to the local `repro/` checkout; override via env on the
# Docker/Linux eval host, where the tools are built at fixed image paths.
REPRO = ROOT.parent / "repro"
COMPARATOR = Path(os.environ.get("COMPARATOR_BIN", REPRO / "comparator/.lake/build/bin/comparator"))
LEAN4EXPORT_BIN = Path(os.environ.get("LEAN4EXPORT_BIN", REPRO / "lean4export/.lake/build/bin"))
TIMER = Path(os.environ.get("TIMER_BIN", ROOT / "judge/timer-kernel/.lake/build/bin/kernel"))
# Bundled pass-through shims for `landrun`/`timeout` so the package is self-contained
# on dev machines. Used ONLY when a real `landrun` isn't already on PATH (Docker/Linux
# ships the real Landlock sandbox, which must win). See tool_env().
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


def valid_slug(s: str) -> bool:
    return bool(s) and s != ".." and SLUG.match(s) is not None


def tool_env():
    env = os.environ.copy()
    parts = [str(LEAN4EXPORT_BIN)]
    # Prepend the bundled shims only if there is no real `landrun` on PATH. On the
    # Docker/Linux eval host the real Landlock sandbox is present and must be used;
    # on a dev machine the pass-through shim keeps the pipeline runnable (NO sandbox).
    if shutil.which("landrun", path=env.get("PATH", "")) is None:
        parts.insert(0, str(SHIM_DIR))
    env["PATH"] = os.pathsep.join(parts + [env["PATH"]])
    return env


def run(cmd, cwd, env, timeout, stdout_path=None):
    """Run a command in its own process group; on timeout kill the whole group so a
    submission-spawned descendant cannot linger and perturb later timings.
    Returns (exit_code | 'timeout', output_tail)."""
    popen_kw = dict(cwd=cwd, env=env, start_new_session=True)
    try:
        if stdout_path:
            with open(stdout_path, "wb") as f:
                p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.PIPE, **popen_kw)
                try:
                    _, err = p.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    _kill_group(p)
                    return "timeout", f"timed out after {timeout}s"
            out = (err or b"").decode(errors="replace")
        else:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **popen_kw)
            try:
                out_b, _ = p.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_group(p)
                return "timeout", f"timed out after {timeout}s"
            out = (out_b or b"").decode(errors="replace")
        return p.returncode, out
    except FileNotFoundError as e:
        raise InfraError(f"tool not found: {e}")


def _kill_group(p):
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        p.wait(timeout=10)
    except Exception:
        pass


def last_line(out):
    lines = [l for l in out.strip().splitlines() if l.strip()]
    return lines[-1] if lines else "(no output)"


def _validate_contestant_tree(sd: Path):
    """Reject symlinks and non-regular files; enforce size/count caps; keep everything
    inside the submission dir. Runs BEFORE any file is copied into the workspace."""
    sd_real = sd.resolve(strict=True)
    entries = [sd / "Submission.lean"]
    subdir = sd / "Submission"
    if subdir.exists():
        if subdir.is_symlink():
            raise InfraError("submission: 'Submission/' is a symlink")
        entries += [p for p in subdir.rglob("*")]
    total = 0
    count = 0
    for p in entries:
        if p.is_symlink():
            raise InfraError(f"submission: symlinks are not allowed ({p.name})")
        if not p.exists():
            raise InfraError(f"submission: missing required file {p.name}")
        # containment: real path must stay under the submission dir
        if not str(p.resolve(strict=True)).startswith(str(sd_real) + os.sep) and p.resolve() != sd_real:
            raise InfraError(f"submission: path escapes submission dir ({p})")
        if p.is_dir():
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


def assemble(problem, submission_dir, sub_name):
    prob_dir = PROBLEMS / problem
    if not (prob_dir / "config.json").exists():
        raise InfraError(f"unknown problem '{problem}'")
    sd = Path(submission_dir)
    if not (sd / "Submission.lean").exists():
        raise InfraError(f"submission '{submission_dir}' has no Submission.lean")
    _validate_contestant_tree(sd)

    work = (RESULTS / "work" / f"{problem}__{sub_name}").resolve()
    if not str(work).startswith(str((RESULTS / "work").resolve()) + os.sep):
        raise InfraError("assembled work path escapes results/work")
    if work.exists():
        shutil.rmtree(work)
    # copytree without following symlinks (there are none in the locked template, but be safe)
    shutil.copytree(prob_dir, work, symlinks=True,
                    ignore=shutil.ignore_patterns(".lake", "lake-manifest.json"))
    shutil.copy(sd / "Submission.lean", work / "Submission.lean", follow_symlinks=False)
    if (sd / "Submission").exists():
        shutil.rmtree(work / "Submission", ignore_errors=True)
        shutil.copytree(sd / "Submission", work / "Submission", symlinks=False)
    return work


def judge(problem, submission_dir, reps, tag):
    sub_name = tag or Path(submission_dir).name
    result = {"problem": problem, "submission": sub_name,
              "status": None, "reason": None, "stages": {}}

    def finish():
        outdir = RESULTS / problem
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / f"{sub_name}.json").write_text(json.dumps(result, indent=2))
        icon = {"accepted": "✅", "rejected": "❌", "error": "💥"}[result["status"]]
        t = result.get("timing", {}).get("median_s")
        print(f"{icon} {problem}/{sub_name}: {result['status']}"
              + (f" — {result['reason']}" if result["reason"] else "")
              + (f" — median {t:.3f}s over {reps} reps" if t is not None else ""))
        return 0 if result["status"] in ("accepted", "rejected") else 2

    work = assemble(problem, submission_dir, sub_name)
    env = tool_env()

    # ---- Stage 1: comparator (correctness gate) ----
    t0 = time.monotonic()
    rc, out = run(["lake", "env", str(COMPARATOR), "config.json"], work, env, COMPARATOR_TIMEOUT)
    result["stages"]["comparator"] = {"exit": rc, "seconds": round(time.monotonic() - t0, 1),
                                      "tail": out[-3000:]}
    if rc == "timeout":
        result["status"], result["reason"] = "rejected", f"comparator timed out (> {COMPARATOR_TIMEOUT}s)"
        return finish()
    if rc != 0:
        result["status"], result["reason"] = "rejected", f"comparator: {last_line(out)}"
        return finish()

    # ---- Stage 2: export Solution ----
    cfg = json.loads((work / "config.json").read_text())
    axioms = cfg["permitted_axioms"]
    decls = cfg["theorem_names"] + cfg.get("definition_names", []) + axioms + PRIMITIVES
    export_file = work / "solution.export.ndjson"
    rc, out = run(["lake", "env", "lean4export", cfg["solution_module"], "--"] + decls,
                  work, env, EXPORT_TIMEOUT, stdout_path=export_file)
    result["stages"]["export"] = {"exit": rc,
                                  "bytes": export_file.stat().st_size if export_file.exists() else 0}
    if rc != 0:
        result["status"], result["reason"] = "error", f"lean4export failed after comparator accepted: {last_line(out)}"
        return finish()

    # ---- Stage 3: rule R2 — definition holes must be raw literals ----
    for d in cfg.get("definition_names", []):
        rc, out = run([str(TIMER), "--check-literal", f"Submission.{d}", str(export_file)],
                      work, env, AUDIT_TIMEOUT)
        result["stages"][f"literal:{d}"] = {"exit": rc, "tail": last_line(out)}
        if rc == "timeout":
            result["status"], result["reason"] = "error", f"R2 audit timed out for {d}"
            return finish()
        if rc != 0:
            result["status"], result["reason"] = "rejected", f"rule R2 ({d}): {last_line(out)}"
            return finish()

    # ---- Stage 4: axiom re-audit on the exact timed export ----
    rc, out = run([str(TIMER), "--check-axioms", ",".join(axioms), str(export_file)],
                  work, env, AUDIT_TIMEOUT)
    result["stages"]["axioms"] = {"exit": rc, "tail": last_line(out)}
    if rc == "timeout":
        result["status"], result["reason"] = "error", "axiom re-audit timed out"
        return finish()
    if rc != 0:
        result["status"], result["reason"] = "rejected", f"axiom audit: {last_line(out)}"
        return finish()

    # ---- Stage 5: timing (the scored event) ----
    times = []
    for i in range(reps):
        t0 = time.monotonic()
        rc, out = run([str(TIMER), str(export_file)], work, env, TIMING_TIMEOUT)
        dt = time.monotonic() - t0
        if rc == "timeout":
            result["status"], result["reason"] = "rejected", f"kernel replay timed out (> {TIMING_TIMEOUT}s)"
            return finish()
        if rc != 0:
            result["status"], result["reason"] = "error", \
                f"official kernel rejected an export comparator accepted (rep {i}): {last_line(out)}"
            return finish()
        times.append(dt)
    result["timing"] = {"reps": [round(t, 3) for t in times],
                        "median_s": round(statistics.median(times), 3),
                        "checker": "official-kernel-replay v4.32.0-rc1",
                        "metric": "wall_time (macOS dev; use perf instructions on Linux)"}
    result["status"] = "accepted"
    return finish()


def md_cell(s) -> str:
    """Escape an untrusted value for a single Markdown table cell."""
    s = str(s if s is not None else "")
    s = s.replace("\\", "\\\\").replace("|", "\\|")
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"[`<>\[\]]", "", s)
    return s[:160]


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
    lines = ["# Lean Competition — leaderboard (local dev)", ""]
    for problem in sorted({r["problem"] for r in rows}):
        lines.append(f"## {md_cell(problem)}")
        lines.append("")
        lines.append("| rank | submission | status | median time (s) | note |")
        lines.append("|---|---|---|---|---|")
        prows = [r for r in rows if r["problem"] == problem]
        accepted = sorted([r for r in prows if r["status"] == "accepted"],
                          key=lambda r: r["timing"]["median_s"])
        for i, r in enumerate(accepted, 1):
            lines.append(f"| {i} | {md_cell(r['submission'])} | ✅ accepted | {r['timing']['median_s']} | |")
        for r in prows:
            if r["status"] != "accepted":
                icon = "❌ rejected" if r["status"] == "rejected" else "💥 error"
                lines.append(f"| – | {md_cell(r['submission'])} | {icon} | – | {md_cell(r.get('reason'))} |")
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
    sub.add_parser("leaderboard")
    args = ap.parse_args()

    if args.cmd == "leaderboard":
        leaderboard()
        return

    # ---- input validation: any failure here is infra (exit 2), never a traceback ----
    problem, tag, sub_name = args.problem, args.tag, (args.tag or Path(args.submission).name)
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
        sys.exit(judge(problem, args.submission, args.reps, tag))
    except InfraError as e:
        # best-effort error JSON so the contract "always a verdict file" holds
        try:
            outdir = RESULTS / (problem if valid_slug(problem) else "_infra")
            outdir.mkdir(parents=True, exist_ok=True)
            name = sub_name if valid_slug(sub_name) else "_invalid"
            (outdir / f"{name}.json").write_text(json.dumps(
                {"problem": problem, "submission": sub_name,
                 "status": "error", "reason": f"infra: {e}", "stages": {}}, indent=2))
        except Exception:
            pass
        print(f"💥 infra error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
