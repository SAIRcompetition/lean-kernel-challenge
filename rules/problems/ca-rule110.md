# Rule 110 Cellular Automaton (`ca-rule110`)

[Back to the Stage 1 problem guide](README.md)

## Problem Statement

Evolve a seeded 256-cell Rule 110 cellular automaton on a cyclic row.
Return the final row as a natural-number bit vector.

The trusted function is `caSpecN` in
[`Spec.lean`](../../evaluation/problems/ca-rule110/Spec.lean).
Your algorithm and representation may differ, but the result must equal `caSpecN` for every
natural-number input.

Mathlib v4.33.1 has no dedicated Rule 110 or cellular-automaton specification.
Its general [`Nat.iterate`](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Logic/Function/Iterate.html#Nat.iterate),
defined in the [fixed source](https://github.com/leanprover-community/mathlib4/blob/0df444a360eaa60ab8c11dca51a86af692955474/Mathlib/Logic/Function/Iterate.lean#L40-L46),
can express repeated stepping but does not define Rule 110, the cyclic row, or
this problem's seed and encoding. The current target therefore remains the
repository's core-Lean `caSpecN`.

For a neighborhood `(left, center, right)`, Rule 110 is:

| Neighborhood | 111 | 110 | 101 | 100 | 011 | 010 | 001 | 000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Next cell | 0 | 1 | 1 | 0 | 1 | 1 | 1 | 0 |

The boundary is cyclic. For cell `i`, the three inputs are:

```text
row[(i + 255) mod 256], row[i], row[(i + 1) mod 256].
```

Cell 0 therefore reads cell 255 on its left, and cell 255 reads cell 0 on its right.
All cells update simultaneously from the previous row.
At zero steps, the seeded initial row is returned unchanged.

The binding files are [`Challenge.lean`](../../evaluation/problems/ca-rule110/Challenge.lean),
[`Solution.lean`](../../evaluation/problems/ca-rule110/Solution.lean), and
[`config.json`](../../evaluation/problems/ca-rule110/config.json).

## Input

There is no standard-input stream.
The judge supplies one Lean parameter `n : Nat` using this packed encoding:

```text
n     = (steps << 32) | seed
steps = n >>> 32
seed  = n &&& 0xffffffff
```

The row always has 256 cells, indexed from 0 through 255.
The first two initial cells are fixed:

```text
cell 0 = true
cell 1 = false
```

For every `i >= 2`, the initial cell is bit 31 of

```text
caMix32(seed + (i + 1) * 0x9e3779b9).
```

`caMix32` is the exact xor-shift/multiply mixer in the trusted specification.
It uses multipliers `0x7feb352d` and `0x846ca68b` and masks intermediate products to
32 bits. Hidden evaluation chooses two distinct 32-bit seeds at each published step count.

## Output

Return the final row as a `Nat`, with the following bit order:

```text
cell 0   = bit 0, the least-significant bit
cell i   = bit i
cell 255 = bit 255
```

The output must be the exact encoded row, not a population count, checksum, or reversed bit
string.

## Examples

```text
Input n:
4294967297

Output:
62412942364118713680778432052760708221590981514164502482365323362230212198349
```

Here `4294967297 = (1 << 32) | 1`.
The specification generates the 256-cell row for seed 1, applies one cyclic Rule 110 step,
then encodes cell `i` as bit `i` of the displayed natural number.

## Constraints and Scoring

The plan has three groups and six hidden cases:

| Group | Evolution steps | Hidden cases | Target watchdog per repetition |
| --- | ---: | ---: | ---: |
| C1 | 2 | 2 | 30 s |
| C2 | 4 | 2 | 60 s |
| C3 | 8 | 2 | 120 s |

Memory: **4096 MiB (4 GiB)**. The [shared scoring rules](README.md#scoring)
and [resource limits](README.md#limits) apply.

## Submission Requirements

Submit one `Submission.lean` with these declarations inside `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = caSpecN n
```

The theorem must cover every `n`, including arbitrary seeds, zero steps, and step counts
outside the measured groups.

Use total, kernel-reducible core Lean code without Mathlib. The
[shared submission requirements](README.md#submission)
apply.

## Starter Code and Local Testing

Start from [problems/ca-rule110/Submission.lean](../../problems/ca-rule110/Submission.lean).
It uses `caSpecN` directly with a reflexivity proof. The
[bit-packed example](../../examples/submissions/ca-rule110/bitpacked/Submission.lean)
shows an alternative row representation with its own correctness proof.
The two TODOs mark the implementation and proof to edit.

Install `elan`, then run from the repository root:

```bash
cd problems/ca-rule110
lake build
```

No separate setup is needed. Edit and submit only `Submission.lean`; keep
`Spec.lean` and the environment files unchanged. `lake build` compiles the code
and proof; it is not an acceptance check or performance measurement.
See the [participant guide](../../problems/ca-rule110/README.md) and
[optional kernel evaluation](../../evaluation/README.md).

## Notes

A packed representation may avoid repeated list indexing and update many cells with a few
large-`Nat` bitwise operations. Other representations are allowed when proved equivalent.
Preserve the 256-bit mask, cyclic rather than zero-padded boundaries, neighborhood order,
and least-significant-bit encoding.
