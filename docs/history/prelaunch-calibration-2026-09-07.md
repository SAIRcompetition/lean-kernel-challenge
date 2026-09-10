# Historical pre-launch calibration notes

Archived during the September 9, 2026 rules review from the checklist at commit
`a66ecf639a48208120eff5fc4c0f30c902173af5` (September 7, 2026).

These excerpts preserve earlier development measurements and proposed work for retired
policies. They are not current rules, validated production results, or active launch blockers.
The original measurement dates and tested revisions were not recorded for every excerpt.
The [current checklist](../pre-launch-checklist.md) governs outstanding acceptance work;
[current problem tables](../../rules/problem-scoring.md) govern scoring.

## Earlier policy transition note

The following is the original transition note, including its historical memory assumptions:

> **Superseded (2026-09-04):** the five-group policy that the items below reference was
> replaced by a uniform three-group policy arranged by order of magnitude of peak memory
> (about 0.03 / 0.3 / 3 GiB on the baseline solutions, every case under an 8 GiB cap). Group
> ids, ranges, and limits quoted below describe the retired layout; `rules/problem-scoring.md`
> carries the current contract.

## Earlier PMU calibration concerns

Also measure a preparation-only floor for every group using a trivial implementation, because
several sealed watchdogs look inverted against dev measurements: `permanent` R1–R5 seal 2–3 s
whole-process watchdogs while timer startup + export parsing are the same order; `sha256` H5's 512
chain steps measured ≈133 s on dev against a 120 s watchdog; `saw` S4/S5 kernel reduction grew
memory at ~250–300 MB/s on dev, so the 4 GiB envelope binds near ~15 s and their real failure mode
may be OOM rather than the published timeout; `mertens` M5 (10^5–3·10^5) and `primecount` Q5
(3–10·10^6) sit far beyond any measured kernel computation — validate that at least one known
implementation can score there, or expect those 38–45 point blocks to go permanently unawarded.

## 5. ca-rule110 orbit structure — decide before sealing

Measured on the shipped 256-cell seeded spec (Python port cross-checked against the frozen
vectors): roughly three quarters of seeds enter a periodic orbit well below the top groups' step
counts — 44/60 sampled seeds repeat a state within the C5 workload of 131,072 steps, 43 of them
within 8,192 steps, with median first repeat ≈2,100 steps and observed cycle lengths 7–1,536. A
submission can therefore compute a few thousand steps, prove the repeat by kernel computation
(the shipped bit-packed example already provides a proved-equal step), and reduce the step count
modulo the cycle — winning C4/C5 (26 + 36 points) at a few percent of the intended work on
cycling seeds, while the remaining ~27 % of seeds admit no shortcut. With only 2 seeds per group,
top-milestone outcomes then hinge on seed luck rather than kernel speed.

**To close, pick one and land it before the first sealed cohort:** (a) publish cycle-jumping as
intended kernel-fu and re-price C4/C5 accordingly; (b) restore the intended scaling by widening
the row (512–1,024 cells pushes typical transients far beyond 131,072) or capping the ladder near
the typical transient (~8k steps); or (c) filter seeds operator-side at plan time — reject seeds
whose orbit repeats before the largest configured step count (deterministic given the seed, cheap
in Python, and requires no Lean-side change).

## 7. Operational notes — non-blocking

- Grouped v2 deliberately has no aggregate performance deadline, so the worst-case official job
  is bounded only by the sum of per-case ceilings: ≈21–27 hours for `permanent` (25 cases) or
  `polydisc` (10 cases × up to 900 s watchdog ×3 reps plus preparation ceilings). Give the batch
  orchestrator an outer wall cap computed from the sealed plan (sum of ceilings + margin) that
  maps to `retry`.
- `permanent` R1 (dimension 4) admits only permanents {6, 8, 9} under the three-ones-per-row
  construction; acceptable as a warm-up group, but document it, and never configure dimension ≤ 3
  (dimension 3 degenerates to the all-ones matrix for every seed).
