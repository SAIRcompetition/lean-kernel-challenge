# Fibonacci — participant workspace

Edit only `Submission.lean`: implement your algorithm and prove
`∀ n, impl n = Nat.fib n`. The starting implementation and proof already work.
`Submission.lean` imports the fixed `Spec.lean`, which imports Mathlib's `Nat.fib`.
See the [problem statement](../../rules/problems/fib.md) for the official Mathlib
specification, input groups, and scoring rules.

## Quick start

Install Git, Python 3.9+, and [elan](https://github.com/leanprover/elan), then run
from the repository root:

```bash
cd problems/fib
python3 setup.py
lake build
```

Setup prepares this folder's pinned Lean 4.33.1 and Mathlib dependencies; first
use needs network access. It does not build or require the evaluator, Docker,
comparator, exporter, or replay timer. After editing your code, repeat `lake build`.
Keep `Spec.lean` and the environment files unchanged; they are generated from the
fixed [evaluation workspace](../../evaluation/problems/fib/).

Building compiles your definitions and proofs. It does not independently check
the official interface or permitted axioms, measure kernel performance, or award
a score. A successful build does not guarantee official acceptance.

Submit only **`Submission.lean`**, not this folder.

## Optional kernel evaluation

To run the canonical judge locally on the same file, follow
[evaluation/README.md](../../evaluation/README.md). This is a separate setup;
you do not need it to write code or build your submission.
