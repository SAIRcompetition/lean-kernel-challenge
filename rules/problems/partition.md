# Integer partitions (`partition`)

## Problem Statement

Given a non-negative integer `n`, count its expressions as a sum of positive
integers, ignoring order and allowing repeated parts. Thus `3 + 1` and `1 + 3`
are the same partition, and the empty sum is the unique partition of zero.

Your total Lean function must equal the locked
[specification](../../evaluation/problems/partition/Spec.lean), which defines
`partAux k n` as the number of partitions of `n` with parts at most `k`:

```text
partAux 0 0       = 1
partAux 0 (n + 1) = 0
partAux (k + 1) n = sum over j = 0, ..., floor(n / (k + 1))
                     of partAux k (n - j * (k + 1))
partitionSpec n   = partAux n n
```

Here `j` is the multiplicity of the largest allowed part; its bound keeps every
subtraction within `n`.

## Input

The Lean function argument `n : Nat`. It is a direct input, with no packing or
seed, and is **not** standard-input text.

## Output

Return the exact count as a `Nat`, without modular reduction. In particular,
`impl 0` must return 1.

## Examples

| Input `n` | Output |
| ---: | ---: |
| 0 | 1 |
| 1 | 1 |
| 4 | 5 |
| 5 | 7 |
| 10 | 42 |

For `n = 4`, the five partitions are:

```text
4
3 + 1
2 + 2
2 + 1 + 1
1 + 1 + 1 + 1
```

The zero case counts the empty sum. These examples are not the hidden plan.

## Constraints and Scoring

The [configuration](../../evaluation/problems/partition/config.json) uses three
groups and **six hidden cases**:

| Group | Inclusive `n` range | Cases | Target watchdog per repetition |
| --- | ---: | ---: | ---: |
| P1 | 14–18 | 2 | 30 s |
| P2 | 22–26 | 2 | 60 s |
| P3 | 32–36 | 2 | 120 s |

Each range uses 15% deterministic seed-derived inward jitter to produce two
distinct, ordered integers. Unseeded local runs use the endpoints. Every
submission in a cohort receives the same hidden plan.

Memory: **4096 MiB (4 GiB)**. The [shared scoring rules](README.md#scoring)
and [resource limits](README.md#limits) apply.

## Submission Requirements

Submit one `Submission.lean`, with these declarations in `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = partitionSpec n
```

The theorem covers **every natural number**, including zero and values outside
the test ranges. This core-Lean problem has no Mathlib dependency; the
[shared requirements](README.md#submission) apply.

## Starter Code and Local Testing

Start from the editable participant starter at
[problems/partition/Submission.lean](../../problems/partition/Submission.lean).
The starter and [worked example](../../examples/partition/Submission.lean) use
`partitionSpec` with a reflexive proof.

Install `elan`, then run from the repository root:

```bash
cd problems/partition
lake build
```

No separate setup is needed. Edit and submit only `Submission.lean`; keep the
other files unchanged. `lake build` checks compilation, not acceptance or
performance.
See the [participant guide](../../problems/partition/README.md) and
[optional kernel evaluation](../../evaluation/README.md).
