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

The API documentation is a reference, not a version pin. The competition uses
the fixed source above. Prove `∀ n, impl n = Nat.fib n`; you do not have to use
Mathlib's algorithm or beat its runtime by a specified factor.

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
[configuration](../../evaluation/problems/fib/config.json), and [evaluation rules](../evaluation.md).

## Submission Requirements

Submit one `Submission.lean` containing these declarations inside
`namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = Nat.fib n
```

The [locked bridge](../../evaluation/problems/fib/Solution.lean) exposes them to the judge.
Prove equality for **all `n`**, not just the examples or hidden cases. The proof
need not use `rfl`, and the algorithm need not follow the specification's
recurrence. Separately, the kernel must reduce `impl n` to the exact answer.
This problem permits the pinned `Mathlib.Data.Nat.Fib.Basic` module and its
transitive imports supplied by the locked workspace. You may use their
definitions and theorems, including `Nat.fastFib` and `Nat.fastFib_eq`.
Additional packages or Mathlib modules outside that supplied import closure
are not permitted for this problem. Total kernel-reducible code and the permitted-axiom
rules still apply; see the [shared requirements](README.md#what-a-submission-must-establish).

For older judge submissions importing `Spec`, `fibSpec` remains an abbreviation
for `Nat.fib`. The participant starter imports Mathlib directly and uses `Nat.fib`.

## Starter Code and Local Testing

Start from [problems/fib/Submission.lean](../../problems/fib/Submission.lean).
It imports Mathlib directly, uses `Nat.fastFib`, and supplies a complete proof
via `Nat.fastFib_eq`. Concise TODOs mark the implementation and correctness
proof to edit. There are no unfinished proof placeholders.
Using the starting implementation unchanged is permitted.

For comparison, the [baseline](../../examples/submissions/fib/baseline/Submission.lean)
uses `Nat.fib` directly, while the
[fast-doubling example](../../examples/submissions/fib/doubling/Submission.lean)
implements and proves its own algorithm.

Install Git, Python 3.9+, and `elan`. From the repository root:

```bash
cd problems/fib
python3 setup.py
lake build
```

Setup prepares the pinned dependencies on first use; it does not require evaluation
tools or Docker. After edits, repeat `lake build`. Building compiles your definitions
and proofs; it does not independently check the official interface or permitted
axioms, measure kernel performance, or score the submission. A successful build
does not guarantee official acceptance. Submit only `Submission.lean`, not the workspace.

For optional kernel measurements on the same file, return to the repository root:

```bash
bash evaluation/setup.sh --problem fib
python3 evaluation/run.py --problem fib --submission problems/fib/Submission.lean
```

This uses the six-case unseeded public plan with one wall-time repetition, not
official PMU scores. The fixed Spec, interfaces, and scoring configuration stay
in `evaluation/problems/fib/`. See the [participant guide](../../problems/fib/README.md)
and [evaluation guide](../../evaluation/README.md).

## Notes

Mathlib's `Nat.fib` iterates a pair of consecutive Fibonacci numbers.
Mathlib also provides [Nat.fastFib](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Data/Nat/Fib/Basic.html#Nat.fastFib)
and [Nat.fastFib_eq](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Data/Nat/Fib/Basic.html#Nat.fastFib_eq),
which proves it equals `Nat.fib`. You may use this faster implementation;
the correctness target remains `Nat.fib`.
The supplied fast-doubling example keeps its own algorithm and now proves
correctness using Mathlib's doubling identities. Its logarithmic number of
stages is not logarithmic bit-time:
the intermediate integers grow, and the output itself has size proportional
to `n` in bits. Algorithm and representation changes should be measured with
kernel replay, not inferred from native execution time. In particular, Mathlib
has a compiler simplification from `Nat.fib` to `Nat.fastFib`; this changes
compiled execution, not the kernel definition being measured.
