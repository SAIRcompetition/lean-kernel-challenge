"""Pure-Python regression tests for the canonical scoring contract."""
import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from problem_layout import evaluation_problem_dir

SPEC = importlib.util.spec_from_file_location("challenge_score", ROOT / "scripts" / "score.py")
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)
CONFIGURED_TOOLCHAIN = json.loads(
    (ROOT / "pipeline" / "config.json").read_text())["toolchain"]


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
        "toolchain": dict(CONFIGURED_TOOLCHAIN),
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


def _reseal_policy(result):
    policy = result["evaluation_cohort"]["policy"]
    encoded = json.dumps(
        policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    result["evaluation_cohort"]["id"] = digest[:24]
    result["evaluation_cohort"]["policy_sha256"] = digest


def make_official_grouped(result):
    """Promote a grouped fixture to the canonical public Stage 1 environment."""
    executor = {"kind": "local", "executor": "pmu-test", "version": "pmu-v1"}
    policy = result["evaluation_cohort"]["policy"]
    result["evaluation_mode"] = "official"
    result["timing_protocol"] = score.LOCAL_PROTOCOL
    policy["evaluation_mode"] = "official"
    policy["timing_protocol"] = score.LOCAL_PROTOCOL
    policy["executor"] = executor
    policy["seed_commitment"] = "a" * 64
    policy["resource_policy"] = {
        "image": "sha256:" + "b" * 64,
        "memory": "4096m",
        "cpus": "2",
        "pids_limit": "512",
        "sandbox_mode": "container",
    }
    policy["budgets"] = dict(score.STAGE1_OFFICIAL_BUDGETS)
    result["evaluation_cohort"]["executor"] = executor
    _reseal_policy(result)
    return result


def _replace_grouped_input(result, slot, n):
    """Keep every sealed/staged copy of one planned input in sync for mutation tests."""
    policy = result["evaluation_cohort"]["policy"]
    policy["performance_plan"][slot]["n"] = n
    policy["inputs"][slot] = n
    result["stages"]["performance_plan"][slot]["n"] = n
    result["stages"]["perf_inputs"][slot] = n
    result["timing"]["scaling"][slot]["n"] = n
    policy["performance_plan_sha256"] = hashlib.sha256(json.dumps(
        policy["performance_plan"], sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    _reseal_policy(result)


def grouped_verdict(name, costs, *, correctness=10, groups=None,
                    ranking=None, inputs=(10, 20, 100, 200), round_id="test-round"):
    """Construct a sealed evaluation-policy-v2 verdict for scorer tests."""
    result = verdict(
        name, costs, correctness=correctness, inputs=inputs, round_id=round_id)
    if groups is None:
        groups = [
            {
                "id": "L1", "label": "Level 1", "order": 1,
                "sampling": {"kind": "fixed", "values": list(inputs[:2]), "count": 2},
                "award": {"mode": "milestones", "table": [
                    {"passed": 0, "points": 0},
                    {"passed": 1, "points": 10},
                    {"passed": 2, "points": 25},
                ]},
                "limits": {"kernel_instructions": 1000, "timeout_seconds": 10},
            },
            {
                "id": "L2", "label": "Level 2", "order": 2,
                "sampling": {"kind": "fixed", "values": list(inputs[2:]), "count": 2},
                "award": {"mode": "milestones", "table": [
                    {"passed": 0, "points": 0},
                    {"passed": 1, "points": 20},
                    {"passed": 2, "points": 50},
                ]},
                "limits": {"kernel_instructions": 1000, "timeout_seconds": 10},
            },
        ]
    if ranking is None:
        ranking = {
            "contract": "group-points-v1", "work": "curve",
            "proof": "last_tiebreak", "profile": "hardest_group_then_slot",
        }
    plan = []
    offset = 0
    for group in groups:
        count = group["sampling"]["count"]
        for case in range(count):
            n = inputs[offset + case]
            plan.append({
                "slot": len(plan), "group": group["id"], "case": case,
                "n": n, "limits": dict(group["limits"]),
            })
            if group["sampling"]["kind"] == "packed":
                plan[-1]["scale"] = group["sampling"]["scale"]
        offset += count
    if offset != len(inputs):
        raise AssertionError("test groups must account for every input")

    result["stages"]["performance_plan"] = json.loads(json.dumps(plan))
    for sample, planned in zip(result["timing"]["scaling"], plan):
        sample["group"] = planned["group"]
        sample["case"] = planned["case"]
    policy = result["evaluation_cohort"]["policy"]
    policy["schema"] = "evaluation-policy-v2"
    del policy["perf"]
    del policy["perf_defaults"]
    policy["budgets"]["perf_phase_budget_seconds"] = 0
    policy["evaluation"] = {
        "schema": "grouped-evaluation-v1",
        "memory_mb": 4096,
        "axis": {
            "label": "test input size", "unit": "n", "input_encoding": "direct Nat input",
        },
        "groups": groups, "ranking": ranking,
    }
    if ranking["contract"] == "full-plan-v1":
        policy["reference_answers"] = {
            "contract": "reference-answers-v1", "sha256": "2" * 64,
            "spec_sha256": "3" * 64, "count": len(inputs),
        }
    policy["performance_plan"] = plan
    plan_encoded = json.dumps(
        plan, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    policy["performance_plan_sha256"] = hashlib.sha256(plan_encoded).hexdigest()
    policy["seed_commitment"] = None
    _reseal_policy(result)
    return result


def configured_grouped_verdict(name, problem, *, correctness, costs=None):
    """Exercise the shipped problem policy with synthetic replay measurements."""
    evaluation = json.loads(
        (evaluation_problem_dir(ROOT, problem) / "config.json").read_text())["evaluation"]
    inputs = []
    for group in evaluation["groups"]:
        sampling = group["sampling"]
        for case in range(sampling["count"]):
            if sampling["kind"] == "packed":
                n = (sampling["scale"] << 32) | (case + 1)
            else:
                n = sampling["min"] + case
            inputs.append(n)
    result = grouped_verdict(
        name, costs if costs is not None else [100] * len(inputs),
        correctness=correctness, inputs=inputs, groups=evaluation["groups"],
        ranking=evaluation["ranking"])
    result["problem"] = problem
    result["evaluation_cohort"]["policy"]["problem"] = problem
    result["evaluation_cohort"]["policy"]["evaluation"] = evaluation
    _reseal_policy(result)
    return result


class ScoringTests(unittest.TestCase):
    def test_retired_tasks_are_not_scoreable_or_loadable_from_local_results(self):
        self.assertEqual(score.STAGE1_PROBLEMS, {
            "fib", "ca-rule110", "mertens", "partition", "permanent", "polydisc",
            "primecount", "sha256",
        })
        for problem in ("saw", "conv"):
            legacy = verdict("retained-legacy", [100, 100, 100], problem=problem)
            grouped = make_official_grouped(grouped_verdict("retained-official", [100] * 4))
            grouped["problem"] = problem
            grouped["evaluation_cohort"]["policy"]["problem"] = problem
            _reseal_policy(grouped)
            for item in (legacy, grouped):
                with self.subTest(problem=problem, submission=item["submission"]):
                    row = score._score_row(item, "perf_instructions")
                    self.assertFalse(row["scoreable"])
                    self.assertIn("retired", row["reason"])
                    self.assertIsNone(row["points"])
                    self.assertFalse(score._is_stage1_public_verdict(item))
                    self.assertEqual(score._groups([item]), {})
            with tempfile.TemporaryDirectory() as temp:
                path = pathlib.Path(temp) / problem / "retained.json"
                path.parent.mkdir()
                path.write_text(json.dumps(grouped))
                with mock.patch.object(score, "RESULTS", temp):
                    self.assertEqual(score._load_verdicts(), [])
                self.assertTrue(path.is_file())

    def test_full_plan_failures_tie_below_passes_for_every_shipped_problem(self):
        for problem in sorted(score.STAGE1_PROBLEMS):
            with self.subTest(problem=problem):
                complete = configured_grouped_verdict("full", problem, correctness=500)
                count = len(complete["timing"]["scaling"])
                failures = [configured_grouped_verdict(
                    name, problem, correctness=proof, costs=costs)
                    for name, proof, costs in [
                        ("one-miss", 1, [1] * (count - 1) + [None]),
                        ("one-pass", 900, [None] * (count - 1) + [100000]),
                        ("no-pass", 100, [None] * count),
                    ]]
                rows = score._rows_for(problem, failures + [complete], "perf_instructions")
                self.assertTrue(all(row["scoreable"] for row in rows), rows)
                self.assertEqual([row["points"] for row in rows], [100, 0, 0, 0])
                self.assertEqual(score._competition_ranks(rows), [1, 2, 2, 2])
                self.assertTrue(all(row["ranking_work"] == float("inf") for row in rows[1:]))
                self.assertEqual(score._format_work(rows[-1]["ranking_work"], "perf_instructions"), "∞")

    def test_full_plan_incomplete_record_or_reference_seal_is_not_a_zero(self):
        original = configured_grouped_verdict("incomplete", "fib", correctness=100)
        for mutate in (
                lambda item: item["timing"]["scaling"].pop(),
                lambda item: item["evaluation_cohort"]["policy"].pop("reference_answers"),
                lambda item: item["evaluation_cohort"]["policy"]["reference_answers"].update(count=1)):
            item = json.loads(json.dumps(original))
            mutate(item)
            _reseal_policy(item)
            row = score._score_row(item, "perf_instructions")
            self.assertFalse(row["scoreable"])
            self.assertIsNone(row["points"])

    def test_full_plan_reference_preparation_failure_cannot_be_scored(self):
        for failure in ("value-eval-timeout", "value-eval-error"):
            item = configured_grouped_verdict("reference-failure", "fib", correctness=100)
            item["timing"]["scaling"][0]["result"] = failure
            row = score._score_row(item, "perf_instructions")
            self.assertFalse(row["scoreable"])
            self.assertIn("reference-answer preparation", row["reason"])

    def test_full_plan_public_report_shows_infinite_cost_and_utc_generation_time(self):
        good = make_official_grouped(configured_grouped_verdict("full", "fib", correctness=100))
        bad = make_official_grouped(configured_grouped_verdict(
            "failed", "fib", correctness=100, costs=[None] * 6))
        old_results = score.RESULTS
        with tempfile.TemporaryDirectory() as temp:
            try:
                score.RESULTS = temp
                directory = pathlib.Path(temp) / "fib"
                directory.mkdir()
                for item in (good, bad):
                    (directory / (item["submission"] + ".json")).write_text(json.dumps(item))
                score.main()
                report = (pathlib.Path(temp) / "scoring.md").read_text()
                self.assertIn("| 2 | failed | 0 | 0/6 | ∞ | scored |", report)
                self.assertRegex(report, r"Generated: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC")
            finally:
                score.RESULTS = old_results

    def test_shipped_problem_policies_use_only_the_declared_work_comparison(self):
        combined = {"ca-rule110", "sha256"}
        target = {"fib", "partition", "mertens", "primecount", "permanent", "polydisc"}
        for problem in sorted(target | combined):
            with self.subTest(problem=problem):
                expensive = configured_grouped_verdict(
                    "a-expensive-proof", problem, correctness=100)
                cheap = configured_grouped_verdict(
                    "z-cheap-proof", problem, correctness=10)
                rows = score._rows_for(problem, [expensive, cheap], "perf_instructions")
                self.assertTrue(all(row["scoreable"] for row in rows), rows)
                self.assertEqual([row["points"] for row in rows], [100, 100])
                if problem in target:
                    self.assertEqual(score._competition_ranks(rows), [1, 1])
                    self.assertEqual([row["sub"] for row in rows],
                                     ["a-expensive-proof", "z-cheap-proof"])
                else:
                    self.assertEqual(score._competition_ranks(rows), [1, 2])
                    self.assertEqual([row["sub"] for row in rows],
                                     ["z-cheap-proof", "a-expensive-proof"])

    def test_shipped_combined_policies_tie_when_total_work_is_equal(self):
        for problem in ("ca-rule110", "sha256"):
            with self.subTest(problem=problem):
                cheap = configured_grouped_verdict("cheap-proof", problem, correctness=10)
                count = len(cheap["stages"]["perf_inputs"])
                expensive = configured_grouped_verdict(
                    "expensive-proof", problem, correctness=100,
                    costs=[10] + [100] * (count - 1))
                rows = score._rows_for(problem, [cheap, expensive], "perf_instructions")
                self.assertTrue(all(row["scoreable"] for row in rows), rows)
                self.assertEqual(rows[0]["ranking_work"], rows[1]["ranking_work"])
                self.assertNotEqual(rows[0]["correctness_work"], rows[1]["correctness_work"])
                self.assertEqual(score._competition_ranks(rows), [1, 1])

    def test_configured_toolchain_matches_current_policy_schema(self):
        policy = verdict("configured-toolchain", [100, 200, 300])[
            "evaluation_cohort"]["policy"]
        self.assertIsNone(score._policy_shape_error(policy))

    def test_public_stage1_reports_admit_only_official_local_pmu_verdicts(self):
        development = grouped_verdict("development", [100] * 4)
        self.assertTrue(score._is_grouped_verdict(development))
        self.assertFalse(score._is_stage1_public_verdict(development))

        official = make_official_grouped(
            grouped_verdict("official", [100] * 4))
        self.assertTrue(score._is_stage1_public_verdict(official))

        official["timing_protocol"] = score.REMOTE_PROTOCOL
        self.assertFalse(score._is_stage1_public_verdict(official))

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
        item = grouped_verdict(
            "aggregate-overflow", [10 ** 308] * 4, correctness=10 ** 308)
        policy = item["evaluation_cohort"]["policy"]
        for group in policy["evaluation"]["groups"]:
            group["limits"].pop("kernel_instructions")
        for case in policy["performance_plan"]:
            case["limits"].pop("kernel_instructions")
        for case in item["stages"]["performance_plan"]:
            case["limits"].pop("kernel_instructions")
        policy["performance_plan_sha256"] = hashlib.sha256(json.dumps(
            policy["performance_plan"], sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        make_official_grouped(item)
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

    def test_grouped_milestones_are_primary_over_completed_case_count(self):
        harder = grouped_verdict("harder", [100, None, 100, None])
        easier = grouped_verdict("easier", [100, 100, None, None])

        rows = score._rows_for("fib", [easier, harder], "perf_instructions")
        by_name = {row["sub"]: row for row in rows}

        self.assertEqual(rows[0]["sub"], "harder")
        self.assertEqual(by_name["harder"]["points"], 30)
        self.assertEqual(by_name["harder"]["group_points"], {"L1": 10, "L2": 20})
        self.assertEqual(by_name["easier"]["points"], 25)

    def test_grouped_ties_prefer_harder_group_then_harder_case(self):
        groups = [
            {
                "id": "L1", "label": "Level 1", "order": 1,
                "sampling": {"kind": "fixed", "values": [10, 20], "count": 2},
                "award": {"mode": "milestones", "table": [
                    {"passed": 0, "points": 0}, {"passed": 1, "points": 10},
                    {"passed": 2, "points": 20},
                ]},
                "limits": {"kernel_instructions": 1000, "timeout_seconds": 10},
            },
            {
                "id": "L2", "label": "Level 2", "order": 2,
                "sampling": {"kind": "fixed", "values": [100, 200], "count": 2},
                "award": {"mode": "milestones", "table": [
                    {"passed": 0, "points": 0}, {"passed": 1, "points": 20},
                    {"passed": 2, "points": 40},
                ]},
                "limits": {"kernel_instructions": 1000, "timeout_seconds": 10},
            },
        ]
        low_group = grouped_verdict(
            "low-group", [100, 100, None, None], groups=groups)
        high_group = grouped_verdict(
            "high-group", [None, None, 100, None], groups=groups)

        rows = score._rows_for(
            "fib", [low_group, high_group], "perf_instructions")
        self.assertTrue(all(row["scoreable"] for row in rows))
        self.assertEqual([row["sub"] for row in rows], ["high-group", "low-group"])

        low_case = grouped_verdict("low-case", [100, None, None, None])
        high_case = grouped_verdict("high-case", [None, 100, None, None])
        rows = score._rows_for(
            "fib", [low_case, high_case], "perf_instructions")
        self.assertTrue(all(row["scoreable"] for row in rows))
        self.assertEqual([row["sub"] for row in rows], ["high-case", "low-case"])

    def test_grouped_sampling_schema_and_plan_membership_are_fail_closed(self):
        unenforced_memory = grouped_verdict("unenforced-memory", [100] * 4)
        unenforced_memory["evaluation_cohort"]["policy"]["evaluation"]["groups"][0][
            "limits"]["memory_mb"] = 4096
        _reseal_policy(unenforced_memory)
        row = score._score_row(unenforced_memory, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("unsupported limits", row["reason"])

        fixed = grouped_verdict("fixed-outside", [100] * 4)
        _replace_grouped_input(fixed, 0, 999999)
        row = score._score_row(fixed, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("fixed sampling", row["reason"])

        extra_field = grouped_verdict("unknown-field", [100] * 4)
        extra_field["evaluation_cohort"]["policy"]["evaluation"]["groups"][0][
            "sampling"]["unexpected"] = True
        _reseal_policy(extra_field)
        row = score._score_row(extra_field, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("unknown field", row["reason"])

        unknown_kind = grouped_verdict("unknown-kind", [100] * 4)
        unknown_kind["evaluation_cohort"]["policy"]["evaluation"]["groups"][0][
            "sampling"] = {"kind": "mystery", "count": 2}
        _reseal_policy(unknown_kind)
        row = score._score_row(unknown_kind, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("unknown sampling kind", row["reason"])

        samplers = {
            "geometric_range": {
                "kind": "geometric_range", "min": 10, "max": 20,
                "count": 2, "jitter": 0.15,
            },
            "linear_range": {
                "kind": "linear_range", "min": 10, "max": 20,
                "count": 2, "jitter": 0.15,
            },
            "range": {
                "kind": "range", "min": 10, "max": 20, "count": 2,
                "jitter": 0.15, "spacing": "linear",
            },
            "uniform_int": {
                "kind": "uniform_int", "min": 10, "max": 20, "count": 2,
            },
        }
        for kind, sampling in samplers.items():
            with self.subTest(kind=kind):
                item = grouped_verdict(kind, [100] * 4)
                item["evaluation_cohort"]["policy"]["evaluation"]["groups"][0][
                    "sampling"] = sampling
                if kind == "uniform_int":
                    evaluation = item["evaluation_cohort"]["policy"]["evaluation"]
                    evaluation["ranking"]["profile"] = "hardest_group_then_count"
                    for group in evaluation["groups"][1:]:
                        values = group["sampling"]["values"]
                        group["sampling"] = {
                            "kind": "uniform_int", "min": min(values),
                            "max": max(values), "count": len(values),
                        }
                _replace_grouped_input(item, 0, 9)
                row = score._score_row(item, "perf_instructions")
                self.assertFalse(row["scoreable"])
                self.assertIn("outside", row["reason"])

        packed = grouped_verdict("packed-mismatch", [100] * 4)
        packed["evaluation_cohort"]["policy"]["evaluation"]["groups"][0][
            "sampling"] = {
                "kind": "packed", "scale": 7, "seed_bits": 32, "count": 2,
            }
        packed_evaluation = packed["evaluation_cohort"]["policy"]["evaluation"]
        packed_evaluation["groups"][1]["sampling"] = {
            "kind": "packed", "scale": 0, "seed_bits": 32, "count": 2,
        }
        packed_evaluation["ranking"]["profile"] = "hardest_group_then_count"
        _reseal_policy(packed)
        row = score._score_row(packed, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("packed sampling", row["reason"])

    def test_grouped_range_plan_cases_must_increase(self):
        item = grouped_verdict("range-order", [100] * 4)
        item["evaluation_cohort"]["policy"]["evaluation"]["groups"][0][
            "sampling"] = {
                "kind": "linear_range", "min": 10, "max": 20,
                "count": 2, "jitter": 0.15,
            }
        _replace_grouped_input(item, 0, 20)
        _replace_grouped_input(item, 1, 10)
        row = score._score_row(item, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("not increasing", row["reason"])

    def test_grouped_zero_points_remains_scoreable(self):
        item = grouped_verdict("zero-points", [None, None, None, None])
        row = score._score_row(item, "perf_instructions")
        self.assertTrue(row["scoreable"])
        self.assertEqual(row["points"], 0)
        self.assertEqual(row["completed_slots"], 0)
        self.assertEqual(row["ranking_work"], 0)

    def test_grouped_memory_exhaustion_is_an_explicit_failed_case(self):
        item = grouped_verdict("memory-limit", [100, None, 100, 100])
        limited = item["timing"]["scaling"][1]
        limited.update({
            "result": "resource-limit",
            "resource": "memory",
            "memory_mb": None,
            "resource_limit_source": "local-container-cgroup",
            "resource_phase": "target-replay",
        })
        row = score._score_row(item, "perf_instructions")
        self.assertTrue(row["scoreable"])
        self.assertEqual(row["completed_slots"], 3)

        # A development launcher may have applied a bound of its own; the record names it.
        limited["memory_mb"] = 4096
        row = score._score_row(item, "perf_instructions")
        self.assertTrue(row["scoreable"])

        limited["memory_mb"] = "4g"
        row = score._score_row(item, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("canonical memory record", row["reason"])

    def test_official_memory_kill_record_must_name_the_sealed_problem_limit(self):
        item = make_official_grouped(
            grouped_verdict("official-memory-limit", [100, None, 100, 100]))
        limited = item["timing"]["scaling"][1]
        limited.update({
            "result": "resource-limit",
            "resource": "memory",
            "memory_mb": 4096,
            "resource_limit_source": "local-container-cgroup",
            "resource_phase": "target-replay",
            "measurement_contract": score.MEASUREMENT_CONTRACT,
            "measurement_boundary": score.PERFORMANCE_BOUNDARY,
            "measurement_target": "Generated.check",
        })
        row = score._score_row(item, "perf_instructions")
        self.assertTrue(row["scoreable"], row["reason"])
        self.assertEqual(row["completed_slots"], 3)

        # A record from a different problem limit cannot pass under this cohort.
        limited["memory_mb"] = 8192
        row = score._score_row(item, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("canonical memory record", row["reason"])

    def test_official_policy_must_seal_the_problem_memory_envelope(self):
        item = make_official_grouped(grouped_verdict("official-envelope", [100] * 4))
        self.assertTrue(score._score_row(item, "perf_instructions")["scoreable"])
        item["evaluation_cohort"]["policy"]["resource_policy"]["memory"] = "unlimited"
        _reseal_policy(item)
        row = score._score_row(item, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("noncanonical resource envelope", row["reason"])

    def test_memory_policy_revisions_are_scored_from_the_seal_and_never_mixed(self):
        first = make_official_grouped(grouped_verdict("before", [100] * 4))
        second = make_official_grouped(grouped_verdict("after", [100] * 4))
        policy = second["evaluation_cohort"]["policy"]
        policy["evaluation"]["memory_mb"] = 8192
        policy["resource_policy"]["memory"] = "8192m"
        _reseal_policy(second)
        with mock.patch("builtins.open", side_effect=AssertionError("live config read")):
            for item in (first, second):
                row = score._score_row(item, "perf_instructions")
                self.assertTrue(row["scoreable"], row["reason"])
        self.assertNotEqual(first["evaluation_cohort"]["id"], second["evaluation_cohort"]["id"])
        rows = score._rows_for("fib", [first, second], "perf_instructions")
        self.assertEqual(len({row["cohort"] for row in rows}), 2)

    def test_official_missing_or_invalid_problem_memory_is_unscored(self):
        for memory in (None, True, 0, -1, 1, 4096.0, "4096", 1 << 80):
            item = make_official_grouped(configured_grouped_verdict("bad-memory", "fib", correctness=10))
            item["evaluation_cohort"]["policy"]["evaluation"]["memory_mb"] = memory
            _reseal_policy(item)
            self.assertFalse(score._score_row(item, "perf_instructions")["scoreable"])
        del item["evaluation_cohort"]["policy"]["evaluation"]["memory_mb"]
        _reseal_policy(item)
        self.assertFalse(score._score_row(item, "perf_instructions")["scoreable"])

    def test_historical_milestone_cohorts_keep_their_original_memory_contract(self):
        item = make_official_grouped(grouped_verdict("historical", [100] * 4))
        policy = item["evaluation_cohort"]["policy"]
        del policy["evaluation"]["memory_mb"]
        policy["resource_policy"]["memory"] = "4g"
        _reseal_policy(item)
        row = score._score_row(item, "perf_instructions")
        self.assertTrue(row["scoreable"], row["reason"])
        policy["resource_policy"]["memory"] = "8g"
        _reseal_policy(item)
        self.assertFalse(score._score_row(item, "perf_instructions")["scoreable"])

    def test_grouped_aggregate_budget_is_disabled_and_cannot_affect_a_case(self):
        enabled = grouped_verdict("aggregate-enabled", [100] * 4)
        enabled["evaluation_cohort"]["policy"]["budgets"][
            "perf_phase_budget_seconds"] = 100
        _reseal_policy(enabled)
        row = score._score_row(enabled, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("disable the aggregate", row["reason"])

        exhausted = grouped_verdict("aggregate-exhausted", [None] * 4)
        exhausted["timing"]["scaling"][0]["result"] = "budget-exhausted"
        row = score._score_row(exhausted, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("requires evaluation retry", row["reason"])

        interrupted = grouped_verdict("interrupted", [100] * 4)
        interrupted["timing"]["scaling"][3]["result"] = "not-run"
        row = score._score_row(interrupted, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("requires evaluation retry", row["reason"])

    def test_official_grouped_policy_requires_three_repetitions(self):
        policy = grouped_verdict(
            "official-reps", [100] * 4)["evaluation_cohort"]["policy"]
        policy["evaluation_mode"] = "official"
        policy["reps"] = 1
        policy["seed_commitment"] = "a" * 64
        policy["resource_policy"] = {
            "image": "sha256:" + "b" * 64,
            "memory": "4096m",
            "cpus": "2",
            "pids_limit": "512",
            "sandbox_mode": "container",
        }
        policy["executor"] = {
            "kind": "local", "executor": "pmu-test", "version": "pmu-v1",
        }
        self.assertIn(
            "exactly 3 repetitions",
            score._policy_v2_shape_error(policy),
        )
        policy["reps"] = 3
        policy["resource_policy"]["memory"] = "8g"
        self.assertIn(
            "noncanonical resource envelope",
            score._policy_v2_shape_error(policy),
        )
        policy["resource_policy"]["memory"] = "4096m"
        policy["executor"] = {
            "kind": "remote", "executor": "pmu-remote", "version": "pmu-v1",
        }
        policy["timing_protocol"] = score.REMOTE_PROTOCOL
        self.assertIn(
            "local PMU protocol",
            score._policy_v2_shape_error(policy),
        )

    def test_grouped_work_and_proof_policies_are_explicit(self):
        last = {
            "contract": "group-points-v1", "work": "curve",
            "proof": "last_tiebreak", "profile": "hardest_group_then_slot",
        }
        expensive_proof = grouped_verdict(
            "expensive-proof", [100, 100, 100, 100], correctness=100, ranking=last)
        cheap_proof = grouped_verdict(
            "cheap-proof", [100, 100, 100, 100], correctness=10, ranking=last)
        rows = score._rows_for(
            "fib", [expensive_proof, cheap_proof], "perf_instructions")
        self.assertEqual([row["sub"] for row in rows], ["cheap-proof", "expensive-proof"])

        gate = dict(last, proof="gate")
        expensive_proof = grouped_verdict(
            "zeta", [100, 100, 100, 100], correctness=100, ranking=gate)
        cheap_proof = grouped_verdict(
            "alpha", [100, 100, 100, 100], correctness=10, ranking=gate)
        rows = score._rows_for(
            "fib", [expensive_proof, cheap_proof], "perf_instructions")
        self.assertEqual(score._competition_ranks(rows), [1, 1])

        include = dict(last, work="total", proof="include")
        expensive_proof = grouped_verdict(
            "expensive-proof", [100, 100, 100, 100], correctness=100,
            ranking=include)
        cheap_proof = grouped_verdict(
            "cheap-proof", [100, 100, 100, 100], correctness=10,
            ranking=include)
        rows = score._rows_for(
            "fib", [expensive_proof, cheap_proof], "perf_instructions")
        self.assertEqual([row["sub"] for row in rows], ["cheap-proof", "expensive-proof"])

    def test_interchangeable_seed_cases_use_counts_without_random_index_tiebreak(self):
        def seeded(name, costs):
            item = grouped_verdict(name, costs)
            policy = item["evaluation_cohort"]["policy"]
            policy["evaluation"]["ranking"]["profile"] = \
                "hardest_group_then_count"
            for group in policy["evaluation"]["groups"]:
                values = group["sampling"]["values"]
                group["sampling"] = {
                    "kind": "uniform_int", "min": min(values),
                    "max": max(values), "count": len(values),
                }
            _reseal_policy(item)
            return item

        left = seeded("left", [100, None, 100, None])
        right = seeded("right", [None, 900, None, 900])
        rows = score._rows_for(
            "seeded", [left, right], "perf_instructions")

        self.assertTrue(all(row["scoreable"] for row in rows))
        self.assertEqual([row["case_profile"] for row in rows], [(1, 1), (1, 1)])
        self.assertTrue(all(not row["work_tiebreak_active"] for row in rows))
        self.assertEqual(score._competition_ranks(rows), [1, 1])

        fast_full = seeded("fast-full", [100, 100, 100, 100])
        slow_full = seeded("slow-full", [200, 200, 200, 200])
        full_rows = score._rows_for(
            "seeded", [slow_full, fast_full], "perf_instructions")
        self.assertTrue(all(row["work_tiebreak_active"] for row in full_rows))
        self.assertEqual(
            [row["sub"] for row in full_rows], ["fast-full", "slow-full"])

    def test_grouped_rejects_inconsistent_work_and_proof_combinations(self):
        for work, proof in (
                ("total", "gate"),
                ("total", "last_tiebreak"),
                ("curve", "include")):
            with self.subTest(work=work, proof=proof):
                ranking = {
                    "contract": "group-points-v1", "work": work, "proof": proof,
                    "profile": "hardest_group_then_slot",
                }
                item = grouped_verdict(
                    f"{work}-{proof}", [100] * 4, ranking=ranking)
                row = score._score_row(item, "perf_instructions")
                self.assertFalse(row["scoreable"])
                self.assertIn("inconsistent work/proof", row["reason"])

    def test_grouped_instruction_limit_determines_case_pass(self):
        item = grouped_verdict("over-cap", [100, 1001, None, None])

        row = score._score_row(item, "perf_instructions")

        self.assertTrue(row["scoreable"])
        self.assertEqual(row["slot_profile"], (1, 0, 0, 0))
        self.assertEqual(row["points"], 10)
        self.assertEqual(row["curve_work"], 100)

    def test_grouped_instruction_limit_is_optional_until_calibrated(self):
        item = grouped_verdict("no-cap", [100, 1001, None, None])
        policy = item["evaluation_cohort"]["policy"]
        for group in policy["evaluation"]["groups"]:
            group["limits"].pop("kernel_instructions")
        for case in policy["performance_plan"]:
            case["limits"].pop("kernel_instructions")
        for case in item["stages"]["performance_plan"]:
            case["limits"].pop("kernel_instructions")
        policy["performance_plan_sha256"] = hashlib.sha256(json.dumps(
            policy["performance_plan"], sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        _reseal_policy(item)

        row = score._score_row(item, "perf_instructions")

        self.assertTrue(row["scoreable"])
        self.assertEqual(row["slot_profile"], (1, 1, 0, 0))
        self.assertEqual(row["points"], 25)

    def test_development_grouped_plan_may_be_a_sampling_prefix(self):
        item = grouped_verdict("local-prefix", [100, 100, 100, 100])
        policy = item["evaluation_cohort"]["policy"]
        for group in policy["evaluation"]["groups"]:
            group["sampling"]["count"] = 3
            group["sampling"]["values"].append(
                group["sampling"]["values"][-1] + 1)
            final = group["award"]["table"][-1]
            group["award"]["table"].append({
                "passed": 3, "points": final["points"] + 10,
            })
        _reseal_policy(item)

        row = score._score_row(item, "perf_instructions")

        self.assertTrue(row["scoreable"])
        self.assertEqual(row["group_points"], {"L1": 25, "L2": 50})
        self.assertIsNotNone(score._grouped_evaluation_shape_error(
            policy["evaluation"], policy["performance_plan"], official=True))

    def test_full_plan_work_and_proof_policies_must_pair(self):
        # Every shipped policy pairs total/include or curve/gate; a mixed pair would
        # publish one comparison and score another.
        for problem, work, proof in (("fib", "curve", "include"), ("sha256", "total", "gate")):
            item = configured_grouped_verdict("mixed", problem, correctness=100)
            policy = item["evaluation_cohort"]["policy"]
            self.assertIsNone(score._grouped_evaluation_shape_error(
                policy["evaluation"], policy["performance_plan"], official=True))
            policy["evaluation"]["ranking"]["work"] = work
            policy["evaluation"]["ranking"]["proof"] = proof
            self.assertIn("must pair", score._grouped_evaluation_shape_error(
                policy["evaluation"], policy["performance_plan"], official=True))

    def test_grouped_plan_and_scaling_identity_are_fail_closed(self):
        stage_mismatch = grouped_verdict("stage-mismatch", [100] * 4)
        stage_mismatch["stages"]["performance_plan"][0]["case"] = 99
        row = score._score_row(stage_mismatch, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("performance_plan", row["reason"])

        scaling_mismatch = grouped_verdict("scaling-mismatch", [100] * 4)
        scaling_mismatch["timing"]["scaling"][0]["group"] = "L2"
        row = score._score_row(scaling_mismatch, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("group/case", row["reason"])

        hash_mismatch = grouped_verdict("hash-mismatch", [100] * 4)
        policy = hash_mismatch["evaluation_cohort"]["policy"]
        policy["performance_plan_sha256"] = "f" * 64
        _reseal_policy(hash_mismatch)
        row = score._score_row(hash_mismatch, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("performance-plan hash", row["reason"])

    def test_grouped_points_cannot_be_injected_through_the_plan(self):
        item = grouped_verdict("injected", [100] * 4)
        item["evaluation_cohort"]["policy"]["performance_plan"][0]["points"] = 999
        item["stages"]["performance_plan"][0]["points"] = 999
        policy = item["evaluation_cohort"]["policy"]
        policy["performance_plan_sha256"] = hashlib.sha256(json.dumps(
            policy["performance_plan"], sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        _reseal_policy(item)

        row = score._score_row(item, "perf_instructions")

        self.assertFalse(row["scoreable"])
        self.assertIn("performance-plan row", row["reason"])

    def test_group_prerequisite_gates_award_until_dependency_is_complete(self):
        item = grouped_verdict("prerequisite", [100, None, 100, 100])
        policy = item["evaluation_cohort"]["policy"]
        policy["evaluation"]["groups"][1]["requires"] = ["L1"]
        _reseal_policy(item)

        row = score._score_row(item, "perf_instructions")

        self.assertTrue(row["scoreable"])
        self.assertEqual(row["group_points"], {"L1": 10, "L2": 0})
        self.assertEqual(row["points"], 10)

    def test_unsafe_normalized_work_contract_is_rejected(self):
        ranking = {
            "contract": "group-points-v1", "work": "worst_normalized",
            "proof": "gate", "profile": "hardest_group_then_slot",
        }
        item = grouped_verdict("unsafe-normalization", [100] * 4, ranking=ranking)

        row = score._score_row(item, "perf_instructions")

        self.assertFalse(row["scoreable"])
        self.assertIn("worst_normalized", row["reason"])


class SealHardeningTests(unittest.TestCase):
    """Regressions for the fail-closed hardenings layered onto the sealed-cohort scorer."""

    def test_value_eval_error_fails_only_its_case(self):
        # A deterministic value-oracle failure at one input is a case failure, not a
        # run-voiding error: the submission keeps every other case's points.
        baseline = grouped_verdict("oracle-crash", [100, None, 100, 100])
        baseline_row = score._score_row(baseline, "perf_instructions")
        self.assertTrue(baseline_row["scoreable"])

        item = grouped_verdict("oracle-crash", [100, None, 100, 100])
        item["timing"]["scaling"][1]["result"] = "value-eval-error"
        item["timing"]["scaling"][1]["detail"] = "value oracle failed at n=20: NONLIT"
        row = score._score_row(item, "perf_instructions")
        self.assertTrue(row["scoreable"])
        self.assertEqual(row["points"], baseline_row["points"])
        self.assertEqual(row["completed_slots"], baseline_row["completed_slots"])

    def test_official_budget_pin_rejects_dev_override(self):
        item = grouped_verdict("dev-budget", [100, 100, 100, 100])
        make_official_grouped(item)
        item["evaluation_cohort"]["policy"]["budgets"]["timing_timeout_seconds"] = 30
        _reseal_policy(item)
        row = score._score_row(item, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("noncanonical watchdog budgets", row["reason"])

    def test_official_toolchain_pin_rejects_stale_seal(self):
        item = grouped_verdict("stale-toolchain", [100, 100, 100, 100])
        make_official_grouped(item)
        item["evaluation_cohort"]["policy"]["toolchain"]["comparator_rev"] = "d" * 40
        _reseal_policy(item)
        row = score._score_row(item, "perf_instructions")
        self.assertFalse(row["scoreable"])
        self.assertIn("different toolchain", row["reason"])

    def test_misfiled_verdict_never_loads(self):
        # The containing directory is authoritative for the problem a record scores under.
        item = make_official_grouped(grouped_verdict("misfiled", [100, 100, 100, 100]))
        old_results = score.RESULTS
        with tempfile.TemporaryDirectory() as temp:
            try:
                score.RESULTS = temp
                wrong = pathlib.Path(temp) / "sha256"
                wrong.mkdir()
                (wrong / "misfiled.json").write_text(json.dumps(item))
                self.assertEqual(score._load_verdicts(), [])
                right = pathlib.Path(temp) / "fib"
                right.mkdir()
                (right / "misfiled.json").write_text(json.dumps(item))
                self.assertEqual(len(score._load_verdicts()), 1)
            finally:
                score.RESULTS = old_results

    def test_round_spanning_official_cohorts_fail_closed(self):
        alice = make_official_grouped(grouped_verdict("alice", [100, 100, 100, 100]))
        bob = grouped_verdict("bob", [100, 100, 100, 100])
        make_official_grouped(bob)
        # A rotated seed reseals a different policy → different cohort id, same round.
        bob["evaluation_cohort"]["policy"]["seed_commitment"] = "c" * 64
        _reseal_policy(bob)
        old_results = score.RESULTS
        with tempfile.TemporaryDirectory() as temp:
            try:
                score.RESULTS = temp
                pdir = pathlib.Path(temp) / "fib"
                pdir.mkdir()
                (pdir / "alice.json").write_text(json.dumps(alice))
                (pdir / "bob.json").write_text(json.dumps(bob))
                with self.assertRaisesRegex(SystemExit, "multiple official cohorts"):
                    score.main()
                self.assertFalse((pathlib.Path(temp) / "scoring.md").exists())
                with mock.patch.dict(os.environ, {"ALLOW_COHORT_SPLIT": "1"}):
                    score.main()
                report = (pathlib.Path(temp) / "scoring.md").read_text()
                self.assertIn("alice", report)
                self.assertIn("bob", report)
            finally:
                score.RESULTS = old_results


if __name__ == "__main__":
    unittest.main()
