"""Pure-Python regression tests for the canonical scoring contract."""
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("challenge_score", ROOT / "scripts" / "score.py")
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


def verdict(name, costs, *, metric="perf_instructions", correctness=10,
            inputs=(10, 20, 40), problem="fib", protocol=score.LOCAL_PROTOCOL,
            executor="local", executor_kind=None, round_id="test-round"):
    field = score.METRICS[metric]["field"]
    scaling = []
    for slot, (n, cost) in enumerate(zip(inputs, costs)):
        measurement = {
            "measurement_contract": score.MEASUREMENT_CONTRACT,
            "measurement_boundary": score.PERFORMANCE_BOUNDARY,
            "measurement_target": f"Judge.Generated_{slot}.check",
        }
        if cost is None:
            scaling.append({
                "slot": slot, "n": n, "result": "timeout", **measurement,
            })
        else:
            scaling.append({
                "slot": slot, "n": n, "result": "ok", field: cost, **measurement,
            })
    result = {
        "problem": problem,
        "submission": name,
        "status": "accepted",
        "metric": metric,
        "evaluation_mode": "development",
        "timing_protocol": protocol,
        "measurement_contract": dict(score.CURRENT_MEASUREMENT_RECORD),
        "stages": {"perf_inputs": list(inputs)},
        "correctness_timing": {
            "result": "ok", "reps": 3,
            "metric": metric,
            "checker": "test-checker",
            "measurement_contract": score.MEASUREMENT_CONTRACT,
            "measurement_boundary": score.CORRECTNESS_BOUNDARY,
            "measurement_target": None,
            field: correctness,
        },
        "timing": {
            "metric": metric, "reps": 3,
            "checker": "test-checker",
            "measurement_contract": score.MEASUREMENT_CONTRACT,
            "measurement_boundary": score.PERFORMANCE_BOUNDARY,
            "scaling": scaling,
        },
    }
    _seal_cohort(
        result, round_id=round_id, executor=executor, executor_kind=executor_kind)
    return result


def _seal_cohort(result, *, round_id="test-round", executor="local", executor_kind=None):
    executor_record = {
        "kind": executor_kind or ("local" if executor == "local" else "remote"),
        "executor": executor,
        "version": "test-v1",
    }
    policy = {
        "schema": "evaluation-policy-v1",
        "round": round_id,
        "problem": result["problem"],
        "problem_bundle_sha256": "0" * 64,
        "evaluator_bundle_sha256": "1" * 64,
        "evaluation_mode": result["evaluation_mode"],
        "perf": {"min": min(result["stages"]["perf_inputs"]),
                 "max": max(result["stages"]["perf_inputs"])},
        "perf_defaults": {"count": len(result["stages"]["perf_inputs"]),
                          "spacing": "linear", "jitter": 0.15},
        "inputs": list(result["stages"]["perf_inputs"]),
        "metric": result["metric"],
        "reps": result["timing"]["reps"],
        "budgets": {
            "comparator_timeout_seconds": 100,
            "audit_timeout_seconds": 10,
            "timing_timeout_seconds": 10,
            "perf_phase_budget_seconds": 100,
        },
        "resource_policy": {
            "image": "local-unspecified", "memory": "local-unspecified",
            "cpus": "local-unspecified", "pids_limit": "local-unspecified",
            "sandbox_mode": "none",
        },
        "toolchain": {
            "lean": "leanprover/lean4:test", "comparator_rev": "2" * 40,
            "lean4export_rev": "3" * 40, "lean4checker_rev": "4" * 40,
        },
        "checker": "test-checker",
        "timing_protocol": result["timing_protocol"],
        "measurement_contract": dict(score.CURRENT_MEASUREMENT_RECORD),
        "executor": executor_record,
    }
    encoded = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    result["evaluation_cohort"] = {
        "id": digest[:24],
        "round": round_id,
        "executor": executor_record,
        "policy_sha256": digest,
        "policy": policy,
    }


class ScoringTests(unittest.TestCase):
    def test_low_end_padding_cannot_improve_rank(self):
        flat = verdict("flat", [100, 100, 100])
        padded = verdict("padded", [10000, 1000, 100])

        rows = score._rows_for("fib", [padded, flat], "perf_instructions")
        by_name = {row["sub"]: row for row in rows}

        # The old α ranking preferred this deliberately padded curve.
        self.assertLess(by_name["padded"]["alpha"], by_name["flat"]["alpha"])
        # The canonical monotone aggregate cannot: padding only adds work.
        self.assertEqual(rows[0]["sub"], "flat")
        self.assertGreater(by_name["padded"]["total_work"], by_name["flat"]["total_work"])

    def test_correctness_replay_is_charged(self):
        table = verdict("table", [1, 1, 1], correctness=1000)
        algorithm = verdict("algorithm", [100, 100, 100], correctness=10)

        rows = score._rows_for("fib", [table, algorithm], "perf_instructions")

        self.assertEqual(rows[0]["sub"], "algorithm")
        self.assertEqual(rows[0]["total_work"], 310)
        self.assertEqual(rows[1]["total_work"], 1003)

    def test_completed_slots_are_primary(self):
        complete = verdict("complete", [1000, 1000, 1000], correctness=1000)
        cheap_prefix = verdict("cheap-prefix", [1, 1, None], correctness=1)

        rows = score._rows_for("fib", [cheap_prefix, complete], "perf_instructions")

        self.assertEqual(rows[0]["sub"], "complete")
        self.assertEqual(rows[0]["completed_slots"], 3)
        self.assertEqual(rows[1]["completed_slots"], 2)

    def test_equal_coverage_prefers_harder_success_slots_before_raw_work(self):
        low_only = verdict("low-only", [1, 1, None], correctness=1)
        high_only = verdict("high-only", [None, 100, 100], correctness=100)

        rows = score._rows_for("fib", [low_only, high_only], "perf_instructions")

        # Raw sums at different n are not comparable; the higher-slot profile wins first.
        self.assertEqual(rows[0]["sub"], "high-only")
        self.assertEqual(rows[0]["slot_profile"], (0, 1, 1))
        self.assertGreater(rows[0]["total_work"], rows[1]["total_work"])

    def test_metrics_are_strictly_separate_groups(self):
        instructions = verdict("instructions", [100, 200, 300])
        seconds = verdict("seconds", [0.1, 0.2, 0.3], metric="wall_time",
                          correctness=0.05)

        groups = score._groups([instructions, seconds])

        instruction_group = ("fib", "perf_instructions",
                             instructions["evaluation_cohort"]["id"])
        seconds_group = ("fib", "wall_time", seconds["evaluation_cohort"]["id"])
        self.assertEqual(set(groups), {instruction_group, seconds_group})
        self.assertEqual(
            [r["sub"] for r in score._rows_for(
                "fib",
                groups[instruction_group],
                "perf_instructions",
            )],
            ["instructions"],
        )
        self.assertEqual(
            [r["sub"] for r in score._rows_for(
                "fib", groups[seconds_group], "wall_time"
            )],
            ["seconds"],
        )

    def test_legacy_verdict_without_correctness_timing_is_unscored(self):
        legacy = verdict("legacy", [100, 200, 300])
        del legacy["correctness_timing"]

        row = score._score_row(legacy, "perf_instructions")

        self.assertFalse(row["scoreable"])
        self.assertIn("missing correctness_timing", row["reason"])

    def test_nested_metric_mismatch_is_unscored(self):
        mixed = verdict("mixed", [100, 200, 300])
        mixed["correctness_timing"]["metric"] = "wall_time"

        row = score._score_row(mixed, "perf_instructions")

        self.assertFalse(row["scoreable"])
        self.assertIn("declared metric", row["reason"])

    def test_evaluation_cohorts_are_never_mixed(self):
        first = verdict("first", [100, 200, 300])
        second = verdict("second", [100, 200, 300], round_id="other-round")

        groups = score._groups([first, second])

        self.assertEqual(len(groups), 2)
        self.assertIn(
            ("fib", "perf_instructions", first["evaluation_cohort"]["id"]), groups)
        self.assertIn(
            ("fib", "perf_instructions", second["evaluation_cohort"]["id"]), groups)

    def test_missing_cohort_is_unscored(self):
        legacy = verdict("legacy-cohort", [100, 200, 300])
        del legacy["evaluation_cohort"]

        row = score._score_row(legacy, "perf_instructions")

        self.assertFalse(row["scoreable"])
        self.assertIn("evaluation_cohort", row["reason"])

    def test_legacy_or_mismatched_measurement_versions_are_unscored(self):
        mutations = {
            "missing top-level contract": (
                lambda v: v.pop("measurement_contract"),
                "measurement contract",
            ),
            "extra top-level contract field": (
                lambda v: v["measurement_contract"].__setitem__("legacy", True),
                "measurement contract",
            ),
            "wrong target proof encoding": (
                lambda v: v["measurement_contract"].__setitem__(
                    "target_proof_encoding", "extracted-wrapper-v0"),
                "measurement contract",
            ),
            "missing protocol": (
                lambda v: v.pop("timing_protocol"),
                "timing protocol",
            ),
            "KTP/1 protocol": (
                lambda v: v.__setitem__("timing_protocol", "KTP/1"),
                "timing protocol",
            ),
            "wrong correctness contract": (
                lambda v: v["correctness_timing"].__setitem__(
                    "measurement_contract", "kernel-replay-v1"),
                "correctness measurement contract",
            ),
            "wrong correctness boundary": (
                lambda v: v["correctness_timing"].__setitem__(
                    "measurement_boundary", "whole-process-v1"),
                "correctness measurement boundary",
            ),
            "non-null correctness target": (
                lambda v: v["correctness_timing"].__setitem__(
                    "measurement_target", "some.theorem"),
                "target must be null",
            ),
            "wrong performance boundary": (
                lambda v: v["timing"].__setitem__(
                    "measurement_boundary", "whole-process-v1"),
                "performance measurement boundary",
            ),
            "wrong performance contract": (
                lambda v: v["timing"].__setitem__(
                    "measurement_contract", "kernel-replay-v1"),
                "performance measurement contract",
            ),
            "missing successful-slot target": (
                lambda v: v["timing"]["scaling"][0].pop(
                    "measurement_target"),
                "lacks a measurement target",
            ),
            "wrong successful-slot boundary": (
                lambda v: v["timing"]["scaling"][0].__setitem__(
                    "measurement_boundary", "whole-process-v1"),
                "measured slot 0",
            ),
        }
        for label, (mutate, reason) in mutations.items():
            with self.subTest(label=label):
                legacy = verdict("legacy", [100, 200, 300])
                mutate(legacy)
                row = score._score_row(legacy, "perf_instructions")
                self.assertFalse(row["scoreable"])
                self.assertIn(reason, row["reason"])

    def test_protocol_must_match_local_or_remote_executor(self):
        local_wrong = verdict(
            "local-as-remote", [100, 200, 300], protocol=score.REMOTE_PROTOCOL)
        remote_wrong = verdict(
            "remote-as-local", [100, 200, 300],
            protocol=score.LOCAL_PROTOCOL, executor="exec-a")
        remote_current = verdict(
            "remote-current", [100, 200, 300],
            protocol=score.REMOTE_PROTOCOL, executor="exec-a")
        pinned_local = verdict(
            "pinned-local", [100, 200, 300], protocol=score.LOCAL_PROTOCOL,
            executor="local-pmu-abcd", executor_kind="local")

        self.assertFalse(
            score._score_row(local_wrong, "perf_instructions")["scoreable"])
        self.assertFalse(
            score._score_row(remote_wrong, "perf_instructions")["scoreable"])
        self.assertTrue(
            score._score_row(remote_current, "perf_instructions")["scoreable"])
        self.assertTrue(
            score._score_row(pinned_local, "perf_instructions")["scoreable"])

    def test_same_cohort_id_does_not_make_legacy_verdict_scoreable(self):
        current = verdict("current", [100, 200, 300])
        legacy = verdict("legacy", [1, 1, 1])
        legacy["evaluation_cohort"]["id"] = current["evaluation_cohort"]["id"]
        del legacy["measurement_contract"]

        rows = score._rows_for(
            "fib", [legacy, current], "perf_instructions")
        by_name = {row["sub"]: row for row in rows}

        self.assertTrue(by_name["current"]["scoreable"])
        self.assertFalse(by_name["legacy"]["scoreable"])

    def test_schedule_requires_explicit_matching_slots(self):
        malformed = verdict("malformed", [100, 200, 300])
        malformed["timing"]["scaling"][1]["slot"] = 0

        row = score._score_row(malformed, "perf_instructions")

        self.assertFalse(row["scoreable"])
        self.assertIn("unique integer slot", row["reason"])

    def test_non_prefix_successes_count_toward_coverage_and_work(self):
        resumed = verdict("resumed", [100, None, 300], correctness=10)

        row = score._score_row(resumed, "perf_instructions")

        self.assertTrue(row["scoreable"])
        self.assertEqual(row["completed_slots"], 2)
        self.assertEqual(row["coverage"], 2 / 3)
        self.assertEqual(row["curve_work"], 400)
        self.assertEqual(row["total_work"], 410)

    def test_zero_input_is_scored_but_excluded_from_log_fit(self):
        zero_first = verdict("zero-first", [5, 20, 40], correctness=10,
                             inputs=(0, 10, 20))

        row = score._score_row(zero_first, "perf_instructions")

        self.assertTrue(row["scoreable"])
        self.assertEqual(row["completed_slots"], 3)
        self.assertEqual(row["curve_work"], 65)
        self.assertIsNotNone(row["alpha"])

    def test_exact_performance_ties_share_rank_but_sort_by_name(self):
        zeta = verdict("zeta", [100, 200, 300])
        alpha = verdict("alpha", [100, 200, 300])
        slower = verdict("slower", [100, 200, 301])

        rows = score._rows_for("fib", [zeta, slower, alpha], "perf_instructions")

        self.assertEqual([row["sub"] for row in rows], ["alpha", "zeta", "slower"])
        self.assertEqual(score._competition_ranks(rows), [1, 1, 3])

    def test_unknown_slot_result_and_fractional_instructions_are_unscored(self):
        unknown = verdict("unknown", [100, 200, 300])
        unknown["timing"]["scaling"][1]["result"] = "banana"
        fractional = verdict("fractional", [100, 200, 300])
        fractional["timing"]["scaling"][0]["median_instructions"] = 0.25

        unknown_row = score._score_row(unknown, "perf_instructions")
        fractional_row = score._score_row(fractional, "perf_instructions")

        self.assertFalse(unknown_row["scoreable"])
        self.assertIn("unknown result", unknown_row["reason"])
        self.assertFalse(fractional_row["scoreable"])
        self.assertIn("positive median_instructions", fractional_row["reason"])

        unhashable = verdict("unhashable-result", [100, 200, 300])
        unhashable["timing"]["scaling"][0]["result"] = []
        unhashable_row = score._score_row(unhashable, "perf_instructions")
        self.assertFalse(unhashable_row["scoreable"])
        self.assertIn("unknown result", unhashable_row["reason"])

    def test_malformed_metric_and_unbounded_integer_do_not_crash(self):
        malformed_metric = verdict("bad-metric", [100, 200, 300])
        malformed_metric["metric"] = []
        huge = verdict("huge", [100, 200, 300])
        huge["correctness_timing"]["median_instructions"] = 10 ** 309

        self.assertEqual(score._groups([malformed_metric]), {})
        huge_row = score._score_row(huge, "perf_instructions")
        self.assertFalse(huge_row["scoreable"])
        self.assertIn("positive median_instructions", huge_row["reason"])

    def test_cohort_policy_must_bind_schedule_executor_and_hash(self):
        wrong_schedule = verdict("wrong-schedule", [100, 200, 300])
        wrong_schedule["stages"]["perf_inputs"] = [11, 22, 44]
        wrong_executor = verdict("wrong-executor", [100, 200, 300])
        wrong_executor["evaluation_cohort"]["executor"]["version"] = "other"
        wrong_hash = verdict("wrong-hash", [100, 200, 300])
        wrong_hash["evaluation_cohort"]["policy_sha256"] = "f" * 64

        for item in (wrong_schedule, wrong_executor, wrong_hash):
            with self.subTest(submission=item["submission"]):
                self.assertFalse(
                    score._score_row(item, "perf_instructions")["scoreable"])

    def test_current_policy_schema_is_complete_and_checker_bound(self):
        for missing in (
                "evaluator_bundle_sha256", "perf", "perf_defaults", "budgets",
                "resource_policy", "toolchain", "checker"):
            with self.subTest(missing=missing):
                item = verdict(f"missing-{missing}", [100, 200, 300])
                policy = item["evaluation_cohort"]["policy"]
                policy.pop(missing)
                digest = hashlib.sha256(json.dumps(
                    policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                item["evaluation_cohort"]["policy_sha256"] = digest
                item["evaluation_cohort"]["id"] = digest[:24]
                self.assertFalse(
                    score._score_row(item, "perf_instructions")["scoreable"])

        mismatch = verdict("checker-mismatch", [100, 200, 300])
        mismatch["timing"]["checker"] = "different-checker"
        row = score._score_row(mismatch, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("checker", row["reason"])

        for field_path in ("perf.jitter", "perf_defaults.jitter", "metric"):
            with self.subTest(malformed=field_path):
                item = verdict(f"malformed-{field_path}", [100, 200, 300])
                policy = item["evaluation_cohort"]["policy"]
                if field_path == "metric":
                    policy["metric"] = []
                else:
                    parent, field = field_path.split(".")
                    policy[parent][field] = 10 ** 309
                digest = hashlib.sha256(json.dumps(
                    policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                item["evaluation_cohort"]["policy_sha256"] = digest
                item["evaluation_cohort"]["id"] = digest[:24]
                self.assertFalse(
                    score._score_row(item, "perf_instructions")["scoreable"])

        for label, mutate in (
                ("float-policy-inputs", lambda v: v["evaluation_cohort"]["policy"].__setitem__(
                    "inputs", [10.0, 20.0, 40.0])),
                ("out-of-range-policy", lambda v: v["evaluation_cohort"]["policy"]["perf"].update(
                    {"min": 100, "max": 200}))):
            with self.subTest(malformed=label):
                item = verdict(label, [100, 200, 300])
                mutate(item)
                policy = item["evaluation_cohort"]["policy"]
                digest = hashlib.sha256(json.dumps(
                    policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                item["evaluation_cohort"]["policy_sha256"] = digest
                item["evaluation_cohort"]["id"] = digest[:24]
                self.assertFalse(
                    score._score_row(item, "perf_instructions")["scoreable"])

        float_sample = verdict("float-sample", [100, 200, 300])
        float_sample["timing"]["scaling"][0]["n"] = 10.0
        self.assertFalse(score._score_row(
            float_sample, "perf_instructions")["scoreable"])

        float_reps = verdict("float-reps", [100, 200, 300])
        float_reps["correctness_timing"]["reps"] = 3.0
        float_reps["timing"]["reps"] = 3.0
        self.assertFalse(score._score_row(
            float_reps, "perf_instructions")["scoreable"])

        zero_jitter = verdict("zero-jitter", [100, 200, 300])
        policy = zero_jitter["evaluation_cohort"]["policy"]
        policy["perf_defaults"]["jitter"] = 0
        digest = hashlib.sha256(json.dumps(
            policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        zero_jitter["evaluation_cohort"]["policy_sha256"] = digest
        zero_jitter["evaluation_cohort"]["id"] = digest[:24]
        self.assertFalse(score._score_row(
            zero_jitter, "perf_instructions")["scoreable"])

    def test_report_survives_aggregate_integer_overflow(self):
        item = verdict("aggregate-overflow", [10 ** 308] * 3, correctness=10 ** 308)
        old_results = score.RESULTS
        with tempfile.TemporaryDirectory() as temp:
            try:
                score.RESULTS = temp
                problem_dir = pathlib.Path(temp) / "fib"
                problem_dir.mkdir()
                (problem_dir / "overflow.json").write_text(json.dumps(item))
                score.main()
                report = (pathlib.Path(temp) / "scoring.md").read_text()
            finally:
                score.RESULTS = old_results
        self.assertIn("aggregate-overflow", report)
        self.assertIn("total measured work is not a finite positive cost", report)


if __name__ == "__main__":
    unittest.main()
