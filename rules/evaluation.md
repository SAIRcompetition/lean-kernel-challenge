# Lean Kernel Challenge — Evaluation

How submissions are judged and scored. For the task, rules, and problems see `overview.md`.

## Judging pipeline

A submission provides `impl : Nat → Output` and `impl_correct : ∀ n, impl n = spec n`.
Judging verifies both artifacts and measures both parts of the accepted computation:

```
Submission.lean
  → validate (slugs, symlinks, size caps)
  → correctness gate : build the locked Solution, which references impl_correct — this checks
                       that impl is a total function equal to the trusted spec on ALL n
                       (axioms restricted to R4; no Mathlib; no sorry/native_decide), then replay
                       and time that comparator-verified correctness export
  → performance      : for each judge-chosen input n, export `theorem : impl n = v := by
                       decide +kernel` and time the official kernel replaying THAT — checking it
                       forces the kernel to fully reduce `impl n`. v is obtained by a kernel-side
                       reduction of `impl n` (Meta `whnf`), never compiled `#eval`, so a submission
                       fast in the kernel is always evaluable even when its codegen is slow; a
                       wrong v merely fails the build and is caught, never mis-scored
  → correctness timing + scaling data + verdict
```

The correctness proof covers every input, so the performance phase can use any `n`, including
inputs never shown to contestants. The judge (`judge/judge.py`) runs this full pipeline and imports
the exact byte-pinned `.olean` graph that produced the comparator-verified export; it does not
re-elaborate contestant source for timing. Both the median cost of replaying the correctness
export and the per-input `impl n` medians contribute to the score.

## Verdicts

- **accepted** — correctness gate passed; carries correctness and per-input timings.
- **rejected** — a rule violation or a failed proof (the reason says which).
- **error** — infrastructure failure (exit code 2); never a scored outcome.

## Scoring

The official measurement unit is the **kernel instruction count** (Linux
`perf -e instructions`, median of N repetitions). The fixed host and pinned toolchain make it
reproducible, although it is not literally hardware-independent. Wall-clock medians are a local
development metric only. Instruction-count and wall-time verdicts are always placed in separate
leaderboard groups; values in different units are never compared.

**Sampling schedule.** Each problem's `config.json` declares `perf {min, max}` and
`pipeline/config.json` supplies the default slot count, geometric spacing, and jitter. The result
is an ordered schedule of nominal difficulty slots. A verdict records every planned slot
explicitly, including timeout/failure outcomes; later independent slots may still complete.
Coverage therefore means the count of successful slots rather than the largest
sampled integer.

For an official run, the operator **must not reuse one public or permanent seed**. `PERF_SEED` is
a secret rotation token, changed for a new official round or deliberate re-evaluation. For each
slot, the judge hashes that token with the problem id and slot index. Every submission in the same
public cohort therefore receives the same hidden schedule—raw kernel work is never compared at
different randomly selected `n`. The production wrapper injects the secret once over stdin before
untrusted elaboration and the judge removes it from every child environment. An unset seed is
permitted only for deterministic local development and is not an official score.

Because a cohort shares one schedule, its raw verdicts and exact inputs are operator-private until
that cohort is closed. Submissions are evaluated as a batch after the submission cutoff; later
entries or deliberate re-evaluations use a new seed and cohort and rescore the comparison set.
Publishing an active cohort's inputs would turn evaluation into an oracle for targeted tables.

**Hardcoding and proof cost.** R3 guarantees extensional correctness; it does *not* imply that a
literal answer must be proved by directly reducing the naïve spec. A submission may derive a
literal through another verified algorithm and its correctness theorem. The scoring contract
therefore does not rely on the old, false claim that answer tables are impossible. Instead:

- exact sampled integers are hidden and rotate between evaluation cohorts;
- the comparator-verified `∀ n` correctness export is replayed and charged once; and
- every completed input replay is charged in the curve aggregate.

A table or special case remains legal if it is globally proved, but building its constants into
the proof is not free. More importantly, increasing work at any proof or curve point cannot improve
the aggregate, unlike a ranking based on a fitted slope.

**Canonical ranking within one problem and one metric.**

1. More completed schedule slots wins.
2. If completed-slot counts tie but planned schedule sizes differ, higher coverage
   `completed / planned` wins.
3. If coverage ties, compare the complete success bitmap from the hardest slot downward.
4. Only identical success profiles use lower total measured kernel work:

   `W = median(correctness replay) + Σ median(completed input replay)`.

The profile step ensures raw work is compared only over the same sampled `n`. The sum uses one
consistent metric throughout the verdict. A legacy verdict without
`correctness_timing`, an incomplete slot record, or a metric mismatch is accepted evidence of
correctness but **unscored** under this contract; it is never silently mixed into the current
ranking. Verdicts are also partitioned by a public evaluation-cohort id committing to the exact
input schedule, timing repetitions/budget, toolchain, metric, and executor identity. A correct
submission that completes no input slot is also accepted but unscored.

**Report-only diagnostics.** The scorer fits `log cost ≈ α log n + β` over completed points and
reports the fitted values alongside the curve data. Both α and β help explain behavior, but
neither affects rank. In
particular, deliberately padding low inputs may produce an attractive negative α, yet it can only
increase `W` and cannot improve placement.

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
