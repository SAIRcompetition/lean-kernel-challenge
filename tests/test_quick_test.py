#!/usr/bin/env python3
"""Unit tests for the public, non-scoring quick-test helper."""

import os
import contextlib
import io
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quick_test  # noqa: E402
from problem_layout import MIGRATED_PROBLEMS  # noqa: E402


class QuickTestTests(unittest.TestCase):
    def test_only_legacy_saw_keeps_its_public_demo_cases(self):
        self.assertEqual(quick_test.DEMO_CASES, {
            "saw": ("sawSpec", ((2 << 32) | 1, (4 << 32) | 2)),
        })

    def test_resolve_submission_accepts_file_and_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            source = directory / "Submission.lean"
            source.write_text("-- demo\n")
            self.assertEqual(quick_test.resolve_submission("partition", source), source.resolve())
            self.assertEqual(quick_test.resolve_submission("partition", directory), source.resolve())

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
            for name in quick_test.LOCKED_FILES:
                self.assertTrue((cwd / name).is_file(), name)
            for name in ("Challenge.lean", "config.json", "dependency-lock.json"):
                self.assertFalse((cwd / name).exists(), name)
            generated.append((cwd / "QuickTest.lean").read_text())
            stdout = "  PASS input=0\n" if len(calls) == 2 else ""
            return subprocess.CompletedProcess(command, 0, stdout, "")

        with mock.patch.object(quick_test, "_run", side_effect=fake_run):
            result = quick_test.run_problem("saw")

        self.assertTrue(result.passed)
        self.assertEqual(calls[0], (["lake", "build", quick_test.DEMO_EXECUTABLE], 120))
        self.assertEqual(Path(calls[1][0][0]).name, quick_test.DEMO_EXECUTABLE)
        self.assertEqual(calls[1][1], 120)
        self.assertTrue(all("judge.py" not in " ".join(command) for command, _ in calls))
        self.assertIn(f"[{(2 << 32) | 1}, {(4 << 32) | 2}]", generated[0])
        self.assertIn("let expected := sawSpec n", generated[0])
        self.assertIn("import Solution", generated[0])

    def test_build_failure_stops_before_demo_execution(self):
        failed = subprocess.CompletedProcess(["lake"], 1, "", "bad proof")
        with mock.patch.object(quick_test, "_run", return_value=failed) as run:
            result = quick_test.run_problem("saw")
        self.assertFalse(result.passed)
        self.assertIn("build failed", result.detail)
        run.assert_called_once()

    def test_demo_mismatch_is_a_failure(self):
        built = subprocess.CompletedProcess(["lake"], 0, "", "")
        failed = subprocess.CompletedProcess(["lake"], 1, "", "FAIL input=10")
        with mock.patch.object(quick_test, "_run", side_effect=[built, failed]):
            result = quick_test.run_problem("saw")
        self.assertFalse(result.passed)
        self.assertIn("demo failed", result.detail)
        self.assertIn("FAIL input=10", result.detail)

    def test_sorry_warning_is_a_failure(self):
        warned = subprocess.CompletedProcess(
            ["lake"], 0, "", "warning: declaration uses `sorry`"
        )
        with mock.patch.object(quick_test, "_run", return_value=warned) as run:
            result = quick_test.run_problem("saw")
        self.assertFalse(result.passed)
        self.assertIn("uses `sorry`", result.detail)
        run.assert_called_once()

    def test_migrated_problems_point_to_supported_commands_without_building(self):
        for problem in MIGRATED_PROBLEMS:
            with self.subTest(problem=problem), mock.patch.object(quick_test, "_run") as run:
                result = quick_test.run_problem(problem)
                self.assertFalse(result.passed)
                self.assertIn("no longer has a quick demo", result.detail)
                self.assertIn(f"lake build` in problems/{problem}", result.detail)
                self.assertIn(f"evaluation/run.py --problem {problem}", result.detail)
                run.assert_not_called()

    def test_migrated_cli_is_rejected_with_migration_guidance(self):
        for problem in MIGRATED_PROBLEMS:
            with self.subTest(problem=problem):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr), \
                     mock.patch.object(quick_test, "run_problem") as run, \
                     self.assertRaises(SystemExit) as raised:
                    quick_test.main(["--problem", problem])
                self.assertEqual(raised.exception.code, 2)
                self.assertIn("no longer has a quick demo", stderr.getvalue())
                self.assertIn("lake build", stderr.getvalue())
                self.assertIn(f"evaluation/run.py --problem {problem}", stderr.getvalue())
                run.assert_not_called()

    def test_default_command_runs_only_legacy_saw(self):
        with contextlib.redirect_stdout(io.StringIO()), \
             mock.patch.object(quick_test, "run_problem", side_effect=lambda problem, *a, **kw:
                               quick_test.QuickResult(problem, True, "PASS")) as run:
            self.assertEqual(quick_test.main([]), 0)
        self.assertEqual([call.args[0] for call in run.call_args_list], list(quick_test.DEMO_CASES))
        self.assertEqual(run.call_count, 1)

    def test_core_only_problems_do_not_stage_dependencies_or_change_build(self):
        dependency_module = SimpleNamespace(validate_prepared_packages=mock.Mock())
        built = subprocess.CompletedProcess(["lake"], 0, "", "")
        ran = subprocess.CompletedProcess(["demo"], 0, "PASS", "")
        for problem in quick_test.DEMO_CASES:
            with self.subTest(problem=problem), \
                 mock.patch.dict(sys.modules, {"problem_dependencies": dependency_module}), \
                 mock.patch.object(quick_test, "_run", side_effect=[built, ran]) as run:
                result = quick_test.run_problem(problem)
                self.assertTrue(result.passed)
                self.assertEqual(
                    run.call_args_list[0].args[0],
                    ["lake", "build", quick_test.DEMO_EXECUTABLE],
                )
        dependency_module.validate_prepared_packages.assert_not_called()

    def test_unknown_problem_is_rejected_without_work(self):
        with mock.patch.object(quick_test, "_run") as run:
            result = quick_test.run_problem("conv")
        self.assertFalse(result.passed)
        self.assertIn("unknown scored problem", result.detail)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
