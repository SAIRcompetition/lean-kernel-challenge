#!/usr/bin/env python3
"""Compatibility entry point for synchronizing the fib participant package."""

import argparse
from pathlib import Path
import sys

import sync_participants


ROOT = Path(__file__).resolve().parents[1]


def expected_files(root=ROOT):
    return sync_participants.expected_files("fib", root)


def synchronize(root=ROOT, *, check=False):
    return sync_participants.synchronize_problem("fib", root, check=check)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check without writing anything")
    args = parser.parse_args()
    try:
        changed = synchronize(check=args.check)
        print("Participant Spec and environment match the evaluator." if args.check
              else "Generated participant dependencies: " + (", ".join(changed) or "already current"))
        return 0
    except (OSError, ValueError, KeyError, StopIteration) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
