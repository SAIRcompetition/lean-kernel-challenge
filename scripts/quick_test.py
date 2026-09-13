#!/usr/bin/env python3
"""Run public, non-scoring smoke tests for Stage 1 submissions.

This helper deliberately does not invoke ``judge/judge.py``.  It copies the
locked problem files and one submission into a temporary Lake workspace,
builds the universal proof, and compares compiled executions of ``impl`` and
the trusted spec on a few small, fixed, public inputs.  It never reads hidden
seeds, uses PMU counters, or writes an official verdict/result.

Usage:
  python3 scripts/quick_test.py
  python3 scripts/quick_test.py --problem fib
  python3 scripts/quick_test.py --problem fib --submission path/to/Submission.lean
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROBLEMS = ROOT / "problems"
EXAMPLES = ROOT / "examples" / "submissions"

# These inputs are intentionally small, fixed, and public.  They exercise the
# input encodings and output comparison without approximating an official
# evaluation plan.  Packed inputs have the scale in the high bits and a small
# public seed in the low 32 bits.
DEMO_CASES: dict[str, tuple[str, tuple[int, ...]]] = {
    "fib": ("fibSpec", (0, 10, 20)),
    "partition": ("partitionSpec", (0, 5, 10)),
    "mertens": ("mertensSpec", (1, 10, 25)),
    "primecount": ("primeCountSpec", (1, 10, 50)),
    "permanent": ("permanentSpecN", ((3 << 32) | 1, (4 << 32) | 2)),
    "saw": ("sawSpec", ((2 << 32) | 1, (4 << 32) | 2)),
    "ca-rule110": ("caSpecN", ((1 << 32) | 1, (2 << 32) | 2)),
    "sha256": ("sha256Spec", ((1 << 32) | 1, (2 << 32) | 2)),
    "polydisc": ("discSpec", (0,)),
}

LOCKED_FILES = ("Spec.lean", "Solution.lean", "lakefile.toml", "lean-toolchain")
DEMO_EXECUTABLE = "quick_test_demo"
EXCLUDED_ENV_PREFIXES = (
    "EVAL_",
    "OFFICIAL_",
    "PERF_",
    "REFERENCE_",
    "TIMING_",
)
EXCLUDED_ENV_NAMES = {
    "COHORT_ID",
    "ELAN_TOOLCHAIN",
    "LEAN_PATH",
    "REFERENCE_BUNDLE",
    "SANDBOX_MODE",
}


@dataclass(frozen=True)
class QuickResult:
    problem: str
    passed: bool
    detail: str


def _demo_source(spec_name: str, inputs: tuple[int, ...]) -> str:
    values = ", ".join(str(value) for value in inputs)
    return f"""import Solution

/-!
Generated public smoke test.  Compiled execution is used only for quick local
feedback; this file and its timings are not part of official evaluation.
-/

def quickInputs : List Nat := [{values}]

def quickCheck (n : Nat) : IO Bool := do
  let actual := impl n
  let expected := {spec_name} n
  if actual == expected then
    IO.println s!\"  PASS input={{n}}\"
    return true
  else
    IO.eprintln s!\"  FAIL input={{n}}: impl={{actual}}, spec={{expected}}\"
    return false

def main : IO UInt32 := do
  let checks <- quickInputs.mapM quickCheck
  return if checks.all id then 0 else 1
"""


def _clean_environment() -> dict[str, str]:
    """Remove official-evaluation material and overrides of the pinned Lean setup."""
    return {
        key: value
        for key, value in os.environ.items()
        if key not in EXCLUDED_ENV_NAMES
        and not any(key.startswith(prefix) for prefix in EXCLUDED_ENV_PREFIXES)
    }


def resolve_submission(problem: str, submission: Path | None) -> Path:
    """Resolve a submission file, defaulting to the shipped baseline demo."""
    candidate = submission or (EXAMPLES / problem / "baseline" / "Submission.lean")
    candidate = candidate.expanduser()
    if candidate.is_dir():
        candidate = candidate / "Submission.lean"
    if not candidate.is_file():
        raise ValueError(f"submission is not a regular file: {candidate}")
    return candidate.resolve()


def _run(command: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=_clean_environment(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _failure_output(proc: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part.strip())
    return output[-4000:] if output else f"command exited {proc.returncode} without output"


def run_problem(problem: str, submission: Path | None = None, *, timeout: int = 120) -> QuickResult:
    """Build and execute one public demo in an automatically removed workspace."""
    if problem not in DEMO_CASES:
        return QuickResult(problem, False, f"unknown scored problem: {problem}")

    try:
        source = resolve_submission(problem, submission)
    except ValueError as error:
        return QuickResult(problem, False, str(error))

    problem_dir = PROBLEMS / problem
    try:
        with tempfile.TemporaryDirectory(prefix=f"lkc-quick-{problem}-") as raw_work:
            work = Path(raw_work)
            for name in LOCKED_FILES:
                locked = problem_dir / name
                if not locked.is_file():
                    return QuickResult(problem, False, f"missing locked file: {locked}")
                shutil.copy2(locked, work / name)
            shutil.copy2(source, work / "Submission.lean")

            spec_name, inputs = DEMO_CASES[problem]
            (work / "QuickTest.lean").write_text(
                _demo_source(spec_name, inputs), encoding="utf-8"
            )
            with (work / "lakefile.toml").open("a", encoding="utf-8") as lakefile:
                lakefile.write(
                    f'\n[[lean_exe]]\nname = "{DEMO_EXECUTABLE}"\nroot = "QuickTest"\n'
                )

            # Build a native executable rather than using ``lean --run``.  The latter
            # interprets recursive specs and can make even tiny demo inputs surprisingly
            # slow; native execution is exactly the lightweight feedback intended here.
            # Importing Solution still builds and type-checks Submission and its proof.
            build = _run(["lake", "build", DEMO_EXECUTABLE], cwd=work, timeout=timeout)
            if build.returncode != 0:
                return QuickResult(problem, False, "build failed:\n" + _failure_output(build))
            build_output = "\n".join((build.stdout, build.stderr))
            if "declaration uses `sorry`" in build_output:
                return QuickResult(
                    problem,
                    False,
                    "build uses `sorry`; replace every placeholder before testing",
                )

            demo = _run(
                [str(work / ".lake" / "build" / "bin" / DEMO_EXECUTABLE)],
                cwd=work,
                timeout=timeout,
            )
            if demo.returncode != 0:
                return QuickResult(problem, False, "demo failed:\n" + _failure_output(demo))
            detail = demo.stdout.strip() or f"{len(inputs)} public demo case(s) passed"
            return QuickResult(problem, True, detail)
    except subprocess.TimeoutExpired:
        return QuickResult(problem, False, f"quick test exceeded the {timeout}s local timeout")
    except OSError as error:
        return QuickResult(problem, False, f"could not run quick test: {error}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compile and run public demo inputs only. This command does not reproduce "
            "the official judge and does not produce a score."
        )
    )
    parser.add_argument(
        "--problem",
        choices=tuple(DEMO_CASES),
        help="run one problem (default: run the shipped baseline demo for every problem)",
    )
    parser.add_argument(
        "--submission",
        type=Path,
        help="Submission.lean file or containing directory; requires --problem",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="local build and execution timeout per phase in seconds (default: 120)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.submission is not None and args.problem is None:
        parser.error("--submission requires --problem")
    if args.timeout < 1:
        parser.error("--timeout must be at least 1")

    problems = (args.problem,) if args.problem else tuple(DEMO_CASES)
    print(
        "PUBLIC QUICK TEST ONLY — compiled demo inputs; no hidden cases, PMU, "
        "official verdict, or score.",
        flush=True,
    )

    failures: list[QuickResult] = []
    for problem in problems:
        chosen = args.submission if args.problem else None
        print(f"\n[{problem}]", flush=True)
        result = run_problem(problem, chosen, timeout=args.timeout)
        print(result.detail, flush=True)
        print("PASS" if result.passed else "FAIL", flush=True)
        if not result.passed:
            failures.append(result)

    if failures:
        print(f"\nQuick test failed: {len(failures)}/{len(problems)} problem(s).")
        return 1
    print(f"\nQuick test passed: {len(problems)}/{len(problems)} problem(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
