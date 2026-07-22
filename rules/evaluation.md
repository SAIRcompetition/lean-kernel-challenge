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
                       (axioms restricted to R3; no Mathlib; no sorry/native_decide)
  → performance      : for each judge-chosen input n, time the kernel reducing `impl n`
                       (a named `theorem : impl n = v := by decide +kernel`, where v is computed
                        by a trusted reference; the kernel must fully reduce impl n to check it)
  → scaling data + verdict
```

The correctness proof is verified once and covers every input, so the performance phase can use
any n — including inputs never shown to contestants, and several sizes to reveal scaling.

## Verdicts

- **accepted** — correctness gate passed; carries per-input timings.
- **rejected** — a rule violation or a failed proof (the reason says which).
- **error** — infrastructure failure (exit code 2); never a scored outcome.

## Scoring

- The score of an accepted submission is the **kernel instruction count** to reduce `impl n`
  at the judge's inputs (Linux `perf -e instructions`; lower is better). Instruction counts are
  hardware-independent, so no cross-machine normalization is applied. Wall-clock is used only for
  local development.
- Results are reported as a **scaling curve** (x = input n, y = instructions), so an algorithm's
  growth is visible, not just a single number. For problems whose difficulty is monotone in n,
  this directly shows how far a submission scales.
- No partial credit within a problem: impl must be correct (for all n) *and* fast.
- Each problem has its own leaderboard. The overall standing is intended to aggregate your best
  problems with a relative-placement ("red queen") component — **not yet implemented / finalized
  (TBD)**; the exact formula will be published in a scoring appendix.

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
