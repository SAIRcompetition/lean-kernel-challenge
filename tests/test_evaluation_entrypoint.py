"""Optional evaluator entrypoints stage one file and delegate all judging."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from problem_layout import evaluation_problem_dir

SPEC = importlib.util.spec_from_file_location("fib_evaluation_entrypoint", ROOT / "evaluation/run.py")
entrypoint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(entrypoint)


class EvaluationEntrypointTests(unittest.TestCase):
    def test_exactly_eight_supported_problems(self):
        self.assertEqual(set(entrypoint.SUPPORTED_PROBLEMS), {
            "fib", "ca-rule110", "mertens", "partition", "permanent", "polydisc", "primecount", "sha256",
        })

    def test_default_submission_is_participant_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "problems/fib/Submission.lean"
            source.parent.mkdir(parents=True)
            source.write_text("-- participant\n")
            with mock.patch.object(entrypoint, "ROOT", root):
                self.assertEqual(entrypoint.resolve_submission(), source.resolve())

    def test_each_problem_defaults_to_its_own_participant_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for problem in entrypoint.SUPPORTED_PROBLEMS:
                source = root / "problems" / problem / "Submission.lean"
                source.parent.mkdir(parents=True)
                source.write_text("-- participant\n")
                with self.subTest(problem=problem), mock.patch.object(entrypoint, "ROOT", root):
                    self.assertEqual(entrypoint.resolve_submission(problem=problem), source.resolve())

    def test_missing_file_and_directory_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for source in (directory, directory / "missing.lean"):
                with self.subTest(source=source), self.assertRaisesRegex(ValueError, "existing file"):
                    entrypoint.resolve_submission(source)

    def test_only_selected_file_is_staged_and_source_is_preserved(self):
        seen = []
        verdict = {"status": "accepted", "scored": True}
        with tempfile.TemporaryDirectory() as temporary:
            original = Path(temporary)
            source = original / "Submission.lean"
            contents = b"import Mathlib.Data.Nat.Fib.Basic\n-- original\n"
            source.write_bytes(contents)
            neighbor = original / "Spec.lean"
            neighbor.write_text("-- not part of submission\n")
            before = source.stat()

            def canonical(problem, payload, timeout):
                self.assertEqual(problem, "fib")
                self.assertEqual(timeout, 123)
                self.assertNotEqual(payload, original)
                self.assertEqual([p.name for p in payload.iterdir()], ["Submission.lean"])
                self.assertEqual((payload / "Submission.lean").read_bytes(), contents)
                (payload / "Submission.lean").write_text("-- disposable copy changed\n")
                seen.append(payload)
                return verdict

            evaluator = SimpleNamespace(evaluate=mock.Mock(side_effect=canonical))
            with mock.patch.object(entrypoint, "_canonical_evaluator", return_value=evaluator):
                self.assertIs(entrypoint.evaluate_file(source, 123), verdict)
            evaluator.evaluate.assert_called_once()
            self.assertEqual(source.read_bytes(), contents)
            self.assertEqual(source.stat().st_mtime_ns, before.st_mtime_ns)
            self.assertEqual(neighbor.read_text(), "-- not part of submission\n")
        self.assertFalse(seen[0].exists())

    def test_payload_is_cleaned_up_if_canonical_call_raises(self):
        seen = []

        def canonical(_problem, payload, _timeout):
            seen.append(payload)
            raise ValueError("failure")

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "Submission.lean"
            source.write_text("-- unchanged\n")
            evaluator = SimpleNamespace(evaluate=canonical)
            with mock.patch.object(entrypoint, "_canonical_evaluator", return_value=evaluator), \
                 self.assertRaisesRegex(ValueError, "failure"):
                entrypoint.evaluate_file(source)
            self.assertEqual(source.read_text(), "-- unchanged\n")
        self.assertFalse(seen[0].exists())

    def test_every_supported_problem_uses_single_file_canonical_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "my-implementation.lean"
            source.write_text("-- source\n")
            (source.parent / "Spec.lean").write_text("-- must not be submitted\n")
            for problem in entrypoint.SUPPORTED_PROBLEMS:
                seen = []

                def canonical(selected, payload, timeout):
                    self.assertEqual(selected, problem)
                    self.assertEqual(timeout, 17)
                    self.assertEqual([p.name for p in payload.iterdir()], ["Submission.lean"])
                    self.assertEqual((payload / "Submission.lean").read_text(), "-- source\n")
                    seen.append(payload)
                    return {"problem": selected, "status": "accepted"}

                with self.subTest(problem=problem), \
                     mock.patch.object(entrypoint, "_canonical_evaluator",
                                       return_value=SimpleNamespace(evaluate=canonical)):
                    self.assertEqual(entrypoint.evaluate_file(source, 17, problem=problem)["problem"], problem)
                self.assertFalse(seen[0].exists())

    def test_nonpositive_timeout_does_not_call_canonical(self):
        with mock.patch.object(entrypoint, "_canonical_evaluator") as load:
            with self.assertRaisesRegex(ValueError, "positive"):
                entrypoint.evaluate_file("Submission.lean", 0)
        load.assert_not_called()

    def test_perf_count_override_is_rejected_before_judging(self):
        for value in ("1", "6", "0", " "):
            with self.subTest(value=value), mock.patch.dict(os.environ, {"PERF_COUNT": value}), \
                 mock.patch.object(entrypoint, "_canonical_evaluator") as load, \
                 self.assertRaisesRegex(ValueError, "unset PERF_COUNT"):
                entrypoint.evaluate_file("Submission.lean")
            load.assert_not_called()

    def test_main_reports_local_result_and_propagates_verdict_status(self):
        for status, expected in (("accepted", 0), ("rejected", 1), ("error", 2), ("retry", 3)):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "Submission.lean"
                source.write_text("-- source\n")
                verdict = {
                    "status": status, "reason": "test reason",
                    "timing": {"scaling": [{"n": 5000, "result": "ok", "median_s": 0.25}]},
                }
                writes = []
                evaluator = SimpleNamespace(_atomic_write=lambda path, text: writes.append((path, text)))
                output = io.StringIO()
                with mock.patch.object(entrypoint, "ROOT", root), \
                     mock.patch.object(entrypoint, "evaluate_file", return_value=verdict) as evaluate, \
                     mock.patch.object(entrypoint, "_canonical_evaluator", return_value=evaluator), \
                     contextlib.redirect_stdout(output):
                    result = entrypoint.main(["--problem", "fib", "--submission", str(source)])
                self.assertEqual(result, expected)
                evaluate.assert_called_once_with(source.resolve(), 120, problem="fib")
                self.assertIn("not official scores", output.getvalue())
                self.assertIn(f"fib/Submission.lean: {status}", output.getvalue())
                self.assertIn("n=5000: OK (0.25s)", output.getvalue())
                self.assertEqual(writes[0][0].parent, root / "results/local-evaluation/fib")
                self.assertEqual(json.loads(writes[0][1]), verdict)

    def test_main_missing_submission_returns_error_without_judging(self):
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(entrypoint, "ROOT", Path(temporary)), \
             mock.patch.object(entrypoint, "evaluate_file") as evaluate, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(entrypoint.main([]), 2)
        self.assertIn("existing file", error.getvalue())
        evaluate.assert_not_called()

    def test_main_writes_results_to_the_selected_problem_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for problem in entrypoint.SUPPORTED_PROBLEMS:
                source = root / "problems" / problem / "Submission.lean"
                source.parent.mkdir(parents=True)
                source.write_text("-- source\n")
                verdict = {"problem": problem, "status": "accepted"}
                writes = []
                evaluator = SimpleNamespace(_atomic_write=lambda path, text: writes.append((path, text)))
                output = io.StringIO()
                with self.subTest(problem=problem), mock.patch.object(entrypoint, "ROOT", root), \
                     mock.patch.object(entrypoint, "evaluate_file", return_value=verdict) as evaluate, \
                     mock.patch.object(entrypoint, "_canonical_evaluator", return_value=evaluator), \
                     contextlib.redirect_stdout(output):
                    self.assertEqual(entrypoint.main(["--problem", problem]), 0)
                evaluate.assert_called_once_with(source.resolve(), 120, problem=problem)
                self.assertIn(f"{problem}/Submission.lean: accepted", output.getvalue())
                self.assertEqual(writes[0][0].parent, root / "results/local-evaluation" / problem)
                self.assertEqual(json.loads(writes[0][1]), verdict)

    def test_unmigrated_problems_are_rejected_before_work(self):
        for problem in ("saw", "conv", "missing", "../fib"):
            with self.subTest(problem=problem), \
                 mock.patch.object(entrypoint, "_canonical_evaluator") as load, \
                 self.assertRaisesRegex(ValueError, "unsupported problem"):
                entrypoint.evaluate_file("Submission.lean", problem=problem)
            load.assert_not_called()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                entrypoint.main(["--problem", problem])
            self.assertEqual(error.exception.code, 2)


class EvaluationSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.evaluation = self.root / "evaluation"
        self.evaluation.mkdir()
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        self.log = self.root / "calls.txt"
        shutil.copy2(ROOT / "evaluation/setup.sh", self.evaluation / "setup.sh")
        shutil.copy2(ROOT / "scripts/problem_layout.py", self.scripts / "problem_layout.py")
        (self.scripts / "setup.sh").write_text(
            '#!/usr/bin/env bash\nset -euo pipefail\nprintf "tools %s\\n" "$*" >> "$SETUP_CALL_LOG"\n'
        )
        (self.scripts / "prepare_problem_dependencies.py").write_text(
            'import os, sys\nwith open(os.environ["SETUP_CALL_LOG"], "a") as out:\n'
            '    out.write("dependencies " + " ".join(sys.argv[1:]) + "\\n")\n'
        )
        for problem in entrypoint.SUPPORTED_PROBLEMS:
            work = evaluation_problem_dir(self.root, problem)
            work.mkdir(parents=True)
            (work / "config.json").write_text("{}")
            if problem == "fib":
                (work / "dependency-lock.json").write_text("{}")

    def run_setup(self, *args):
        return subprocess.run(
            ["bash", str(self.evaluation / "setup.sh"), *args],
            env=dict(os.environ, SETUP_CALL_LOG=str(self.log)),
            capture_output=True, text=True, timeout=10,
        )

    def test_default_prepares_all_eight_but_only_downloads_locked_dependencies(self):
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ["tools --tools-only", "dependencies --problem fib"])
        self.assertIn("Evaluator setup complete: " + " ".join(entrypoint.SUPPORTED_PROBLEMS), result.stdout)

    def test_selected_core_problem_does_not_prepare_mathlib(self):
        result = self.run_setup("--problem", "sha256")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ["tools --tools-only"])
        self.assertIn("Evaluator setup complete: sha256", result.stdout)

    def test_selected_problems_are_deduplicated(self):
        result = self.run_setup("--problem", "fib", "--problem", "partition", "--problem", "fib")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ["tools --tools-only", "dependencies --problem fib"])
        self.assertIn("Evaluator setup complete: fib partition", result.stdout)

    def test_bad_options_and_missing_workspace_fail_before_shared_setup(self):
        for args in (("--problem", "saw"), ("--problem", "conv"), ("--problem",), ("--unknown",)):
            with self.subTest(args=args):
                result = self.run_setup(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(self.log.exists())
        (evaluation_problem_dir(self.root, "fib") / "config.json").unlink()
        result = self.run_setup("--problem", "fib")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_help_does_not_build_or_download(self):
        result = self.run_setup("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--problem", result.stdout)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
