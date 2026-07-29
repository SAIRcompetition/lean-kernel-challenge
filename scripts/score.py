#!/usr/bin/env python3
"""Function-paradigm scoring: turn each submission's scaling curve into an empirical
complexity fit and an efficiency-vs-reference number.

Reads the judge verdict JSONs under results/<problem>/*.json (the files the leaderboard
uses) and writes results/scoring.md — per-problem tables of:

  (1) slope α  — from a least-squares fit of log I vs log n; the empirical complexity
                 exponent and the PRIMARY signal (scale-free, lower is better).
  (2) β        — the fit's intercept = log-constant factor / kernel-encoding quality
                 (secondary tiebreak among equal α).
  (3) e = I/R  — kernel work per unit of naive-spec reference work, at the reach input,
                 for problems whose reference work R(n) has a clean closed form (human-
                 readable efficiency; not the primary ranking key).

Ranking within a problem: scaling reach (largest completed input) → α → β.
Metric: median_instructions when present (Linux perf), else median_s (local dev).
Stdlib only. See rules/evaluation.md for the methodology.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")


def _fact(n):
    r = 1
    for i in range(2, n + 1):
        r *= i
    return r


# Naive-spec reference work R(n), only for problems where it has a clean closed form.
# (primecount / mertens / partition depend on answer-level quantities, so they get no e —
# their scoring leans on α + relative placement, per rules/evaluation.md.)
REFERENCE_WORK = {
    "fib":        lambda n: max(n, 1),           # Θ(n) course-of-values steps
    "permanent":  lambda n: _fact(n) * max(n, 1),
    "saw":        lambda n: 4 ** n,              # brute-force branching upper bound
    "ca-rule110": lambda n: max(n, 1) * 32 * 32,
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
                r = json.load(open(os.path.join(pdir, fn)))
            except (json.JSONDecodeError, OSError):
                continue
            if not (isinstance(r, dict) and isinstance(r.get("problem"), str)
                    and isinstance(r.get("submission"), str)
                    and isinstance(r.get("status"), str) and isinstance(r.get("stages"), dict)):
                continue
            rows.append(r)
    return rows


def _points(verdict):
    """[(n, I)] over completed inputs, I>0, using whichever metric the verdict carries."""
    pts = []
    for row in verdict.get("timing", {}).get("scaling", []):
        if row.get("result") != "ok":
            continue
        n = row.get("n")
        val = row.get("median_instructions", row.get("median_s"))
        if isinstance(n, int) and n > 0 and isinstance(val, (int, float)) and val > 0:
            pts.append((n, float(val)))
    return pts


def _fit(pts):
    """Least-squares (α, β) for log I ≈ α·log n + β; (None, None) if < 2 usable points."""
    if len(pts) < 2:
        return None, None
    xs = [math.log(n) for n, _ in pts]
    ys = [math.log(v) for _, v in pts]
    m = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    d = m * sxx - sx * sx
    if d == 0:
        return None, None
    alpha = (m * sxy - sx * sy) / d
    beta = (sy - alpha * sx) / m
    return alpha, beta


def _rows_for(problem, verdicts):
    Rfn = REFERENCE_WORK.get(problem)
    out = []
    for v in verdicts:
        pts = _points(v)
        if not pts:
            out.append({"sub": v["submission"], "reach": None,
                        "alpha": None, "beta": None, "e": None})
            continue
        reach = max(n for n, _ in pts)
        alpha, beta = _fit(pts)
        top_I = dict(pts)[reach]
        e = (top_I / Rfn(reach)) if Rfn else None
        out.append({"sub": v["submission"], "reach": reach,
                    "alpha": alpha, "beta": beta, "e": e})
    # rank: further reach first, then lower α, then lower β
    out.sort(key=lambda r: (-(r["reach"] if r["reach"] is not None else -1),
                            r["alpha"] if r["alpha"] is not None else 9e9,
                            r["beta"] if r["beta"] is not None else 9e9))
    return out


def main():
    verdicts = [r for r in _load_verdicts() if r["status"] == "accepted"]
    by_problem = {}
    for r in verdicts:
        by_problem.setdefault(r["problem"], []).append(r)

    md = ["# Lean Kernel Challenge — scoring (function paradigm)", "",
          "Primary: slope **α** (empirical complexity exponent, lower is better). "
          "Tiebreak: **β** (log-constant / encoding). **e = I/R** is efficiency vs the naive "
          "spec's reference work where it has a closed form. See `rules/evaluation.md`.", ""]
    for problem in sorted(by_problem):
        md.append(f"## {problem}")
        md.append("")
        md.append("| rank | submission | reach (n) | α (slope) | β (intercept) | e = I/R @ reach |")
        md.append("|---|---|---|---|---|---|")
        for i, r in enumerate(_rows_for(problem, by_problem[problem]), 1):
            a = f"{r['alpha']:.3f}" if r["alpha"] is not None else "—"
            b = f"{r['beta']:.2f}" if r["beta"] is not None else "—"
            e = f"{r['e']:.3e}" if r["e"] is not None else "—"
            reach = r["reach"] if r["reach"] is not None else "unscored"
            md.append(f"| {i} | {r['sub']} | {reach} | {a} | {b} | {e} |")
        md.append("")

    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, "scoring.md")
    open(out, "w").write("\n".join(md))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
