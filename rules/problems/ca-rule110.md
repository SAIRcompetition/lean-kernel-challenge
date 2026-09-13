# Rule 110 Cellular Automaton (`ca-rule110`)

[Back to the Stage 1 problem guide](README.md)

## Problem Statement

Evolve a seeded 256-cell Rule 110 cellular automaton on a cyclic row.
Return the final row as a natural-number bit vector.

The trusted function is `caSpecN` in
[`Spec.lean`](../../evaluation/problems/ca-rule110/Spec.lean).
Your algorithm and representation may differ, but the result must equal `caSpecN` for every
natural-number input.

For a neighborhood `(left, center, right)`, Rule 110 is:

| Neighborhood | 111 | 110 | 101 | 100 | 011 | 010 | 001 | 000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Next cell | 0 | 1 | 1 | 0 | 1 | 1 | 1 | 0 |

Only `111`, `100`, and `000` produce `false`; every other triple produces `true`.

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

The current problem memory limit is **4096 MiB**, with zero additional swap.
This value is provisional pending official-host validation; a revision requires a new cohort
and a complete rescore under the rules.

| Group | Evolution steps | Hidden cases | Target watchdog per repetition |
| --- | ---: | ---: | ---: |
| C1 | 2 | 2 | 30 s |
| C2 | 4 | 2 | 60 s |
| C3 | 8 | 2 | 120 s |

Each target declaration is replayed three times, and the median kernel instruction count
is recorded. All three repetitions must finish within the listed watchdog.
The correctness closure is separately replayed three times under the common limits.

This problem uses **combined work (`T + C`)**:

- `T` is the sum of the six target-declaration replay medians.
- `C` is the correctness-closure replay median, included once.

An otherwise scoreable submission earns **100 points** only when all six cases pass.
One failed case gives **0 points** and infinite ranking cost; no group earns partial credit.
Among complete passes, lower `T + C` ranks better, and equal costs remain tied.
Infrastructure errors and incomplete evaluations are unscored, not zero-point failures.

The final official cohort's exact inputs remain hidden during evaluation and are released
after it closes.
See [`problem-scoring.md`](../problem-scoring.md) for the binding table and
[`evaluation.md`](../evaluation.md) for the common measurement and failure rules.

## Submission Requirements

Submit exactly one `Submission.lean` file, at most 1 MiB.
Place every submitted declaration inside `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = caSpecN n
```

The theorem must cover every `n`, including arbitrary seeds, zero steps, and step counts
outside the measured groups.
The hidden closed theorems `impl n = v` then measure reduction at selected inputs; passing
those instances alone cannot replace the universal proof.

`impl` must be total and kernel-reducible.
Use core Lean only; Mathlib imports are not allowed.
Only `propext`, `Quot.sound`, and `Classical.choice` are permitted axioms.
Submissions may not rely on `sorry`, `native_decide`, `partial`, or `unsafe`.

## Starter Code and Local Testing

Start from [problems/ca-rule110/Submission.lean](../../problems/ca-rule110/Submission.lean).
It uses `caSpecN` directly with a reflexivity proof. The
[bit-packed example](../../examples/submissions/ca-rule110/bitpacked/Submission.lean)
shows an alternative row representation with its own correctness proof.
The implementation and proof are complete; use the two TODOs to make your changes.
A starting implementation is not guaranteed to pass every performance case.

Install `elan`, then run from the repository root:

```bash
cd problems/ca-rule110
lake build
```

No Mathlib or separate setup is needed. Keep the generated `Spec.lean` and environment
files unchanged; edit and submit only `Submission.lean`. Building compiles your
definitions and proofs. It does not independently check the official interface or
permitted axioms, benchmark, or score the submission. See the [participant guide](../../problems/ca-rule110/README.md).

For optional kernel evaluation, run from the repository root:

```bash
bash evaluation/setup.sh
python3 evaluation/run.py --problem ca-rule110 --submission problems/ca-rule110/Submission.lean
```

This uses the full unseeded public plan with one wall-time repetition, not official
PMU scores. See the [evaluation guide](../../evaluation/README.md).

## Notes

A packed representation may avoid repeated list indexing and update many cells with a few
large-`Nat` bitwise operations. Other representations are allowed when proved equivalent.
Preserve the 256-bit mask, cyclic rather than zero-padded boundaries, neighborhood order,
and least-significant-bit encoding. Because correctness replay contributes to `T + C`, both
the evaluator and its universal proof can affect ranking work.
