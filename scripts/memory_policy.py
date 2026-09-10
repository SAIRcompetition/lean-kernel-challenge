#!/usr/bin/env python3
"""Shared parsing for the per-problem container memory policy (units are MiB)."""
import argparse
import json
import re
from pathlib import Path


def valid_memory_mb(value):
    # Docker requires at least 6 MiB; its byte limit is a signed 64-bit integer.
    return type(value) is int and 6 <= value <= (((1 << 63) - 1) >> 20)


def problem_memory_mb(config):
    evaluation = config.get("evaluation") if isinstance(config, dict) else None
    value = evaluation.get("memory_mb") if isinstance(evaluation, dict) else None
    if not valid_memory_mb(value):
        raise ValueError("evaluation.memory_mb must be an integer of at least 6 MiB "
                         "within Docker's signed 64-bit byte range")
    return value


def memory_mb_from_envelope(value):
    """Parse an exact, whole-MiB Docker size; unknown or unbounded sizes return None."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"([1-9][0-9]{0,18})([bBkKmMgG]?)", value)
    if match is None:
        return None
    shift = {"": 0, "b": 0, "k": 10, "m": 20, "g": 30}[match.group(2).lower()]
    size = int(match.group(1)) << shift
    if size % (1 << 20):
        return None
    value = size >> 20
    return value if valid_memory_mb(value) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--envelope", default="", help="optional assertion, never an override")
    args = parser.parse_args()
    try:
        memory_mb = problem_memory_mb(json.loads(args.config.read_text()))
        if args.envelope and memory_mb_from_envelope(args.envelope) != memory_mb:
            raise ValueError(f"--memory must match this problem's evaluation.memory_mb "
                             f"({memory_mb} MiB)")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"{memory_mb}m")


if __name__ == "__main__":
    main()
