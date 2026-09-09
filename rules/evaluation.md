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
elaborator-side reduction. This step is neither trusted nor scored. Failure to produce a supported
literal fails only that case. If the generated theorem fails kernel checking, the run is treated
as an evaluation error and is not scored.

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
the attested memory limit for that problem, a memory kill in the comparator or correctness axiom
audit is a terminal rejection, while a timed correctness-replay memory kill is accepted but unscored.

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
generation failure at one input — the elaborator-side value-generation step fails to produce a
supported literal or exits with an error — fails that case only; later cases are still attempted.
Such a failure does not by itself establish that `impl` is not kernel-reducible. A confirmed
violation of R2 is a rejection. Subject to the scoreability requirements below, a submission
passing no case scores zero points rather than becoming unscored.

Each problem has its own memory limit, published before it is used for official evaluation.
Organizers may revise a problem's limit during the competition. The limit is fixed within each
evaluation cohort and recorded in its sealed resource policy; a revision requires a new cohort
and a complete rescore of that problem's comparison set. Scores from different memory policies
are never mixed in one ranking.

The official evaluator job enforces the problem's limit through a cgroup-v2 envelope covering
the correctness gate, correctness replay, and performance cases. A child SIGKILL is classified
as memory exhaustion only when the attested `memory.events` OOM counter also increases. If that
cgroup kills a child while generating a case value, building/exporting its theorem, auditing it, or replaying its
target, the case fails with `resource-limit` and later cases are still attempted. Non-official
KTP/3 binds each replay request to the applicable problem memory limit. If resource enforcement
terminates the evaluator before it can write a complete case record, the run is investigated and
rerun against the same sealed plan; an incomplete run never receives a score.

Before evaluation, the judge resolves every hidden group/case coordinate into a complete
performance plan. The cohort seals that plan, its hash, and the grouped evaluation policy. The
verdict records an explicit outcome for every planned case. A timeout does not by itself stop the
plan: every later case is still attempted under its own limits. Grouped evaluation has no shared
aggregate deadline, so one case's work does not reduce another case's configured time allowance. A platform interruption
or fatal evaluator error makes the run incomplete and requires re-evaluation; fatal evaluator
errors require organizer review before the run is repeated. Unattempted cases cannot be turned
into zero-point results. The legacy `conv` development schedule retains its separate
aggregate development budget and is not eligible for a Stage 1 leaderboard.

Official evaluation requires a secret `PERF_SEED`, rotated between evaluation cohorts. Hidden
values are derived from the problem, group, and case coordinates, so every submission in the same
cohort receives the same plan. The cohort records a seed commitment. The production wrapper reads
the seed once from standard input and does not expose it to contestant-controlled Lean processes.
An unseeded plan is permitted only for deterministic local development and is not an official
score.

Official results come from one evaluation cohort run as a batch after the submission cutoff.
The evaluation window and final results publication date and time are to be announced in the
[overview schedule](overview.md#schedule). No fixed evaluation duration is specified.
Raw verdicts and exact inputs remain private throughout the evaluation phase. After the final
official cohort closes, its resolution seed, exact input plan, results, and benchmark data are
released publicly under an open-source license. A deliberate re-evaluation uses a new hidden
seed and cohort and rescores the comparison set.

**Provisional standings during the submission window.** Each day the platform evaluates each
entrant's latest formal submission per problem using hidden inputs sampled under the published
problem policy, separately from the final official evaluation. Organizers may update these
reference inputs; their input plans and seeds are not subject to the final-results publication
commitment above. The platform builds a per-problem temporary board from those results:
the board updates once per day, not in real time, and an entrant's entry reflects their latest
submission's terminal verdict — a rejected or unscored newer submission replaces an accepted
older one. Selection uses the platform's recorded submission time, regardless of when evaluation
finishes. The same latest-submission rule selects
the official entry at the cutoff, as specified in [`overview.md`](overview.md#submission).
The organizers may publish the temporary board during the submission window. It is provisional,
never shows raw verdicts or hidden inputs, and does not determine the official result.
An incomplete daily edition is never published. After the cutoff the last complete temporary
edition may stay visible with a final-evaluation notice
until the published final leaderboard replaces it.

**Hardcoding and proof cost.** A table or special case is legal only if it is covered by the
universal correctness proof. Exact inputs remain hidden during evaluation. Final official inputs
are released as described above; no publication of provisional reference inputs or seeds is promised.
Both the complete verified correctness closure and every successful target replay are measured.
Every submission must complete the correctness replays within the applicable resource limits.
Each problem's published work policy states whether correctness-closure work also contributes to
ranking: combined-work problems include it, while target-work problems use only the successful
target replays for the work comparison. Neither policy adds a separate proof-cost tie-break.

**Canonical ranking within one problem, metric, measurement contract, and evaluation cohort.**

1. Higher total points wins.
2. If totals tie, compare group points from the hardest group to the easiest.
3. If group points tie, apply the problem's declared case profile. Ordered range samplers compare
   the complete pass/fail bitmap from larger inputs to smaller inputs. Interchangeable seeded
   samplers compare only the number passed in each group, never the hidden seed index.
4. Compare lower instruction cost under the problem's declared target-work or combined-work
   policy below. Ordered profiles use this comparison after the preceding values tie. For
   interchangeable samplers, equal partial profiles remain tied and the work comparison applies
   only after the complete plan passes.

The common work policies are:

- **target work:** compare the sum of successful target-declaration medians; and
- **combined work:** compare the correctness-closure median plus the sum of successful
  target-declaration medians.

This prevents arbitrary seed numbering or a cheaper subset of hidden instances from deciding a
partial tie. The per-problem policy is listed in [`problem-scoring.md`](problem-scoring.md). If all
competitive values tie, the submissions remain tied; correctness-closure work is not compared
again. Submission name determines display order but does not break the competitive tie.

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

## Evaluation environment

- Official instruction counts are measured on the pinned Linux PMU host inside the evaluation
  container.
- Submission validation and elaboration run as a non-root user in a network-disabled container
  with the problem's published memory limit, 2 CPUs, and a 512-process limit.
- Official kernel replay uses that local PMU environment. Non-official KTP/3 validation may send
  only immutable exported artifacts to a remote executor and binds each request and response to
  the applicable problem memory limit.
- The stage uses Lean **v4.33.1**, comparator `3927ad3`, lean4export `15f6055`, and
  kernel replay via Lean's built-in `Lean.Replay`.
- Attempts to escape the evaluation environment or exploit the judge result in disqualification.

The production measurement and container paths must be validated on the official PMU hardware
before launch.

## Local development

`scripts/perf_eval.py` runs one wall-time repetition through the canonical judge. It uses the same
export, audit, and measurement boundaries as the official path, but it is for development only and
does not use official seeds, cohorts, remote timing, or production isolation.
