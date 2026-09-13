"""Active evaluator discovery must not resurrect locally retained retired tasks."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from problem_layout import EVALUATION_PROBLEMS, evaluation_problem_dir, iter_evaluation_problem_dirs


class ProblemLayoutTests(unittest.TestCase):
    def test_retired_assets_are_excluded_from_git_and_image_context(self):
        retired_paths = (
            "problems/saw/", "evaluation/problems/saw/", "examples/submissions/saw/",
            "problems/conv/", "evaluation/problems/conv/", "examples/submissions/conv/",
            "rules/problems/conv.md", "scripts/gen_conv_bank.py",
            "rules/problems/saw.md", "scripts/quick_test.py",
            "tests/test_quick_test.py", "tests/retired_saw_quick_test.py",
        )
        for ignore_file in (".gitignore", ".dockerignore"):
            patterns = {line.lstrip("/") for line in (ROOT / ignore_file).read_text().splitlines()}
            for path in retired_paths:
                with self.subTest(ignore_file=ignore_file, path=path):
                    self.assertIn(path, patterns)

    def test_dependency_cli_rejects_retired_task_without_preparation(self):
        for problem in ("saw", "conv"):
            with self.subTest(problem=problem):
                result = subprocess.run([
                    sys.executable, str(ROOT / "scripts/prepare_problem_dependencies.py"),
                    "--problem", problem,
                ], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2)
                self.assertIn(f"retired evaluator problem: {problem}", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_supported_registry_is_exactly_eight_tasks(self):
        self.assertEqual(EVALUATION_PROBLEMS, {
            "fib", "ca-rule110", "mertens", "partition", "permanent", "polydisc",
            "primecount", "sha256",
        })

    def test_retained_configs_cannot_reenter_evaluator_discovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in ("evaluation/problems/fib", "problems/conv", "evaluation/problems/conv", "problems/saw",
                             "evaluation/problems/saw", "problems/unknown", "problems/sha256"):
                path = root / relative
                path.mkdir(parents=True)
                (path / "config.json").write_text("{}")
            self.assertEqual(
                list(iter_evaluation_problem_dirs(root)),
                [root / "evaluation/problems/fib"],
            )
            for problem in ("saw", "conv", "unknown"):
                with self.subTest(problem=problem), self.assertRaises(ValueError):
                    evaluation_problem_dir(root, problem)
            self.assertTrue((root / "problems/saw/config.json").is_file())
            self.assertTrue((root / "problems/conv/config.json").is_file())

    def test_layout_cli_rejects_retired_task_before_using_retained_config(self):
        with tempfile.TemporaryDirectory() as temp:
            for problem in ("saw", "conv"):
                with self.subTest(problem=problem):
                    config = Path(temp) / "problems" / problem / "config.json"
                    config.parent.mkdir(parents=True)
                    config.write_text("{}")
                    result = subprocess.run([
                        sys.executable, str(ROOT / "scripts/problem_layout.py"),
                        "--root", temp, "--problem", problem,
                    ], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(f"retired evaluator problem: {problem}", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual(result.stdout, "")

    def test_local_evaluator_rejects_retired_config_without_starting_judge(self):
        from unittest import mock
        import perf_eval

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for problem in ("saw", "conv"):
                config = root / "problems" / problem / "config.json"
                config.parent.mkdir(parents=True)
                config.write_text("{}")
                with self.subTest(problem=problem), mock.patch.object(perf_eval, "BASE", root), \
                     mock.patch.object(perf_eval._judge, "judge") as judge_mock:
                    verdict = perf_eval.evaluate(problem, root / "submission")
                    self.assertEqual(verdict["status"], "error")
                    self.assertIn(f"retired evaluator problem: {problem}", verdict["reason"])
                    judge_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
