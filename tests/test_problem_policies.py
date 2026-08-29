#!/usr/bin/env python3
"""Repository-level checks for the published Stage 1 scoring policies."""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "judge"))
sys.path.insert(0, str(ROOT / "scripts"))

import judge
import score


GROUPED_PROBLEMS = {
    "fib": {
        "ids": ["F1", "F2", "F3", "F4", "F5"],
        "kind": "geometric_range",
        "scales": [
            (10_000, 30_000),
            (50_000, 100_000),
            (150_000, 300_000),
            (400_000, 700_000),
            (800_000, 1_200_000),
        ],
        "counts": [2, 2, 2, 2, 2],
        "points": [5, 10, 15, 25, 45],
        "timeouts": [15, 30, 60, 90, 120],
    },
    "partition": {
        "ids": ["P1", "P2", "P3", "P4", "P5"],
        "kind": "geometric_range",
        "scales": [(10, 20), (25, 35), (50, 100),
                   (200, 500), (1_000, 2_000)],
        "counts": [2, 2, 2, 2, 2],
        "points": [5, 10, 15, 25, 45],
        "timeouts": [15, 30, 60, 120, 300],
    },
    "mertens": {
        "ids": ["M1", "M2", "M3", "M4", "M5"],
        "kind": "geometric_range",
        "scales": [(50, 100), (200, 500), (1_000, 3_000),
                   (10_000, 30_000), (100_000, 300_000)],
        "counts": [2, 2, 2, 2, 2],
        "points": [6, 12, 18, 26, 38],
        "timeouts": [15, 30, 90, 240, 600],
    },
    "primecount": {
        "ids": ["Q1", "Q2", "Q3", "Q4", "Q5"],
        "kind": "geometric_range",
        "scales": [(1_000, 3_000), (5_000, 10_000),
                   (30_000, 100_000), (300_000, 1_000_000),
                   (3_000_000, 10_000_000)],
        "counts": [2, 2, 2, 2, 2],
        "points": [5, 10, 15, 25, 45],
        "timeouts": [30, 60, 120, 300, 600],
    },
    "permanent": {
        "ids": ["R1", "R2", "R3", "R4", "R5"],
        "kind": "packed",
        "scales": [4, 6, 8, 10, 12],
        "counts": [5, 5, 5, 5, 5],
        "points": [5, 10, 15, 25, 45],
        "timeouts": [2, 2, 2, 3, 3],
        "profile": "hardest_group_then_count",
    },
    "saw": {
        "ids": ["S1", "S2", "S3", "S4", "S5"],
        "kind": "packed",
        "scales": [6, 7, 8, 9, 10],
        "counts": [2, 2, 2, 2, 2],
        "points": [5, 10, 15, 25, 45],
        "timeouts": [10, 20, 25, 60, 120],
        "profile": "hardest_group_then_count",
    },
    "ca-rule110": {
        "ids": ["C1", "C2", "C3", "C4", "C5"],
        "kind": "packed",
        "scales": [512, 2048, 8192, 32768, 131072],
        "counts": [2, 2, 2, 2, 2],
        "points": [8, 12, 18, 26, 36],
        "timeouts": [30, 45, 60, 90, 120],
        "profile": "hardest_group_then_count",
    },
    "sha256": {
        "ids": ["H1", "H2", "H3", "H4", "H5"],
        "kind": "packed",
        "scales": [2, 8, 32, 128, 512],
        "counts": [2, 2, 2, 2, 2],
        "points": [6, 10, 16, 26, 42],
        "timeouts": [30, 30, 45, 60, 120],
        "profile": "hardest_group_then_count",
    },
    "polydisc": {
        "ids": ["D1", "D2", "D3", "D4", "D5"],
        "kind": "uniform_int",
        "scales": [
            (2 ** 18, 2 ** 25),
            (2 ** 27, 2 ** 35),
            (2 ** 37, 2 ** 45),
            (2 ** 47, 2 ** 55),
            (2 ** 57, 2 ** 63),
        ],
        "counts": [2, 2, 2, 2, 2],
        "points": [20, 20, 20, 20, 20],
        "timeouts": [120, 180, 300, 600, 900],
        "profile": "hardest_group_then_count",
    },
}


def _config(problem):
    return json.loads((ROOT / "problems" / problem / "config.json").read_text())


class PublishedProblemPolicyTests(unittest.TestCase):
    def test_exactly_nine_grouped_leaderboards_and_conv_is_excluded(self):
        found = {
            path.parent.name
            for path in (ROOT / "problems").glob("*/config.json")
            if "evaluation" in json.loads(path.read_text())
        }
        self.assertEqual(found, set(GROUPED_PROBLEMS))
        self.assertEqual(score.STAGE1_PROBLEMS, set(GROUPED_PROBLEMS))

        conv = _config("conv")
        self.assertNotIn("evaluation", conv)
        self.assertIn("perf", conv)

    def test_published_group_shape_and_hundred_point_total(self):
        global_cfg = json.loads((ROOT / "pipeline" / "config.json").read_text())
        global_timeout = global_cfg["judge"]["timing_timeout_seconds"]
        self.assertEqual(global_cfg["judge"]["timing_reps"], 3)

        for problem, expected in GROUPED_PROBLEMS.items():
            with self.subTest(problem=problem):
                cfg = _config(problem)
                self.assertNotIn("perf", cfg)
                evaluation = cfg["evaluation"]
                self.assertEqual(evaluation["schema"], "grouped-evaluation-v1")
                self.assertEqual(
                    evaluation["ranking"]["contract"], "group-points-v1")
                self.assertEqual(
                    evaluation["ranking"]["profile"],
                    expected.get("profile", "hardest_group_then_slot"),
                )

                groups = evaluation["groups"]
                self.assertEqual([group["id"] for group in groups], expected["ids"])
                self.assertEqual([group["order"] for group in groups], [1, 2, 3, 4, 5])
                self.assertEqual(
                    [group["sampling"]["count"] for group in groups],
                    expected["counts"],
                )
                self.assertEqual(
                    [group["award"]["table"][-1]["points"] for group in groups],
                    expected["points"],
                )
                self.assertEqual(
                    [group["limits"]["timeout_seconds"] for group in groups],
                    expected["timeouts"],
                )
                self.assertEqual(sum(expected["points"]), 100)
                scales = []
                for index, group in enumerate(groups):
                    sampling = group["sampling"]
                    self.assertEqual(sampling["kind"], expected["kind"])
                    if sampling["kind"] == "packed":
                        self.assertEqual(sampling["seed_bits"], 32)
                        scales.append(sampling["scale"])
                    else:
                        scales.append((sampling["min"], sampling["max"]))

                    table = group["award"]["table"]
                    self.assertEqual(table[0], {"passed": 0, "points": 0})
                    self.assertEqual(table[-1]["passed"], expected["counts"][index])
                    self.assertEqual(
                        [(row["passed"], row["points"]) for row in table],
                        sorted((row["passed"], row["points"]) for row in table),
                    )
                    self.assertEqual(set(group["limits"]), {"timeout_seconds"})
                    self.assertLessEqual(
                        group["limits"]["timeout_seconds"], global_timeout)

                    earlier = set(expected["ids"][:index])
                    self.assertTrue(set(group.get("requires", [])) <= earlier)

                self.assertEqual(scales, expected["scales"])

    def test_full_hidden_plans_bind_every_case_to_its_group(self):
        with mock.patch.object(judge, "TIMING_METRIC", "wall_time"), \
             mock.patch.object(judge, "OFFICIAL_EVAL", False), \
             mock.patch.object(judge, "PERF_SEED", "policy-regression-seed"), \
             mock.patch.dict(os.environ, {"PERF_COUNT": ""}):
            for problem, expected in GROUPED_PROBLEMS.items():
                with self.subTest(problem=problem):
                    plan = judge.performance_plan(_config(problem), problem)
                    self.assertEqual(len(plan), sum(expected["counts"]))
                    self.assertEqual([row["slot"] for row in plan], list(range(len(plan))))
                    self.assertEqual(len({row["n"] for row in plan}), len(plan))

                    offset = 0
                    for group_id, count, scale in zip(
                            expected["ids"], expected["counts"], expected["scales"]):
                        rows = plan[offset:offset + count]
                        self.assertEqual([row["group"] for row in rows], [group_id] * count)
                        self.assertEqual([row["case"] for row in rows], list(range(count)))
                        if expected["kind"] == "packed":
                            self.assertEqual(
                                [row["n"] >> 32 for row in rows], [scale] * count)
                            self.assertEqual([row["scale"] for row in rows], [scale] * count)
                        offset += count


if __name__ == "__main__":
    unittest.main()
