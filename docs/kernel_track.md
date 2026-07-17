# Kernel Computation Track — I/O Contract & Budgets

The track specification. For the binding rules see [`rules.md`](rules.md); for how
the judge works internally see [`../README.md`](../README.md).

## Task

For each problem you compute a value and prove it equals the problem's trusted
spec, such that the **official Lean kernel re-checks your proof with the fewest
instructions**. The kernel's re-checking *is* the timed computation.

## Submission I/O contract

- A submission is one directory containing `Submission.lean` and, optionally,
  additional `.lean` files under a `Submission/` subdirectory. Nothing else is read.
- `Submission.lean` must define, in `namespace Submission`:
  - `answer` — the computed value, a **raw numeral literal** of the problem's
    answer type (`Nat` or `Int`);
  - `answer_correct` — a proof of `spec instance = answer`.
- Allowed imports: the problem's provided modules (e.g. `Spec`) and Lean **core**
  only. No Mathlib, no external dependencies (rule R5).
- The judge supplies the locked `Spec.lean`, `Challenge.lean`, `Solution.lean`,
  and `config.json`; your copies of these are ignored (rule R1).

## Verdict

The judge returns one of:

- `accepted` — passed comparator (statement + axiom whitelist + kernel replay),
  the R2 literal audit, and the R3 axiom re-audit; carries a timing.
- `rejected` — a rule violation or a failed proof (the `reason` says which:
  comparator failure, `R2`, axiom audit, or a timeout).
- `error` — infrastructure failure (exit code 2), never a scored outcome.

## Budgets (pipeline/config.json)

| Budget | Default | Meaning |
|---|---|---|
| comparator | 3600 s | build + verify (correctness gate; not scored) |
| export | 1800 s | lean4export of the Solution closure |
| audit | 300 s | R2 literal + R3 axiom checks |
| timing rep | 1800 s | each of N kernel-replay reps |
| reps | 3 | timing is the median |
| payload | 8 MiB / 256 files | contestant submission cap |

## Scoring

- Score of an accepted submission = **kernel re-check instruction count** on the
  Linux host (`perf`), normalized to virtual CPU time (6.0 Ginstr/s); lower is
  better. Peak memory is a reported tiebreaker. Locally, wall time is used.
- Per-problem leaderboards; overall standing aggregates your best N problems with
  a relative-placement component (scoring appendix, finalized mid-competition).

## Environment

- Linux, bare-metal (PMU for `perf`), sandboxed container (see `Dockerfile`).
- Pinned toolchain: Lean v4.32.0-rc1; comparator/lean4export/Lean4Checker at the
  revisions in `pipeline/config.json`. Frozen for the stage.
- No network; resource-limited. Sandbox-escape or harness-exploit attempts are
  disqualified.

## Local development

```bash
scripts/setup.sh                                  # build the pinned tools
python3 scripts/run_harness.py --quick            # green gate on the examples
python3 judge/judge.py run --problem fib --submission examples/submissions/fib/doubling
```

The local landrun shim does **not** sandbox — never run untrusted submissions on
a dev machine. Real sandboxing is in the Docker image only.
