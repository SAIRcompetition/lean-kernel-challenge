# Example submissions

Each problem has one complete implementation and universal proof in
`<problem>/Submission.lean`. Examples may exceed performance limits.

| Problem | Example algorithm |
| --- | --- |
| [Fibonacci](fib/Submission.lean) | Fast doubling, proved against `Nat.fib` |
| [Integer partitions](partition/Submission.lean) | The existing partition recurrence |
| [Mertens function](mertens/Submission.lean) | Möbius values from Mathlib prime-factor lists |
| [Prime counting](primecount/Submission.lean) | Trial division up to the square root |
| [Matrix permanent](permanent/Submission.lean) | Sparse depth-first traversal with an occupied-column mask |
| [Rule 110](ca-rule110/Submission.lean) | Bit-packed state and evolution |
| [SHA-256](sha256/Submission.lean) | A rolling 16-word message schedule |
| [Polynomial discriminant](polydisc/Submission.lean) | Subresultants with a Bareiss fallback |

## Use an example

Examples are single files, not standalone Lean packages. Back up your work,
then copy an example to `problems/<id>/Submission.lean`. Keep `Spec.lean` and
environment files unchanged and follow the [quick start](../README.md#quick-start).

Or evaluate it without replacing your code, from the repository root:

```bash
bash evaluation/setup.sh --problem fib
python3 evaluation/run.py --problem fib --submission examples/fib/Submission.lean
```

Replace `fib` with your problem ID. This checks correctness and kernel wall time,
not official scores. See [local evaluation](../evaluation/README.md) and
[problem statements](../rules/problems/README.md).
