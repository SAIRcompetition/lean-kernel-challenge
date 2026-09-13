# Contributing

This repository holds the Stage 1 infrastructure for the Lean Kernel Challenge.
Contributions we welcome:

## New problems

A problem is a locked workspace under `problems/<id>/` (see any existing problem
for the layout). A good kernel-computation problem has:

- a **naive but correct** parametric spec `spec : Nat → Output` in core Lean (no
  Mathlib), using **structural recursion** so the kernel can reduce it on any `n`;
- a spec whose direct kernel evaluation blows up as `n` grows, so contestants must
  be clever;
- a long optimization ladder (mathematical shortcuts *and* kernel-fu), not just
  a representation tweak;
- a `baseline` submission `impl := spec` with `impl_correct := fun _ => rfl`;
- an `evaluation` block in `config.json` that defines the difficulty axis, ordered
  workload groups, a reproducible sampler, case counts, resource limits, and the
  per-problem instruction-cost policy. Under `full-plan-v1`, every case must pass to earn
  100 points; groups do not award partial points. See `rules/problem-scoring.md` and the
  existing scored problems.

Add the workspace (Spec / Challenge / Solution / config with `definition_names = ["impl"]`,
`theorem_names = ["impl_correct"]`, and a grouped `evaluation` policy) and at least the
`baseline` example submission. Wire it into `tests/harness_manifest.json` and add the public
group table to `rules/problem-scoring.md`.

## Adversarial test submissions

New ways a submission might cheat are especially valuable. Add the submission
under `examples/submissions/<problem>/<name>/` and a `rejected` case to the
manifest with a `reason_contains` substring.

## Green gate

Run `python3 scripts/quick_test.py` for a fast check of all shipped baselines on small,
fixed public inputs. This compiled demo is participant-facing convenience only: it does
not run the official judge, hidden plan, PMU measurement, axiom audit, or scoring path.

Every change must also keep the repository test suite and `python3 scripts/run_harness.py`
green. The harness exercises the judging pipeline; it is intentionally separate from the
public quick test. See `README.md` for the development commands and `rules/overview.md` for
the rules.

## Reporting a soundness issue

If you find a way to get an incorrect submission **accepted**, do not open a
public issue — contact the organizers directly.
