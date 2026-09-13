# Mertens Function (`mertens`)

## Problem Statement

Given a non-negative integer `n`, compute the Mertens function:

```text
M(n) = μ(1) + μ(2) + ... + μ(n), with M(0) = 0.
```

The Möbius function `μ` is defined as follows:

- `μ(0) = 0` by the specification's convention.
- `μ(1) = 1`.
- `μ(k) = 0` if `k` is divisible by the square of a prime.
- Otherwise `μ(k) = (−1)^r`, where `r` is the number of distinct prime divisors.

Your implementation must agree with the locked
[`mertensSpec`](../../evaluation/problems/mertens/Spec.lean) for every input. That definition
is the inclusive finite sum of Mathlib v4.33.1's official
[`ArithmeticFunction.moebius`](https://leanprover-community.github.io/mathlib4_docs/Mathlib/NumberTheory/ArithmeticFunction/Moebius.html#ArithmeticFunction.moebius).
Mathlib defines the Möbius value from squarefreeness and the number of prime factors in the
[fixed source](https://github.com/leanprover-community/mathlib4/blob/0df444a360eaa60ab8c11dca51a86af692955474/Mathlib/NumberTheory/ArithmeticFunction/Moebius.lean#L48-L52).
The sum includes index zero, whose Möbius value is zero.

## Input

One argument `n : Nat`, the **inclusive** summation bound. The judge calls
`impl n` directly; there is no standard-input parser or input file to implement.

The function must be defined for every natural number, including zero. The
performance-test ranges below do not restrict the correctness theorem's domain.

## Output

Return `M(n)` as an `Int`. Do not print the answer. The result may be negative;
do not take its absolute value, clip it to zero, or reduce it modulo a number.

## Examples

Each row is a separate function call.

| Input `n` | Output `impl n` |
| ---: | ---: |
| 0 | 0 |
| 1 | 1 |
| 2 | 0 |
| 5 | -2 |
| 10 | -1 |
| 25 | -2 |

For `n = 5`, the Möbius values are `1, -1, -1, 0, -1`, whose sum is `-2`.
In particular, `μ(4) = 0` because 4 is divisible by the square of 2.
The empty sum at `n = 0` is zero.

## Constraints and Scoring

The difficulty axis is the summation bound `n`. The official plan has three
groups and six hidden cases in total.

| Group | Inclusive input range | Cases | Target replay limit, each repetition |
| --- | ---: | ---: | ---: |
| M1 | 25–50 | 2 | 30 s |
| M2 | 80–150 | 2 | 60 s |
| M3 | 300–500 | 2 | 120 s |

Each group uses `geometric_range`: two distinct, increasing values with
deterministic 15% seed-derived jitter inward from the endpoints. Unseeded local
plans use the endpoints. Official exact values remain hidden during evaluation.
The current memory limit is **4,096 MiB (4 GiB)**, provisional pending
official-host validation and fixed within a cohort.

An otherwise scoreable submission earns **100 points only if all six cases
pass**. Any failed case gives 0 points and infinite ranking cost; there is no
partial credit. Full-plan passes rank by **target work `T`**: the sum of the
median kernel instruction count for each case's three target replays. Lower is
better; equal costs remain tied. Correctness replay must complete but its cost
is not added to this problem's ranking metric. Infrastructure errors are unscored.

All three target replays must finish within the case's per-repetition limit.
Preparation and correctness checks have separate limits, not a shared group
budget. See the [scoring plan](../problem-scoring.md#mertens),
[configuration](../../evaluation/problems/mertens/config.json), and [evaluation rules](../evaluation.md).

## Submission Requirements

Submit one `Submission.lean` containing these declarations inside
`namespace Submission`:

```text
impl : Nat → Int
impl_correct : ∀ n, impl n = mertensSpec n
```

The [locked bridge](../../evaluation/problems/mertens/Solution.lean) exposes them to the
judge. Prove equality for **all `n`**, not just the examples or hidden cases.
The proof need not use `rfl`, and the algorithm need not evaluate the Möbius
sum in the same way as Mathlib. Separately, the kernel must reduce `impl n` to
the exact integer answer. Use only this problem's supplied pinned Mathlib
closure, total kernel-reducible code, and permitted axioms; see the
[shared requirements](README.md#what-a-submission-must-establish).

## Starter Code and Local Testing

Start from [problems/mertens/Submission.lean](../../problems/mertens/Submission.lean).
It directly sums Mathlib's Möbius function, with a reflexivity proof against `mertensSpec`.
The implementation and proof are complete; use the two TODOs to make your changes.
A starting implementation is not guaranteed to pass every performance case.

Install `elan`, Git, and Python 3.9+, then run from the repository root:

```bash
cd problems/mertens
python3 setup.py
lake build
```

The setup command prepares the dependency versions pinned by this package. Keep
`Spec.lean` and the environment files unchanged; edit and submit only
`Submission.lean`. Building compiles your
definitions and proofs. It does not independently check the official interface or
permitted axioms, benchmark, or score the submission. See the [participant guide](../../problems/mertens/README.md).

For optional kernel evaluation, run from the repository root:

```bash
bash evaluation/setup.sh --problem mertens
python3 evaluation/run.py --problem mertens --submission problems/mertens/Submission.lean
```

This uses the full unseeded public plan with one wall-time repetition, not official
PMU scores. See the [evaluation guide](../../evaluation/README.md).

## Notes

The baseline directly sums `ArithmeticFunction.moebius`. A separate
[factor-list example](../../examples/submissions/mertens/factor-list/Submission.lean)
uses Mathlib's prime-factor lists and proves equality with the same sum.
This is an alternative implementation, not a claim of better performance.
A sieve or shared factor information could reduce repeated work, but any
replacement needs a proof against `mertensSpec`. Intermediate representations
must be tested under kernel replay, not only native execution; no speedup is
implied by the algorithm name alone.
