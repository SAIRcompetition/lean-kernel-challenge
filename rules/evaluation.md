# Lean Kernel Challenge — Evaluation

How submissions are judged and scored. For the task, rules, and problems see `overview.md`.

## Judging pipeline

A submission provides `impl : Nat → Output` and `impl_correct : ∀ n, impl n = spec n`.
Judging has two independent parts:

```
Submission.lean
  → validate (slugs, symlinks, size caps)
  → correctness gate : build the locked Solution, which references impl_correct — this checks,
                       once, that impl is a total function equal to the trusted spec on ALL n
                       (axioms restricted to R4; no Mathlib; no sorry/native_decide)
  → performance      : for each judge-chosen input n, export `theorem : impl n = v := by
                       decide +kernel` and time the official kernel replaying THAT — checking it
                       forces the kernel to fully reduce `impl n`. v is obtained by a kernel-side
                       reduction of `impl n` (Meta `whnf`), never compiled `#eval`, so a submission
                       fast in the kernel is always evaluable even when its codegen is slow; a
                       wrong v merely fails the build and is caught, never mis-scored
  → scaling data + verdict
```

The correctness proof is verified once and covers every input, so the performance phase can use
any n — including inputs never shown to contestants, and several sizes to reveal scaling. The
judge (`judge/judge.py`) runs this full pipeline; timing the reduction of `impl n` — not the ∀n
proof — is what makes a better *algorithm*, rather than a shorter proof, win.

## Verdicts

- **accepted** — correctness gate passed; carries per-input timings.
- **rejected** — a rule violation or a failed proof (the reason says which).
- **error** — infrastructure failure (exit code 2); never a scored outcome.

## Scoring

Because a submission is a *function*, we score its whole **cost curve**, not a single point. The
base measurement is the **kernel instruction count** `I(n)` to reduce `impl n` (Linux
`perf -e instructions`, median of N reps; the fixed host + pinned toolchain make it reproducible —
instruction counts avoid the wall-clock noise of shared machines, though they are not literally
hardware-independent). Wall-clock is used only for local development.

**Sampling.** The judge times `impl n` at a monotone-increasing set of inputs `n₁ < … < n_K`
and records `(nᵢ, I(nᵢ))` — the scaling curve. The inputs are a **configured policy, never
hardcoded**: each problem's `config.json` declares `perf {min, max}` (with global
`perf_defaults {count, spacing, jitter}` in `pipeline/config.json`), and the judge samples
`count` **geometrically-spaced** points in `[min, max]` (even log-space coverage → a stable
slope), clamped to distinct integers. For the official run, `PERF_SEED` is set and each point is
**jittered by ±jitter** from a seed-derived hash, so the *exact* n is hidden even though the scale
(the public policy) is known. Without a seed the points are deterministic (local dev).

**Why a hardcoded answer table cannot win.** The jitter is only a secondary layer; the real
protection is **R3 + reach-first ranking**. To hardcode `impl n = v` at some input, the `∀ n` proof
(R3) must still establish `v = spec n` — which forces the kernel to reduce the *naive spec* at that
`n`. Where the naive spec is infeasible to reduce (exactly the large end of `[min, max]`, chosen so
a naive baseline truncates before `max`), that proof cannot be built, so a table cannot cover those
inputs at all. It can only cover small inputs where the naive spec is cheap — and there a real
algorithm is just as cheap, while it also *reaches* the large inputs the table cannot. Since ranking
is reach-first, the general algorithm wins. Hardcoding is therefore self-defeating: proving an
answer costs the very computation the competition is about.

**① Primary signal — empirical scaling exponent.** Fit `log I` against `log n` (least squares
over the completed points) to get a slope **α**. This is the empirical complexity exponent and is
the headline signal: it is scale-free and answers the competition's actual question — *is this a
genuinely better general algorithm?* Lower α wins (e.g. a log-time algorithm gives α ≈ 0 and a
flat curve; linear gives α ≈ 1). At least 3–4 well-separated inputs are needed for a stable fit.

**② Secondary signal — efficiency vs the reference algorithm.** For problems whose naive-spec
work `R(n)` has a clean closed form, we also report the normalized efficiency
`e(n) = I(n) / R(n)` — dimensionless "kernel instructions per unit of reference work". Because the
kernel cost reflects *encoding* as well as *algorithm* (term sharing, GMP `Nat` ops, representation),
`e` rewards a kernel-friendly encoding on top of a better algorithm, and is comparable across
problems. It is reported at the largest completed input (and as a trend). Reference work per problem:

| problem | reference work `R(n)` (naive spec) | clean closed form? |
|---|---|---|
| `fib` | Θ(n) course-of-values steps (bignum-weighted) | yes |
| `permanent` | Θ(n!·n) | yes |
| `saw` | Θ(4ⁿ) walk-tree nodes | yes |
| `ca-rule110` | Θ(n·w²), w = 32 | yes |
| `primecount` | Θ(Σ_{p≤n} p) trial-division ops | approx |
| `mertens` | polynomial (μ by trial division, ~Σ_{k≤n} k²) | approx |
| `partition` | Θ(p(n)·n) | depends on p(n) |

For the "approx / depends" problems the exact count is itself answer-level to compute, so scoring
there leans on α and relative placement rather than `e`.

**③ Plot.** Every accepted submission gets a log–log curve of `I` vs `n`, overlaid across
submissions per problem, so the scaling separation is visible at a glance.

**Ranking within a problem.** Primarily by scaling reach (largest completed input, further is
better — the inputs are monotone in difficulty, so this is the completed prefix), then by α, then
by `e` (or raw `I`) at the largest common input. A correct submission too slow to complete even the
smallest input is *accepted but unscored*.

**Cross-problem standing.** Aggregate each contestant's **relative placement** per problem
("red queen"), best-N problems — this avoids tying the overall score to any one reference-algorithm
choice. The exact aggregation weights are finalized in the scoring appendix (TBD before launch).

## Evaluation environment

- Official evaluation runs on a fixed Linux host (bare-metal, PMU for `perf`). Each submission is
  judged in its own container, which is the sandbox and resource boundary: no network, bounded
  memory/CPU/PID, one job per container, non-root.
- Pinned toolchain, frozen for the stage: **Lean v4.32.0-rc1**, comparator `71b52ec`,
  lean4export `3de59f1`, Lean4Checker `b73981`.
- Do not attempt to escape the sandbox or exploit the harness; such submissions are disqualified.

**Status of the production path:** the perf metric and container isolation are implemented but not
yet run on PMU hardware (TBD before launch). Locally the sandbox is a pass-through shim and timing
is wall-clock — for development only.

## Local development

`scripts/perf_eval.py` reproduces the paradigm locally: it builds Solution (correctness), then times
the kernel reducing `impl n` at a range of inputs and writes a scaling JSON. See the script header.
