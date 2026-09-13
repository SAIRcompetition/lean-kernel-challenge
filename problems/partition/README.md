# Integer partitions — participant workspace

Edit only `Submission.lean`: implement your algorithm and prove
`∀ n, impl n = partitionSpec n`. The starting implementation and proof already work.
See the [problem statement](../../rules/problems/partition.md) for the input, output,
and scoring rules.

## Build

Install [elan](https://github.com/leanprover/elan), then run from the repository root:

```bash
cd problems/partition
lake build
```

The pinned Lean 4.33.1 toolchain is downloaded on first use if needed. This
problem uses core Lean, not Mathlib; no separate setup command is required.
Keep `Spec.lean` and the environment files unchanged. They are generated from
the fixed [evaluation workspace](../../evaluation/problems/partition/).

Building compiles your definitions and proofs. It does not independently check
the official interface or permitted axioms, measure kernel performance, or award
a score. Submit only **`Submission.lean`**, not this folder.

## Optional kernel evaluation

From the repository root:

```bash
bash evaluation/setup.sh --problem partition
python3 evaluation/run.py --problem partition --submission problems/partition/Submission.lean
```

This separate workflow uses the full unseeded public plan and local wall time,
not official PMU scores. See the [evaluation guide](../../evaluation/README.md).
