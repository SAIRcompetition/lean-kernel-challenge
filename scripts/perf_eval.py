#!/usr/bin/env python3
"""Run a one-repetition local evaluation through the canonical judge.

This command intentionally delegates to ``evaluation/judge/judge.py`` instead of maintaining a
second timing implementation.  It therefore uses the same comparator-verified export,
identity pins, axiom audits, ``kernel-replay-v2`` boundaries, and timer-internal wall
clock as an ordinary local judge run.
"""

import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "evaluation" / "judge"))
import judge as _judge
from problem_layout import evaluation_problem_dir

# Kept as a compatibility alias for tooling that checks the oracle policy here.  The
# implementation itself lives in the canonical judge and disables Lean heartbeats.
_VALUE_META = _judge._VALUE_META


def _failure(problem, submission, status, reason):
    return {
        "problem": problem,
        "submission": submission,
        "status": status,
        "reason": reason,
        "stages": {},
        "scored": False,
    }


def evaluate(problem, submission_dir, timeout=120):
    """Evaluate through the canonical judge with one timing repetition.

    ``timeout`` replaces the configured timer-process budget for this development run
    and is included in the resulting cohort hash.  All artifacts first go to a private
    temporary results directory; the CLI publishes only the final JSON requested below.
    """
    submission_path = Path(submission_dir)
    submission = submission_path.name
    if timeout <= 0:
        return _failure(problem, submission, "error", "timeout must be positive")
    if not _judge.valid_slug(problem):
        return _failure(problem, submission, "error", f"invalid problem slug {problem!r}")
    try:
        problem_dir = evaluation_problem_dir(BASE, problem)
    except ValueError as exc:
        return _failure(problem, submission, "error", str(exc))
    if not (problem_dir / "config.json").is_file():
        return _failure(problem, submission, "error", f"unknown problem '{problem}'")
    if (_judge.OFFICIAL_EVAL or _judge.PERF_SEED or _judge.EVALUATION_COHORT
            or _judge.TIMING_EXECUTOR_URLS
            or _judge.TIMING_METRIC != "wall_time"):
        return _failure(
            problem,
            submission,
            "error",
            "perf_eval is local wall-time only; unset official seed/cohort/remote timing settings",
        )

    old_results = _judge.RESULTS
    old_timeout = _judge.TIMING_TIMEOUT
    old_executor = _judge._PINNED_EXECUTOR[0]
    old_executor_identity = _judge._PINNED_EXECUTOR_IDENTITY[0]
    temp_path = Path(tempfile.mkdtemp(prefix="lean-kernel-perf-eval-"))
    try:
        private_results = temp_path / "results"
        job_dir = temp_path / "job"
        private_results.mkdir()
        job_dir.mkdir()
        _judge.RESULTS = private_results
        _judge.TIMING_TIMEOUT = timeout
        try:
            # The canonical judge prints its own one-line status. Suppress that internal
            # line so this wrapper has one stable human-readable output format.
            with contextlib.redirect_stdout(io.StringIO()):
                _judge.judge(job_dir, problem, submission_path, 1, "perf-eval")
            verdict_path = private_results / problem / "perf-eval.json"
            verdict = json.loads(verdict_path.read_text())
        except _judge.SubmissionError as exc:
            return _failure(
                problem, submission, "rejected", f"submission format: {exc}")
        except _judge.TimingRetry as exc:
            return _failure(problem, submission, "retry", f"timing deferred: {exc}")
        except _judge.InfraError as exc:
            return _failure(problem, submission, "error", f"infra: {exc}")
        except Exception as exc:
            return _failure(
                problem, submission, "error",
                f"unexpected {type(exc).__name__}: {exc}")

        verdict["submission"] = submission
        try:
            score_view = _judge._score_view(verdict)
        except Exception as exc:
            return _failure(
                problem,
                submission,
                "error",
                f"score validation failed: {type(exc).__name__}: {exc}",
            )
        if verdict.get("score") and score_view is None:
            return _failure(
                problem,
                submission,
                "error",
                "canonical judge score failed current measurement-contract validation",
            )
        verdict["scored"] = (score_view is not None
                             and _judge._canonical_scorer()._placement_key(score_view) is not None)
        return verdict
    finally:
        if temp_path.exists():
            _judge.thaw(temp_path)
            shutil.rmtree(temp_path, ignore_errors=True)
        _judge.RESULTS = old_results
        _judge.TIMING_TIMEOUT = old_timeout
        _judge._PINNED_EXECUTOR[0] = old_executor
        _judge._PINNED_EXECUTOR_IDENTITY[0] = old_executor_identity


def _atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        try:
            Path(temporary).unlink()
        except FileNotFoundError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem", required=True)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    verdict = evaluate(args.problem, args.submission, args.timeout)
    # Keep this convenience artifact outside the canonical scorer's one-directory scan.
    # The filename is derived, not taken directly from user-controlled slugs.
    if _judge.valid_slug(args.problem):
        token = hashlib.sha256(str(Path(args.submission)).encode()).hexdigest()[:16]
        output_path = BASE / "results" / "perf-eval" / args.problem / f"{token}.json"
        _atomic_write(output_path, json.dumps(verdict, indent=2))

    suffix = (
        f" (scored={verdict['scored']})"
        if verdict["status"] == "accepted"
        else ""
    )
    print(f"{verdict['problem']}/{verdict['submission']}: {verdict['status']}{suffix}")
    for row in verdict.get("timing", {}).get("scaling", []):
        seconds = row.get("median_s")
        display = "-" if seconds is None else f"{seconds:.9g}s"
        print(f"  n={row['n']:<7} {display:<14} {row['result'].upper()}")
    if verdict.get("reason"):
        print("  reason:", verdict["reason"])
    if verdict["status"] == "retry":
        raise SystemExit(3)
    if verdict["status"] == "error":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
