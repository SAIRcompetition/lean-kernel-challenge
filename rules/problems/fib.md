# Fibonacci (`fib`)

## Problem Statement

Given a non-negative integer `n`, compute the `n`th Fibonacci number. The sequence
is defined by:

```text
F(0) = 0
F(1) = 1
F(n + 2) = F(n) + F(n + 1)
```

Your implementation must compute the exact value and equal Mathlib's official
`Nat.fib` for every input.

### Mathlib specification

The correctness target is **`Nat.fib : Nat → Nat`**, defined in
`Mathlib.Data.Nat.Fib.Basic`. The locked [Spec.lean](../../evaluation/problems/fib/Spec.lean)
imports this definition directly; it does not provide a separate Fibonacci algorithm.

- Official API documentation: [Nat.fib](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Data/Nat/Fib/Basic.html#Nat.fib).
- Exact competition version: [Mathlib v4.33.1 source](https://github.com/leanprover-community/mathlib4/blob/0df444a360eaa60ab8c11dca51a86af692955474/Mathlib/Data/Nat/Fib/Basic.lean#L59),
  pinned to commit `0df444a360eaa60ab8c11dca51a86af692955474` in the
  [evaluation dependency manifest](../../evaluation/problems/fib/lake-manifest.json).

The fixed source, not the changing API documentation, determines the version.

## Input

One argument `n : Nat`, the Fibonacci index. The judge calls `impl n` directly;
there is no standard-input parser or input file to implement.

## Output

Return `F(n)` as a `Nat`. Do not print the answer. There is no modulus,
truncation, or fixed-width overflow.

## Examples

| Input `n` | Output `impl n` |
| ---: | ---: |
| 0 | 0 |
| 1 | 1 |
| 2 | 1 |
| 10 | 55 |
| 20 | 6765 |

Indexing starts at zero.

## Constraints and Scoring

The difficulty axis is the index `n`. The official plan has three groups and
six hidden cases in total.

| Group | Inclusive input range | Cases | Target replay limit, each repetition |
| --- | ---: | ---: | ---: |
| F1 | 5,000–10,000 | 2 | 30 s |
| F2 | 20,000–40,000 | 2 | 60 s |
| F3 | 80,000–150,000 | 2 | 120 s |

Each group uses `geometric_range`: two distinct, increasing values with
deterministic 15% seed-derived jitter inward from the endpoints. Unseeded local
plans use the endpoints. Official exact values remain hidden during evaluation.

Memory: **4096 MiB (4 GiB)**. The [shared scoring rules](README.md#scoring)
and [resource limits](README.md#limits) apply.
The [fixed configuration](../../evaluation/problems/fib/config.json) records this plan.

## Submission Requirements

Submit one `Submission.lean` containing these declarations inside
`namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = Nat.fib n
```

The [locked bridge](../../evaluation/problems/fib/Solution.lean) fixes the interface.
Prove equality for **all `n`**, not just the test cases; any permitted algorithm
and proof may be used.
This problem permits the pinned `Mathlib.Data.Nat.Fib.Basic` module and its
transitive imports supplied by the locked workspace. You may use their
definitions and theorems, including `Nat.fastFib` and `Nat.fastFib_eq`.
Imports outside that closure are not permitted. See the
[shared requirements](README.md#submission).

The participant package contains a generated copy of the locked `Spec.lean`.
Import `Spec` in `Submission.lean` and keep the Spec file unchanged. It imports
Mathlib's `Nat.fib`; `fibSpec` is only a compatibility abbreviation for the same function.

## Starter Code and Local Testing

Start from the editable participant starter at
[problems/fib/Submission.lean](../../problems/fib/Submission.lean).
It imports `Spec`, uses `Nat.fastFib`, and supplies a complete proof
via `Nat.fastFib_eq`. The two TODOs mark the implementation and proof to edit.

The separate [worked example](../../examples/fib/Submission.lean) implements
fast doubling and proves its own algorithm against the same fixed specification.

Install Git, Python 3.9+, and `elan`. From the repository root:

```bash
cd problems/fib
python3 setup.py
lake build
```

Setup prepares pinned dependencies. Edit and submit only `Submission.lean`;
keep `Spec.lean` and the environment files unchanged. `lake build` compiles the
code and proof; it is not an acceptance check or performance measurement.
See the [participant guide](../../problems/fib/README.md) and
[optional kernel evaluation](../../evaluation/README.md).

## Notes

Mathlib's `Nat.fib` iterates a pair of consecutive Fibonacci numbers.
Mathlib also provides [Nat.fastFib](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Data/Nat/Fib/Basic.html#Nat.fastFib)
and [Nat.fastFib_eq](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Data/Nat/Fib/Basic.html#Nat.fastFib_eq),
which proves it equals `Nat.fib`. You may use this faster implementation;
the correctness target remains `Nat.fib`.
The public fast-doubling example keeps its own algorithm and proves
correctness using Mathlib's doubling identities. Its logarithmic number of
stages is not logarithmic bit-time:
the intermediate integers grow, and the output itself has size proportional
to `n` in bits. Algorithm and representation changes should be measured with
kernel replay, not inferred from native execution time. In particular, Mathlib
has a compiler simplification from `Nat.fib` to `Nat.fastFib`; this changes
compiled execution, not the kernel definition being measured.
