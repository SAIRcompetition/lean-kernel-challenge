# Prime Counting (`primecount`)

## Problem Statement

Given a non-negative integer `n`, count the prime numbers at most `n`:

```text
π(n) = number of primes p with 2 ≤ p ≤ n.
```

A prime is an integer at least 2 with no divisor other than 1 and itself.
Neither 0 nor 1 is prime. Your implementation must agree with the locked
[`primeCountSpec`](../../evaluation/problems/primecount/Spec.lean) for every input.
That target is backed directly by Mathlib v4.33.1's official
[`Nat.primeCounting`](https://leanprover-community.github.io/mathlib4_docs/Mathlib/NumberTheory/PrimeCounting.html#Nat.primeCounting),
which counts primes less than or equal to its argument; see the
[fixed source](https://github.com/leanprover-community/mathlib4/blob/0df444a360eaa60ab8c11dca51a86af692955474/Mathlib/NumberTheory/PrimeCounting.lean#L47-L58).

## Input

One argument `n : Nat`, an **inclusive** upper bound. The judge calls `impl n`
directly; there is no standard-input parser or input file to implement.

## Output

Return `π(n)` as a `Nat`. Do not print the answer. Return the exact count, not
a list of primes, an approximation, or a Boolean primality result.

## Examples

| Input `n` | Output `impl n` |
| ---: | ---: |
| 0 | 0 |
| 1 | 0 |
| 2 | 1 |
| 10 | 4 |
| 50 | 15 |

For `n = 10`, the primes counted are `2`, `3`, `5`, and `7`, so the answer is 4.
For `n = 2`, the bound itself is prime and is included, so the answer is 1.

## Constraints and Scoring

The difficulty axis is the inclusive bound `n`. The official plan has three
groups and six hidden cases in total.

| Group | Inclusive input range | Cases | Target replay limit, each repetition |
| --- | ---: | ---: | ---: |
| Q1 | 50–100 | 2 | 30 s |
| Q2 | 150–300 | 2 | 60 s |
| Q3 | 600–1,000 | 2 | 120 s |

Each group uses `geometric_range`: two distinct, increasing values with
deterministic 15% seed-derived jitter inward from the endpoints. Unseeded local
plans use the endpoints. Official exact values remain hidden during evaluation.

Memory: **4096 MiB (4 GiB)**. The [shared scoring rules](README.md#scoring)
and [resource limits](README.md#limits) apply.
The [fixed configuration](../../evaluation/problems/primecount/config.json) records this plan.

## Submission Requirements

Submit one `Submission.lean` containing these declarations inside
`namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = primeCountSpec n
```

The [locked bridge](../../evaluation/problems/primecount/Solution.lean) fixes the interface.
Prove equality for **all `n`**, including zero and inputs outside the test ranges.
Your algorithm may differ from Mathlib's. Use only this problem's supplied pinned
Mathlib closure and follow the
[shared requirements](README.md#submission).

## Starter Code and Local Testing

Start from [problems/primecount/Submission.lean](../../problems/primecount/Submission.lean).
It includes a complete baseline using Mathlib's `Nat.minFac`, with a proof against
`Nat.primeCounting`. The
[square-root trial-division example](../../examples/submissions/primecount/sqrt/Submission.lean)
shows another proved implementation.
The two TODOs mark the implementation and proof to edit.

Install `elan`, Git, and Python 3.9+, then run from the repository root:

```bash
cd problems/primecount
python3 setup.py
lake build
```

Setup prepares pinned dependencies. Edit and submit only `Submission.lean`;
keep `Spec.lean` and the environment files unchanged. `lake build` compiles the
code and proof; it is not an acceptance check or performance measurement.
See the [participant guide](../../problems/primecount/README.md) and
[optional kernel evaluation](../../evaluation/README.md).

## Notes

The baseline tests each integer using Mathlib's least-prime-factor function
`Nat.minFac`. The [direct Mathlib example](../../examples/submissions/primecount/mathlib-direct/Submission.lean)
uses `Nat.primeCounting` itself; it is correct but can time out on larger cases.
The square-root example stops when `d × d > p` and proves its alternative predicate
correct. Reusing prime information or changing the counting representation are possible alternatives,
but native performance does not predict kernel-reduction performance. Any
replacement must preserve the inclusive endpoint and the cases 0 and 1.
