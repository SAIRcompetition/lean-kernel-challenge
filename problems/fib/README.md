# Fibonacci — participant workspace

Edit only `Submission.lean`: implement your algorithm and prove
`∀ n, impl n = Nat.fib n`. The starting implementation and proof already work.
See the [problem statement](../../rules/problems/fib.md) for the official Mathlib
specification, input groups, and scoring rules.

## Quick start

Install Git, Python 3.9+, and [elan](https://github.com/leanprover/elan), then run
from the repository root:

```bash
cd problems/fib
python3 setup.py
lake build
lake exe quick_test
```

Setup prepares this folder's pinned Lean 4.33.1 and Mathlib dependencies; first
use needs network access. It does not build or require the evaluator, Docker,
comparator, exporter, or replay timer. After editing your code, repeat the last
two commands. Keep the checked-in environment files unchanged.

`QuickTest.lean` checks the required all-input theorem and compares compiled
outputs on `0`, `1`, `2`, `10`, and `20`. This is a public quick test, not an
official correctness audit, kernel benchmark, submission, or score. Passing
does not guarantee official acceptance or performance.

Submit only **`Submission.lean`**, not this folder.

## Optional kernel evaluation

To run the canonical judge locally on the same file, follow
[evaluation/README.md](../../evaluation/README.md). This is a separate setup;
you do not need it to write code or run the quick test.
