#!/usr/bin/env python3
"""Green-gate harness for the kernel-computation track.

Runs every example submission in tests/harness_manifest.json through the judge and
asserts the outcome (accepted/rejected) and, for rejections, a substring of the
reason. Exit 0 iff every case matches. This is the canonical regression gate:
run it after any change to the judge, timer-kernel, problems, or rules.

Usage:
  python3 scripts/run_harness.py            # all cases
  python3 scripts/run_harness.py --quick    # accepted cases use 1 timing rep
  python3 scripts/run_harness.py --only fib # cases whose problem matches a substring
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JUDGE = ROOT / "judge" / "judge.py"
MANIFEST = ROOT / "tests" / "harness_manifest.json"
SUBS = ROOT / "examples" / "submissions"


def run_case(case, reps):
    problem, name = case["problem"], case["submission"]
    sub_dir = SUBS / problem / name
    tag = f"harness-{problem}-{name}"
    verdict_file = ROOT / "results" / problem / f"{tag}.json"
    # Delete any stale verdict first, so a crashed judge can't pass on last run's file.
    if verdict_file.exists():
        verdict_file.unlink()
    cmd = [sys.executable, str(JUDGE), "run", "--problem", problem,
           "--submission", str(sub_dir), "--tag", tag, "--reps", str(reps)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not verdict_file.exists():
        return False, f"no verdict file (exit {proc.returncode}); stderr: {proc.stderr.strip()[:200]}"
    v = json.loads(verdict_file.read_text())
    status, reason = v.get("status"), (v.get("reason") or "")
    # Exit-code contract: 0 = judged (accepted/rejected), 2 = infra failure.
    if proc.returncode == 2 and case["expect"] != "error":
        return False, f"infra error (exit 2): {reason[:140]}"
    if proc.returncode not in (0, 2):
        return False, f"unexpected judge exit {proc.returncode}"
    if status != case["expect"]:
        return False, f"expected {case['expect']}, got {status} ({reason[:120]})"
    if "reason_contains" in case and case["reason_contains"] not in reason:
        return False, f"reason missing '{case['reason_contains']}': {reason[:120]}"
    if status == "accepted":
        # A verdict alone doesn't prove the PERFORMANCE phase ran — assert it produced a
        # scaling curve, and (when the case declares it) an actual score, so a fully broken
        # perf phase can't slip through green.
        scaling = v.get("timing", {}).get("scaling")
        if not isinstance(scaling, list) or not scaling:
            return False, "accepted but no timing/scaling (perf phase did not run)"
        if case.get("scored") and not v.get("score"):
            return False, "accepted but unscored (case expects a score)"
    detail = status + (f", {v['score']}" if v.get("score") else "")
    return True, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="use 1 timing rep for accepted cases")
    ap.add_argument("--only", help="run only cases whose problem contains this substring")
    ap.add_argument("--count", type=int, help="override PERF_COUNT (sample points per problem)")
    args = ap.parse_args()

    # The gate checks verdicts + that the perf phase produced a score; it does not need the full
    # official 10-point curve. Default --quick to a few points for speed (official run: no override).
    if args.count is not None:
        os.environ["PERF_COUNT"] = str(args.count)
    elif args.quick and not os.environ.get("PERF_COUNT"):
        os.environ["PERF_COUNT"] = "4"

    cases = json.loads(MANIFEST.read_text())["cases"]
    if args.only:
        cases = [c for c in cases if args.only in c["problem"]]
        if not cases:
            print(f"no cases match --only '{args.only}'", file=sys.stderr)
            sys.exit(2)

    reps = 1 if args.quick else None  # None → judge default from config
    npass = 0
    failures = []
    for c in cases:
        r = reps if reps is not None else json.loads((ROOT / "pipeline" / "config.json").read_text())["judge"]["timing_reps"]
        ok, detail = run_case(c, r)
        mark = "✅" if ok else "❌"
        print(f"{mark} {c['problem']}/{c['submission']}: {detail}")
        if ok:
            npass += 1
        else:
            failures.append((c, detail))

    print(f"\n{npass}/{len(cases)} cases passed")
    if failures:
        print("FAILURES:")
        for c, d in failures:
            print(f"  - {c['problem']}/{c['submission']}: {d}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
