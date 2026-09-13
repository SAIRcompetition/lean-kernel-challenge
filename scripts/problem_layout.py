#!/usr/bin/env python3
"""Resolve trusted evaluator workspaces independently of participant packages."""

from pathlib import Path


MIGRATED_PROBLEMS = frozenset({
    "fib",
    "ca-rule110",
    "mertens",
    "partition",
    "permanent",
    "polydisc",
    "primecount",
    "sha256",
})
RETIRED_PROBLEMS = frozenset({"saw"})
EVALUATION_PROBLEMS = MIGRATED_PROBLEMS | {"conv"}


def evaluation_problem_dir(root: Path, problem: str) -> Path:
    """Return the authoritative workspace, never a participant-directory fallback."""
    if problem in RETIRED_PROBLEMS:
        raise ValueError(f"retired evaluator problem: {problem}")
    if problem not in EVALUATION_PROBLEMS:
        raise ValueError(f"unknown evaluator problem: {problem}")
    parent = root / "evaluation" / "problems" if problem in MIGRATED_PROBLEMS else root / "problems"
    return parent / problem


def iter_evaluation_problem_dirs(root: Path):
    """Yield configured active tasks only, even when retired files remain on disk."""
    for problem in sorted(EVALUATION_PROBLEMS):
        path = evaluation_problem_dir(root, problem)
        if (path / "config.json").is_file():
            yield path


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--problem", required=True)
    args = parser.parse_args()
    try:
        path = evaluation_problem_dir(args.root, args.problem)
    except ValueError as exc:
        parser.error(str(exc))
    if not (path / "config.json").is_file():
        parser.error(f"unknown evaluator problem: {args.problem}")
    print(path)


if __name__ == "__main__":
    main()
