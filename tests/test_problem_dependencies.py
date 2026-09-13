"""Unit tests for pinned problem dependency validation and staging."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import problem_dependencies as deps  # noqa: E402
import prepare_problem_dependencies as prepare_deps  # noqa: E402


class DependencyFixture:
    def __init__(self, root: Path):
        self.problem = root / "problem"
        self.problem.mkdir(parents=True)
        (self.problem / "Spec.lean").write_text("import Demo.Basic\n")
        (self.problem / "lean-toolchain").write_text("leanprover/lean4:v4.33.1\n")
        self.lakefile = (
            'name = "demo"\n\n'
            '[[require]]\nname = "demoDep"\ngit = "https://example.invalid/demo"\n'
            'rev = "REV"\n\n'
            '[[lean_lib]]\nname = "Spec"\n'
        )
        checkout = self.problem / ".lake/packages/demoDep"
        checkout.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=checkout, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=checkout, check=True)
        (checkout / "README").write_text("fixture\n")
        subprocess.run(["git", "add", "README"], cwd=checkout, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=checkout, check=True)
        self.rev = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
        ).strip()
        self.lakefile = self.lakefile.replace("REV", self.rev)
        (self.problem / "lakefile.toml").write_text(self.lakefile)
        self.manifest = {
            "version": "1.2.0", "packagesDir": ".lake/packages",
            "packages": [{
                "name": "demoDep", "url": "https://example.invalid/demo", "rev": self.rev,
            }],
        }
        (self.problem / "lake-manifest.json").write_text(json.dumps(self.manifest))
        self.artifacts = {
            "Demo/Basic.ir.sig": b"signature",
            "Demo/Basic.olean": b"compiled module",
            "Demo/Basic.olean.private": b"private module data",
        }
        bundle = self.problem / deps.BUNDLE_LIB
        for relative, payload in self.artifacts.items():
            path = bundle / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        runtime = deps._strip_require_blocks(self.lakefile).encode()
        records = [
            {"path": relative, "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
            for relative, payload in sorted(self.artifacts.items())
        ]
        self.lock = {
            "schema": deps.SCHEMA,
            "toolchain": "leanprover/lean4:v4.33.1",
            "source": {
                "lakefile_sha256": hashlib.sha256(self.lakefile.encode()).hexdigest(),
                "manifest_sha256": hashlib.sha256(json.dumps(self.manifest).encode()).hexdigest(),
            },
            "root_modules": ["Demo.Basic"],
            "packages": [{
                "name": "demoDep", "url": "https://example.invalid/demo", "rev": self.rev,
            }],
            "runtime_lakefile_sha256": hashlib.sha256(runtime).hexdigest(),
            "artifacts": records,
            "bundle_sha256": deps._bundle_digest(records),
        }
        (self.problem / deps.LOCK_NAME).write_text(json.dumps(self.lock))


class ProblemDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = DependencyFixture(Path(self.temp.name))

    def test_stage_verifies_and_flattens_closure_with_package_free_lakefile(self):
        workspace = Path(self.temp.name) / "work"
        workspace.mkdir()
        (workspace / "lakefile.toml").write_text(self.fixture.lakefile)
        (workspace / "lake-manifest.json").write_text("must disappear")

        result = deps.stage_problem_dependencies(self.fixture.problem, workspace)

        self.assertEqual(result.artifact_count, len(self.fixture.artifacts))
        self.assertEqual(result.artifact_bytes, sum(map(len, self.fixture.artifacts.values())))
        self.assertNotIn("[[require]]", (workspace / "lakefile.toml").read_text())
        self.assertFalse((workspace / "lake-manifest.json").exists())
        for relative, payload in self.fixture.artifacts.items():
            staged = workspace / ".lake/build/lib/lean" / relative
            self.assertEqual(staged.read_bytes(), payload)
            self.assertEqual(staged.stat().st_mode & 0o222, 0)

    def test_tampered_artifact_is_rejected(self):
        (self.fixture.problem / deps.BUNDLE_LIB / "Demo/Basic.olean").write_bytes(b"tampered")
        with self.assertRaisesRegex(deps.DependencyError, "does not match lock"):
            deps.stage_problem_dependencies(self.fixture.problem, Path(self.temp.name) / "work")

    def test_extra_bundle_file_is_rejected(self):
        (self.fixture.problem / deps.BUNDLE_LIB / "Demo/Extra.olean").write_bytes(b"extra")
        with self.assertRaisesRegex(deps.DependencyError, "file set"):
            deps.stage_problem_dependencies(self.fixture.problem, Path(self.temp.name) / "work")

    def test_lock_rejects_path_escape_and_false_bundle_digest(self):
        lock_path = self.fixture.problem / deps.LOCK_NAME
        lock = json.loads(lock_path.read_text())
        lock["artifacts"][0]["path"] = "../escape.olean"
        lock_path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(deps.DependencyError, "escapes"):
            deps.load_dependency_lock(self.fixture.problem)

        lock = self.fixture.lock.copy()
        lock["bundle_sha256"] = "0" * 64
        lock_path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(deps.DependencyError, "bundle digest"):
            deps.load_dependency_lock(self.fixture.problem)

    def test_canonical_source_and_toolchain_are_bound(self):
        for relative in ("lakefile.toml", "lake-manifest.json", "lean-toolchain"):
            with self.subTest(relative=relative):
                fixture = DependencyFixture(Path(self.temp.name) / relative.replace(".", "_"))
                path = fixture.problem / relative
                path.write_text(path.read_text() + ("x" if relative == "lean-toolchain" else "\n"))
                with self.assertRaises(deps.DependencyError):
                    deps.runtime_lakefile(fixture.problem)

    def test_prepared_package_revisions_and_packages_dir_are_validated(self):
        self.assertEqual(
            deps.validate_prepared_packages(self.fixture.problem),
            self.fixture.problem / ".lake/packages",
        )
        manifest_path = self.fixture.problem / "lake-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["packagesDir"] = "/tmp/untrusted"
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(deps.DependencyError):
            deps.validate_prepared_packages(self.fixture.problem)

    def test_dependency_aware_spec_fingerprint_and_legacy_compatibility(self):
        fingerprint = deps.specification_fingerprint(self.fixture.problem)
        self.assertRegex(fingerprint, r"[0-9a-f]{64}")
        lock_path = self.fixture.problem / deps.LOCK_NAME
        lock_path.unlink()
        (self.fixture.problem / "lakefile.toml").write_text(
            deps._strip_require_blocks(self.fixture.lakefile)
        )
        self.assertEqual(
            deps.specification_fingerprint(self.fixture.problem),
            hashlib.sha256((self.fixture.problem / "Spec.lean").read_bytes()).hexdigest(),
        )

    def test_problem_without_lock_is_not_staged(self):
        (self.fixture.problem / deps.LOCK_NAME).unlink()
        (self.fixture.problem / "lakefile.toml").write_text(
            deps._strip_require_blocks(self.fixture.lakefile)
        )
        self.assertIsNone(
            deps.stage_problem_dependencies(self.fixture.problem, Path(self.temp.name) / "unused")
        )

    def test_dependency_lakefile_without_lock_fails_closed(self):
        (self.fixture.problem / deps.LOCK_NAME).unlink()
        with self.assertRaisesRegex(deps.DependencyError, "missing its trusted"):
            deps.stage_problem_dependencies(self.fixture.problem, Path(self.temp.name) / "unused")
        with self.assertRaisesRegex(deps.DependencyError, "missing its trusted"):
            deps.specification_fingerprint(self.fixture.problem)

    def test_cold_preparation_fetches_pins_then_only_targeted_mathlib_cache(self):
        (self.fixture.problem / "Spec.lean").write_text(
            "import Mathlib.NumberTheory.PrimeCounting\n"
            "import Mathlib.NumberTheory.ArithmeticFunction.Moebius\n"
        )
        packages = self.fixture.problem / ".lake/packages"
        # Simulate a fresh checkout without prepared package directories.
        for child in list(packages.iterdir()):
            import shutil
            shutil.rmtree(child)
        calls = []

        def fake_run(command, cwd, timeout=1800):
            calls.append((command, cwd))
            if command == ["lake", "update"]:
                (packages / "mathlib").mkdir(parents=True)
            return ""

        with mock.patch.object(prepare_deps, "_run", side_effect=fake_run), \
             mock.patch.object(prepare_deps, "validate_prepared_packages", return_value=packages):
            prepare_deps._ensure_prepared_packages(self.fixture.problem, validate_lock=True)

        self.assertEqual(calls[0], (["lake", "update"], self.fixture.problem))
        self.assertEqual(
            calls[1],
            (["lake", "exe", "cache", "get", "Mathlib/NumberTheory/PrimeCounting.lean",
              "Mathlib/NumberTheory/ArithmeticFunction/Moebius.lean"],
             packages / "mathlib"),
        )

    def test_targeted_cache_requires_a_mathlib_import(self):
        packages = self.fixture.problem / ".lake/packages"
        (packages / "mathlib").mkdir()
        with mock.patch.object(prepare_deps, "_run"), \
             mock.patch.object(prepare_deps, "validate_prepared_packages", return_value=packages), \
             self.assertRaisesRegex(deps.DependencyError, "no direct Mathlib import"):
            prepare_deps._ensure_prepared_packages(self.fixture.problem, validate_lock=True)

    def test_cold_spec_build_can_create_pinned_package_artifact_roots(self):
        problem = self.fixture.problem
        source_root = problem / ".lake/packages/demoDep/.lake/build/lib/lean"
        self.assertFalse(source_root.exists())
        lock_path = problem / deps.LOCK_NAME
        original_lock = lock_path.read_bytes()

        def build_closure(problem_dir):
            self.assertEqual(problem_dir, problem.resolve())
            self.assertFalse(source_root.exists())
            for relative, payload in self.fixture.artifacts.items():
                source = source_root / relative
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(payload)
            spec = problem / ".lake/build/lib/lean/Spec.olean"
            spec.parent.mkdir(parents=True)
            spec.write_bytes(b"spec root")
            core = Path(self.temp.name) / "lean-core"
            core.mkdir()
            return [("Spec", spec), ("Demo.Basic", source_root / "Demo/Basic.olean")], core

        with mock.patch.object(prepare_deps, "_ensure_prepared_packages"), \
             mock.patch.object(prepare_deps, "_closure", side_effect=build_closure) as closure:
            lock = prepare_deps.prepare_problem(problem)

        closure.assert_called_once_with(problem.resolve())
        self.assertEqual(lock, self.fixture.lock)
        self.assertEqual(lock_path.read_bytes(), original_lock)
        bundle = problem / deps.BUNDLE_LIB
        self.assertEqual(bundle.stat().st_mode & 0o777, 0o755)
        for directory in (path for path in bundle.rglob("*") if path.is_dir()):
            self.assertEqual(directory.stat().st_mode & 0o777, 0o755, directory)
        for relative, payload in self.fixture.artifacts.items():
            artifact = bundle / relative
            self.assertEqual(artifact.read_bytes(), payload)
            self.assertEqual(artifact.stat().st_mode & 0o777, 0o444, artifact)

    def test_post_build_roots_still_reject_modules_outside_pinned_packages(self):
        problem = self.fixture.problem
        source_root = problem / ".lake/packages/demoDep/.lake/build/lib/lean"
        source_root.mkdir(parents=True)
        escaped = Path(self.temp.name) / "unapproved/External.olean"
        escaped.parent.mkdir()
        escaped.write_bytes(b"unapproved module")
        core = Path(self.temp.name) / "lean-core"
        core.mkdir()

        with mock.patch.object(prepare_deps, "_ensure_prepared_packages"), \
             mock.patch.object(prepare_deps, "_closure", return_value=([("External", escaped)], core)), \
             self.assertRaisesRegex(deps.DependencyError, "escaped the approved package/core roots"):
            prepare_deps.prepare_problem(problem)

        for relative, payload in self.fixture.artifacts.items():
            self.assertEqual((problem / deps.BUNDLE_LIB / relative).read_bytes(), payload)

    def test_docker_checks_full_dependency_staging_as_nonroot_judge(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        gates = [match for match in re.finditer(r"(?m)^\s*python3 -c '([^']+)'", dockerfile)
                 if "stage_problem_dependencies(" in match.group(1)]
        self.assertEqual(len(gates), 1)
        gate = gates[0]
        users = re.findall(r"(?m)^USER\s+(\S+)\s*$", dockerfile[:gate.start()])
        self.assertTrue(users)
        self.assertEqual(users[-1], "judge")
        self.assertIn('Path("evaluation/problems") / sys.argv[1]', gate.group(1))
        self.assertIn('RUN for problem in fib mertens primecount; do', dockerfile[:gate.start()])
        self.assertIn('"$problem" || exit 1', dockerfile[gate.end():])
        self.assertIn("tempfile.TemporaryDirectory()", gate.group(1))
        self.assertIn("result.artifact_count", gate.group(1))

    def test_image_and_setup_prepare_all_dependency_enabled_problems(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        setup = (ROOT / "scripts/setup.sh").read_text()
        self.assertIn("RUN python3 scripts/prepare_problem_dependencies.py \\\n", dockerfile)
        self.assertIn('python3 "$HERE/scripts/prepare_problem_dependencies.py"\n', setup)
        for problem in ("fib", "mertens", "primecount"):
            self.assertIn(f"/evaluation/problems/{problem}/.lake/packages", dockerfile)


if __name__ == "__main__":
    unittest.main()
