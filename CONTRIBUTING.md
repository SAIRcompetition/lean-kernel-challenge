# Contributing

This repository holds the Stage 1 (kernel-computation track) infrastructure for
the Lean Kernel Challenge. Contributions we welcome:

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
- an `evaluation` block in `config.json` that defines the difficulty axis, ordered groups,
  reproducible sampler, case count, milestone points, resource limits, and per-problem tie-break.
  The groups must total 100 points and span a useful optimization ladder; see
  `rules/problem-scoring.md` and the existing scored problems.

Add the workspace (Spec / Challenge / Solution / config with `definition_names = ["impl"]`,
`theorem_names = ["impl_correct"]`, and a grouped `evaluation` policy) and at least the
`baseline` example submission. Wire it into `tests/harness_manifest.json` and add the public
group table to `rules/problem-scoring.md`.

## Adversarial test submissions
New ways a submission might cheat are especially valuable. Add the submission
under `examples/submissions/<problem>/<name>/` and a `rejected` case to the
manifest with a `reason_contains` substring.

## Green gate
Every change must keep `python3 scripts/run_harness.py` green. See `README.md`
for the pipeline and `rules/overview.md` for the rules (a pre-launch draft — still
subject to change before launch).

## Reporting a soundness issue
If you find a way to get an incorrect submission **accepted**, do not open a
public issue — contact the organizers directly.
