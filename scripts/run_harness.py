#!/usr/bin/env python3
"""Green-gate harness for the kernel-computation track.

Runs every example submission in tests/harness_manifest.json through the judge and
asserts the outcome (accepted/rejected) and, for rejections, a substring of the
reason. Exit 0 iff every case matches. This is the canonical regression gate:
run it after any change to the judge, timer-kernel, problems, or rules.

Usage:
  python3 scripts/run_harness.py            # all cases
  python3 scripts/run_harness.py --quick    # 1 rep/case per level, 30 s prep cap
  python3 scripts/run_harness.py --only fib # cases whose problem matches a substring
  python3 scripts/run_harness.py --jobs 4   # run up to 4 cases concurrently

Concurrency safety: every case judges into its own per-run workspace
(``judge/judge.py`` allocates a unique ``results/work/<problem>__<sub>__*``
directory) and publishes a unique run-tag verdict under
``results/<problem>/`` before atomically replacing that problem's canonical
verdict. Different cases never share a verdict path and no case runs twice in
one invocation, so the cases are independent. The limiting resource is
memory: each concurrent case holds a Lean compilation whose peak RSS can
reach several GiB. The default is deliberately one worker. Only raise
``--jobs`` after measuring the target host; exceeding its available memory
can turn the intended speedup into swap thrashing or an out-of-memory failure.
"""
import argparse
import concurrent.futures
import importlib.util
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JUDGE = ROOT / "judge" / "judge.py"
MANIFEST = ROOT / "tests" / "harness_manifest.json"
SUBS = ROOT / "examples" / "submissions"
SCORE_SPEC = importlib.util.spec_from_file_location(
    "challenge_score", ROOT / "scripts" / "score.py")
SCORER = importlib.util.module_from_spec(SCORE_SPEC)
SCORE_SPEC.loader.exec_module(SCORER)


def validate_manifest(cases):
    """Fail if an example is unregistered, duplicated, or points to a missing submission."""
    if not isinstance(cases, list):
        raise ValueError("manifest cases must be a list")
    keys = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"manifest case {index} is not an object")
        problem, submission = case.get("problem"), case.get("submission")
        if not (isinstance(problem, str) and isinstance(submission, str)):
            raise ValueError(f"manifest case {index} lacks problem/submission strings")
        if case.get("expect") not in ("accepted", "rejected", "error"):
            raise ValueError(f"manifest case {problem}/{submission} has invalid expectation")
        keys.append((problem, submission))
    if len(keys) != len(set(keys)):
        raise ValueError("manifest contains duplicate problem/submission cases")

    discovered = {
        (path.parent.parent.name, path.parent.name)
        for path in SUBS.glob("*/*/Submission.lean")
    }
    registered = set(keys)
    missing = sorted(registered - discovered)
    unregistered = sorted(discovered - registered)
    problem_ids = {
        path.parent.name for path in (ROOT / "problems").glob("*/config.json")
    }
    covered_problem_ids = {problem for problem, _ in registered}
    uncovered_problems = sorted(problem_ids - covered_problem_ids)
    unknown_problems = sorted(covered_problem_ids - problem_ids)
    if missing or unregistered or uncovered_problems or unknown_problems:
        details = []
        if missing:
            details.append("missing examples: " + ", ".join(f"{p}/{s}" for p, s in missing))
        if unregistered:
            details.append(
                "unregistered examples: " + ", ".join(f"{p}/{s}" for p, s in unregistered))
        if uncovered_problems:
            details.append("problems without a harness case: " + ", ".join(uncovered_problems))
        if unknown_problems:
            details.append("manifest references unknown problems: " + ", ".join(unknown_problems))
        raise ValueError("; ".join(details))


def configure_local_overrides(args):
    """Apply development-only harness overrides without weakening checked-in policy.

    ``--quick`` shortens both the sampled schedule and unscored preparation.
    Explicit command-line or environment values always win.
    """
    if args.timeout is not None:
        os.environ["TIMING_TIMEOUT_SECONDS"] = str(args.timeout)
    elif args.quick and not os.environ.get("TIMING_TIMEOUT_SECONDS"):
        os.environ["TIMING_TIMEOUT_SECONDS"] = "30"

    if args.count is not None:
        os.environ["PERF_COUNT"] = str(args.count)
    elif args.quick and not os.environ.get("PERF_COUNT"):
        os.environ["PERF_COUNT"] = "1"


def run_case(case, reps):
    problem, name = case["problem"], case["submission"]
    sub_dir = SUBS / problem / name
    canonical_tag = f"harness-{problem}-{name}"
    # Judge into a unique file and publish it over the canonical harness verdict only after
    # every assertion passes. An interrupted/crashed run therefore cannot destroy the last
    # known-good result, and a stale canonical verdict can never make this run pass.
    run_tag = f"{canonical_tag}-run-{os.getpid()}-{secrets.token_hex(4)}"
    verdict_file = ROOT / "results" / problem / f"{run_tag}.json"
    canonical_file = ROOT / "results" / problem / f"{canonical_tag}.json"

    def fail(detail):
        # A failed assertion must not leave a structurally valid run-tag verdict for the
        # canonical scorer/leaderboard to mistake for another submission.
        try:
            verdict_file.unlink()
        except FileNotFoundError:
            pass
        return False, detail

    cmd = [sys.executable, str(JUDGE), "run", "--problem", problem,
           "--submission", str(sub_dir), "--tag", run_tag, "--reps", str(reps)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not verdict_file.exists():
        return fail(f"no verdict file (exit {proc.returncode}); stderr: {proc.stderr.strip()[:200]}")
    try:
        v = json.loads(verdict_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return fail(f"invalid verdict {verdict_file.name}: {e}")
    status, reason = v.get("status"), (v.get("reason") or "")
    # Exit-code contract: 0 = judged (accepted/rejected), 2 = infra failure.
    if proc.returncode == 2 and case["expect"] != "error":
        return fail(f"infra error (exit 2): {reason[:140]}")
    if proc.returncode not in (0, 2):
        return fail(f"unexpected judge exit {proc.returncode}")
    if status != case["expect"]:
        return fail(f"expected {case['expect']}, got {status} ({reason[:120]})")
    if "reason_contains" in case and case["reason_contains"] not in reason:
        return fail(f"reason missing '{case['reason_contains']}': {reason[:120]}")
    if status == "accepted":
        # A verdict alone doesn't prove the scored pipeline ran. Require the separately timed
        # correctness artifact plus one scaling row per planned input (including explicit
        # timeout rows), so input collapse or an early `break` cannot pass the green gate.
        contract_error = SCORER._measurement_contract_error(v)
        if contract_error is not None:
            return fail(f"accepted with legacy/incompatible measurement: {contract_error}")
        correctness = v.get("correctness_timing")
        if not isinstance(correctness, dict) or not correctness.get("result"):
            return fail("accepted but no correctness_timing (scored proof replay did not run)")
        scaling = v.get("timing", {}).get("scaling")
        if not isinstance(scaling, list) or not scaling:
            return fail("accepted but no timing/scaling (perf phase did not run)")
        inputs = v.get("stages", {}).get("perf_inputs")
        if not isinstance(inputs, list) or len(scaling) != len(inputs):
            return fail(f"perf curve incomplete: {len(scaling)} rows for "
                        f"{len(inputs) if isinstance(inputs, list) else 'invalid'} inputs")
        if case.get("scored"):
            if not v.get("score"):
                return fail("accepted but unscored (case expects a score)")
            score_view = SCORER._score_row(v, v.get("metric"))
            if not score_view["scoreable"]:
                return fail(
                    "judge emitted a score rejected by canonical scorer: "
                    + str(score_view["reason"])
                )
            # len(scaling) == len(inputs) above only checks that every planned slot has a ROW
            # (timeout rows count too); a scored case could still collapse to one success (only
            # the smallest input, everything larger timing out) and pass. Require more than one
            # SUCCESSFUL slot once ≥3 are planned (per-case "min_slots" may raise the bar).
            ok = sum(1 for row in scaling if row.get("result") == "ok")
            need = min(len(inputs), case.get("min_slots", 2 if len(inputs) >= 3 else 1))
            if ok < need:
                return fail(f"only {ok}/{len(inputs)} slots completed; a scored case expects "
                            f">= {need} successful slots")
    # The temporary judge tag must not leak into the durable result/leaderboard identity.
    v["submission"] = canonical_tag
    verdict_file.write_text(json.dumps(v, indent=2))
    canonical_file.parent.mkdir(parents=True, exist_ok=True)
    os.replace(verdict_file, canonical_file)
    detail = status + (f", {v['score']}" if v.get("score") else "")
    return True, detail


def run_cases(cases, reps, jobs, report):
    """Run cases concurrently and report each completion on the caller thread.

    Pending cases are cancelled if the caller is interrupted.  The executor
    context-manager form cannot be used here: its implicit ``shutdown(wait=True)``
    would run every already-queued case before returning from Ctrl-C.
    """
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=jobs)
    future_to_case = {}
    try:
        future_to_case = {pool.submit(run_case, case, reps): case for case in cases}
        for future in concurrent.futures.as_completed(future_to_case):
            case = future_to_case[future]
            try:
                ok, detail = future.result()
            except Exception as exc:  # a worker crash must fail the gate, not hang it
                ok, detail = False, f"harness exception: {exc}"
            report(case, ok, detail)
    except BaseException:
        # cancel_futures prevents an interrupt from draining the entire queue. Running
        # judge children share the foreground process group and receive terminal signals.
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--quick", action="store_true",
        help=("use 1 timing rep, PERF_COUNT=1, and a 30 s preparation timeout "
              "unless already overridden"))
    ap.add_argument("--only", help="run only cases whose problem contains this substring")
    ap.add_argument(
        "--jobs", type=int, default=1,
        help=("run up to N harness cases concurrently; each case holds a Lean "
              "compilation whose peak RSS can reach several GiB, so bound N by "
              "measured available memory (default: 1)"))
    ap.add_argument(
        "--count", type=int,
        help=("override PERF_COUNT: total sample points for legacy policies; "
              "maximum cases in each group for grouped policies"))
    ap.add_argument("--timeout", type=int,
                    help="override the per-step timing budget in seconds (dev gate speed). Use this "
                         "instead of editing pipeline/config.json, which risks committing a tiny "
                         "debug budget into the official configuration.")
    args = ap.parse_args()
    if args.jobs < 1:
        ap.error("--jobs must be at least 1")

    # The gate checks verdicts + that the perf phase produced a score; it does not need the full
    # official schedule.  In grouped policies the override caps EACH group, retaining one case at
    # every difficulty level instead of accidentally dropping all but the easiest groups.
    configure_local_overrides(args)

    cases = json.loads(MANIFEST.read_text())["cases"]
    try:
        validate_manifest(cases)
    except ValueError as error:
        print(f"invalid harness manifest: {error}", file=sys.stderr)
        sys.exit(2)
    if args.only:
        cases = [c for c in cases if args.only in c["problem"]]
        if not cases:
            print(f"no cases match --only '{args.only}'", file=sys.stderr)
            sys.exit(2)

    reps = 1 if args.quick else None  # None → judge default from config
    if reps is None:
        reps = json.loads((ROOT / "pipeline" / "config.json").read_text())["judge"]["timing_reps"]

    jobs = min(args.jobs, len(cases))
    print(f"running {len(cases)} harness cases with {jobs} worker(s)", flush=True)

    npass = 0
    failures = []

    def report(case, ok, detail):
        nonlocal npass
        mark = "✅" if ok else "❌"
        print(f"{mark} {case['problem']}/{case['submission']}: {detail}", flush=True)
        if ok:
            npass += 1
        else:
            failures.append((case, detail))

    try:
        run_cases(cases, reps, jobs, report)
    except KeyboardInterrupt:
        print("\ninterrupted; cancelled harness cases that had not started", file=sys.stderr,
              flush=True)
        sys.exit(130)

    print(f"\n{npass}/{len(cases)} cases passed")
    if failures:
        failures.sort(key=lambda cd: (cd[0]["problem"], cd[0]["submission"]))
        print("FAILURES:")
        for c, d in failures:
            print(f"  - {c['problem']}/{c['submission']}: {d}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
