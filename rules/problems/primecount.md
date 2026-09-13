# Prime Counting (`primecount`)

## Problem Statement

Given a non-negative integer `n`, count the prime numbers at most `n`:

```text
π(n) = number of primes p with 2 ≤ p ≤ n.
```

A prime is an integer at least 2 with no divisor other than 1 and itself.
Neither 0 nor 1 is prime. Your implementation must agree with the locked
[`primeCountSpec`](../../evaluation/problems/primecount/Spec.lean) for every input.

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
[configuration](../../evaluation/problems/primecount/config.json), and [evaluation rules](../evaluation.md).

## Submission Requirements

Submit one `Submission.lean` containing these declarations inside
`namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = primeCountSpec n
```

The [locked bridge](../../evaluation/problems/primecount/Solution.lean) exposes them to the
judge. Prove equality for **all `n`**, including zero and inputs outside the
official ranges. The proof need not use `rfl`, and your algorithm need not use
the specification's trial divisions. Separately, the kernel must reduce
`impl n` to the exact answer. The current rules require core Lean without
Mathlib, total kernel-reducible code, and permitted axioms only; see the
[shared requirements](README.md#what-a-submission-must-establish).

## Starter Code and Local Testing

Start from [problems/primecount/Submission.lean](../../problems/primecount/Submission.lean).
It uses `primeCountSpec` directly with a reflexivity proof. The
[square-root trial-division example](../../examples/submissions/primecount/sqrt/Submission.lean)
shows another proved implementation.
The implementation and proof are complete; use the two TODOs to make your changes.
A starting implementation is not guaranteed to pass every performance case.

Install `elan`, then run from the repository root:

```bash
cd problems/primecount
lake build
```

No Mathlib or separate setup is needed. Keep the generated `Spec.lean` and environment
files unchanged; edit and submit only `Submission.lean`. Building compiles your
definitions and proofs. It does not independently check the official interface or
permitted axioms, benchmark, or score the submission. See the [participant guide](../../problems/primecount/README.md).

For optional kernel evaluation, run from the repository root:

```bash
bash evaluation/setup.sh --problem primecount
python3 evaluation/run.py --problem primecount --submission problems/primecount/Submission.lean
```

This uses the full unseeded public plan with one wall-time repetition, not official
PMU scores. See the [evaluation guide](../../evaluation/README.md).

## Notes

The baseline filters all integers from 0 through `n`, testing possible divisors
of each candidate by trial division. The square-root example stops when
`d × d > p` and proves the two primality predicates equivalent. Reusing prime
information or changing the counting representation are possible alternatives,
but native performance does not predict kernel-reduction performance. Any
replacement must preserve the inclusive endpoint and the cases 0 and 1.
