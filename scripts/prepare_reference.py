#!/usr/bin/env python3
"""Prepare a private, submission-independent answer bundle for one complete plan."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "judge"))
import judge
import reference_answers
from problem_dependencies import specification_fingerprint
from problem_layout import evaluation_problem_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", required=True, choices=sorted(reference_answers.OUTPUT_TYPES))
    parser.add_argument("--output", required=True, type=Path,
                        help="private answer file; an existing file is never overwritten")
    parser.add_argument("--official", action="store_true",
                        help="read the hidden seed from stdin and prepare the full official plan")
    args = parser.parse_args()
    try:
        judge.OFFICIAL_EVAL = args.official
        if args.official:
            os.environ["PERF_SEED_STDIN"] = "1"
            judge._consume_perf_seed_stdin()
        else:
            # This command always prepares the complete plan, even in development.
            os.environ.pop("PERF_COUNT", None)
        import json
        problem_dir = evaluation_problem_dir(ROOT, args.problem)
        cfg = json.loads((problem_dir / "config.json").read_text())
        plan = judge._validated_performance_plan(cfg, args.problem)
        spec_digest = specification_fingerprint(problem_dir)
        bundle = reference_answers.prepare(args.problem, [row["n"] for row in plan], spec_digest)
        payload = reference_answers.canonical_bytes(bundle)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(payload)
        print(f"Prepared {len(plan)} reference answers for {args.problem}.")
    except (judge.InfraError, ValueError, ArithmeticError, OSError) as exc:
        parser.exit(2, f"Reference preparation failed: {exc}\n")


if __name__ == "__main__":
    main()
