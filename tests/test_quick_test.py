#!/usr/bin/env python3
"""Unit tests for the public, non-scoring quick-test helper."""

import os
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
from problem_layout import iter_evaluation_problem_dirs  # noqa: E402


class QuickTestTests(unittest.TestCase):
    def test_every_scored_problem_has_public_demo_cases(self):
        scored = {
            path.name for path in iter_evaluation_problem_dirs(ROOT)
            if path.name != "conv"
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
            for name in ("Spec.lean", "Challenge.lean", "Solution.lean", "config.json", "dependency-lock.json"):
                self.assertFalse((cwd / name).exists(), name)
            generated.append((cwd / "QuickTest.lean").read_text())
            stdout = "  PASS input=0\n" if len(calls) == 2 else ""
            return subprocess.CompletedProcess(command, 0, stdout, "")

        with mock.patch.object(quick_test, "_stage_dependencies", return_value=True), \
             mock.patch.object(quick_test, "_run", side_effect=fake_run):
            result = quick_test.run_problem("fib")

        self.assertTrue(result.passed)
        self.assertEqual(calls[0], (["lake", "--no-cache", "build", quick_test.FIB_DEMO_EXECUTABLE], 120))
        self.assertEqual(Path(calls[1][0][0]).name, quick_test.FIB_DEMO_EXECUTABLE)
        self.assertEqual(calls[1][1], 120)
        self.assertTrue(all("judge.py" not in " ".join(command) for command, _ in calls))
        self.assertIn("[0, 1, 2, 10, 20]", generated[0])
        self.assertIn("example : ∀ n : Nat, Submission.impl n = Nat.fib n := Submission.impl_correct", generated[0])
        self.assertIn("import Submission", generated[0])
        self.assertNotIn("import Solution", generated[0])

    def test_build_failure_stops_before_demo_execution(self):
        failed = subprocess.CompletedProcess(["lake"], 1, "", "bad proof")
        with mock.patch.object(quick_test, "_stage_dependencies", return_value=True), \
             mock.patch.object(quick_test, "_run", return_value=failed) as run:
            result = quick_test.run_problem("fib")
        self.assertFalse(result.passed)
        self.assertIn("build failed", result.detail)
        run.assert_called_once()

    def test_demo_mismatch_is_a_failure(self):
        built = subprocess.CompletedProcess(["lake"], 0, "", "")
        failed = subprocess.CompletedProcess(["lake"], 1, "", "FAIL input=10")
        with mock.patch.object(quick_test, "_stage_dependencies", return_value=True), \
             mock.patch.object(quick_test, "_run", side_effect=[built, failed]):
            result = quick_test.run_problem("fib")
        self.assertFalse(result.passed)
        self.assertIn("demo failed", result.detail)
        self.assertIn("FAIL input=10", result.detail)

    def test_sorry_warning_is_a_failure(self):
        warned = subprocess.CompletedProcess(
            ["lake"], 0, "", "warning: declaration uses `sorry`"
        )
        with mock.patch.object(quick_test, "_stage_dependencies", return_value=True), \
             mock.patch.object(quick_test, "_run", return_value=warned) as run:
            result = quick_test.run_problem("fib")
        self.assertFalse(result.passed)
        self.assertIn("uses `sorry`", result.detail)
        run.assert_called_once()

    def test_fib_stages_exact_manifest_and_links_validated_packages(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            problem_dir = root / "fib"
            packages = problem_dir / ".lake" / "packages"
            packages.mkdir(parents=True)
            (packages / "prepared-marker").write_text("unchanged")
            manifest = b'{"packages": [{"name": "mathlib", "rev": "pinned"}]}\n'
            (problem_dir / "lake-manifest.json").write_bytes(manifest)
            validator = mock.Mock(return_value=packages)
            dependency_module = SimpleNamespace(validate_prepared_packages=validator)
            with tempfile.TemporaryDirectory() as temp_work, \
                 mock.patch.dict(sys.modules, {"problem_dependencies": dependency_module}), \
                 mock.patch.object(quick_test, "_run") as run:
                work = Path(temp_work)
                self.assertTrue(quick_test._stage_dependencies("fib", problem_dir, work))
                self.assertEqual((work / "lake-manifest.json").read_bytes(), manifest)
                link = work / ".lake" / "packages"
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), packages.resolve())
                validator.assert_called_once_with(problem_dir)
                run.assert_not_called()
            # Deleting the disposable workspace must not remove shared packages.
            self.assertEqual((packages / "prepared-marker").read_text(), "unchanged")

    def test_fib_dependency_failure_explains_setup_without_building(self):
        for failure in (ValueError("manifest revision mismatch"), OSError("cache missing")):
            with self.subTest(failure=failure):
                validator = mock.Mock(side_effect=failure)
                dependency_module = SimpleNamespace(validate_prepared_packages=validator)
                with mock.patch.dict(sys.modules, {"problem_dependencies": dependency_module}), \
                     mock.patch.object(quick_test, "_run") as run:
                    result = quick_test.run_problem("fib")
                self.assertFalse(result.passed)
                self.assertIn("dependency setup is missing or inconsistent", result.detail)
                self.assertIn(
                    "python3 problems/fib/setup.py", result.detail
                )
                run.assert_not_called()

    def test_core_only_problems_do_not_stage_dependencies_or_change_build(self):
        dependency_module = SimpleNamespace(validate_prepared_packages=mock.Mock())
        built = subprocess.CompletedProcess(["lake"], 0, "", "")
        ran = subprocess.CompletedProcess(["demo"], 0, "PASS", "")
        for problem in set(quick_test.DEMO_CASES) - {"fib"}:
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
