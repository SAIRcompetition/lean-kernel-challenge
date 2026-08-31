#!/usr/bin/env python3
"""Regression tests for green-gate manifest coverage."""

import argparse
import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_harness  # noqa: E402


class HarnessManifestTests(unittest.TestCase):
    def test_current_manifest_covers_every_example_and_problem(self):
        cases = json.loads(run_harness.MANIFEST.read_text())["cases"]
        run_harness.validate_manifest(cases)

    def test_duplicate_case_is_rejected(self):
        cases = json.loads(run_harness.MANIFEST.read_text())["cases"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            run_harness.validate_manifest(cases + [dict(cases[0])])

    def test_quick_mode_bounds_schedule_and_preparation_by_default(self):
        args = argparse.Namespace(quick=True, timeout=None, count=None)
        with mock.patch.dict(os.environ, {}, clear=True):
            run_harness.configure_local_overrides(args)
            self.assertEqual(os.environ["PERF_COUNT"], "1")
            self.assertEqual(os.environ["TIMING_TIMEOUT_SECONDS"], "30")

    def test_explicit_quick_environment_overrides_are_preserved(self):
        args = argparse.Namespace(quick=True, timeout=None, count=None)
        with mock.patch.dict(os.environ, {
            "PERF_COUNT": "2",
            "TIMING_TIMEOUT_SECONDS": "75",
        }, clear=True):
            run_harness.configure_local_overrides(args)
            self.assertEqual(os.environ["PERF_COUNT"], "2")
            self.assertEqual(os.environ["TIMING_TIMEOUT_SECONDS"], "75")

    def test_command_line_overrides_win(self):
        args = argparse.Namespace(quick=True, timeout=12, count=3)
        with mock.patch.dict(os.environ, {
            "PERF_COUNT": "2",
            "TIMING_TIMEOUT_SECONDS": "75",
        }, clear=True):
            run_harness.configure_local_overrides(args)
            self.assertEqual(os.environ["PERF_COUNT"], "3")
            self.assertEqual(os.environ["TIMING_TIMEOUT_SECONDS"], "12")

    def test_run_cases_respects_worker_limit_and_reports_every_case(self):
        cases = [
            {"problem": "p", "submission": f"s{index}"}
            for index in range(4)
        ]
        lock = threading.Lock()
        active = 0
        peak = 0

        def fake_run(case, _reps):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return True, case["submission"]

        reported = []
        with mock.patch.object(run_harness, "run_case", side_effect=fake_run):
            run_harness.run_cases(cases, 1, 2, lambda *result: reported.append(result))

        self.assertEqual(peak, 2)
        self.assertCountEqual((case for case, _ok, _detail in reported), cases)
        self.assertTrue(all(ok for _case, ok, _detail in reported))

    def test_run_cases_turns_worker_exception_into_failure(self):
        case = {"problem": "p", "submission": "broken"}
        reported = []
        with mock.patch.object(run_harness, "run_case", side_effect=RuntimeError("boom")):
            run_harness.run_cases([case], 1, 1, lambda *result: reported.append(result))

        self.assertEqual(reported, [(case, False, "harness exception: boom")])

    def test_run_cases_cancels_pending_work_on_interrupt(self):
        cases = [
            {"problem": "p", "submission": "one"},
            {"problem": "p", "submission": "two"},
        ]
        pool = mock.Mock()
        futures = [mock.Mock(), mock.Mock()]
        pool.submit.side_effect = futures

        with mock.patch.object(
                run_harness.concurrent.futures, "ThreadPoolExecutor", return_value=pool), \
             mock.patch.object(
                 run_harness.concurrent.futures, "as_completed", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                run_harness.run_cases(cases, 1, 1, mock.Mock())

        pool.shutdown.assert_called_once_with(wait=False, cancel_futures=True)

    def test_image_gate_defaults_to_one_configurable_worker(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertIn("ARG HARNESS_JOBS=1", dockerfile)
        self.assertIn('--jobs "$HARNESS_JOBS"', dockerfile)


if __name__ == "__main__":
    unittest.main()
