# Fibonacci (`fib`)

## Problem Statement

Given a non-negative integer `n`, compute the `n`th Fibonacci number. The sequence
is defined by:

```text
F(0) = 0
F(1) = 1
F(n + 2) = F(n) + F(n + 1)
```

Your implementation must compute the exact value and agree with the locked
[`fibSpec`](../../problems/fib/Spec.lean) for every input.

## Input

One argument `n : Nat`, the Fibonacci index. The judge calls `impl n` directly;
there is no standard-input parser or input file to implement.

The function must be defined for every natural number, including zero. The
performance-test ranges below do not restrict the correctness theorem's domain.

## Output

Return `F(n)` as a `Nat`. Do not print the answer. There is no modulus,
truncation, or fixed-width overflow.

## Examples

Each row is a separate function call.

| Input `n` | Output `impl n` |
| ---: | ---: |
| 0 | 0 |
| 1 | 1 |
| 2 | 1 |
| 10 | 55 |
| 20 | 6765 |

The sequence begins `0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55`; its element at
index 10 is 55. In particular, indexing starts at zero, not one.

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
budget. See the [scoring plan](../problem-scoring.md#fib),
[configuration](../../problems/fib/config.json), and [evaluation rules](../evaluation.md).

## Submission Requirements

Submit one `Submission.lean` containing these declarations inside
`namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = fibSpec n
```

The [locked bridge](../../problems/fib/Solution.lean) exposes them to the judge.
Prove equality for **all `n`**, not just the examples or hidden cases. The proof
need not use `rfl`, and the algorithm need not follow the specification's
recurrence. Separately, the kernel must reduce `impl n` to the exact answer.
The current rules require core Lean without Mathlib, total kernel-reducible
code, and permitted axioms only; see the [shared requirements](README.md#what-a-submission-must-establish).

## Starter Code and Local Testing

Start from the [completed baseline](../../examples/submissions/fib/baseline/Submission.lean),
which uses `fibSpec` directly, or inspect the
[fast-doubling example](../../examples/submissions/fib/doubling/Submission.lean).
The problem workspace's `Submission.lean` is a template with placeholders.

From the repository root, after following the
[setup instructions](README.md#quick-test-before-using-the-judge), run:

```bash
python3 scripts/quick_test.py --problem fib
python3 scripts/quick_test.py --problem fib --submission examples/submissions/fib/doubling/Submission.lean
python3 scripts/quick_test.py --problem fib --submission path/to/Submission.lean
```

The demo builds the implementation and universal proof, then compares compiled
outputs on public inputs `0`, `10`, and `20`. It is not a formal submission or
official evaluation: it performs no official axiom audit, hidden-case evaluation,
PMU measurement, or scoring. Passing does not establish official acceptance or
kernel performance. For local kernel measurements, use the
[shared testing guide](README.md#quick-test-before-using-the-judge).

## Notes

The baseline recurrence is elaborated using course-of-values recursion; do not
infer exponential kernel cost from its two source-level recursive calls.
The fast-doubling example halves the index and proves the corresponding
identities. Its logarithmic number of stages is not logarithmic bit-time:
the intermediate integers grow, and the output itself has size proportional
to `n` in bits. Algorithm and representation changes should be measured with
kernel replay, not inferred from native execution time.
