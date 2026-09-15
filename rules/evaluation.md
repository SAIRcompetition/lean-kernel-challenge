# Stage 1 — Evaluation

[Problems and Scoring](problems/README.md#scoring) defines test plans and ranking;
[implementation status](problems/README.md#implementation-status) records the
current policy and deployment boundary.

## Specification and implementation

The fixed `spec` defines the mathematical result. The judge checks
`impl_correct : ∀ n, impl n = spec n`, a proof for every natural-number input,
not just test cases. Independently, `impl` must be total and kernel-reducible to
an output literal under [R2 and R3](overview.md#rules).

A Mathlib specification fixes the target, not the algorithm. The
[Fibonacci starter](../problems/fib/Submission.lean) uses
`Nat.fastFib` and proves equality with `Nat.fib`; the evaluator measures `impl`.
The [status table](problems/README.md#mathlib-status) lists the three Mathlib and
five repository-defined targets.

## Evaluation process

1. **Build and verify correctness.** Check the file, locked interface, permitted
   axioms, and universal proof. Only a pass is **Accepted**.
2. **Replay verification.** Replay the verified definitions and proof three
   times. Record their median instruction count separately as **correctness
   replay — verification only**. All three must finish; their counts never
   affect ranking.
3. **Prepare each case.** For official input `n` and exact output `v`, generate,
   kernel-check, and export `impl n = v` against the frozen compiled submission,
   without re-elaborating contestant source. Check its binding to the verified
   implementation, input, and target, then its axioms. Build/export share 600
   seconds per case; binding/axiom checks share another 300 seconds per case.
4. **Measure computation.** In three separate processes, count only the target
   declaration's kernel check, which reduces `impl n` and compares it with `v`.
5. **Report and rank.** Report every selected case's outcome and median of its
   three **computation replay** counts. Rank only complete passes by the sum
   `T` of those medians, lowest first; equal totals tie. Correctness replay is
   reported separately and excluded for all eight problems.

Audits and replays use one immutable export. Its generated `Eq.refl v` proves
`impl n = v` only when the kernel reduces `impl n` to `v`, during preparation
and every replay. A contestant-supplied single-answer proof cannot replace it.

Preparation, audits, startup, and export parsing are outside the ranking counter;
each target process kernel-checks dependencies before opening it. All consume
time and memory: the watchdog includes startup, parsing, and dependency replay,
and the problem memory limit applies throughout. A run may exhaust resources
before the target. The metric is kernel work, not compiled runtime or process time.

Organizers independently prepare the cohort-wide output bundle before judging.
It must match the specification and full plan, never replacing kernel checks. A
missing or invalid bundle, or failed generated equality check, is an evaluation
error, not contestant failure.

**Verdicts:** `accepted` means correctness passed; failed cases or incomplete
verification leave it unranked. `rejected` means validation, correctness, or a
rule failed; `retry` requests another attempt; `error` requires organizer
review. Infrastructure failures are not contestant performance failures.

[Check and case limits](problems/README.md#limits) are independent:

- The correctness comparator gets 600 seconds, its axiom audit 60 seconds, and
  each of three correctness replays 300 seconds. Each target replay separately
  gets its group's 30-, 60-, or 120-second limit on each of three repetitions.
- Comparator timeout fails correctness; correctness-audit timeout is an
  infrastructure error. Correctness-replay timeout leaves an Accepted entry
  unranked.
- An attested comparator or correctness-audit memory kill rejects. The same in
  correctness replay leaves the entry Accepted but unranked; in case
  build/export, case axiom audit, or target replay it marks that case
  `resource-limit`. Memory classification requires an increased cgroup OOM
  counter, not SIGKILL alone.
- Export binding must finish before timing. Failure, timeout, or memory exhaustion
  stops the run with `error` for review and re-evaluation; an unfinished check
  does not prove implementation change. Binding and case axiom audit share 300
  seconds, with the audit receiving the remainder.
- Later cases continue after a case failure. Fatal evaluator failures require
  review and re-evaluation, with unattempted cases recorded as such. Timeout
  alone does not establish a reducibility violation.

A cohort fixes inputs and seed commitment, answers, specification,
dependencies, ranking policy, repetitions, budgets, limits, toolchain, executor,
and measurement boundaries. Any change requires a new cohort and full rescore;
budget changes require a rebuilt image and aligned platform consumers.
Cohorts and metrics never mix. See
[standings and publication](#standings-and-publication) for disclosure.

The orchestration deadline must cover all budgets, setup, reference preparation,
and overhead; it cannot shorten or omit later cases. The
[maintainer guide](../evaluation/maintainers.md#stage-budgets-and-task-deadlines)
gives planning totals and compatibility requirements. Proposed limits neither
establish hosted adoption nor guarantee every valid proof finishes.

Official evaluation rotates a secret `PERF_SEED` by cohort. The isolated wrapper
sends it once via judge stdin, never to contestant-controlled Lean processes.
Unseeded runs are local development only.

## Environment

| Component | Configuration |
| --- | --- |
| Lean | **4.33.1** for all eight problems |
| Mathlib | Pinned **v4.33.1** for fib, mertens, and primecount; core Lean for the other five |
| Official OS / metric | Linux PMU host with cgroup v2 and Landlock; Ubuntu 24.04 container; kernel instruction counts |
| CPU allocation | 2 CPUs per evaluation job |
| Memory | 8 GiB for permanent; provisional 4 GiB for the other seven; no extra swap |
| Process limit | 512 per container |
| Isolation | Non-root container, networking disabled, read-only submission files |
| Tools | Comparator `3927ad3` with the [emit-export patch](../evaluation/patches/comparator-emit-export.patch); lean4export `15f6055`; Lean's `Lean.Replay` |

**The official CPU model and full hardware specification are not yet published.**
CPU allocation is not a hardware model; production-host validation remains
pending. The wrapper verifies memory and swap against the fixed problem
configuration and records cohort host identity. Attempting to escape the
environment or exploit the judge leads to disqualification.

[Tool pins](../evaluation/config.json) and Mathlib locks fix the software.
Official timing uses in-container `local-v2`, `kernel-replay-v2`,
`full-closure-replay-v1` correctness, `target-declaration-replay-v1`
computation, and a recorded target-proof encoding. Remote `KTP/3` is
non-official validation bound to the problem memory limit.

## Local quick start

Install Python 3.9+, Git, [elan](https://github.com/leanprover/elan), and a C/C++
toolchain; on macOS, GNU coreutils. From the repository root:

```bash
bash evaluation/setup.sh --problem partition
python3 evaluation/run.py --problem partition
```

Replace `partition` with a problem ID. This checks
`problems/<id>/Submission.lean` on the **full unseeded public plan**, measuring
wall time once per case. It checks correctness and kernel computation but does
not reproduce official PMU counts, isolation, or rankings.

See the [local evaluator guide](../evaluation/README.md) for custom submissions,
timeouts, and results, or [maintainer deployment](../evaluation/maintainers.md)
for official-host setup. Evaluation is optional in the
[participant workflow](problems/README.md#quick-start).

## Standings and publication

### Submission records

Use the latest formal entry under the [submission rules](overview.md#submission).
Its identity is immutable across status changes and retries. Missing, unreadable,
or integrity-failing source produces a platform error without omission or
fallback to an older entry. Final selection is fully frozen only after the
original source is recovered and verified against its original manifest and hash.

### Daily provisional standings

During submission, the platform may publish up to one provisional edition per
day using hidden reference inputs under the published policy. Organizers may
change and need not later disclose them; the board is not real-time.

A submission day is 00:00 UTC inclusive to the next 00:00 exclusive, including
23:59:59. Each edition freezes selected identities and states its cutoff or
coverage date, generation time, and time zone. Lag and missed-edition handling
will be announced before launch. Cutoff and publication promise neither
completion nor shorter resource limits.

An edition is complete only when every selected submission has a trusted
terminal outcome—accepted, rejected, or an explicitly classified judge or
infrastructure error—whose evidence identifies that selected identity. Queued, running,
retrying, missing, and unknown remain unfinished; a failed attempt awaiting
retry is not terminal. Deadlines, elapsed time, or absent metrics cannot drop an
entry or make it terminal.

Terminal errors are processed but receive no public row, total, or rank. They
remain subject to organizer review and recovery; the affected team can query a
sanitized private status and reason. Once all selected outcomes are terminal,
later editions need not await successful reruns. Only rankable results are
public; rejected and accepted-but-unscored entries create no failure row or
fallback success.

Never publish an incomplete edition. Keep the previous complete board with a
delay notice; before the first, show that preparation continues. The last
provisional board may remain after the deadline with a final-evaluation notice.
Boards reveal no raw verdicts, hidden inputs, or secrets.

### Final evaluation and release

Final results are a separate batch cohort after the deadline, using the same
latest-entry rule; no duration is promised. Raw verdicts, inputs, and contestant
code stay private during evaluation. Incomplete runs are re-evaluated, with fatal
errors reviewed first. Deliberate re-evaluation uses a new hidden seed and cohort
and rescores the comparison set rather than mixing cohorts.

After the final cohort closes, release its seed, exact input plan, results, and
benchmark data under an open-source license. Publish contestant code afterward
under the submission-version, licensing, and authorization terms announced
before launch.
