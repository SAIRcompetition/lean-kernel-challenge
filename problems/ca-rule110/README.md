# Rule 110 — participant workspace

Edit `Submission.lean` and prove `∀ n, impl n = caSpecN n`. See the
[problem statement](../../rules/problems/ca-rule110.md) for the specification,
examples, test groups, and scoring.

## Quick start

Install [elan](https://github.com/leanprover/elan), then run from the repository
root:

```bash
cd problems/ca-rule110
lake build
```

This package uses core Lean and needs no separate setup. Keep `Spec.lean` and
the environment files unchanged; submit only `Submission.lean`. `lake build`
checks compilation and proofs, not official acceptance or performance. For
optional local evaluation, see the [evaluator guide](../../evaluation/README.md).
The starter is not guaranteed to pass every performance case.
