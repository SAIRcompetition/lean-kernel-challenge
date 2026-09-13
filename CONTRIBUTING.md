# Contributing

This repository holds the Stage 1 infrastructure for the Lean Kernel Challenge.
Contributions we welcome:

## New problems

A problem has a locked evaluation workspace. All eight scored tasks use
`evaluation/problems/<id>/`, separate from the editable `problems/<id>/` participant
package.
Use the routing helpers in `scripts/problem_layout.py`
when locating evaluation files. A good kernel-computation problem has:

- a **correct, total** parametric spec `spec : Nat → Output` that the kernel can
  reduce on every input, using only the dependencies pinned for that problem;
- substantial room for algorithmic and representation improvements, measured
  through kernel replay rather than compiled execution;
- a `baseline` submission `impl := spec` with `impl_correct := fun _ => rfl`;
- an `evaluation` block in `config.json` that defines the difficulty axis, ordered
  workload groups, a reproducible sampler, case counts, resource limits, and the
  per-problem instruction-cost policy. Under `full-plan-v1`, every case must pass to earn
  100 points; groups do not award partial points. See `rules/problem-scoring.md` and the
  existing scored problems.

Specs may import a standard library definition instead of reimplementing it.
For example, `fib` uses Mathlib v4.33.1's `Nat.fib` from `Mathlib.Data.Nat.Fib.Basic`;
see its [official API and pinned source](rules/problems/fib.md#mathlib-specification).
The other seven scored tasks remain core-Lean-only. A library-backed task
must document its exact declaration and version, link the official API and fixed-version
source, and supply locked dependencies for offline evaluation.

Add the workspace (Spec / Challenge / Solution / config with `definition_names = ["impl"]`,
`theorem_names = ["impl_correct"]`, and a grouped `evaluation` policy) and at least the
`baseline` example submission. Register the task in the evaluator, scoring, and reference-answer
registries and the local entrypoints; creating a directory alone does not activate a task.
Update the participant synchronization and registry tests, wire the examples into
`tests/harness_manifest.json`, and add the public group table to `rules/problem-scoring.md`.

## Adversarial test submissions

New ways a submission might cheat are especially valuable. Add the submission
under `examples/submissions/<problem>/<name>/` and a `rejected` case to the
manifest with a `reason_contains` substring.

## Green gate

For each scored task, run `lake build` inside `problems/<id>/`. Only fib needs
its [participant setup](README.md#quick-start) first. This compiles the definitions and proofs, not an
independent check against the official interface or permitted axioms.

Regenerate participant dependencies with `python3 scripts/sync_participants.py`;
use `--check` to verify their toolchains, Lake configuration, and fixed Spec copies
against the canonical evaluation files. Fib additionally has a pinned Mathlib manifest.
Do not edit generated participant dependencies independently. The older
`sync_fib_participant.py` command remains compatible for fib only.

Every change must also keep the repository test suite and `python3 scripts/run_harness.py`
green. The harness requires the separate [judge setup](README.md#maintainer-regression-and-judge-checks)
and is separate from participant builds. See `rules/overview.md` for the rules.

## Reporting a soundness issue

If you find a way to get an incorrect submission **accepted**, do not open a
public issue — contact the organizers directly.
