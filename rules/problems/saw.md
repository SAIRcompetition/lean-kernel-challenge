# Self-avoiding walks with seeded obstacles (`saw`)

## Problem Statement

Count length-`L` self-avoiding walks from the origin of the square lattice,
avoiding a deterministically generated obstacle field.

A walk is an ordered sequence `p₀, p₁, ..., pL` of integer-coordinate positions,
where `p₀ = (0, 0)`. Each step adds one of `(1, 0)`, `(-1, 0)`, `(0, 1)`,
or `(0, -1)`. Every position must be distinct and unblocked. The origin is
already visited, so a walk cannot return to it.

Length counts steps: a length-`L` walk contains `L + 1` positions. There is
no prescribed endpoint; count all valid endings. Distinct rooted, ordered walks
count separately, without identifying rotations, reflections, or reversals.
The obstacle field need not have any of those symmetries.

## Input

The argument `n : Nat` encodes the length and a 32-bit seed:

```text
n      = (length << 32) | seed
length = n >>> 32
seed   = n &&& 0xffffffff
```

Use `0 ≤ seed < 2^32` when packing. This is a Lean function parameter, **not**
standard input. It selects a seeded instance, not an arbitrary graph or an
explicit obstacle list. The locked [specification](../../problems/saw/Spec.lean)
defines the obstacle field as follows:

1. Every point `(x, 0)` with `x ≥ 0` is open.
2. Other positions use the coordinate encoding `enc(x) = 2*x` for `x ≥ 0`,
   or `enc(x) = 2*abs(x) - 1` for `x < 0`.
3. The encoded coordinates are multiplied by fixed constants, XORed with the
   seed and a salt, then mixed into 32 bits by `sawMix32`.
4. A position outside the open corridor is blocked exactly when the mixed value
   is 0 modulo 11.

See `sawBlocked` for the exact constants. This rule does not promise that
exactly one eleventh of any particular finite region is blocked. There is no
separately imposed board boundary. The open non-negative x-axis guarantees at
least one valid walk at every length: keep stepping right.

## Output

Return `sawSpec n : Nat`, the exact number of valid walks, without modular
reduction. At length zero, the unique walk consists only of the origin, so the
answer is 1 for every seed, including input `n = 0`.

## Examples

| Input `n` | Length | Seed | Output |
| ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 1 |
| 4294967297 | 1 | 1 | 4 |
| 8589934593 | 2 | 1 | 11 |
| 17179869186 | 4 | 2 | 84 |

Seed 1 permits all four first steps but yields only 11 valid two-step walks.
Counts for the obstacle-free lattice therefore cannot replace the required
outputs. The examples are kernel-checkable with `rfl` against the spec;
they are public illustrations, not the official hidden seed list.

## Constraints and Scoring

The current [configuration](../../problems/saw/config.json) uses three groups
and **six hidden cases**:

| Group | Walk length | Distinct hidden seeds | Target watchdog per repetition |
| --- | ---: | ---: | ---: |
| S1 | 4 | 2 | 30 s |
| S2 | 6 | 2 | 60 s |
| S3 | 8 | 2 | 120 s |

The packed sampler fixes each length and derives two distinct 32-bit seeds per
group. Different seeds need not produce distinct obstacle patterns over the
reachable region. All submissions in a cohort receive the same hidden plan.

Memory is **4096 MiB (4 GiB), provisional**, with official-host acceptance still
required. Each target has three repetitions, all of which must finish within
its watchdog. Separate build/export, audit, and correctness budgets follow the
[common evaluation rules](../evaluation.md#scoring).

An otherwise scoreable submission earns **100 points only if all six cases pass**;
any failed case gives **0 points and infinite ranking cost**. Infrastructure
errors and incomplete evaluations remain unscored. Among full-plan passes, lower
**combined work** wins: the sum of the six target-replay instruction-count
medians, plus the correctness-closure instruction-count median **once**.
Proof work therefore affects this ranking. There is no partial credit or
separate proof-cost tie-break. See the [scoring policy](../problem-scoring.md).

## Submission Requirements

Submit one `Submission.lean`, with these declarations in `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = sawSpec n
```

The proof covers **every `Nat`**: all decoded lengths and seeds, including
length zero, not only the sampled cases. The algorithm may differ from the spec,
and the proof need not use `rfl`. Current rules require total, kernel-reducible
core Lean without Mathlib and restrict axioms; see [R1–R4](../overview.md#rules).
The locked [challenge](../../problems/saw/Challenge.lean) and
[solution bridge](../../problems/saw/Solution.lean) fix the interface.

## Starter Code and Local Testing

Start from the [baseline Submission.lean](../../examples/submissions/saw/baseline/Submission.lean).
It defines `impl := sawSpec` with a reflexivity proof.
From the repository root, after the [quick-start setup](../../README.md#quick-start):

```bash
python3 scripts/quick_test.py --problem saw
python3 scripts/quick_test.py --problem saw --submission path/to/Submission.lean
```

The demo builds the proof and compares compiled outputs at `(length, seed)`
pairs `(2, 1)` and `(4, 2)`. It does not use the official hidden plan, canonical
judge, axiom audit, PMU measurement, or scoring. A pass is local feedback, not
official acceptance or kernel performance. See the [shared contestant guide](README.md).

## Notes

The baseline counts extensions depth first, checking four neighbors against a
visited-position list and the obstacle function. A different visited-set
representation or cached obstacles may reduce work. Memoization must account for
the visited set: endpoint and remaining length alone do not determine the count.
Any bounded representation must preserve the unbounded-lattice semantics for
every input; compiled speed does not establish a kernel speedup.
