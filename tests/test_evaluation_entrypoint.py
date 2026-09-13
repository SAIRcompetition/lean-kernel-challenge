"""The optional fib entrypoint stages one file and delegates all judging."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("fib_evaluation_entrypoint", ROOT / "evaluation/run.py")
entrypoint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(entrypoint)


class EvaluationEntrypointTests(unittest.TestCase):
    def test_default_submission_is_participant_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "problems/fib/Submission.lean"
            source.parent.mkdir(parents=True)
            source.write_text("-- participant\n")
            with mock.patch.object(entrypoint, "ROOT", root):
                self.assertEqual(entrypoint.resolve_submission(), source.resolve())

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
                evaluate.assert_called_once_with(source.resolve(), 120)
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

    def test_main_rejects_non_fib_problem(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            entrypoint.main(["--problem", "sha256"])
        self.assertEqual(error.exception.code, 2)

    def test_setup_delegates_to_existing_canonical_setup(self):
        script = (ROOT / "evaluation/setup.sh").read_text()
        self.assertIn('exec bash "$EVALUATION_ROOT/scripts/setup.sh" "$@"', script)
        self.assertNotIn("git ", script)


if __name__ == "__main__":
    unittest.main()
