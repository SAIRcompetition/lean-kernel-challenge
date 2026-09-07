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

- **accepted** — the correctness gate passed. The submission is scored when its timed correctness
  replay and sealed cohort record are valid; passing no performance case yields zero points.
- **rejected** — submission validation, a competition rule, or the correctness gate failed.
- **retry** — the timing service is temporarily unavailable. The run is requeued and not scored.
- **error** — the judge or evaluation infrastructure failed. The run is not scored and requires
  organizer review.

## Scoring

Official scores use **kernel instruction counts** measured on a pinned Linux PMU executor. Each
recorded cost is the median of three repetitions. All three must complete within the group's
per-repetition watchdog for that case to pass. Local wall-clock measurements are for development
only and are never compared with official scores.

The universal correctness comparator has a 3,600-second watchdog, and its axiom audit has a
300-second watchdog. Scoreability also requires all three complete correctness-closure replays to
finish, each under a 1,800-second per-repetition watchdog. A comparator timeout fails the
correctness gate; a correctness axiom-audit timeout is an infrastructure error requiring organizer
review; and a correctness-replay timeout leaves an otherwise accepted submission unscored. Under
the attested 4 GiB job envelope, a memory kill in the comparator or correctness axiom audit is a
terminal rejection, while a timed correctness-replay memory kill is accepted but unscored.

Stage 1 has **nine independent 100-point problem leaderboards**. There is no cross-problem total or
relative-placement aggregation. `conv` is retained as an experimental development task and is not
part of these leaderboards.

**Difficulty groups and cases.** Each scored problem's `config.json` defines three ordered groups.
For every group it publishes the difficulty axis, input generator or range, case count, milestone
points, target-replay limit, and any prerequisite groups. A case passes when its target replay
completes in every configured repetition within the published per-repetition watchdog; if the
group declares a kernel-instruction limit, the median measurement must also stay within it.
Reaching a milestone awards that group's corresponding points. The exact tables are the public
contract in
[`problem-scoring.md`](problem-scoring.md).

The published watchdog applies separately to each target-timing process. It includes that
process's untimed parsing and preload overhead, while the ranking metric itself covers only the
target-declaration kernel replay. Earlier value generation, generated-theorem build/export, and
axiom audit use separate per-case ceilings: 1,800 seconds for value generation, 1,800 seconds
shared by theorem build and export, and 300 seconds for axiom audit. A timeout in any required
step fails that case, but cannot consume another case's limit. Likewise, a deterministic value
generation failure at one input — the submission's `impl` does not reduce to an integer literal
there, or the evaluation process fails on it — fails that case only; later cases are still
attempted, and a submission passing no case scores zero points rather than becoming unscored.

The official evaluator job has one common 4 GiB cgroup-v2 envelope. A child SIGKILL is classified
as memory exhaustion only when the attested `memory.events` OOM counter also increases. If that
cgroup kills a child while generating a case value, building/exporting its theorem, auditing it, or replaying its
target, the case fails with `resource-limit` and later cases are still attempted. Non-official
KTP/3 reports the same outcome under its per-request 4 GiB limit. If resource enforcement
terminates the evaluator before it can write a complete case record, the run is investigated and
rerun against the same sealed plan; an incomplete run never receives a score.

Before evaluation, the judge resolves every hidden group/case coordinate into a complete
performance plan. The cohort seals that plan, its hash, and the grouped evaluation policy. The
verdict records an explicit outcome for every planned case. A timeout does not by itself stop the
plan: every later case is still attempted under its own limits. Grouped evaluation has no shared
aggregate deadline, so one case's work does not reduce another case's configured time allowance. A platform interruption
or fatal evaluator error makes the run incomplete and requires retry; it cannot turn unattempted
cases into zero-point results. The legacy `conv` development schedule retains its separate
aggregate development budget and is not eligible for a Stage 1 leaderboard.

Official evaluation requires a secret `PERF_SEED`, rotated between evaluation cohorts. Hidden
values are derived from the problem, group, and case coordinates, so every submission in the same
cohort receives the same plan. The cohort records a seed commitment. The production wrapper reads
the seed once from standard input and does not expose it to contestant-controlled Lean processes.
An unseeded plan is permitted only for deterministic local development and is not an official
score.

Official results come from one evaluation cohort run as a batch after the submission cutoff.
Raw verdicts and exact inputs remain private throughout the evaluation phase. After that cohort
closes, its resolution seed, exact input plan, results, and benchmark data are released publicly
under an open-source license. A deliberate re-evaluation uses a new hidden seed and cohort and
rescores the comparison set.

**Provisional standings during the submission window.** Each day the platform evaluates each
entrant's newest formal submission per problem under a separate hidden reference cohort and
builds a per-problem temporary board from those results: the board updates once per day, not in
real time, and an entrant's entry reflects their newest submission's terminal verdict — a rejected
newer submission replaces an accepted older one. The organizers may publish the temporary board
during the submission window; it is provisional, it never shows raw verdicts or hidden inputs, an
incomplete daily edition is never published, and it does not determine the official result. After
the cutoff the last complete temporary edition may stay visible with a final-evaluation notice
until the published final leaderboard replaces it.

**Hardcoding and proof cost.** A table or special case is legal only if it is covered by the
universal correctness proof. Exact inputs remain hidden until their cohort closes, and new cohorts
use new hidden inputs.
Both the complete verified correctness closure and every successful target replay are measured.
Each problem's published tie-break policy states whether proof work is included with performance
work or used only as the final tie-break, so constants, tables, and their proofs inside the
verified artifact are not free.

**Canonical ranking within one problem, metric, measurement contract, and evaluation cohort.**

1. Higher total points wins.
2. If totals tie, compare group points from the hardest group to the easiest.
3. If group points tie, apply the problem's declared case profile. Ordered range samplers compare
   the complete pass/fail bitmap from larger inputs to smaller inputs. Interchangeable seeded
   samplers compare only the number passed in each group, never the hidden seed index.
4. Ordered profiles then use lower measured kernel work. For interchangeable samplers, equal
   partial profiles remain tied and measured work applies only after the complete plan passes.
5. If declared, lower correctness-closure work is the final tie-break.

The common work policies are:

- **target work, then proof:** compare the sum of successful target-declaration medians, followed
  by the correctness-closure median; and
- **combined work:** compare the correctness-closure median plus the sum of successful
  target-declaration medians.

This prevents arbitrary seed numbering or a cheaper subset of hidden instances from deciding a
partial tie. The per-problem policy is listed in [`problem-scoring.md`](problem-scoring.md). If all
competitive values tie, submission name determines display order but does not break the competitive
tie.

**Scoreability and versioning.** Only accepted verdicts with a successful correctness replay, a
complete case record, a valid sealed policy, and one consistent metric are scoreable. A valid
submission that passes no case receives zero points. Stage 1 official cohorts require in-container
**local-v2** PMU timing. Resource-bound **KTP/3** is available only for non-official validation.
Rankings never mix
metrics, evaluation cohorts, executors, timing protocols, or measurement-contract versions. Any
change to these fields requires a new cohort and complete rescore.

The cohort id commits to the exact performance plan, group policy, repetition count, evaluation
budgets, resource policy, toolchain, metric, measurement contract, target-proof encoding, and
timing-executor identity. A correct submission whose timed correctness replay does not finish is
accepted but unscored.

**Report-only diagnostics.** The scorer may report a log-log fit
`log cost ≈ α log n + β` over successful cases. These values help describe scaling behavior but
do not affect ranking.

## Evaluation environment

- Official instruction counts are measured on the pinned Linux PMU host inside the evaluation
  container.
- Submission validation and elaboration run as a non-root user in a network-disabled container
  with 4 GiB memory, 2 CPUs, and a 512-process limit.
- Official kernel replay uses that local PMU environment. Non-official KTP/3 validation may send
  only immutable exported artifacts to a remote executor and binds each request and response to
  the same 4 GiB replay limit.
- The stage uses Lean **v4.33.1**, comparator `3927ad3`, lean4export `15f6055`, and
  kernel replay via Lean's built-in `Lean.Replay`.
- Attempts to escape the evaluation environment or exploit the judge result in disqualification.

The production measurement and container paths were validated on the official PMU hardware
before launch.

## Local development

`scripts/perf_eval.py` runs one wall-time repetition through the canonical judge. It uses the same
export, audit, and measurement boundaries as the official path, but it is for development only and
does not use official seeds, cohorts, remote timing, or production isolation.
