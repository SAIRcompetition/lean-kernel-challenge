"""The seven core problems expose standalone participant packages, not judge workspaces."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from problem_layout import MIGRATED_PROBLEMS, evaluation_problem_dir  # noqa: E402
import sync_participants as sync  # noqa: E402


PROBLEMS = sync.CORE_PARTICIPANT_PROBLEMS
JUDGE_ONLY = ("Challenge.lean", "Solution.lean", "config.json", "dependency-lock.json")


class ParticipantLayoutTests(unittest.TestCase):
    def test_expected_problems_are_migrated_without_saw_or_conv(self):
        self.assertEqual(
            set(PROBLEMS),
            {"ca-rule110", "mertens", "partition", "permanent", "polydisc",
             "primecount", "sha256"},
        )
        self.assertEqual(set(MIGRATED_PROBLEMS), set(PROBLEMS) | {"fib"})
        self.assertNotIn("saw", MIGRATED_PROBLEMS)
        self.assertNotIn("conv", MIGRATED_PROBLEMS)

    def test_participants_have_no_judge_files_and_only_build_submission(self):
        for problem in PROBLEMS:
            with self.subTest(problem=problem):
                participant = ROOT / "problems" / problem
                evaluator = evaluation_problem_dir(ROOT, problem)
                for name in JUDGE_ONLY:
                    self.assertFalse((participant / name).exists(), name)
                for name in ("Spec.lean", "Submission.lean", "lakefile.toml",
                             "lake-manifest.json", "lean-toolchain"):
                    self.assertTrue((participant / name).is_file(), name)
                for name in ("Spec.lean", "Challenge.lean", "Solution.lean", "Submission.lean",
                             "config.json", "lakefile.toml", "lean-toolchain"):
                    self.assertTrue((evaluator / name).is_file(), name)
                lakefile = (participant / "lakefile.toml").read_text()
                self.assertIn('defaultTargets = ["Submission"]', lakefile)
                self.assertIn("warningAsError = true", lakefile)
                self.assertNotIn('name = "Challenge"', lakefile)
                self.assertNotIn('name = "Solution"', lakefile)
                manifest = json.loads((participant / "lake-manifest.json").read_text())
                self.assertEqual(manifest["packagesDir"], ".lake/packages")
                self.assertEqual(manifest["packages"], [])

    def test_specs_and_environment_pins_are_synchronized(self):
        self.assertEqual(sync.synchronize(problems=PROBLEMS, check=True), {
            problem: [] for problem in PROBLEMS
        })
        for problem in PROBLEMS:
            participant = ROOT / "problems" / problem
            evaluator = evaluation_problem_dir(ROOT, problem)
            self.assertEqual(
                (participant / "Spec.lean").read_bytes(),
                (evaluator / "Spec.lean").read_bytes(),
            )
            self.assertEqual(
                (participant / "lean-toolchain").read_bytes(),
                (evaluator / "lean-toolchain").read_bytes(),
            )

    def test_sync_never_overwrites_submission(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for problem in PROBLEMS:
                source_eval = evaluation_problem_dir(ROOT, problem)
                target_eval = root / "evaluation/problems" / problem
                target_eval.mkdir(parents=True)
                for name in ("Spec.lean", "config.json", "lakefile.toml", "lean-toolchain"):
                    shutil.copy2(source_eval / name, target_eval / name)
                participant = root / "problems" / problem
                participant.mkdir(parents=True)
                (participant / "Submission.lean").write_text(f"-- private {problem} solution\n")

            changed = sync.synchronize(root, problems=PROBLEMS)
            self.assertTrue(all(files for files in changed.values()))
            self.assertEqual(sync.synchronize(root, problems=PROBLEMS, check=True), {
                problem: [] for problem in PROBLEMS
            })
            for problem in PROBLEMS:
                self.assertEqual(
                    (root / "problems" / problem / "Submission.lean").read_text(),
                    f"-- private {problem} solution\n",
                )

    def test_sync_fails_closed_if_core_evaluator_gains_dependencies(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = evaluation_problem_dir(ROOT, "partition")
            canonical = root / "evaluation/problems/partition"
            canonical.mkdir(parents=True)
            for name in ("Spec.lean", "config.json", "lakefile.toml", "lean-toolchain"):
                shutil.copy2(source / name, canonical / name)
            (canonical / "lakefile.toml").write_text(
                (canonical / "lakefile.toml").read_text()
                + '\n[[require]]\nname = "unexpected"\npath = "../unexpected"\n'
            )
            with self.assertRaisesRegex(ValueError, "unexpectedly declares dependencies"):
                sync.expected_files("partition", root)

    def test_migrated_resolver_never_falls_back_to_participant_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for problem in MIGRATED_PROBLEMS:
                participant = root / "problems" / problem
                participant.mkdir(parents=True)
                (participant / "config.json").write_text("participant must not be trusted\n")
                expected = root / "evaluation/problems" / problem
                self.assertEqual(evaluation_problem_dir(root, problem), expected)
                self.assertFalse(expected.exists())


@unittest.skipUnless(shutil.which("lake"), "Lean/Lake is not installed")
class ParticipantStandaloneBuildTests(unittest.TestCase):
    @staticmethod
    def _environment():
        clean_env = dict(os.environ)
        for name in ("ELAN_TOOLCHAIN", "LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT"):
            clean_env.pop(name, None)
        return clean_env

    def _build_replacement(self, problem: str, source: str):
        with tempfile.TemporaryDirectory(prefix=f"lkc-participant-negative-{problem}-") as raw:
            work = Path(raw)
            participant = ROOT / "problems" / problem
            for name in ("Spec.lean", "lakefile.toml", "lake-manifest.json", "lean-toolchain"):
                shutil.copy2(participant / name, work / name)
            (work / "Submission.lean").write_text(source)
            return subprocess.run(
                ["lake", "--no-cache", "build"],
                cwd=work, env=self._environment(), text=True, capture_output=True, timeout=300,
            )

    def test_all_core_participant_packages_build_without_evaluator(self):
        clean_env = self._environment()

        def build(problem: str):
            with tempfile.TemporaryDirectory(prefix=f"lkc-participant-{problem}-") as raw:
                work = Path(raw)
                participant = ROOT / "problems" / problem
                for name in ("Spec.lean", "Submission.lean", "lakefile.toml",
                             "lake-manifest.json", "lean-toolchain"):
                    shutil.copy2(participant / name, work / name)
                result = subprocess.run(
                    ["lake", "--no-cache", "build"],
                    cwd=work, env=clean_env, text=True, capture_output=True, timeout=300,
                )
                return problem, result

        # Keep the test bounded while still exercising genuinely isolated Lake workspaces.
        with ThreadPoolExecutor(max_workers=min(4, len(PROBLEMS))) as pool:
            results = list(pool.map(build, PROBLEMS))
        failures = [
            f"{problem}:\n{(result.stdout + result.stderr)[-4000:]}"
            for problem, result in results if result.returncode != 0
        ]
        self.assertEqual(failures, [])

    def test_incorrect_proof_is_rejected(self):
        result = self._build_replacement(
            "partition",
            "import Spec\nnamespace Submission\n"
            "def impl : Nat → Nat := fun _ => 0\n"
            "theorem impl_correct : ∀ n, impl n = partitionSpec n := by intro n; rfl\n"
            "end Submission\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Submission.lean", result.stdout + result.stderr)

    def test_sorry_is_rejected_by_warning_as_error(self):
        result = self._build_replacement(
            "partition",
            "import Spec\nnamespace Submission\n"
            "def impl : Nat → Nat := partitionSpec\n"
            "theorem impl_correct : ∀ n, impl n = partitionSpec n := by sorry\n"
            "end Submission\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sorry", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
