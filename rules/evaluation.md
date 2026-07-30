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
                       (axioms restricted to R4; no Mathlib; no sorry/native_decide), then parse
                       the comparator-verified export outside the counter and charge one replay
                       of its complete declaration closure
  → performance      : for each judge-chosen input n, export a theorem `impl n = v` whose
                       `of_decide_eq_true rfl` proof remains directly in that declaration;
                       parse it and preload its non-target dependency closure outside the
                       counter, then charge only replay of the generated target declaration.
                       Checking its `rfl` forces the kernel to fully reduce `impl n`
  → correctness timing + scaling data + verdict
```

The correctness proof covers every input, so the performance phase can use any `n`, including
inputs never shown to contestants. The judge (`judge/judge.py`) runs this full pipeline and imports
the exact byte-pinned `.olean` graph that produced the comparator-verified export; it does not
re-elaborate contestant source for timing. Both the median cost of replaying the correctness
export and the per-input `impl n` medians contribute to the score.

**Measurement contract `kernel-replay-v2`.** Its correctness boundary is
`full-closure-replay-v1`: process startup and export parsing are outside the counter, while one
complete replay of the verified closure is charged. Its performance boundary is
`target-declaration-replay-v1`: all non-target declarations are first replayed into a fresh
environment without counting, then the counter encloses only replay of the generated
`impl n = v` declaration. This is a scoped measurement, not an estimate obtained by subtracting
two noisy process totals.

The generated proof is intentionally a direct `of_decide_eq_true rfl` term. Lean's
`decide +kernel` tactic instead extracts the expensive check into a private
`check._proof_*` theorem and leaves `check` as a cheap wrapper, which would move the algorithm
outside this boundary. The timer rejects such extracted target helpers rather than publishing a
silently under-counted sample. Verdicts and cohort hashes pin this generator choice as
`direct-of-decide-eq-true-rfl-v1`; older records without that field are unscored.

The value `v` is obtained by kernel-side reduction (`Meta.whnf`), never compiled `#eval`; this
oracle is a correctness/build step and is not scored. A wrong value cannot be scored because the
generated theorem then fails. Target replay still includes reduction of `impl n` and comparison
with its exact output literal. Constructing and checking a large `Nat`/`Int` target is therefore
retained: it is input-dependent necessary kernel work, not fixed harness overhead.

## Verdicts

- **accepted** — correctness gate passed; carries correctness and per-input timings.
- **rejected** — a rule violation or a failed proof (the reason says which).
- **error** — infrastructure failure (exit code 2); never a scored outcome.

## Scoring

The official measurement unit is the **kernel instruction count** for the scoped replay region
(Linux PMU, median of N repetitions). The fixed host and pinned toolchain make it reproducible,
although it is not literally hardware-independent. Wall-clock medians are a local development
metric only. Instruction-count and wall-time verdicts are always placed in separate leaderboard
groups; values in different units are never compared.

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
- the complete comparator-verified `∀ n` correctness closure is replayed and charged once; and
- every completed target-declaration replay is charged in the curve aggregate.

A table or special case remains legal if it is globally proved, but building its constants into
the proof is not free. More importantly, increasing work at any proof or curve point cannot improve
the aggregate, unlike a ranking based on a fitted slope.

**Canonical ranking within one problem and one metric.**

1. More completed schedule slots wins.
2. If completed-slot counts tie but planned schedule sizes differ, higher coverage
   `completed / planned` wins.
3. If coverage ties, compare the complete success bitmap from the hardest slot downward.
4. Only identical success profiles use lower total measured kernel work:

   `W = median(full correctness-closure replay) + Σ median(completed target-declaration replay)`.

The profile step ensures raw work is compared only over the same sampled `n`. The sum uses one
consistent metric throughout the verdict. A legacy verdict without
`correctness_timing`, an incomplete slot record, or a metric mismatch is accepted evidence of
correctness but **unscored** under this contract; it is never silently mixed into the current
ranking. Remote scoped timing uses protocol **KTP/2**, and every current verdict commits to KTP/2
plus `kernel-replay-v2`, its two boundary versions, and its target-proof encoding. Changing any
of those fields requires a new public evaluation cohort and complete rescore: KTP/1 whole-process
results and other legacy verdicts never share a ranking with scoped-replay verdicts. Within one
version, verdicts are still partitioned by a cohort id committing to the exact input schedule,
repetitions/budget, toolchain, metric, and executor identity. A correct submission that completes
no input slot is also accepted but unscored.

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

`scripts/perf_eval.py` runs one repetition through the canonical judge locally and writes its
versioned verdict as a scaling JSON. It deliberately shares the same export, audit, and scoped
timer path instead of maintaining a second whole-process timing implementation. It accepts only
the local wall-time configuration and refuses official seed/cohort or remote-executor settings.
