#!/usr/bin/env python3
"""Unit tests for the public, non-scoring quick-test helper."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quick_test  # noqa: E402


class QuickTestTests(unittest.TestCase):
    def test_every_scored_problem_has_public_demo_cases(self):
        scored = {
            path.parent.name
            for path in (ROOT / "problems").glob("*/config.json")
            if path.parent.name != "conv"
        }
        self.assertEqual(set(quick_test.DEMO_CASES), scored)
        self.assertTrue(all(inputs for _spec, inputs in quick_test.DEMO_CASES.values()))

    def test_resolve_submission_accepts_file_and_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            source = directory / "Submission.lean"
            source.write_text("-- demo\n")
            self.assertEqual(quick_test.resolve_submission("fib", source), source.resolve())
            self.assertEqual(quick_test.resolve_submission("fib", directory), source.resolve())

    def test_official_environment_is_not_forwarded(self):
        with mock.patch.dict(os.environ, {
            "PATH": "/bin",
            "PERF_SEED": "secret",
            "OFFICIAL_EVAL": "1",
            "EVAL_COHORT_ID": "private",
            "REFERENCE_BUNDLE": "/private/reference.json",
            "TIMING_METRIC": "perf_instructions",
            "ELAN_TOOLCHAIN": "unrelated-override",
            "LEAN_PATH": "/unrelated/imports",
            "SAFE_PUBLIC_VALUE": "kept",
        }, clear=True):
            clean = quick_test._clean_environment()
        self.assertEqual(clean, {"PATH": "/bin", "SAFE_PUBLIC_VALUE": "kept"})

    def test_run_problem_uses_temporary_workspace_and_never_calls_judge(self):
        calls = []
        generated = []

        def fake_run(command, *, cwd, timeout):
            calls.append((command, timeout))
            self.assertTrue(cwd.is_dir())
            self.assertTrue((cwd / "Submission.lean").is_file())
            self.assertFalse((cwd / "results").exists())
            generated.append((cwd / "QuickTest.lean").read_text())
            stdout = "  PASS input=0\n" if len(calls) == 2 else ""
            return subprocess.CompletedProcess(command, 0, stdout, "")

        with mock.patch.object(quick_test, "_run", side_effect=fake_run):
            result = quick_test.run_problem("fib")

        self.assertTrue(result.passed)
        self.assertEqual(calls[0], (["lake", "build", quick_test.DEMO_EXECUTABLE], 120))
        self.assertEqual(Path(calls[1][0][0]).name, quick_test.DEMO_EXECUTABLE)
        self.assertEqual(calls[1][1], 120)
        self.assertTrue(all("judge.py" not in " ".join(command) for command, _ in calls))
        self.assertIn("def quickInputs : List Nat := [0, 10, 20]", generated[0])

    def test_build_failure_stops_before_demo_execution(self):
        failed = subprocess.CompletedProcess(["lake"], 1, "", "bad proof")
        with mock.patch.object(quick_test, "_run", return_value=failed) as run:
            result = quick_test.run_problem("fib")
        self.assertFalse(result.passed)
        self.assertIn("build failed", result.detail)
        run.assert_called_once()

    def test_demo_mismatch_is_a_failure(self):
        built = subprocess.CompletedProcess(["lake"], 0, "", "")
        failed = subprocess.CompletedProcess(["lake"], 1, "", "FAIL input=10")
        with mock.patch.object(quick_test, "_run", side_effect=[built, failed]):
            result = quick_test.run_problem("fib")
        self.assertFalse(result.passed)
        self.assertIn("demo failed", result.detail)
        self.assertIn("FAIL input=10", result.detail)

    def test_sorry_warning_is_a_failure(self):
        warned = subprocess.CompletedProcess(
            ["lake"], 0, "", "warning: declaration uses `sorry`"
        )
        with mock.patch.object(quick_test, "_run", return_value=warned) as run:
            result = quick_test.run_problem("fib")
        self.assertFalse(result.passed)
        self.assertIn("uses `sorry`", result.detail)
        run.assert_called_once()

    def test_unknown_problem_is_rejected_without_work(self):
        with mock.patch.object(quick_test, "_run") as run:
            result = quick_test.run_problem("conv")
        self.assertFalse(result.passed)
        self.assertIn("unknown scored problem", result.detail)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
