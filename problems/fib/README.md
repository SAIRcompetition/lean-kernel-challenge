# Fibonacci — participant workspace

Edit `Submission.lean`: implement your algorithm and prove
`∀ n, impl n = Nat.fib n`. The starter already compiles.
See the [problem statement](../../rules/problems/fib.md) for the specification,
examples, test groups, and scoring.

## Quick start

Install [elan](https://github.com/leanprover/elan), Git, and Python 3.9+, then run from the repository root:

```bash
cd problems/fib
python3 setup.py
lake build
```

Setup prepares this package's pinned Mathlib dependencies; first setup needs network access.
Lean is pinned to **4.33.1**. After editing, repeat `lake build`.
Keep the fixed `Spec.lean` and environment files unchanged. Submit only
**`Submission.lean`**, not the folder.

Building checks code and proofs, not the official interface, axiom policy, or
performance. No evaluator or Docker is required. For optional correctness and
kernel wall-time checks, follow the [local evaluator guide](../../evaluation/README.md).
A starter is not guaranteed to pass every performance case.
