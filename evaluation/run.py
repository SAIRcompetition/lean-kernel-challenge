#!/usr/bin/env python3
"""Evaluate one fib submission through the canonical local judge."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent


def _canonical_evaluator():
    sys.path.insert(0, str(ROOT / "scripts"))
    import perf_eval
    return perf_eval


def resolve_submission(value=None):
    source = Path(value) if value is not None else ROOT / "problems/fib/Submission.lean"
    source = source.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"submission must be an existing file: {source}")
    return source


def evaluate_file(source, timeout=120):
    """Copy only the selected file; never use its enclosing project as a payload."""
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if os.environ.get("PERF_COUNT"):
        raise ValueError("unset PERF_COUNT: this entrypoint requires the complete six-case public plan")
    source = resolve_submission(source)
    evaluator = _canonical_evaluator()
    with tempfile.TemporaryDirectory(prefix="lkc-fib-submission-") as temporary:
        payload = Path(temporary) / "payload"
        payload.mkdir()
        shutil.copyfile(source, payload / "Submission.lean")
        return evaluator.evaluate("fib", payload, timeout)


def _write_result(source, verdict):
    token = hashlib.sha256(str(source).encode()).hexdigest()[:16]
    output = ROOT / "results/local-evaluation/fib" / f"{token}.json"
    _canonical_evaluator()._atomic_write(output, json.dumps(verdict, indent=2) + "\n")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", choices=["fib"], default="fib")
    parser.add_argument("--submission", help="Lean file (default: problems/fib/Submission.lean)")
    parser.add_argument("--timeout", type=int, default=120, help="local per-process time budget in seconds")
    args = parser.parse_args(argv)
    print("Local evaluation: unseeded public cases, one wall-time repetition; not official scores.")
    try:
        source = resolve_submission(args.submission)
        verdict = evaluate_file(source, args.timeout)
        output = _write_result(source, verdict)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    status = verdict.get("status", "error")
    print(f"fib/{source.name}: {status}")
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
