# Mertens Function (`mertens`)

## Problem Statement

Given a non-negative integer `n`, compute the Mertens function:

```text
M(n) = μ(1) + μ(2) + ... + μ(n), with M(0) = 0.
```

Here `μ(0) = 0`, `μ(1) = 1`, and `μ(k) = 0` when a prime square divides
`k`; otherwise `μ(k) = (−1)^r`, where `r` is the number of distinct prime
divisors.

The fixed [`mertensSpec`](../../evaluation/problems/mertens/Spec.lean) is the
inclusive sum through `n` of Mathlib v4.33.1's
[`ArithmeticFunction.moebius`](https://leanprover-community.github.io/mathlib4_docs/Mathlib/NumberTheory/ArithmeticFunction/Moebius.html#ArithmeticFunction.moebius).
Its definition from squarefreeness and prime factors is in the
[pinned source](https://github.com/leanprover-community/mathlib4/blob/0df444a360eaa60ab8c11dca51a86af692955474/Mathlib/NumberTheory/ArithmeticFunction/Moebius.lean#L48-L52).
The sum includes index zero, whose value is zero.

## Input

One argument `n : Nat`, the inclusive summation bound. The judge calls `impl n`
directly; there is no standard input or input file.

## Output

Return the exact `M(n)` as an `Int`, without printing, absolute value,
clipping, or modulus. The result may be negative.

## Examples

| Input `n` | Output `impl n` |
| ---: | ---: |
| 0 | 0 |
| 1 | 1 |
| 2 | 0 |
| 5 | -2 |
| 10 | -1 |
| 25 | -2 |

For `n = 5`, the values `1, -1, -1, 0, -1` sum to `-2`; `μ(4) = 0`
because `2²` divides 4.

## Constraints and Scoring

The difficulty axis is `n`. The official plan contains six hidden cases:

| Group | Inclusive input range | Cases | Target replay limit, each repetition |
| --- | ---: | ---: | ---: |
| M1 | 25–50 | 2 | 30 s |
| M2 | 80–150 | 2 | 60 s |
| M3 | 300–500 | 2 | 120 s |

Each group uses `geometric_range`: two distinct, increasing values with
deterministic 15% seed-derived jitter inward from the endpoints. Unseeded local
plans use the endpoints; official values remain hidden during evaluation.

Memory: **4096 MiB (4 GiB)**. See the [shared scoring rules](README.md#scoring),
[resource limits](README.md#limits), and
[fixed configuration](../../evaluation/problems/mertens/config.json).

## Submission Requirements

Inside `namespace Submission`, provide:

```text
impl : Nat → Int
impl_correct : ∀ n, impl n = mertensSpec n
```

Prove equality for every `n`; the computation may differ from Mathlib's. Use
only this problem's pinned Mathlib import closure and follow the
[shared requirements](README.md#submission).

## Starter Code and Local Testing

The editable [starter](../../problems/mertens/Submission.lean) directly sums
Mathlib's Möbius function. The separate
[worked example](../../examples/mertens/Submission.lean) computes the same
values from prime-factor lists and proves equality with `mertensSpec`.

Install `elan`, Git, and Python 3.9+, then run from the repository root:

```bash
cd problems/mertens
python3 setup.py
lake build
```

Setup prepares the pinned dependencies. Edit and submit only `Submission.lean`;
keep `Spec.lean` and the environment files unchanged. See the
[participant guide](../../problems/mertens/README.md) and
[optional kernel evaluation](../../evaluation/README.md).
