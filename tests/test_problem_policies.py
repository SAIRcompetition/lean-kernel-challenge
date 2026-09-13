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
from problem_layout import evaluation_problem_dir, iter_evaluation_problem_dirs


GROUPED_PROBLEMS = {
    "fib": {
        "ids": ["F1", "F2", "F3"],
        "kind": "geometric_range",
        "scales": [(5_000, 10_000), (20_000, 40_000), (80_000, 150_000)],
        "counts": [2, 2, 2],
        "timeouts": [30, 60, 120],
    },
    "partition": {
        "ids": ["P1", "P2", "P3"],
        "kind": "geometric_range",
        "scales": [(14, 18), (22, 26), (32, 36)],
        "counts": [2, 2, 2],
        "timeouts": [30, 60, 120],
    },
    "mertens": {
        "ids": ["M1", "M2", "M3"],
        "kind": "geometric_range",
        "scales": [(25, 50), (80, 150), (300, 500)],
        "counts": [2, 2, 2],
        "timeouts": [30, 60, 120],
    },
    "primecount": {
        "ids": ["Q1", "Q2", "Q3"],
        "kind": "geometric_range",
        "scales": [(50, 100), (150, 300), (600, 1_000)],
        "counts": [2, 2, 2],
        "timeouts": [30, 60, 120],
    },
    "permanent": {
        "ids": ["R1", "R2", "R3"],
        "kind": "packed",
        "scales": [6, 12, 16],
        "counts": [5, 5, 5],
        "timeouts": [30, 60, 120],
        "profile": "hardest_group_then_count",
    },
    "ca-rule110": {
        "ids": ["C1", "C2", "C3"],
        "kind": "packed",
        "scales": [2, 4, 8],
        "counts": [2, 2, 2],
        "timeouts": [30, 60, 120],
        "profile": "hardest_group_then_count",
    },
    "sha256": {
        "ids": ["H1", "H2", "H3"],
        "kind": "packed",
        "scales": [4, 32, 512],
        "counts": [2, 2, 2],
        "timeouts": [30, 60, 120],
        "profile": "hardest_group_then_count",
    },
    "polydisc": {
        "ids": ["D1", "D3", "D5"],
        "kind": "uniform_int",
        "scales": [
            (2 ** 18, 2 ** 25),
            (2 ** 37, 2 ** 45),
            (2 ** 57, 2 ** 63),
        ],
        "counts": [2, 2, 2],
        "timeouts": [30, 60, 120],
        "profile": "hardest_group_then_count",
    },
}


def _config(problem):
    return json.loads((evaluation_problem_dir(ROOT, problem) / "config.json").read_text())


class PublishedProblemPolicyTests(unittest.TestCase):
    def test_exactly_eight_grouped_leaderboards(self):
        found = {
            path.name
            for path in iter_evaluation_problem_dirs(ROOT)
            if "evaluation" in json.loads((path / "config.json").read_text())
        }
        self.assertEqual(found, set(GROUPED_PROBLEMS))
        self.assertEqual(score.STAGE1_PROBLEMS, set(GROUPED_PROBLEMS))

        for problem in ("conv", "saw"):
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                evaluation_problem_dir(ROOT, problem)

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
                    evaluation["ranking"]["contract"], "full-plan-v1")
                self.assertEqual(evaluation["ranking"]["max_points"], 100)
                self.assertNotIn("profile", evaluation["ranking"])

                groups = evaluation["groups"]
                self.assertEqual([group["id"] for group in groups], expected["ids"])
                self.assertEqual([group["order"] for group in groups], [1, 2, 3])
                self.assertEqual(
                    [group["sampling"]["count"] for group in groups],
                    expected["counts"],
                )
                self.assertEqual(
                    [group["limits"]["timeout_seconds"] for group in groups],
                    expected["timeouts"],
                )
                scales = []
                for index, group in enumerate(groups):
                    sampling = group["sampling"]
                    self.assertEqual(sampling["kind"], expected["kind"])
                    if sampling["kind"] == "packed":
                        self.assertEqual(sampling["seed_bits"], 32)
                        scales.append(sampling["scale"])
                    else:
                        scales.append((sampling["min"], sampling["max"]))

                    self.assertNotIn("award", group)
                    self.assertNotIn("requires", group)
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
