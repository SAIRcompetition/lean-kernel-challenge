# Lean Kernel Challenge — Stage 1: Evaluation

How submissions are judged and scored. For the task and rules, see
[`overview.md`](overview.md).

## Judging pipeline

A submission defines `impl : Nat → Output` and proves
`impl_correct : ∀ n, impl n = spec n`. The judge:

1. validates the submission's structure and size;
2. builds the locked solution and checks the universal correctness proof and permitted axioms;
3. measures repeated complete replays of the verified correctness closure and records their
   median cost;
4. for each hidden input `n`, generates and checks a direct theorem `impl n = v`, then measures
   replay of that target declaration; and
5. records the measurements and verdict.

The correctness replay includes the verified definitions and proof. For each input, non-target
dependencies are replayed before measurement, and only the generated target declaration is
measured. Checking that declaration forces the kernel to reduce `impl n` and compare it with the
exact output literal. Process startup, export parsing, and dependency preloading are not scored.
The definition of `impl` is charged once in the correctness replay rather than once per input.

Correctness timing uses the immutable export produced by the correctness gate. For each performance
input, the judge creates a separate immutable export from the exact verified build; contestant
source is not re-elaborated. The judge obtains the candidate literal `v` through Lean's
elaborator-side reduction. This step is neither trusted nor scored: if the value is wrong or
unsupported, the generated theorem cannot pass kernel checking and the run is not scored.

These boundaries are versioned as measurement contract `kernel-replay-v2`, with
`full-closure-replay-v1` for correctness and `target-declaration-replay-v1` for each input.
Verdicts also record the target-proof encoding. A change to any of these fields requires a new
evaluation cohort.

## Verdicts

- **accepted** — the correctness gate passed. The submission may be scored or accepted but
  unscored if its timed correctness replay or all performance slots fail to finish.
- **rejected** — submission validation, a competition rule, or the correctness gate failed.
- **retry** — the timing service is temporarily unavailable. The run is requeued and not scored.
- **error** — the judge or evaluation infrastructure failed. The run is not scored and requires
  organizer review.

## Scoring

Official scores use **kernel instruction counts** measured on a pinned Linux PMU executor. Each
recorded cost is the median over the configured repetitions. Local wall-clock measurements are for
development only and are never compared with official scores.

**Sampling schedule.** Each problem's `config.json` defines its input range and may override the
slot count, spacing, and jitter defaults in `pipeline/config.json`. The judge produces an ordered
schedule and records an outcome for every planned slot. A timeout does not by itself stop the
schedule: later slots are attempted while the total performance-phase budget remains. Once that
budget is exhausted, all remaining slots are marked `budget-exhausted`. A fatal evaluation error
stops the run, and remaining slots are marked `not-run`. Coverage is `completed / planned`; it is
not inferred from the largest completed input.

Official evaluation requires a secret `PERF_SEED`, rotated between evaluation cohorts. Every
submission in the same cohort receives the same hidden schedule. The production wrapper reads the
seed once from standard input and does not expose it to contestant-controlled Lean processes. An
unseeded schedule is permitted only for deterministic local development and is not an official
score.

Submissions are evaluated as a batch after the submission cutoff. Raw verdicts and exact inputs
remain private throughout the evaluation phase. After that phase, all results and benchmark data
are released publicly under an open-source license. A deliberate re-evaluation uses a new seed and
cohort and rescores the comparison set.

**Hardcoding and proof cost.** A table or special case is legal only if it is covered by the
universal correctness proof. Exact evaluation inputs remain hidden and rotate between cohorts.
Scoring charges the complete verified correctness closure once and every successful target replay,
so constants, tables, and their proofs inside the verified artifact are not free.

**Canonical ranking within one problem, metric, measurement contract, and evaluation cohort.**

1. More completed schedule slots wins.
2. If completed-slot counts tie but planned schedule sizes differ, higher coverage
   `completed / planned` wins.
3. If coverage ties, compare the complete success bitmap from the highest-index slot downward.
4. Only identical success profiles use lower total measured kernel work:

   `W = median(full correctness-closure replay) + Σ median(successful target-declaration replay)`.

The success-profile comparison ensures that `W` is compared only over the same sampled inputs.
If all ranking values tie, submissions are listed in deterministic submission-name order.

**Scoreability and versioning.** Only accepted verdicts with a successful correctness replay, a
complete slot record, at least one successful performance slot, and one consistent metric are
scoreable. Remote timing uses **KTP/2**; in-process timing uses **local-v2**. Rankings never mix
metrics, evaluation cohorts, executors, timing protocols, or measurement-contract versions. Any
change to these fields requires a new cohort and complete rescore.

The cohort id commits to the exact input schedule, repetition count, configured timing timeout,
toolchain, metric, measurement contract, target-proof encoding, and timing-executor identity. A
correct submission that does not finish its timed correctness replay or any performance slot is
accepted but unscored.

**Report-only diagnostics.** The scorer reports a log-log fit
`log cost ≈ α log n + β` over completed slots. These values help describe scaling behavior but do
not affect ranking.

**Cross-problem standing.** Each problem has a separate leaderboard. The overall standing will
combine relative placement across each contestant's best-performing problems. The complete
formula, including the number of problems and aggregation weights, will be published before the
official launch.

## Evaluation environment

- Official instruction counts are measured on a pinned Linux PMU executor.
- Submission validation and elaboration run in an isolated container with no network, bounded
  memory, CPU, and process count, and a non-root user.
- Kernel replay runs either in the pinned local PMU environment or, when remote KTP/2 timing is
  configured, on a remote executor. In the remote case, only immutable exported artifacts are sent
  to that executor.
- The stage uses Lean **v4.33.1**, comparator `3927ad3`, lean4export `15f6055`, and
  kernel replay via Lean's built-in `Lean.Replay`.
- Attempts to escape the evaluation environment or exploit the judge result in disqualification.

The production measurement and container paths are implemented but still require final validation
on the official PMU hardware before launch.

## Local development

`scripts/perf_eval.py` runs one wall-time repetition through the canonical judge. It uses the same
export, audit, and measurement boundaries as the official path, but it is for development only and
does not use official seeds, cohorts, remote timing, or production isolation.
