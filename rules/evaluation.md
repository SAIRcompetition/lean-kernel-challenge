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
4. for each hidden input `n`, uses the official standard output `v` to generate and check
   a direct theorem `impl n = v`, then measures
   replay of that target declaration; and
5. records the measurements and verdict.

The correctness replay includes the verified definitions and proof. For each input, non-target
dependencies are replayed before measurement, and only the generated target declaration is
measured. Checking that declaration forces the kernel to reduce `impl n` and compare it with the
exact output literal. Process startup, export parsing, and dependency preloading are not scored.
The definition of `impl` is charged once in the correctness replay rather than once per input.

Correctness timing uses the immutable export produced by the correctness gate. For each performance
input, the judge creates a separate immutable export from the exact verified build; contestant
source is not re-elaborated. Before submissions are evaluated, the organizers prepare the standard
outputs independently with a reference program, a precomputed table, or another method consistent
with the trusted specification. The same cohort uses the same input/output pairs. This preparation
is outside the counter and never executes a contestant's `impl`.

The judge validates the answer bundle against the problem, specification version, and complete
input plan before running contestant code. Its digest is sealed into the cohort. These answers
are not trusted proofs: the direct target theorem still forces kernel reduction of `impl n` and
comparison with the exact literal. Missing, malformed, or incorrect official answers are evaluation
errors, not contestant failures. If the generated theorem fails kernel checking, the run is treated
as an evaluation error and is not scored.

These boundaries are versioned as measurement contract `kernel-replay-v2`, with
`full-closure-replay-v1` for correctness and `target-declaration-replay-v1` for each input.
Verdicts also record the target-proof encoding. A change to any of these fields requires a new
evaluation cohort.

## Verdicts

- **accepted** — the correctness gate passed. The submission is scored when its timed correctness
  replay and sealed cohort record are valid; any failed performance case yields zero points
  and infinite ranking cost.
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

Stage 1 has **eight independent 100-point problem leaderboards**. There is no cross-problem total or
relative-placement aggregation. `conv` is retained as an experimental development task and is not
part of these leaderboards.

**Complete-plan scoring.** Each problem publishes three input groups with an input generator or
range, case count, and target-replay limit. Groups specify workloads, not separate point awards.
A case passes when every target repetition completes within its watchdog and any published
instruction limit is satisfied by the median. All required case preparation must also succeed.
The exact plans are described in [`problem-scoring.md`](problem-scoring.md).

An otherwise scoreable submission earns **100 points only if every case in its complete hidden
plan passes**. If even one case fails, it earns **0 points and its ranking cost is infinite**.
There is no partial credit or ranking by harder groups, number of passes, or pass/fail order.
A baseline may earn 100 points; full-plan passes compete by reducing instruction cost.

The published watchdog applies separately to each target-timing process. It includes that
process's untimed parsing and preload overhead, while the ranking metric itself covers only the
target-declaration kernel replay. Generated-theorem build/export and axiom audit use separate
per-case ceilings: 1,800 seconds shared by build and export, and 300 seconds for the audit.
A contestant-dependent timeout in a required step fails that case and therefore gives the
submission zero points, but cannot consume another case's limit; later cases are still attempted.
Official reference-answer preparation is independent of the submission and is not charged to
these per-case budgets. A timeout does not by itself prove that `impl` is not kernel-reducible;
a confirmed violation of R2 is a rejection.

Each problem has its own memory limit, declared in `evaluation.memory_mb` (MiB) in
the locked `evaluation/problems/<id>/config.json` and published before official use.
Matrix permanent (`permanent`) has an 8192 MiB (8 GiB) limit. The other seven problems
retain provisional 4096 MiB (4 GiB)
limits pending organizer confirmation. Official-host validation remains required for every
problem; these allocations do not establish that every current baseline fits.
Organizers may revise a problem's limit during the competition. The limit is fixed within each
evaluation cohort and recorded in its sealed resource policy; a revision requires a new cohort
and a complete rescore of that problem's comparison set. Scores from different memory policies
are never mixed in one ranking.

The official evaluator job enforces the problem's limit through a cgroup-v2 envelope covering
the correctness gate, correctness replay, and performance cases, with zero extra swap. The judge
checks that the declared limit, image policy, and actual cgroup memory/swap settings agree. A child SIGKILL is classified
as memory exhaustion only when the attested `memory.events` OOM counter also increases. If that
cgroup kills a child while building/exporting a case theorem, auditing it, or replaying its
target, the case fails with `resource-limit` and later cases are still attempted. Non-official
KTP/3 binds each replay request to the applicable problem memory limit. If resource enforcement
terminates the evaluator before it can write a complete case record, the run is investigated and
must be rerun against the same sealed plan before it can receive a score. Daily processing
completion follows the provisional-standings rules below; it does not make an incomplete run
scoreable.

Before evaluation, the judge resolves every hidden group/case coordinate into a complete
performance plan. The cohort seals that plan, its hash, and the grouped evaluation policy. The
verdict records an explicit outcome for every planned case. A timeout does not by itself stop the
plan: every later case is still attempted under its own limits. Grouped evaluation has no shared
aggregate deadline, so one case's work does not reduce another case's configured time allowance.
A platform interruption or fatal evaluator error makes the run incomplete. An incomplete final
official run requires re-evaluation; fatal evaluator errors require organizer review before the
run is repeated. For a daily reference run, the completion rules below allow a classified terminal
error to count as processed, but a complete re-evaluation is still required before it can receive
a score. Unattempted cases cannot be turned into zero-point results. The legacy `conv`
development schedule retains its separate
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
released publicly under an open-source license. Contestant code is private during the competition
and is published afterward; its version scope and licensing terms will be specified before launch
as described in [`prelaunch.md`](prelaunch.md). A deliberate re-evaluation uses a new hidden
seed and cohort and rescores the comparison set.

**Provisional standings during the submission window.** Each day the platform evaluates each
team's latest formal submission per problem as of the daily cutoff, using hidden inputs sampled
under the published problem policy, separately from the final official evaluation. Organizers may update these
reference inputs; their input plans and seeds are not subject to the final-results publication
commitment above. The platform builds a per-problem temporary board from those results:
the board updates once per day, not in real time. Submission days end at **23:59:59 UTC**,
including the whole final second; a day is the interval from 00:00 UTC inclusive to the next
00:00 UTC exclusive. Each edition must display its **generation timestamp and time zone**,
and identify its submission cutoff or coverage date. A cutoff assigns submissions to an edition;
it does not promise that evaluation and publication finish at that instant. The publication lag
and the handling of editions that miss their planned publication time will be announced before
launch. Neither the daily cutoff nor the planned publication time is an evaluation timeout or
shortens the published resource limits.

Freeze the selected submission identities for each edition. Selection uses the platform's
recorded submission time, regardless of when evaluation finishes. The same latest-submission
rule selects the official entry at the cutoff, as specified in
[`overview.md`](overview.md#submission). A newer rejected,
accepted-but-unscored, or terminal-error submission replaces an older success for that
team/problem; it does not restore the older result or create a public failure row. Only scoreable
results receive a public entry and rank.

For a daily edition, **processing is complete** when every selected submission has a recorded
terminal outcome: accepted, rejected, or an explicitly classified judge or infrastructure error.
Each outcome must be established from trusted evaluation-task evidence and belong to the selected
submission. A failed attempt with a retry still pending is not a terminal outcome. Queued, running,
retrying, missing, and unknown outcomes remain unfinished; neither elapsed time, missing metrics,
nor an approaching publication time permits dropping an entry or declaring it a terminal error.

A terminal error counts as processed for that daily edition. Retain its submission identity and
error record; it receives no score or rank and is not a zero-point contestant failure. Once every
selected submission has a terminal outcome, the edition may complete processing and later daily
scopes may proceed without first obtaining successful reruns of those errors. Organizer review
and any recovery still apply. This daily completion rule does not change the requirements for
scoreability or the final official evaluation.

When a terminal error is recorded, the team entitled to view that submission must be able to
query its error status and an understandable, sanitized reason. Its private status must reflect
the recorded error rather than continue to show the task as waiting. This does not disclose raw
verdicts, hidden inputs, or secrets, or publish a public leaderboard entry.

The organizers may publish the temporary board during the submission window. It is provisional
and does not determine the official result. An incomplete daily edition is never published. If
an edition is unfinished at its planned publication time, retain the previous complete edition
with a delay notice; before the first complete edition, show that it is being prepared. Publish
complete editions under the announced schedule and publication controls, without exposing raw
verdicts or hidden inputs. After the submission deadline, the last complete temporary edition
may stay visible with a final-evaluation notice until the published final leaderboard replaces it.

**Hardcoding and proof cost.** A table or special case is legal only if it is covered by the
universal correctness proof. Exact inputs remain hidden during evaluation. Final official inputs
are released as described above; no publication of provisional reference inputs or seeds is promised.
Both the complete verified correctness closure and every successful target replay are measured.
Every submission must complete the correctness replays within the applicable resource limits.
Each problem's published work policy states whether correctness-closure work also contributes to
ranking: combined-work problems include it, while target-work problems use only the successful
target replays for the work comparison. Neither policy adds a separate proof-cost tie-break.

**Canonical ranking within one problem, metric, measurement contract, and evaluation cohort.**

1. A full-plan pass (100 points) ranks above a failed plan (0 points).
2. Among full-plan passes, lower instruction cost wins under the problem's declared policy:
   **target work** is the sum of every target-declaration median; **combined work** adds the
   correctness-closure median once.
3. Equal costs remain tied. All scoreable failed plans have infinite ranking cost and remain
   tied; neither successful subsets nor correctness costs break their tie.

The per-problem work policy is listed in [`problem-scoring.md`](problem-scoring.md).
There is no separate correctness-cost comparison. Submission name may determine display order
but does not break the competitive tie. The sealed ranking contract is `full-plan-v1`;
previously sealed milestone policies retain their original semantics and cannot share its cohort.

**Scoreability and versioning.** Only accepted verdicts with a successful correctness replay, a
complete case record, a valid sealed policy, and one consistent metric are scoreable. A valid
submission with any failed case receives zero points and infinite ranking cost. Stage 1 official
cohorts require in-container **local-v2** PMU timing. Resource-bound **KTP/3** is available only for non-official validation.
Rankings never mix
metrics, evaluation cohorts, executors, timing protocols, or measurement-contract versions. Any
change to these fields requires a new cohort and complete rescore.

The cohort id commits to the exact performance plan, reference-answer digest and specification
version, scoring policy, repetition count, evaluation budgets, resource policy, toolchain, metric,
measurement contract, target-proof encoding, and
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
- The stage uses Lean **v4.33.1**, comparator `3927ad3` with the checked-in
  [emit-export patch](../patches/comparator-emit-export.patch), lean4export `15f6055`,
  and kernel replay via Lean's built-in `Lean.Replay`. Full revision pins are in
  [`pipeline/config.json`](../pipeline/config.json); evaluator setup applies the patch.
- Attempts to escape the evaluation environment or exploit the judge result in disqualification.

The production measurement and container paths must be validated on the official PMU hardware
before launch.

## Local development

Eight [participant workspaces](problems/README.md) are independent of the evaluator.
Run `lake build` inside `problems/<id>/`; fib alone needs `python3 setup.py` first.
This compiles definitions and proofs without the comparator, exporter, replay timer, or Docker.
It does not independently check the official interface or permitted axioms,
measure kernel performance, or produce a score.

For optional kernel measurements, run from the repository root:

```bash
bash evaluation/setup.sh --problem fib
python3 evaluation/run.py --problem fib --submission problems/fib/Submission.lean
```

Replace fib with the selected problem ID. The entrypoint copies only the selected
file and delegates to `scripts/perf_eval.py`. It runs that problem's complete
unseeded public plan with one wall-time repetition through the
canonical judge. This uses the same export, audit, and measurement boundaries as
the official path, but no official seed, cohort, PMU score, or production isolation.
See the [local evaluator guide](../evaluation/README.md).

Fixed evaluation files for all eight tasks live in `evaluation/problems/<id>/`.
The seven core-Lean tasks supply byte-identical generated Spec copies for participant
builds. Fib instead imports Mathlib; judge setup prepares its pinned Fibonacci
import closure for offline use. Its dependency lock
is part of the specification identity; changing it requires fresh reference answers
and a new cohort. Participant dependency files are generated from those same pins;
maintainers verify all eight packages with `python3 scripts/sync_participants.py --check`.
The other seven scored tasks do not require Mathlib.
