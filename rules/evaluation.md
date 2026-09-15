# Stage 1 — Evaluation

See [Problems and Scoring](problems/README.md#scoring) for test plans and ranking,
and [implementation status](problems/README.md#implementation-status) for deployment.

## Specification and implementation

The judge checks `impl_correct : ∀ n, impl n = spec n` for every natural-number
input, not just test cases. `impl` must also be total and kernel-reducible to an
output literal under [R2 and R3](overview.md#rules).

The specification fixes the result, not the algorithm; the evaluator measures
`impl`. For example, the [Fibonacci starter](../problems/fib/Submission.lean)
uses `Nat.fastFib` to compute `Nat.fib`. See the
[specification table](problems/README.md#mathlib-status) for all targets.

## Evaluation process

1. **Build and verify correctness.** Check the file, locked interface, permitted
   axioms, and universal proof. Only a pass is **Accepted**.
2. **Replay verification.** Replay the verified definitions and proof three times.
   Report the median instruction count as **correctness replay — verification only**.
   All three must finish; their counts do not affect ranking.
3. **Prepare each case.** For official input `n` and exact output `v`, generate,
   kernel-check, and export `impl n = v` against the frozen compiled submission,
   without re-elaborating contestant source. Check its binding to the verified
   implementation, input, and target, then its axioms.
4. **Measure computation.** In three separate processes, count only the target
   declaration's kernel check, which reduces `impl n` and compares it with `v`.
5. **Report and rank.** Report each selected case's outcome and median
   **computation replay** count. Rank complete passes by the sum `T` of these
   medians, lowest first; equal totals tie. This applies to all eight problems.

Audits and replays use the same immutable export. The generated `Eq.refl v`
forces the kernel to reduce `impl n` to `v` during preparation and each replay;
a contestant-supplied single-answer proof cannot replace it.

**Verdicts:** `accepted` means correctness passed, but failed cases or incomplete
verification leave it unranked. `rejected` means validation, correctness, or a
rule failed; `retry` requires another attempt; `error` requires organizer review.
Infrastructure failures are not contestant performance failures.

[Check and case limits](problems/README.md#limits) are independent:

- The correctness comparator gets 600 seconds, its axiom audit 60 seconds, and
  each correctness replay 300 seconds. Each target replay gets its group's
  30-, 60-, or 120-second limit. All replay limits apply per repetition.
  Build/export share 600 seconds per case; binding/axiom audits share a separate
  300 seconds per case, with the axiom audit receiving the remainder.
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
  does not prove implementation change.
- Later cases continue after a case failure. Fatal evaluator failures require
  review and re-evaluation, with unattempted cases recorded as such. Timeout
  alone does not establish a reducibility violation.

A cohort fixes inputs, seed commitment, answers, specification, dependencies,
ranking, repetitions, budgets, resources, toolchain, executor, and measurement
boundaries. Changes require a new cohort and full rescore; never mix cohorts or
metrics. Official runs use a secret `PERF_SEED`, rotated per cohort and passed
once through judge stdin, never to contestant-controlled Lean processes.
Unseeded runs are for local development.

Overall deadlines must cover all stage budgets, setup, reference preparation,
and overhead without shortening or omitting cases. Budget changes require a
rebuilt image and aligned platform consumers; see the
[maintainer guide](../evaluation/maintainers.md#stage-budgets-and-task-deadlines).
These limits do not imply hosted adoption or guarantee every valid proof finishes.

## Environment

Lean and Mathlib are currently pinned to **4.33.1**. We will upgrade the
environment for major Lean updates.

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
Production-host validation is pending. The wrapper verifies memory and swap
against the fixed problem configuration and records the host identity.
Attempting to escape the environment or exploit the judge leads to disqualification.

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

Replace `partition` with your problem ID. This checks correctness and kernel
computation for `problems/<id>/Submission.lean` on the **full unseeded public plan**,
with one wall-time measurement per case—not official PMU counts, isolation, or rankings.

See the [local evaluator guide](../evaluation/README.md) for custom submissions,
timeouts, and results, or [maintainer deployment](../evaluation/maintainers.md)
for official-host setup. Evaluation is optional in the
[participant workflow](problems/README.md#quick-start).

## Standings and publication

### Submission records

Select the latest formal entry under the [submission rules](overview.md#submission);
status changes and retries cannot change its identity. Missing, unreadable, or
integrity-failing source is a platform error: never omit the entry or restore an
older one. Final selection is fully frozen only after the original source is
recovered and verified against its original manifest and hash.

### Daily provisional standings

During submission, the platform may publish up to one provisional edition daily
using hidden reference inputs under the published policy. These may change
between editions and need not be disclosed later. Updates are not real-time.

A submission day runs from 00:00 UTC inclusive to the next 00:00 exclusive.
Each edition freezes selected identities and shows its cutoff or coverage date,
generation time, and time zone. Publication timing never guarantees completion
or shortens resource limits. Lag and missed-edition handling will be announced
before launch.

An edition is complete only when every selected entry has a trusted terminal
outcome—accepted, rejected, or an explicitly classified judge or infrastructure
error—with evidence identifying that entry. Queued, running, retrying, missing,
and unknown outcomes remain unfinished, including failed attempts awaiting retry.
Deadlines, elapsed time, or missing metrics cannot justify dropping an entry or
declaring it terminal.

Terminal errors count as processed but have no public row, total, or rank.
They remain subject to organizer review and recovery; affected teams can query
a sanitized private status and reason. Once all selected outcomes are terminal,
later editions need not await successful reruns. Publish only rankable results:
rejected or unscored entries produce neither failure rows nor fallback successes.

Never publish an incomplete edition: keep the previous complete board with a
delay notice, or a preparation notice before the first edition. After the
deadline, the last provisional board may remain with a final-evaluation notice.
Do not publish raw verdicts, hidden inputs, or secrets.

### Final evaluation and release

Final evaluation is a separate post-deadline batch cohort using the same
latest-entry rule, with no fixed duration. Raw verdicts, inputs, and contestant
code remain private during evaluation. Re-evaluate incomplete runs after
reviewing any fatal errors. Deliberate re-evaluation uses a new hidden seed and
cohort and rescores the full comparison set.

After the final cohort closes, release its seed, exact input plan, results, and
benchmark data under an open-source license. Publish contestant code afterward
under the submission-version, licensing, and authorization terms announced
before launch.
