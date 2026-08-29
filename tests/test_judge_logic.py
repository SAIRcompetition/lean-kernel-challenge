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

    def test_positive_endpoints_jitter_inward_instead_of_clamping(self):
        lo = 2 ** 18
        hi = 2 ** 63
        cfg = {
            "perf": {
                "min": lo, "max": hi, "count": 10,
                "spacing": "geometric", "jitter": 0.15,
            }
        }
        schedules = []
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            for seed in ("rotation-a", "rotation-b", "rotation-c"):
                with mock.patch.object(judge, "PERF_SEED", seed):
                    points = judge.perf_inputs(cfg, "demo")
                self.assertGreater(points[0], lo)
                self.assertLess(points[-1], hi)
                self.assertTrue(all(a < b for a, b in zip(points, points[1:])))
                schedules.append(points)
        self.assertEqual(len({tuple(points) for points in schedules}), len(schedules))

    def test_zero_lower_endpoint_stays_fixed_under_multiplicative_jitter(self):
        cfg = {
            "perf": {
                "min": 0, "max": 1000, "count": 5,
                "spacing": "geometric", "jitter": 0.5,
            }
        }
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", "operator-secret"), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            points = judge.perf_inputs(cfg, "zero")

        self.assertEqual(points[0], 0)
        self.assertLess(points[-1], 1000)
        self.assertTrue(all(a < b for a, b in zip(points, points[1:])))

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


def _grouped_cfg(*groups):
    profile = (
        "hardest_group_then_count"
        if groups and all(
            group.get("sampling", {}).get("kind") in ("packed", "uniform_int")
            for group in groups
        )
        else "hardest_group_then_slot"
    )
    return {
        "evaluation": {
            "schema": "grouped-evaluation-v1",
            "axis": {"label": "encoded input", "unit": "case", "input_encoding": "packed-v1"},
            "groups": list(groups),
            "ranking": {
                "contract": "group-points-v1", "work": "total",
                "proof": "include", "profile": profile,
            },
        }
    }


def _packed_group(group, order, scale, count=2, limits=None):
    return {
        "id": group,
        "label": group,
        "order": order,
        "sampling": {
            "kind": "packed", "scale": scale, "seed_bits": 32, "count": count,
        },
        "award": {
            "mode": "milestones",
            "table": [
                {"passed": 0, "points": 0},
                {"passed": count, "points": 10 * (order + 1)},
            ],
        },
        "limits": limits or {
            "kernel_instructions": 1000000, "timeout_seconds": 17,
        },
    }


class GroupedPerformancePlanTests(unittest.TestCase):
    def test_official_repetition_count_is_fixed(self):
        with mock.patch.object(judge, "OFFICIAL_EVAL", True), \
             mock.patch.object(judge, "DEFAULT_REPS", 3):
            judge._validate_repetition_count(3)
            with self.assertRaisesRegex(judge.InfraError, "exactly 3"):
                judge._validate_repetition_count(1)
        with mock.patch.object(judge, "OFFICIAL_EVAL", False):
            judge._validate_repetition_count(1)

    def test_group_timeout_applies_only_to_target_replay(self):
        plan = [{
            "slot": 0, "group": "L1", "case": 0, "n": 10,
            "limits": {
                "kernel_instructions": 1000000,
                "timeout_seconds": 17,
            },
        }]
        with mock.patch.object(judge, "TIMING_TIMEOUT", 1800), \
             mock.patch.object(judge, "AUDIT_TIMEOUT", 300):
            caps = judge._performance_timeout_caps(plan, 10)

        self.assertEqual(caps, {
            "value_eval": 1800,
            "build_export": 1800,
            "axiom_audit": 300,
            "target_replay": 17,
        })

    def test_legacy_slot_keeps_existing_infrastructure_timeouts(self):
        with mock.patch.object(judge, "TIMING_TIMEOUT", 1800), \
             mock.patch.object(judge, "AUDIT_TIMEOUT", 300):
            caps = judge._performance_timeout_caps(None, 10)

        self.assertEqual(caps, {
            "value_eval": 1800,
            "build_export": 1800,
            "axiom_audit": 300,
            "target_replay": 1800,
        })

    def test_complete_grouped_contract_is_validated_before_judging(self):
        cfg = _grouped_cfg(_packed_group("L1", 0, 3))
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", ""), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            plan = judge._validated_performance_plan(cfg, "demo")
            self.assertEqual(len(plan), 2)

            bad_award = json.loads(json.dumps(cfg))
            bad_award["evaluation"]["groups"][0]["award"] = {
                "mode": "nonsense", "table": [],
            }
            with self.assertRaisesRegex(judge.InfraError, "invalid award"):
                judge._validated_performance_plan(bad_award, "demo")

            bad_ranking = json.loads(json.dumps(cfg))
            bad_ranking["evaluation"]["ranking"]["contract"] = "broken"
            with self.assertRaisesRegex(judge.InfraError, "ranking contract"):
                judge._validated_performance_plan(bad_ranking, "demo")

            bad_axis = json.loads(json.dumps(cfg))
            bad_axis["evaluation"]["axis"] = {"label": "missing fields"}
            with self.assertRaisesRegex(judge.InfraError, "difficulty axis"):
                judge._validated_performance_plan(bad_axis, "demo")

    def test_official_stage1_rejects_legacy_only_problem_policy(self):
        with mock.patch.object(judge, "TIMING_METRIC", "perf_instructions"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", True), \
             mock.patch.object(judge, "PERF_SEED", "cohort-secret"), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            with self.assertRaisesRegex(judge.InfraError, "requires a grouped policy"):
                judge._validated_performance_plan(
                    {"perf": {"min": 1, "max": 10}}, "conv")

        with mock.patch.object(judge, "OFFICIAL_EVAL", False):
            self.assertIsNone(judge._validated_performance_plan(
                {"perf": {"min": 1, "max": 10}}, "conv"))

    def test_grouped_official_plan_api_requires_seed(self):
        cfg = _grouped_cfg(_packed_group("L1", 0, 3))
        with mock.patch.object(judge, "TIMING_METRIC", "perf_instructions"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", ""), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            with self.assertRaisesRegex(judge.InfraError, "PERF_SEED"):
                judge.performance_plan(cfg, "demo")

    def test_packed_plan_is_shared_reproducible_and_seed_rotated(self):
        cfg = _grouped_cfg(
            _packed_group("L1", 0, 7),
            _packed_group("L2", 1, 19, limits={
                "kernel_instructions": 2000000, "timeout_seconds": 23,
            }),
        )
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", "cohort-secret"), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            first = judge.performance_plan(cfg, "demo")
            same = judge.performance_plan(cfg, "demo")
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", "next-secret"), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            rotated = judge.performance_plan(cfg, "demo")

        self.assertEqual(first, same)
        self.assertNotEqual([row["n"] for row in first], [row["n"] for row in rotated])
        self.assertEqual([row["slot"] for row in first], [0, 1, 2, 3])
        self.assertEqual([row["group"] for row in first], ["L1", "L1", "L2", "L2"])
        self.assertEqual([row["case"] for row in first], [0, 1, 0, 1])
        self.assertEqual([row["scale"] for row in first], [7, 7, 19, 19])
        self.assertEqual([row["n"] >> 32 for row in first], [7, 7, 19, 19])
        self.assertEqual(first[0]["limits"], {
            "kernel_instructions": 1000000, "timeout_seconds": 17,
        })
        self.assertEqual(first[2]["limits"], {
            "kernel_instructions": 2000000, "timeout_seconds": 23,
        })
        self.assertEqual(len({row["n"] for row in first}), len(first))

    def test_group_memory_limit_is_rejected_until_it_is_enforced(self):
        cfg = _grouped_cfg(_packed_group("L1", 0, 7, limits={
            "timeout_seconds": 17, "memory_mb": 4096,
        }))
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", "cohort-secret"), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            with self.assertRaisesRegex(judge.InfraError, "memory_mb"):
                judge.performance_plan(cfg, "demo")

    def test_unseeded_local_packed_plan_is_deterministic_and_uncommitted(self):
        cfg = _grouped_cfg(_packed_group("L1", 0, 3))
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", ""), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            self.assertEqual(
                judge.performance_plan(cfg, "demo"),
                judge.performance_plan(cfg, "demo"),
            )
            self.assertIsNone(judge._seed_commitment())

    def test_official_grouped_policy_forbids_perf_count_override(self):
        cfg = _grouped_cfg(_packed_group("L1", 0, 3))
        with mock.patch.object(judge, "TIMING_METRIC", "perf_instructions"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", True), \
             mock.patch.object(judge, "PERF_SEED", "cohort-secret"), \
             mock.patch.dict(os.environ, {"PERF_COUNT": "1"}):
            with self.assertRaisesRegex(judge.InfraError, "PERF_COUNT is forbidden"):
                judge.performance_plan(cfg, "demo")

    def test_local_perf_count_caps_each_group_to_a_stable_prefix(self):
        cfg = _grouped_cfg(
            _packed_group("L1", 0, 3, count=2),
            _packed_group("L2", 1, 9, count=3),
        )
        common = [
            mock.patch.object(judge, "TIMING_METRIC", "wall_time"),
            mock.patch.object(judge, "OFFICIAL_EVAL", False),
            mock.patch.object(judge, "PERF_SEED", "cohort-secret"),
        ]
        with common[0], common[1], common[2], \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            full = judge.performance_plan(cfg, "demo")
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", "cohort-secret"), \
             mock.patch.dict(os.environ, {"PERF_COUNT": "1"}):
            quick = judge.performance_plan(cfg, "demo")

        self.assertEqual(len(full), 5)
        self.assertEqual([row["slot"] for row in quick], [0, 1])
        self.assertEqual(
            [(row["group"], row["case"]) for row in quick],
            [("L1", 0), ("L2", 0)],
        )
        self.assertEqual(quick[0]["n"], full[0]["n"])
        self.assertEqual(quick[1]["n"], full[2]["n"])

    def test_nonpositive_or_malformed_local_group_count_is_ignored(self):
        cfg = _grouped_cfg(_packed_group("L1", 0, 3, count=2))
        plans = []
        for override in ("0", "-1", "bogus"):
            with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
                 mock.patch.object(judge, "OFFICIAL_EVAL", False), \
                 mock.patch.object(judge, "PERF_SEED", "cohort-secret"), \
                 mock.patch.dict(os.environ, {"PERF_COUNT": override}):
                plans.append(judge.performance_plan(cfg, "demo"))
        self.assertTrue(all(len(plan) == 2 for plan in plans))
        self.assertEqual(plans[0], plans[1])
        self.assertEqual(plans[1], plans[2])

    def test_range_fixed_and_invalid_mixed_legacy_policy(self):
        cfg = _grouped_cfg(
            {
                "id": "small", "order": 0,
                "sampling": {
                    "kind": "linear_range", "min": 10, "max": 30,
                    "count": 3, "jitter": 0,
                },
                "award": {"mode": "milestones", "table": [{"passed": 3, "points": 10}]},
                "limits": {},
            },
            {
                "id": "large", "order": 1,
                "sampling": {"kind": "fixed", "values": [100, 101]},
                "award": {"mode": "milestones", "table": [{"passed": 2, "points": 20}]},
                "limits": {},
            },
        )
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", ""), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            plan = judge.performance_plan(cfg, "demo")
        self.assertEqual([row["n"] for row in plan], [10, 20, 30, 100, 101])

        cfg["perf"] = {"min": 1, "max": 2}
        with self.assertRaisesRegex(judge.InfraError, "must not define both"):
            judge.performance_plan(cfg, "demo")

    def test_policy_v2_commits_to_plan_seed_and_full_evaluation_config(self):
        cfg = _grouped_cfg(_packed_group("L1", 0, 5))
        result = {"stages": {}, "timing_protocol": "local-v2"}
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", "cohort-secret"), \
             mock.patch.object(judge, "EVALUATION_COHORT", "round-x"), \
             mock.patch.object(judge, "_problem_bundle_digest", return_value="a" * 64), \
             mock.patch.object(judge, "_evaluator_bundle_digest", return_value="b" * 64), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            plan = judge.performance_plan(cfg, "demo")
            cohort = judge._evaluation_cohort(
                "demo", cfg, [row["n"] for row in plan], 3, result,
                performance_plan=plan,
            )
            changed_cfg = json.loads(json.dumps(cfg))
            changed_cfg["evaluation"]["groups"][0]["award"]["table"][0]["points"] += 1
            changed = judge._evaluation_cohort(
                "demo", changed_cfg, [row["n"] for row in plan], 3, result,
                performance_plan=plan,
            )

        policy = cohort["policy"]
        self.assertEqual(policy["schema"], "evaluation-policy-v2")
        self.assertEqual(policy["budgets"]["perf_phase_budget_seconds"], 0)
        self.assertEqual(policy["evaluation"], cfg["evaluation"])
        self.assertEqual(policy["performance_plan"], plan)
        encoded = json.dumps(
            plan, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        self.assertEqual(
            policy["performance_plan_sha256"],
            __import__("hashlib").sha256(encoded).hexdigest(),
        )
        self.assertRegex(policy["seed_commitment"], r"^[0-9a-f]{64}$")
        self.assertEqual(cohort["id"], cohort["policy_sha256"][:24])
        self.assertNotEqual(cohort["id"], changed["id"])

    def test_grouped_cases_disable_the_legacy_aggregate_deadline(self):
        with mock.patch.object(judge, "PERF_PHASE_BUDGET", 10800), \
             mock.patch.object(judge.time, "monotonic", return_value=100.0):
            self.assertIsNone(judge._performance_phase_deadline([{"slot": 0}]))
            self.assertEqual(judge._performance_phase_deadline(None), 10900.0)

    def test_scaling_rows_repeat_group_and_case_for_every_outcome(self):
        plan = [
            {"slot": 0, "group": "L1", "case": 0, "n": 10, "limits": {}},
            {"slot": 1, "group": "L1", "case": 1, "n": 20, "limits": {}},
            {"slot": 2, "group": "L2", "case": 0, "n": 30, "limits": {}},
        ]

        def probe(n):
            if n == 10:
                return {"n": n, "result": "timeout"}, None
            if n == 20:
                return {"n": n, "result": "build-error"}, "boom"
            return {"n": n, "result": "ok"}, None

        scaling, error = judge._collect_perf_slots(
            [10, 20, 30], probe, performance_plan=plan)
        self.assertEqual(error, "boom")
        self.assertEqual(
            [(row["group"], row["case"], row["result"]) for row in scaling],
            [("L1", 0, "timeout"), ("L1", 1, "build-error"), ("L2", 0, "not-run")],
        )

        exhausted, error = judge._collect_perf_slots(
            [10, 20, 30], probe, deadline=0.0, performance_plan=plan)
        self.assertIsNone(error)
        self.assertEqual(
            [(row["group"], row["case"], row["result"]) for row in exhausted],
            [("L1", 0, "budget-exhausted"),
             ("L1", 1, "budget-exhausted"),
             ("L2", 0, "budget-exhausted")],
        )


class GroupedJudgeReportingTests(unittest.TestCase):
    def test_completed_grouped_verdict_scoring_failure_is_infrastructure(self):
        from tests.test_scoring import grouped_verdict

        malformed = grouped_verdict("malformed", [100, 100, 100, 100])
        malformed["stages"]["performance_plan"][0]["case"] = 99
        with self.assertRaisesRegex(judge.InfraError, "canonical grouped scoring rejected"):
            judge._validated_grouped_score_view(malformed)

        zero_points = grouped_verdict("zero", [None, None, None, None])
        view = judge._validated_grouped_score_view(zero_points)
        self.assertTrue(view["scoreable"])
        self.assertEqual(view["points"], 0)

    def test_grouped_score_summary_uses_canonical_points_and_instruction_caps(self):
        from tests.test_scoring import grouped_verdict

        item = grouped_verdict("grouped", [100, 1001, 100, None], correctness=10)
        view = judge._score_view(item)

        self.assertIsNotNone(view)
        self.assertEqual(view["points"], 30)
        self.assertEqual(view["completed_slots"], 2)
        self.assertEqual(
            judge._grouped_score_summary(item, view),
            "30/75 points; 2/4 passed cases; 200 ranking instructions",
        )

    def test_grouped_leaderboard_uses_points_profile_not_legacy_coverage(self):
        from tests.test_scoring import grouped_verdict, verdict, _reseal_policy

        grouped = grouped_verdict("grouped", [100, 1001, 100, None], correctness=10)
        legacy = verdict("legacy-conv", [100, 200, 300])
        legacy["problem"] = "conv"
        legacy["evaluation_cohort"]["policy"]["problem"] = "conv"
        _reseal_policy(legacy)
        old_results = judge.RESULTS
        with tempfile.TemporaryDirectory() as td:
            try:
                judge.RESULTS = Path(td)
                for item in (grouped, legacy):
                    directory = Path(td) / item["problem"]
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / f"{item['submission']}.json").write_text(json.dumps(item))
                judge.leaderboard()
                report = (Path(td) / "leaderboard.md").read_text()
            finally:
                judge.RESULTS = old_results

        self.assertIn(
            "| points | passed cases | group profile | case outcomes | ranking work |",
            report,
        )
        self.assertIn("L2:20/50, L1:10/25", report)
        self.assertIn("L2:01, L1:01", report)
        self.assertIn("30/75 points; 2/4 passed cases", report)
        self.assertNotIn("legacy-conv", report)
        self.assertNotIn("## conv", report)
        self.assertNotIn("| rank | submission | coverage | total work | score |", report)


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

    def test_oracle_sigkill_is_a_resource_limit(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(judge, "run", return_value=(-9, "")), \
                 mock.patch.object(
                     judge, "_attested_local_memory_kill", return_value=True):
                kind, detail = judge._eval_impl_value(Path(td), {}, 10, 1)
        self.assertEqual((kind, detail), ("resource-limit", None))

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

    def test_perf_export_build_and_export_share_one_stage_cap(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            artifact_lib = work / "lib"
            artifact_lib.mkdir()
            with mock.patch.object(judge, "run", return_value=(0, "")) as run_mock, \
                 mock.patch.object(
                     judge.time, "monotonic", side_effect=[100.0, 100.0, 110.0]):
                kind, detail, _ = judge._perf_export(
                    work, {}, 7, "13", work / "point.export", 9,
                    artifact_lib, Path("lean"))

        self.assertEqual((kind, detail), ("timeout", None))
        self.assertEqual(run_mock.call_count, 1)

    def test_perf_export_sigkill_is_a_resource_limit(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            artifact_lib = work / "lib"
            artifact_lib.mkdir()
            with mock.patch.object(judge, "run", return_value=(137, "")), \
                 mock.patch.object(
                     judge, "_attested_local_memory_kill", return_value=True):
                kind, detail, _ = judge._perf_export(
                    work, {}, 7, "13", work / "point.export", 9,
                    artifact_lib, Path("lean"))
        self.assertEqual((kind, detail), ("resource-limit", None))

    def test_perf_export_rechecks_legacy_deadline_between_steps(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            artifact_lib = work / "lib"
            artifact_lib.mkdir()
            with mock.patch.object(judge, "run", return_value=(0, "")) as run_mock, \
                 mock.patch.object(
                     judge.time, "monotonic", side_effect=[100.0, 100.0, 106.0]):
                kind, detail, _ = judge._perf_export(
                    work, {}, 7, "13", work / "point.export", 9,
                    artifact_lib, Path("lean"), deadline=105.0)

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
        "memory_mb": judge.REPLAY_MEMORY_MB,
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
            "memory_mb": judge.REPLAY_MEMORY_MB,
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

    def test_target_and_v3_contract_are_bound_into_remote_request(self):
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
        self.assertEqual(parsed.path, "/ktp/v3/time")
        self.assertEqual(query["measurement_contract"], [judge.MEASUREMENT_CONTRACT])
        self.assertEqual(query["boundary"], [judge.TARGET_REPLAY_BOUNDARY])
        self.assertEqual(query["target"], [target])
        self.assertEqual(query["memory_mb"], [str(judge.REPLAY_MEMORY_MB)])
        headers = {key.lower(): value for key, value in req.header_items()}
        self.assertEqual(
            headers["x-measurement-contract"], judge.MEASUREMENT_CONTRACT)
        self.assertEqual(
            headers["x-measurement-boundary"], judge.TARGET_REPLAY_BOUNDARY)
        self.assertEqual(headers["x-measurement-target"], target)
        self.assertEqual(
            headers["x-replay-memory-mb"], str(judge.REPLAY_MEMORY_MB))

    def test_remote_resource_limit_is_valid_only_with_bound_memory(self):
        limited = _ok_response()
        limited["status"] = "resource-limit"
        limited.pop("samples")
        limited["resource"] = "memory"
        limited["resource_phase"] = "replay"
        self.assertIsNone(judge._remote_response_error(limited, 1))

        limited["memory_mb"] += 1
        self.assertIn(
            "memory limit", judge._remote_response_error(limited, 1))

        limited["memory_mb"] = judge.REPLAY_MEMORY_MB
        limited["resource"] = "cpu"
        self.assertIn(
            "not identified as memory", judge._remote_response_error(limited, 1))

    def test_sigkill_exit_forms_are_resource_limit_candidates(self):
        self.assertTrue(judge._died_by_sigkill(-9))
        self.assertTrue(judge._died_by_sigkill(137))
        self.assertFalse(judge._died_by_sigkill(-11))
        self.assertFalse(judge._attested_local_memory_kill(-9))
        with mock.patch.object(judge, "SANDBOX_MODE", "container"), \
             mock.patch.object(judge, "EVALUATION_RESOURCE_POLICY", {"memory": "4g"}), \
             mock.patch.object(judge, "_LAST_RUN_OOM_KILL", [True]), \
             mock.patch.dict(os.environ, {"ISOLATION_ATTESTATION": "run_isolated.sh"}):
            self.assertTrue(judge._attested_local_memory_kill(-9))

        with mock.patch.object(judge, "SANDBOX_MODE", "container"), \
             mock.patch.object(judge, "EVALUATION_RESOURCE_POLICY", {"memory": "4g"}), \
             mock.patch.object(judge, "_LAST_RUN_OOM_KILL", [False]), \
             mock.patch.dict(os.environ, {"ISOLATION_ATTESTATION": "run_isolated.sh"}):
            self.assertFalse(judge._attested_local_memory_kill(-9))

    def test_run_binds_and_resets_cgroup_oom_evidence_per_command(self):
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(judge, "_LAST_RUN_OOM_KILL", [True]) as evidence, \
             mock.patch.object(judge, "_read_cgroup_oom_kills", side_effect=[7, 7]):
            rc, _ = judge.run(["/usr/bin/true"], Path(td), os.environ.copy(), 2)
            self.assertEqual(rc, 0)
            self.assertFalse(evidence[0])

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(judge, "_LAST_RUN_OOM_KILL", [False]) as evidence, \
             mock.patch.object(judge, "_read_cgroup_oom_kills", side_effect=[7, 8]):
            rc, _ = judge.run(["/usr/bin/true"], Path(td), os.environ.copy(), 2)
            self.assertEqual(rc, 0)
            self.assertTrue(evidence[0])

        # Even a non-SIGKILL consumer clears the preceding command's evidence.
        with mock.patch.object(judge, "_LAST_RUN_OOM_KILL", [True]) as evidence:
            self.assertFalse(judge._attested_local_memory_kill(1))
            self.assertFalse(evidence[0])

    def test_group_timeout_caps_remote_per_replay_timeout(self):
        captured = []

        def urlopen(req, timeout):
            captured.append((req, timeout))
            return _Response(_ok_response())

        with mock.patch.object(judge, "TIMING_EXECUTOR_URLS", ["https://exec"]), \
             mock.patch.object(judge, "_EXECUTOR_ATTEMPT_SLEEPS", [0]), \
             mock.patch.object(judge, "TIMING_TIMEOUT", 1800), \
             mock.patch.object(judge.urllib.request, "urlopen", side_effect=urlopen):
            judge._time_remote(self.export, 1, timeout_cap=17)

        parsed = judge.urllib.parse.urlparse(captured[0][0].full_url)
        query = judge.urllib.parse.parse_qs(parsed.query)
        self.assertEqual(query["timeout_secs"], ["17"])

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

    def test_official_evaluation_cannot_use_remote_timing(self):
        with mock.patch.object(judge, "OFFICIAL_EVAL", True), \
             mock.patch.object(judge, "TIMING_METRIC", "perf_instructions"), \
             mock.patch.object(judge, "TIMING_EXECUTOR_URLS", ["https://executor"]), \
             mock.patch.object(judge, "PERF_SEED", "secret"), \
             mock.patch.object(judge, "_PERF_SEED_SOURCE", ["stdin"]), \
             mock.patch.object(judge, "EVALUATION_COHORT", "round-x"), \
             mock.patch.object(judge, "EVALUATION_RUN_ID", "run-x"):
            with self.assertRaisesRegex(judge.InfraError, "local PMU timing"):
                judge.judge(Path("/tmp/unused-job"), "fib", "/tmp/unused", 3, "test")

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
        self.assertEqual(contract["remote_protocol"], "KTP/3")
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
        self.assertNotIn("Lean4Checker", timer_lakefile)  # 4.33.1 uses built-in Lean.Replay


if __name__ == "__main__":
    unittest.main()
