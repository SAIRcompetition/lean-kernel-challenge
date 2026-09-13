#!/usr/bin/env python3
"""Build canonical, per-problem scoring tables from sealed judge verdicts.

``evaluation-policy-v2`` cohorts use the embedded ranking contract. ``full-plan-v1``
awards 100 points only for complete passes and compares their configured instruction
cost; every scoreable failed plan ties at zero points and infinite cost. Previously
sealed ``group-points-v1`` cohorts retain their milestone and profile semantics.
The scorer never consults a live problem config or trusts points copied into a verdict.

Legacy ``evaluation-policy-v1`` ranking remains deliberately simple and monotone:

  1. more completed sampling slots wins;
  2. for equal completed-slot counts, higher coverage wins;
  3. for equal coverage, success at harder (higher-index) slots wins;
  4. only identical success profiles are tied by total measured kernel work:

         full correctness-closure replay median
         + sum(completed target-declaration replay medians)

The correctness replay is charged because it is part of the verified computation
artifact.  Increasing the work at any point can therefore never improve a rank.
The log-log fit (α, β) remains useful diagnostic data, but is report-only.

Instruction-count and wall-time verdicts are placed in separate groups, as are distinct
evaluation cohorts. A verdict is unscored unless it explicitly carries the current protocol,
measurement contract, both replay boundaries, and one consistent metric. Legacy whole-process
verdicts are never silently compared with scoped-replay verdicts, even if they reuse a cohort id.

Stdlib only.  See rules/evaluation.md for the binding scoring contract.
"""
import hashlib
import json
from datetime import datetime, timezone
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from memory_policy import memory_mb_from_envelope, valid_memory_mb
from problem_layout import RETIRED_PROBLEMS
with open(os.path.join(ROOT, "pipeline", "config.json")) as _config_file:
    _PIPELINE_POLICY = json.load(_config_file)
_TIMING_POLICY = _PIPELINE_POLICY["timing"]
STAGE1_OFFICIAL_REPS = _PIPELINE_POLICY["judge"]["timing_reps"]
# Official cohorts must seal exactly the checked-in watchdog budgets and toolchain: the public
# contract publishes these ceilings, and a verdict is otherwise free to carry any self-consistent
# policy of its own (the seal hashes are unkeyed). Pinning them here fail-closes both a drifted
# dev override sealed into an "official" run and a stale verdict from an older toolchain.
STAGE1_OFFICIAL_BUDGETS = {
    "comparator_timeout_seconds": _PIPELINE_POLICY["judge"]["comparator_timeout_seconds"],
    "audit_timeout_seconds": _PIPELINE_POLICY["judge"]["audit_timeout_seconds"],
    "timing_timeout_seconds": _PIPELINE_POLICY["judge"]["timing_timeout_seconds"],
    "perf_phase_budget_seconds": 0,
}
STAGE1_OFFICIAL_TOOLCHAIN = _PIPELINE_POLICY["toolchain"]
STAGE1_PROBLEMS = frozenset({
    "ca-rule110", "fib", "mertens", "partition", "permanent",
    "polydisc", "primecount", "sha256",
})

REMOTE_PROTOCOL = _TIMING_POLICY["remote_protocol"]
LOCAL_PROTOCOL = "local-v2"
MEASUREMENT_CONTRACT = _TIMING_POLICY["measurement_contract"]
CORRECTNESS_BOUNDARY = _TIMING_POLICY["correctness_boundary"]
PERFORMANCE_BOUNDARY = _TIMING_POLICY["performance_boundary"]
TARGET_PROOF_ENCODING = _TIMING_POLICY["target_proof_encoding"]
CURRENT_MEASUREMENT_RECORD = {
    "id": MEASUREMENT_CONTRACT,
    "correctness_boundary": CORRECTNESS_BOUNDARY,
    "performance_boundary": PERFORMANCE_BOUNDARY,
    "target_proof_encoding": TARGET_PROOF_ENCODING,
    "wall_clock_source": "timer-internal-monotonic-ns",
    "perf_counter_control": "timer-perf-event-open+ioctl-enable",
    "local_protocol": LOCAL_PROTOCOL,
    "remote_protocol": REMOTE_PROTOCOL,
    "timeout_scope": "whole-timer-process-including-untimed-preparation",
}

METRICS = {
    "perf_instructions": {
        "field": "median_instructions",
        "label": "kernel instructions",
    },
    "wall_time": {
        "field": "median_s",
        "label": "wall seconds (dev only)",
    },
}

PERFORMANCE_RESULTS = {
    "ok",
    "timeout",
    "value-eval-timeout",
    # Deterministic value-oracle failure (NONLIT / invalid literal / oracle crash) depends only
    # on the submission's impl at that input: the case fails, the rest of the plan still counts.
    "value-eval-error",
    "build-timeout",
    "axiom-audit-timeout",
    "resource-limit",
    "budget-exhausted",
    "not-run",
}


def _load_verdicts():
    rows = []
    if not os.path.isdir(RESULTS):
        return rows
    for prob in sorted(os.listdir(RESULTS)):
        pdir = os.path.join(RESULTS, prob)
        if not os.path.isdir(pdir) or prob in ("work", "plots") or prob in RETIRED_PROBLEMS:
            continue
        for fn in sorted(os.listdir(pdir)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(pdir, fn)) as f:
                    r = json.load(f)
            except (json.JSONDecodeError, OSError, UnicodeError, ValueError, RecursionError):
                continue
            if not (isinstance(r, dict) and isinstance(r.get("problem"), str)
                    and isinstance(r.get("submission"), str)
                    and isinstance(r.get("status"), str) and isinstance(r.get("stages"), dict)):
                continue
            if r["problem"] != prob:
                # The directory is authoritative: a record may only score under the problem
                # whose directory it lives in, so a misfiled or relabeled verdict cannot
                # land on another problem's board.
                continue
            rows.append(r)
    return rows


def _is_cost(value, integral=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return False
    if integral and type(value) is not int:
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def _policy_digest(policy):
    try:
        encoded = json.dumps(
            policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def _nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _sha256_string(value):
    return (isinstance(value, str) and len(value) == 64
            and all(ch in "0123456789abcdef" for ch in value))


def _policy_integer(value):
    if type(value) is int:
        return value
    if isinstance(value, str):
        text = value.strip()
        digits = text[1:] if text[:1] in ("+", "-") else text
        if digits and all("0" <= ch <= "9" for ch in digits):
            return int(text)
    return None


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def _policy_v1_shape_error(policy):
    """Validate the complete schema emitted by the current judge, not just its hash."""
    required = {
        "schema", "round", "problem", "problem_bundle_sha256",
        "evaluator_bundle_sha256", "evaluation_mode", "perf", "perf_defaults",
        "inputs", "metric", "reps", "budgets", "resource_policy", "toolchain",
        "checker", "timing_protocol", "measurement_contract", "executor",
    }
    if set(policy) != required:
        return "evaluation cohort policy has an incomplete or unknown field set"
    if not (_nonempty_string(policy["round"]) and _nonempty_string(policy["problem"])):
        return "evaluation cohort policy has an invalid round/problem"
    if not (_sha256_string(policy["problem_bundle_sha256"])
            and _sha256_string(policy["evaluator_bundle_sha256"])):
        return "evaluation cohort policy has an invalid bundle hash"
    if policy["evaluation_mode"] not in ("official", "development"):
        return "evaluation cohort policy has an invalid evaluation mode"

    perf = policy["perf"]
    if not (isinstance(perf, dict) and {"min", "max"} <= set(perf)
            and set(perf) <= {"min", "max", "count", "spacing", "jitter"}):
        return "evaluation cohort policy has an invalid perf policy"
    lo, hi = _policy_integer(perf["min"]), _policy_integer(perf["max"])
    if lo is None or hi is None or lo < 0 or hi < lo:
        return "evaluation cohort policy has an invalid perf range"
    inputs = policy["inputs"]
    if not (isinstance(inputs, list) and inputs
            and all(type(n) is int and lo <= n <= hi for n in inputs)
            and inputs == sorted(set(inputs))):
        return "evaluation cohort policy has invalid or out-of-range inputs"
    if "count" in perf:
        count = _policy_integer(perf["count"])
        if count is None or count < 1:
            return "evaluation cohort policy has an invalid perf count"
    if "spacing" in perf and perf["spacing"] not in ("linear", "geometric"):
        return "evaluation cohort policy has an invalid perf spacing"
    if "jitter" in perf:
        jitter = perf["jitter"]
        if not _finite_number(jitter) or not 0 <= jitter < 1:
            return "evaluation cohort policy has an invalid perf jitter"

    defaults = policy["perf_defaults"]
    if not (isinstance(defaults, dict)
            and set(defaults) == {"count", "spacing", "jitter"}
            and type(defaults["count"]) is int and defaults["count"] > 0
            and defaults["spacing"] in ("linear", "geometric")
            and _finite_number(defaults["jitter"])
            and 0 <= defaults["jitter"] < 1):
        return "evaluation cohort policy has invalid perf defaults"
    effective_jitter = perf.get("jitter", defaults["jitter"])

    budgets = policy["budgets"]
    budget_fields = {
        "comparator_timeout_seconds", "audit_timeout_seconds",
        "timing_timeout_seconds", "perf_phase_budget_seconds",
    }
    if not (isinstance(budgets, dict) and set(budgets) == budget_fields
            and all(type(budgets[field]) is int and budgets[field] > 0
                    for field in budget_fields)):
        return "evaluation cohort policy has invalid evaluation budgets"

    resources = policy["resource_policy"]
    resource_fields = {"image", "memory", "cpus", "pids_limit", "sandbox_mode"}
    if not (isinstance(resources, dict) and set(resources) == resource_fields
            and all(_nonempty_string(resources[field]) for field in resource_fields)
            and resources["sandbox_mode"] in ("none", "container")):
        return "evaluation cohort policy has an invalid resource policy"

    toolchain = policy["toolchain"]
    tool_fields = {"lean", "comparator_rev", "lean4export_rev"}
    if not (isinstance(toolchain, dict) and set(toolchain) == tool_fields
            and all(_nonempty_string(toolchain[field]) for field in tool_fields)
            and all(len(toolchain[field]) == 40
                    and all(ch in "0123456789abcdef" for ch in toolchain[field])
                    for field in tool_fields - {"lean"})):
        return "evaluation cohort policy has an invalid toolchain record"
    if not _nonempty_string(policy["checker"]):
        return "evaluation cohort policy has an invalid checker"
    if (not isinstance(policy["metric"], str) or policy["metric"] not in METRICS
            or type(policy["reps"]) is not int or policy["reps"] < 1):
        return "evaluation cohort policy has an invalid metric/repetition count"
    if policy["metric"] == "perf_instructions" and effective_jitter <= 0:
        return "instruction-count evaluation policy requires positive schedule jitter"
    if policy["measurement_contract"] != CURRENT_MEASUREMENT_RECORD:
        return "evaluation cohort policy has an invalid measurement contract"
    executor = policy["executor"]
    if not (isinstance(executor, dict)
            and set(executor) == {"kind", "executor", "version"}
            and executor["kind"] in ("local", "remote")
            and _nonempty_string(executor["executor"])
            and _nonempty_string(executor["version"])):
        return "evaluation cohort policy has an invalid executor"
    if not _nonempty_string(policy["timing_protocol"]):
        return "evaluation cohort policy has an invalid timing protocol"
    if policy["evaluation_mode"] == "official":
        if policy["metric"] != "perf_instructions":
            return "official evaluation policy must use kernel instructions"
        if resources["sandbox_mode"] != "container" or any(
                resources[field] == "local-unspecified"
                for field in resource_fields - {"sandbox_mode"}):
            return "official evaluation policy lacks its container resource envelope"
        image = resources["image"]
        if not (image.startswith("sha256:") and _sha256_string(image[7:])):
            return "official evaluation policy lacks an immutable image ID"
        if (executor["kind"] == "local"
                and (executor["executor"] == "local"
                     or executor["version"] == "fixed-host")):
            return "official evaluation policy lacks a pinned PMU executor identity"
    return None


_V1_POLICY_FIELDS = {
    "schema", "round", "problem", "problem_bundle_sha256",
    "evaluator_bundle_sha256", "evaluation_mode", "perf", "perf_defaults",
    "inputs", "metric", "reps", "budgets", "resource_policy", "toolchain",
    "checker", "timing_protocol", "measurement_contract", "executor",
}


def _group_sampling_shape(sampling, *, official):
    """Return ``(error, metadata)`` for one sealed grouped sampler.

    The resolved plan is authoritative only after it has been shown to belong to
    the sampler published in the cohort.  Keep this validator self-contained:
    the canonical scorer must never consult the current problem config or infer
    omitted sampler defaults from a different evaluator build.
    """
    if not isinstance(sampling, dict):
        return "grouped evaluation has an invalid sampling policy", None
    kind = sampling.get("kind")
    if kind in ("geometric_range", "linear_range"):
        required = {"kind", "min", "max", "count", "jitter"}
        if set(sampling) != required:
            return "grouped range sampling has an incomplete or unknown field set", None
        spacing = "geometric" if kind == "geometric_range" else "linear"
    elif kind == "range":
        required = {"kind", "min", "max", "count", "jitter", "spacing"}
        if set(sampling) != required:
            return "grouped range sampling has an incomplete or unknown field set", None
        spacing = sampling.get("spacing")
        if spacing not in ("geometric", "linear"):
            return "grouped range sampling has an invalid spacing", None
    elif kind == "uniform_int":
        required = {"kind", "min", "max", "count"}
        if set(sampling) != required:
            return "grouped uniform sampling has an incomplete or unknown field set", None
        spacing = None
    elif kind == "packed":
        required = {"kind", "scale", "seed_bits", "count"}
        if set(sampling) != required:
            return "grouped packed sampling has an incomplete or unknown field set", None
        scale = sampling.get("scale")
        seed_bits = sampling.get("seed_bits")
        count = sampling.get("count")
        if (type(scale) is not int or scale < 0
                or seed_bits != 32
                or type(count) is not int or count < 1 or count > 2 ** 32):
            return "grouped evaluation has an invalid packed sampling policy", None
        return None, {"kind": kind, "count": count, "scale": scale}
    elif kind == "fixed":
        if not ({"kind", "values"} <= set(sampling)
                and set(sampling) <= {"kind", "values", "count"}):
            return "grouped fixed sampling has an incomplete or unknown field set", None
        values = sampling.get("values")
        if not (isinstance(values, list) and values
                and all(type(value) is int and value >= 0 for value in values)
                and len(values) == len(set(values))):
            return "grouped evaluation has invalid fixed sampling values", None
        if "count" in sampling and (
                type(sampling["count"]) is not int
                or sampling["count"] != len(values)):
            return "grouped fixed sampling count does not match its values", None
        return None, {"kind": kind, "count": len(values), "values": values}
    else:
        return f"grouped evaluation has an unknown sampling kind {kind!r}", None

    lo = sampling.get("min")
    hi = sampling.get("max")
    count = sampling.get("count")
    if (type(lo) is not int or type(hi) is not int
            or lo < 0 or hi < lo
            or type(count) is not int or count < 1 or count > hi - lo + 1):
        return "grouped evaluation has an invalid integer sampling range", None
    if kind != "uniform_int":
        jitter = sampling.get("jitter")
        if (not _finite_number(jitter) or not 0 <= jitter < 1
                or (official and jitter == 0)):
            return "grouped range sampling has an invalid jitter", None
    return None, {
        "kind": kind, "count": count, "min": lo, "max": hi,
        "spacing": spacing,
    }


def _evaluation_memory_mb(evaluation):
    """Read the sealed limit, retaining the fixed envelope of historical milestone cohorts."""
    if not isinstance(evaluation, dict):
        return None
    if "memory_mb" in evaluation:
        return evaluation["memory_mb"]
    ranking = evaluation.get("ranking")
    if isinstance(ranking, dict) and ranking.get("contract") == "group-points-v1":
        return 4096  # Historical contract only; never a fallback for new full-plan runs.
    return None


def _grouped_evaluation_shape_error(evaluation, performance_plan, *, official):
    """Validate the public grouped-scoring contract embedded in a v2 cohort.

    New full-plan policies have no per-group awards. Previously sealed milestone
    policies retain their original behavior. The sealed policy, not a live problem
    config or points copied into a verdict, is the source of scoring authority.
    """
    if not (isinstance(evaluation, dict)
            and set(evaluation) in ({"schema", "axis", "groups", "ranking"},
                                    {"schema", "axis", "groups", "ranking", "memory_mb"})
            and evaluation.get("schema") == "grouped-evaluation-v1"):
        return "evaluation cohort policy has an invalid grouped evaluation contract"
    if ((official or "memory_mb" in evaluation)
            and not valid_memory_mb(_evaluation_memory_mb(evaluation))):
        return "grouped evaluation requires a valid per-problem memory_mb limit"
    axis = evaluation["axis"]
    if not (isinstance(axis, dict)
            and set(axis) == {"label", "unit", "input_encoding"}
            and all(_nonempty_string(axis[field]) for field in axis)):
        return "grouped evaluation has an invalid difficulty axis"

    ranking = evaluation["ranking"]
    full_plan = isinstance(ranking, dict) and ranking.get("contract") == "full-plan-v1"
    ranking_fields = ({"contract", "work", "proof", "max_points"} if full_plan
                      else {"contract", "work", "proof", "profile"})
    if not (isinstance(ranking, dict)
            and set(ranking) == ranking_fields
            and ranking.get("contract") in ("group-points-v1", "full-plan-v1")
            and ranking.get("work") in ("total", "curve", "worst_normalized")
            and ranking.get("proof") in ("include", "gate", "last_tiebreak")
            and (full_plan or ranking.get("profile") in (
                "hardest_group_then_slot", "hardest_group_then_count"))):
        return "grouped evaluation has an invalid ranking contract"
    if full_plan and (type(ranking["max_points"]) is not int
                      or ranking["max_points"] != 100
                      or ranking["proof"] == "last_tiebreak"):
        return "full-plan ranking requires 100 points and no separate proof tie-break"
    if full_plan and (ranking["work"] == "total") != (ranking["proof"] == "include"):
        # The published policy names one comparison: combined work (total/include) or
        # target work with correctness as a completion gate (curve/gate). A mixed pair
        # would publish one policy and score another.
        return "full-plan ranking must pair work=total with proof=include or work=curve with proof=gate"
    # A normalization denominator must be calibrated and defined uniformly before this
    # mode can be compared safely.  Fail closed instead of silently guessing from limits.
    if ranking["work"] == "worst_normalized":
        return "worst_normalized ranking is not supported by this scorer"
    if (ranking["work"], ranking["proof"]) not in {
            ("total", "include"),
            ("curve", "gate"),
            ("curve", "last_tiebreak"),
    }:
        return "grouped evaluation has an inconsistent work/proof ranking policy"

    groups = evaluation["groups"]
    if not isinstance(groups, list) or not groups:
        return "grouped evaluation requires at least one group"
    group_by_id = {}
    sampling_by_id = {}
    orders = set()
    for group in groups:
        required = {"id", "label", "order", "sampling", "limits"}
        if not full_plan:
            required.add("award")
        allowed = required if full_plan else required | {"requires"}
        if not (isinstance(group, dict)
                and required <= set(group)
                and set(group) <= allowed):
            return "grouped evaluation has an invalid group field set"
        group_id = group.get("id")
        order = group.get("order")
        if (not _nonempty_string(group_id) or group_id in group_by_id
                or not _nonempty_string(group.get("label"))
                or type(order) is not int or order < 0 or order in orders
                or not isinstance(group.get("sampling"), dict)
                or not isinstance(group.get("limits"), dict)):
            return "grouped evaluation has an invalid group identity or metadata"
        limits = group["limits"]
        unknown_limits = set(limits) - {"timeout_seconds", "kernel_instructions"}
        if unknown_limits:
            return (
                f"grouped evaluation group {group_id!r} has unsupported limits "
                f"{sorted(unknown_limits)!r}")
        if (type(limits.get("timeout_seconds")) is not int
                or limits["timeout_seconds"] <= 0):
            return f"grouped evaluation group {group_id!r} lacks a timeout limit"
        for field in ("kernel_instructions",):
            if field in limits and (
                    type(limits[field]) is not int or limits[field] <= 0):
                return f"grouped evaluation group {group_id!r} has an invalid {field} limit"
        requires = group.get("requires", [])
        if not (isinstance(requires, list)
                and all(_nonempty_string(item) for item in requires)
                and len(requires) == len(set(requires))
                and group_id not in requires):
            return f"grouped evaluation group {group_id!r} has invalid prerequisites"

        if not full_plan:
            award = group.get("award")
            table = award.get("table") if isinstance(award, dict) else None
            if not (isinstance(award, dict)
                    and set(award) == {"mode", "table"}
                    and award.get("mode") == "milestones"
                    and isinstance(table, list) and table):
                return f"grouped evaluation group {group_id!r} has an invalid award"
            previous_passed = previous_points = -1
            for milestone in table:
                if not (isinstance(milestone, dict)
                        and set(milestone) == {"passed", "points"}
                        and type(milestone.get("passed")) is int
                        and type(milestone.get("points")) is int
                        and milestone["passed"] >= 0 and milestone["points"] >= 0
                        and milestone["passed"] > previous_passed
                        and milestone["points"] > previous_points):
                    return f"grouped evaluation group {group_id!r} has invalid milestones"
                previous_passed = milestone["passed"]
                previous_points = milestone["points"]
            if table[0] != {"passed": 0, "points": 0}:
                return f"grouped evaluation group {group_id!r} must start at 0 passed / 0 points"
        sampling_error, sampling_meta = _group_sampling_shape(
            group["sampling"], official=official)
        if sampling_error is not None:
            return f"grouped evaluation group {group_id!r}: {sampling_error}"
        group_by_id[group_id] = group
        sampling_by_id[group_id] = sampling_meta
        orders.add(order)

    profile_mode = ranking.get("profile")
    interchangeable = {"packed", "uniform_int"}
    sampling_kinds = {sampling["kind"] for sampling in sampling_by_id.values()}
    if (profile_mode == "hardest_group_then_count"
            and not sampling_kinds <= interchangeable):
        return "hardest_group_then_count requires interchangeable seeded samplers"
    if (profile_mode == "hardest_group_then_slot"
            and sampling_kinds & interchangeable):
        return "interchangeable seeded samplers require hardest_group_then_count"

    if [group["order"] for group in groups] != sorted(orders):
        return "grouped evaluation groups are not ordered by difficulty"
    for group in groups:
        for prerequisite in group.get("requires", []):
            required_group = group_by_id.get(prerequisite)
            if required_group is None or required_group["order"] >= group["order"]:
                return f"grouped evaluation group {group['id']!r} has an invalid prerequisite"

    if not isinstance(performance_plan, list) or not performance_plan:
        return "evaluation cohort policy has an invalid performance plan"
    plan_counts = {group_id: 0 for group_id in group_by_id}
    plan_cases = {group_id: [] for group_id in group_by_id}
    plan_values = {group_id: [] for group_id in group_by_id}
    expected_order = []
    for slot, case in enumerate(performance_plan):
        allowed = {"slot", "group", "case", "n", "limits", "scale"}
        if not (isinstance(case, dict)
                and {"slot", "group", "case", "n", "limits"} <= set(case)
                and set(case) <= allowed
                and type(case.get("slot")) is int and case["slot"] == slot
                and _nonempty_string(case.get("group"))
                and case["group"] in group_by_id
                and type(case.get("case")) is int and case["case"] >= 0
                and type(case.get("n")) is int and case["n"] >= 0
                and isinstance(case.get("limits"), dict)):
            return "evaluation cohort policy has an invalid performance-plan row"
        if "scale" in case and (type(case["scale"]) is not int or case["scale"] < 0):
            return "evaluation cohort policy has an invalid packed-case scale"
        group_id = case["group"]
        sampling = sampling_by_id[group_id]
        if sampling["kind"] == "packed":
            if ("scale" not in case
                    or case["scale"] != sampling["scale"]
                    or case["n"] >> 32 != case["scale"]):
                return "performance plan does not match its packed sampling policy"
        elif "scale" in case:
            return "non-packed performance-plan row carries a scale"
        if sampling["kind"] == "fixed":
            case_index = case["case"]
            if (case_index >= len(sampling["values"])
                    or case["n"] != sampling["values"][case_index]):
                return "performance plan does not match its fixed sampling values"
        elif sampling["kind"] in (
                "geometric_range", "linear_range", "range", "uniform_int"):
            if not sampling["min"] <= case["n"] <= sampling["max"]:
                return "performance plan input lies outside its published sampling range"
        if case["limits"] != group_by_id[group_id]["limits"]:
            return "performance-plan limits do not match the grouped evaluation"
        plan_counts[group_id] += 1
        plan_cases[group_id].append(case["case"])
        plan_values[group_id].append(case["n"])
        expected_order.append((group_by_id[group_id]["order"], case["case"]))
    if expected_order != sorted(expected_order):
        return "performance plan is not ordered by group difficulty and case"
    for group_id, group in group_by_id.items():
        count = plan_counts[group_id]
        if count < 1 or plan_cases[group_id] != list(range(count)):
            return f"performance plan has invalid cases for group {group_id!r}"
        sampling = sampling_by_id[group_id]
        sampling_count = sampling["count"]
        if count > sampling_count or (official and count != sampling_count):
            return f"performance plan does not match group {group_id!r} sampling count"
        if (sampling["kind"] in ("geometric_range", "linear_range", "range")
                and any(left >= right for left, right in zip(
                    plan_values[group_id], plan_values[group_id][1:]))):
            return f"performance plan range cases are not increasing for group {group_id!r}"
        if not full_plan and group["award"]["table"][-1]["passed"] != sampling_count:
            return f"group {group_id!r} does not award its final milestone at full coverage"
    return None


def _policy_v2_shape_error(policy):
    common_fields = _V1_POLICY_FIELDS - {"perf", "perf_defaults"}
    required = common_fields | {
        "evaluation", "performance_plan", "performance_plan_sha256",
        "seed_commitment",
    }
    evaluation = policy.get("evaluation")
    ranking = evaluation.get("ranking") if isinstance(evaluation, dict) else None
    full_plan = isinstance(ranking, dict) and ranking.get("contract") == "full-plan-v1"
    if full_plan:
        required.add("reference_answers")
    if set(policy) != required:
        return "evaluation cohort policy has an incomplete or unknown field set"
    if full_plan:
        reference = policy["reference_answers"]
        if (not isinstance(reference, dict)
                or set(reference) != {"contract", "sha256", "spec_sha256", "count"}
                or reference["contract"] != "reference-answers-v1"
                or not _sha256_string(reference["sha256"])
                or not _sha256_string(reference["spec_sha256"])
                or type(reference["count"]) is not int
                or not isinstance(policy.get("inputs"), list)
                or reference["count"] != len(policy["inputs"])):
            return "full-plan evaluation has an invalid reference-answer seal"

    # Reuse every v1 environment/measurement check.  Only the schema and the added
    # grouped fields differ in v2.
    inputs = policy.get("inputs")
    if not (isinstance(inputs, list) and inputs
            and all(type(n) is int and n >= 0 for n in inputs)
            and len(inputs) == len(set(inputs))):
        return "evaluation cohort policy has invalid grouped inputs"
    budgets = policy.get("budgets")
    budget_fields = {
        "comparator_timeout_seconds", "audit_timeout_seconds",
        "timing_timeout_seconds", "perf_phase_budget_seconds",
    }
    if not (isinstance(budgets, dict) and set(budgets) == budget_fields
            and budgets.get("perf_phase_budget_seconds") == 0
            and all(type(budgets.get(field)) is int and budgets[field] > 0
                    for field in budget_fields - {"perf_phase_budget_seconds"})):
        return "grouped evaluation must disable the aggregate performance-phase deadline"

    common = {field: policy[field] for field in common_fields}
    # Reuse the v1 validator for the shared fields.  Its legacy aggregate budget
    # must be positive, whereas v2 deliberately seals zero (disabled).
    common["budgets"] = {
        **budgets,
        "perf_phase_budget_seconds": 1,
    }
    common["schema"] = "evaluation-policy-v1"
    common["inputs"] = sorted(inputs)
    common["perf"] = {"min": min(inputs), "max": max(inputs)}
    common["perf_defaults"] = {
        "count": len(inputs), "spacing": "linear", "jitter": 0.15,
    }
    common_error = _policy_v1_shape_error(common)
    if common_error is not None:
        return common_error
    if (policy["evaluation_mode"] == "official"
            and policy["reps"] != STAGE1_OFFICIAL_REPS):
        return (
            f"official grouped evaluation requires exactly "
            f"{STAGE1_OFFICIAL_REPS} repetitions")
    if policy["evaluation_mode"] == "official":
        resources = policy["resource_policy"]
        evaluation = policy.get("evaluation")
        declared_memory = _evaluation_memory_mb(evaluation)
        if (not valid_memory_mb(declared_memory)
                or memory_mb_from_envelope(resources["memory"]) != declared_memory
                or resources["cpus"] != "2"
                or resources["pids_limit"] != "512"):
            return "official grouped evaluation has a noncanonical resource envelope"
        if (policy["executor"]["kind"] != "local"
                or policy["timing_protocol"] != LOCAL_PROTOCOL):
            return "official grouped evaluation must use the local PMU protocol"
        if budgets != STAGE1_OFFICIAL_BUDGETS:
            return "official grouped evaluation has noncanonical watchdog budgets"
        if policy["toolchain"] != STAGE1_OFFICIAL_TOOLCHAIN:
            return "official grouped evaluation was sealed under a different toolchain"
    plan = policy["performance_plan"]
    plan_digest = _policy_digest(plan)
    if (not _sha256_string(policy["performance_plan_sha256"])
            or policy["performance_plan_sha256"] != plan_digest):
        return "evaluation cohort policy has an invalid performance-plan hash"
    commitment = policy["seed_commitment"]
    if policy["evaluation_mode"] == "official":
        if not _sha256_string(commitment):
            return "official evaluation cohort policy has an invalid seed commitment"
    elif commitment is not None and not _sha256_string(commitment):
        return "development evaluation cohort policy has an invalid seed commitment"
    grouped_error = _grouped_evaluation_shape_error(
        policy["evaluation"], plan,
        official=policy["evaluation_mode"] == "official")
    if grouped_error is not None:
        return grouped_error
    if policy["inputs"] != [case["n"] for case in plan]:
        return "evaluation cohort policy inputs do not match its performance plan"
    return None


def _policy_shape_error(policy):
    """Validate either immutable scoring-policy generation without weakening v1."""
    if not isinstance(policy, dict):
        return "evaluation cohort policy is not an object"
    schema = policy.get("schema")
    if schema == "evaluation-policy-v1":
        return _policy_v1_shape_error(policy)
    if schema == "evaluation-policy-v2":
        return _policy_v2_shape_error(policy)
    return "unsupported evaluation cohort policy schema"


def _fit(points):
    """Report-only least-squares (α, β) for log cost ≈ α·log n + β."""
    points = [(n, value) for n, value in points if n > 0]
    if len(points) < 2:
        return None, None
    xs = [math.log(n) for n, _ in points]
    ys = [math.log(value) for _, value in points]
    m = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    denominator = m * sxx - sx * sx
    if denominator == 0:
        return None, None
    alpha = (m * sxy - sx * sy) / denominator
    beta = (sy - alpha * sx) / m
    return alpha, beta


def _measurement_contract_error(verdict):
    """Return why a verdict is not a current scoped-replay measurement, or None.

    This is intentionally exact and fail-closed. Merely sharing an evaluation-cohort id with
    current results cannot make a legacy whole-process verdict scoreable.
    """
    cohort = verdict.get("evaluation_cohort")
    if not (isinstance(cohort, dict)
            and isinstance(cohort.get("id"), str) and cohort["id"]
            and isinstance(cohort.get("round"), str) and cohort["round"]):
        return "missing/invalid evaluation_cohort"
    executor = cohort.get("executor") if isinstance(cohort, dict) else None
    if not (isinstance(executor, dict)
            and executor.get("kind") in ("local", "remote")
            and isinstance(executor.get("executor"), str)
            and executor["executor"]
            and isinstance(executor.get("version"), str)
            and executor["version"]):
        return "missing/invalid evaluation cohort executor"

    policy = cohort.get("policy")
    policy_sha256 = cohort.get("policy_sha256")
    actual_policy_sha256 = _policy_digest(policy)
    if not (isinstance(policy, dict)
            and isinstance(policy_sha256, str) and len(policy_sha256) == 64
            and actual_policy_sha256 == policy_sha256):
        return "missing/invalid evaluation cohort policy"
    if cohort["id"] != policy_sha256[:24]:
        return "evaluation cohort id does not match its policy hash"
    policy_schema = policy.get("schema")
    if policy_schema not in ("evaluation-policy-v1", "evaluation-policy-v2"):
        return "unsupported evaluation cohort policy schema"
    shape_error = _policy_shape_error(policy)
    if shape_error is not None:
        return shape_error
    mode = verdict.get("evaluation_mode")
    if mode not in ("official", "development") or policy.get("evaluation_mode") != mode:
        return "missing/mismatched evaluation mode"
    stages = verdict.get("stages", {})
    planned = stages.get("perf_inputs") if isinstance(stages, dict) else None
    if (policy.get("round") != cohort["round"]
            or policy.get("problem") != verdict.get("problem")
            or policy.get("inputs") != planned
            or policy.get("metric") != verdict.get("metric")
            or policy.get("measurement_contract") != CURRENT_MEASUREMENT_RECORD
            or policy.get("executor") != executor):
        return "evaluation cohort policy does not match the verdict"
    if (policy_schema == "evaluation-policy-v2"
            and stages.get("performance_plan") != policy.get("performance_plan")):
        return "verdict performance_plan does not match the evaluation cohort policy"

    expected_protocol = LOCAL_PROTOCOL if executor["kind"] == "local" else REMOTE_PROTOCOL
    protocol = verdict.get("timing_protocol")
    if protocol != expected_protocol:
        return (
            f"missing/mismatched timing protocol "
            f"(expected {expected_protocol}, got {protocol!r})"
        )
    if policy.get("timing_protocol") != protocol:
        return "evaluation cohort policy has a mismatched timing protocol"

    if verdict.get("measurement_contract") != CURRENT_MEASUREMENT_RECORD:
        return f"missing/mismatched measurement contract {MEASUREMENT_CONTRACT}"

    correctness = verdict.get("correctness_timing")
    if not isinstance(correctness, dict):
        return "legacy verdict: missing correctness_timing"
    if correctness.get("measurement_contract") != MEASUREMENT_CONTRACT:
        return "missing/mismatched correctness measurement contract"
    if correctness.get("checker") != policy.get("checker"):
        return "correctness checker does not match the evaluation policy"
    if correctness.get("measurement_boundary") != CORRECTNESS_BOUNDARY:
        return "missing/mismatched correctness measurement boundary"
    if "measurement_target" not in correctness or correctness["measurement_target"] is not None:
        return "correctness measurement target must be null"

    timing = verdict.get("timing")
    if not isinstance(timing, dict):
        return "missing timing record"
    if timing.get("measurement_contract") != MEASUREMENT_CONTRACT:
        return "missing/mismatched performance measurement contract"
    if timing.get("checker") != policy.get("checker"):
        return "performance checker does not match the evaluation policy"
    if timing.get("measurement_boundary") != PERFORMANCE_BOUNDARY:
        return "missing/mismatched performance measurement boundary"
    reps = policy.get("reps")
    if (type(reps) is not int or reps < 1
            or type(correctness.get("reps")) is not int
            or type(timing.get("reps")) is not int
            or correctness.get("reps") != reps or timing.get("reps") != reps):
        return "missing/mismatched timing repetition count"
    return None


def _base_row(verdict, metric, reason):
    return {
        "sub": verdict.get("submission", "<?>"),
        "metric": metric,
        "cohort": None,
        "round": None,
        "timing_protocol": verdict.get("timing_protocol"),
        "measurement_contract": None,
        "scoreable": False,
        "reason": reason,
        "planned_slots": 0,
        "completed_slots": 0,
        "coverage": 0.0,
        "slot_profile": (),
        "reach": None,
        "correctness_work": None,
        "curve_work": None,
        "total_work": None,
        "alpha": None,
        "beta": None,
        "scoring_schema": None,
        "points": None,
        "group_points": {},
        "group_points_profile": (),
        "group_points_detail": (),
        "case_profile": (),
        "group_case_detail": (),
        "ranking_work": None,
        "ranking_work_profile": (),
        "work_tiebreak_active": False,
        "ranking_policy": None,
    }


def _milestone_points(table, passed):
    """Return the greatest points milestone reached by ``passed`` cases."""
    points = 0
    for milestone in table:
        if milestone["passed"] > passed:
            break
        points = milestone["points"]
    return points


def _apply_grouped_scoring(row, policy, slot_values):
    """Derive v2 points and tie-break profiles solely from the sealed policy."""
    evaluation = policy["evaluation"]
    plan = policy["performance_plan"]
    groups = evaluation["groups"]
    passed_by_group = {group["id"]: 0 for group in groups}
    slots_by_group = {group["id"]: [] for group in groups}
    work_by_group = {group["id"]: 0 for group in groups}
    for case in plan:
        slot = case["slot"]
        group_id = case["group"]
        passed = row["slot_profile"][slot] == 1
        slots_by_group[group_id].append((case["case"], passed))
        if passed:
            passed_by_group[group_id] += 1
            work_by_group[group_id] += slot_values[slot]

    ranking = evaluation["ranking"]
    if ranking["contract"] == "full-plan-v1":
        complete = row["completed_slots"] == row["planned_slots"]
        row["points"] = ranking["max_points"] if complete else 0
        row["ranking_policy"] = dict(ranking)
        row["work_tiebreak_active"] = complete
        # Failed plans all have infinite competitive cost; successful-subset costs
        # remain diagnostics only and must never rank one failed plan above another.
        row["ranking_work"] = (
            row["total_work"] if ranking["work"] == "total" else row["curve_work"]
        ) if complete else math.inf
        row["group_case_detail"] = tuple(
            (group["id"], passed_by_group[group["id"]], len(slots_by_group[group["id"]]))
            for group in reversed(groups))
        return

    maximum_passed = {
        group["id"]: group["award"]["table"][-1]["passed"] for group in groups
    }
    group_points = {}
    eligible_by_group = {}
    for group in groups:
        group_id = group["id"]
        prerequisites_met = all(
            passed_by_group[required] >= maximum_passed[required]
            for required in group.get("requires", [])
        )
        eligible_by_group[group_id] = prerequisites_met
        group_points[group_id] = (
            _milestone_points(group["award"]["table"], passed_by_group[group_id])
            if prerequisites_met else 0
        )

    hardest = sorted(groups, key=lambda group: group["order"], reverse=True)
    row["points"] = sum(group_points.values())
    row["group_points"] = group_points
    row["group_points_profile"] = tuple(
        group_points[group["id"]] for group in hardest)
    row["group_points_detail"] = tuple(
        (group["id"], group_points[group["id"]],
         group["award"]["table"][-1]["points"])
        for group in hardest
    )
    ranking = evaluation["ranking"]
    row["ranking_policy"] = dict(ranking)
    if ranking["profile"] == "hardest_group_then_count":
        # Packed/uniform cases within one group are exchangeable random instances.  Comparing
        # their arbitrary hidden case indices would introduce a random tie-break.  Count passes
        # by difficulty group instead, and compare work only once every case is shared.
        row["case_profile"] = tuple(
            passed_by_group[group["id"]] if eligible_by_group[group["id"]] else 0
            for group in hardest)
        row["group_case_detail"] = tuple(
            (group["id"], passed_by_group[group["id"]],
             len(slots_by_group[group["id"]]))
            for group in hardest
        )
        row["work_tiebreak_active"] = (
            row["completed_slots"] == row["planned_slots"])
    else:
        # Eligibility gates the ranking bits here exactly as in count mode: a group whose
        # prerequisites are unmet earns no points and must contribute zero to the ranking
        # profile, or its bits could still decide a tie the published rules say it cannot.
        # (group_case_detail below stays raw in both modes — it is display, not ranking.)
        row["case_profile"] = tuple(
            int(passed) if eligible_by_group[group["id"]] else 0
            for group in hardest
            for _, passed in sorted(
                slots_by_group[group["id"]], key=lambda pair: pair[0], reverse=True)
        )
        row["group_case_detail"] = tuple(
            (group["id"], "".join(
                "1" if passed else "0"
                for _, passed in sorted(
                    slots_by_group[group["id"]],
                    key=lambda pair: pair[0], reverse=True)))
            for group in hardest
        )
        row["work_tiebreak_active"] = True

    work_mode = ranking["work"]
    proof_mode = ranking["proof"]
    if work_mode == "total":
        row["ranking_work"] = row["total_work"]
    elif work_mode == "curve":
        # ``include`` means the proof is part of the first work comparator.  ``gate``
        # excludes it after validity, and ``last_tiebreak`` appends it below.
        row["ranking_work"] = (
            row["total_work"] if proof_mode == "include" else row["curve_work"])
    else:  # rejected by policy validation; defensive for direct helper callers
        row["ranking_work"] = None
    row["ranking_work_profile"] = tuple(
        work_by_group[group["id"]] for group in hardest)


def _is_grouped_row(row):
    return row.get("scoring_schema") == "grouped-evaluation-v1"


def _score_row(verdict, metric):
    """Validate one verdict and derive its canonical ranking fields.

    New-format verdicts have one scaling row for every planned slot. Successful
    rows carry the metric-specific median and failures remain explicit. This makes
    coverage auditable rather than inferring it from the largest sampled input.
    """
    row = _base_row(verdict, metric, None)
    if isinstance(verdict.get("problem"), str) and verdict["problem"] in RETIRED_PROBLEMS:
        row["reason"] = "retired problem is not scoreable"
        return row
    if verdict.get("status") != "accepted":
        row["reason"] = "verdict status is not accepted"
        return row
    if not isinstance(metric, str) or metric not in METRICS:
        row["reason"] = "unknown metric"
        return row
    cohort = verdict.get("evaluation_cohort")
    if not (isinstance(cohort, dict)
            and isinstance(cohort.get("id"), str) and cohort["id"]
            and isinstance(cohort.get("round"), str) and cohort["round"]):
        row["reason"] = "missing/invalid evaluation_cohort"
        return row
    row["cohort"] = cohort["id"]
    row["round"] = cohort["round"]
    contract_error = _measurement_contract_error(verdict)
    if contract_error is not None:
        row["reason"] = contract_error
        return row
    policy = cohort["policy"]
    grouped = policy["schema"] == "evaluation-policy-v2"
    full_plan = grouped and policy["evaluation"]["ranking"]["contract"] == "full-plan-v1"
    row["scoring_schema"] = (
        "grouped-evaluation-v1" if grouped else "legacy-slot-ranking-v1")
    row["measurement_contract"] = MEASUREMENT_CONTRACT
    if verdict.get("metric") != metric:
        row["reason"] = "metric group mismatch"
        return row

    timing = verdict.get("timing")
    if not isinstance(timing, dict) or timing.get("metric") != metric:
        row["reason"] = "timing.metric does not match verdict metric"
        return row

    correctness = verdict["correctness_timing"]
    if correctness.get("result") != "ok" or correctness.get("metric") != metric:
        row["reason"] = "correctness replay did not complete in the declared metric"
        return row

    cost_field = METRICS[metric]["field"]
    correctness_work = correctness.get(cost_field)
    if not _is_cost(correctness_work, integral=(metric == "perf_instructions")):
        row["reason"] = f"correctness_timing lacks a positive {cost_field}"
        return row

    planned = verdict.get("stages", {}).get("perf_inputs")
    if not (isinstance(planned, list) and planned
            and all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in planned)
            and len(planned) == len(set(planned))
            and (grouped or planned == sorted(planned))):
        row["reason"] = "invalid or non-distinct perf_inputs"
        return row
    row["planned_slots"] = len(planned)

    scaling = timing.get("scaling")
    if not isinstance(scaling, list) or len(scaling) != len(planned):
        row["reason"] = "scaling must contain one explicit row per planned slot"
        return row

    by_slot = {}
    for sample in scaling:
        if not isinstance(sample, dict):
            row["reason"] = "invalid scaling row"
            return row
        slot = sample.get("slot")
        if not isinstance(slot, int) or isinstance(slot, bool) or slot in by_slot:
            row["reason"] = "scaling rows require unique integer slot identifiers"
            return row
        by_slot[slot] = sample
    if set(by_slot) != set(range(len(planned))):
        row["reason"] = "scaling slots do not match the planned schedule"
        return row

    points = []
    slot_profile = []
    slot_values = {}
    performance_plan = policy.get("performance_plan") if grouped else None
    for slot, planned_n in enumerate(planned):
        sample = by_slot[slot]
        if type(sample.get("n")) is not int or sample.get("n") != planned_n:
            row["reason"] = f"slot {slot} input does not match perf_inputs"
            return row
        if grouped:
            planned_case = performance_plan[slot]
            if (sample.get("group") != planned_case["group"]
                    or type(sample.get("case")) is not int
                    or sample.get("case") != planned_case["case"]):
                row["reason"] = (
                    f"slot {slot} group/case does not match performance_plan")
                return row
        sample_result = sample.get("result")
        if not isinstance(sample_result, str) or sample_result not in PERFORMANCE_RESULTS:
            row["reason"] = f"slot {slot} has an unknown result {sample_result!r}"
            return row
        if grouped and sample_result in ("budget-exhausted", "not-run"):
            row["reason"] = "grouped verdict is incomplete and requires evaluation retry"
            return row
        if full_plan and (sample_result.startswith("value-eval-")
                          or sample.get("resource_phase") == "value-eval"):
            row["reason"] = "reference-answer preparation cannot be a contestant case failure"
            return row
        if sample_result in ("ok", "timeout"):
            if sample.get("measurement_contract") != MEASUREMENT_CONTRACT:
                row["reason"] = (
                    f"measured slot {slot} has a mismatched measurement contract")
                return row
            if sample.get("measurement_boundary") != PERFORMANCE_BOUNDARY:
                row["reason"] = (
                    f"measured slot {slot} has a mismatched measurement boundary")
                return row
            if not (isinstance(sample.get("measurement_target"), str)
                    and sample["measurement_target"]):
                row["reason"] = (
                    f"measured slot {slot} lacks a measurement target")
                return row
        if sample_result == "resource-limit":
            memory_mb = sample.get("memory_mb")
            if policy["evaluation_mode"] == "official":
                canonical_memory = (valid_memory_mb(memory_mb)
                                    and memory_mb == _evaluation_memory_mb(policy["evaluation"]))
            else:
                canonical_memory = memory_mb is None or (
                    isinstance(memory_mb, int) and not isinstance(memory_mb, bool)
                    and memory_mb > 0)
            if (sample.get("resource") != "memory"
                    or not canonical_memory
                    or not isinstance(sample.get("resource_limit_source"), str)
                    or sample.get("resource_phase") not in {
                        "value-eval", "build-export", "axiom-audit", "target-replay",
                    }):
                row["reason"] = f"resource-limited slot {slot} lacks the canonical memory record"
                return row
            if sample["resource_phase"] == "target-replay":
                if (sample.get("measurement_contract") != MEASUREMENT_CONTRACT
                        or sample.get("measurement_boundary") != PERFORMANCE_BOUNDARY
                        or not isinstance(sample.get("measurement_target"), str)
                        or not sample["measurement_target"]):
                    row["reason"] = (
                        f"resource-limited target slot {slot} lacks its measurement identity")
                    return row
        if sample_result == "ok":
            value = sample.get(cost_field)
            if not _is_cost(value, integral=(metric == "perf_instructions")):
                row["reason"] = f"successful slot {slot} lacks a positive {cost_field}"
                return row
            within_limit = True
            if grouped and metric == "perf_instructions":
                instruction_cap = performance_plan[slot]["limits"].get(
                    "kernel_instructions")
                within_limit = instruction_cap is None or value <= instruction_cap
            if within_limit:
                points.append((planned_n, value))
                slot_values[slot] = value
                slot_profile.append(1)
            else:
                slot_profile.append(0)
        else:
            slot_profile.append(0)

    completed = len(points)
    row["completed_slots"] = completed
    row["coverage"] = completed / len(planned)
    row["slot_profile"] = tuple(slot_profile)
    row["reach"] = max((n for n, _ in points), default=None)
    row["correctness_work"] = correctness_work
    row["curve_work"] = sum(value for _, value in points)
    alpha, beta = _fit(points)
    row["alpha"], row["beta"] = alpha, beta

    if not points and not grouped:
        row["reason"] = "accepted but completed no performance slot"
        return row

    row["total_work"] = row["correctness_work"] + row["curve_work"]
    if not _is_cost(row["total_work"], integral=(metric == "perf_instructions")):
        row["reason"] = "total measured work is not a finite positive cost"
        return row
    if grouped:
        _apply_grouped_scoring(row, policy, slot_values)
        if not _is_cost(row["ranking_work"], integral=(metric == "perf_instructions")):
            # A zero curve is legitimate only when no case passed; the success profile is
            # compared first, so treating it as an exact zero tie-break cannot reward failure.
            full_plan_failure = (
                row["ranking_policy"]["contract"] == "full-plan-v1"
                and row["completed_slots"] < row["planned_slots"]
                and row["ranking_work"] == math.inf)
            if not (full_plan_failure or (row["ranking_work"] == 0 and not points)):
                row["reason"] = "grouped ranking work is not a finite nonnegative cost"
                return row
    row["scoreable"] = True
    return row


def _placement_key(row):
    """Competitive ranking values only; submission names never affect placement."""
    if not row["scoreable"]:
        return None
    if _is_grouped_row(row):
        if row.get("ranking_policy", {}).get("contract") == "full-plan-v1":
            return (-row["points"], row["ranking_work"])
        # Profiles are compared before work, so work is only compared for submissions
        # that passed the same cases.  This prevents cheap failures from improving rank.
        key = (
            -row["points"],
            tuple(-points for points in row["group_points_profile"]),
            tuple(-passed for passed in row["case_profile"]),
        )
        if row.get("work_tiebreak_active"):
            key += (row["ranking_work"],)
            policy = row.get("ranking_policy", {})
            if policy.get("proof") == "last_tiebreak":
                key += (row["correctness_work"],)
        return key
    # Higher-index slots are nominally harder. Comparing the complete success bitmap before
    # work also guarantees that total_work is only compared over the same set of n values.
    harder_slots_first = tuple(-bit for bit in reversed(row["slot_profile"]))
    return (-row["completed_slots"], -row["coverage"],
            harder_slots_first, row["total_work"])


def _rank_key(row):
    placement = _placement_key(row)
    if placement is None:
        return (1, str(row["sub"]))
    # Name is a deterministic display-order key only. `_competition_ranks` ignores it.
    return (0, *placement, str(row["sub"]))


def _competition_ranks(rows):
    """Return standard competition ranks (1, 1, 3) for already sorted rows."""
    ranks = []
    previous = object()
    current_rank = 0
    scored_position = 0
    for row in rows:
        placement = _placement_key(row)
        if placement is None:
            ranks.append(None)
            continue
        scored_position += 1
        if placement != previous:
            current_rank = scored_position
            previous = placement
        ranks.append(current_rank)
    return ranks


def _rows_for(problem, verdicts, metric):
    """Return one strictly single-metric ranking group."""
    del problem  # kept in the API because callers naturally score per problem
    rows = [_score_row(v, metric) for v in verdicts if v.get("metric") == metric]
    rows.sort(key=_rank_key)
    return rows


def _groups(verdicts):
    """Accepted verdicts grouped without crossing metric or evaluation cohorts."""
    groups = {}
    for verdict in verdicts:
        metric = verdict.get("metric")
        if (verdict.get("status") != "accepted"
                or (isinstance(verdict.get("problem"), str)
                    and verdict["problem"] in RETIRED_PROBLEMS)
                or not isinstance(metric, str) or metric not in METRICS):
            continue
        cohort = verdict.get("evaluation_cohort")
        cohort_id = cohort.get("id") if isinstance(cohort, dict) else None
        # Coerce to a single type: a dict missing/null "id" would otherwise yield None, which
        # cannot be sorted alongside the "<missing>" string produced for non-dict cohorts.
        if not isinstance(cohort_id, str):
            cohort_id = "<missing>"
        groups.setdefault((verdict["problem"], metric, cohort_id), []).append(verdict)
    return groups


def _is_grouped_verdict(verdict):
    """Whether a verdict carries the current grouped policy, including development runs."""
    cohort = verdict.get("evaluation_cohort")
    policy = cohort.get("policy") if isinstance(cohort, dict) else None
    return isinstance(policy, dict) and policy.get("schema") == "evaluation-policy-v2"


def _is_stage1_public_verdict(verdict):
    """Whether a verdict belongs in the official public Stage 1 reports.

    Legacy v1 scoring remains available through ``_score_row`` and ``_groups``
    for development and regression compatibility. Grouped wall-time and KTP/3
    validation records are likewise non-official and never enter public boards.
    """
    cohort = verdict.get("evaluation_cohort")
    policy = cohort.get("policy") if isinstance(cohort, dict) else None
    executor = policy.get("executor") if isinstance(policy, dict) else None
    return (
        _is_grouped_verdict(verdict)
        and isinstance(verdict.get("problem"), str)
        and verdict.get("problem") in STAGE1_PROBLEMS
        and verdict.get("evaluation_mode") == "official"
        and policy.get("evaluation_mode") == "official"
        and verdict.get("metric") == "perf_instructions"
        and verdict.get("timing_protocol") == LOCAL_PROTOCOL
        and isinstance(executor, dict)
        and executor.get("kind") == "local"
    )


def _stage1_problem_ids():
    """Return the fixed public Stage 1 allowlist; cohort policy supplies score semantics."""
    return set(STAGE1_PROBLEMS)


def _format_work(value, metric):
    integral = metric == "perf_instructions"
    if value == math.inf:
        return "∞"
    if value == 0 and not isinstance(value, bool):
        return "0"
    if not _is_cost(value, integral=integral):
        return "—"
    try:
        if integral:
            return str(value)
        return f"{value:.6g}"
    except (OverflowError, TypeError, ValueError):
        return "—"


def _format_group_points(row):
    """Render labeled hardest-first group points from a canonical score row."""
    return ", ".join(
        f"{group_id}:{earned}/{maximum}"
        for group_id, earned, maximum in row.get("group_points_detail", ())
    ) or "—"


def _format_group_cases(row):
    """Render the exact ranking-relevant case profile without exposing inputs."""
    detail = row.get("group_case_detail", ())
    if not detail:
        return "—"
    if all(len(item) == 3 for item in detail):
        return ", ".join(
            f"{group_id}:{passed}/{total}"
            for group_id, passed, total in detail
        )
    return ", ".join(f"{group_id}:{bitmap}" for group_id, bitmap in detail)


def _write_text_atomic(path, text):
    """Report files must never be observable half-written (a crash mid-write would leave a
    fresh scoring.md alongside stale per-problem boards); write-then-rename is atomic on POSIX."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def main():
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    stage1_problems = _stage1_problem_ids()
    groups = _groups([
        verdict for verdict in _load_verdicts()
        if (_is_stage1_public_verdict(verdict)
            and verdict.get("problem") in stage1_problems)
    ])

    # Fail-closed cohort integrity, checked before anything is written.
    # (a) A ranking table's rows must all be sealed under ONE policy: the grouping key's
    #     cohort id is the 96-bit hash prefix, so demand full-hash agreement inside it.
    # (b) One (problem, round) must not span multiple official cohorts: that is the
    #     signature of a mid-round seed rotation, env drift, or a stale verdict left in
    #     results/ — each fragment would silently get its own rank 1. An operator who
    #     intends parallel cohorts must say so explicitly.
    split = {}
    for (problem, metric, cohort_id), members in sorted(groups.items()):
        hashes = {
            (m.get("evaluation_cohort") or {}).get("policy_sha256")
            for m in members if isinstance(m.get("evaluation_cohort"), dict)
        }
        if len(hashes) > 1:
            raise SystemExit(
                f"refusing to score: cohort `{cohort_id}` ({problem}, {metric}) contains "
                f"verdicts sealed under {len(hashes)} different policies")
        rounds = {
            (m.get("evaluation_cohort") or {}).get("round") for m in members
        }
        for round_id in rounds:
            split.setdefault((problem, metric, round_id), set()).add(cohort_id)
    conflicts = {key: ids for key, ids in split.items() if len(ids) > 1}
    if conflicts and os.environ.get("ALLOW_COHORT_SPLIT") != "1":
        lines = "; ".join(
            f"{problem}/{metric} round `{round_id}`: cohorts {sorted(ids)}"
            for (problem, metric, round_id), ids in sorted(conflicts.items()))
        raise SystemExit(
            "refusing to publish: one round spans multiple official cohorts — likely a "
            "seed rotation, sealed-env drift, or stale verdicts needing cleanup "
            f"({lines}). Set ALLOW_COHORT_SPLIT=1 to publish them side by side anyway.")
    md = [
        "# Lean Kernel Challenge — canonical scoring",
        "",
        "Each problem is ranked independently under the scoring contract sealed into its "
        "evaluation cohort. Full-plan cohorts award 100 points only when every case passes; "
        "other scoreable plans tie at 0 points and infinite cost. Full passes compare the "
        "declared instruction cost. Previously sealed milestone cohorts retain their own rules. "
        "This public Stage 1 report includes grouped v2 cohorts only; legacy v1 scoring remains "
        "available for local compatibility but is not published as a Stage 1 leaderboard. "
        f"Only official {LOCAL_PROTOCOL} verdicts under {MEASUREMENT_CONTRACT} enter these "
        f"public boards. {REMOTE_PROTOCOL} and wall-time grouped verdicts remain "
        "validation-only. α and β are diagnostics only. "
        "Instruction, wall-time, and evaluation cohorts are never mixed. "
        "See `rules/evaluation.md`.",
        "",
    ]

    problem_sections = {problem: [] for problem in stage1_problems}
    for problem, metric, cohort_id in sorted(groups):
        section_start = len(md)
        label = METRICS[metric]["label"]
        first = groups[(problem, metric, cohort_id)][0]
        cohort = first.get("evaluation_cohort")
        round_id = cohort.get("round") if isinstance(cohort, dict) else "missing"
        md.append(f"## {problem} — {label} — cohort `{cohort_id}`")
        md.append("")
        md.append(f"Round: `{round_id}`")
        md.append(f"Generated: {generated_at}")
        md.append("")
        rows = _rows_for(problem, groups[(problem, metric, cohort_id)], metric)
        # Keep the shared hidden schedule out of the publishable table. Raw verdicts are
        # operator-private until the cohort closes (rules/evaluation.md).
        grouped = (isinstance(cohort, dict)
                   and isinstance(cohort.get("policy"), dict)
                   and cohort["policy"].get("schema") == "evaluation-policy-v2")
        full_plan = grouped and cohort["policy"]["evaluation"]["ranking"]["contract"] == "full-plan-v1"
        if full_plan:
            md.append("| rank | submission | points | cases | ranking cost | status |")
            md.append("|---|---|---|---|---|---|")
        elif grouped:
            md.append("| rank | submission | points | group points | case outcomes | "
                      "cases | performance work | proof work | status |")
            md.append("|---|---|---|---|---|---|---|---|---|")
        else:
            md.append("| rank | submission | coverage | correctness work | "
                      "curve work | total work | α (report only) | β (report only) | status |")
            md.append("|---|---|---|---|---|---|---|---|---|")
        for row, placement in zip(rows, _competition_ranks(rows)):
            if row["scoreable"]:
                rank = str(placement)
                status = "scored"
            else:
                rank = "—"
                status = row["reason"] or "unscored"
            alpha = f"{row['alpha']:.3f}" if row["alpha"] is not None else "—"
            beta = f"{row['beta']:.2f}" if row["beta"] is not None else "—"
            coverage = f"{row['completed_slots']}/{row['planned_slots']}"
            if full_plan:
                md.append(
                    f"| {rank} | {row['sub']} | "
                    f"{row['points'] if row['points'] is not None else '—'} | {coverage} | "
                    f"{_format_work(row['ranking_work'], metric)} | {status} |")
            elif grouped:
                group_profile = _format_group_points(row)
                case_profile = _format_group_cases(row)
                performance_work = (
                    _format_work(row["curve_work"], metric)
                    if row["work_tiebreak_active"] else "not compared")
                proof_work = (
                    _format_work(row["correctness_work"], metric)
                    if row["work_tiebreak_active"] else "not compared")
                md.append(
                    f"| {rank} | {row['sub']} | "
                    f"{row['points'] if row['points'] is not None else '—'} | "
                    f"{group_profile} | {case_profile} | {coverage} | "
                    f"{performance_work} | {proof_work} | {status} |"
                )
            else:
                md.append(
                    f"| {rank} | {row['sub']} | {coverage} | "
                    f"{_format_work(row['correctness_work'], metric)} | "
                    f"{_format_work(row['curve_work'], metric)} | "
                    f"{_format_work(row['total_work'], metric)} | {alpha} | {beta} | {status} |"
                )
        md.append("")
        problem_sections[problem].extend(md[section_start:])

    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, "scoring.md")
    _write_text_atomic(out, "\n".join(md))
    for problem in sorted(stage1_problems):
        problem_dir = os.path.join(RESULTS, problem)
        os.makedirs(problem_dir, exist_ok=True)
        problem_out = os.path.join(problem_dir, "leaderboard.md")
        sections = problem_sections[problem]
        body = sections if sections else ["_No scored cohort yet._", ""]
        _write_text_atomic(problem_out, "\n".join([
            f"# Lean Kernel Challenge — {problem} leaderboard",
            "",
            "This leaderboard is independent; no cross-problem total is computed.",
            "",
            *body,
        ]))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
