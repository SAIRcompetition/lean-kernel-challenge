# Matrix permanent — participant workspace

Edit `Submission.lean`: implement your algorithm and prove
`∀ n, impl n = permanentSpecN n`. The starter already compiles.
See the [problem statement](../../rules/problems/permanent.md) for the specification,
examples, test groups, and scoring.

## Quick start

Install [elan](https://github.com/leanprover/elan), then run from the repository root:

```bash
cd problems/permanent
lake build
```

This problem uses core Lean; no Mathlib or separate setup is needed.
Lean is pinned to **4.33.1**. After editing, repeat `lake build`.
Keep the fixed `Spec.lean` and environment files unchanged. Submit only
**`Submission.lean`**, not the folder.

Building checks code and proofs, not the official interface, axiom policy, or
performance. No evaluator or Docker is required. For optional correctness and
kernel wall-time checks, follow the [local evaluator guide](../../evaluation/README.md).
A starter is not guaranteed to pass every performance case.
