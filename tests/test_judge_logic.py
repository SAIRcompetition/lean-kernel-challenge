#!/usr/bin/env python3
"""Focused unit tests for judge policy and timing-control logic."""

import json
import os
import sys
import tempfile
import time
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


class DeferredTimingModeTests(unittest.TestCase):
    def test_deferred_timing_requires_retained_nonofficial_workspace(self):
        with mock.patch.object(judge, "DEFER_TIMING", True), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "TIMING_EXECUTOR_URLS", []):
            judge._validate_timing_mode(True)
            with self.assertRaisesRegex(judge.InfraError, "--keep-workspace"):
                judge._validate_timing_mode(False)

    def test_deferred_timing_rejects_official_or_in_judge_remote_modes(self):
        cases = [
            {"OFFICIAL_EVAL": True, "TIMING_METRIC": "wall_time",
             "TIMING_EXECUTOR_URLS": []},
            {"OFFICIAL_EVAL": False, "TIMING_METRIC": "perf_instructions",
             "TIMING_EXECUTOR_URLS": []},
            {"OFFICIAL_EVAL": False, "TIMING_METRIC": "wall_time",
             "TIMING_EXECUTOR_URLS": ["https://timer.example"]},
        ]
        for values in cases:
            with self.subTest(values=values), \
                 mock.patch.object(judge, "DEFER_TIMING", True), \
                 mock.patch.object(judge, "OFFICIAL_EVAL", values["OFFICIAL_EVAL"]), \
                 mock.patch.object(judge, "TIMING_METRIC", values["TIMING_METRIC"]), \
                 mock.patch.object(
                     judge, "TIMING_EXECUTOR_URLS", values["TIMING_EXECUTOR_URLS"]):
                with self.assertRaises(judge.InfraError):
                    judge._validate_timing_mode(True)

    def test_deferred_measurement_preserves_remote_contract_fields(self):
        target = "LeanKernelChallengeJudge.Generated_demo.check"
        self.assertEqual(judge._deferred_measurement(), {
            "result": "deferred",
            "measurement_contract": judge.MEASUREMENT_CONTRACT,
            "measurement_boundary": judge.FULL_REPLAY_BOUNDARY,
            "measurement_target": None,
        })
        self.assertEqual(judge._deferred_measurement(target), {
            "result": "deferred",
            "measurement_contract": judge.MEASUREMENT_CONTRACT,
            "measurement_boundary": judge.TARGET_REPLAY_BOUNDARY,
            "measurement_target": target,
        })

    def test_deferred_timing_never_invokes_the_local_measurement(self):
        measure = mock.Mock(return_value=("ok", [{"wall_ns": 1}]))
        with mock.patch.object(judge, "DEFER_TIMING", True):
            self.assertEqual(judge._measure_or_defer(measure), ("deferred", None))
        measure.assert_not_called()

        with mock.patch.object(judge, "DEFER_TIMING", False):
            self.assertEqual(
                judge._measure_or_defer(measure),
                ("ok", [{"wall_ns": 1}]),
            )
        measure.assert_called_once_with()


class LiveStageProgressTests(unittest.TestCase):
    def test_progress_stream_is_optional(self):
        with mock.patch.object(judge, "SAIR_PROGRESS_FILE", ""), \
             mock.patch.object(judge.time, "monotonic", return_value=8.0):
            judge._emit_stage_progress("comparator", "done", 7.0)

    def test_progress_event_preserves_a_real_zero_duration(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "progress.jsonl"
            path.write_bytes(b"")
            with mock.patch.object(judge, "SAIR_PROGRESS_FILE", str(path)), \
                 mock.patch.object(judge.time, "monotonic", return_value=7.0):
                judge._emit_stage_progress("comparator", "done", 7.0)

            self.assertEqual(json.loads(path.read_text()), {
                "key": "comparator",
                "status": "done",
                "durationMs": 0,
            })

    def test_progress_target_must_already_exist(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "missing.jsonl"
            with mock.patch.object(judge, "SAIR_PROGRESS_FILE", str(path)):
                with self.assertRaisesRegex(judge.InfraError, "cannot append"):
                    judge._emit_stage_progress("axiom_audit", "failed", time.monotonic())

    def test_progress_rejects_invalid_status_and_key(self):
        with mock.patch.object(judge, "SAIR_PROGRESS_FILE", "/unused"):
            with self.assertRaisesRegex(judge.InfraError, "status"):
                judge._emit_stage_progress("comparator", "running", time.monotonic())
            with self.assertRaisesRegex(judge.InfraError, "stage key"):
                judge._emit_stage_progress("Comparator", "done", time.monotonic())


class OracleAndGeneratedTheoremTests(unittest.TestCase):
    def test_oracle_and_generated_proof_disable_heartbeats(self):
        self.assertIn("set_option maxHeartbeats 0", judge._VALUE_META)
        self.assertIn("set_option maxHeartbeats 0", perf_eval._VALUE_META)
        source, theorem = judge._perf_theorem_source(7, "13", "nonce-a")
        self.assertIn("set_option maxHeartbeats 0", source)
        self.assertIn("set_option maxRecDepth 4000000", source)
        # EXPERIMENT (branch problem/sha256): kernel-checked addDecl encoding; both
        # source-level forms fail on one problem shape each. See _perf_theorem_source.
        self.assertIn("Lean.addDecl", source)
        self.assertIn("Lean.mkNatLit 7", source)
        self.assertIn("Lean.mkNatLit 13", source)
        self.assertIn(f"name := `{theorem}", source)
        self.assertNotIn("of_decide_eq_true", source)
        self.assertNotIn("by decide +kernel", source)
        self.assertTrue(theorem.startswith("LeanKernelChallengeJudge.Generated_"))
        self.assertNotIn("theorem perf_check", source)
        _, other = judge._perf_theorem_source(7, "13", "nonce-b")
        self.assertNotEqual(theorem, other)

    def test_value_result_is_independent_of_diagnostic_tail_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            digits = "1" + "0" * (judge.MAX_TOOL_OUTPUT_BYTES + 10)

            def fake_run(_cmd, cwd, _env, _timeout):
                (Path(cwd) / judge._VALUE_OUTPUT).write_text(digits)
                return 0, "[earlier tool output truncated]\n"

            with mock.patch.object(judge, "run", side_effect=fake_run):
                kind, value = judge._eval_impl_value(work, {}, 1, 10)

        self.assertEqual(kind, "ok")
        self.assertEqual(value, digits)

    def test_only_wall_clock_expiry_is_an_oracle_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            with mock.patch.object(
                    judge, "run", return_value=(1, "maximum number of heartbeats has been reached")):
                kind, detail = judge._eval_impl_value(work, {}, 10, 1)
        self.assertEqual(kind, "error")
        self.assertIn("heartbeats", detail)

    def test_perf_export_returns_the_exact_fully_qualified_target(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            artifact_lib = work / "lib"
            artifact_lib.mkdir()
            out_path = work / "point.export"

            def fake_run(cmd, cwd, env, timeout, stdout_path=None):
                if stdout_path is not None:
                    Path(stdout_path).write_bytes(b"export")
                return 0, ""

            with mock.patch.object(judge, "run", side_effect=fake_run) as run_mock:
                kind, detail, target = judge._perf_export(
                    work, {}, 7, "13", out_path, 9, artifact_lib, Path("lean"))

        self.assertEqual((kind, detail), ("ok", None))
        self.assertTrue(target.startswith("LeanKernelChallengeJudge.Generated_"))
        export_cmd = run_mock.call_args_list[-1].args[0]
        self.assertEqual(export_cmd[-1], target)

    def test_perf_export_rechecks_shared_deadline_between_build_and_export(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            artifact_lib = work / "lib"
            artifact_lib.mkdir()
            with mock.patch.object(judge, "run", return_value=(0, "")) as run_mock, \
                 mock.patch.object(judge, "_remaining_timeout", side_effect=[1.0, 0.0]):
                kind, detail, _ = judge._perf_export(
                    work, {}, 7, "13", work / "point.export", 9,
                    artifact_lib, Path("lean"), deadline=123.0)

        self.assertEqual((kind, detail), ("budget-exhausted", None))
        self.assertEqual(run_mock.call_count, 1)


def _timer_output(target=None, wall_ns=123456):
    payload = {
        "measurement_contract": judge.MEASUREMENT_CONTRACT,
        "boundary": judge._measurement_boundary(target),
        "target": target,
        "wall_ns": wall_ns,
        "phase": "complete",
    }
    return "Accepted.\nKERNEL_TIMING=" + json.dumps(payload, separators=(",", ":")) + "\n"


class LocalTimingProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        self.export = self.work / "proof.export"
        self.export.write_bytes(b"proof")

    def tearDown(self):
        self.tmp.cleanup()

    def test_wall_metric_uses_timer_internal_nanoseconds_and_target_argv(self):
        target = "LeanKernelChallengeJudge.Generated_abc.check"
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "run", return_value=(0, _timer_output(target))) as run_mock:
            rc, _, sample = judge._time_replay(
                self.export, self.work, {}, 9, target=target)

        self.assertEqual(rc, 0)
        self.assertEqual(sample["wall_ns"], 123456)
        self.assertEqual(sample["wall_s"], 0.000123456)
        cmd = run_mock.call_args.args[0]
        self.assertEqual(
            cmd, [str(judge.TIMER), "--target", target, str(self.export)])

    def test_perf_starts_disabled_and_counts_explicit_target_only(self):
        target = "LeanKernelChallengeJudge.Generated_perf.check"

        def fake_run(cmd, cwd, env, timeout):
            self.assertEqual(cwd, self.work)
            (self.work / "perf.txt").write_text(
                "321,,instructions,\n1.25,,task-clock,\n")
            return 0, _timer_output(target, wall_ns=777)

        with mock.patch.object(judge, "TIMING_METRIC", "perf_instructions"), \
             mock.patch.object(judge.shutil, "which", return_value="/usr/bin/perf"), \
             mock.patch.object(judge, "run", side_effect=fake_run) as run_mock:
            rc, _, sample = judge._time_replay(
                self.export, self.work, {"PATH": "/bin"}, 9, target=target)

        self.assertEqual(rc, 0)
        self.assertEqual(sample["instructions"], 321)
        self.assertEqual(sample["wall_ns"], 777)
        cmd = run_mock.call_args.args[0]
        self.assertEqual(cmd[:4], ["/usr/bin/perf", "stat", "-D", "-1"])
        self.assertEqual(
            cmd[-5:],
            ["--", str(judge.TIMER), "--target", target, str(self.export)])

    def test_timer_output_is_unique_versioned_and_target_bound(self):
        target = "Judge.Generated.check"
        with self.assertRaisesRegex(judge.InfraError, "0 measurement records"):
            judge._parse_timer_measurement("Accepted\n", target)
        duplicate = _timer_output(target) + _timer_output(target)
        with self.assertRaisesRegex(judge.InfraError, "2 measurement records"):
            judge._parse_timer_measurement(duplicate, target)
        with self.assertRaisesRegex(judge.InfraError, "target mismatch"):
            judge._parse_timer_measurement(_timer_output("Other.check"), target)
        old = json.loads(_timer_output(target).split("KERNEL_TIMING=", 1)[1])
        old["measurement_contract"] = "kernel-replay-v1"
        with self.assertRaisesRegex(judge.InfraError, "contract mismatch"):
            judge._parse_timer_measurement(
                "KERNEL_TIMING=" + json.dumps(old), target)

    def test_submillisecond_wall_median_never_rounds_to_zero(self):
        summary = judge._summarize_samples(
            [{"wall_ns": 400}, {"wall_ns": 600}, {"wall_ns": 500}],
            metric="wall_time")
        self.assertEqual(summary["median_wall_ns"], 500)
        self.assertEqual(summary["median_s"], 0.0000005)
        self.assertGreater(summary["median_s"], 0)

    def test_outer_timeout_records_preparation_scope(self):
        target = "Judge.Generated.check"
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "run", return_value=("timeout", "late")):
            rc, _, sample = judge._time_replay(
                self.export, self.work, {}, 9, target=target)
        self.assertEqual(rc, "timeout")
        self.assertEqual(sample["timeout_scope"], judge.PROCESS_TIMEOUT_SCOPE)
        self.assertEqual(sample["measurement_target"], target)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def _ok_response(executor="exec-a", version="v1", instructions=100, reps=1,
                 target=None):
    return {
        "status": "ok",
        "executor": executor,
        "version": version,
        "measurement_contract": judge.MEASUREMENT_CONTRACT,
        "boundary": judge._measurement_boundary(target),
        "target": target,
        "samples": [
            {"instructions": instructions, "task_clock_ms": 1.25, "wall_ns": 1250}
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

    def test_exhausted_phase_budget_prevents_remote_request(self):
        with mock.patch.object(judge, "TIMING_EXECUTOR_URLS", ["https://only"]), \
             mock.patch.object(judge.urllib.request, "urlopen") as urlopen:
            with self.assertRaises(judge.PerfBudgetExhausted):
                judge._time_remote(self.export, 1, budget_s=0)
        urlopen.assert_not_called()

    def test_transport_outage_at_phase_deadline_remains_retryable(self):
        outage = judge.urllib.error.URLError("offline")
        with mock.patch.object(judge, "TIMING_EXECUTOR_URLS", ["https://only"]), \
             mock.patch.object(judge, "_EXECUTOR_ATTEMPT_SLEEPS", [0, 0.05]), \
             mock.patch.object(judge.urllib.request, "urlopen", side_effect=outage):
            with self.assertRaises(judge.TimingRetry):
                judge._time_remote(self.export, 1, budget_s=0.01)

    def test_late_valid_kernel_failure_is_not_softened_to_budget_exhaustion(self):
        failed = {
            "status": "failed", "executor": "exec-a", "version": "v1",
            "measurement_contract": judge.MEASUREMENT_CONTRACT,
            "boundary": judge._measurement_boundary(None), "target": None,
            "output_tail": "kernel rejected export",
        }

        class SlowResponse(_Response):
            def read(self):
                time.sleep(0.03)
                return super().read()

        with mock.patch.object(judge, "TIMING_EXECUTOR_URLS", ["https://only"]), \
             mock.patch.object(judge, "_EXECUTOR_ATTEMPT_SLEEPS", [0]), \
             mock.patch.object(
                 judge.urllib.request, "urlopen", return_value=SlowResponse(failed)):
            result = judge._time_remote(
                self.export, 1, deadline=time.monotonic() + 0.01)
        self.assertEqual(result["status"], "failed")

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

    def test_target_and_v2_contract_are_bound_into_remote_request(self):
        target = "LeanKernelChallengeJudge.Generated_remote.check"
        captured = []

        def urlopen(req, timeout):
            captured.append((req, timeout))
            return _Response(_ok_response(target=target))

        with mock.patch.object(judge, "TIMING_EXECUTOR_URLS", ["https://exec"]), \
             mock.patch.object(judge, "_EXECUTOR_ATTEMPT_SLEEPS", [0]), \
             mock.patch.object(judge.urllib.request, "urlopen", side_effect=urlopen):
            result = judge._time_remote(self.export, 1, target=target)

        self.assertEqual(result["target"], target)
        req, _ = captured[0]
        parsed = judge.urllib.parse.urlparse(req.full_url)
        query = judge.urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        self.assertEqual(parsed.path, "/ktp/v2/time")
        self.assertEqual(query["measurement_contract"], [judge.MEASUREMENT_CONTRACT])
        self.assertEqual(query["boundary"], [judge.TARGET_REPLAY_BOUNDARY])
        self.assertEqual(query["target"], [target])
        headers = {key.lower(): value for key, value in req.header_items()}
        self.assertEqual(
            headers["x-measurement-contract"], judge.MEASUREMENT_CONTRACT)
        self.assertEqual(
            headers["x-measurement-boundary"], judge.TARGET_REPLAY_BOUNDARY)
        self.assertEqual(headers["x-measurement-target"], target)

    def test_old_or_wrong_target_response_fails_closed_as_retry(self):
        target = "LeanKernelChallengeJudge.Generated_expected.check"
        old = {
            "status": "ok", "executor": "old", "version": "v1",
            "samples": [{"instructions": 100}],
        }
        self.assertIn(
            "measurement contract",
            judge._remote_response_error(old, 1, target=target))

        wrong = _ok_response(target="LeanKernelChallengeJudge.Generated_other.check")
        with mock.patch.object(judge, "TIMING_EXECUTOR_URLS", ["https://only"]), \
             mock.patch.object(judge, "_EXECUTOR_ATTEMPT_SLEEPS", [0]), \
             mock.patch.object(
                 judge.urllib.request, "urlopen", return_value=_Response(wrong)):
            with self.assertRaises(judge.TimingRetry):
                judge._time_remote(self.export, 1, target=target)
        self.assertIsNone(judge._PINNED_EXECUTOR[0])


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
            "EVALUATION_RUN_ID": "run-x",
            "EVALUATION_IMAGE": "judge:test",
            "EVALUATION_MEMORY": "4g",
        }):
            env = judge.tool_env()

        self.assertNotIn("PERF_SEED", env)
        self.assertNotIn("TIMING_EXECUTOR_SECRET", env)
        self.assertNotIn("OFFICIAL_EVAL", env)
        self.assertNotIn("EVALUATION_COHORT", env)
        self.assertNotIn("EVALUATION_RUN_ID", env)
        self.assertNotIn("EVALUATION_IMAGE", env)
        self.assertNotIn("EVALUATION_MEMORY", env)
        self.assertNotIn("EVALUATION_EXECUTOR_ID", env)
        self.assertNotIn("EVALUATION_EXECUTOR_VERSION", env)
        self.assertEqual(env["LEAN_ABORT_ON_PANIC"], "1")
        self.assertIn("ELAN_HOME", env)

    def test_official_evaluation_cannot_run_with_sandbox_disabled(self):
        with mock.patch.object(judge, "OFFICIAL_EVAL", True), \
             mock.patch.object(judge, "TIMING_METRIC", "perf_instructions"), \
             mock.patch.object(judge, "SANDBOX_MODE", "none"), \
             mock.patch.object(judge, "PERF_SEED", "secret"), \
             mock.patch.object(judge, "_PERF_SEED_SOURCE", ["stdin"]), \
             mock.patch.object(judge, "EVALUATION_COHORT", "round-x"), \
             mock.patch.object(judge, "EVALUATION_RUN_ID", "run-x"), \
             mock.patch.object(judge, "EVALUATION_EXECUTOR_ID", "pmu-host"), \
             mock.patch.object(judge, "EVALUATION_EXECUTOR_VERSION", "pmu-v1"), \
             mock.patch.object(judge, "EVALUATION_RESOURCE_POLICY", {
                 "image": "sha256:" + "a" * 64,
             }):
            with self.assertRaisesRegex(judge.InfraError, "sandbox.mode=container"):
                judge.judge(Path("/tmp/unused-job"), "fib", "/tmp/unused", 1, "test")

    def test_official_evaluation_cannot_use_development_wall_time(self):
        with mock.patch.object(judge, "OFFICIAL_EVAL", True), \
             mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "SANDBOX_MODE", "container"), \
             mock.patch.object(judge, "PERF_SEED", "secret"), \
             mock.patch.object(judge, "_PERF_SEED_SOURCE", ["stdin"]), \
             mock.patch.object(judge, "EVALUATION_COHORT", "round-x"), \
             mock.patch.object(judge, "EVALUATION_RUN_ID", "run-x"):
            with self.assertRaisesRegex(judge.InfraError, "TIMING_METRIC=perf_instructions"):
                judge.judge(Path("/tmp/unused-job"), "fib", "/tmp/unused", 1, "test")

    def test_cohort_id_commits_to_schedule(self):
        cfg = {"perf": {"min": 1, "max": 10, "count": 2}}
        result = {"stages": {}}
        with mock.patch.object(judge, "EVALUATION_COHORT", "round-x"), \
             mock.patch.object(judge, "_problem_bundle_digest", return_value="a" * 64):
            first = judge._evaluation_cohort("demo", cfg, [1, 10], 3, result)
            same = judge._evaluation_cohort("demo", cfg, [1, 10], 3, result)
            changed = judge._evaluation_cohort("demo", cfg, [1, 9], 3, result)
            with mock.patch.object(
                    judge, "TARGET_REPLAY_BOUNDARY",
                    "target-declaration-replay-v2"):
                changed_contract = judge._evaluation_cohort(
                    "demo", cfg, [1, 10], 3, result)

        self.assertEqual(first["id"], same["id"])
        self.assertNotEqual(first["id"], changed["id"])
        self.assertNotEqual(first["id"], changed_contract["id"])
        self.assertEqual(first["round"], "round-x")
        self.assertEqual(first["id"], first["policy_sha256"][:24])

    def test_cohort_id_commits_to_phase_budget_audit_budget_and_problem_bundle(self):
        cfg = {"perf": {"min": 1, "max": 10, "count": 2}}
        result = {"stages": {}}
        common = [
            mock.patch.object(judge, "EVALUATION_COHORT", "round-x"),
            mock.patch.object(judge, "_problem_bundle_digest", return_value="a" * 64),
        ]
        with common[0], common[1]:
            baseline = judge._evaluation_cohort("demo", cfg, [1, 10], 3, result)
        with mock.patch.object(judge, "EVALUATION_COHORT", "round-x"), \
             mock.patch.object(judge, "_problem_bundle_digest", return_value="a" * 64), \
             mock.patch.object(judge, "PERF_PHASE_BUDGET", judge.PERF_PHASE_BUDGET + 1):
            phase_changed = judge._evaluation_cohort("demo", cfg, [1, 10], 3, result)
        with mock.patch.object(judge, "EVALUATION_COHORT", "round-x"), \
             mock.patch.object(judge, "_problem_bundle_digest", return_value="a" * 64), \
             mock.patch.object(judge, "AUDIT_TIMEOUT", judge.AUDIT_TIMEOUT + 1):
            audit_changed = judge._evaluation_cohort("demo", cfg, [1, 10], 3, result)
        with mock.patch.object(judge, "EVALUATION_COHORT", "round-x"), \
             mock.patch.object(judge, "_problem_bundle_digest", return_value="b" * 64):
            problem_changed = judge._evaluation_cohort("demo", cfg, [1, 10], 3, result)

        self.assertNotEqual(baseline["id"], phase_changed["id"])
        self.assertNotEqual(baseline["id"], audit_changed["id"])
        self.assertNotEqual(baseline["id"], problem_changed["id"])

    def test_measurement_contract_record_names_both_boundaries_and_protocols(self):
        contract = judge._measurement_contract_record()
        timing_policy = judge._CFG["timing"]
        self.assertEqual(contract["id"], judge.MEASUREMENT_CONTRACT)
        self.assertEqual(
            contract["correctness_boundary"], judge.FULL_REPLAY_BOUNDARY)
        self.assertEqual(
            contract["performance_boundary"], judge.TARGET_REPLAY_BOUNDARY)
        self.assertEqual(
            contract["target_proof_encoding"], judge.TARGET_PROOF_ENCODING)
        self.assertEqual(contract["local_protocol"], "local-v2")
        self.assertEqual(contract["remote_protocol"], "KTP/2")
        self.assertEqual(timing_policy["measurement_contract"], contract["id"])
        self.assertEqual(
            timing_policy["correctness_boundary"], contract["correctness_boundary"])
        self.assertEqual(
            timing_policy["performance_boundary"], contract["performance_boundary"])
        self.assertEqual(
            timing_policy["target_proof_encoding"], contract["target_proof_encoding"])
        self.assertEqual(timing_policy["remote_protocol"], contract["remote_protocol"])
        timer_source = (ROOT / "judge" / "timer-kernel" / "Main.lean").read_text()
        self.assertIn(f'"{judge.MEASUREMENT_CONTRACT}"', timer_source)
        self.assertIn(f'"{judge.FULL_REPLAY_BOUNDARY}"', timer_source)
        self.assertIn(f'"{judge.TARGET_REPLAY_BOUNDARY}"', timer_source)
        self.assertIn("target theorem has an extracted proof helper", timer_source)
        timer_lakefile = (ROOT / "judge" / "timer-kernel" / "lakefile.lean").read_text()
        self.assertIn(judge._CFG["toolchain"]["lean4export_rev"], timer_lakefile)
        self.assertIn(judge._CFG["toolchain"]["lean4checker_rev"], timer_lakefile)


if __name__ == "__main__":
    unittest.main()
