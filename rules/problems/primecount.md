# Prime Counting (`primecount`)

## Problem Statement

Given a non-negative integer `n`, compute

```text
π(n) = number of primes p with 2 ≤ p ≤ n.
```

A prime is at least 2 and has no divisors other than 1 and itself. Thus neither
0 nor 1 is prime. The fixed
[`primeCountSpec`](../../evaluation/problems/primecount/Spec.lean) is Mathlib
v4.33.1's [`Nat.primeCounting`](https://leanprover-community.github.io/mathlib4_docs/Mathlib/NumberTheory/PrimeCounting.html#Nat.primeCounting),
which counts primes at most its argument; see the
[pinned source](https://github.com/leanprover-community/mathlib4/blob/0df444a360eaa60ab8c11dca51a86af692955474/Mathlib/NumberTheory/PrimeCounting.lean#L47-L58).

## Input

One argument `n : Nat`, the inclusive upper bound. The judge calls `impl n`
directly; there is no standard input or input file.

## Output

Return the exact count `π(n)` as a `Nat`, without printing. Do not return a list,
approximation, or Boolean primality result.

## Examples

| Input `n` | Output `impl n` |
| ---: | ---: |
| 0 | 0 |
| 1 | 0 |
| 2 | 1 |
| 10 | 4 |
| 50 | 15 |

For `n = 10`, the counted primes are `2`, `3`, `5`, and `7`. Because the bound
is inclusive, `π(2) = 1`.

## Constraints and Scoring

The difficulty axis is `n`. The official plan contains six hidden cases:

| Group | Inclusive input range | Cases | Target replay limit, each repetition |
| --- | ---: | ---: | ---: |
| Q1 | 50–100 | 2 | 30 s |
| Q2 | 150–300 | 2 | 60 s |
| Q3 | 600–1,000 | 2 | 120 s |

Each group uses `geometric_range`: two distinct, increasing values with
deterministic 15% seed-derived jitter inward from the endpoints. Unseeded local
plans use the endpoints; official values remain hidden during evaluation.

Memory: **4096 MiB (4 GiB)**. See the [shared scoring rules](README.md#scoring),
[resource limits](README.md#limits), and
[fixed configuration](../../evaluation/problems/primecount/config.json).

## Submission Requirements

Inside `namespace Submission`, provide:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = primeCountSpec n
```

Prove equality for every `n`, including zero and inputs outside the test ranges.
The algorithm may differ from Mathlib's. Use only this problem's pinned Mathlib
import closure and follow the [shared requirements](README.md#submission).

## Starter Code and Local Testing

The editable [starter](../../problems/primecount/Submission.lean) counts using
Mathlib's `Nat.minFac`. The separate
[worked example](../../examples/primecount/Submission.lean) uses proved
square-root trial division. Both target `Nat.primeCounting`.

Install `elan`, Git, and Python 3.9+, then run from the repository root:

```bash
cd problems/primecount
python3 setup.py
lake build
```

Setup prepares the pinned dependencies. Edit and submit only `Submission.lean`;
keep `Spec.lean` and the environment files unchanged. See the
[participant guide](../../problems/primecount/README.md) and
[optional kernel evaluation](../../evaluation/README.md).
