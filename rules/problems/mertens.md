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

## Output

Return `M(n)` as an `Int`. Do not print the answer. The result may be negative;
do not take its absolute value, clip it to zero, or reduce it modulo a number.

## Examples

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

Memory: **4096 MiB (4 GiB)**. The [shared scoring rules](README.md#scoring)
and [resource limits](README.md#limits) apply.
The [fixed configuration](../../evaluation/problems/mertens/config.json) records this plan.

## Submission Requirements

Submit one `Submission.lean` containing these declarations inside
`namespace Submission`:

```text
impl : Nat → Int
impl_correct : ∀ n, impl n = mertensSpec n
```

Prove equality for **all `n`**; you may compute the sum differently from Mathlib.
Use only this problem's supplied pinned Mathlib closure and follow the
[shared requirements](README.md#submission).

## Starter Code and Local Testing

Start from the editable participant starter at
[problems/mertens/Submission.lean](../../problems/mertens/Submission.lean).
It directly sums Mathlib's Möbius function, with a reflexivity proof against `mertensSpec`.
The two TODOs mark the implementation and proof to edit.

Install `elan`, Git, and Python 3.9+, then run from the repository root:

```bash
cd problems/mertens
python3 setup.py
lake build
```

Setup prepares pinned dependencies. Edit and submit only `Submission.lean`;
keep `Spec.lean` and the environment files unchanged. `lake build` compiles the
code and proof; it is not an acceptance check or performance measurement.
See the [participant guide](../../problems/mertens/README.md) and
[optional kernel evaluation](../../evaluation/README.md).

## Notes

The participant starter directly sums `ArithmeticFunction.moebius`. The separate
[worked example](../../examples/mertens/Submission.lean) uses Mathlib's
prime-factor lists and proves equality with the same sum.
This is an alternative implementation, not a claim of better performance.
A sieve or shared factor information could reduce repeated work, but any
replacement needs a proof against `mertensSpec`. Intermediate representations
must be tested under kernel replay, not only native execution; no speedup is
implied by the algorithm name alone.
