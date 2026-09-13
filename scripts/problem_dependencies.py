#!/usr/bin/env python3
"""Pinned, problem-scoped Lean dependency bundles.

The source Lake lock remains the canonical dependency record.  Evaluation does
not expose a package checkout to untrusted elaboration: an offline preparation
step walks the locked Spec's compiled import graph and creates a small flattened
artifact library under ``.lake/dependency-bundle/lib/lean``.  This module
validates and stages that library without running Lean or participant code.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil


LOCK_NAME = "dependency-lock.json"
BUNDLE_LIB = Path(".lake/dependency-bundle/lib/lean")
SCHEMA = "lean-problem-dependencies-v1"
ARTIFACT_SUFFIXES = (".olean", ".olean.private", ".olean.server", ".ir.sig", ".ir")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REV = re.compile(r"[0-9a-f]{40}")


class DependencyError(ValueError):
    """A dependency lock, package checkout, or prepared bundle is invalid."""


@dataclass(frozen=True)
class DependencyStage:
    fingerprint: str
    artifact_count: int
    artifact_bytes: int


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_bytes(path: Path, description: str) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise DependencyError(f"{description} is missing or is not a regular file: {path}")
        return path.read_bytes()
    except OSError as exc:
        raise DependencyError(f"cannot read {description} {path}: {exc}") from exc


def _load_json(path: Path, description: str) -> tuple[dict, bytes]:
    payload = _read_bytes(path, description)
    try:
        value = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DependencyError(f"invalid {description} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DependencyError(f"{description} must be a JSON object: {path}")
    return value, payload


def _safe_artifact_path(value: object) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise DependencyError(f"invalid dependency artifact path: {value!r}")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise DependencyError(f"dependency artifact path escapes its bundle: {value!r}")
    if not any(value.endswith(suffix) for suffix in ARTIFACT_SUFFIXES):
        raise DependencyError(f"unsupported dependency artifact suffix: {value!r}")
    return path


def load_dependency_lock(problem_dir: Path) -> tuple[dict, bytes] | None:
    """Load and structurally validate a problem lock, or return ``None``."""
    problem_dir = Path(problem_dir)
    lock_path = problem_dir / LOCK_NAME
    if not lock_path.exists() and not lock_path.is_symlink():
        return None
    lock, payload = _load_json(lock_path, "dependency lock")
    required = {
        "schema", "toolchain", "source", "root_modules", "packages",
        "runtime_lakefile_sha256", "artifacts", "bundle_sha256",
    }
    if set(lock) != required or lock.get("schema") != SCHEMA:
        raise DependencyError(f"dependency lock has an unsupported shape or schema: {lock_path}")
    if not isinstance(lock["toolchain"], str) or not lock["toolchain"]:
        raise DependencyError("dependency lock has no toolchain pin")
    if (not isinstance(lock["root_modules"], list) or not lock["root_modules"]
            or any(not isinstance(x, str) or not x for x in lock["root_modules"])):
        raise DependencyError("dependency lock has invalid root_modules")
    if not isinstance(lock["packages"], list) or not lock["packages"]:
        raise DependencyError("dependency lock has no packages")
    if not _SHA256.fullmatch(str(lock["runtime_lakefile_sha256"])):
        raise DependencyError("dependency lock has an invalid runtime lakefile digest")
    if not _SHA256.fullmatch(str(lock["bundle_sha256"])):
        raise DependencyError("dependency lock has an invalid bundle digest")

    source = lock["source"]
    if (not isinstance(source, dict)
            or set(source) != {"lakefile_sha256", "manifest_sha256"}
            or any(not _SHA256.fullmatch(str(value)) for value in source.values())):
        raise DependencyError("dependency lock has invalid source digests")

    package_names = set()
    for package in lock["packages"]:
        if (not isinstance(package, dict) or set(package) != {"name", "url", "rev"}
                or not isinstance(package["name"], str) or not package["name"]
                or package["name"] in package_names
                or not isinstance(package["url"], str) or not package["url"]
                or not _REV.fullmatch(str(package["rev"]))):
            raise DependencyError("dependency lock contains an invalid package pin")
        package_names.add(package["name"])

    artifacts = lock["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise DependencyError("dependency lock has no artifacts")
    previous = None
    for artifact in artifacts:
        if (not isinstance(artifact, dict) or set(artifact) != {"path", "sha256", "size"}
                or not _SHA256.fullmatch(str(artifact["sha256"]))
                or type(artifact["size"]) is not int or artifact["size"] < 0):
            raise DependencyError("dependency lock contains an invalid artifact record")
        path = _safe_artifact_path(artifact["path"]).as_posix()
        if previous is not None and path <= previous:
            raise DependencyError("dependency artifacts must be unique and sorted by path")
        previous = path
    if _bundle_digest(artifacts) != lock["bundle_sha256"]:
        raise DependencyError("dependency lock bundle digest does not match its artifact records")
    return lock, payload


def _lakefile_declares_dependencies(problem_dir: Path) -> bool:
    lakefile = problem_dir / "lakefile.toml"
    try:
        return "[[require]]" in lakefile.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DependencyError(f"cannot inspect canonical lakefile {lakefile}: {exc}") from exc


def _strip_require_blocks(source: str) -> str:
    """Derive the package-free runtime TOML used with the flattened artifact lib."""
    lines = source.splitlines(keepends=True)
    output: list[str] = []
    skipping = False
    found = False
    for line in lines:
        if re.fullmatch(r"\s*\[\[require\]\]\s*(?:#.*)?(?:\r?\n)?", line):
            skipping = True
            found = True
            continue
        if skipping and re.match(r"\s*\[", line):
            skipping = False
        if not skipping:
            output.append(line)
    if not found:
        raise DependencyError("dependency-enabled lakefile.toml contains no [[require]] block")
    runtime = "".join(output)
    if "[[require]]" in runtime:
        raise DependencyError("could not derive a package-free runtime lakefile")
    return runtime


def runtime_lakefile(problem_dir: Path, lock: dict | None = None) -> bytes:
    """Validate canonical source locks and return the derived runtime lakefile."""
    problem_dir = Path(problem_dir)
    if lock is None:
        loaded = load_dependency_lock(problem_dir)
        if loaded is None:
            raise DependencyError(f"problem has no {LOCK_NAME}: {problem_dir}")
        lock = loaded[0]
    lakefile = _read_bytes(problem_dir / "lakefile.toml", "canonical lakefile")
    manifest = _read_bytes(problem_dir / "lake-manifest.json", "canonical Lake manifest")
    if _sha256_bytes(lakefile) != lock["source"]["lakefile_sha256"]:
        raise DependencyError("canonical lakefile does not match dependency lock")
    if _sha256_bytes(manifest) != lock["source"]["manifest_sha256"]:
        raise DependencyError("canonical Lake manifest does not match dependency lock")
    toolchain = _read_bytes(problem_dir / "lean-toolchain", "Lean toolchain").decode().strip()
    if toolchain != lock["toolchain"]:
        raise DependencyError("Lean toolchain does not match dependency lock")
    try:
        runtime = _strip_require_blocks(lakefile.decode("utf-8")).encode("utf-8")
    except UnicodeError as exc:
        raise DependencyError(f"canonical lakefile is not UTF-8: {exc}") from exc
    if _sha256_bytes(runtime) != lock["runtime_lakefile_sha256"]:
        raise DependencyError("derived runtime lakefile does not match dependency lock")
    return runtime


def validate_prepared_packages(problem_dir: Path, *, validate_lock: bool = True) -> Path:
    """Validate exact git revisions in ``.lake/packages`` and return that path.

    This is for trusted dependency preparation. Evaluation
    uses :func:`stage_problem_dependencies` and never exposes package checkouts.
    """
    problem_dir = Path(problem_dir)
    manifest, _ = _load_json(problem_dir / "lake-manifest.json", "Lake manifest")
    loaded = load_dependency_lock(problem_dir) if validate_lock else None
    if loaded is not None:
        # This validates the canonical lakefile, manifest, and toolchain digests as well as the
        # deterministic package-free derivation before a caller lets Lake inspect the checkout.
        runtime_lakefile(problem_dir, loaded[0])
    expected = loaded[0]["packages"] if loaded is not None else None
    if manifest.get("packagesDir") != ".lake/packages":
        raise DependencyError("Lake manifest packagesDir must be .lake/packages")
    packages = manifest.get("packages")
    if not isinstance(packages, list) or not packages:
        raise DependencyError("Lake manifest has no pinned packages")
    manifest_pins = []
    for item in packages:
        if (not isinstance(item, dict) or not isinstance(item.get("name"), str)
                or not isinstance(item.get("url"), str)
                or not _REV.fullmatch(str(item.get("rev", "")))):
            raise DependencyError("Lake manifest contains an unpinned package")
        manifest_pins.append({"name": item["name"], "url": item["url"], "rev": item["rev"]})
    if expected is not None and manifest_pins != expected:
        raise DependencyError("Lake manifest package pins do not match dependency lock")

    packages_dir = problem_dir / ".lake" / "packages"
    for package in manifest_pins:
        checkout = packages_dir / package["name"]
        git_dir = checkout / ".git"
        if checkout.is_symlink() or not checkout.is_dir() or not git_dir.exists():
            raise DependencyError(f"prepared package checkout is missing: {package['name']}")
        import subprocess
        proc = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            text=True, capture_output=True, check=False,
        )
        if proc.returncode != 0 or proc.stdout.strip() != package["rev"]:
            raise DependencyError(f"prepared package revision mismatch: {package['name']}")
    return packages_dir


def _bundle_digest(records: list[dict]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(record["path"].encode() + b"\0")
        digest.update(record["sha256"].encode() + b"\0")
        digest.update(str(record["size"]).encode() + b"\0")
    return digest.hexdigest()


def stage_problem_dependencies(problem_dir: Path, workspace: Path) -> DependencyStage | None:
    """Verify and copy a prepared dependency closure into a disposable workspace."""
    problem_dir, workspace = Path(problem_dir), Path(workspace)
    loaded = load_dependency_lock(problem_dir)
    if loaded is None:
        if _lakefile_declares_dependencies(problem_dir):
            raise DependencyError(
                f"dependency-enabled problem is missing its trusted {LOCK_NAME}: {problem_dir}"
            )
        return None
    lock, lock_bytes = loaded
    runtime = runtime_lakefile(problem_dir, lock)
    bundle = problem_dir / BUNDLE_LIB
    if bundle.is_symlink() or not bundle.is_dir():
        raise DependencyError(
            f"prepared dependency bundle is missing; run scripts/prepare_problem_dependencies.py --problem {problem_dir.name}"
        )

    expected_paths = {record["path"] for record in lock["artifacts"]}
    actual_paths = set()
    for path in bundle.rglob("*"):
        if path.is_symlink():
            raise DependencyError(f"prepared dependency bundle contains a symlink: {path}")
        if path.is_file():
            actual_paths.add(path.relative_to(bundle).as_posix())
    if actual_paths != expected_paths:
        raise DependencyError("prepared dependency bundle file set does not match dependency lock")

    destination = workspace / ".lake" / "build" / "lib" / "lean"
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    for record in lock["artifacts"]:
        relative = _safe_artifact_path(record["path"])
        source = bundle / relative
        payload = _read_bytes(source, "prepared dependency artifact")
        if len(payload) != record["size"] or _sha256_bytes(payload) != record["sha256"]:
            raise DependencyError(f"prepared dependency artifact does not match lock: {relative}")
        target = destination / relative
        if target.exists() or target.is_symlink():
            raise DependencyError(f"dependency artifact collides with workspace file: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write the exact bytes just verified.  Reopening a mutable local preparation cache for a
        # second copy operation would create a verify/copy race on development hosts.
        target.write_bytes(payload)
        target.chmod(0o444)
        total += len(payload)

    (workspace / "lakefile.toml").write_bytes(runtime)
    (workspace / "lake-manifest.json").unlink(missing_ok=True)
    return DependencyStage(
        fingerprint=_sha256_bytes(lock_bytes),
        artifact_count=len(lock["artifacts"]),
        artifact_bytes=total,
    )


def specification_fingerprint(problem_dir: Path) -> str:
    """Reference-answer fingerprint, dependency-aware with legacy compatibility."""
    problem_dir = Path(problem_dir)
    spec = _read_bytes(problem_dir / "Spec.lean", "problem specification")
    loaded = load_dependency_lock(problem_dir)
    if loaded is None:
        if _lakefile_declares_dependencies(problem_dir):
            raise DependencyError(
                f"dependency-enabled problem is missing its trusted {LOCK_NAME}: {problem_dir}"
            )
        return _sha256_bytes(spec)
    lock, lock_bytes = loaded
    # Validate the canonical Lake/toolchain inputs before binding their lock.
    runtime_lakefile(problem_dir, lock)
    digest = hashlib.sha256()
    for name, payload in (("Spec.lean", spec), (LOCK_NAME, lock_bytes)):
        digest.update(name.encode() + b"\0" + payload + b"\0")
    return digest.hexdigest()
