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
import secrets
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
        if case.get("scored") and not v.get("score"):
            return fail("accepted but unscored (case expects a score)")
    # The temporary judge tag must not leak into the durable result/leaderboard identity.
    v["submission"] = canonical_tag
    verdict_file.write_text(json.dumps(v, indent=2))
    canonical_file.parent.mkdir(parents=True, exist_ok=True)
    os.replace(verdict_file, canonical_file)
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
