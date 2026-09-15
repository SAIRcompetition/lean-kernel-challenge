# Polynomial Discriminant (`polydisc`)

## Problem Statement

Compute the exact signed discriminant of a generated monic degree-24 integer
polynomial, as defined by `discSpec : Nat → Int` in
[`Spec.lean`](../../evaluation/problems/polydisc/Spec.lean).
Its high-to-low coefficient list is:

```text
[1, a1, a2, ..., a24].
P(x) = x^24 + a1*x^23 + ... + a23*x + a24.
```

All 24 generated coefficients are nonzero; the degree is always exactly 24.

## Input

The judge calls `impl n` with `n : Nat`. The complete `n` selects a width band
and seeds the generator; it is **not** a packed scale/seed pair.
The specification supports five bands:

| Condition on `n` | Level | Maximum coefficient width `k` |
| --- | ---: | ---: |
| `n < 2^26` | 0 | 15 bits |
| `2^26 ≤ n < 2^36` | 1 | 36 bits |
| `2^36 ≤ n < 2^46` | 2 | 205 bits |
| `2^46 ≤ n < 2^56` | 3 | 1,001 bits |
| `2^56 ≤ n` | 4 | 3,484 bits |

Stage 1 scores only levels 0, 2, and 4 as D1, D3, and D5; correctness still covers
every natural-number input and all five bands.

The 64-bit MMIX generator uses:

```text
A = 6364136223846793005
C = 1442695040888963407
M = 2^64
initial state = (A * (n + 1) + C) mod M
next(state)   = (A * state + C) mod M.
```

For coefficient `i`, `coefficientWidth k i` in the specification sets a width
`w` between 2 and `k`. Advance the LCG before each word, assemble `ceil(w/64)`
consecutive 64-bit words little-endian, take the requested high bits, subtract
`2^(w-1)`, and replace zero with 1. Thus `-2^(w-1) ≤ ai < 2^(w-1)` and `ai ≠ 0`;
width is a bound, not an exact magnitude-bit count.

## Output

Return the exact signed discriminant as an `Int`, not its magnitude or a residue.
For roots `r1, ..., r24`:

```text
disc(P) = product over 1 ≤ i < j ≤ 24 of (ri - rj)^2
        = (-1)^(24*23/2) * resultant(P, P').
```

The exponent is 276, so the sign factor is positive. The discriminant itself
can be negative because the roots may be complex.

## Examples

```text
Input n:
0

Output:
-1437475373221515423615709146748564172609479315133942550011246093047173337258904221338662563268181154344436806624326331905334612913874200226104057144892486060212832
```

Input 0 selects the 15-bit level-0 profile and generates:

```text
[1, 1, 18, -15, 75, 1, 27, -223, 347, -618, 503, 146, 1161,
 -1499, -2101, 4094, -2473, 2364, 4018, -9725, 11989, 15716,
 1630, 3984, -3697].
```

This is a public example, not an official hidden input.

## Constraints and Scoring

The [test plan](../../evaluation/problems/polydisc/config.json) has six hidden
cases, sampling two distinct integers uniformly from each inclusive range:

| Group | Inclusive input range | Maximum width | Cases | Target watchdog per repetition |
| --- | ---: | ---: | ---: | ---: |
| D1 | `2^18` through `2^25` | 15 bits | 2 | 30 s |
| D3 | `2^37` through `2^45` | 205 bits | 2 | 60 s |
| D5 | `2^57` through `2^63` | 3,484 bits | 2 | 120 s |

Memory: **4096 MiB (4 GiB)**. The [shared scoring rules](README.md#scoring)
and [resource limits](README.md#limits) apply.

## Submission Requirements

Submit one `Submission.lean` with these declarations inside `namespace Submission`:

```text
impl : Nat → Int
impl_correct : ∀ n, impl n = discSpec n
```

Prove equality for **every `n : Nat` and all five bands**, including fallback
cases. This problem uses core Lean without Mathlib; the
[shared submission requirements](README.md#submission) apply.

## Starter Code and Local Testing

The [starter](../../problems/polydisc/Submission.lean) and
[complete example](../../examples/polydisc/Submission.lean) call `discSpec`
with a reflexive proof. It tries a normal subresultant polynomial remainder
sequence; an abnormal degree drop or failed exact division falls back to a
reduced 24×24 monic resultant matrix and fraction-free Bareiss elimination
with row pivoting. Your implementation need not follow the same algorithm.

Install `elan`, then run from the repository root:

```bash
cd problems/polydisc
lake build
```

No separate setup is needed. Edit only `Submission.lean`. `lake build` checks
compilation and proofs, not official acceptance or performance.
See the [participant guide](../../problems/polydisc/README.md) and
[optional kernel evaluation](../../evaluation/README.md).
