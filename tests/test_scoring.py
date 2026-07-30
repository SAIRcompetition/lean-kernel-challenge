"""Pure-Python regression tests for the canonical scoring contract."""
import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("challenge_score", ROOT / "scripts" / "score.py")
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


def verdict(name, costs, *, metric="perf_instructions", correctness=10,
            inputs=(10, 20, 40), problem="fib", protocol=score.LOCAL_PROTOCOL,
            executor="local"):
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
    return {
        "problem": problem,
        "submission": name,
        "status": "accepted",
        "metric": metric,
        "timing_protocol": protocol,
        "measurement_contract": dict(score.CURRENT_MEASUREMENT_RECORD),
        "evaluation_cohort": {
            "id": f"cohort-{metric}",
            "round": "test-round",
            "executor": {"executor": executor, "version": "test-v1"},
        },
        "stages": {"perf_inputs": list(inputs)},
        "correctness_timing": {
            "result": "ok",
            "metric": metric,
            "measurement_contract": score.MEASUREMENT_CONTRACT,
            "measurement_boundary": score.CORRECTNESS_BOUNDARY,
            "measurement_target": None,
            field: correctness,
        },
        "timing": {
            "metric": metric,
            "measurement_contract": score.MEASUREMENT_CONTRACT,
            "measurement_boundary": score.PERFORMANCE_BOUNDARY,
            "scaling": scaling,
        },
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

        self.assertEqual(set(groups), {
            ("fib", "perf_instructions", "cohort-perf_instructions"),
            ("fib", "wall_time", "cohort-wall_time"),
        })
        self.assertEqual(
            [r["sub"] for r in score._rows_for(
                "fib",
                groups[("fib", "perf_instructions", "cohort-perf_instructions")],
                "perf_instructions",
            )],
            ["instructions"],
        )
        self.assertEqual(
            [r["sub"] for r in score._rows_for(
                "fib", groups[("fib", "wall_time", "cohort-wall_time")], "wall_time"
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
        second = verdict("second", [100, 200, 300])
        second["evaluation_cohort"] = {
            "id": "other-cohort",
            "round": "other-round",
            "executor": {"executor": "local", "version": "test-v1"},
        }

        groups = score._groups([first, second])

        self.assertEqual(len(groups), 2)
        self.assertIn(("fib", "perf_instructions", "cohort-perf_instructions"), groups)
        self.assertIn(("fib", "perf_instructions", "other-cohort"), groups)

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

        self.assertFalse(
            score._score_row(local_wrong, "perf_instructions")["scoreable"])
        self.assertFalse(
            score._score_row(remote_wrong, "perf_instructions")["scoreable"])
        self.assertTrue(
            score._score_row(remote_current, "perf_instructions")["scoreable"])

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


if __name__ == "__main__":
    unittest.main()
