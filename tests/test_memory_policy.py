"""Memory configuration must have identical units at launch, judging, and scoring."""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from memory_policy import memory_mb_from_envelope, problem_memory_mb, valid_memory_mb
from problem_layout import evaluation_problem_dir, iter_evaluation_problem_dirs


class MemoryPolicyTests(unittest.TestCase):
    def test_whole_mib_units_are_exact_and_not_rounded(self):
        for text in ("4g", "4G", "4096m", "4096M", "4194304k", "4294967296b", "4294967296"):
            self.assertEqual(memory_mb_from_envelope(text), 4096, text)
        for text in (None, "unlimited", "max", "local-unspecified", "0", "1", "5m",
                     "1.5g", "4096mb", "4g ", "-4g", "4g;false", "4294967295b",
                     "9" * 100 + "g", "9223372036854775808"):
            self.assertIsNone(memory_mb_from_envelope(text), text)

    def test_invalid_or_missing_limits_have_no_global_fallback(self):
        for value in (None, True, False, 0, -1, 5, 4096.0, "4096", 1 << 80):
            self.assertFalse(valid_memory_mb(value))
            with self.assertRaises(ValueError):
                problem_memory_mb({"evaluation": {"memory_mb": value}})
        for config in ({}, {"evaluation": {}}, {"evaluation": None}, []):
            with self.assertRaises(ValueError):
                problem_memory_mb(config)
        self.assertEqual(problem_memory_mb({"evaluation": {"memory_mb": 8192}}), 8192)

    def test_every_scored_problem_declares_its_own_limit(self):
        pipeline = json.loads((ROOT / "pipeline/config.json").read_text())
        self.assertNotIn("memory_mb", pipeline["sandbox"])
        count = 0
        for path in iter_evaluation_problem_dirs(ROOT):
            cfg = json.loads((path / "config.json").read_text())
            if "evaluation" in cfg:
                count += 1
                self.assertTrue(valid_memory_mb(problem_memory_mb(cfg)), path)
        self.assertEqual(count, 9)

    def test_ci_memory_command_reads_the_evaluator_config(self):
        workflow = (ROOT / ".github/workflows/isolation-wrapper.yml").read_text()
        config_paths = re.findall(r"python3 scripts/memory_policy\.py ([^\s)]+)", workflow)
        self.assertEqual(len(config_paths), 1)
        config = evaluation_problem_dir(ROOT, "fib") / "config.json"
        self.assertEqual(ROOT / config_paths[0], config)
        result = subprocess.run(
            [sys.executable, "scripts/memory_policy.py", config_paths[0]],
            cwd=ROOT, capture_output=True, text=True, timeout=10, check=True,
        )
        expected = problem_memory_mb(json.loads(config.read_text()))
        self.assertEqual(result.stdout.strip(), f"{expected}m")


if __name__ == "__main__":
    unittest.main()
