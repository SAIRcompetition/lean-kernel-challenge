#!/usr/bin/env python3
"""Lean Kernel Challenge judge.

Pipeline per submission (each contestant job runs in a unique temp workspace):
  1. Validate + assemble: copy the locked problem template, then overlay the contestant's single
     Submission.lean. The file is re-audited ON THE ASSEMBLED
     tree (regular files, no symlinks, size/count caps, containment) to close the
     validate-then-copy TOCTOU window.
  2. Correctness gate: run comparator (statement match, axiom whitelist, kernel replay of
     the ∀n proof). Sandboxed via landrun on Linux; on macOS the pass-through shim strips
     sandboxing. The SHA-256 of the verified Submission bytes is pinned for step 4.
  3. Axiom re-audit of the comparator-emitted solution export (whitelisted axioms only).
  4. Scored replay: time the comparator-verified correctness export, then for each
     judge-chosen input n reduce `impl n` to a literal v via an elaborator-side oracle, confirm the
     Submission is byte-unchanged from step 2, build+export a uniquely named
     `impl n = v` theorem whose direct proof forces kernel reduction, re-audit THAT export,
     and time the official kernel replaying it, N reps. A too-slow input occupies
     its explicit slot and later slots are still attempted; a deterministic oracle/build/kernel
     fault errors with no score. metric=wall_time (dev) or perf_instructions (Linux host).
     In non-official validation, TIMING_EXECUTOR_URLS runs replays on a remote KTP/3 executor
     with real PMU hardware; each per-input export is uploaded with its SHA-256. An unreachable executor is
     NOT a verdict: the run exits 3 with a "retry" verdict so the caller can requeue losslessly.

Exit codes: 0 = judged (verdict JSON, accepted OR rejected); 2 = infrastructure error;
3 = timing executor unreachable (verdict status "retry" — requeue and try again later).
Every infra failure still writes an error JSON and exits 2, never a traceback.

ISOLATION (not the judge's job): killing EVERY process a submission spawns (incl. setsid
escapes), resource caps, and non-root execution are enforced by the container/cgroup, not
this process — use scripts/run_isolated.sh. The bundled process-group kill and read-only
freeze here are defense in depth, not a security boundary.
"""
import argparse
import collections
import fcntl
import hashlib
import hmac
import importlib.util
import json
import math
import os
import re
import resource
import select
import shutil
import signal
import stat
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Some approved problems produce exact integer answers far beyond Python's
# default int<->str digit cap (4300 on 3.11+). The polydisc reference
# discriminant alone has ~24k digits, and the perf-phase theorem source
# embeds the full value as a Lean nat literal. This judge only ever renders
# oracle-verified values, so lift the cap instead of refusing legitimate
# conversions (Python 3.11+; harmless no-op on older interpreters).
if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)

ROOT = Path(__file__).resolve().parent.parent            # lean-kernel-challenge/
PROBLEMS = ROOT / "problems"
RESULTS = ROOT / "results"

# Judge budgets + timing/sandbox policy live in pipeline/config.json (SAIR convention).
_CFG = json.loads((ROOT / "pipeline" / "config.json").read_text())
_J = _CFG["judge"]
COMPARATOR_TIMEOUT = _J["comparator_timeout_seconds"]
AUDIT_TIMEOUT = _J["audit_timeout_seconds"]
def _int_env(name, default):
    """Positive-integer env override, ignoring junk (dev knobs must never break a real run)."""
    try:
        v = int(os.environ.get(name, ""))
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


# Dev override so the green gate can shrink the budget WITHOUT editing pipeline/config.json —
# hand-editing it risks committing a tiny debug budget into the official configuration.
TIMING_TIMEOUT = _int_env("TIMING_TIMEOUT_SECONDS", _J["timing_timeout_seconds"])
# Legacy-v1 whole-phase ceiling (currently only the experimental ``conv`` schedule).
# Grouped-v2 cases are independently bounded and deliberately do not share this deadline.
# On legacy exhaustion, remaining slots are marked and a normal verdict is emitted.
PERF_PHASE_BUDGET = _J.get("perf_phase_budget_seconds", 10800)
DEFAULT_REPS = _J["timing_reps"]
MAX_SUBMISSION_BYTES = _J["max_submission_bytes"]
MAX_SUBMISSION_FILES = _J["max_submission_files"]
MAX_TOOL_OUTPUT_BYTES = _J.get("max_tool_output_bytes", 1_048_576)
REPLAY_MEMORY_MB = _CFG["sandbox"]["memory_mb"]
REMOTE_PROTOCOL = _CFG["timing"]["remote_protocol"]
# Timing metric + sandbox mode; env overrides let the Docker host switch to perf.
TIMING_METRIC = os.environ.get("TIMING_METRIC", _CFG.get("timing", {}).get("metric", "wall_time"))
SANDBOX_MODE = os.environ.get("SANDBOX_MODE", _CFG.get("sandbox", {}).get("mode", "none"))
OFFICIAL_EVAL = os.environ.get("OFFICIAL_EVAL", "") == "1"
# Playground orchestration may ask this isolated process to stop after it has
# produced, pinned, and audited every export. The trusted host then performs
# the authoritative KTP replay before persisting a terminal verdict. This is
# deliberately forbidden for official evaluation and requires the caller to
# retain the workspace containing those exports.
DEFER_TIMING = os.environ.get("DEFER_TIMING", "") == "1"
# Optional host-owned JSONL stream for live Playground stage progress. The
# service pre-creates this file in the per-run results mount and tails it while
# the container is alive. Official/offline invocations leave it unset.
SAIR_PROGRESS_FILE = os.environ.get("SAIR_PROGRESS_FILE", "")
# Remote timing executor (KTP/3, lean-timer-executor). Comma-separated URLs in
# active-standby order; used only when metric=perf_instructions. The secret is
# the executor's bearer token and never appears in verdicts or logs.
TIMING_EXECUTOR_URLS = [u.strip().rstrip("/") for u in
                        os.environ.get("TIMING_EXECUTOR_URLS", "").split(",") if u.strip()]
TIMING_EXECUTOR_SECRET = os.environ.pop("TIMING_EXECUTOR_SECRET", "")
# Dispatch attempts across the URL list before giving up with a "retry"
# verdict: sleep, then walk every URL again. Short and bounded — long
# outages are the CALLER's requeue loop, not ours.
_EXECUTOR_ATTEMPT_SLEEPS = [0, 10, 30]
# Once one executor serves a point, PIN it for the rest of this submission so a mid-curve
# failover cannot mix PMU data from different machines under one label. If the pinned node
# later goes unreachable, that raises TimingRetry and the whole submission is requeued (never
# silently continued on another node). One judge process = one submission, so this is per-job.
_PINNED_EXECUTOR = [None]
_PINNED_EXECUTOR_IDENTITY = [None]

# Tool locations. Default to the local `repro/` checkout; override via env on the
# Docker/Linux eval host, where the tools are built at fixed image paths.
REPRO = ROOT.parent / "repro"
COMPARATOR = Path(os.environ.get("COMPARATOR_BIN", REPRO / "comparator/.lake/build/bin/comparator"))
LEAN4EXPORT_BIN = Path(os.environ.get("LEAN4EXPORT_BIN", REPRO / "lean4export/.lake/build/bin"))
TIMER = Path(os.environ.get("TIMER_BIN", ROOT / "judge/timer-kernel/.lake/build/bin/kernel"))
# Versioned measurement protocol shared by this judge, timer-kernel, and KTP/3 executors.
# Changing any boundary semantics must change at least one of these strings so the cohort hash
# prevents old and new samples from being ranked together.
MEASUREMENT_CONTRACT = "kernel-replay-v2"
FULL_REPLAY_BOUNDARY = "full-closure-replay-v1"
TARGET_REPLAY_BOUNDARY = "target-declaration-replay-v1"
TARGET_PROOF_ENCODING = "direct-rfl-v1-experimental"
CHECKER_ID = f"official-kernel-replay v4.33.1 ({MEASUREMENT_CONTRACT})"
_TIMER_TIMING_PREFIX = "KERNEL_TIMING="
# The replay memory window (peak_rss_kb) needs procfs, not the PMU: the timer
# measures it exactly when it runs on Linux, so its validation is
# platform-derived rather than metric-derived.
_LINUX = sys.platform.startswith("linux")
# There is no READY/ACK channel in v2. The process watchdog therefore bounds untimed
# parse/dependency preparation plus the measured replay. Record that limitation explicitly
# whenever it fires; a normal nonzero exit remains a deterministic failure, never a timeout.
PROCESS_TIMEOUT_SCOPE = "whole-timer-process-including-untimed-preparation"
# Bundled pass-through shims for `landrun`/`timeout` so the package is self-contained on
# dev machines. Used ONLY when a real `landrun` isn't on PATH (Docker/Linux ships the
# real Landlock sandbox, which must win). See tool_env().
SHIM_DIR = Path(os.environ.get("SHIM_DIR", ROOT / "scripts" / "shims"))

# Kernel-builtin constants comparator always exports alongside the targets.
PRIMITIVES = [
    "Nat.add", "Nat.sub", "Nat.mul", "Nat.pow", "Nat.gcd", "Nat.div", "Nat.mod",
    "Nat.beq", "Nat.ble", "Nat.land", "Nat.lor", "Nat.xor",
    "Nat.shiftLeft", "Nat.shiftRight", "String.ofList",
]

# No slashes, no "..", no whitespace — and no leading dash, so a name like "--reps" can never be
# mistaken for an option when it is passed through argv (self-inflicted DoS, not an injection).
SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
MAX_SLUG_LENGTH = 96

# Scored problems declare a complete grouped evaluation policy in config.json. The legacy
# `perf` range and these global defaults remain only for evaluation-policy-v1 tasks such as the
# experimental `conv` workspace. Every submission in one cohort receives the same schedule; the
# operator rotates its hidden seed between cohorts. An unseeded plan is deterministic local
# development only. See rules/evaluation.md and rules/problem-scoring.md.
_PERF_DEFAULTS = _CFG.get("perf_defaults", {"count": 10, "spacing": "geometric", "jitter": 0.15})
PERF_SEED = os.environ.pop("PERF_SEED", "")
_PERF_SEED_SOURCE = ["environment" if PERF_SEED else None]
EVALUATION_COHORT = os.environ.get("EVALUATION_COHORT", "")
EVALUATION_RUN_ID = os.environ.get("EVALUATION_RUN_ID", "")
EVALUATION_EXECUTOR_ID = os.environ.get("EVALUATION_EXECUTOR_ID", "local")
EVALUATION_EXECUTOR_VERSION = os.environ.get(
    "EVALUATION_EXECUTOR_VERSION", "fixed-host")
EVALUATION_RESOURCE_POLICY = {
    "image": os.environ.get("EVALUATION_IMAGE", "local-unspecified"),
    "memory": os.environ.get("EVALUATION_MEMORY", "local-unspecified"),
    "cpus": os.environ.get("EVALUATION_CPUS", "local-unspecified"),
    "pids_limit": os.environ.get("EVALUATION_PIDS_LIMIT", "local-unspecified"),
    "sandbox_mode": SANDBOX_MODE,
}


def _official_eval():
    return TIMING_METRIC == "perf_instructions" or OFFICIAL_EVAL


def _validate_timing_mode(keep_workspace):
    if not DEFER_TIMING:
        return
    if OFFICIAL_EVAL or TIMING_METRIC == "perf_instructions":
        raise InfraError("DEFER_TIMING is only valid for non-official development runs")
    if TIMING_EXECUTOR_URLS:
        raise InfraError("DEFER_TIMING cannot be combined with in-judge remote timing")
    if not keep_workspace:
        raise InfraError("DEFER_TIMING requires --keep-workspace")


def _deferred_measurement(target=None):
    return {
        "result": "deferred",
        "measurement_contract": MEASUREMENT_CONTRACT,
        "measurement_boundary": _measurement_boundary(target),
        "measurement_target": target,
    }


def _emit_stage_progress(key, status, started_at):
    """Append one completed stage boundary to the host-owned progress stream.

    The stream is optional so standalone and official Judge invocations keep
    their existing behavior. When configured it is a required orchestration
    contract: an invalid or unavailable target is an infrastructure fault,
    never something to hide behind a terminal verdict.
    """
    if not SAIR_PROGRESS_FILE:
        return
    if status not in ("done", "failed"):
        raise InfraError(f"invalid live progress status {status!r}")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
        raise InfraError(f"invalid live progress stage key {key!r}")
    duration_ms = int((time.monotonic() - started_at) * 1000)
    if duration_ms < 0:
        raise InfraError("live progress monotonic clock moved backwards")
    payload = (json.dumps({
        "key": key,
        "status": status,
        "durationMs": duration_ms,
    }, separators=(",", ":")) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(SAIR_PROGRESS_FILE, flags)
        try:
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("short write")
                view = view[written:]
        finally:
            os.close(fd)
    except OSError as exc:
        raise InfraError(f"cannot append live stage progress: {exc}") from exc


def _measure_or_defer(measure):
    if DEFER_TIMING:
        return "deferred", None
    return measure()


def _perf_policy_error(problem, detail):
    raise InfraError(f"invalid perf policy for '{problem}': {detail}")


def _policy_int(value, problem, field):
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value.strip()):
        return int(value)
    _perf_policy_error(problem, f"{field} must be an integer (got {value!r})")


def _perf_jitter(x, lo, hi, frac, problem, idx, endpoint=None):
    """Deterministic per-point jitter, directed inward at positive endpoints.

    One hidden rotation token yields one shared schedule per problem. Submission-specific
    jitter is deliberately forbidden: comparing raw work at different n is not a fair score,
    especially for factorial/exponential problems.  Sampling the endpoint directions instead
    of clamping outward samples avoids placing half of the hidden top slots exactly at `hi`.
    Zero remains fixed because multiplicative jitter has no positive scale there.
    """
    if not PERF_SEED or frac <= 0:
        return x
    material = json.dumps([PERF_SEED, problem, idx],
                          ensure_ascii=True, separators=(",", ":")).encode()
    h = hashlib.sha256(material).digest()
    sample = int.from_bytes(h[:8], "big")
    # Endpoint samples use an open unit interval, including for all-zero/all-one hash
    # prefixes.  Interior points retain the established [0, 1) mapping and symmetric jitter.
    endpoint_sample = sample >> 11
    inward_u = (endpoint_sample + 1) / (2 ** 53 + 1)      # uniform in (0, 1)
    if endpoint == "lower":
        if lo == 0:
            return x
        return min(hi, x * (1.0 + inward_u * frac))
    if endpoint == "upper":
        return max(lo, x * (1.0 - inward_u * frac))
    u = sample / 2.0 ** 64                                # uniform in [0, 1)
    return min(hi, max(lo, x * (1.0 + (2.0 * u - 1.0) * frac)))


def perf_inputs(cfg, problem):
    """Return exactly `count` strictly increasing Nat inputs from the configured policy.

    Official evaluation requires a nonempty, operator-supplied rotation seed. Invalid or
    impossible policies fail explicitly instead of silently returning fewer points.
    """
    perf = cfg.get("perf")
    if not (isinstance(perf, dict) and "min" in perf and "max" in perf):
        return None
    if _official_eval() and not PERF_SEED:
        raise InfraError("official evaluation requires a nonempty PERF_SEED")

    lo = _policy_int(perf["min"], problem, "min")
    hi = _policy_int(perf["max"], problem, "max")
    if lo < 0:
        _perf_policy_error(problem, f"min must be >= 0 for Nat inputs (got {lo})")
    if hi < lo:
        _perf_policy_error(problem, f"max ({hi}) is smaller than min ({lo})")

    configured_count = _policy_int(
        perf.get("count", _PERF_DEFAULTS.get("count", 10)), problem, "count")
    count_override = os.environ.get("PERF_COUNT")
    if count_override not in (None, "") and re.fullmatch(r"[+-]?[0-9]+", count_override.strip()):
        count = int(count_override)
    else:
        # PERF_COUNT is an operator convenience, not part of the problem policy. Preserve the
        # established forgiving behavior for a malformed override, while still rejecting an
        # invalid configured count below.
        count = configured_count
    if count < 1:
        _perf_policy_error(problem, f"count must be >= 1 (got {count})")
    capacity = hi - lo + 1
    if count > capacity:
        _perf_policy_error(
            problem, f"count {count} exceeds the {capacity} distinct integers in [{lo}, {hi}]")

    spacing = perf.get("spacing", _PERF_DEFAULTS.get("spacing", "geometric"))
    if spacing not in ("geometric", "linear"):
        _perf_policy_error(problem, f"spacing must be 'geometric' or 'linear' (got {spacing!r})")

    frac_value = perf.get("jitter", _PERF_DEFAULTS.get("jitter", 0.15))
    if isinstance(frac_value, bool) or not isinstance(frac_value, (int, float)):
        _perf_policy_error(problem, f"jitter must be a finite number (got {frac_value!r})")
    frac = float(frac_value)
    if not math.isfinite(frac) or not 0 <= frac < 1:
        _perf_policy_error(problem, f"jitter must satisfy 0 <= jitter < 1 (got {frac_value!r})")
    if _official_eval() and frac == 0:
        _perf_policy_error(problem, "official evaluation requires positive jitter")

    if count == 1:
        raw = [float(lo)]
    elif spacing == "linear":
        raw = [lo + (hi - lo) * i / (count - 1) for i in range(count)]
    elif lo == 0:
        # Log spacing is undefined at zero. Keep zero as the first slot and distribute the
        # remaining slots geometrically over the positive part of the interval.
        if count == 2:
            raw = [0.0, float(hi)]
        else:
            positive_count = count - 1
            raw = [0.0] + [
                hi ** (i / (positive_count - 1)) for i in range(positive_count)
            ]
    else:
        raw = [lo * (hi / lo) ** (i / (count - 1)) for i in range(count)]  # geometric

    # Project the possibly-colliding/locally-reordered rounded targets onto feasible integer
    # slots. The per-index bounds leave exactly enough room for all later points, so this
    # produces `count` points without retry loops or silent set-based collapse.
    pts = []
    for idx, x in enumerate(raw):
        endpoint = "lower" if idx == 0 else "upper" if idx + 1 == count else None
        target = int(round(_perf_jitter(x, lo, hi, frac, problem, idx, endpoint)))
        lower = lo + idx
        upper = hi - (count - 1 - idx)
        if pts:
            lower = max(lower, pts[-1] + 1)
        pts.append(min(upper, max(lower, target)))
    if len(pts) != count or any(a >= b for a, b in zip(pts, pts[1:])):
        _perf_policy_error(problem, "could not construct the requested distinct input slots")
    return pts


_GROUPED_EVALUATION_SCHEMA = "grouped-evaluation-v1"
_SEED_COMMITMENT_DOMAIN = b"lean-kernel-challenge/grouped-evaluation-seed-v1\0"
_GROUP_SAMPLE_DOMAIN = b"lean-kernel-challenge/grouped-evaluation-sample-v1\0"
_GROUP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _seed_commitment():
    """Commit to the hidden schedule seed without recording the seed itself.

    The commitment and the fully resolved plan are both part of evaluation-policy-v2.  After a
    cohort closes, publishing the seed lets anybody reproduce the plan and verify this value.
    Local, deliberately unseeded development runs record null rather than a hash of an empty
    string, so they cannot be mistaken for a hidden official schedule.
    """
    if not PERF_SEED:
        return None
    return hashlib.sha256(_SEED_COMMITMENT_DOMAIN + PERF_SEED.encode("utf-8")).hexdigest()


def _group_sample_digest(problem, group, case, purpose, attempt=0):
    """Domain-separated deterministic PRF output for one grouped schedule choice."""
    key = PERF_SEED.encode("utf-8")
    material = json.dumps(
        [problem, group, case, purpose, attempt],
        ensure_ascii=True, separators=(",", ":"),
    ).encode("utf-8")
    return hmac.new(key, _GROUP_SAMPLE_DOMAIN + material, hashlib.sha256).digest()


def _group_jitter(x, lo, hi, frac, problem, group, case, endpoint=None):
    """Grouped-policy counterpart of `_perf_jitter`, additionally separated by group id."""
    if not PERF_SEED or frac <= 0:
        return x
    sample = int.from_bytes(
        _group_sample_digest(problem, group, case, "jitter")[:8], "big")
    endpoint_sample = sample >> 11
    inward_u = (endpoint_sample + 1) / (2 ** 53 + 1)
    if endpoint == "lower":
        if lo == 0:
            return x
        return min(hi, x * (1.0 + inward_u * frac))
    if endpoint == "upper":
        return max(lo, x * (1.0 - inward_u * frac))
    u = sample / 2.0 ** 64
    return min(hi, max(lo, x * (1.0 + (2.0 * u - 1.0) * frac)))


def _group_sampling_error(problem, group, detail):
    raise InfraError(
        f"invalid grouped evaluation policy for '{problem}' group '{group}': {detail}")


def _group_int(value, problem, group, field):
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value.strip()):
        return int(value)
    _group_sampling_error(problem, group, f"{field} must be an integer (got {value!r})")


def _group_sampling_count(sampling, problem, group):
    count = _group_int(sampling.get("count"), problem, group, "sampling.count")
    if count < 1:
        _group_sampling_error(problem, group, f"count must be >= 1 (got {count})")
    return count


def _group_range_values(sampling, problem, group, spacing):
    lo = _group_int(sampling.get("min"), problem, group, "sampling.min")
    hi = _group_int(sampling.get("max"), problem, group, "sampling.max")
    if lo < 0:
        _group_sampling_error(problem, group, f"min must be >= 0 (got {lo})")
    if hi < lo:
        _group_sampling_error(problem, group, f"max ({hi}) is smaller than min ({lo})")
    count = _group_sampling_count(sampling, problem, group)
    capacity = hi - lo + 1
    if count > capacity:
        _group_sampling_error(
            problem, group,
            f"count {count} exceeds the {capacity} distinct integers in [{lo}, {hi}]")

    # No default: the canonical scorer's sealed-contract validator requires an explicit
    # jitter on range samplers, so defaulting here would only defer the failure past
    # plan construction. Both validators must state the same contract.
    if "jitter" not in sampling:
        _group_sampling_error(problem, group, "sampling.jitter must be declared explicitly")
    jitter_value = sampling["jitter"]
    if isinstance(jitter_value, bool) or not isinstance(jitter_value, (int, float)):
        _group_sampling_error(problem, group, f"jitter must be a finite number (got {jitter_value!r})")
    jitter = float(jitter_value)
    if not math.isfinite(jitter) or not 0 <= jitter < 1:
        _group_sampling_error(
            problem, group, f"jitter must satisfy 0 <= jitter < 1 (got {jitter_value!r})")
    if _official_eval() and jitter == 0:
        _group_sampling_error(problem, group, "official range sampling requires positive jitter")

    if count == 1:
        raw = [float(lo)]
    elif spacing == "linear":
        raw = [lo + (hi - lo) * i / (count - 1) for i in range(count)]
    elif lo == 0:
        if count == 2:
            raw = [0.0, float(hi)]
        else:
            positive_count = count - 1
            raw = [0.0] + [
                hi ** (i / (positive_count - 1)) for i in range(positive_count)
            ]
    else:
        raw = [lo * (hi / lo) ** (i / (count - 1)) for i in range(count)]

    values = []
    for case, x in enumerate(raw):
        endpoint = "lower" if case == 0 else "upper" if case + 1 == count else None
        target = int(round(
            _group_jitter(x, lo, hi, jitter, problem, group, case, endpoint)))
        lower = lo + case
        upper = hi - (count - 1 - case)
        if values:
            lower = max(lower, values[-1] + 1)
        values.append(min(upper, max(lower, target)))
    if len(values) != count or any(a >= b for a, b in zip(values, values[1:])):
        _group_sampling_error(problem, group, "could not construct distinct ordered range samples")
    return values


def _group_uniform_values(sampling, problem, group):
    lo = _group_int(sampling.get("min"), problem, group, "sampling.min")
    hi = _group_int(sampling.get("max"), problem, group, "sampling.max")
    if lo < 0:
        _group_sampling_error(problem, group, f"min must be >= 0 (got {lo})")
    if hi < lo:
        _group_sampling_error(problem, group, f"max ({hi}) is smaller than min ({lo})")
    count = _group_sampling_count(sampling, problem, group)
    capacity = hi - lo + 1
    if count > capacity:
        _group_sampling_error(
            problem, group,
            f"count {count} exceeds the {capacity} distinct integers in [{lo}, {hi}]")

    # Rejection sampling avoids modulo bias and makes the exact integer schedule independently
    # reproducible from the revealed seed. Collision retries are separately domain-separated.
    modulus = 1 << 256
    unbiased_limit = modulus - (modulus % capacity)
    values = []
    used = set()
    for case in range(count):
        attempt = 0
        while True:
            sample = int.from_bytes(
                _group_sample_digest(problem, group, case, "uniform-int", attempt), "big")
            attempt += 1
            if sample >= unbiased_limit:
                continue
            value = lo + sample % capacity
            if value not in used:
                used.add(value)
                values.append(value)
                break
    return values


def _group_packed_values(sampling, problem, group):
    """Encode one public scale and one hidden 32-bit instance seed into a Nat."""
    scale = _group_int(sampling.get("scale"), problem, group, "sampling.scale")
    seed_bits = _group_int(sampling.get("seed_bits"), problem, group, "sampling.seed_bits")
    if scale < 0:
        _group_sampling_error(problem, group, f"scale must be >= 0 (got {scale})")
    if seed_bits != 32:
        _group_sampling_error(
            problem, group, f"packed seed_bits must be exactly 32 (got {seed_bits})")
    count = _group_sampling_count(sampling, problem, group)
    capacity = 1 << seed_bits
    if count > capacity:
        _group_sampling_error(problem, group, f"count {count} exceeds the packed seed space")

    values = []
    used_seeds = set()
    for case in range(count):
        attempt = 0
        while True:
            seed = int.from_bytes(
                _group_sample_digest(problem, group, case, "packed-seed", attempt)[:4], "big")
            attempt += 1
            if seed not in used_seeds:
                used_seeds.add(seed)
                values.append((scale << seed_bits) | seed)
                break
    return scale, values


def performance_plan(cfg, problem):
    """Resolve a grouped evaluation policy into an explicit, flat slot plan.

    `None` means the problem uses the legacy v1 `perf` policy.  Group order, case identity and
    exact Nat inputs are explicit in every v2 row; no scorer has to infer difficulty from `n`.
    """
    evaluation = cfg.get("evaluation")
    if evaluation is None:
        return None
    if "perf" in cfg:
        raise InfraError(
            f"problem '{problem}' config must not define both legacy perf and evaluation")
    if not isinstance(evaluation, dict):
        raise InfraError(f"invalid grouped evaluation policy for '{problem}': evaluation must be an object")
    if evaluation.get("schema") != _GROUPED_EVALUATION_SCHEMA:
        raise InfraError(
            f"invalid grouped evaluation policy for '{problem}': unsupported schema "
            f"{evaluation.get('schema')!r}")
    groups = evaluation.get("groups")
    if not isinstance(groups, list) or not groups:
        raise InfraError(
            f"invalid grouped evaluation policy for '{problem}': groups must be a nonempty list")
    if _official_eval() and not PERF_SEED:
        raise InfraError("official evaluation requires a nonempty PERF_SEED")
    count_override_text = os.environ.get("PERF_COUNT")
    if OFFICIAL_EVAL and count_override_text not in (None, ""):
        raise InfraError("PERF_COUNT is forbidden for official grouped evaluation policies")
    # Local smoke tests may cap EACH group independently.  Resolve the configured schedule first
    # and then take its prefix, so quick mode is literally a prefix of the full local cohort (and
    # packed case seeds keep the same case identities).  Malformed/non-positive development
    # overrides retain the legacy forgiving behavior and are ignored.
    group_case_cap = None
    if (not OFFICIAL_EVAL and isinstance(count_override_text, str)
            and re.fullmatch(r"[+]?[0-9]+", count_override_text.strip())):
        parsed_override = int(count_override_text)
        if parsed_override > 0:
            group_case_cap = parsed_override

    plan = []
    seen_groups = set()
    seen_orders = set()
    seen_inputs = set()
    previous_order = None
    for group_cfg in groups:
        if not isinstance(group_cfg, dict):
            raise InfraError(
                f"invalid grouped evaluation policy for '{problem}': every group must be an object")
        group = group_cfg.get("id")
        if not isinstance(group, str) or not _GROUP_ID.fullmatch(group):
            raise InfraError(
                f"invalid grouped evaluation policy for '{problem}': invalid group id {group!r}")
        if group in seen_groups:
            _group_sampling_error(problem, group, "duplicate group id")
        seen_groups.add(group)
        order = group_cfg.get("order")
        if type(order) is not int or order < 0:
            _group_sampling_error(problem, group, f"order must be a nonnegative integer (got {order!r})")
        if order in seen_orders:
            _group_sampling_error(problem, group, f"duplicate group order {order}")
        if previous_order is not None and order <= previous_order:
            _group_sampling_error(problem, group, "groups must be listed in strictly increasing order")
        seen_orders.add(order)
        previous_order = order

        sampling = group_cfg.get("sampling")
        if not isinstance(sampling, dict):
            _group_sampling_error(problem, group, "sampling must be an object")
        kind = sampling.get("kind")
        plan_extras = {}
        if kind in ("geometric_range", "linear_range", "range"):
            spacing = (sampling.get("spacing", "geometric") if kind == "range"
                       else "geometric" if kind == "geometric_range" else "linear")
            if spacing not in ("geometric", "linear"):
                _group_sampling_error(
                    problem, group, f"spacing must be 'geometric' or 'linear' (got {spacing!r})")
            values = _group_range_values(sampling, problem, group, spacing)
        elif kind == "uniform_int":
            values = _group_uniform_values(sampling, problem, group)
        elif kind == "packed":
            scale, values = _group_packed_values(sampling, problem, group)
            plan_extras = {"scale": scale}
        elif kind == "fixed":
            values = sampling.get("values")
            if not (isinstance(values, list) and values
                    and all(type(n) is int and n >= 0 for n in values)
                    and len(values) == len(set(values))):
                _group_sampling_error(
                    problem, group, "fixed values must be a nonempty list of distinct Nat inputs")
            if "count" in sampling and _group_sampling_count(sampling, problem, group) != len(values):
                _group_sampling_error(problem, group, "fixed count does not match values length")
        else:
            _group_sampling_error(problem, group, f"unknown sampling kind {kind!r}")

        if group_case_cap is not None:
            values = values[:group_case_cap]

        limits = group_cfg.get("limits", {})
        if not isinstance(limits, dict):
            _group_sampling_error(problem, group, "limits must be an object")
        unknown_limits = set(limits) - {
            "timeout_seconds", "kernel_instructions",
        }
        if unknown_limits:
            _group_sampling_error(
                problem, group, f"unknown limit fields {sorted(unknown_limits)!r}")
        for limit_name, limit_value in limits.items():
            if type(limit_value) is not int or limit_value <= 0:
                _group_sampling_error(
                    problem, group,
                    f"limits.{limit_name} must be a positive integer (got {limit_value!r})")
        # The effective replay deadline is min(evaluator ceiling, group watchdog). A group
        # watchdog above the checked-in ceiling would be silently clipped while the public
        # table and the sealed policy advertise the larger value — reject it at plan time.
        # Compare against the checked-in config value, not the env-derived TIMING_TIMEOUT:
        # dev quick mode legitimately shrinks the latter below every group watchdog.
        replay_cap = limits.get("timeout_seconds")
        if replay_cap is not None and replay_cap > _J["timing_timeout_seconds"]:
            _group_sampling_error(
                problem, group,
                f"limits.timeout_seconds ({replay_cap}) exceeds the evaluator timing ceiling "
                f"({_J['timing_timeout_seconds']}s) and would be silently clipped")

        for case, n in enumerate(values):
            if n in seen_inputs:
                _group_sampling_error(problem, group, f"input {n} duplicates another plan slot")
            seen_inputs.add(n)
            plan.append({
                "slot": len(plan), "group": group, "case": case, "n": n,
                "limits": dict(limits), **plan_extras,
            })

    return plan


def _validated_performance_plan(cfg, problem):
    """Resolve and validate the complete grouped scoring contract before judging.

    ``performance_plan`` owns deterministic schedule construction.  The canonical
    scorer owns awards, prerequisites, ranking, and the sealed-plan shape.  Running
    both here prevents a malformed organizer config from consuming contestant work
    and later being promoted as accepted-but-unscored.
    """
    plan = performance_plan(cfg, problem)
    if plan is None:
        if OFFICIAL_EVAL:
            raise InfraError(
                f"official Stage 1 evaluation requires a grouped policy for '{problem}'")
        return None
    scorer = _canonical_scorer()
    error = scorer._grouped_evaluation_shape_error(
        cfg.get("evaluation"), plan, official=OFFICIAL_EVAL)
    if error is not None:
        raise InfraError(f"invalid grouped evaluation policy for '{problem}': {error}")
    return plan


class InfraError(Exception):
    """Raised for any infrastructure failure; caught at top level → error JSON + exit 2."""


class SubmissionError(Exception):
    """Raised for a contestant-side format error (missing / oversized / symlinked / non-.lean
    Submission). It is the submission's fault, so the top level writes a REJECTED verdict
    (exit 0) — not an infra error, which (exit 2) would requeue an invalid submission forever."""


class TimingRetry(Exception):
    """Raised when every timing executor is unreachable. NOT a judgement: the top
    level writes a 'retry' verdict and exits 3 so the caller requeues the
    submission losslessly (never an error verdict for an executor outage)."""


class PerfBudgetExhausted(Exception):
    """Raised internally when an absolute performance-phase deadline is exhausted."""


def _remaining_timeout(deadline, cap):
    """Return the remaining timeout for one sub-step, or zero after an absolute deadline."""
    if deadline is None:
        return float(cap)
    return max(0.0, min(float(cap), deadline - time.monotonic()))


def _consume_perf_seed_stdin():
    """Read the official seed once, before any untrusted process is started.

    The production wrapper sends it on stdin instead of Docker env/argv, then the pipe is
    exhausted. This keeps the secret out of the elaborator environment and out of the parent
    process's initial `/proc/.../environ` image.
    """
    global PERF_SEED
    marker = os.environ.pop("PERF_SEED_STDIN", "")
    if not marker:
        return
    if marker != "1":
        raise InfraError("PERF_SEED_STDIN must be exactly '1'")
    if PERF_SEED:
        raise InfraError("ambiguous PERF_SEED sources (environment and stdin)")
    raw = sys.stdin.buffer.readline(1026)
    if not raw.endswith(b"\n") or len(raw) > 1025:
        raise InfraError("official PERF_SEED stdin record is missing or too long")
    try:
        seed = raw[:-1].decode("utf-8")
    except UnicodeDecodeError:
        raise InfraError("official PERF_SEED must be valid UTF-8")
    if not seed or "\x00" in seed:
        raise InfraError("official PERF_SEED must be nonempty and contain no NUL")
    PERF_SEED = seed
    _PERF_SEED_SOURCE[0] = "stdin"


def valid_slug(s: str) -> bool:
    return (isinstance(s, str) and 0 < len(s) <= MAX_SLUG_LENGTH
            and s not in (".", "..") and SLUG.fullmatch(s) is not None)


def _atomic_json(path: Path, payload):
    """Atomically replace one JSON file so report readers never see a partial verdict."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2, allow_nan=False)
        os.replace(temporary, path)
    finally:
        try:
            Path(temporary).unlink()
        except FileNotFoundError:
            pass


def _store_verdict(problem, sub_name, payload, promote):
    """Persist every attempt and optionally promote it to the current verdict.

    Immutable attempt records keep prior cohorts and infrastructure failures available for audit.
    A retry/error never replaces an existing accepted or rejected result.
    """
    safe_problem = problem if valid_slug(problem or "") else "_infra"
    safe_name = sub_name if valid_slug(sub_name or "") else "_invalid"
    record = dict(payload)
    run_id = record.get("run_id")
    if not valid_slug(run_id or ""):
        run_id = f"run-{os.getpid()}-{time.time_ns()}"
        record["run_id"] = run_id

    outdir = RESULTS / safe_problem
    attempt = outdir / "attempts" / f"{safe_name}__{run_id}.json"
    current = outdir / f"{safe_name}.json"
    _atomic_json(attempt, record)
    # Serialize the current-verdict read/decision/write across judge processes. Without the
    # lock, a retry can observe no current verdict, pause, and then replace an accepted verdict
    # written by a concurrent run. Attempt files remain immutable and need no shared lock.
    lock_dir = outdir / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir / f"{safe_name}.lock").open("a+") as lock:
        lock_deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= lock_deadline:
                    raise InfraError(
                        f"timed out acquiring verdict lock for {safe_problem}/{safe_name}")
                time.sleep(0.05)
        should_promote = promote or not current.exists()
        if not should_promote:
            try:
                previous = json.loads(current.read_text())
                should_promote = previous.get("status") not in ("accepted", "rejected")
            except (OSError, UnicodeError, ValueError, AttributeError):
                should_promote = True
        if should_promote:
            _atomic_json(current, record)
            return current
    return attempt


def _write_infra_verdict(problem, sub_name, reason, status="error"):
    """Best-effort error verdict so the contract 'always a verdict file, never a
    traceback' holds even for unexpected failures. Non-terminal attempts do not overwrite a
    prior judged result."""
    try:
        _store_verdict(
            problem,
            sub_name,
            {"problem": problem, "submission": sub_name, "run_id": EVALUATION_RUN_ID,
             "status": status, "reason": reason, "stages": {}},
            promote=status in ("accepted", "rejected"),
        )
    except Exception:
        pass


def _network_is_reachable():
    """Probe whether outbound networking works, as evidence the container envelope was applied.

    FAIL CLOSED: only an explicit "no route" errno counts as evidence of isolation. Treating any
    OSError as isolated would accept ECONNREFUSED — which proves the opposite, since a refusal
    means the packet reached a host. Both IPv4 and IPv6 are probed: a v6-only egress would
    otherwise pass a v4-only check. A connect timeout also counts as reachable (routable but
    filtered), as does any error we cannot positively attribute to an unreachable network."""
    import errno
    import socket

    unreachable = {errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN, errno.EAFNOSUPPORT}
    targets = [
        (socket.AF_INET, ("192.0.2.1", 80)),         # TEST-NET-1 (RFC 5737)
        (socket.AF_INET, ("8.8.8.8", 53)),           # public resolver
        (socket.AF_INET6, ("2001:db8::1", 80)),      # documentation prefix (RFC 3849)
        (socket.AF_INET6, ("2001:4860:4860::8888", 53)),
    ]
    for family, addr in targets:
        try:
            s = socket.socket(family, socket.SOCK_STREAM)
        except OSError as e:
            if e.errno in unreachable:
                continue                              # family unavailable → consistent with isolation
            return True
        s.settimeout(1.0)
        try:
            s.connect(addr)
            return True                               # connected → not isolated
        except (socket.timeout, TimeoutError):
            return True                               # routable but filtered → not isolated
        except OSError as e:
            if e.errno in unreachable:
                continue                              # genuinely no route → consistent with isolation
            return True                               # e.g. ECONNREFUSED: something answered
        finally:
            s.close()
    return False


def has_real_landrun(env):
    return shutil.which("landrun", path=env.get("PATH", "")) not in (None, str(SHIM_DIR / "landrun"))


def tool_env():
    # Keep every untrusted Lean/comparator process on a small, stable environment.
    # In particular, PERF_SEED and executor credentials must never cross this boundary.
    env = {}
    for key in ("HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR"):
        if key in os.environ:
            env[key] = os.environ[key]
    env["HOME"] = env.get("HOME", str(Path.home()))
    env["ELAN_HOME"] = os.environ.get("ELAN_HOME", str(Path.home() / ".elan"))
    env["LEAN_ABORT_ON_PANIC"] = "1"
    parts = [str(LEAN4EXPORT_BIN)]
    # Prepend the bundled shim only if no real landrun is on PATH (dev machine).
    host_path = os.environ.get("PATH", os.defpath)
    if shutil.which("landrun", path=host_path) is None:
        parts.insert(0, str(SHIM_DIR))
    env["PATH"] = os.pathsep.join(parts + [host_path])
    return env


def _kill_group(pgid):
    """Kill a saved process-group id. NOTE: this reaps descendants that stayed in the
    group; it is NOT a security boundary — a descendant can `setsid()` out of the group,
    and same-UID processes can race files. Real isolation (kill-all, resource caps) is
    the container/cgroup + non-root user's job (see Dockerfile). This is defense in depth."""
    if pgid is None:
        return
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _raise_stack():
    """Raise the child's stack rlimit before exec so deep kernel/Meta reduction (reducing
    `impl n` for large n, or elaborating the generated kernel proof) doesn't overflow the default
    ~8 MB stack. macOS refuses `soft == hard` for RLIMIT_STACK, so try a descending set of
    targets and keep the largest that sticks (Linux's infinite hard limit takes 512 MB on
    the first try; a raise that doesn't stick just leaves the default in place)."""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    except (ValueError, OSError):
        return
    cap = (512 * 1024 * 1024) if hard == resource.RLIM_INFINITY else hard
    for target in (cap, cap - (1 << 20), 256 * 1024 * 1024, 64 * 1024 * 1024):
        if target <= soft:
            return
        try:
            resource.setrlimit(resource.RLIMIT_STACK, (target, hard))
            return
        except (ValueError, OSError):
            continue


class _OutputTail:
    """A bounded byte ring used while a subprocess is running."""

    def __init__(self, limit):
        self.limit = max(1, limit)
        self.chunks = collections.deque()
        self.size = 0
        self.truncated = False

    def append(self, data):
        if not data:
            return
        if len(data) >= self.limit:
            self.truncated = self.truncated or self.size > 0 or len(data) > self.limit
            self.chunks.clear()
            data = data[-self.limit:]
            self.chunks.append(data)
            self.size = len(data)
            return
        self.chunks.append(data)
        self.size += len(data)
        while self.size > self.limit:
            excess = self.size - self.limit
            first = self.chunks[0]
            self.truncated = True
            if len(first) <= excess:
                self.size -= len(self.chunks.popleft())
            else:
                self.chunks[0] = first[excess:]
                self.size -= excess

    def text(self):
        prefix = b"[earlier tool output truncated]\n" if self.truncated else b""
        return (prefix + b"".join(self.chunks)).decode(errors="replace")


def _drain_output(stream, tail, stop):
    fd = stream.fileno()
    os.set_blocking(fd, False)
    try:
        while not stop.is_set():
            readable, _, _ = select.select([fd], [], [], 0.02)
            if not readable:
                continue
            try:
                chunk = os.read(fd, 64 * 1024)
            except BlockingIOError:
                continue
            if not chunk:
                break
            tail.append(chunk)
    except (OSError, ValueError):
        # The parent closes the pipe if an escaped descendant keeps it open after the direct
        # child exits. Output already collected remains useful as a bounded diagnostic tail.
        return
    finally:
        try:
            stream.close()
        except OSError:
            pass


def run(cmd, cwd, env, timeout, stdout_path=None):
    """Run a command in its own process group. The saved pgid is killed on timeout AND on
    normal exit (pgid captured at spawn, not via getpgid on an already-exited child).
    Tool output is continuously drained into a bounded in-memory tail, preventing verbose
    elaboration from consuming unbounded memory or disk. Returns
    (exit_code | 'timeout', output_tail)."""
    oom_kills_before = _read_cgroup_oom_kills()
    _LAST_RUN_OOM_KILL[0] = False
    popen_kw = dict(cwd=cwd, env=env, start_new_session=True, preexec_fn=_raise_stack)
    p = None
    pgid = None
    output_file = None
    output_pipe = None
    reader = None
    reader_stop = threading.Event()
    tail = _OutputTail(MAX_TOOL_OUTPUT_BYTES)
    try:
        if stdout_path:
            output_file = open(stdout_path, "wb")
            p = subprocess.Popen(cmd, stdout=output_file, stderr=subprocess.PIPE, **popen_kw)
            output_pipe = p.stderr
        else:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **popen_kw)
            output_pipe = p.stdout
        pgid = p.pid  # start_new_session=True → child is its own group leader
        reader = threading.Thread(
            target=_drain_output, args=(output_pipe, tail, reader_stop), daemon=True,
            name=f"tool-output-{p.pid}")
        reader.start()
        timed_out = False
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(pgid)
            p.wait()
        else:
            # Kill group descendants before waiting for pipe EOF. A descendant that inherited
            # stdout/stderr would otherwise keep the reader blocked after the direct child exits.
            _kill_group(pgid)

        # Output has been drained continuously, so EOF should be immediate for an ordinary
        # child. Keep only a short grace period; an escaped descendant must not extend a phase
        # deadline by holding the inherited pipe open.
        reader.join(timeout=0.25)
        if reader.is_alive():
            reader_stop.set()
            reader.join(timeout=0.1)
        output = tail.text()
        if timed_out:
            return "timeout", f"timed out after {timeout}s\n{output}"
        return p.returncode, output
    except FileNotFoundError as e:
        raise InfraError(f"tool not found: {e}")
    finally:
        # Reap any descendants left in the group (dev boxes without landrun). Uses the
        # pgid captured at spawn, so it works even though the direct child has exited.
        _kill_group(pgid)
        if output_file is not None:
            output_file.close()
        if output_pipe is not None and not output_pipe.closed:
            output_pipe.close()
        oom_kills_after = _read_cgroup_oom_kills()
        _LAST_RUN_OOM_KILL[0] = (
            oom_kills_before is not None
            and oom_kills_after is not None
            and oom_kills_after > oom_kills_before
        )


def last_line(out):
    lines = [l for l in out.strip().splitlines() if l.strip()]
    return lines[-1] if lines else "(no output)"


def _died_by_signal(rc):
    """True if a trusted tool was killed by a signal rather than exiting on its own verdict.

    At correctness-gate stages every such death is an infrastructure fault, never evidence that
    a proof is invalid. The target-replay path separately recognizes SIGKILL under the sealed
    cgroup as a case resource-limit outcome. Python reports a raw negative code, while `lake env`
    launders it into the shell's 128+N convention."""
    if not isinstance(rc, int):
        return False
    return rc < 0 or 128 < rc <= 192


def _died_by_sigkill(rc):
    """Recognize the exit forms produced when the cgroup OOM killer sends SIGKILL."""
    return rc in (-signal.SIGKILL, 128 + signal.SIGKILL)


def _read_cgroup_oom_kills():
    """Read the cgroup-v2 OOM-kill counter, or ``None`` outside that environment."""
    try:
        fields = {}
        for line in Path("/sys/fs/cgroup/memory.events").read_text().splitlines():
            key, value = line.split()
            fields[key] = int(value)
        return fields.get("oom_kill")
    except (OSError, ValueError):
        return None


_LAST_RUN_OOM_KILL = [False]


def _attested_local_memory_kill(rc):
    """Require the canonical wrapper and OOM evidence bound to the preceding command."""
    evidenced = _LAST_RUN_OOM_KILL[0]
    _LAST_RUN_OOM_KILL[0] = False
    return bool(
        evidenced
        and _died_by_sigkill(rc)
        and SANDBOX_MODE == "container"
        and EVALUATION_RESOURCE_POLICY.get("memory") == "4g"
        and os.environ.get("ISOLATION_ATTESTATION") == "run_isolated.sh"
    )


def _resolve_lean_runtime(work, env):
    """Resolve the pinned Lean binary/sysroot before any contestant elaboration runs."""
    rc, out = run(["lake", "env", "lean", "--print-prefix"], work, env, AUDIT_TIMEOUT)
    if rc == "timeout":
        raise InfraError("timed out while resolving the pinned Lean runtime")
    if rc != 0:
        raise InfraError(f"cannot resolve the pinned Lean runtime: {last_line(out)}")
    prefix = Path(last_line(out))
    lean_bin = prefix / "bin" / "lean"
    core_lib = prefix / "lib" / "lean"
    if not (prefix.is_absolute() and lean_bin.is_file() and core_lib.is_dir()):
        raise InfraError(f"invalid Lean runtime prefix returned by toolchain: {prefix}")
    return lean_bin, prefix, core_lib


def _verified_runtime_env(base_env, artifact_lib, lean_prefix, core_lib):
    """Environment for judge-owned modules importing the pinned comparator artifacts."""
    env = dict(base_env)
    env["LEAN_SYSROOT"] = str(lean_prefix)
    env["LEAN_PATH"] = os.pathsep.join((str(artifact_lib), str(core_lib)))
    env["PATH"] = os.pathsep.join((str(lean_prefix / "bin"), env["PATH"]))
    return env


def _audit_tree(base: Path, roots):
    """Audit `roots` (files/dirs) under `base`: no symlinks, regular .lean files only,
    within `base`, under size/count caps. Used on the assembled workspace so a symlink
    swapped in after the pre-copy check cannot survive."""
    base_real = base.resolve(strict=True)
    total = count = 0
    stack = list(roots)
    while stack:
        p = stack.pop()
        if not p.exists() and not p.is_symlink():
            continue
        if p.is_symlink():
            raise SubmissionError(f"submission: symlinks are not allowed ({p.name})")
        rp = p.resolve(strict=True)
        if rp != base_real and not str(rp).startswith(str(base_real) + os.sep):
            raise SubmissionError(f"submission: path escapes workspace ({p})")
        if p.is_dir():
            stack.extend(p.iterdir())
            continue
        if not p.is_file():
            raise SubmissionError(f"submission: not a regular file ({p.name})")
        if p.suffix not in ("", ".lean"):
            raise SubmissionError(f"submission: only .lean files allowed ({p.name})")
        count += 1
        total += p.stat().st_size
        if count > MAX_SUBMISSION_FILES:
            raise SubmissionError(f"submission: too many files (> {MAX_SUBMISSION_FILES})")
        if total > MAX_SUBMISSION_BYTES:
            raise SubmissionError(f"submission: payload too large (> {MAX_SUBMISSION_BYTES} bytes)")


def _chmod_tree(path, dir_mode, file_mode):
    for root, dirs, files in os.walk(path):
        for name in files:
            try: os.chmod(os.path.join(root, name), file_mode)
            except OSError: pass
        for name in dirs:
            try: os.chmod(os.path.join(root, name), dir_mode)
            except OSError: pass
    try: os.chmod(path, dir_mode)
    except OSError: pass


def freeze_readonly(path):
    _chmod_tree(path, 0o555, 0o444)


def thaw(path):
    _chmod_tree(path, 0o755, 0o644)


def _preflight_payload(sd: Path):
    """Validate the contestant's single-file SOURCE payload before it is copied.

    Two reasons this runs on the source rather than (only) the assembled tree:
      * a special file (FIFO/socket/device) makes `shutil.copytree` raise a bare `shutil.Error`
        that escapes as an infra `error` + exit 2, so the caller requeues a submission that can
        never succeed. It is the contestant's payload → SubmissionError → `rejected`.
      * the size/count caps otherwise apply only AFTER the whole tree is on disk, so the copy cost
        is proportional to whatever was supplied instead of to the configured cap.
    """
    try:
        entries = list(sd.iterdir())
    except OSError as e:
        raise SubmissionError(f"submission: unreadable payload directory ({e})")
    unexpected = sorted(p.name for p in entries if p.name != "Submission.lean")
    if unexpected:
        preview = ", ".join(repr(name) for name in unexpected[:3])
        if len(unexpected) > 3:
            preview += ", ..."
        raise SubmissionError(
            f"submission: exactly one Submission.lean file is allowed (unexpected: {preview})")

    source = sd / "Submission.lean"
    try:
        if source.is_symlink():
            raise SubmissionError("submission: Submission.lean may not be a symlink")
        st = source.stat()
        if not stat.S_ISREG(st.st_mode):
            raise SubmissionError("submission: Submission.lean must be a regular file")
        if st.st_size > MAX_SUBMISSION_BYTES:
            raise SubmissionError(
                f"submission: payload too large (> {MAX_SUBMISSION_BYTES} bytes)")
    except FileNotFoundError:
        raise SubmissionError("submission: missing Submission.lean")
    except OSError as e:
        raise SubmissionError(f"submission: unreadable Submission.lean ({e})")


def assemble(job_dir: Path, problem, submission_dir):
    prob_dir = PROBLEMS / problem
    if not (prob_dir / "config.json").exists():
        raise InfraError(f"unknown problem '{problem}'")
    sd = Path(submission_dir)
    if (sd / "Submission.lean").is_symlink() or not (sd / "Submission.lean").is_file():
        raise SubmissionError(f"submission '{submission_dir}' has no regular Submission.lean")

    # Pre-flight the SOURCE payload before writing anything: enforce the one-file rule, reject
    # special files, and stop at the size cap before copying.
    _preflight_payload(sd)

    work = job_dir / "workspace"
    # Copy the locked template (preserve any symlink AS a symlink; there are none, but
    # never silently follow one).
    shutil.copytree(prob_dir, work, symlinks=True,
                    ignore=shutil.ignore_patterns(".lake", "lake-manifest.json"))
    # Overlay the one contestant file without following symlinks.
    try:
        shutil.copy(sd / "Submission.lean", work / "Submission.lean", follow_symlinks=False)
    except (shutil.Error, OSError) as e:
        # Contestant's payload is at fault → rejected (exit 0), never an infra retry loop.
        raise SubmissionError(f"submission: unreadable or special file in payload ({e})")
    # Re-audit the ASSEMBLED contestant files (closes validate→copy TOCTOU).
    _audit_tree(work, [work / "Submission.lean"])
    return work


def _measurement_boundary(target):
    if target is None:
        return FULL_REPLAY_BOUNDARY
    if not isinstance(target, str) or not target or any(ch.isspace() for ch in target):
        raise InfraError(f"invalid timer target {target!r}")
    return TARGET_REPLAY_BOUNDARY


def _measurement_contract_record():
    """Machine-readable contract committed into verdicts and evaluation cohorts."""
    return {
        "id": MEASUREMENT_CONTRACT,
        "correctness_boundary": FULL_REPLAY_BOUNDARY,
        "performance_boundary": TARGET_REPLAY_BOUNDARY,
        "target_proof_encoding": TARGET_PROOF_ENCODING,
        "wall_clock_source": "timer-internal-monotonic-ns",
        "perf_counter_control": "timer-perf-event-open+ioctl-enable",
        "local_protocol": "local-v2",
        "remote_protocol": REMOTE_PROTOCOL,
        "timeout_scope": PROCESS_TIMEOUT_SCOPE,
    }


def _timeout_measurement(target, source):
    return {
        "measurement_contract": MEASUREMENT_CONTRACT,
        "measurement_boundary": _measurement_boundary(target),
        "measurement_target": target,
        "timeout_scope": PROCESS_TIMEOUT_SCOPE,
        "timeout_source": source,
    }


def _resource_limit_measurement(target, source, phase):
    record = {
        "resource": "memory",
        "memory_mb": REPLAY_MEMORY_MB,
        "resource_limit_source": source,
        "resource_phase": phase,
    }
    if phase in ("correctness-replay", "target-replay"):
        record.update({
            "measurement_contract": MEASUREMENT_CONTRACT,
            "measurement_boundary": _measurement_boundary(target),
            "measurement_target": target,
        })
    return record


def _parse_timer_measurement(out, target):
    """Parse the one fail-closed timer-kernel v2 measurement record."""
    records = [
        line[len(_TIMER_TIMING_PREFIX):]
        for line in out.splitlines()
        if line.startswith(_TIMER_TIMING_PREFIX)
    ]
    if len(records) != 1:
        raise InfraError(
            f"timer emitted {len(records)} measurement records (expected exactly one)")
    try:
        data = json.loads(records[0])
    except json.JSONDecodeError as e:
        raise InfraError(f"timer emitted malformed measurement JSON: {e.msg}")
    expected_keys = {
        "measurement_contract", "boundary", "target", "wall_ns", "instructions",
        "peak_rss_kb", "phase",
    }
    if not isinstance(data, dict) or set(data) != expected_keys:
        raise InfraError("timer measurement record has an incompatible schema")
    if data["measurement_contract"] != MEASUREMENT_CONTRACT:
        raise InfraError(
            f"timer measurement contract mismatch ({data['measurement_contract']!r})")
    expected_boundary = _measurement_boundary(target)
    if data["boundary"] != expected_boundary:
        raise InfraError(
            f"timer measurement boundary mismatch ({data['boundary']!r})")
    if data["target"] != target:
        raise InfraError(f"timer measurement target mismatch ({data['target']!r})")
    if data["phase"] != "complete":
        raise InfraError(f"timer measurement did not complete ({data['phase']!r})")
    if type(data["wall_ns"]) is not int or data["wall_ns"] <= 0:
        raise InfraError("timer measurement wall_ns must be a positive integer")
    if TIMING_METRIC == "perf_instructions":
        if type(data["instructions"]) is not int or data["instructions"] <= 0:
            raise InfraError("timer measurement instructions must be a positive integer "
                             "(PMU unavailable to the timer?)")
    elif data["instructions"] is not None:
        # The timer must not have touched the PMU outside the instruction metric.
        raise InfraError("timer counted instructions outside metric=perf_instructions")
    if _LINUX:
        if type(data["peak_rss_kb"]) is not int or data["peak_rss_kb"] <= 0:
            raise InfraError("timer measurement peak_rss_kb must be a positive integer on Linux")
    elif data["peak_rss_kb"] is not None:
        # The non-Linux timer stub cannot measure the window; a value here is a fault.
        raise InfraError("timer reported a replay memory peak off Linux")
    return data


def _timer_command(export_file, target):
    cmd = [str(TIMER)]
    if TIMING_METRIC == "perf_instructions":
        # Only the instruction metric asks the timer to open its own PMU counter. Wall-time
        # development runs (and the Docker image's build-time gate) must stay PMU-free.
        cmd.append("--count-instructions")
    if target is not None:
        _measurement_boundary(target)  # validate before it reaches argv
        cmd += ["--target", target]
    return cmd + [str(export_file)]


def _preflight_perf_counter(env):
    """Prove the local PMU instruction counter works BEFORE elaborating the submission.

    Two production failure modes would otherwise surface only after the comparator hour, as
    errors misattributed to the submission's replay: Ubuntu's linux-tools `perf` wrapper has
    no build for the running kernel (nonzero exit on any host/kernel drift), and a PMU
    permission shortfall (perf_event_paranoid >= 2 without effective CAP_PERFMON) makes perf
    silently downgrade to user-only counting under the renamed event `instructions:u`, which
    would not measure what the sealed contract promises. Probe with a trivial command and
    demand the exact full-scope `instructions` event.
    """
    perf = shutil.which("perf", path=env.get("PATH", ""))
    if not perf:
        raise InfraError("metric=perf_instructions but `perf` not found — requires the Linux eval host")
    try:
        proc = subprocess.run([perf, "stat", "-x", ",", "-e", "instructions", "--", "true"],
                              capture_output=True, text=True, timeout=30, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise InfraError(f"perf preflight could not execute: {e}")
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-500:]
        raise InfraError("perf preflight exited nonzero — no working perf for the running kernel "
                         f"(linux-tools wrapper/kernel mismatch?): {tail}")
    events = []
    for line in proc.stderr.splitlines():
        f = line.split(",")
        if len(f) >= 3 and f[0] not in ("", "<not counted>", "<not supported>"):
            events.append(f[2])
    if "instructions" not in events:
        downgraded = sorted(e for e in events if e.startswith("instructions:"))
        if downgraded:
            raise InfraError(
                f"perf preflight counted only {', '.join(downgraded)} — the container lacks "
                "kernel-scope PMU permission (perf_event_paranoid >= 2 without effective "
                "CAP_PERFMON); refusing a metric that would not match the sealed contract")
        raise InfraError("perf preflight produced no usable `instructions` count "
                         "(PMU unavailable in this container?)")


def _time_replay(export_file, work, env, timeout, target=None):
    """One full-closure or explicit-target replay.

    The trusted timer emits the replay-only monotonic wall duration. Under
    metric=perf_instructions it is also passed `--count-instructions`, so it opens its own
    hardware instruction counter (perf_event_open + ioctl) only around the selected replay
    and reports the count in the same record.
    The outer watchdog still includes untimed preparation; timeout metadata says so explicitly.
    Returns (rc, out, sample_dict).
    """
    timer_cmd = _timer_command(export_file, target)
    if TIMING_METRIC == "perf_instructions":
        # The timer manages its own PMU counter (perf_event_open + ioctl) around the
        # replay window and reports the instruction count in its measurement record.
        # This replaces the `perf stat -D -1` + prctl scheme, whose delayed enable never
        # armed the perf-owned counter (prctl only enables events the caller opened).
        rc, out = run(timer_cmd, work, env, timeout)
        if rc == "timeout":
            return rc, out, _timeout_measurement(target, "local-process-watchdog")
        if rc != 0:
            return rc, out, {}
        measured = _parse_timer_measurement(out, target)
        return rc, out, {
            "instructions": measured["instructions"],
            "task_clock_ms": None,
            "wall_ns": measured["wall_ns"],
            "wall_s": measured["wall_ns"] / 1_000_000_000,
            "peak_rss_kb": measured["peak_rss_kb"],
            "measurement_contract": MEASUREMENT_CONTRACT,
            "measurement_boundary": measured["boundary"],
            "measurement_target": target,
        }
    else:
        rc, out = run(timer_cmd, work, env, timeout)
        if rc == "timeout":
            return rc, out, _timeout_measurement(target, "local-process-watchdog")
        if rc != 0:
            return rc, out, {}
        measured = _parse_timer_measurement(out, target)
        return rc, out, {
            "wall_ns": measured["wall_ns"],
            "wall_s": measured["wall_ns"] / 1_000_000_000,
            "peak_rss_kb": measured["peak_rss_kb"],
            "measurement_contract": MEASUREMENT_CONTRACT,
            "measurement_boundary": measured["boundary"],
            "measurement_target": target,
        }


def _remote_response_error(data, reps, target=None):
    """Return None for a usable resource-bound KTP/3 response."""
    if not isinstance(data, dict):
        return "response is not a JSON object"
    expected_boundary = _measurement_boundary(target)
    if data.get("measurement_contract") != MEASUREMENT_CONTRACT:
        return "missing/mismatched measurement contract"
    if data.get("boundary") != expected_boundary:
        return "missing/mismatched measurement boundary"
    if "target" not in data or data["target"] != target:
        return "missing/mismatched measurement target"
    status = data.get("status")
    if status not in ("ok", "timeout", "resource-limit", "failed"):
        return f"unrecognized status {status!r}"
    executor = data.get("executor")
    version = data.get("version")
    if not isinstance(executor, str) or not executor.strip():
        return "missing/invalid executor identity"
    if not isinstance(version, str) or not version.strip():
        return "missing/invalid executor version"
    if data.get("memory_mb") != REPLAY_MEMORY_MB:
        return "missing/mismatched executor memory limit"
    if status == "resource-limit":
        if data.get("resource") != "memory":
            return "remote resource limit is not identified as memory"
        if data.get("resource_phase") not in {
                "parse", "preload", "replay", "whole-process"}:
            return "remote resource limit has an invalid phase"
    if status != "ok":
        return None
    samples = data.get("samples")
    if not isinstance(samples, list) or len(samples) != reps:
        return f"expected exactly {reps} samples"
    for idx, sample in enumerate(samples):
        if not isinstance(sample, dict):
            return f"sample {idx} is not an object"
        instructions = sample.get("instructions")
        if type(instructions) is not int or instructions <= 0:
            return f"sample {idx} instructions must be a positive integer"
        wall_ns = sample.get("wall_ns")
        if wall_ns is not None and (type(wall_ns) is not int or wall_ns <= 0):
            return f"sample {idx} wall_ns must be a positive integer"
        task_clock = sample.get("task_clock_ms")
        if (task_clock is not None
                and (isinstance(task_clock, bool)
                     or not isinstance(task_clock, (int, float))
                     or not math.isfinite(task_clock)
                     or task_clock <= 0)):
            return f"sample {idx} task_clock_ms must be a positive finite number"
    return None


def _time_remote(export_file, reps, target=None, budget_s=None, deadline=None,
                 timeout_cap=None):
    """Run all timing reps on a remote resource-bound KTP/3 executor.

    Returns the executor's decoded 200 response: {"status": "ok", "samples":
    [{"instructions": …, "task_clock_ms": …}, …]} or a terminal
    {"status": "timeout"|"resource-limit"|"failed", …}. Anything that prevents obtaining a 200
    (connection failure, 5xx, auth/param 4xx, undecodable body) is treated as
    "executor unavailable": every URL is tried per attempt, attempts are
    separated by short sleeps, and exhaustion raises TimingRetry — never an
    error verdict, so an executor outage can only delay a score, not destroy
    a submission."""
    if budget_s is not None and deadline is not None:
        raise InfraError("remote timing received both a relative and absolute deadline")
    if deadline is None and budget_s is not None:
        deadline = time.monotonic() + budget_s

    # A budget already exhausted before dispatch is attributable to earlier contestant work.
    # Once dispatch starts, failure to obtain a valid executor response is infrastructure and
    # must remain retryable even if the remaining phase time expires during transport/backoff.
    if budget_s is not None and budget_s <= 0:
        raise PerfBudgetExhausted(
            "performance-phase budget exhausted before remote timing")

    if deadline is not None and deadline <= time.monotonic():
        raise PerfBudgetExhausted(
            "performance-phase budget exhausted before remote timing")
    export_bytes = export_file.read_bytes()
    digest = hashlib.sha256(export_bytes).hexdigest()
    if deadline is not None and deadline <= time.monotonic():
        raise PerfBudgetExhausted(
            "performance-phase budget exhausted while preparing remote timing input")

    def remaining():
        if deadline is None:
            return None
        return deadline - time.monotonic()

    last_err = "no executor URLs configured"
    # Restrict to the pinned node once one has served this submission (else the full list).
    urls = [_PINNED_EXECUTOR[0]] if _PINNED_EXECUTOR[0] else TIMING_EXECUTOR_URLS
    for sleep_s in _EXECUTOR_ATTEMPT_SLEEPS:
        if sleep_s:
            rem = remaining()
            if rem is not None and (rem <= 0 or sleep_s >= rem):
                raise TimingRetry(
                    f"timing executor unavailable until phase deadline (last: {last_err})")
            time.sleep(sleep_s)
        for base in urls:
            rem = remaining()
            if rem is not None and rem <= 0:
                raise TimingRetry(
                    f"timing executor unavailable until phase deadline (last: {last_err})")
            per_replay_timeout = min(
                TIMING_TIMEOUT,
                timeout_cap if timeout_cap is not None else TIMING_TIMEOUT,
            )
            if rem is not None:
                per_replay_timeout = max(
                    1, min(per_replay_timeout, int(rem / max(reps, 1))))
            request_timeout = reps * per_replay_timeout + 120
            if rem is not None:
                request_timeout = max(0.001, min(request_timeout, rem))
            boundary = _measurement_boundary(target)
            query = urllib.parse.urlencode({
                "reps": reps,
                "timeout_secs": per_replay_timeout,
                "measurement_contract": MEASUREMENT_CONTRACT,
                "boundary": boundary,
                "target": target or "",
                "memory_mb": REPLAY_MEMORY_MB,
            })
            url = f"{base}/ktp/v3/time?{query}"
            req = urllib.request.Request(url, data=export_bytes, method="POST", headers={
                "Authorization": f"Bearer {TIMING_EXECUTOR_SECRET}",
                "Content-Type": "application/octet-stream",
                "X-Export-SHA256": digest,
                "X-Measurement-Contract": MEASUREMENT_CONTRACT,
                "X-Measurement-Boundary": boundary,
                "X-Measurement-Target": target or "",
                "X-Replay-Memory-MB": str(REPLAY_MEMORY_MB),
            })
            try:
                with urllib.request.urlopen(req, timeout=request_timeout) as resp:
                    body = resp.read()
                data = json.loads(body)
                schema_error = _remote_response_error(data, reps, target)
                if schema_error is not None:
                    last_err = f"{base}: invalid executor response ({schema_error})"
                    continue
                identity = (data["executor"], data["version"])
                pinned_identity = _PINNED_EXECUTOR_IDENTITY[0]
                if pinned_identity is not None and identity != pinned_identity:
                    last_err = (
                        f"{base}: executor identity changed from "
                        f"{pinned_identity[0]}/{pinned_identity[1]} to "
                        f"{identity[0]}/{identity[1]}")
                    continue
                # A validated kernel failure is fatal evidence and must never be softened into
                # a contestant budget exhaustion merely because transport returned late.
                if (data["status"] != "failed" and deadline is not None
                        and deadline <= time.monotonic()):
                    raise PerfBudgetExhausted(
                        "performance-phase budget expired before the remote result arrived")
                # Pin only after the entire response is validated. A malformed `status=ok`
                # therefore cannot capture the submission and suppress a healthy standby.
                _PINNED_EXECUTOR[0] = base
                _PINNED_EXECUTOR_IDENTITY[0] = identity
                data["executor_url"] = base
                return data
            except urllib.error.HTTPError as e:
                # Auth/param 4xx and executor 5xx alike: a misconfiguration is
                # an operator problem to fix, not a reason to void the
                # submission — keep it queued and visible in logs.
                detail = ""
                try:
                    detail = e.read(300).decode(errors="replace")
                except Exception:
                    pass
                last_err = f"{base}: HTTP {e.code} {detail}".strip()
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                last_err = f"{base}: {e}"
            print(f"timing executor unavailable: {last_err}", file=sys.stderr)
    raise TimingRetry(f"all timing executors unavailable (last: {last_err})")


# Reference value v = impl n by ELABORATOR-side reduction (Meta `whnf`), NOT compiled `#eval`.
# `#eval` runs codegen output, which can be exponential even when the kernel reduction is
# cheap (the naive fib spec compiles to an exponential tree but reduces via `brecOn` in
# linear kernel time) — so a submission fast in the kernel could be un-evaluable by #eval.
# `Meta.whnf` is the elaborator's reduction engine, not the kernel's (the kernel does expose its
# own `Kernel.whnf`, but core documents it as a debugging entry point, and the oracle needs no
# trust either way); it only PROPOSES the literal, handling Nat and Int results, and the kernel
# redoes the whole computation when it checks the generated theorem. A wrong v cannot mis-score: the
# kernel-checked proof in _perf_export would then fail to build — as would a rare
# whnf/kernel divergence, an unscored failure rather than a wrong score.
_VALUE_OUTPUT = "EvalValue.out"
_VALUE_META = r"""import Submission
import Lean
open Lean Meta
set_option maxRecDepth 4000000
set_option maxHeartbeats 0
run_meta do
  let e0 ← whnf (mkApp (mkConst ``Submission.impl) (mkNatLit __N__))
  match e0 with
  | .lit (.natVal v) => IO.FS.writeFile "EvalValue.out" s!"{v}"
  | .app (.const ``Int.ofNat _) a =>
    match (← whnf a) with
    | .lit (.natVal v) => IO.FS.writeFile "EvalValue.out" s!"{v}"
    | _ => IO.FS.writeFile "EvalValue.out" "NONLIT"
  | .app (.const ``Int.negSucc _) a =>
    match (← whnf a) with
    | .lit (.natVal v) => IO.FS.writeFile "EvalValue.out" s!"-{v + 1}"
    | _ => IO.FS.writeFile "EvalValue.out" "NONLIT"
  | _ => IO.FS.writeFile "EvalValue.out" "NONLIT"
"""


def _eval_impl_value(work, env, n, timeout, lean_bin="lean"):
    """Reduce `impl n` to a literal via the elaborator-side oracle above. Returns (kind, payload):
    ('ok', v) with v a decimal string; ('timeout', None) only when the real wall-clock budget
    expires; ('error', tail) for every deterministic Lean/oracle failure. Heartbeats are disabled
    in _VALUE_META so the process timeout is the oracle's sole computation budget."""
    value_path = work / _VALUE_OUTPUT
    try:
        value_path.unlink(missing_ok=True)
    except OSError as e:
        return "error", f"cannot clear stale value-oracle output: {e}"
    (work / "EvalVal.lean").write_text(_VALUE_META.replace("__N__", str(n)))
    rc, out = run([str(lean_bin), "EvalVal.lean"], work, env, timeout)
    if rc == "timeout":
        return "timeout", None
    if _attested_local_memory_kill(rc):
        return "resource-limit", None
    if rc != 0:
        return "error", last_line(out)
    try:
        value = value_path.read_text().strip()
    except (OSError, UnicodeError) as e:
        return "error", f"value oracle produced no readable result: {e}; {last_line(out)}"
    if re.fullmatch(r"-?(0|[1-9][0-9]*)", value):
        return "ok", value
    if value == "NONLIT":
        return "error", "value oracle produced no literal (NONLIT)"
    preview = value[:120] + ("…" if len(value) > 120 else "")
    return "error", f"value oracle produced an invalid integer literal ({preview!r})"


def _perf_theorem_source(n, v, nonce):
    """Return (Lean source, fully-qualified theorem name) for one generated timing theorem.

    The namespace suffix includes a per-job nonce (normally the random export path), so an
    imported contestant declaration cannot collide with the generated theorem's global name.
    """
    token = hashlib.sha256(f"{nonce}\0{n}\0{v}".encode()).hexdigest()[:24]
    namespace = f"LeanKernelChallengeJudge.Generated_{token}"
    theorem = f"{namespace}.check"
    # EXPERIMENT (branch problem/sha256): the target theorem `impl n = v := Eq.refl v` is
    # added via `Lean.addDecl`, so the KERNEL alone type-checks it. Neither source-level
    # encoding works everywhere: `of_decide_eq_true (rfl : decide (...) = true)` makes the
    # elaborator normalize the decide application (Meta.whnf recursion mirrors term nesting →
    # stack overflow on deep-DAG specs like sha256, and still > maxRecDepth 4000000 with a
    # 2 GiB stack), while a source-level bare `rfl` sends the elaborator's isDefEq down
    # lazy-delta unfolding that pathologically slows on fib-shaped impls at large n. The
    # generator below does only inferType/mkNatLit/mkEq — no deep Meta reduction — and the
    # kernel replays the identical `Eq.refl` theorem either source form would produce.
    value = str(v)
    if value.startswith("-"):
        rhs = f"Lean.mkApp (Lean.mkConst ``Int.negSucc) (Lean.mkNatLit {int(value[1:]) - 1})"
    else:
        # Output type decided at generator runtime: Nat gets a raw literal, Int gets Int.ofNat.
        rhs = (f"if outIsInt then Lean.mkApp (Lean.mkConst ``Int.ofNat) (Lean.mkNatLit {value}) "
               f"else Lean.mkNatLit {value}")
    source = (
        "import Submission\n"
        "import Lean\n"
        "set_option maxRecDepth 4000000\n"
        "set_option maxHeartbeats 0\n"
        "open Lean Meta Elab in\n"
        "run_meta do\n"
        "  let implC := Lean.mkConst ``Submission.impl\n"
        f"  let lhs := Lean.mkApp implC (Lean.mkNatLit {n})\n"
        "  let out ← whnf (← inferType implC).bindingBody!\n"
        "  let outIsInt := out.isConstOf ``Int\n"
        "  unless outIsInt || out.isConstOf ``Nat do\n"
        "    throwError \"unsupported impl output type {out}\"\n"
        f"  let rhs := {rhs}\n"
        "  let ty ← mkEq lhs rhs\n"
        "  let pf ← mkEqRefl rhs\n"
        "  Lean.addDecl (.thmDecl {\n"
        f"    name := `{theorem},\n"
        "    levelParams := [],\n"
        "    type := ty,\n"
        "    value := pf })\n"
    )
    return source, theorem


def _perf_export(work, env, n, v, out_path, timeout, artifact_lib, lean_bin, deadline=None):
    """Build and export a uniquely namespaced, directly reducible `impl n = v` theorem.

    The generated `Eq.refl` theorem is added directly as a declaration, so the exported target
    contains the computation instead of referring to an untimed extracted proof helper. Kernel
    replay therefore reduces `impl n` at this specific n. Returns
    (kind, error, fully_qualified_theorem): 'ok';
    'timeout' when this slot's build/export is too slow; 'resource-limit' when its process is
    killed by the memory cgroup; 'budget-exhausted' when the shared phase deadline expires; or 'error' for a
    non-timeout build/export failure — which includes a wrong reference `v` (the direct proof
    then fails to prove `impl n = v` *deterministically*, so it is errored, not scored). The
    caller records only wall-clock timeouts as unsuccessful slots and continues with later
    slots; a wrong value fails deterministically far inside the timing budget, so it never
    reaches that timeout path in practice."""
    source, theorem = _perf_theorem_source(n, v, out_path)
    # Compilation and export are one preparation stage and share this cap.  Giving
    # each subprocess a fresh full timeout would silently double the published
    # infrastructure allowance for every case.
    build_export_deadline = time.monotonic() + timeout

    def remaining_build_export():
        now = time.monotonic()
        if deadline is not None and now >= deadline:
            return 0.0, "budget-exhausted"
        remaining = build_export_deadline - now
        if deadline is not None:
            remaining = min(remaining, deadline - now)
        return max(0.0, remaining), "timeout"

    (work / "Perf.lean").write_text(source)
    perf_olean = artifact_lib / "Perf.olean"
    if perf_olean.exists():
        try:
            perf_olean.chmod(0o644)
            perf_olean.unlink()
        except OSError as e:
            return "error", f"cannot replace generated Perf.olean at n={n}: {e}", theorem
    # Compile only the judge-owned theorem. `import Submission` resolves to the byte-pinned
    # comparator artifact; no contestant source is re-elaborated in the performance phase.
    step_timeout, expired_kind = remaining_build_export()
    if step_timeout <= 0:
        return expired_kind, None, theorem
    rc, out = run(
        [str(lean_bin), "-o", str(perf_olean), "Perf.lean"],
        work, env, step_timeout)
    if rc == "timeout":
        # This build timeout is distinct from the later timer process watchdog.
        return "timeout", None, theorem
    if _attested_local_memory_kill(rc):
        return "resource-limit", None, theorem
    if rc != 0:
        # The oracle already produced a value, so the build should succeed. Any DETERMINISTIC
        # failure is a fault, never a timeout. In particular, a wrong oracle value makes the
        # direct equality theorem fail kernel checking, so it can never be scored.
        return "error", f"perf build failed at n={n}: {last_line(out)}", theorem
    step_timeout, expired_kind = remaining_build_export()
    if step_timeout <= 0:
        return expired_kind, None, theorem
    rc, out = run([str(LEAN4EXPORT_BIN / "lean4export"), "Perf", "--", theorem],
                  work, env, step_timeout, stdout_path=out_path)
    if rc == "timeout":
        return "timeout", None, theorem
    if _attested_local_memory_kill(rc):
        return "resource-limit", None, theorem
    if rc != 0:
        return "error", f"perf export failed at n={n}: {last_line(out)}", theorem
    if not out_path.exists() or out_path.stat().st_size == 0:
        return "error", f"perf export produced no output at n={n}", theorem
    return "ok", None, theorem


def _submission_digest(work):
    """SHA-256 over the contestant's Submission.lean, so the perf phase can prove the `impl` it
    times is byte-identical to the one
    comparator verified `impl_correct : ∀n` against — an axiom-clean but different impl,
    swapped in after verification, has a different digest and is rejected as a fault."""
    h = hashlib.sha256()
    paths = [work / "Submission.lean"]
    for p in paths:
        h.update(p.relative_to(work).as_posix().encode() + b"\0")
        try:
            h.update(p.read_bytes())
        except OSError as e:
            # Fail closed: an unreadable submission file cannot be bound, so it must not hash
            # to a fixed sentinel that a mutated tree could reproduce.
            raise InfraError(f"cannot read submission file '{p.name}' for identity binding: {e}")
        h.update(b"\0")
    return h.hexdigest()


def _pin_export_bytes(path):
    """Read and make an export read-only; callers compare these exact bytes after each consumer."""
    try:
        pinned = path.read_bytes()
        path.chmod(0o444)
        return pinned
    except OSError as e:
        raise InfraError(f"cannot pin export '{path.name}': {e}")


def _export_matches(path, pinned):
    try:
        return path.read_bytes() == pinned
    except OSError as e:
        raise InfraError(f"cannot re-read pinned export '{path.name}': {e}")


def _snapshot_verified_artifacts(work):
    """Pin the `.olean` graph that produced the comparator-verified export.

    Performance checks import this graph directly; they never re-elaborate Submission source.
    That matters because elaboration can depend on environment, time, or filesystem state even
    when the source digest is unchanged.
    """
    lib = work / ".lake" / "build" / "lib" / "lean"
    if not lib.is_dir():
        raise InfraError("comparator accepted but produced no Lean build artifact directory")
    # These names are judge-owned scratch modules, never contestant modules.
    for name in ("Perf.olean", "EvalVal.olean"):
        path = lib / name
        if path.exists():
            try:
                path.chmod(0o644)
                path.unlink()
            except OSError as e:
                raise InfraError(f"cannot clear stale generated artifact '{name}': {e}")

    files = sorted(lib.rglob("*.olean"), key=lambda p: p.relative_to(lib).as_posix())
    if not files or not (lib / "Submission.olean").is_file():
        raise InfraError("comparator accepted but emitted no Submission.olean")
    snapshot = {}
    digest = hashlib.sha256()
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise InfraError(f"invalid verified build artifact '{path.name}'")
        rel = path.relative_to(lib).as_posix()
        try:
            payload = path.read_bytes()
            path.chmod(0o444)
        except OSError as e:
            raise InfraError(f"cannot pin verified build artifact '{rel}': {e}")
        snapshot[rel] = payload
        digest.update(rel.encode() + b"\0" + payload + b"\0")
    return lib, snapshot, digest.hexdigest()


def _artifacts_match(lib, snapshot):
    for rel, payload in snapshot.items():
        path = lib / rel
        try:
            if path.is_symlink() or path.read_bytes() != payload:
                return False
        except OSError:
            return False
    return True


def _prepare_generated_workspace(work, artifact_lib):
    """Open only the directories/files needed for judge-generated modules.

    Verified `.olean` files stay read-only and byte-pinned. The root and artifact directory
    must be writable so Lean can receive EvalVal.lean/Perf.lean and the generated Perf.olean.
    """
    for path in (
        work,
        work / ".lake",
        work / ".lake" / "build",
        work / ".lake" / "build" / "lib",
        artifact_lib,
    ):
        try:
            path.chmod(0o755)
        except OSError as e:
            raise InfraError(f"cannot prepare generated-module directory '{path.name}': {e}")
    for name in ("EvalVal.lean", "Perf.lean"):
        path = work / name
        if path.exists():
            try:
                path.chmod(0o644)
            except OSError as e:
                raise InfraError(f"cannot prepare generated source '{name}': {e}")


def _remote_sample(remote_sample):
    """One KTP/3 executor sample in the shape the local timer produces.

    The executor reports the instruction count (its scored value), the
    diagnostic task clock and wall time, and — when it runs the peak-RSS timer
    — the replay window's RSS high-water mark. Keeping ``peak_rss_kb`` here
    lets the summary and the retained samples of a remotely timed run carry
    the same peak a locally timed run records; an executor that predates the
    field simply yields samples without it, and the summary then omits the
    peak rather than inventing one.
    """
    sample = {
        "instructions": remote_sample["instructions"],
        "task_clock_ms": remote_sample.get("task_clock_ms"),
    }
    if "wall_ns" in remote_sample:
        sample["wall_ns"] = remote_sample["wall_ns"]
        sample["wall_s"] = remote_sample["wall_ns"] / 1_000_000_000
    peak_rss_kb = remote_sample.get("peak_rss_kb")
    if type(peak_rss_kb) is int and peak_rss_kb > 0:
        sample["peak_rss_kb"] = peak_rss_kb
    return sample


def _retained_sample(sample):
    """The measured values of one timed replay, kept verbatim for audit.

    Only the measurements themselves are retained (instructions, wall_ns,
    peak_rss_kb); the contract, boundary and target already sit on the record
    that summarizes the series. A value the timer could not report (a remote
    executor sample carries no peak, the non-Linux stub reports None) is
    omitted rather than written as null, so every retained sample is a plain
    subset of the same three keys.
    """
    retained = {}
    for key in ("instructions", "wall_ns", "peak_rss_kb"):
        value = sample.get(key)
        if type(value) is int and value > 0:
            retained[key] = value
    return retained


def _summarize_samples(samples, metric=None):
    metric = metric or TIMING_METRIC
    summary = {}
    # Every timed replay is retained next to its summary, in measurement order,
    # so a reader can re-derive the median and the worst peak from the raw
    # repetitions and a leaderboard can show the individual replays behind them.
    summary["samples"] = [_retained_sample(s) for s in samples]
    # Peak replay RSS comes from the local in-timer window only; remote executor
    # samples do not carry it and the non-Linux stub reports None. Surface the
    # worst rep when every sample reports one, so a remote or platform-mixed
    # series stays valid without it.
    peaks = [s.get("peak_rss_kb") for s in samples]
    if peaks and all(type(p) is int and p > 0 for p in peaks):
        summary["peak_rss_kb"] = max(peaks)
    if metric == "perf_instructions":
        insns = [s["instructions"] for s in samples]
        median = statistics.median(insns)
        # Instruction counts are integral. Round .5 upward instead of Python's banker's round.
        summary["median_instructions"] = int(math.floor(median + 0.5))
        return summary
    # Preserve the timer's nanosecond resolution. Target-only checks can complete well below
    # one millisecond, so the old three-decimal rounding could turn valid samples into score 0.
    median_ns = statistics.median([s["wall_ns"] for s in samples])
    summary["median_wall_ns"] = median_ns
    summary["median_s"] = median_ns / 1_000_000_000
    return summary


def _coverage_fields(inputs, scaling):
    completed = [row for row in scaling if row.get("result") == "ok"]
    total = len(inputs)
    return {
        "successful_slots": len(completed),
        "total_slots": total,
        "coverage": (len(completed) / total) if total else 0.0,
    }


def _headline_row(scaling):
    completed = [row for row in scaling if row.get("result") == "ok"]
    return max(completed, key=lambda row: row["n"]) if completed else None


def _plan_slot_annotations(performance_plan, slot, n):
    if performance_plan is None:
        return {}
    if not isinstance(performance_plan, list) or slot >= len(performance_plan):
        raise InfraError("performance plan does not cover every input slot")
    planned = performance_plan[slot]
    if not (isinstance(planned, dict)
            and planned.get("slot") == slot
            and type(planned.get("n")) is int and planned["n"] == n
            and isinstance(planned.get("group"), str)
            and type(planned.get("case")) is int and planned["case"] >= 0):
        raise InfraError(f"invalid performance plan row for slot {slot}")
    return {"group": planned["group"], "case": planned["case"]}


def _performance_timeout_caps(performance_plan, n):
    """Return independent preparation and scored-replay caps for one slot.

    A group's published ``timeout_seconds`` limits only the measured target
    replay. The unscored value oracle and theorem build/export retain the
    evaluator timing timeout, while the axiom audit retains its audit timeout.
    Legacy callers may additionally intersect these caps with their aggregate
    development deadline. Grouped-v2 cases deliberately do not share one.
    """
    point_limits = {}
    if performance_plan is not None:
        point_limits = next(
            (row.get("limits", {}) for row in performance_plan
             if isinstance(row, dict) and row.get("n") == n),
            {},
        )
    replay_timeout = min(
        TIMING_TIMEOUT,
        point_limits.get("timeout_seconds", TIMING_TIMEOUT),
    )
    return {
        "value_eval": TIMING_TIMEOUT,
        "build_export": TIMING_TIMEOUT,
        "axiom_audit": AUDIT_TIMEOUT,
        "target_replay": replay_timeout,
    }


def _collect_perf_slots(inputs, probe, deadline=None, performance_plan=None):
    """Probe every configured slot unless a deterministic fatal error is returned.

    `probe(n)` returns `(row, error)`. Timeout rows carry no error and therefore never suppress
    later inputs; a deterministic fault returns an error and terminates the curve.

    When supplied for a legacy-v1 schedule, `deadline` (monotonic seconds) bounds the whole
    performance phase. On exhaustion the remaining legacy slots are recorded as
    `budget-exhausted`. Grouped-v2 schedules always pass ``None`` because their cases are
    independently bounded and an aggregate cutoff would make scores depend on case order.
    """
    scaling = []
    for slot, n in enumerate(inputs):
        annotations = _plan_slot_annotations(performance_plan, slot, n)
        if deadline is not None and time.monotonic() >= deadline:
            for later_slot, later_n in enumerate(inputs[slot:], start=slot):
                later_annotations = _plan_slot_annotations(
                    performance_plan, later_slot, later_n)
                scaling.append({
                    "slot": later_slot, **later_annotations,
                    "n": later_n, "result": "budget-exhausted",
                })
            return scaling, None
        # Pass a legacy deadline down: capping only BETWEEN slots would let one slot chain
        # several per-step timeouts and overshoot that development budget.
        row, error = probe(n, deadline) if deadline is not None else probe(n)
        if row is not None:
            # Judge-owned identity fields win even if a future probe accidentally returns one.
            row = {**row, "slot": slot, **annotations}
            scaling.append(row)
        if error is not None:
            for later_slot, later_n in enumerate(inputs[slot + 1:], start=slot + 1):
                later_annotations = _plan_slot_annotations(
                    performance_plan, later_slot, later_n)
                scaling.append({
                    "slot": later_slot, **later_annotations,
                    "n": later_n, "result": "not-run",
                })
            return scaling, error
    return scaling, None


def _performance_phase_deadline(performance_plan):
    """Return the legacy aggregate deadline, or ``None`` for grouped cases.

    Every grouped-v2 case has its own sealed preparation and replay limits.  An
    aggregate deadline would make later case outcomes depend on the work spent by
    earlier cases, so it is intentionally retained only for legacy-v1 development
    schedules (currently ``conv``).
    """
    if performance_plan is not None or not PERF_PHASE_BUDGET:
        return None
    return time.monotonic() + PERF_PHASE_BUDGET


def _canonical_work(correctness_timing, scaling, metric=None):
    """Structured work components; ranking/aggregation is intentionally left to scoring."""
    metric = metric or TIMING_METRIC
    key = "median_instructions" if metric == "perf_instructions" else "median_s"
    if correctness_timing.get("result") != "ok" or correctness_timing.get(key) is None:
        return None
    curve_values = [
        row[key] for row in scaling
        if row.get("result") == "ok" and row.get(key) is not None
    ]
    correctness = correctness_timing[key]
    curve_sum = sum(curve_values)
    return {
        "metric": metric,
        "correctness_median": correctness,
        "completed_curve_sum": curve_sum,
        "total": correctness + curve_sum,
        "completed_slots": len(curve_values),
    }


def _problem_bundle_digest(problem):
    """Hash the locked files that define one problem and its build environment."""
    base = PROBLEMS / problem
    if not base.is_dir():
        raise InfraError(f"unknown problem '{problem}'")
    digest = hashlib.sha256()
    files = []
    for path in base.rglob("*"):
        rel = path.relative_to(base)
        if ".lake" in rel.parts or rel.as_posix() in ("Submission.lean", "lake-manifest.json"):
            continue
        if path.is_symlink():
            raise InfraError(f"problem bundle contains a symlink ({rel.as_posix()})")
        if path.is_file():
            files.append(path)
    for path in sorted(files, key=lambda p: p.relative_to(base).as_posix()):
        rel = path.relative_to(base).as_posix()
        try:
            payload = path.read_bytes()
        except OSError as e:
            raise InfraError(f"cannot hash problem file '{rel}': {e}")
        digest.update(rel.encode() + b"\0" + payload + b"\0")
    if not files:
        raise InfraError(f"problem bundle '{problem}' contains no locked files")
    return digest.hexdigest()


def _evaluator_bundle_digest():
    """Hash the repository files that define judging, timing, scoring, and isolation policy."""
    paths = [
        ROOT / "Dockerfile",
        ROOT / "judge" / "judge.py",
        ROOT / "judge" / "timer-kernel" / "Main.lean",
        ROOT / "judge" / "timer-kernel" / "timer_control.c",
        ROOT / "judge" / "timer-kernel" / "lakefile.lean",
        ROOT / "pipeline" / "config.json",
        ROOT / "lean-toolchain",
        ROOT / "scripts" / "run_isolated.sh",
        ROOT / "scripts" / "setup.sh",
        ROOT / "scripts" / "score.py",
        ROOT / "patches" / "comparator-emit-export.patch",
    ]
    digest = hashlib.sha256()
    for path in paths:
        try:
            payload = path.read_bytes()
        except OSError as e:
            raise InfraError(f"cannot hash evaluator file '{path.relative_to(ROOT)}': {e}")
        rel = path.relative_to(ROOT).as_posix()
        digest.update(rel.encode() + b"\0" + payload + b"\0")
    return digest.hexdigest()


def _evaluation_cohort(problem, cfg, inputs, reps, result, performance_plan=None):
    """Return the public comparison cohort recorded in every current verdict.

    The round label is operator supplied. The derived id commits to the exact schedule, problem
    bundle, budgets, resource envelope, toolchain, measurement contract, and executor identity.
    """
    round_id = EVALUATION_COHORT or "local-dev"
    executor = result.get("stages", {}).get("timing_executor") or {
        "kind": "local",
        "executor": EVALUATION_EXECUTOR_ID,
        "version": EVALUATION_EXECUTOR_VERSION,
    }
    common = {
        "round": round_id,
        "problem": problem,
        "problem_bundle_sha256": _problem_bundle_digest(problem),
        "evaluator_bundle_sha256": _evaluator_bundle_digest(),
        "evaluation_mode": "official" if OFFICIAL_EVAL else "development",
        "inputs": inputs,
        "metric": TIMING_METRIC,
        "reps": reps,
        "budgets": {
            "comparator_timeout_seconds": COMPARATOR_TIMEOUT,
            "audit_timeout_seconds": AUDIT_TIMEOUT,
            "timing_timeout_seconds": TIMING_TIMEOUT,
            "perf_phase_budget_seconds": PERF_PHASE_BUDGET,
        },
        "resource_policy": dict(EVALUATION_RESOURCE_POLICY),
        "toolchain": _CFG.get("toolchain"),
        "checker": CHECKER_ID,
        "timing_protocol": result.get("timing_protocol"),
        "measurement_contract": _measurement_contract_record(),
        "executor": executor,
    }
    evaluation = cfg.get("evaluation")
    if evaluation is None:
        if performance_plan is not None:
            raise InfraError("legacy evaluation policy cannot carry a grouped performance plan")
        policy = {
            "schema": "evaluation-policy-v1",
            **common,
            "perf": cfg.get("perf"),
            "perf_defaults": {
                key: _PERF_DEFAULTS.get(key) for key in ("count", "spacing", "jitter")
            },
        }
    else:
        if not isinstance(performance_plan, list) or not performance_plan:
            raise InfraError("grouped evaluation policy requires a resolved performance plan")
        if [row.get("n") for row in performance_plan if isinstance(row, dict)] != inputs:
            raise InfraError("resolved performance plan does not match evaluation inputs")
        plan_encoded = json.dumps(
            performance_plan, sort_keys=True, separators=(",", ":"),
            allow_nan=False).encode()
        policy = {
            "schema": "evaluation-policy-v2",
            **common,
            "budgets": {
                **common["budgets"],
                # Grouped cases are independently bounded.  Zero is an explicit,
                # sealed statement that no order-dependent aggregate deadline applies.
                "perf_phase_budget_seconds": 0,
            },
            "evaluation": evaluation,
            "performance_plan": performance_plan,
            "performance_plan_sha256": hashlib.sha256(plan_encoded).hexdigest(),
            "seed_commitment": _seed_commitment(),
        }
    encoded = json.dumps(
        policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {
        "id": hashlib.sha256(encoded).hexdigest()[:24],
        "round": round_id,
        "executor": executor,
        "policy_sha256": hashlib.sha256(encoded).hexdigest(),
        "policy": policy,
    }


def judge(job_dir: Path, problem, submission_dir, reps, tag):
    sub_name = tag or Path(submission_dir).name
    timing_protocol = (
        REMOTE_PROTOCOL
        if TIMING_METRIC == "perf_instructions" and TIMING_EXECUTOR_URLS
        else "local-v2"
    )
    run_id = EVALUATION_RUN_ID or job_dir.name
    result = {"problem": problem, "submission": sub_name, "run_id": run_id,
              "status": None, "reason": None, "metric": TIMING_METRIC, "stages": {},
              "evaluation_mode": "official" if OFFICIAL_EVAL else "development",
              "timing_protocol": timing_protocol,
              "measurement_contract": _measurement_contract_record()}

    def finish():
        _store_verdict(
            problem,
            sub_name,
            result,
            promote=result["status"] in ("accepted", "rejected"),
        )
        icon = {"accepted": "✅", "rejected": "❌", "error": "💥"}[result["status"]]
        sc = result.get("score")
        print(f"{icon} {problem}/{sub_name}: {result['status']}"
              + (f" — {result['reason']}" if result["reason"] else "")
              + (f" — {sc}" if sc else ""))
        return 0 if result["status"] in ("accepted", "rejected") else 2

    # A process normally judges one submission, but resetting here also makes repeated in-process
    # invocations safe: executor identity must never leak from a prior job.
    _PINNED_EXECUTOR[0] = None
    _PINNED_EXECUTOR_IDENTITY[0] = None
    if _official_eval() and not PERF_SEED:
        raise InfraError("official evaluation requires a nonempty PERF_SEED")
    if OFFICIAL_EVAL and _PERF_SEED_SOURCE[0] != "stdin":
        raise InfraError("official evaluation requires one-shot PERF_SEED stdin injection")
    if OFFICIAL_EVAL and not EVALUATION_COHORT:
        raise InfraError("official evaluation requires a nonempty EVALUATION_COHORT")
    if OFFICIAL_EVAL and not valid_slug(EVALUATION_RUN_ID):
        raise InfraError("official evaluation requires a valid EVALUATION_RUN_ID")
    if OFFICIAL_EVAL and TIMING_METRIC != "perf_instructions":
        raise InfraError("official evaluation requires TIMING_METRIC=perf_instructions")
    if OFFICIAL_EVAL and TIMING_EXECUTOR_URLS:
        raise InfraError("Stage 1 official evaluation requires in-container local PMU timing")
    if OFFICIAL_EVAL and (
            not EVALUATION_EXECUTOR_ID or EVALUATION_EXECUTOR_ID == "local"
            or not EVALUATION_EXECUTOR_VERSION
            or EVALUATION_EXECUTOR_VERSION == "fixed-host"):
        raise InfraError("official evaluation requires a pinned local PMU executor identity")
    image_id = EVALUATION_RESOURCE_POLICY.get("image", "")
    if (OFFICIAL_EVAL and not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)):
        raise InfraError("official evaluation requires an immutable Docker image ID")
    if OFFICIAL_EVAL and SANDBOX_MODE != "container":
        raise InfraError("official evaluation requires sandbox.mode=container")
    if OFFICIAL_EVAL and os.environ.get("ISOLATION_ATTESTATION") != "run_isolated.sh":
        raise InfraError("official evaluation must be launched via scripts/run_isolated.sh "
                         "(missing or invalid ISOLATION_ATTESTATION)")
    if OFFICIAL_EVAL and _read_cgroup_oom_kills() is None:
        raise InfraError("official evaluation requires cgroup-v2 memory.events OOM accounting")
    if OFFICIAL_EVAL and os.environ.get("TIMING_TIMEOUT_SECONDS"):
        # The dev knob would be silently sealed into the cohort budgets, contradicting the
        # published watchdog ceilings. Official runs take the checked-in value only.
        raise InfraError("official evaluation forbids the TIMING_TIMEOUT_SECONDS dev override")

    # Fail-closed sandbox policy: production must have a real sandbox.
    env = tool_env()
    if SANDBOX_MODE == "container":
        # Tool presence proves nothing: `landrun` and SANDBOX_MODE=container are both baked into
        # the image, so a bare `docker run IMAGE judge.py ...` (no isolation flags at all) used to
        # pass this check. Demand EVIDENCE of the envelope instead.
        if not has_real_landrun(env):
            raise InfraError("sandbox.mode=container but no real landrun on PATH "
                             "(refusing to run unsandboxed)")
        reachable = _network_is_reachable()
        if reachable:
            raise InfraError("sandbox.mode=container but the network is reachable — the container "
                             "was started without --network none (refusing to run unsandboxed)")
        result["stages"]["sandbox"] = {"mode": SANDBOX_MODE, "network_reachable": reachable}

    cfg = json.loads((PROBLEMS / problem / "config.json").read_text())
    resolved_plan = _validated_performance_plan(cfg, problem)
    work = assemble(job_dir, problem, submission_dir)
    axioms = cfg["permitted_axioms"]
    lean_bin, lean_prefix, core_lib = _resolve_lean_runtime(work, env)

    # Identity binding (1/2): pin the submission bytes BEFORE comparator reads them, so the
    # baseline is exactly what gets correctness-verified — not some post-verification state.
    verified_digest = _submission_digest(work)

    # ---- Comparator: correctness gate (statement match + axioms + kernel replay of ∀n) ----
    # The patched comparator writes the exact export it just verified (COMPARATOR_SOLUTION_EXPORT).
    # That export is the correctness artifact. The perf phase imports the exact byte-pinned
    # `.olean` graph that produced it, then separately builds and times judge-owned per-input
    # `impl n` exports. Source digests remain an additional mutation check.
    # A missing/uninstalled comparator is a DEPLOYMENT fault (→ infra error/exit 2), not a
    # contestant rejection: check explicitly so a nonzero exit isn't misread as "proof invalid".
    if not Path(COMPARATOR).exists():
        raise InfraError(f"comparator binary not found at {COMPARATOR} (run scripts/setup.sh)")
    export_file = job_dir / "solution.export.ndjson"
    cenv = dict(
        env,
        COMPARATOR_SOLUTION_EXPORT=str(export_file),
        COMPARATOR_LEAN4EXPORT=str(LEAN4EXPORT_BIN / "lean4export"),
    )
    t0 = time.monotonic()
    rc, out = run(["lake", "env", str(COMPARATOR), "config.json"], work, cenv, COMPARATOR_TIMEOUT)
    result["stages"]["comparator"] = {"exit": rc, "seconds": round(time.monotonic() - t0, 1),
                                      "tail": out[-3000:]}
    if rc == "timeout":
        _emit_stage_progress("comparator", "failed", t0)
        result["status"], result["reason"] = "rejected", f"comparator timed out (> {COMPARATOR_TIMEOUT}s)"
        return finish()
    if _attested_local_memory_kill(rc):
        _emit_stage_progress("comparator", "failed", t0)
        result["status"], result["reason"] = "rejected", \
            "correctness gate exceeded the 4 GiB memory envelope"
        return finish()
    if _died_by_signal(rc):
        _emit_stage_progress("comparator", "failed", t0)
        result["status"], result["reason"] = "error", \
            f"comparator killed by signal (exit {rc}) — infrastructure fault, not a proof failure"
        return finish()
    if rc != 0:
        _emit_stage_progress("comparator", "failed", t0)
        result["status"], result["reason"] = "rejected", f"comparator: {last_line(out)}"
        return finish()
    if not export_file.exists() or export_file.stat().st_size == 0:
        _emit_stage_progress("comparator", "failed", t0)
        result["status"], result["reason"] = "error", "comparator accepted but emitted no export (patched comparator required)"
        return finish()
    # Identity binding (2/2): the submission must be byte-identical to what comparator just
    # verified — catch any mutation a submission-spawned process (elaboration-time IO) made
    # DURING the build, before we freeze and reuse the workspace for timing.
    if _submission_digest(work) != verified_digest:
        _emit_stage_progress("comparator", "failed", t0)
        result["status"], result["reason"] = "error", "submission changed during correctness verification"
        return finish()
    result["stages"]["export"] = {"source": "comparator-verified", "bytes": export_file.stat().st_size}
    correctness_export_bytes = _pin_export_bytes(export_file)
    artifact_lib, verified_artifacts, artifact_digest = _snapshot_verified_artifacts(work)
    verified_env = _verified_runtime_env(env, artifact_lib, lean_prefix, core_lib)
    result["stages"]["verified_artifacts"] = {
        "source": "comparator-build",
        "olean_files": len(verified_artifacts),
        "sha256": artifact_digest,
    }
    freeze_readonly(work)
    _emit_stage_progress("comparator", "done", t0)


    # ---- Axiom re-audit (R4): whitelisted axioms only, on the comparator-verified correctness
    # export (the per-input timed exports are separately re-audited in the perf loop below) ----
    axiom_started = time.monotonic()
    rc, out = run([str(TIMER), "--check-axioms", ",".join(axioms), str(export_file)],
                  work, env, AUDIT_TIMEOUT)
    result["stages"]["axioms"] = {"exit": rc, "tail": last_line(out)}
    if not _export_matches(export_file, correctness_export_bytes):
        _emit_stage_progress("axiom_audit", "failed", axiom_started)
        result["status"], result["reason"] = "error", "correctness export changed during axiom audit"
        return finish()
    if not _artifacts_match(artifact_lib, verified_artifacts):
        _emit_stage_progress("axiom_audit", "failed", axiom_started)
        result["status"], result["reason"] = "error", \
            "comparator-verified build artifacts changed during axiom audit"
        return finish()
    if rc == "timeout":
        _emit_stage_progress("axiom_audit", "failed", axiom_started)
        result["status"], result["reason"] = "error", "axiom re-audit timed out"
        return finish()
    if _attested_local_memory_kill(rc):
        _emit_stage_progress("axiom_audit", "failed", axiom_started)
        result["status"], result["reason"] = "rejected", \
            "correctness axiom audit exceeded the 4 GiB memory envelope"
        return finish()
    if _died_by_signal(rc):
        _emit_stage_progress("axiom_audit", "failed", axiom_started)
        result["status"], result["reason"] = "error", \
            f"axiom auditor killed by signal (exit {rc}) — infrastructure fault, not a rule violation"
        return finish()
    if rc != 0:
        _emit_stage_progress("axiom_audit", "failed", axiom_started)
        result["status"], result["reason"] = "rejected", f"axiom audit: {last_line(out)}"
        return finish()
    _emit_stage_progress("axiom_audit", "done", axiom_started)

    def time_export(export_path, target=None, deadline=None, timeout_cap=None):
        """Replay one export through the authoritative full or target-only boundary."""
        replay_timeout = min(
            TIMING_TIMEOUT,
            timeout_cap if timeout_cap is not None else TIMING_TIMEOUT,
        )
        if TIMING_METRIC == "perf_instructions" and TIMING_EXECUTOR_URLS:
            if deadline is not None and _remaining_timeout(deadline, float("inf")) <= 0:
                return "budget-exhausted", None
            try:
                remote = _time_remote(
                    export_path, reps, target, deadline=deadline,
                    timeout_cap=replay_timeout)
            except PerfBudgetExhausted:
                return "budget-exhausted", None
            result["stages"].setdefault("timing_executor", {
                "kind": "remote",
                "executor": remote["executor"], "version": remote["version"]})
            if remote["status"] == "timeout":
                timeout_meta = _timeout_measurement(target, "remote-process-watchdog")
                if isinstance(remote.get("timeout_phase"), str):
                    timeout_meta["executor_timeout_phase"] = remote["timeout_phase"]
                return "timeout", timeout_meta
            if remote["status"] == "resource-limit":
                resource_meta = _resource_limit_measurement(
                    target, "remote-executor-cgroup",
                    "correctness-replay" if target is None else "target-replay")
                if isinstance(remote.get("resource_phase"), str):
                    resource_meta["executor_resource_phase"] = remote["resource_phase"]
                return "resource-limit", resource_meta
            if remote["status"] == "failed":
                return "failed", last_line(remote.get("output_tail", ""))
            return "ok", [_remote_sample(s) for s in remote["samples"]]

        samples = []
        for i in range(reps):
            step_timeout = _remaining_timeout(deadline, replay_timeout)
            if step_timeout <= 0:
                return "budget-exhausted", None
            trc, tout, sample = _time_replay(
                export_path, work, env, step_timeout, target=target)
            if trc == "timeout":
                return "timeout", sample
            if _attested_local_memory_kill(trc):
                return "resource-limit", _resource_limit_measurement(
                    target, "local-container-cgroup",
                    "correctness-replay" if target is None else "target-replay")
            if trc != 0:
                return "failed", f"rep {i}: {last_line(tout)}"
            samples.append(sample)
        if TIMING_METRIC == "perf_instructions":
            if any(type(s.get("instructions")) is not int or s["instructions"] <= 0
                   for s in samples):
                raise InfraError("local perf produced a non-positive/non-integral instruction sample")
        return "ok", samples

    if TIMING_METRIC == "perf_instructions" and not TIMING_EXECUTOR_URLS and not DEFER_TIMING:
        # Prove the local PMU instruction counter works before the first timed replay: a broken
        # perf wrapper or a permission downgrade must fail here with its real diagnosis, not
        # surface as an error misattributed to the correctness export or a perf case. Placed
        # after the correctness gate so PMU-less hosts can still exercise the gate itself
        # (the CI attestation sanity test relies on that).
        _preflight_perf_counter(env)

    # Score the proof work too. This prevents a specialization table from appearing free merely
    # because its expensive closed-value proofs live in the already-verified correctness export.
    correctness_status, correctness_payload = _measure_or_defer(
        lambda: time_export(export_file, target=None))
    if not _export_matches(export_file, correctness_export_bytes):
        result["status"], result["reason"] = "error", "correctness export changed during timing"
        return finish()
    if not _artifacts_match(artifact_lib, verified_artifacts):
        result["status"], result["reason"] = "error", \
            "comparator-verified build artifacts changed during correctness timing"
        return finish()
    correctness_timing = {
        "metric": TIMING_METRIC, "reps": reps, "result": correctness_status,
        "checker": CHECKER_ID,
        "measurement_contract": MEASUREMENT_CONTRACT,
        "measurement_boundary": FULL_REPLAY_BOUNDARY,
        "measurement_target": None,
    }
    if correctness_status == "ok":
        correctness_timing.update(_summarize_samples(correctness_payload))
    elif correctness_status in ("timeout", "resource-limit") and isinstance(
            correctness_payload, dict):
        correctness_timing.update(correctness_payload)
    elif correctness_status == "failed":
        result["correctness_timing"] = correctness_timing
        result["status"], result["reason"] = (
            "error", f"official kernel rejected correctness export: {correctness_payload}")
        return finish()
    result["correctness_timing"] = correctness_timing

    inputs = ([row["n"] for row in resolved_plan]
              if resolved_plan is not None else perf_inputs(cfg, problem))
    if not inputs:
        result["status"], result["reason"] = "error", \
            f"no performance policy configured for '{problem}'"
        return finish()
    result["stages"]["perf_inputs"] = inputs
    if resolved_plan is not None:
        result["stages"]["performance_plan"] = resolved_plan
    result["evaluation_cohort"] = _evaluation_cohort(
        problem, cfg, inputs, reps, result, performance_plan=resolved_plan)

    # A timed correctness replay is required for every score. Once it times out, running the
    # performance curve cannot change scoreability, so record the complete schedule and stop.
    if correctness_status in ("timeout", "resource-limit"):
        incomplete_reason = (
            "correctness-timing-resource-limit"
            if correctness_status == "resource-limit"
            else "correctness-timing-timeout"
        )
        scaling = []
        for slot, n in enumerate(inputs):
            scaling.append({
                "slot": slot, **_plan_slot_annotations(resolved_plan, slot, n),
                "n": n, "result": "not-run",
                "reason": incomplete_reason,
            })
        result["timing"] = {
            "metric": TIMING_METRIC,
            "reps": reps,
            "scaling": scaling,
            "checker": CHECKER_ID,
            "measurement_contract": MEASUREMENT_CONTRACT,
            "measurement_boundary": TARGET_REPLAY_BOUNDARY,
            **_coverage_fields(inputs, scaling),
        }
        result["status"] = "accepted"
        result["reason"] = (
            "unscored: correctness export exceeded the memory limit"
            if correctness_status == "resource-limit"
            else "unscored: correctness export did not complete in time"
        )
        return finish()

    # ---- Performance: time the kernel reducing `impl n` at judge-chosen inputs ----
    # Correctness (the ∀n proof) was verified by comparator above. Here we time the
    # COMPUTATION, not the ∀n proof: for each input n we export a direct `impl n = v` theorem,
    # then time the kernel replaying THAT declaration. This
    # forces reduction of `impl n` at this n and yields the algorithm's scaling curve.
    # Reuse the exact comparator build graph. Re-elaborating identical source is not an identity
    # proof: run_meta/run_elab can depend on environment or filesystem state. Only judge-owned
    # EvalVal/Perf modules are compiled below, importing the pinned Submission.olean.
    _prepare_generated_workspace(work, artifact_lib)

    # A timeout occupies only its own configured slot. We still probe every later slot because a
    # valid implementation's reduction cost need not be monotone in n. Deterministic failures of
    # the VALUE ORACLE (NONLIT, invalid literal, nonzero oracle exit) depend only on how far the
    # submission's impl reduces, so they fail that case and the plan continues — otherwise a
    # comparator-legal submission that passed every easier group would lose all its points to a
    # deterministic elaborator crash at one harder input, ranking strictly worse than timing out
    # there (non-monotone and contrary to the published "zero cases passed scores 0" rule).
    # Judge-owned faults (identity, generated-theorem build, kernel rejection of a perf export)
    # remain fatal and can never be misread as a slow-but-valid point.
    def probe_point(n, deadline=None):
        # Preparation keeps its infrastructure timeout; only the target timing process uses
        # the group's published watchdog. Legacy schedules may also supply an aggregate
        # development deadline; grouped cases pass no shared deadline.
        timeout_caps = _performance_timeout_caps(resolved_plan, n)

        def budget(step_timeout):
            return _remaining_timeout(deadline, step_timeout)

        if not _artifacts_match(artifact_lib, verified_artifacts):
            return {"n": n, "result": "identity-error"}, \
                f"comparator-verified build artifacts changed before n={n}"
        step_timeout = budget(timeout_caps["value_eval"])
        if step_timeout <= 0:
            return {"n": n, "result": "budget-exhausted"}, None
        vkind, v = _eval_impl_value(work, verified_env, n, step_timeout, lean_bin)
        if not _artifacts_match(artifact_lib, verified_artifacts):
            return {"n": n, "result": "identity-error"}, \
                f"comparator-verified build artifacts changed during value evaluation at n={n}"
        if vkind == "timeout":
            return {"n": n, "result": "value-eval-timeout"}, None
        if vkind == "resource-limit":
            return {
                "n": n, "result": "resource-limit",
                **_resource_limit_measurement(
                    None, "value-eval-container-cgroup", "value-eval"),
            }, None
        if vkind == "error":
            # Contestant-dependent deterministic failure: this case fails, later cases still run.
            return {"n": n, "result": "value-eval-error", "detail": str(v)[:300]}, None
        # Identity binding: the impl we are about to build/time must be byte-identical to the
        # one comparator verified `impl_correct` against. A mismatch means the Submission was
        # modified after verification — a fault, never a score.
        if _submission_digest(work) != verified_digest:
            return {"n": n, "result": "identity-error"}, \
                f"submission changed after correctness verification (at n={n})"
        perf_export = job_dir / f"perf_{n}.export.ndjson"
        pkind, err, perf_target = _perf_export(
            work, verified_env, n, v, perf_export, timeout_caps["build_export"],
            artifact_lib, lean_bin,
            deadline=deadline)
        if not _artifacts_match(artifact_lib, verified_artifacts):
            return {"n": n, "result": "identity-error"}, \
                f"comparator-verified build artifacts changed during perf build at n={n}"
        if pkind == "timeout":
            return {"n": n, "result": "build-timeout"}, None
        if pkind == "resource-limit":
            return {
                "n": n, "result": "resource-limit",
                **_resource_limit_measurement(
                    perf_target, "build-export-container-cgroup", "build-export"),
            }, None
        if pkind == "budget-exhausted":
            return {"n": n, "result": "budget-exhausted"}, None
        if pkind == "error":
            return {"n": n, "result": "build-error"}, err
        # Source is not re-elaborated, but a mutation during the generated theorem build is still
        # a fault and must be caught before the export is trusted and timed.
        if _submission_digest(work) != verified_digest:
            return {"n": n, "result": "identity-error"}, \
                f"submission changed during perf build (at n={n})"
        # Pin the exact export bytes and freeze the file, so the axiom audit and the (separate)
        # timing process provably run identical bytes — not different ones swapped in between.
        perf_bytes = _pin_export_bytes(perf_export)
        step_timeout = budget(timeout_caps["axiom_audit"])
        if step_timeout <= 0:
            return {"n": n, "result": "budget-exhausted"}, None
        arc, aout = run([str(TIMER), "--check-axioms", ",".join(axioms), str(perf_export)],
                        work, env, step_timeout)
        if not _export_matches(perf_export, perf_bytes):
            return {"n": n, "result": "identity-error"}, \
                f"perf export changed during axiom audit (at n={n})"
        if not _artifacts_match(artifact_lib, verified_artifacts):
            return {"n": n, "result": "identity-error"}, \
                f"comparator-verified build artifacts changed during perf audit at n={n}"
        if arc == "timeout":
            return {"n": n, "result": "axiom-audit-timeout"}, None
        if _attested_local_memory_kill(arc):
            return {
                "n": n, "result": "resource-limit",
                **_resource_limit_measurement(
                    perf_target, "axiom-audit-container-cgroup", "axiom-audit"),
            }, None
        if arc != 0:
            return {"n": n, "result": "axiom-audit-error"}, \
                f"perf export axiom audit failed at n={n}: {last_line(aout)}"
        status, payload = _measure_or_defer(
            lambda: time_export(
                perf_export,
                target=perf_target,
                deadline=deadline,
                timeout_cap=timeout_caps["target_replay"],
            ))
        if status == "deferred":
            return {
                "n": n,
                **_deferred_measurement(perf_target),
            }, None
        if not _export_matches(perf_export, perf_bytes):
            return {"n": n, "result": "identity-error"}, \
                f"perf export changed during timing (at n={n})"
        if not _artifacts_match(artifact_lib, verified_artifacts):
            return {"n": n, "result": "identity-error"}, \
                f"comparator-verified build artifacts changed during perf timing at n={n}"
        if status == "failed":
            return {"n": n, "result": "timing-error"}, \
                f"official kernel rejected perf export at n={n}: {payload}"
        if status == "budget-exhausted":
            return {"n": n, "result": "budget-exhausted"}, None
        if status == "resource-limit":
            return {
                "n": n,
                "result": "resource-limit",
                **(payload if isinstance(payload, dict) else {}),
            }, None
        if status == "timeout":
            return {
                "n": n,
                "result": "timeout",
                "measurement_boundary": TARGET_REPLAY_BOUNDARY,
                "measurement_target": perf_target,
                **(payload if isinstance(payload, dict) else {}),
            }, None
        return {
            "n": n,
            "result": "ok",
            "measurement_contract": MEASUREMENT_CONTRACT,
            "measurement_boundary": TARGET_REPLAY_BOUNDARY,
            "measurement_target": perf_target,
            **_summarize_samples(payload),
        }, None

    perf_deadline = _performance_phase_deadline(resolved_plan)
    scaling, perf_error = _collect_perf_slots(
        inputs, probe_point, perf_deadline, performance_plan=resolved_plan)

    timing = {"metric": TIMING_METRIC, "reps": reps, "scaling": scaling,
              "checker": CHECKER_ID,
              "measurement_contract": MEASUREMENT_CONTRACT,
              "measurement_boundary": TARGET_REPLAY_BOUNDARY,
              **_coverage_fields(inputs, scaling)}
    canonical_work = _canonical_work(correctness_timing, scaling)
    if canonical_work is not None:
        result["canonical_work"] = canonical_work
    if perf_error is not None:
        result["timing"] = timing
        result["status"], result["reason"] = "error", perf_error
        return finish()

    if DEFER_TIMING:
        result["timing"] = timing
        result["status"] = "accepted"
        result["reason"] = "timing deferred to the trusted host executor"
        return finish()

    # Correctness already passed, so the submission is ACCEPTED regardless of speed; performance
    # only determines its score. Grouped-v2 awards a valid zero-point score when no case passes.
    # Legacy v1 remains accepted-but-unscored when no input completes. Slowness is not a
    # rejection (only incorrect or illegal-axiom submissions are rejected, above; a kernel
    # rejection of a judge-built export contradicts the comparator's own verification and is
    # therefore an infrastructure error verdict, not a rejection).
    result["timing"] = timing
    result["status"] = "accepted"
    ok_rows = [r for r in scaling if r.get("result") == "ok"]
    if ok_rows:
        top = _headline_row(scaling)
        result["timing"]["headline_n"] = top["n"]
        if TIMING_METRIC == "perf_instructions":
            result["timing"]["median_instructions"] = top.get("median_instructions")
        else:
            result["timing"]["median_s"] = top.get("median_s")

    # Grouped policies are scored by the one canonical scorer, including instruction caps and
    # per-group milestones.  Reusing that view here prevents the immediate verdict summary from
    # claiming raw slot coverage that the actual leaderboard does not award.
    if resolved_plan is not None:
        if correctness_timing["result"] != "ok":
            result["reason"] = "unscored: correctness export did not complete in time"
        else:
            view = _validated_grouped_score_view(result)
            result["score"] = _grouped_score_summary(result, view)
        return finish()

    if correctness_timing["result"] != "ok":
        result["reason"] = "unscored: correctness export did not complete in time"
    elif not ok_rows:
        result["reason"] = "unscored: did not complete any judge input in time"
    else:
        if TIMING_METRIC == "perf_instructions":
            result["score"] = (
                f"{len(ok_rows)}/{len(inputs)} slots; "
                f"{canonical_work['total']} total instructions")
        else:
            result["score"] = (
                f"{len(ok_rows)}/{len(inputs)} slots; "
                f"{canonical_work['total']:.3f}s total replay")
    return finish()


def md_cell(s) -> str:
    """Escape an untrusted value for a single Markdown table cell."""
    s = str(s if s is not None else "")
    s = s.replace("\\", "\\\\").replace("|", "\\|")
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"[`<>\[\]]", "", s)
    return s[:160]


_SCORER_MODULE = [None]


def _canonical_scorer():
    """Load the one scoring implementation used by both CLI reports.

    Keeping the leaderboard on scripts/score.py's validator and rank key prevents a
    second, subtly different interpretation of the verdict schema from drifting in here.
    """
    if _SCORER_MODULE[0] is None:
        path = ROOT / "scripts" / "score.py"
        spec = importlib.util.spec_from_file_location("lean_kernel_challenge_score", path)
        if spec is None or spec.loader is None:
            raise InfraError(f"cannot load canonical scorer at {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SCORER_MODULE[0] = module
    return _SCORER_MODULE[0]


def _score_view(r):
    scorer = _canonical_scorer()
    metric = r.get("metric")
    if metric not in scorer.METRICS:
        return None
    view = scorer._score_row(r, metric)
    return view if view["scoreable"] else None


def _validated_grouped_score_view(result):
    """Return a canonical grouped view or fail this judge run as infrastructure."""
    scorer = _canonical_scorer()
    metric = result.get("metric")
    if metric not in scorer.METRICS:
        raise InfraError(f"canonical grouped scoring received invalid metric {metric!r}")
    view = scorer._score_row(result, metric)
    if not view["scoreable"]:
        raise InfraError(
            "canonical grouped scoring rejected the completed verdict: "
            + str(view.get("reason") or "unknown scoring error"))
    return view


def _score_key(r):
    view = _score_view(r)
    return _canonical_scorer()._rank_key(view) if view is not None else None


def _grouped_max_points(result):
    try:
        groups = result["evaluation_cohort"]["policy"]["evaluation"]["groups"]
        return sum(group["award"]["table"][-1]["points"] for group in groups)
    except (KeyError, TypeError, IndexError):
        return None


def _grouped_score_summary(result, view):
    """Short verdict text derived from an already validated canonical grouped view."""
    maximum = _grouped_max_points(result)
    base = (
        f"{view['points']}/{maximum} points; "
        f"{view['completed_slots']}/{view['planned_slots']} passed cases"
    )
    if not view.get("work_tiebreak_active"):
        return base + "; interchangeable partial profiles remain tied"
    scorer = _canonical_scorer()
    work = scorer._format_work(view.get("ranking_work"), view.get("metric"))
    metric_label = _METRIC_LABEL.get(view.get("metric"), view.get("metric", "work"))
    return base + f"; {work} ranking {metric_label}"


def _grouped_profile(result, view):
    """Human-readable hardest-first group score profile for the local leaderboard."""
    del result
    return _canonical_scorer()._format_group_points(view)


def _grouped_cases(view):
    """Human-readable hardest-first case profile for the local leaderboard."""
    return _canonical_scorer()._format_group_cases(view)


# Human label + sort order for each metric; scores of different metrics are NOT comparable
# (wall seconds vs instruction counts), so the leaderboard ranks within a metric only.
_METRIC_LABEL = {"perf_instructions": "instructions", "wall_time": "wall seconds (dev)"}


def _stage1_problem_ids():
    """Return current grouped problem ids for non-ranked status reporting."""
    problem_ids = set()
    for path in PROBLEMS.glob("*/config.json"):
        try:
            cfg = json.loads(path.read_text())
        except (OSError, UnicodeError, ValueError, RecursionError):
            continue
        evaluation = cfg.get("evaluation") if isinstance(cfg, dict) else None
        if (isinstance(evaluation, dict)
                and evaluation.get("schema") == _GROUPED_EVALUATION_SCHEMA):
            problem_ids.add(path.parent.name)
    return problem_ids


def leaderboard():
    rows = []
    legacy_rows = []
    stage1_problems = _stage1_problem_ids()
    if not RESULTS.is_dir():          # fresh clone with no results/ yet — empty board, no crash
        print(f"no results yet at {RESULTS}")
        return
    for pdir in sorted(RESULTS.iterdir()):
        if not pdir.is_dir() or pdir.name in ("work", "plots"):
            continue
        for f in sorted(pdir.glob("*.json")):
            try:
                r = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError, UnicodeError, ValueError, RecursionError):
                continue
            # Only rank official judge verdicts, identified by STRUCTURE (a legitimate submission
            # may be named e.g. "x.perf", so a filename-suffix filter would wrongly drop it).
            # Requiring every field prevents a KeyError on malformed or legacy diagnostic files.
            # Current perf_eval output delegates to this judge and is therefore canonical.
            if not (isinstance(r, dict)
                    and isinstance(r.get("problem"), str) and isinstance(r.get("submission"), str)
                    and isinstance(r.get("status"), str) and isinstance(r.get("stages"), dict)):
                continue
            if r["problem"] not in stage1_problems:
                legacy_rows.append(r)
                continue
            if r["status"] == "accepted":
                if not _canonical_scorer()._is_grouped_verdict(r):
                    legacy_rows.append(r)
                    continue
            rows.append(r)
    lines = ["# Lean Kernel Challenge — leaderboard (local dev)", ""]
    problem_sections = {}
    for problem in sorted({r["problem"] for r in rows}):
        section_start = len(lines)
        lines.append(f"## {md_cell(problem)}")
        lines.append("")
        prows = [r for r in rows if r["problem"] == problem]
        accepted = [r for r in prows if r["status"] == "accepted"]

        # Coerce to a single sortable type: `.get(k, default)` only fills a MISSING key, so an
        # explicit "metric": null / cohort id null would leak None into a set that is later
        # sorted() alongside strings, raising TypeError. Force every key to a str.
        def _metric_key(r):
            m = r.get("metric")
            return m if isinstance(m, str) else "wall_time"

        def _cohort_key(r):
            c = r.get("evaluation_cohort")
            cid = c.get("id") if isinstance(c, dict) else None
            return cid if isinstance(cid, str) else "<missing>"

        # Rank within each metric separately — never mix seconds and instruction counts.
        metrics = sorted({_metric_key(r) for r in accepted})
        for metric in metrics:
            metric_rows = [r for r in accepted if _metric_key(r) == metric]
            cohort_ids = sorted({_cohort_key(r) for r in metric_rows})
            for cohort_id in cohort_ids:
                grp = [r for r in metric_rows if _cohort_key(r) == cohort_id]
                scorer = _canonical_scorer()
                ranked = []
                unscored = []
                for r in grp:
                    view = scorer._score_row(r, metric)
                    if view["scoreable"]:
                        ranked.append((r, view))
                    else:
                        unscored.append((r, view["reason"]))
                ranked.sort(key=lambda pair: scorer._rank_key(pair[1]))
                label = _METRIC_LABEL.get(metric, metric)
                placements = scorer._competition_ranks([view for _, view in ranked])
                grouped = any(
                    isinstance(r.get("evaluation_cohort"), dict)
                    and isinstance(r["evaluation_cohort"].get("policy"), dict)
                    and r["evaluation_cohort"]["policy"].get("schema")
                        == "evaluation-policy-v2"
                    for r in grp
                )
                if grouped:
                    lines.append(
                        f"**canonical {label} ranking — cohort `{md_cell(cohort_id)}`:** "
                        "points, harder-group/case profile, then configured ranking work")
                    lines.append("")
                    lines.append(
                        "| rank | submission | points | passed cases | group profile | case outcomes | "
                        "ranking work | score |")
                    lines.append("|---|---|---|---|---|---|---|---|")
                    for (r, view), placement in zip(ranked, placements):
                        maximum = _grouped_max_points(r)
                        passed = f"{view['completed_slots']}/{view['planned_slots']}"
                        profile = _grouped_profile(r, view)
                        cases = _grouped_cases(view)
                        work = (
                            scorer._format_work(view["ranking_work"], metric)
                            if view.get("work_tiebreak_active") else "not compared")
                        summary = _grouped_score_summary(r, view)
                        lines.append(
                            f"| {placement} | {md_cell(r['submission'])} | "
                            f"{view['points']}/{maximum} | {passed} | {md_cell(profile)} | "
                            f"{md_cell(cases)} | {md_cell(work)} | {md_cell(summary)} |")
                else:
                    # Preserve the legacy v1 report byte-for-byte apart from surrounding cohorts.
                    lines.append(
                        f"**canonical {label} ranking — cohort `{md_cell(cohort_id)}`:** "
                        f"completed slots, coverage, harder-slot profile, then lower total replay work")
                    lines.append("")
                    lines.append("| rank | submission | coverage | total work | score |")
                    lines.append("|---|---|---|---|---|")
                    for (r, view), placement in zip(ranked, placements):
                        coverage = f"{view['completed_slots']}/{view['planned_slots']}"
                        total = scorer._format_work(view["total_work"], metric)
                        lines.append(
                            f"| {placement} | {md_cell(r['submission'])} | {coverage} | "
                            f"{md_cell(total)} | {md_cell(r.get('score'))} |")
                lines.append("")
                if unscored:
                    lines.append("_accepted but unscored under the current scoring contract:_")
                    lines.append("")
                    for r, reason in unscored:
                        lines.append(
                            f"- {md_cell(r['submission'])} — "
                            f"{md_cell(reason or r.get('reason') or 'unscored')}")
                    lines.append("")
        other = [r for r in prows if r["status"] != "accepted"]
        if other:
            icons = {"rejected": "❌ rejected", "error": "💥 error", "retry": "⏳ retry"}
            lines.append("| submission | status | note |")
            lines.append("|---|---|---|")
            for r in other:
                icon = icons.get(r["status"], f"? {r['status']}")
                lines.append(f"| {md_cell(r['submission'])} | {icon} | {md_cell(r.get('reason'))} |")
            lines.append("")
        problem_sections[problem] = lines[section_start:]
    if legacy_rows:
        # Informal visibility for experimental problems (conv) and pre-redesign v1 verdicts:
        # they belong on no Stage 1 board, but silently vanishing from EVERY report would make
        # local development on them blind. Listed only — never ranked or mixed with cohorts.
        lines.append("## Experimental / legacy verdicts (informal, unranked)")
        lines.append("")
        lines.append("| problem | submission | status | metric | note |")
        lines.append("|---|---|---|---|---|")
        for r in sorted(legacy_rows, key=lambda r: (r["problem"], r["submission"])):
            lines.append(
                f"| {md_cell(r['problem'])} | {md_cell(r['submission'])} | "
                f"{md_cell(r['status'])} | {md_cell(r.get('metric'))} | "
                f"{md_cell(r.get('score') or r.get('reason'))} |")
        lines.append("")
    for problem in sorted(stage1_problems):
        problem_dir = RESULTS / problem
        problem_dir.mkdir(parents=True, exist_ok=True)
        section = problem_sections.get(problem, ["_No local results yet._", ""])
        (problem_dir / "leaderboard-local.md").write_text("\n".join([
            f"# Lean Kernel Challenge — {problem} leaderboard (local dev)",
            "",
            "This local leaderboard is independent; no cross-problem total is computed.",
            "",
            *section,
        ]))
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "leaderboard.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}")


def _validate_repetition_count(reps):
    if reps < 1:
        raise InfraError(f"--reps must be >= 1 (got {reps})")
    if OFFICIAL_EVAL and reps != DEFAULT_REPS:
        raise InfraError(
            f"official evaluation requires exactly {DEFAULT_REPS} timing repetitions "
            f"(got {reps})")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--problem", required=True)
    r.add_argument("--submission", required=True)
    r.add_argument("--reps", type=int, default=DEFAULT_REPS)
    r.add_argument("--tag")
    r.add_argument("--keep-workspace", action="store_true", help="don't delete the temp job dir (debug)")
    sub.add_parser("leaderboard")
    args = ap.parse_args()

    if args.cmd == "leaderboard":
        leaderboard()
        return

    problem, tag, sub_name = args.problem, args.tag, (args.tag or Path(args.submission).name)
    job_dir = None

    # An external kill (CI timeout, k8s eviction, operator SIGTERM) must not break the "always a
    # verdict" contract nor leak the job workspace: turn the signal into an exception so the
    # existing handler writes a `retry` verdict and `finally` thaws + removes the job dir.
    # `cleaning[0]` is set once we reach the finally block. A signal arriving during cleanup must
    # NOT raise: the exception would escape every `except` (they are already unwinding), producing
    # exit 1 + a traceback, no verdict, and a leaked workspace. During cleanup we only record the
    # signal; the single verdict for this run has already been written by then.
    cleaning = [False]

    def _on_signal(signum, _frame):
        if cleaning[0]:
            return
        raise TimingRetry(f"judge terminated by signal {signum} before completing")

    for _sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(_sig, _on_signal)
        except (ValueError, OSError):
            pass

    try:
        _consume_perf_seed_stdin()
        if not valid_slug(problem):
            raise InfraError(f"invalid --problem slug '{problem}'")
        if not (PROBLEMS / problem / "config.json").exists():
            raise InfraError(f"unknown problem '{problem}' (not in problems/)")
        if tag is not None and not valid_slug(tag):
            raise InfraError(f"invalid --tag slug '{tag}'")
        if not valid_slug(sub_name):
            raise InfraError(f"submission name '{sub_name}' is not a safe slug; pass --tag")
        _validate_repetition_count(args.reps)
        if TIMING_METRIC not in ("wall_time", "perf_instructions"):
            raise InfraError(f"invalid TIMING_METRIC '{TIMING_METRIC}' "
                             "(must be 'wall_time' or 'perf_instructions')")
        _validate_timing_mode(args.keep_workspace)
        (RESULTS / "work").mkdir(parents=True, exist_ok=True)
        job_dir = Path(tempfile.mkdtemp(dir=RESULTS / "work", prefix=f"{problem}__{sub_name}__"))
        sys.exit(judge(job_dir, problem, args.submission, args.reps, tag))
    except SubmissionError as e:
        # Contestant's fault (bad submission format) → a REJECTED verdict (exit 0), not an
        # infra error/retry, so an invalid submission is not requeued forever.
        _write_infra_verdict(problem, sub_name, f"submission format: {e}", status="rejected")
        print(f"❌ rejected: {e}", file=sys.stderr)
        sys.exit(0)
    except TimingRetry as e:
        _write_infra_verdict(problem, sub_name, f"retry: {e}", status="retry")
        print(f"⏳ timing deferred: {e}", file=sys.stderr)
        sys.exit(3)
    except InfraError as e:
        _write_infra_verdict(problem, sub_name, f"infra: {e}")
        print(f"💥 infra error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        # Catch-all: any unexpected error (OSError, ValueError from perf parsing,
        # schema issues, …) still yields a verdict + exit 2, never a bare traceback.
        _write_infra_verdict(problem, sub_name, f"unexpected {type(e).__name__}: {e}")
        print(f"💥 unexpected infra error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)
    finally:
        # From here on a signal must not raise (see _on_signal): cleanup has to complete so the
        # workspace is never leaked, and the verdict for this run is already written.
        cleaning[0] = True
        if job_dir is not None and job_dir.exists() and not args.keep_workspace:
            try:
                thaw(job_dir)                 # workspace was frozen read-only
                shutil.rmtree(job_dir, ignore_errors=True)
            except Exception:
                # Never let cleanup trouble replace the verdict/exit code already decided above.
                pass


if __name__ == "__main__":
    main()
