# Lean Kernel Challenge — Stage 1

*Stage 1 of a multi-stage competition on improving the performance of verified computation in the
Lean 4 kernel.*

## Co-organizers

Stage 1 of the Lean Kernel Challenge is co-organized by (in alphabetical order by surname):

- Joachim Breitner
- Leonardo de Moura
- Kim Morrison
- Terence Tao

The co-organizing institutions are [Lean FRO](https://lean-fro.org/) and the
[SAIR Foundation](https://sair.foundation/).

## Background

The Lean Kernel Challenge is a competition series that brings the community together to
improve the performance of verified computation in the Lean kernel.

Stage 1 is the first, experimental stage of the series. It begins with a set of fundamental
computational problems. Later stages will cover a broader range of mathematical and scientific
fields and more complex problems.

The Lean 4 kernel is the trusted core that type-checks every proof the system accepts.
Type-checking includes definitional-equality checking, which the kernel discharges by
reduction (β/δ/ι reduction and evaluation to weak head normal form). When a proof
depends on a computed result — for instance an equation `f x = y` closed by `rfl` — the
kernel establishes it by reducing `f x` and comparing. Verifying such a proof and
performing the computation are therefore one and the same operation.

The algorithms, representations, and open-source results and benchmark
data produced through the competition will form a collective contribution to
Lean's continued development and benefit Lean users worldwide.

This makes the kernel a well-defined, deterministic model of computation with its own
performance characteristics: reduction is call-by-name, natural-number literals are
backed by GMP with a fixed set of native `Nat` operations, and evaluation strategy,
term representation, and sharing all bear directly on cost. The resulting question is
concrete and largely unstudied:

> **How efficiently can a computation be expressed so that the kernel *verifies* it,
> and which algorithmic and encoding techniques scale within the kernel's reduction
> model?**

The Lean FRO's [Lean Kernel Arena](https://arena.lean-lang.org/) measures kernel
*implementations* — how fast different checkers verify a fixed corpus of proofs. This
competition addresses the orthogonal axis: the official kernel is fixed as the judge,
and submissions compete on how few instructions it takes to check them. Speed alone is
not the objective — a submission is a general algorithm plus a machine-verifiable proof
that it matches the spec on every input, so progress comes from stronger algorithms and
kernel-level encodings rather than from bypassing the computation.

---

## The task

Each problem gives you a **trusted spec** — a deliberately naive but correct definition
`spec : Nat → Output` in core Lean (e.g. the partition function `p(n)`). You submit:

1. a **function** `impl : Nat → Output` — your fast algorithm, and
2. a **proof** `impl_correct : ∀ n, impl n = spec n` — that it agrees with the spec on
   *every* input.

What is timed is **not how fast your compiled code runs**. The official Lean kernel charges one
complete replay of the verified correctness closure and, at each sampling slot, only replay of
the generated target declaration that reduces `impl n`. Process startup, export parsing, and
per-input dependency preloading are outside the counter. Lower is better after slot coverage is
compared.

Correctness for all `n` lets the judge rotate hidden inputs, but it does not make literal
tables logically impossible: a contestant can derive constants through another verified
algorithm. The scoring contract therefore charges the full correctness-closure replay as well as
each successful target-declaration replay. The simplest submission is `impl := spec` with
`impl_correct := fun _ => rfl` — correct but slow because the kernel reduces the naïve spec.

## What you submit

Exactly one file, **`Submission.lean`**, at most 1 MiB. Nothing else — every lemma your
proof needs lives in that file, inside `namespace Submission`. You fill two holes in a
locked workspace:

```lean
namespace Submission

def impl : Nat → Nat := sorry                       -- ① your fast algorithm (a total function)

theorem impl_correct : ∀ n, impl n = fibSpec n :=   -- ② proof it equals the spec on every n
  sorry

end Submission
```

The trusted files (`Spec.lean`, `Challenge.lean`, `Solution.lean`, `config.json`) are
fixed; the judge supplies its own copies. For the timeline, registration,
participation policies, and co-organizers see
**[`rules/prelaunch.md`](rules/prelaunch.md)**. See
**[`rules/overview.md`](rules/overview.md)**
for the binding rules and **[`rules/evaluation.md`](rules/evaluation.md)** for how judging
and scoring work.

## Rules in brief

A submission has two parts — a function `impl` and a proof `impl_correct` — and the rules
follow that shape (full text in [`rules/overview.md`](rules/overview.md)):

- **R1** Submit exactly one file, `Submission.lean`; every other file is locked.
- **R2** `impl` is a total core-Lean function that the kernel can reduce on every input
  (structural recursion is recommended; well-founded recursion is also permitted; no Mathlib).
- **R3** `impl_correct` proves `∀ n, impl n = spec n` — correctness for *all* inputs.
- **R4** The proof may depend only on the standard axioms `propext`, `Quot.sound`,
  `Classical.choice`; `sorry` and `native_decide` are rejected.
- **R5** Kernel replay is scored: one full correctness-closure median plus the successful
  per-input target-declaration medians. Parsing, dependency preload, and process startup are
  excluded; exact output-literal checking remains included.

## Problems (Stage 1)

Every problem is parametric in `n : Nat`; the judge evaluates `impl` along that axis.

| Problem | `impl n` computes | Naive spec cost |
|---|---|---|
| `fib` *(tutorial)* | the n-th Fibonacci number | linear (`brecOn`) |
| `partition` | the partition function p(n) | ~p(n)·n |
| `mertens` | the Mertens function M(n) | quadratic |
| `primecount` | the prime-counting function π(n) | quadratic |
| `permanent` | the permanent of a deterministic n×n 0/1 matrix | n! |
| `saw` | count of self-avoiding walks of length n on ℤ² | exponential |
| `ca-rule110` | a Rule 110 automaton's state after n steps | linear (list-based) |
| `sha256` | the SHA-256 hash chain digest after n steps | linear (~0.3 s/step, word-per-Nat) |
| `polydisc` | the discriminant of a monic degree-min(2+n/2,24) integer polynomial (Int; coefficient width grows past n=44) | factorial in the degree (Laplace) |
| `conv` | the packed integer convolution of two length-n 16-bit sequences (a NN conv layer / polynomial product) | ~n^2.5 (naive double sum, list walks) |

Each spec is intentionally naive: reducing it directly in the kernel blows up as `n`
grows, so competitive submissions require both better algorithms and kernel-level
encodings that reduce efficiently. The worked `fib` example ships two submissions — a
baseline (`impl := spec`) and fast doubling with a full `∀ n` proof.

## How judging works

```
Submission.lean
  → validate (slugs, symlinks, size caps)
  → correctness : parse outside the counter, then time the full verified-closure replay once
  → performance : for each n, parse/preload outside, then time only the target-declaration replay
  → correctness timing + complete slot record + verdict
```

This is measurement contract `kernel-replay-v2`, with boundaries
`full-closure-replay-v1` and `target-declaration-replay-v1`. Scoped counters remove fixed
harness cost without subtracting noisy process totals. Target replay still reduces `impl n` and
compares the exact result, so checking a large `Nat`/`Int` literal remains input-dependent scored
work. The verdict also pins the direct target-proof encoding
`direct-rfl-v1-experimental`, preventing extracted-proof wrapper timings from mixing in.

For official evaluation, `PERF_SEED` is a secret rotation token. The judge hashes it with
the problem id and slot index, so every submission in one public evaluation cohort receives
the same hidden schedule. Operators rotate the token and cohort id for a new round or
deliberate rescore; an unset seed is deterministic local development only. The production
wrapper injects the seed once over stdin, never into the submission's elaboration environment.
Raw verdicts and exact inputs remain private throughout the evaluation phase. After that phase,
all results and benchmark data are released publicly under an open-source license.

## Scoring

Within each problem, submissions are ranked by:

1. more completed sampling slots;
2. then higher `completed / planned` coverage if schedule sizes differ;
3. then success at harder (higher-index) slots;
4. then, for an identical success profile, lower total measured kernel work: the full
   correctness-closure replay median plus the sum of successful target-declaration medians.

The official metric is **kernel instructions** on the Linux evaluation host
(`perf -e instructions`, median of N reps). Wall time is a separate local-development
leaderboard and is never compared with instruction counts. Fitted α and β values and the
log-log curves are report-only diagnostics; they never affect rank, so padding a cheap end
of the curve can only add work. Legacy verdicts without a same-metric `correctness_timing`
record are accepted evidence but unscored by the current contract. Remote scoped timing uses
**KTP/2**. Verdicts commit to the protocol, `kernel-replay-v2`, both boundary versions, and the
target-proof encoding; KTP/1 whole-process results never mix with them. Any change to those
measurement fields creates a new cohort and requires a full rescore. Cohorts also commit to the
exact schedule, toolchain, timing policy, and executor. Run `python3 scripts/score.py` to generate
the canonical tables.

Each problem has its own leaderboard. Your overall standing aggregates your best problems
with a relative-placement component. The exact formula will be published in the scoring
appendix before the official launch.

## Quick start

```bash
scripts/setup.sh                                  # build the pinned tools (comparator, lean4export, timer-kernel)
python3 scripts/run_harness.py                    # green gate: judge every example, check verdicts
python3 judge/judge.py run --problem fib --submission examples/submissions/fib/doubling
python3 scripts/score.py                          # canonical metric-separated scoring tables
```

The local judge reproduces the evaluation pipeline, so you can check a submission before
sending it. (Note: the local sandbox is a pass-through shim — never run untrusted
submissions on your own machine; real sandboxing is enforced by the wrapper-launched
Docker container.)

### Isolated evaluation of untrusted submissions

Build the evaluation image once, then run every untrusted submission through the
host-side wrapper:

```bash
docker build -t lean-kernel-judge .
scripts/run_isolated.sh \
  --problem fib \
  --submission "$PWD/examples/submissions/fib/doubling" \
  --results "$PWD/results" \
  --perf-seed 'official-secret-seed' \
  --cohort stage1-round1 \
  --perfmon
```

`scripts/run_isolated.sh` is the supported production entry point. It always runs one
submission per container with networking disabled, bounded memory/CPU/process counts,
`no-new-privileges`, and the non-root `judge` user. The submission is mounted read-only
and verdicts are written through a persistent results mount. The seed is consumed from a
one-shot stdin pipe before any untrusted Lean process starts; `--cohort` is the public round
identifier used to prevent cross-round scores from being mixed. `--perfmon` is optional on
hosts whose `perf_event_paranoid` setting already permits instruction counting. On a native
Linux Docker host, the results directory must be writable by the image's judge UID 10001;
the wrapper checks this before it starts elaborating the submission.

## Repository layout

```
lean-kernel-challenge/
├─ rules/           overview.md (binding rules) · evaluation.md (judging + I/O contract)
├─ problems/<id>/   10 locked problem workspaces (Spec / Challenge / Solution / config)
├─ examples/submissions/<problem>/<name>/   worked + adversarial example submissions
├─ judge/           judge.py (the judge) · timer-kernel/ (kernel replay + axiom audit)
├─ pipeline/        config.json (budgets, sandbox mode, toolchain pins)
├─ tests/           harness_manifest.json (expected verdicts — the green gate)
├─ scripts/         setup.sh · run_harness.py · run_isolated.sh · perf_eval.py · score.py · shims/
├─ Dockerfile       Linux evaluation image (pinned toolchain, perf, landrun sandbox)
└─ results/         verdict JSONs + scoring.md / leaderboard.md (generated)
```

## Toolchain

Pinned and frozen for the stage: **Lean v4.32.0-rc1**, comparator `71b52ec`,
lean4export `3de59f1`, Lean4Checker `b73981`. `scripts/setup.sh` rebuilds the tools from
these pins; the third-party checkouts are not committed.

## Status

> **The sampling ranges in `problems/*/config.json` are development/smoke values, not competition
> values.** At the current ranges even the naive baseline completes every slot, so `reach` stops
> discriminating and hardcoded answer tables become provable. They must be re-derived on the
> evaluation host before launch — see **[`docs/pre-launch-checklist.md`](docs/pre-launch-checklist.md)**
> for the measurements and the other open pre-launch items.

**Prototype / pre-launch.** All 10 problems are functionalized and compile; the correctness
gate (comparator + axiom audit) and the green-gate harness are in place (10 baselines +
3 proven optimized submissions — `fib/doubling`, `ca-rule110/bitpacked`, `primecount/sqrt` —
accepted; three fib cheat classes — `sorry`, illegal axiom, Mathlib — rejected). The main
judge (`judge/judge.py`) times both the comparator-verified correctness closure and every
planned input slot (local replay or the remote KTP/2 executor) under measurement contract
`kernel-replay-v2`. The performance phase imports
the byte-pinned `.olean` graph produced by comparator instead of re-elaborating contestant
source. `scripts/perf_eval.py` is a local-wall-time, one-repetition wrapper around that same
canonical judge path, so it cannot drift back to whole-process timing or expose an official
seed/cohort. Inputs are config-driven
and shared within a cohort through a rotating official `PERF_SEED`; the seed is never exposed
to elaboration. `scripts/score.py` applies the coverage-then-total-work contract within each
cohort, with α/β as report-only diagnostics. Not yet finalized: a PMU-hardware
run; the cross-problem scoring aggregation (best-N + relative placement); the four remaining
optimized example submissions. Rule text may still change before launch (see
`rules/overview.md`).
