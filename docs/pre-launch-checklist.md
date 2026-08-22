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
| `polydisc` | 0 – 5 | 5.7 s — completes |
| `conv` | 4 – 64 | 2.6 s — completes |

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

Suggested launch ranges from the 2026-08-25 per-problem dives (wall-clock on the dev Mac, ±2x —
re-derive the exact constants on the evaluation host): `fib` [10^4, 10^7] (naive truncates
≈3.2×10^6; doubling reaches 10^7 in 44 ms); `partition` [50, 3×10^4–5×10^4] (naive truncates
n≈60); `mertens` [10^3, 10^6–10^7] (naive ~50 s at 10^3, ~n^2→n^3/log n growth); `primecount`
[5×10^3, 10^8–10^9] (naive truncates ≈1.06×10^4; sqrt example ~40x cheaper); `permanent`
[6, 20] (min ≥ 6 escapes the 1,1,1,2,2 head; naive truncates n≈9–10 — see the saw/permanent
memory caveat in item 1b); `saw` conditional on item 1b's OOM fix (naive ~30 s at n=9, memory
grows ~250–300 MB per second of reduction); `sha256` re-derive with the others (naive
truncates n≈7000 at ~0.26 s/step); `conv` [32, ~10^4] — naive truncates n≈600–800, but the
Kronecker apex runs at noise floor at any length, so the max is bounded by oracle/literal size
rather than replay cost (re-derive on the host); `ca-rule110` — NO range works until item 1c is resolved;
`polydisc` — the raise-max rule does NOT apply (naive Laplace dies at degree 5–6, n≈7–9,
far below any competitive range): anchor the range to the optimized rung instead — Bareiss
floors at ~5.5 s per 47×47 instance from n=45 (list-op bound, ±2x), so [8, 300–1000] with the
closure-priced table economics doing the anti-table work; re-derive on the host.

## 1b. Kernel memory growth can OOM-kill perf builds — judge scores it as a fatal fault

Confirmed on `saw` (2026-08-25 dive): kernel reduction memory grows roughly linearly with
reduction work (~250–300 MB/s observed); at `saw` n=9 the perf build already exceeds the
official 4 GiB sandbox cap, and the sandbox SIGKILL surfaces as a deterministic build fault —
an `error` verdict that destroys the submission — instead of a failed slot like a timeout.
`permanent` at n≥10 likely dies the same way (3.6M-element foldl spine). **To close:** teach the
judge to classify sandbox OOM kills of the perf build/replay as an unsuccessful slot (continue
with later slots), and size official ranges so the naive truncation mode is the timeout, not the
memory cap.

## 1c. ca-rule110 instance is trivialized by a 166-state orbit — instance must change

Confirmed empirically (2026-08-25 dive, verified independently in Python and Lean): the fixed
32-cell `initRow` orbit has preperiod 118 and period 48, so `caSpecN n` for n ≥ 118 takes only
48 values and `caSpecN n = caSpecN (118 + (n − 118) % 48)` holds. A submission that proves the
cycle once (the shipped `bitpacked` example already contains the hard part — the full ∀n
bitpacked equivalence proof) answers every large-n slot by table lookup over 48 values. No
`{min,max}` choice rescues the current instance. **To close:** enlarge the instance (wider row
and/or rotating seed-derived `initRow` per cohort, with the generator script committed so the
instance is auditable — the current LCG seed comment has no reproducing script in the repo), and
re-check the orbit structure of any new instance before launch.

**Caveat — the range remedy does not neutralize tables on chain problems (`sha256`,
`ca-rule110`).** The argument above assumes a table's `∀ n` proof must reduce the *naive spec* at
large `n`. On an iterated-map problem a contestant instead proves digest anchors at stride `s`
by chaining their own proved-equal fast step function — the exact artifact the contest wants
optimized — paying one chain traversal in the correctness closure, after which every slot below
the anchor horizon replays in ~`s` steps regardless of `{min, max}`. Under the current ranking
(completed slots → coverage → bitmap → W) that submission weakly dominates the same submission
without the table. Decide before launch: either embrace it (it still ranks step-function
kernel-fu; state that the closure budget is the effective table budget) or reweight the
correctness-closure term for chain problems. Tracked since the `sha256` review (2026-08-21).

## 1d. Jitter clamping makes the top slot predictable half the time — judge sampling fix

The slot sampler jitters geometric positions then clamps into `[min, max]`; upward jitter of the
top position clamps to exactly `max`, so the decisive hardest slot equals `max` with probability
~1/2 while the rules promise a hidden schedule. Targeted single-value tables at `max` become a
coin-flip win. **To close:** jitter the top slot inward only (or resample instead of clamping)
in `judge.perf_inputs`, and rotate cohorts after the change.

## 2. Full 10-problem sweep on the evaluation host — not yet run

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
seven problems have only baselines, so their ladders are unproven by example.
