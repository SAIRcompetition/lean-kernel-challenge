# Pre-launch checklist

Things that are **deliberately not final** in the current tree, with the evidence needed to close
them. Everything here is a launch blocker unless marked otherwise.

## 1. Sampling ranges are development/smoke values — MUST be re-derived before launch

`problems/*/config.json` `perf {min,max}` and `pipeline/config.json` `perf_defaults.count = 4` are
currently tuned for a fast local gate, **not** for a real competition.

Measured on this tree (naive `baseline` submission, value oracle at each problem's `max`):

| problem | current range | naive baseline at `max` |
|---|---|---|
| `fib` | 1000 – 100000 | completes |
| `partition` | 5 – 20 | 5.6 s — completes |
| `permanent` | 1 – 5 | 1.7 s — completes |
| `saw` | 1 – 5 | 1.9 s — completes |
| `mertens` | 50 – 300 | 8.8 s — completes |
| `primecount` | 100 – 600 | 8.2 s — completes |
| `ca-rule110` | 50 – 300 | 10.1 s — completes |
| `sha256` | 1 – 8 | ~2.6 s — completes |

Two consequences, both of which void the competition if launched as-is:

- **The primary ranking key stops discriminating.** Ranking is *completed slots → coverage →
  success bitmap → W*. If even the naive baseline completes every slot, the first three levels tie
  for everybody and the result collapses to "smallest constant factor at tiny inputs" instead of
  "whose algorithm scales".
- **Hardcoded answer tables become viable.** The protection against tables is that at large `n` the
  naive spec cannot be reduced in the kernel, so the `∀ n` proof (R3) for a hardcoded constant
  cannot be built. That protection only holds while `max` sits *past* the naive spec's feasible
  range. At the current ranges every slot is reducible within ~10 s, so a table covering all four
  slots is provable. `permanent` is the extreme case: over `1..5` the permanent is `1, 1, 1, 2, 2`.

**To close:** on the Linux evaluation host, for each problem raise `max` until the naive baseline
truncates before it (that is the discriminating point), keep `min` in a range where a good
algorithm is already meaningfully cheaper, and re-check that `permanent` avoids its trivial head
(`p(6)=17, p(7)=133, p(8)=380, p(9)=2010, p(10)=8908`). A previously calibrated example: `fib`
`max = 1000000`, where the baseline oracle exceeds 90 s while fast doubling finishes in 19.1 s.

## 2. Full 8-problem sweep on the evaluation host — not yet run

All local numbers are wall-clock on a laptop. The official metric is `perf -e instructions` on a
bare-metal Linux host with PMU access. Nothing in this repo has been run under
`TIMING_METRIC=perf_instructions` on real hardware.

**To close:** run the full sweep through `scripts/run_isolated.sh` on the evaluation host, confirm
instruction counts are recorded, and re-derive the ranges from item 1 with those numbers.

## 3. Real-container isolation CI job — written but never executed

`.github/workflows/isolation-wrapper.yml` has a `workflow_dispatch` job that builds the image and
asserts network unreachability (v4+v6), `--pids-limit` containment of a fork bomb, and refusal of an
official run without `ISOLATION_ATTESTATION` (plus positive controls for both). It has **never been
run** — there is no Docker in the development environment.

**To close:** trigger the workflow manually (or run the same commands on a Docker host) and confirm
every assertion passes, including the two controls.

## 4. Cross-problem scoring aggregation — TBD (not a blocker for a single-problem pilot)

Per-problem ranking is implemented and documented. The overall standing ("red queen" relative
placement over best-N problems) has no agreed weights yet; `rules/evaluation.md` says so.

## 5. Remaining optimized example submissions — nice to have

`fib/doubling`, `ca-rule110/bitpacked` and `primecount/sqrt` ship with full `∀ n` proofs. The other
four problems have only baselines, so their ladders are unproven by example.
