"""All eight problems expose standalone participant packages, not judge workspaces."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from problem_layout import MIGRATED_PROBLEMS, evaluation_problem_dir  # noqa: E402
import sync_participants as sync  # noqa: E402


PROBLEMS = sync.CORE_PARTICIPANT_PROBLEMS
ALL_PROBLEMS = tuple(sorted(MIGRATED_PROBLEMS))
MATHLIB_PROBLEMS = sync.MATHLIB_PARTICIPANT_PROBLEMS
JUDGE_ONLY = ("Challenge.lean", "Solution.lean", "config.json", "dependency-lock.json")


class ParticipantLayoutTests(unittest.TestCase):
    def test_expected_problems_are_migrated_without_saw_or_conv(self):
        self.assertEqual(
            set(PROBLEMS),
            {"ca-rule110", "partition", "permanent", "polydisc", "sha256"},
        )
        self.assertEqual(set(MATHLIB_PROBLEMS), {"fib", "mertens", "primecount"})
        self.assertEqual(set(MIGRATED_PROBLEMS), set(PROBLEMS) | set(MATHLIB_PROBLEMS))
        self.assertNotIn("saw", MIGRATED_PROBLEMS)
        self.assertNotIn("conv", MIGRATED_PROBLEMS)

    def test_participants_have_no_judge_files_and_only_build_submission(self):
        for problem in ALL_PROBLEMS:
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
                if problem in PROBLEMS:
                    self.assertEqual(manifest["packages"], [])
                    self.assertFalse((participant / "setup.py").exists())
                else:
                    self.assertTrue((participant / "setup.py").is_file())
                    self.assertIn("mathlib", {entry["name"] for entry in manifest["packages"]})
                    canonical_manifest = json.loads((evaluator / "lake-manifest.json").read_text())
                    self.assertEqual(manifest["packages"], canonical_manifest["packages"])

    def test_specs_and_environment_pins_are_synchronized(self):
        self.assertEqual(sync.synchronize(check=True), {
            problem: [] for problem in ALL_PROBLEMS
        })
        for problem in ALL_PROBLEMS:
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
            for problem in ALL_PROBLEMS:
                source_eval = evaluation_problem_dir(ROOT, problem)
                target_eval = root / "evaluation/problems" / problem
                target_eval.mkdir(parents=True)
                for name in ("Spec.lean", "config.json", "lakefile.toml", "lean-toolchain",
                             "lake-manifest.json"):
                    # Dependency-free evaluators may omit the optional empty manifest.
                    if name == "lake-manifest.json" and not (source_eval / name).is_file():
                        continue
                    shutil.copy2(source_eval / name, target_eval / name)
                participant = root / "problems" / problem
                participant.mkdir(parents=True)
                (participant / "Submission.lean").write_text(f"-- private {problem} solution\n")

            changed = sync.synchronize(root)
            self.assertTrue(all(files for files in changed.values()))
            self.assertEqual(sync.synchronize(root, check=True), {
                problem: [] for problem in ALL_PROBLEMS
            })
            for problem in ALL_PROBLEMS:
                self.assertEqual(
                    (root / "problems" / problem / "Submission.lean").read_text(),
                    f"-- private {problem} solution\n",
                )

    def test_mathlib_setup_targets_each_specs_direct_imports(self):
        for problem in MATHLIB_PROBLEMS:
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                canonical = root / "evaluation/problems" / problem
                canonical.mkdir(parents=True)
                for name in ("config.json", "lakefile.toml", "lake-manifest.json", "lean-toolchain"):
                    shutil.copy2(ROOT / "evaluation/problems/fib" / name, canonical / name)
                (canonical / "Spec.lean").write_text(
                    "import Std\nimport Mathlib.Data.Nat.Fib.Basic\n"
                    "import Mathlib.NumberTheory.ArithmeticFunction.Moebius -- target\n"
                )
                participant = root / "problems" / problem
                participant.mkdir(parents=True)
                source = participant / "Submission.lean"
                source.write_text("-- private solution\n")
                sync.synchronize_problem(problem, root)
                spec_before = (participant / "Spec.lean").read_bytes()
                module_spec = importlib.util.spec_from_file_location(
                    f"participant_setup_{problem}", participant / "setup.py"
                )
                setup = importlib.util.module_from_spec(module_spec)
                module_spec.loader.exec_module(setup)
                expected_modules = ["Mathlib/Data/Nat/Fib/Basic.lean",
                                    "Mathlib/NumberTheory/ArithmeticFunction/Moebius.lean"]
                self.assertEqual(setup.CACHE_MODULES, expected_modules)
                pins = setup.package_pins(json.loads((participant / "lake-manifest.json").read_text()))
                calls = []

                def run(command, **kwargs):
                    calls.append((command, kwargs))
                    return subprocess.CompletedProcess(command, 0)

                with mock.patch.object(setup.subprocess, "run", side_effect=run), \
                     mock.patch.object(setup.subprocess, "check_output",
                                       side_effect=[rev + "\n" for _, _, rev in pins]), \
                     mock.patch.dict(os.environ, {"ELAN_TOOLCHAIN": "wrong", "LEAN_PATH": "/wrong"}), \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(setup.main(), 0)
                self.assertEqual([command for command, _ in calls], [
                    ["lake", "update"], ["lake", "exe", "cache", "get", *expected_modules],
                ])
                self.assertEqual(calls[-1][1]["cwd"], (participant / ".lake/packages/mathlib").resolve())
                self.assertNotIn("ELAN_TOOLCHAIN", calls[-1][1]["env"])
                self.assertNotIn("LEAN_PATH", calls[-1][1]["env"])
                self.assertEqual(source.read_text(), "-- private solution\n")
                self.assertEqual((participant / "Spec.lean").read_bytes(), spec_before)
                (participant / "setup.py").write_text("# changed setup\n")
                with self.assertRaisesRegex(ValueError, "out of sync: setup.py"):
                    sync.synchronize_problem(problem, root, check=True)
                self.assertEqual((participant / "setup.py").read_text(), "# changed setup\n")

    def test_mathlib_spec_must_identify_targeted_imports(self):
        with self.assertRaisesRegex(ValueError, "direct Mathlib imports"):
            sync.mathlib_cache_modules("import Std\n")
        self.assertEqual(sync.mathlib_cache_modules(
            "import Mathlib.Data.Nat.Fib.Basic\npublic import Mathlib.Data.Nat.Fib.Basic\n"
        ), ["Mathlib/Data/Nat/Fib/Basic.lean"])

    def test_mathlib_sync_rejects_unpinned_manifest(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            canonical = root / "evaluation/problems/fib"
            canonical.mkdir(parents=True)
            for name in ("Spec.lean", "config.json", "lakefile.toml", "lake-manifest.json", "lean-toolchain"):
                shutil.copy2(ROOT / "evaluation/problems/fib" / name, canonical / name)
            manifest = json.loads((canonical / "lake-manifest.json").read_text())
            manifest["packages"][0]["rev"] = "master"
            (canonical / "lake-manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "exact package revisions"):
                sync.expected_files("fib", root)

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


@unittest.skipUnless(os.environ.get("LKC_REAL_TOOLS") == "1", "requires prepared Lean/Mathlib")
class MathlibParticipantStandaloneTests(unittest.TestCase):
    def test_mathlib_packages_setup_and_build_without_evaluator(self):
        # All three packages share exact pins. Reuse only the public dependency
        # checkout; the copied package has no access to evaluator-owned sources.
        dependencies = ROOT / "problems/fib/.lake/packages"
        self.assertTrue((dependencies / "mathlib/.git").exists(), "prepare problems/fib first")
        clean_env = ParticipantStandaloneBuildTests._environment()
        for problem in MATHLIB_PROBLEMS:
            with self.subTest(problem=problem), tempfile.TemporaryDirectory(
                prefix=f"lkc-mathlib-participant-{problem}-"
            ) as raw:
                work = Path(raw)
                participant = ROOT / "problems" / problem
                for name in ("Spec.lean", "Submission.lean", "lakefile.toml",
                             "lake-manifest.json", "lean-toolchain", "setup.py"):
                    shutil.copy2(participant / name, work / name)
                source_before = (work / "Submission.lean").read_bytes()
                (work / ".lake").mkdir()
                (work / ".lake/packages").symlink_to(dependencies, target_is_directory=True)
                prepared = subprocess.run(
                    [sys.executable, "setup.py"], cwd=work, env=clean_env,
                    text=True, capture_output=True, timeout=1800,
                )
                self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
                result = subprocess.run(
                    ["lake", "--no-cache", "build"], cwd=work, env=clean_env,
                    text=True, capture_output=True, timeout=300,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((work / "Submission.lean").read_bytes(), source_before)
                for name in JUDGE_ONLY:
                    self.assertFalse((work / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
