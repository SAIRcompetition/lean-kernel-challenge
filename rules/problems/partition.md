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

Memory is **4096 MiB (4 GiB), provisional**. Official-host acceptance remains
required. Each target has three repetitions, all of which must finish within
the table's watchdog. Separate build/export, audit, and correctness-replay
budgets follow the [common evaluation rules](../evaluation.md#scoring).

An otherwise scoreable submission earns **100 points only if all six cases pass**;
a failed case gives **0 points and infinite ranking cost**. Infrastructure errors
or incomplete evaluations remain unscored. Among full-plan passes, lower
**target work** wins: the sum of the six target-replay instruction-count medians.
Correctness replay is mandatory but is not added to ranking cost. Groups have
no separate point awards. See the [scoring policy](../problem-scoring.md).

## Submission Requirements

Submit one `Submission.lean`, with these declarations in `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = partitionSpec n
```

The theorem must cover **every natural number**, including zero and inputs
outside the scored ranges. Your algorithm need not follow the spec's recurrence,
and the proof need not use `rfl`. It must remain total and kernel-reducible.
Current rules require core Lean without Mathlib and permit only the standard
axioms listed in [R1–R4](../overview.md#rules). The locked
[challenge](../../evaluation/problems/partition/Challenge.lean) and
[solution bridge](../../evaluation/problems/partition/Solution.lean) fix the interface.

## Starter Code and Local Testing

Start from [problems/partition/Submission.lean](../../problems/partition/Submission.lean).
It uses the existing `partitionSpec` baseline and proves correctness by reflexivity.
The implementation and proof are complete; use the two TODOs to make your changes.
A starting implementation is not guaranteed to pass every performance case.

Install `elan`, then run from the repository root:

```bash
cd problems/partition
lake build
```

No Mathlib or separate setup is needed. Keep the generated `Spec.lean` and environment
files unchanged; edit and submit only `Submission.lean`. Building compiles your
definitions and proofs. It does not independently check the official interface or
permitted axioms, benchmark, or score the submission. See the [participant guide](../../problems/partition/README.md).

For optional kernel evaluation, run from the repository root:

```bash
bash evaluation/setup.sh
python3 evaluation/run.py --problem partition --submission problems/partition/Submission.lean
```

This uses the full unseeded public plan with one wall-time repetition, not official
PMU scores. See the [evaluation guide](../../evaluation/README.md).

## Notes

The baseline recursively enumerates multiplicities without memoization.
A dynamic-programming table or another proved recurrence may avoid repeated
subproblems. Any alternative must preserve the exact result for all inputs;
compiled speed alone does not establish better kernel performance.
