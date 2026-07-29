#!/usr/bin/env python3
"""Focused unit tests for judge policy and timing-control logic."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "judge"))
sys.path.insert(0, str(ROOT / "scripts"))

import judge
import perf_eval


class PerfInputTests(unittest.TestCase):
    def test_official_modes_require_seed(self):
        cfg = {"perf": {"min": 1, "max": 100, "count": 4}}
        with mock.patch.object(judge, "TIMING_METRIC", "perf_instructions"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", ""), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            with self.assertRaisesRegex(judge.InfraError, "PERF_SEED"):
                judge.perf_inputs(cfg, "demo")

    def test_shared_jitter_is_reproducible_and_exact_count(self):
        cfg = {
            "perf": {
                "min": 7, "max": 1000, "count": 10,
                "spacing": "geometric", "jitter": 0.9,
            }
        }
        with mock.patch.object(judge, "TIMING_METRIC", "perf_instructions"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", "operator-secret"), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            a1 = judge.perf_inputs(cfg, "demo")
            a2 = judge.perf_inputs(cfg, "demo")
            same_cohort = judge.perf_inputs(cfg, "demo")
        with mock.patch.object(judge, "TIMING_METRIC", "perf_instructions"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", "next-rotation"), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            next_rotation = judge.perf_inputs(cfg, "demo")

        self.assertEqual(a1, a2)
        self.assertEqual(a1, same_cohort)
        self.assertNotEqual(a1, next_rotation)
        self.assertEqual(len(a1), 10)
        self.assertTrue(all(x < y for x, y in zip(a1, a1[1:])))
        self.assertTrue(all(7 <= x <= 1000 for x in a1))

    def test_zero_min_geometric_and_linear_spacing(self):
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", ""), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            geometric = judge.perf_inputs(
                {"perf": {"min": 0, "max": 10, "count": 5,
                          "spacing": "geometric", "jitter": 0}},
                "zero")
            linear = judge.perf_inputs(
                {"perf": {"min": 0, "max": 8, "count": 5,
                          "spacing": "linear", "jitter": 0}},
                "zero")

        self.assertEqual(len(geometric), 5)
        self.assertTrue(all(x < y for x, y in zip(geometric, geometric[1:])))
        self.assertEqual(linear, [0, 2, 4, 6, 8])

    def test_malformed_perf_count_env_falls_back_to_problem_count(self):
        cfg = {"perf": {"min": 1, "max": 100, "count": 3, "jitter": 0}}
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", ""), \
             mock.patch.dict(os.environ, {"PERF_COUNT": "bogus"}):
            points = judge.perf_inputs(cfg, "demo")
        self.assertEqual(len(points), 3)

    def test_impossible_or_invalid_config_is_explicit(self):
        bad_policies = [
            {"min": -1, "max": 10, "count": 2},
            {"min": 1, "max": 2, "count": 3},
            {"min": 1, "max": 10, "count": 0},
            {"min": 1, "max": 10, "count": "bogus"},
            {"min": 1, "max": 10, "count": 2, "spacing": "random"},
            {"min": 1, "max": 10, "count": 2, "jitter": float("nan")},
        ]
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", ""), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            for perf in bad_policies:
                with self.subTest(perf=perf):
                    with self.assertRaisesRegex(judge.InfraError, "invalid perf policy"):
                        judge.perf_inputs({"perf": perf}, "bad")


class OracleAndGeneratedTheoremTests(unittest.TestCase):
    def test_oracle_and_generated_proof_disable_heartbeats(self):
        self.assertIn("set_option maxHeartbeats 0", judge._VALUE_META)
        self.assertIn("set_option maxHeartbeats 0", perf_eval._VALUE_META)
        source, theorem = judge._perf_theorem_source(7, "13", "nonce-a")
        self.assertIn("set_option maxHeartbeats 0", source)
        self.assertIn("set_option maxRecDepth 4000000", source)
        self.assertIn(f"theorem check : Submission.impl 7 = 13", source)
        self.assertTrue(theorem.startswith("LeanKernelChallengeJudge.Generated_"))
        self.assertNotIn("theorem perf_check", source)
        _, other = judge._perf_theorem_source(7, "13", "nonce-b")
        self.assertNotEqual(theorem, other)

    def test_only_wall_clock_expiry_is_an_oracle_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            with mock.patch.object(
                    judge, "run", return_value=(1, "maximum number of heartbeats has been reached")):
                kind, detail = judge._eval_impl_value(work, {}, 10, 1)
        self.assertEqual(kind, "error")
        self.assertIn("heartbeats", detail)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def _ok_response(executor="exec-a", version="v1", instructions=100, reps=1):
    return {
        "status": "ok",
        "executor": executor,
        "version": version,
        "samples": [
            {"instructions": instructions, "task_clock_ms": 1.25}
            for _ in range(reps)
        ],
    }


class RemoteTimingTests(unittest.TestCase):
    def setUp(self):
        judge._PINNED_EXECUTOR[0] = None
        judge._PINNED_EXECUTOR_IDENTITY[0] = None
        self.tmp = tempfile.TemporaryDirectory()
        self.export = Path(self.tmp.name) / "proof.export"
        self.export.write_bytes(b"proof")

    def tearDown(self):
        self.tmp.cleanup()
        judge._PINNED_EXECUTOR[0] = None
        judge._PINNED_EXECUTOR_IDENTITY[0] = None

    def test_malformed_ok_does_not_suppress_healthy_standby(self):
        malformed = {
            "status": "ok", "executor": "bad", "version": "v1", "samples": []
        }
        responses = [_Response(malformed), _Response(_ok_response("good", "v2"))]
        calls = []

        def urlopen(req, timeout):
            calls.append(req.full_url)
            return responses.pop(0)

        with mock.patch.object(judge, "TIMING_EXECUTOR_URLS", ["https://bad", "https://good"]), \
             mock.patch.object(judge, "_EXECUTOR_ATTEMPT_SLEEPS", [0]), \
             mock.patch.object(judge.urllib.request, "urlopen", side_effect=urlopen):
            result = judge._time_remote(self.export, 1)

        self.assertEqual(result["executor"], "good")
        self.assertEqual(judge._PINNED_EXECUTOR[0], "https://good")
        self.assertEqual(len(calls), 2)

    def test_non_positive_or_non_integral_instruction_sample_is_rejected(self):
        for bad in (-1, 0, 1.5, True):
            with self.subTest(instructions=bad):
                judge._PINNED_EXECUTOR[0] = None
                judge._PINNED_EXECUTOR_IDENTITY[0] = None
                response = _Response(_ok_response(instructions=bad))
                with mock.patch.object(judge, "TIMING_EXECUTOR_URLS", ["https://only"]), \
                     mock.patch.object(judge, "_EXECUTOR_ATTEMPT_SLEEPS", [0]), \
                     mock.patch.object(judge.urllib.request, "urlopen", return_value=response):
                    with self.assertRaises(judge.TimingRetry):
                        judge._time_remote(self.export, 1)
                self.assertIsNone(judge._PINNED_EXECUTOR[0])

    def test_executor_identity_and_version_cannot_change_mid_submission(self):
        responses = [
            _Response(_ok_response("exec-a", "v1")),
            _Response(_ok_response("exec-b", "v2")),
        ]
        with mock.patch.object(judge, "TIMING_EXECUTOR_URLS", ["https://one"]), \
             mock.patch.object(judge, "_EXECUTOR_ATTEMPT_SLEEPS", [0]), \
             mock.patch.object(judge.urllib.request, "urlopen", side_effect=responses):
            first = judge._time_remote(self.export, 1)
            self.assertEqual(first["executor"], "exec-a")
            with self.assertRaises(judge.TimingRetry):
                judge._time_remote(self.export, 1)

        self.assertEqual(judge._PINNED_EXECUTOR_IDENTITY[0], ("exec-a", "v1"))


class SlotAccountingTests(unittest.TestCase):
    def test_timeouts_do_not_stop_later_slots(self):
        called = []

        def probe(n):
            called.append(n)
            if n in (10, 30):
                return {"n": n, "result": "timeout"}, None
            return {"n": n, "result": "ok", "median_instructions": n}, None

        scaling, error = judge._collect_perf_slots([10, 20, 30, 40], probe)
        self.assertIsNone(error)
        self.assertEqual(called, [10, 20, 30, 40])
        self.assertEqual([row["slot"] for row in scaling], [0, 1, 2, 3])
        self.assertEqual([row["result"] for row in scaling],
                         ["timeout", "ok", "timeout", "ok"])
        self.assertEqual(judge._headline_row(scaling)["n"], 40)
        self.assertEqual(
            judge._coverage_fields([10, 20, 30, 40], scaling),
            {"successful_slots": 2, "total_slots": 4, "coverage": 0.5},
        )

    def test_fatal_error_marks_later_slots_not_run(self):
        def probe(n):
            if n == 20:
                return {"n": n, "result": "build-error"}, "boom"
            return {"n": n, "result": "ok", "median_instructions": n}, None

        scaling, error = judge._collect_perf_slots([10, 20, 30], probe)
        self.assertEqual(error, "boom")
        self.assertEqual([row["result"] for row in scaling],
                         ["ok", "build-error", "not-run"])
        self.assertEqual([row["slot"] for row in scaling], [0, 1, 2])

    def test_canonical_work_includes_correctness_and_all_completed_slots(self):
        correctness = {
            "result": "ok", "metric": "perf_instructions", "median_instructions": 11
        }
        scaling = [
            {"slot": 0, "n": 10, "result": "timeout"},
            {"slot": 1, "n": 20, "result": "ok", "median_instructions": 23},
            {"slot": 2, "n": 30, "result": "ok", "median_instructions": 31},
        ]
        self.assertEqual(
            judge._canonical_work(correctness, scaling, "perf_instructions"),
            {
                "metric": "perf_instructions",
                "correctness_median": 11,
                "completed_curve_sum": 54,
                "total": 65,
                "completed_slots": 2,
            },
        )


class ExportPinTests(unittest.TestCase):
    def test_export_pin_detects_change_between_consumers(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proof.export"
            path.write_bytes(b"one")
            pinned = judge._pin_export_bytes(path)
            self.assertTrue(judge._export_matches(path, pinned))
            path.chmod(0o644)
            path.write_bytes(b"two")
            self.assertFalse(judge._export_matches(path, pinned))


class ArtifactIdentityTests(unittest.TestCase):
    def test_verified_olean_graph_is_pinned(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            lib = work / ".lake" / "build" / "lib" / "lean"
            (lib / "Submission").mkdir(parents=True)
            (lib / "Submission.olean").write_bytes(b"verified impl")
            (lib / "Submission" / "Helper.olean").write_bytes(b"verified helper")

            pinned_lib, snapshot, digest = judge._snapshot_verified_artifacts(work)

            self.assertEqual(pinned_lib, lib)
            self.assertEqual(len(snapshot), 2)
            self.assertEqual(len(digest), 64)
            self.assertTrue(judge._artifacts_match(lib, snapshot))
            (lib / "Submission.olean").chmod(0o644)
            (lib / "Submission.olean").write_bytes(b"different impl")
            self.assertFalse(judge._artifacts_match(lib, snapshot))


class EnvironmentBoundaryTests(unittest.TestCase):
    def test_untrusted_tool_environment_excludes_judge_secrets_and_mode_switches(self):
        with mock.patch.dict(os.environ, {
            "PERF_SEED": "secret",
            "TIMING_EXECUTOR_SECRET": "bearer",
            "OFFICIAL_EVAL": "1",
            "EVALUATION_COHORT": "round-x",
        }):
            env = judge.tool_env()

        self.assertNotIn("PERF_SEED", env)
        self.assertNotIn("TIMING_EXECUTOR_SECRET", env)
        self.assertNotIn("OFFICIAL_EVAL", env)
        self.assertNotIn("EVALUATION_COHORT", env)
        self.assertEqual(env["LEAN_ABORT_ON_PANIC"], "1")
        self.assertIn("ELAN_HOME", env)

    def test_cohort_id_commits_to_schedule(self):
        cfg = {"perf": {"min": 1, "max": 10, "count": 2}}
        result = {"stages": {}}
        with mock.patch.object(judge, "EVALUATION_COHORT", "round-x"):
            first = judge._evaluation_cohort("demo", cfg, [1, 10], 3, result)
            same = judge._evaluation_cohort("demo", cfg, [1, 10], 3, result)
            changed = judge._evaluation_cohort("demo", cfg, [1, 9], 3, result)

        self.assertEqual(first["id"], same["id"])
        self.assertNotEqual(first["id"], changed["id"])
        self.assertEqual(first["round"], "round-x")


if __name__ == "__main__":
    unittest.main()
