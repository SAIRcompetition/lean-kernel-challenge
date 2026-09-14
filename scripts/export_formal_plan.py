#!/usr/bin/env python3
"""Export a private, sealed candidate for an eight-problem official evaluation.

This prepares data only. It neither freezes submissions nor contacts a service,
executes Lean, verifies a Docker image, or establishes host acceptance.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from problem_layout import EVALUATION_PROBLEMS, evaluation_problem_dir
from problem_dependencies import specification_fingerprint

SCHEMA = "formal-plan-export-v1"
MAX_PREPARE_BYTES = 8 * 1024 * 1024


class PreparationError(Exception):
    """An operator-facing error that contains no seed, inputs, or answers."""


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def verify_checkout(revision):
    """Require committed source, including every file the problem digest reads."""
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise PreparationError("--revision must be a full lowercase Git commit SHA")

    def git(*args):
        # Do not expose Git stderr or arbitrary paths in an operator error.
        return subprocess.check_output(["git", "-C", str(ROOT), *args],
                                       stderr=subprocess.DEVNULL)

    try:
        if Path(os.fsdecode(git("rev-parse", "--show-toplevel")).strip()).resolve() != ROOT:
            raise PreparationError("run the exporter from an exact repository checkout")
        if git("rev-parse", "HEAD").decode().strip() != revision:
            raise PreparationError("--revision does not match this checkout's HEAD")
        if git("status", "--porcelain", "--untracked-files=no"):
            raise PreparationError("the checkout has tracked changes; commit or use a clean checkout")
        tracked = {os.fsdecode(p) for p in git("ls-files", "-z").split(b"\0") if p}
        for problem in sorted(EVALUATION_PROBLEMS):
            base = evaluation_problem_dir(ROOT, problem)
            dependency_enabled = (base / "dependency-lock.json").is_file()
            if not base.is_dir():
                raise PreparationError(f"missing evaluator workspace for {problem}")
            for path in base.rglob("*"):
                rel = path.relative_to(base)
                if (".lake" in rel.parts or rel.as_posix() == "Submission.lean"
                        or (rel.as_posix() == "lake-manifest.json" and not dependency_enabled)):
                    continue
                if path.is_symlink() or (path.is_file()
                        and path.relative_to(ROOT).as_posix() not in tracked):
                    raise PreparationError(f"the evaluator workspace for {problem} is not a clean Git snapshot")
        if "scripts/export_formal_plan.py" not in tracked:
            raise PreparationError("the exporter must be part of the selected commit")
    except subprocess.SubprocessError:
        raise PreparationError("cannot verify the repository checkout with Git") from None


def load_official_judge(args):
    """Load the canonical builder without inheriting development overrides."""
    for key in tuple(os.environ):
        if (key.startswith("EVALUATION_") or key in {
                "PERF_COUNT", "PERF_SEED", "PERF_SEED_STDIN", "REFERENCE_ANSWERS_STDIN",
                "TIMING_TIMEOUT_SECONDS", "TIMING_METRIC", "OFFICIAL_EVAL", "SANDBOX_MODE",
                "DEFER_TIMING", "TIMING_EXECUTOR_URLS", "TIMING_EXECUTOR_SECRET",
                "SAIR_PROGRESS_FILE"}):
            os.environ.pop(key, None)
    os.environ.update({
        "OFFICIAL_EVAL": "1", "TIMING_METRIC": "perf_instructions", "SANDBOX_MODE": "container",
        "PERF_SEED_STDIN": "1", "EVALUATION_COHORT": args.cohort,
        "EVALUATION_IMAGE": args.image_id, "EVALUATION_MEMORY": "4096m",
        "EVALUATION_CPUS": "2", "EVALUATION_PIDS_LIMIT": "512",
        "EVALUATION_EXECUTOR_ID": args.executor_id,
        "EVALUATION_EXECUTOR_VERSION": args.executor_version,
    })
    sys.path.insert(0, str(ROOT / "evaluation" / "judge"))
    spec = importlib.util.spec_from_file_location(
        "formal_plan_judge", ROOT / "evaluation" / "judge" / "judge.py")
    judge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(judge)
    return judge


def prepare_export(judge, revision):
    """Use the same plan, reference seal, policy, and validator as the judge."""
    answers = {}
    policies = {}
    records = {}
    scorer = judge._canonical_scorer()
    for problem in sorted(EVALUATION_PROBLEMS):
        try:
            problem_dir = evaluation_problem_dir(ROOT, problem)
            cfg = json.loads((problem_dir / "config.json").read_text())
            plan = judge._validated_performance_plan(cfg, problem)
            inputs = [case["n"] for case in plan]
            spec_digest = specification_fingerprint(problem_dir)
            bundle = judge.reference_answers.prepare(problem, inputs, spec_digest)
            judge.EVALUATION_RESOURCE_POLICY["memory"] = f"{judge.problem_memory_mb(cfg)}m"
            cohort = judge._evaluation_cohort(
                problem, cfg, inputs, judge.DEFAULT_REPS, {"timing_protocol": "local-v2"},
                performance_plan=plan, reference_bundle=bundle)
            policy = cohort["policy"]
            if scorer._policy_shape_error(policy) is not None:
                raise PreparationError(f"canonical official policy validation failed for {problem}")
            policies[problem] = policy
            answers[problem] = bundle
            records[problem] = {
                "cohort_id": cohort["id"], "policy_sha256": cohort["policy_sha256"],
                "problem_bundle_sha256": policy["problem_bundle_sha256"],
                "performance_plan_sha256": policy["performance_plan_sha256"],
                "reference_answers": policy["reference_answers"],
            }
        except PreparationError:
            raise
        except Exception:
            # Internal exceptions may mention hidden n or an answer. Do not log them.
            raise PreparationError(f"canonical preparation failed for {problem}") from None
    prepare = {"cohortId": judge.EVALUATION_COHORT, "seed": judge.PERF_SEED, "policies": policies}
    payload = canonical_bytes(prepare)
    if len(payload) > MAX_PREPARE_BYTES:
        raise PreparationError("the prepared request exceeds the service's 8 MiB request limit")
    first_policy = policies[sorted(policies)[0]]
    return {
        "schema": SCHEMA,
        "prepare": prepare,
        "reference_answers": answers,
        "provenance": {
            "source_revision": revision,
            "image_id": first_policy["resource_policy"]["image"],
            "executor": first_policy["executor"],
            "toolchain": first_policy["toolchain"],
            "checker": first_policy["checker"],
            "timing_protocol": first_policy["timing_protocol"],
            "evaluator_bundle_sha256": first_policy["evaluator_bundle_sha256"],
            "prepare_sha256": hashlib.sha256(payload).hexdigest(),
            "problems": records,
        },
    }


def publish_private(path, payload):
    """Publish a complete regular file atomically, without replacing any entry."""
    fd, temporary = tempfile.mkstemp(prefix=".formal-plan-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            os.fchmod(out.fileno(), 0o600)
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        # A hard link creates the destination exclusively (including against symlinks).
        # Both names are in the same directory/filesystem, so there is no partial copy.
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True, help="full commit SHA of this clean host checkout")
    parser.add_argument("--cohort", required=True, help="round label, identical to the service cohortId")
    parser.add_argument("--image-id", required=True, help="verified Docker image ID, sha256:<64 hex>")
    parser.add_argument("--executor-id", required=True, help="configured, accepted PMU executor identity")
    parser.add_argument("--executor-version", required=True, help="configured, accepted executor version")
    parser.add_argument("--output", required=True, type=Path,
                        help="new private JSON file; parent must exist, destination must not exist")
    args = parser.parse_args()
    try:
        if re.fullmatch(r"sha256:[0-9a-f]{64}", args.image_id) is None:
            raise PreparationError("--image-id must be an immutable sha256 image ID")
        if (not args.executor_id.strip() or args.executor_id == "local"
                or not args.executor_version.strip() or args.executor_version == "fixed-host"):
            raise PreparationError("supply the actual executor identity and version; defaults are not accepted")
        if any(len(value) > 256 or "\n" in value or "\x00" in value
               for value in (args.executor_id, args.executor_version)):
            raise PreparationError("executor identity and version must each fit one line of at most 256 characters")
        if (re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", args.cohort) is None
                or args.cohort in (".", "..")):
            raise PreparationError("--cohort must be a valid round slug")
        if os.path.lexists(args.output):
            raise PreparationError("the output already exists; it will not be overwritten")
        if not args.output.parent.is_dir():
            raise PreparationError("the output parent directory must already exist")
        parent = args.output.parent.resolve()
        if parent == ROOT or ROOT in parent.parents:
            raise PreparationError("the private output must be outside the repository checkout")
        verify_checkout(args.revision)
        judge = load_official_judge(args)
        try:
            judge._consume_perf_seed_stdin()
            if sys.stdin.buffer.read(1):
                raise PreparationError("stdin must contain exactly one newline-terminated seed record")
        except judge.InfraError:
            raise PreparationError("stdin must be one nonempty UTF-8 seed record of at most 1024 bytes, without NUL") from None
        result = prepare_export(judge, args.revision)
        # Recheck before publishing in case source was edited during preparation.
        verify_checkout(args.revision)
        publish_private(args.output, canonical_bytes(result))
    except PreparationError as exc:
        parser.exit(2, f"Formal plan preparation failed: {exc}\n")
    except Exception:
        # Paths, decoding exceptions, and internal values can be private as well.
        parser.exit(2, "Formal plan preparation failed; inspect the private output before retrying.\n")
    print(f"Prepared sealed candidate for {len(EVALUATION_PROBLEMS)} problems; no service state changed.")


if __name__ == "__main__":
    main()
