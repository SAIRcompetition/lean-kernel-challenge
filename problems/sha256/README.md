# SHA-256 chain — participant workspace

Edit `Submission.lean` and prove `∀ n, impl n = sha256Spec n`. See the
[problem statement](../../rules/problems/sha256.md) for the specification,
examples, test groups, and scoring.

## Quick start

Install [elan](https://github.com/leanprover/elan), then run from the repository
root:

```bash
cd problems/sha256
lake build
```

This package uses core Lean and needs no separate setup. Keep `Spec.lean` and
the environment files unchanged; submit only `Submission.lean`. `lake build`
checks compilation and proofs, not official acceptance or performance. For
optional local evaluation, see the [evaluator guide](../../evaluation/README.md).
The starter is not guaranteed to pass every performance case.
