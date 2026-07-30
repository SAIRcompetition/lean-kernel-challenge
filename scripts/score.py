#!/usr/bin/env python3
"""Build the canonical per-problem scoring tables from judge verdicts.

Official ranking is deliberately simple and monotone:

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
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
with open(os.path.join(ROOT, "pipeline", "config.json")) as _config_file:
    _TIMING_POLICY = json.load(_config_file)["timing"]

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
    "perf_counter_control": "perf-delay-minus-one+timer-prctl",
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


def _load_verdicts():
    rows = []
    if not os.path.isdir(RESULTS):
        return rows
    for prob in sorted(os.listdir(RESULTS)):
        pdir = os.path.join(RESULTS, prob)
        if not os.path.isdir(pdir) or prob in ("work", "plots"):
            continue
        for fn in sorted(os.listdir(pdir)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(pdir, fn)) as f:
                    r = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            if not (isinstance(r, dict) and isinstance(r.get("problem"), str)
                    and isinstance(r.get("submission"), str)
                    and isinstance(r.get("status"), str) and isinstance(r.get("stages"), dict)):
                continue
            rows.append(r)
    return rows


def _is_cost(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(float(value)) and value > 0)


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
            and isinstance(executor.get("executor"), str)
            and executor["executor"]):
        return "missing/invalid evaluation cohort executor"

    expected_protocol = (
        LOCAL_PROTOCOL if executor["executor"] == "local" else REMOTE_PROTOCOL
    )
    protocol = verdict.get("timing_protocol")
    if protocol != expected_protocol:
        return (
            f"missing/mismatched timing protocol "
            f"(expected {expected_protocol}, got {protocol!r})"
        )

    if verdict.get("measurement_contract") != CURRENT_MEASUREMENT_RECORD:
        return f"missing/mismatched measurement contract {MEASUREMENT_CONTRACT}"

    correctness = verdict.get("correctness_timing")
    if not isinstance(correctness, dict):
        return "legacy verdict: missing correctness_timing"
    if correctness.get("measurement_contract") != MEASUREMENT_CONTRACT:
        return "missing/mismatched correctness measurement contract"
    if correctness.get("measurement_boundary") != CORRECTNESS_BOUNDARY:
        return "missing/mismatched correctness measurement boundary"
    if "measurement_target" not in correctness or correctness["measurement_target"] is not None:
        return "correctness measurement target must be null"

    timing = verdict.get("timing")
    if not isinstance(timing, dict):
        return "missing timing record"
    if timing.get("measurement_contract") != MEASUREMENT_CONTRACT:
        return "missing/mismatched performance measurement contract"
    if timing.get("measurement_boundary") != PERFORMANCE_BOUNDARY:
        return "missing/mismatched performance measurement boundary"
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
    }


def _score_row(verdict, metric):
    """Validate one verdict and derive its canonical ranking fields.

    New-format verdicts have one scaling row for every planned slot. Successful
    rows carry the metric-specific median and failures remain explicit. This makes
    coverage auditable rather than inferring it from the largest sampled input.
    """
    row = _base_row(verdict, metric, None)
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
    row["measurement_contract"] = MEASUREMENT_CONTRACT
    if metric not in METRICS or verdict.get("metric") != metric:
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
    if not _is_cost(correctness_work):
        row["reason"] = f"correctness_timing lacks a positive {cost_field}"
        return row

    planned = verdict.get("stages", {}).get("perf_inputs")
    if not (isinstance(planned, list) and planned
            and all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in planned)
            and planned == sorted(set(planned))):
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
    for slot, planned_n in enumerate(planned):
        sample = by_slot[slot]
        if sample.get("n") != planned_n:
            row["reason"] = f"slot {slot} input does not match perf_inputs"
            return row
        sample_result = sample.get("result")
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
        if sample_result == "ok":
            value = sample.get(cost_field)
            if not _is_cost(value):
                row["reason"] = f"successful slot {slot} lacks a positive {cost_field}"
                return row
            points.append((planned_n, value))
            slot_profile.append(1)
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

    if not points:
        row["reason"] = "accepted but completed no performance slot"
        return row

    row["total_work"] = row["correctness_work"] + row["curve_work"]
    row["scoreable"] = True
    return row


def _rank_key(row):
    if not row["scoreable"]:
        return (1, 0, 0, (), math.inf, row["sub"])
    # Higher-index slots are nominally harder. Comparing the complete success bitmap before
    # work also guarantees that total_work is only compared over the same set of n values.
    harder_slots_first = tuple(-bit for bit in reversed(row["slot_profile"]))
    return (0, -row["completed_slots"], -row["coverage"],
            harder_slots_first, row["total_work"], row["sub"])


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
        if verdict.get("status") != "accepted" or metric not in METRICS:
            continue
        cohort = verdict.get("evaluation_cohort")
        cohort_id = cohort.get("id") if isinstance(cohort, dict) else "<missing>"
        groups.setdefault((verdict["problem"], metric, cohort_id), []).append(verdict)
    return groups


def _format_work(value, metric):
    if value is None:
        return "—"
    if metric == "perf_instructions":
        return f"{value:.0f}"
    return f"{value:.6g}"


def main():
    groups = _groups(_load_verdicts())
    md = [
        "# Lean Kernel Challenge — canonical scoring",
        "",
        "Official order: completed slots, then coverage, then harder-slot success profile, "
        "then lower total measured kernel work (one full correctness-closure replay median "
        "plus the completed target-declaration medians). "
        f"Only {REMOTE_PROTOCOL}/{LOCAL_PROTOCOL} verdicts under {MEASUREMENT_CONTRACT} "
        "and its exact replay boundaries are scoreable. α and β are diagnostics only. "
        "Instruction, wall-time, and evaluation cohorts are never mixed. "
        "See `rules/evaluation.md`.",
        "",
    ]

    for problem, metric, cohort_id in sorted(groups):
        label = METRICS[metric]["label"]
        first = groups[(problem, metric, cohort_id)][0]
        cohort = first.get("evaluation_cohort")
        round_id = cohort.get("round") if isinstance(cohort, dict) else "missing"
        md.append(f"## {problem} — {label} — cohort `{cohort_id}`")
        md.append("")
        md.append(f"Round: `{round_id}`")
        md.append("")
        # Keep the shared hidden schedule out of the publishable table. Raw verdicts are
        # operator-private until the cohort closes (rules/evaluation.md).
        md.append("| rank | submission | coverage | correctness work | "
                  "curve work | total work | α (report only) | β (report only) | status |")
        md.append("|---|---|---|---|---|---|---|---|---|")
        scored_rank = 0
        for row in _rows_for(problem, groups[(problem, metric, cohort_id)], metric):
            if row["scoreable"]:
                scored_rank += 1
                rank = str(scored_rank)
                status = "scored"
            else:
                rank = "—"
                status = row["reason"] or "unscored"
            alpha = f"{row['alpha']:.3f}" if row["alpha"] is not None else "—"
            beta = f"{row['beta']:.2f}" if row["beta"] is not None else "—"
            coverage = f"{row['completed_slots']}/{row['planned_slots']}"
            md.append(
                f"| {rank} | {row['sub']} | {coverage} | "
                f"{_format_work(row['correctness_work'], metric)} | "
                f"{_format_work(row['curve_work'], metric)} | "
                f"{_format_work(row['total_work'], metric)} | {alpha} | {beta} | {status} |"
            )
        md.append("")

    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, "scoring.md")
    with open(out, "w") as f:
        f.write("\n".join(md))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
