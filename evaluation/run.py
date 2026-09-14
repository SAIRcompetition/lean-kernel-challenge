#!/usr/bin/env python3
"""Evaluate one submission through the canonical local judge."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_PROBLEMS = (
    "fib", "ca-rule110", "mertens", "partition", "permanent", "polydisc", "primecount", "sha256",
)


def _check_problem(problem):
    if problem not in SUPPORTED_PROBLEMS:
        raise ValueError(f"unsupported problem: {problem}")


def _canonical_evaluator():
    sys.path.insert(0, str(ROOT / "scripts"))
    import perf_eval
    return perf_eval


def resolve_submission(value=None, *, problem="fib"):
    _check_problem(problem)
    source = Path(value) if value is not None else ROOT / "problems" / problem / "Submission.lean"
    source = source.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"submission must be an existing file: {source}")
    return source


def evaluate_file(source, timeout=120, *, problem="fib"):
    """Copy only the selected file; never use its enclosing project as a payload."""
    _check_problem(problem)
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if os.environ.get("PERF_COUNT"):
        raise ValueError("unset PERF_COUNT: this entrypoint requires the complete public plan")
    source = resolve_submission(source, problem=problem)
    evaluator = _canonical_evaluator()
    with tempfile.TemporaryDirectory(prefix=f"lkc-{problem}-submission-") as temporary:
        payload = Path(temporary) / "payload"
        payload.mkdir()
        shutil.copyfile(source, payload / "Submission.lean")
        return evaluator.evaluate(problem, payload, timeout)


def _write_result(source, verdict, *, problem="fib"):
    _check_problem(problem)
    token = hashlib.sha256(str(source).encode()).hexdigest()[:16]
    output = ROOT / "results/local-evaluation" / problem / f"{token}.json"
    _canonical_evaluator()._atomic_write(output, json.dumps(verdict, indent=2) + "\n")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", choices=SUPPORTED_PROBLEMS, default="fib")
    parser.add_argument("--submission", help="Lean file (default: problems/PROBLEM/Submission.lean)")
    parser.add_argument("--timeout", type=int, default=120, help="local per-process time budget in seconds")
    args = parser.parse_args(argv)
    print("Local evaluation: unseeded public cases, one wall-time repetition; not official scores.")
    try:
        source = resolve_submission(args.submission, problem=args.problem)
        verdict = evaluate_file(source, args.timeout, problem=args.problem)
        output = _write_result(source, verdict, problem=args.problem)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    status = verdict.get("status", "error")
    print(f"{args.problem}/{source.name}: {status}")
    report = verdict.get("replay_report")
    if report is not None:
        correctness = report["correctness"]
        c_value = correctness.get("median_s")
        t_value = report["computation_total"]
        print(f"  Correctness replay C (verification only): {c_value if c_value is not None else '—'} s; "
              f"{correctness['result']}")
        print(f"  Computation replay T: {t_value if t_value is not None else '—'} s; "
              + ("complete" if report["eligible"] else "unranked"))
    for row in verdict.get("timing", {}).get("scaling", []):
        seconds = row.get("median_s")
        elapsed = "-" if seconds is None else f"{seconds:.9g}s"
        print(f"  n={row['n']}: {row['result'].upper()} ({elapsed})")
    if verdict.get("reason"):
        print(f"  reason: {verdict['reason']}")
    print(f"Local result: {output}")
    return {"accepted": 0, "rejected": 1, "error": 2, "retry": 3}.get(status, 2)


if __name__ == "__main__":
    raise SystemExit(main())
