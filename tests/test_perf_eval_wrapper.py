#!/usr/bin/env python3
"""Regression tests for the canonical perf_eval wrapper."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import perf_eval


class PerfEvalWrapperTests(unittest.TestCase):
    def test_evaluate_delegates_once_and_restores_judge_globals(self):
        original_results = perf_eval._judge.RESULTS
        original_timeout = perf_eval._judge.TIMING_TIMEOUT
        original_executor = perf_eval._judge._PINNED_EXECUTOR[0]
        original_identity = perf_eval._judge._PINNED_EXECUTOR_IDENTITY[0]
        observed = {}

        def fake_judge(job_dir, problem, submission, reps, tag):
            observed.update({
                "job_dir": job_dir,
                "problem": problem,
                "submission": submission,
                "reps": reps,
                "tag": tag,
                "results": perf_eval._judge.RESULTS,
                "timeout": perf_eval._judge.TIMING_TIMEOUT,
            })
            out = perf_eval._judge.RESULTS / problem / f"{tag}.json"
            out.parent.mkdir(parents=True)
            out.write_text(json.dumps({
                "problem": problem,
                "submission": tag,
                "status": "rejected",
                "reason": "test rejection",
                "metric": "wall_time",
                "stages": {},
            }))
            perf_eval._judge._PINNED_EXECUTOR[0] = "temporary"
            perf_eval._judge._PINNED_EXECUTOR_IDENTITY[0] = ("temporary", "v")
            return 0

        with tempfile.TemporaryDirectory() as temp:
            submission = Path(temp) / "baseline"
            submission.mkdir()
            with mock.patch.object(perf_eval._judge, "judge", side_effect=fake_judge), \
                 mock.patch.object(perf_eval._judge, "OFFICIAL_EVAL", False), \
                 mock.patch.object(perf_eval._judge, "PERF_SEED", ""), \
                 mock.patch.object(perf_eval._judge, "EVALUATION_COHORT", ""), \
                 mock.patch.object(perf_eval._judge, "TIMING_EXECUTOR_URLS", []), \
                 mock.patch.object(perf_eval._judge, "TIMING_METRIC", "wall_time"):
                verdict = perf_eval.evaluate("fib", submission, timeout=17)

        self.assertEqual(verdict["status"], "rejected")
        self.assertFalse(verdict["scored"])
        self.assertEqual(observed["reps"], 1)
        self.assertEqual(observed["tag"], "perf-eval")
        self.assertEqual(observed["timeout"], 17)
        self.assertNotEqual(observed["results"], original_results)
        self.assertEqual(perf_eval._judge.RESULTS, original_results)
        self.assertEqual(perf_eval._judge.TIMING_TIMEOUT, original_timeout)
        self.assertEqual(perf_eval._judge._PINNED_EXECUTOR[0], original_executor)
        self.assertEqual(
            perf_eval._judge._PINNED_EXECUTOR_IDENTITY[0], original_identity)

    def test_official_or_remote_settings_are_refused_before_judging(self):
        with mock.patch.object(perf_eval._judge, "PERF_SEED", "hidden"), \
             mock.patch.object(perf_eval._judge, "judge") as judge_mock:
            verdict = perf_eval.evaluate("fib", "/tmp/submission", timeout=10)

        self.assertEqual(verdict["status"], "error")
        self.assertIn("local wall-time only", verdict["reason"])
        judge_mock.assert_not_called()

    def test_participant_config_cannot_replace_missing_evaluator_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            participant_config = root / "problems/fib/config.json"
            participant_config.parent.mkdir(parents=True)
            participant_config.write_text("{}")
            with mock.patch.object(perf_eval, "BASE", root), \
                 mock.patch.object(perf_eval._judge, "judge") as judge_mock:
                verdict = perf_eval.evaluate("fib", root / "submission")
        self.assertEqual(verdict["status"], "error")
        self.assertIn("unknown problem", verdict["reason"])
        judge_mock.assert_not_called()

    def test_atomic_output_replaces_complete_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "nested" / "verdict.json"
            perf_eval._atomic_write(path, "first")
            perf_eval._atomic_write(path, "second")
            self.assertEqual(path.read_text(), "second")
            self.assertEqual(list(path.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
