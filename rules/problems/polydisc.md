# Degree-24 Polynomial Discriminant (`polydisc`)

[Back to the Stage 1 problem guide](README.md)

## Problem Statement

Compute the exact discriminant of a deterministically generated monic degree-24 integer
polynomial.

The trusted function is `discSpec : Nat → Int` in
[`Spec.lean`](../../problems/polydisc/Spec.lean).
Your implementation may use another representation or algorithm, but it must equal
`discSpec` for every natural-number input.

Every polynomial has the high-to-low coefficient list

```text
[1, a1, a2, ..., a24].
P(x) = x^24 + a1*x^23 + ... + a23*x + a24.
```

Thus it is monic, has exact degree 24, and has 24 generated non-leading coefficients.
The generator maps any generated zero coefficient to 1, so every `ai` is nonzero.

For a monic polynomial with roots `r1, ..., r24`, its discriminant is

```text
disc(P) = product over 1 ≤ i < j ≤ 24 of (ri - rj)^2
        = (-1)^(24*23/2) * resultant(P, P').
```

The roots may be complex; the discriminant is an exact integer and can be negative.
The formal proof target is the complete locked `discSpec` computation. A formal equivalence
theorem to another library's discriminant is not supplied; Mathlib imports are currently
not allowed.

The binding files are [`Challenge.lean`](../../problems/polydisc/Challenge.lean),
[`Solution.lean`](../../problems/polydisc/Solution.lean), and
[`config.json`](../../problems/polydisc/config.json).

## Input

There is no standard-input stream; the judge calls `impl` with one Lean parameter `n : Nat`.

This problem does **not** use a high-bits/low-seed packed encoding.
The complete value `n` selects a coefficient-width band and seeds the generator.

The specification supports five bands:

| Condition on `n` | Level | Maximum coefficient width `k` |
| --- | ---: | ---: |
| `n < 2^26` | 0 | 15 bits |
| `2^26 ≤ n < 2^36` | 1 | 36 bits |
| `2^36 ≤ n < 2^46` | 2 | 205 bits |
| `2^46 ≤ n < 2^56` | 3 | 1,001 bits |
| `2^56 ≤ n` | 4 | 3,484 bits |

Stage 1 actively scores only levels 0, 2, and 4 as D1, D3, and D5.
The universal proof must still cover all five specification bands.

The 64-bit MMIX linear congruential generator uses:

```text
A = 6364136223846793005
C = 1442695040888963407
M = 2^64
initial state = (A * (n + 1) + C) mod M
next(state)   = (A * state + C) mod M.
```

Each coefficient has a public position-dependent width between 2 and `k`.
The exact formula is in `coefficientWidth` in the trusted specification.
The generator advances the LCG before each word, assembles words little-endian, extracts the
requested high bits, subtracts `2^(width-1)`, and replaces zero with 1.
For a coefficient of width `w`, this gives `-2^(w-1) ≤ ai < 2^(w-1)` and `ai ≠ 0`.
The width is a generation bound, not a promise that every coefficient has exactly that
many magnitude bits.

## Output

Return the exact signed discriminant as an `Int`.
Do not return its magnitude, sign bit, hash, residue, or bit length.

The specification derives the polynomial in high-to-low order and multiplies its resultant
with its derivative by `(-1)^(degree*(degree-1)/2)`.
For degree 24 the exponent is 276, so that final sign factor is positive.

## Examples

```text
Input n:
0

Output:
-1437475373221515423615709146748564172609479315133942550011246093047173337258904221338662563268181154344436806624326331905334612913874200226104057144892486060212832
```

Input 0 selects level 0 and the 15-bit maximum-width profile.
The actual generator produces the polynomial

```text
[1, 1, 18, -15, 75, 1, 27, -223, 347, -618, 503, 146, 1161,
 -1499, -2101, 4094, -2473, 2364, 4018, -9725, 11989, 15716,
 1630, 3984, -3697].
```

The trusted resultant/discriminant computation gives the exact `Int` shown above.
This is a public specification example, not an official hidden input.

## Constraints and Scoring

The current problem memory limit is **4096 MiB**, with zero additional swap.
This value is provisional pending official-host validation; a revision requires a new cohort
and a complete rescore under the rules.
Each group samples two distinct hidden integers uniformly from its inclusive range.

| Group | Inclusive input range | Maximum width | Cases | Target watchdog per repetition |
| --- | ---: | ---: | ---: | ---: |
| D1 | `2^18` through `2^25` | 15 bits | 2 | 30 s |
| D3 | `2^37` through `2^45` | 205 bits | 2 | 60 s |
| D5 | `2^57` through `2^63` | 3,484 bits | 2 | 120 s |

These are the three current scoring groups; the other two supported bands do not create
additional Stage 1 cases or tiers.

Each target declaration is replayed three times.
Its median kernel instruction count is recorded, and all three repetitions must finish
within the listed per-repetition watchdog.
The correctness closure must also complete three replays under the common limits.

This problem uses **target work (`T`)**:

- `T` is the sum of all six target-declaration replay medians.
- Correctness replay is a scoreability gate but is not added to ranking work.

An otherwise scoreable submission earns **100 points** only if all six cases pass.
Any failed case gives **0 points** and infinite ranking cost; there is no partial credit.
Among complete passes, lower `T` ranks better, and equal costs remain tied.
Infrastructure errors and incomplete evaluations are unscored, not zero-point failures.

The final official cohort's exact inputs remain hidden during evaluation and are released
after it closes.
See [`problem-scoring.md`](../problem-scoring.md) and
[`evaluation.md`](../evaluation.md) for the binding plan and common judge rules.

## Submission Requirements

Submit exactly one `Submission.lean` file, at most 1 MiB, with these declarations inside
`namespace Submission`:

```text
impl : Nat → Int
impl_correct : ∀ n, impl n = discSpec n
```

All helpers must also be inside `namespace Submission`.
The universal theorem covers every input and all five bands, while the measured closed
theorem `impl n = v` evaluates one hidden instance against its exact `Int` literal.

The implementation must be total and kernel-reducible.
Use core Lean only; Mathlib imports are not allowed.
Only `propext`, `Quot.sound`, and `Classical.choice` are permitted axioms.
Do not use `sorry`, `native_decide`, `partial`, or `unsafe` to bypass the contract.

## Starter Code and Local Testing

The [baseline](../../examples/submissions/polydisc/baseline/Submission.lean) defines
`impl := discSpec` and proves the universal equality by reflexivity.
Its path is the trusted normal subresultant computation with the reduced-matrix Bareiss
fallback; it is not guaranteed to pass every official case within its limits.

From the repository root, after the [quick-start setup](README.md#quick-test-before-using-the-judge),
run the public baseline demo:

```bash
python3 scripts/quick_test.py --problem polydisc
```

Run a candidate file or directory:

```bash
python3 scripts/quick_test.py --problem polydisc --submission path/to/Submission.lean
```

The helper builds the universal proof and compares compiled `impl` and `discSpec` at `n = 0`.
It is compiled-only smoke testing, not a formal cross-check with another polynomial library.
It does not use hidden inputs, count PMU instructions, apply the production sandbox, audit
axioms, issue a verdict, or compute a score.

## Notes

The trusted algorithm first tries a normal subresultant polynomial remainder sequence.
An abnormal degree drop or failed exact division switches to a reduced 24×24 monic
resultant matrix and fraction-free Bareiss elimination with row pivoting.
Possible approaches include a cheaper representation or proved-equivalent resultant algorithm.
Preserve coefficient order, the generator, signed output, and the result on inputs where
the specification takes its fallback. Your implementation need not take the same path.
Compiled arithmetic performance is not the official kernel instruction metric.
