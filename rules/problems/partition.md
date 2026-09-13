# Integer partitions (`partition`)

## Problem Statement

Given a non-negative integer `n`, count the ways to write it as a sum of positive
integers, ignoring the order of the summands. Repeated parts are allowed:
`3 + 1` and `1 + 3` are the same partition. The empty sum is the unique
partition of zero.

Implement a total Lean function that computes this count, and prove that it
agrees with the locked [specification](../../evaluation/problems/partition/Spec.lean).
The specification uses `partAux k n`, the number of partitions of `n` whose
parts are at most `k`:

```text
partAux 0 0       = 1
partAux 0 (n + 1) = 0
partAux (k + 1) n = sum over j = 0, ..., floor(n / (k + 1))
                     of partAux k (n - j * (k + 1))
partitionSpec n   = partAux n n
```

Here `j` is the multiplicity of the largest allowed part. Its bound ensures
that the subtraction never removes more than `n`.

Mathlib v4.33.1 separately represents an integer partition as
[`Nat.Partition n`](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Combinatorics/Enumerative/Partition/Basic.html#Nat.Partition)
and supplies a finite instance, so `Fintype.card (Nat.Partition n)` is the
standard library count; see the fixed definitions of
[`Nat.Partition`](https://github.com/leanprover-community/mathlib4/blob/0df444a360eaa60ab8c11dca51a86af692955474/Mathlib/Combinatorics/Enumerative/Partition/Basic.lean#L55-L63)
and its [`Fintype`](https://github.com/leanprover-community/mathlib4/blob/0df444a360eaa60ab8c11dca51a86af692955474/Mathlib/Combinatorics/Enumerative/Partition/Basic.lean#L203-L207).
That cardinality is a possible future specification, not the current target:
no theorem proving `partitionSpec n = Fintype.card (Nat.Partition n)` for all
`n` is supplied. This problem remains core-Lean and repository-specified.

## Input

The argument `n : Nat` of your Lean function. It is the integer to partition;
there is no packed encoding or seed. This is a function interface, **not**
a standard-input text format.

## Output

Return the exact partition count as a `Nat`. Do not reduce it modulo another
number. In particular, `impl 0` must return 1.

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

The zero case counts the empty sum. These examples are kernel-checkable with
`rfl` against the spec; they are not the hidden evaluation plan.

## Constraints and Scoring

The current [configuration](../../evaluation/problems/partition/config.json) uses three
groups and **six hidden cases**:

| Group | Inclusive `n` range | Cases | Target watchdog per repetition |
| --- | ---: | ---: | ---: |
| P1 | 14–18 | 2 | 30 s |
| P2 | 22–26 | 2 | 60 s |
| P3 | 32–36 | 2 | 120 s |

Each range uses the geometric-range sampler with 15% deterministic seed-derived
jitter: the two endpoints are jittered inward to produce distinct, ordered
integers. Unseeded local runs use the endpoints. All submissions in a cohort
receive the same hidden plan.

Memory: **4096 MiB (4 GiB)**. The [shared scoring rules](README.md#scoring)
and [resource limits](README.md#limits) apply.

## Submission Requirements

Submit one `Submission.lean`, with these declarations in `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = partitionSpec n
```

The theorem covers **every natural number**, including zero and inputs outside
the test ranges. Any algorithm satisfying the
[shared requirements](README.md#submission) is permitted;
this problem uses core Lean without Mathlib. The locked
[challenge](../../evaluation/problems/partition/Challenge.lean) and
[solution bridge](../../evaluation/problems/partition/Solution.lean) fix the interface.

## Starter Code and Local Testing

Start from [problems/partition/Submission.lean](../../problems/partition/Submission.lean).
It uses the existing `partitionSpec` baseline and proves correctness by reflexivity.
The two TODOs mark the implementation and proof to edit.

Install `elan`, then run from the repository root:

```bash
cd problems/partition
lake build
```

No separate setup is needed. Edit and submit only `Submission.lean`; keep
`Spec.lean` and the environment files unchanged. `lake build` compiles the code
and proof; it is not an acceptance check or performance measurement.
See the [participant guide](../../problems/partition/README.md) and
[optional kernel evaluation](../../evaluation/README.md).

## Notes

The baseline recursively enumerates multiplicities without memoization.
A dynamic-programming table or another proved recurrence may avoid repeated
subproblems. Any alternative must preserve the exact result for all inputs;
compiled speed alone does not establish better kernel performance.
