# Mertens function — participant workspace

Edit `Submission.lean` and prove `∀ n, impl n = mertensSpec n`. See the
[problem statement](../../rules/problems/mertens.md) for the specification,
examples, test groups, and scoring.

## Quick start

Install [elan](https://github.com/leanprover/elan), Git, and Python 3.9+. From
the repository root:

```bash
cd problems/mertens
python3 setup.py
lake build
```

Setup prepares pinned Mathlib dependencies and initially needs network access.
Keep `Spec.lean` and the environment files unchanged; submit only
`Submission.lean`. `lake build` checks compilation and proofs, not official
acceptance or performance. For optional local evaluation, see the
[evaluator guide](../../evaluation/README.md). The starter is not guaranteed to
pass every performance case.
