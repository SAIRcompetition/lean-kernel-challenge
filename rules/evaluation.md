# Lean Kernel Challenge — Evaluation

How submissions are judged and scored. For the task, rules, and problems see
[`overview.md`](overview.md).

## Judging pipeline

```
Submission.lean
  → validate (slugs, symlinks, size caps)
  → comparator : statement matches the locked challenge? axioms within R3? proof kernel-checks?
                 → emits the exact verified export (no separate re-export step)
  → R2 audit   : `answer` is a raw literal
  → R3 re-audit: that export declares only whitelisted axioms
  → timing     : official kernel replays that export, N reps, median   ← the score
  → verdict JSON + leaderboard
```

The judge times the export comparator itself verified, byte-for-byte — there is no independent
re-export, so what is measured is exactly what was statement-matched, axiom-checked, and
kernel-replayed.

## Verdicts

- **accepted** — cleared every gate; carries a score.
- **rejected** — a rule violation or failed proof (the reason says which: comparator failure, R2,
  axiom audit, or a timeout).
- **error** — infrastructure failure (exit code 2); never a scored outcome.

## Scoring

- The score of an accepted submission is the **instruction count** for the official kernel to
  re-check the verified export (Linux `perf -e instructions`, median of N reps; lower is better).
  Instruction counts are hardware-independent, so no cross-machine normalization is applied.
  Wall-clock is used only for local development.
- A rejected submission does not score. There is no partial credit within a problem: the answer
  must be correct *and* proven under the rules.
- Each problem has its own leaderboard. The overall standing is intended to aggregate your best
  **N** problems with a relative-placement ("red queen") component. **This aggregation is not yet
  implemented / finalized (TBD)**; the formula will be published in a scoring appendix and may be
  set mid-competition once the field's distribution is known.

## Budgets

| Budget | Default | Meaning |
|---|---|---|
| comparator | 3600 s | build + verify + emit the verified export (correctness gate; not scored) |
| audit | 300 s | R2 literal + R3 axiom checks |
| timing rep | 1800 s | each of N kernel-replay reps |
| reps | 3 | timing is the median |
| payload | 8 MiB / 256 files | contestant submission cap |

Budgets live in `pipeline/config.json`.

## Evaluation environment

- Official evaluation runs on a fixed Linux host (bare-metal, PMU access for `perf`). Each
  submission is judged in its own container, which is the sandbox and resource boundary: no
  network, bounded memory/CPU/PID, one job per container, non-root, and the whole job is killed on
  completion.
- Pinned toolchain, frozen for the stage: **Lean v4.32.0-rc1**, comparator `71b52ec` (+ the
  emit-export patch in `patches/`), lean4export `3de59f1`, Lean4Checker `b73981`.
- Do not attempt to escape the sandbox or exploit the harness; such submissions are disqualified.

**Status of the production path:** the perf instruction-counting metric and the container
isolation are implemented and code-reviewed but **not yet run on PMU hardware** (TBD before
launch). Locally the sandbox is a pass-through shim and timing is wall-clock — for development
only.

## Local reproduction

The local judge reproduces the exact evaluation pipeline, so you can check a submission before
sending it:

```bash
scripts/setup.sh                                  # build the pinned tools
python3 scripts/run_harness.py                    # green gate over the example submissions
python3 judge/judge.py run --problem fib --submission examples/submissions/fib/doubling
python3 judge/judge.py leaderboard
```

The local landrun shim does **not** sandbox — never run untrusted submissions on a dev machine.
Real isolation lives in the Docker image (see `Dockerfile`).
