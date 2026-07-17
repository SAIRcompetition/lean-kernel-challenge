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
    cmd = [sys.executable, str(JUDGE), "run", "--problem", problem,
           "--submission", str(sub_dir), "--tag", tag, "--reps", str(reps)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    verdict_file = ROOT / "results" / problem / f"{tag}.json"
    if not verdict_file.exists():
        return False, f"no verdict file (exit {proc.returncode}); stderr: {proc.stderr.strip()[:200]}"
    v = json.loads(verdict_file.read_text())
    status, reason = v.get("status"), (v.get("reason") or "")
    if status != case["expect"]:
        return False, f"expected {case['expect']}, got {status} ({reason[:120]})"
    if "reason_contains" in case and case["reason_contains"] not in reason:
        return False, f"reason missing '{case['reason_contains']}': {reason[:120]}"
    detail = f"{status}"
    if v.get("timing"):
        detail += f", {v['timing']['median_s']}s"
    return True, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="use 1 timing rep for accepted cases")
    ap.add_argument("--only", help="run only cases whose problem contains this substring")
    args = ap.parse_args()

    cases = json.loads(MANIFEST.read_text())["cases"]
    if args.only:
        cases = [c for c in cases if args.only in c["problem"]]

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
