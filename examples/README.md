# Example submissions

Each Stage 1 problem has one complete example in `<problem>/Submission.lean`.
All examples provide an implementation and a universal correctness proof.
They are starting points, not guarantees that every performance case finishes
within its limits.

| Problem | Example algorithm |
| --- | --- |
| [Fibonacci](fib/Submission.lean) | Fast doubling, proved against `Nat.fib` |
| [Integer partitions](partition/Submission.lean) | The existing partition recurrence |
| [Mertens function](mertens/Submission.lean) | Möbius values from Mathlib prime-factor lists |
| [Prime counting](primecount/Submission.lean) | Trial division up to the square root |
| [Matrix permanent](permanent/Submission.lean) | Sparse depth-first traversal with an occupied-column mask |
| [Rule 110](ca-rule110/Submission.lean) | Bit-packed state and evolution |
| [SHA-256 chain](sha256/Submission.lean) | A rolling 16-word message schedule |
| [Polynomial discriminant](polydisc/Submission.lean) | Subresultants with a Bareiss fallback |

## Use an example

Examples are single submission files, not standalone Lean packages. To use one
as your starting point, first back up your work, then place it in the matching
`problems/<id>/` package as `Submission.lean`. Keep the fixed `Spec.lean` and
environment files unchanged; follow the [participant quick start](../README.md#quick-start).

Alternatively, evaluate an example without replacing your code. From the
repository root:

```bash
bash evaluation/setup.sh --problem fib
python3 evaluation/run.py --problem fib --submission examples/fib/Submission.lean
```

Replace `fib` with the selected problem. This optional local evaluation checks
correctness and measures kernel wall time, not official instruction-count rankings.
See [local evaluation](../evaluation/README.md) and the
[problem statements](../rules/problems/README.md).

The public harness checks all eight examples.
