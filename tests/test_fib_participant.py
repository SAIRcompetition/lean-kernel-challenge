"""The fib participant package is standalone and shares the evaluator's pins."""

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
PARTICIPANT = ROOT / "problems/fib"
sys.path.insert(0, str(ROOT / "scripts"))
import sync_fib_participant as sync

SETUP_SPEC = importlib.util.spec_from_file_location("fib_participant_setup", PARTICIPANT / "setup.py")
setup = importlib.util.module_from_spec(SETUP_SPEC)
SETUP_SPEC.loader.exec_module(setup)


class FibParticipantTests(unittest.TestCase):
    def test_participant_has_no_evaluator_files(self):
        for name in ("Spec.lean", "Challenge.lean", "Solution.lean", "config.json", "dependency-lock.json"):
            self.assertFalse((PARTICIPANT / name).exists(), name)
        self.assertFalse((PARTICIPANT / "QuickTest.lean").exists())
        lakefile = (PARTICIPANT / "lakefile.toml").read_text()
        self.assertIn('defaultTargets = ["Submission"]', lakefile)
        self.assertNotIn("[[lean_exe]]", lakefile)
        self.assertNotIn("quick_test", lakefile)
        self.assertEqual(sync.synchronize(check=True), [])

    def test_sync_checks_pins_without_overwriting_user_code(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            canonical = root / "evaluation/problems/fib"
            canonical.mkdir(parents=True)
            for name in ("lake-manifest.json", "lean-toolchain"):
                shutil.copy2(ROOT / "evaluation/problems/fib" / name, canonical / name)
            participant = root / "problems/fib"
            participant.mkdir(parents=True)
            source = participant / "Submission.lean"
            source.write_text("-- my solution\n")
            sync.synchronize(root)
            self.assertEqual(sync.synchronize(root, check=True), [])
            manifest = participant / "lake-manifest.json"
            contents = json.loads(manifest.read_text())
            contents["packages"][0]["rev"] = "a" * 40
            manifest.write_text(json.dumps(contents))
            with self.assertRaisesRegex(ValueError, "out of sync"):
                sync.synchronize(root, check=True)
            self.assertEqual(json.loads(manifest.read_text())["packages"][0]["rev"], "a" * 40)
            sync.synchronize(root)
            self.assertEqual(source.read_text(), "-- my solution\n")
            self.assertEqual(sync.synchronize(root, check=True), [])

    def test_standalone_setup_only_prepares_dependencies(self):
        with tempfile.TemporaryDirectory() as raw:
            participant = Path(raw)
            shutil.copy2(PARTICIPANT / "lake-manifest.json", participant / "lake-manifest.json")
            pins = setup.package_pins(json.loads((participant / "lake-manifest.json").read_text()))
            source = participant / "Submission.lean"
            source.write_text("-- my solution\n")
            calls = []

            def run(command, **kwargs):
                calls.append((command, kwargs))
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.object(setup, "HERE", participant), \
                 mock.patch.object(setup.subprocess, "run", side_effect=run), \
                 mock.patch.object(setup.subprocess, "check_output", side_effect=[rev + "\n" for _, _, rev in pins]), \
                 mock.patch.dict(os.environ, {"ELAN_TOOLCHAIN": "wrong", "LEAN_PATH": "/wrong"}), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(setup.main(), 0)
            self.assertEqual([command for command, _ in calls], [
                ["lake", "update"],
                ["lake", "exe", "cache", "get", "Mathlib/Data/Nat/Fib/Basic.lean"],
            ])
            for _, options in calls:
                self.assertNotIn("ELAN_TOOLCHAIN", options["env"])
                self.assertNotIn("LEAN_PATH", options["env"])
            self.assertEqual(source.read_text(), "-- my solution\n")

    def test_setup_rejects_unpinned_manifest(self):
        manifest = {"packagesDir": ".lake/packages", "packages": [
            {"name": "mathlib", "url": "https://example.invalid", "rev": "main"},
        ]}
        with self.assertRaisesRegex(ValueError, "exact package revisions"):
            setup.package_pins(manifest)


@unittest.skipUnless(os.environ.get("LKC_REAL_TOOLS") == "1", "requires prepared Lean/Mathlib")
class FibParticipantLeanTests(unittest.TestCase):
    def build(self, replacement=None):
        # Copy only public package sources into a directory with no repository/evaluator.
        # Reuse its dependency cache to avoid downloads, never judge-owned files.
        with tempfile.TemporaryDirectory(prefix="lkc-fib-participant-") as raw:
            work = Path(raw)
            for name in ("Submission.lean", "lakefile.toml", "lake-manifest.json", "lean-toolchain"):
                shutil.copy2(PARTICIPANT / name, work / name)
            (work / ".lake").mkdir()
            (work / ".lake/packages").symlink_to(PARTICIPANT / ".lake/packages", target_is_directory=True)
            if replacement is not None:
                (work / "Submission.lean").write_text(replacement)
            env = dict(os.environ)
            for name in ("ELAN_TOOLCHAIN", "LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT"):
                env.pop(name, None)
            result = subprocess.run(["lake", "--no-cache", "build"], cwd=work, env=env,
                                    capture_output=True, text=True, timeout=180)
            self.assertFalse((work / ".lake/build/bin/quick_test").exists())
            return result

    def test_public_package_builds_without_evaluator(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_incorrect_proof_is_rejected_by_build(self):
        result = self.build(
            "import Mathlib.Data.Nat.Fib.Basic\nnamespace Submission\n"
            "def impl (_ : Nat) : Nat := 0\n"
            "theorem impl_correct : ∀ n, impl n = Nat.fib n := by intro n; rfl\nend Submission\n"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Submission.lean", result.stdout + result.stderr)

    def test_unfinished_proof_is_rejected_by_build(self):
        result = self.build(
            "import Mathlib.Data.Nat.Fib.Basic\nnamespace Submission\n"
            "def impl : Nat → Nat := Nat.fastFib\n"
            "theorem impl_correct : ∀ n, impl n = Nat.fib n := by sorry\nend Submission\n"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sorry", result.stdout + result.stderr)
