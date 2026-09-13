#!/usr/bin/env python3
"""Prepare pinned, flattened import-closure bundles for dependency-enabled problems."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from problem_dependencies import (  # noqa: E402
    ARTIFACT_SUFFIXES,
    BUNDLE_LIB,
    LOCK_NAME,
    SCHEMA,
    DependencyError,
    _bundle_digest,
    _strip_require_blocks,
    validate_prepared_packages,
)
from problem_layout import evaluation_problem_dir, iter_evaluation_problem_dirs


_CLOSURE_READER = r'''
import Lean

open Lean

partial def walk (todo : List (Name × System.FilePath))
    (seen : Std.HashSet String := {})
    (regions : Array CompactedRegion := #[]) : IO Unit := do
  match todo with
  | [] => pure ()
  | (name, path) :: rest =>
    let key := path.toString
    if seen.contains key then
      walk rest seen regions
    else
      IO.println s!"{name}\t{path}"
      let (data, region) ← Lean.readModuleData path
      let mut children := #[]
      for imported in data.imports do
        children := children.push (imported.module, ← Lean.findOLean imported.module)
      -- ModuleData names may point into compacted storage. Retain every region for the complete
      -- traversal instead of relying on the lifetime of this stack frame.
      walk (children.toList ++ rest) (seen.insert key) (regions.push region)

def main (args : List String) : IO UInt32 := do
  match args with
  | [module, path] =>
    walk [(module.toName, path)]
    return 0
  | _ =>
    IO.eprintln "expected MODULE OLEAN"
    return 2
'''


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _direct_imports(spec: Path) -> list[str]:
    imports = []
    pattern = re.compile(
        r"^\s*(?:public\s+)?import(?:\s+all)?\s+([A-Za-z_][A-Za-z0-9_'.]*)\s*(?:--.*)?$"
    )
    for line in spec.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            imports.append(match.group(1))
    if not imports:
        raise DependencyError("Spec.lean has no supported dependency import")
    return imports


def _clean_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT", "ELAN_TOOLCHAIN"):
        environment.pop(name, None)
    environment["MATHLIB_NO_CACHE_ON_UPDATE"] = "1"
    return environment


def _run(command: list[str], cwd: Path, timeout: int = 1800) -> str:
    proc = subprocess.run(
        command, cwd=cwd, env=_clean_environment(), text=True, capture_output=True, timeout=timeout
    )
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout, proc.stderr))[-4000:]
        raise DependencyError(f"command failed ({' '.join(command)}):\n{tail}")
    return proc.stdout


def _package_pins(problem_dir: Path) -> list[dict]:
    manifest = json.loads((problem_dir / "lake-manifest.json").read_text())
    return [
        {"name": item["name"], "url": item["url"], "rev": item["rev"]}
        for item in manifest["packages"]
    ]


def _ensure_prepared_packages(problem_dir: Path, *, validate_lock: bool) -> None:
    """Fetch exact manifest pins and the targeted Mathlib cache on trusted setup hosts."""
    manifest = json.loads((problem_dir / "lake-manifest.json").read_text())
    packages = manifest.get("packages", [])
    missing = any(
        not (problem_dir / ".lake/packages" / item.get("name", "") / ".git").exists()
        for item in packages if isinstance(item, dict)
    )
    if missing:
        _run(["lake", "update"], problem_dir)
    validate_prepared_packages(problem_dir, validate_lock=validate_lock)
    # This cache target is deliberately problem-scoped. It downloads the compiled import closure
    # needed by the locked spec without materializing Mathlib's complete multi-gigabyte cache.
    mathlib_dir = problem_dir / ".lake/packages/mathlib"
    if not mathlib_dir.is_dir():
        raise DependencyError("prepared Mathlib checkout is missing")
    _run(["lake", "exe", "cache", "get", "Mathlib/Data/Nat/Fib/Basic.lean"], mathlib_dir)


def _artifact_roots(problem_dir: Path, packages: list[dict]) -> list[Path]:
    roots = []
    for package in packages:
        root = problem_dir / ".lake/packages" / package["name"] / ".lake/build/lib/lean"
        if root.is_dir() and not root.is_symlink():
            roots.append(root.resolve())
    return roots


def _relative_to_one(path: Path, roots: list[Path]) -> Path | None:
    resolved = path.resolve(strict=True)
    for root in roots:
        try:
            return resolved.relative_to(root)
        except ValueError:
            pass
    return None


def _closure(problem_dir: Path) -> tuple[list[tuple[str, Path]], Path]:
    _run(["lake", "--no-cache", "build", "Spec"], problem_dir)
    spec_olean = problem_dir / ".lake/build/lib/lean/Spec.olean"
    if not spec_olean.is_file():
        raise DependencyError("lake build Spec produced no Spec.olean")
    with tempfile.TemporaryDirectory(prefix="lkc-dependency-reader-") as raw:
        reader = Path(raw) / "DependencyClosure.lean"
        reader.write_text(_CLOSURE_READER, encoding="utf-8")
        output = _run(
            ["lake", "env", "lean", "--run", str(reader), "Spec", str(spec_olean.resolve())],
            problem_dir,
        )
    result = []
    for line in output.splitlines():
        if "\t" not in line:
            continue
        module, raw_path = line.split("\t", 1)
        path = Path(raw_path)
        if not module or not path.is_absolute() or not path.is_file():
            raise DependencyError(f"invalid module closure record: {line!r}")
        result.append((module, path))
    if not result or result[0][0] != "Spec":
        raise DependencyError("Lean closure reader returned no Spec root")
    core_lib = Path(_run(["lake", "env", "lean", "--print-libdir"], problem_dir).strip())
    if not core_lib.is_absolute() or not core_lib.is_dir():
        raise DependencyError(f"Lean returned an invalid core library path: {core_lib}")
    return result, core_lib.resolve()


def prepare_problem(problem_dir: Path, *, refresh_lock: bool = False) -> dict:
    problem_dir = problem_dir.resolve()
    existing_lock = problem_dir / LOCK_NAME
    if not existing_lock.is_file() and not refresh_lock:
        raise DependencyError(
            f"{LOCK_NAME} is missing; maintainers must create it with --refresh-lock"
        )
    _ensure_prepared_packages(problem_dir, validate_lock=not refresh_lock)
    packages_dir = validate_prepared_packages(problem_dir, validate_lock=not refresh_lock)
    del packages_dir  # validated source only; it is never copied into the evaluation bundle
    packages = _package_pins(problem_dir)
    # A cold Spec build may create artifact directories for pinned transitive packages.
    # Enumerate their approved roots only after that build has completed.
    closure, core_lib = _closure(problem_dir)
    roots = _artifact_roots(problem_dir, packages)
    if not roots:
        raise DependencyError("no prepared package artifact roots were found")

    selected: dict[str, Path] = {}
    spec_olean = (problem_dir / ".lake/build/lib/lean/Spec.olean").resolve()
    for module, olean in closure:
        relative = _relative_to_one(olean, roots)
        if relative is None:
            resolved = olean.resolve(strict=True)
            try:
                resolved.relative_to(core_lib)
                is_core = True
            except ValueError:
                is_core = False
            if (module == "Spec" and resolved == spec_olean) or is_core:
                # The Spec root is rebuilt in each workspace; Lean core comes from lean-toolchain.
                continue
            raise DependencyError(
                f"module closure escaped the approved package/core roots: {module} ({olean})"
            )
        if relative.suffix != ".olean":
            raise DependencyError(f"closure reader returned a non-olean artifact: {olean}")
        stem = Path(str(olean)[:-len(".olean")])
        for suffix in ARTIFACT_SUFFIXES:
            companion = Path(str(stem) + suffix)
            if not companion.is_file():
                continue
            companion_relative = _relative_to_one(companion, roots)
            if companion_relative is None:
                raise DependencyError(f"dependency companion escaped package roots: {companion}")
            key = companion_relative.as_posix()
            prior = selected.get(key)
            if prior is not None and prior.resolve() != companion.resolve():
                raise DependencyError(f"two packages provide dependency artifact {key}")
            selected[key] = companion
    if not selected:
        raise DependencyError("the Spec import closure contains no package artifacts")

    records = []
    for relative, source in sorted(selected.items()):
        records.append({"path": relative, "sha256": _sha256(source), "size": source.stat().st_size})

    lakefile = problem_dir / "lakefile.toml"
    manifest = problem_dir / "lake-manifest.json"
    runtime = _strip_require_blocks(lakefile.read_text(encoding="utf-8")).encode()
    lock = {
        "schema": SCHEMA,
        "toolchain": (problem_dir / "lean-toolchain").read_text().strip(),
        "source": {"lakefile_sha256": _sha256(lakefile), "manifest_sha256": _sha256(manifest)},
        "root_modules": _direct_imports(problem_dir / "Spec.lean"),
        "packages": packages,
        "runtime_lakefile_sha256": hashlib.sha256(runtime).hexdigest(),
        "artifacts": records,
        "bundle_sha256": _bundle_digest(records),
    }

    lock_path = problem_dir / LOCK_NAME
    if not refresh_lock:
        try:
            canonical = json.loads(lock_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise DependencyError(f"cannot read existing dependency lock: {exc}") from exc
        if canonical != lock:
            raise DependencyError(
                "prepared closure differs from dependency-lock.json; refusing to rewrite the "
                "trusted lock (maintainers may review and use --refresh-lock)"
            )
        lock = canonical

    # Only replace a usable prepared bundle after the recomputed closure has matched the trusted
    # lock (or the caller explicitly selected the maintainer refresh operation).
    bundle = problem_dir / BUNDLE_LIB
    bundle_parent = bundle.parent
    bundle_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dependency-bundle-", dir=bundle_parent) as raw:
        staged = Path(raw)
        for relative, source in sorted(selected.items()):
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(0o444)
        # TemporaryDirectory starts at 0700. The root-built image must let the
        # non-root judge traverse the published bundle without making it writable.
        for directory, _, _ in os.walk(staged):
            Path(directory).chmod(0o755)
        if bundle.exists():
            shutil.rmtree(bundle)
        os.replace(staged, bundle)
    if refresh_lock:
        temporary_lock = lock_path.with_suffix(".json.tmp")
        temporary_lock.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary_lock, lock_path)
    return lock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", action="append",
                        help="problem id; default: every problem with dependency-lock.json")
    parser.add_argument(
        "--refresh-lock", action="store_true",
        help="maintainer action: replace dependency-lock.json after reviewing a pin/closure change",
    )
    parser.add_argument(
        "--skip-native-warmup", action="store_true",
        help=argparse.SUPPRESS,  # backwards-compatible no-op; participant builds are independent
    )
    args = parser.parse_args(argv)
    if args.problem:
        names = args.problem
    else:
        names = [path.name for path in iter_evaluation_problem_dirs(ROOT)
                 if (path / LOCK_NAME).is_file()]
    if not names:
        parser.error("no dependency-enabled problems found; pass --problem")
    try:
        for name in names:
            problem_dir = evaluation_problem_dir(ROOT, name)
            if not problem_dir.is_dir():
                raise DependencyError(f"unknown problem: {name}")
            lock = prepare_problem(problem_dir, refresh_lock=args.refresh_lock)
            total = sum(item["size"] for item in lock["artifacts"])
            print(f"Prepared {name}: {len(lock['artifacts'])} artifacts, {total} bytes.")
        return 0
    except (DependencyError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f"Dependency preparation failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
