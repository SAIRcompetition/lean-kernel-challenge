#!/usr/bin/env python3
"""Regression tests for green-gate manifest coverage."""

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_harness  # noqa: E402


class HarnessManifestTests(unittest.TestCase):
    def test_current_manifest_covers_every_example_and_problem(self):
        cases = json.loads(run_harness.MANIFEST.read_text())["cases"]
        run_harness.validate_manifest(cases)

    def test_duplicate_case_is_rejected(self):
        cases = json.loads(run_harness.MANIFEST.read_text())["cases"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            run_harness.validate_manifest(cases + [dict(cases[0])])


if __name__ == "__main__":
    unittest.main()
