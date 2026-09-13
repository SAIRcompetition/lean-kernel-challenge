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


def evaluation_problem_dir(root: Path, problem: str) -> Path:
    """Return the authoritative workspace, never a participant-directory fallback."""
    parent = root / "evaluation" / "problems" if problem in MIGRATED_PROBLEMS else root / "problems"
    return parent / problem


def iter_evaluation_problem_dirs(root: Path):
    """Yield configured evaluator workspaces in problem-id order during migration."""
    names = {
        path.parent.name for path in (root / "problems").glob("*/config.json")
        if path.parent.name not in MIGRATED_PROBLEMS
    }
    names.update(
        problem for problem in MIGRATED_PROBLEMS
        if (evaluation_problem_dir(root, problem) / "config.json").is_file()
    )
    for problem in sorted(names):
        yield evaluation_problem_dir(root, problem)


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--problem", required=True)
    args = parser.parse_args()
    path = evaluation_problem_dir(args.root, args.problem)
    if not (path / "config.json").is_file():
        parser.error(f"unknown evaluator problem: {args.problem}")
    print(path)


if __name__ == "__main__":
    main()
