# Fibonacci (`fib`)

## Problem Statement

Given a non-negative integer `n`, compute the `n`th Fibonacci number:

```text
F(0) = 0
F(1) = 1
F(n + 2) = F(n) + F(n + 1)
```

The result must equal Mathlib's `Nat.fib` for every input.

### Mathlib specification

The fixed [Spec.lean](../../evaluation/problems/fib/Spec.lean) imports
**`Nat.fib : Nat → Nat`** from `Mathlib.Data.Nat.Fib.Basic`.

- Official API: [Nat.fib](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Data/Nat/Fib/Basic.html#Nat.fib)
- Pinned source: [Mathlib v4.33.1](https://github.com/leanprover-community/mathlib4/blob/0df444a360eaa60ab8c11dca51a86af692955474/Mathlib/Data/Nat/Fib/Basic.lean#L59), commit `0df444a360eaa60ab8c11dca51a86af692955474`
- [Evaluation dependency manifest](../../evaluation/problems/fib/lake-manifest.json)

The pinned source, not the changing API documentation, determines the target.

## Input

One argument `n : Nat`, the zero-based Fibonacci index. The judge calls `impl n`
directly; there is no standard input or input file.

## Output

Return the exact `F(n)` as a `Nat`, without printing, truncation, modulus, or
fixed-width overflow.

## Examples

| Input `n` | Output `impl n` |
| ---: | ---: |
| 0 | 0 |
| 1 | 1 |
| 2 | 1 |
| 10 | 55 |
| 20 | 6765 |

## Constraints and Scoring

The difficulty axis is `n`. The official plan contains six hidden cases:

| Group | Inclusive input range | Cases | Target replay limit, each repetition |
| --- | ---: | ---: | ---: |
| F1 | 5,000–10,000 | 2 | 30 s |
| F2 | 20,000–40,000 | 2 | 60 s |
| F3 | 80,000–150,000 | 2 | 120 s |

Each group uses `geometric_range`: two distinct, increasing values with
deterministic 15% seed-derived jitter inward from the endpoints. Unseeded local
plans use the endpoints; official values remain hidden during evaluation.

Memory: **4096 MiB (4 GiB)**. See the [shared scoring rules](README.md#scoring),
[resource limits](README.md#limits), and
[fixed configuration](../../evaluation/problems/fib/config.json).

## Submission Requirements

Inside `namespace Submission`, provide:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = Nat.fib n
```

The proof must cover every `n`; any permitted algorithm and proof may be used.
This problem permits the pinned `Mathlib.Data.Nat.Fib.Basic` import closure,
including `Nat.fastFib` and `Nat.fastFib_eq`, but no imports outside it. Import
the generated, fixed `Spec`; its `fibSpec` is a compatibility abbreviation for
`Nat.fib`. See the [shared requirements](README.md#submission).

## Starter Code and Local Testing

The editable [starter](../../problems/fib/Submission.lean) uses `Nat.fastFib`
with `Nat.fastFib_eq`. The separate [worked example](../../examples/fib/Submission.lean)
implements and proves a fast-doubling algorithm against the same specification.

Install Git, Python 3.9+, and `elan`, then run from the repository root:

```bash
cd problems/fib
python3 setup.py
lake build
```

Setup prepares the pinned dependencies. Edit and submit only `Submission.lean`;
keep `Spec.lean` and the environment files unchanged. See the
[participant guide](../../problems/fib/README.md) and
[optional kernel evaluation](../../evaluation/README.md).
