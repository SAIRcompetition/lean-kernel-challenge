#!/usr/bin/env python3
"""Regression tests for green-gate manifest coverage."""

import argparse
import json
import os
import sys
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


if __name__ == "__main__":
    unittest.main()
