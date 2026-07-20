# Contributing

This repository holds the Stage 1 (kernel-computation track) infrastructure for
the Lean Kernel Challenge. Contributions we welcome:

## New problems
A problem is a locked workspace under `problems/<id>/` (see any existing problem
for the layout). A good kernel-computation problem has:
- a **naive but correct** spec in core Lean (no Mathlib), using **structural
  recursion** so the kernel can reduce it;
- a spec whose direct kernel evaluation at the instance is infeasible or slow, so
  contestants must be clever;
- a long optimization ladder (mathematical shortcuts *and* kernel-fu), not just
  a representation tweak;
- a known/verifiable answer for the chosen instance.

Add the workspace, an official-answer note, and at least a `baseline` example
submission. Wire it into `tests/harness_manifest.json`.

## Adversarial test submissions
New ways a submission might cheat are especially valuable. Add the submission
under `examples/submissions/<problem>/<name>/` and a `rejected` case to the
manifest with a `reason_contains` substring.

## Green gate
Every change must keep `python3 scripts/run_harness.py` green. See `README.md`
for the pipeline and `rules/overview.md` for the finalized rules.

## Reporting a soundness issue
If you find a way to get an incorrect submission **accepted**, do not open a
public issue — contact the organizers directly.
