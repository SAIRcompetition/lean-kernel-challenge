# Prime Counting (`primecount`)

## Problem Statement

Given a non-negative integer `n`, count the prime numbers at most `n`:

```text
π(n) = number of primes p with 2 ≤ p ≤ n.
```

A prime is an integer at least 2 with no divisor other than 1 and itself.
Neither 0 nor 1 is prime. Your implementation must agree with the locked
[`primeCountSpec`](../../problems/primecount/Spec.lean) for every input.

## Input

One argument `n : Nat`, an **inclusive** upper bound. The judge calls `impl n`
directly; there is no standard-input parser or input file to implement.

The function must be defined for every natural number, including zero. The
performance-test ranges below do not restrict the correctness theorem's domain.

## Output

Return `π(n)` as a `Nat`. Do not print the answer. Return the exact count, not
a list of primes, an approximation, or a Boolean primality result.

## Examples

Each row is a separate function call.

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
budget. See the [scoring plan](../problem-scoring.md#primecount),
[configuration](../../problems/primecount/config.json), and [evaluation rules](../evaluation.md).

## Submission Requirements

Submit one `Submission.lean` containing these declarations inside
`namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = primeCountSpec n
```

The [locked bridge](../../problems/primecount/Solution.lean) exposes them to the
judge. Prove equality for **all `n`**, including zero and inputs outside the
official ranges. The proof need not use `rfl`, and your algorithm need not use
the specification's trial divisions. Separately, the kernel must reduce
`impl n` to the exact answer. The current rules require core Lean without
Mathlib, total kernel-reducible code, and permitted axioms only; see the
[shared requirements](README.md#what-a-submission-must-establish).

## Starter Code and Local Testing

Start from the [completed baseline](../../examples/submissions/primecount/baseline/Submission.lean),
which uses `primeCountSpec` directly, or inspect the
[square-root trial-division example](../../examples/submissions/primecount/sqrt/Submission.lean).
The problem workspace's `Submission.lean` is a template with placeholders.

From the repository root, after following the
[setup instructions](README.md#quick-test-before-using-the-judge), run:

```bash
python3 scripts/quick_test.py --problem primecount
python3 scripts/quick_test.py --problem primecount --submission examples/submissions/primecount/sqrt/Submission.lean
python3 scripts/quick_test.py --problem primecount --submission path/to/Submission.lean
```

The demo builds the implementation and universal proof, then compares compiled
outputs on public inputs `1`, `10`, and `50`. It is not a formal submission or
official evaluation: it performs no official axiom audit, hidden-case evaluation,
PMU measurement, or scoring. Passing does not establish official acceptance or
kernel performance. For local kernel measurements, use the
[shared testing guide](README.md#quick-test-before-using-the-judge).

## Notes

The baseline filters all integers from 0 through `n`, testing possible divisors
of each candidate by trial division. The square-root example stops when
`d × d > p` and proves the two primality predicates equivalent. Reusing prime
information or changing the counting representation are possible alternatives,
but native performance does not predict kernel-reduction performance. Any
replacement must preserve the inclusive endpoint and the cases 0 and 1.
