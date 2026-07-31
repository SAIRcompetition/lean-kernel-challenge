#!/usr/bin/env python3
"""Coverage for the two output entry points and the verdict-contract classifiers.

`score.py main()` and `judge.py leaderboard()` are the only functions that produce the public
report, and they had zero coverage — which is exactly how a crash on a single malformed verdict
survived two rewrite cycles. These tests run BOTH entry points over a results/ tree containing
deliberately malformed verdicts, plus the signal/slug/payload classifiers that decide whether a
failure is the contestant's fault or the infrastructure's.

Run: python3 tests/test_reporting_and_contract.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "judge"))
sys.path.insert(0, str(ROOT / "scripts"))

import judge as JUDGE  # noqa: E402


def _verdict(**over):
    """A minimally well-formed accepted verdict; keyword args override any field."""
    v = {
        "problem": "fib",
        "submission": "s",
        "status": "accepted",
        "metric": "wall_time",
        "stages": {"perf_inputs": [1, 2]},
        "timing": {"scaling": [{"slot": 0, "n": 1, "result": "ok", "median_s": 1.0},
                               {"slot": 1, "n": 2, "result": "ok", "median_s": 2.0}]},
        "correctness_timing": {"result": "ok", "median_s": 0.5},
        "evaluation_cohort": {"id": "c1", "round": "r1"},
    }
    v.update(over)
    return v


class MalformedVerdictReporting(unittest.TestCase):
    """Neither report tool may crash on a bad file; a bad file must not hide the good ones."""

    MALFORMED = [
        ("null_metric", _verdict(metric=None)),
        ("cohort_missing_id", _verdict(evaluation_cohort={"round": "r1"})),
        ("cohort_not_dict", _verdict(evaluation_cohort="nope")),
        ("cohort_null_id", _verdict(evaluation_cohort={"id": None})),
        ("no_stages", {"problem": "fib", "submission": "x", "status": "accepted"}),
        ("null_status", _verdict(status=None)),
    ]

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="report_test_"))
        (self.tmp / "fib").mkdir(parents=True)
        for name, v in self.MALFORMED:
            (self.tmp / "fib" / f"{name}.json").write_text(json.dumps(v))
        (self.tmp / "fib" / "good.json").write_text(json.dumps(_verdict(submission="good")))
        (self.tmp / "fib" / "corrupt.json").write_text("{not json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, script):
        """Run an entry point with RESULTS pointed at the malformed tree."""
        code = (
            "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
            "import pathlib\n"
            "import %s as M\n"
            "M.RESULTS = %s\n"
            "M.%s()\n"
        ) % (
            str(ROOT / "judge"), str(ROOT / "scripts"),
            script,
            ("pathlib.Path(%r)" % str(self.tmp)) if script == "judge" else repr(str(self.tmp)),
            "leaderboard" if script == "judge" else "main",
        )
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              cwd=str(ROOT))

    def test_leaderboard_survives_malformed_verdicts(self):
        p = self._run("judge")
        self.assertEqual(p.returncode, 0, f"leaderboard crashed: {p.stderr[-400:]}")
        self.assertNotIn("Traceback", p.stderr)

    def test_score_survives_malformed_verdicts(self):
        p = self._run("score")
        self.assertEqual(p.returncode, 0, f"score.py crashed: {p.stderr[-400:]}")
        self.assertNotIn("Traceback", p.stderr)


class SignalClassification(unittest.TestCase):
    """A trusted tool killed by a signal is an infra fault, never a contestant rejection."""

    def test_signal_exits_are_infrastructure(self):
        for rc in (-11, -9, 139, 137):
            self.assertTrue(JUDGE._died_by_signal(rc), f"{rc} should count as a signal death")

    def test_ordinary_exits_are_not(self):
        for rc in (0, 1, 2, 127, "timeout", None):
            self.assertFalse(JUDGE._died_by_signal(rc), f"{rc} must not count as a signal death")


class SlugValidation(unittest.TestCase):
    """A leading dash would be read as an option when the slug reaches argv."""

    def test_leading_dash_rejected(self):
        for bad in ("--reps", "-x", "-", ".", "..", "", "a/b", "a b"):
            self.assertFalse(JUDGE.valid_slug(bad), f"{bad!r} must be rejected")

    def test_ordinary_names_accepted(self):
        for good in ("fib", "a-b", "x.perf", "A_1", "baseline"):
            self.assertTrue(JUDGE.valid_slug(good), f"{good!r} must be accepted")


class PayloadPreflight(unittest.TestCase):
    """Caps and special files are enforced on the SOURCE, before anything is copied."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="payload_test_"))
        (self.tmp / "Submission").mkdir()
        (self.tmp / "Submission.lean").write_text("-- impl\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_accepts_ordinary_payload(self):
        (self.tmp / "Submission" / "Helpers.lean").write_text("-- helper\n")
        JUDGE._preflight_payload(self.tmp)          # must not raise

    def test_rejects_fifo(self):
        os.mkfifo(self.tmp / "Submission" / "evil.lean")
        with self.assertRaises(JUDGE.SubmissionError):
            JUDGE._preflight_payload(self.tmp)

    def test_rejects_oversize_before_copy(self):
        big = b"x" * (JUDGE.MAX_SUBMISSION_BYTES + 1)
        (self.tmp / "Submission" / "big.lean").write_bytes(big)
        with self.assertRaises(JUDGE.SubmissionError):
            JUDGE._preflight_payload(self.tmp)

    def test_rejects_too_many_files(self):
        for i in range(JUDGE.MAX_SUBMISSION_FILES + 2):
            (self.tmp / "Submission" / f"f{i}.lean").write_text("-- x\n")
        with self.assertRaises(JUDGE.SubmissionError):
            JUDGE._preflight_payload(self.tmp)


class PerfPhaseBudget(unittest.TestCase):
    """The whole performance phase is bounded, and exhaustion still yields a full slot record."""

    def test_exhausted_budget_marks_remaining_slots(self):
        seen = []

        def probe(n):
            seen.append(n)
            return {"n": n, "result": "ok"}, None

        # A deadline already in the past: no slot may run, every slot is still recorded.
        scaling, err = JUDGE._collect_perf_slots([1, 2, 3], probe, deadline=0.0)
        self.assertIsNone(err)
        self.assertEqual(seen, [])
        self.assertEqual([r["result"] for r in scaling], ["budget-exhausted"] * 3)
        self.assertEqual([r["n"] for r in scaling], [1, 2, 3])

    def test_no_deadline_probes_every_slot(self):
        scaling, err = JUDGE._collect_perf_slots(
            [1, 2], lambda n: ({"n": n, "result": "ok"}, None), deadline=None)
        self.assertIsNone(err)
        self.assertEqual([r["result"] for r in scaling], ["ok", "ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
