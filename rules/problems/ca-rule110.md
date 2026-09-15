# Rule 110 Cellular Automaton (`ca-rule110`)

## Problem Statement

Evolve a seeded 256-cell Rule 110 automaton on a cyclic row and return the final
row as a natural-number bit vector. The result must equal the trusted
[`caSpecN`](../../evaluation/problems/ca-rule110/Spec.lean) for every `Nat`.

For a neighborhood `(left, center, right)`, Rule 110 is:

| Neighborhood | 111 | 110 | 101 | 100 | 011 | 010 | 001 | 000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Next cell | 0 | 1 | 1 | 0 | 1 | 1 | 1 | 0 |

Each simultaneous update of cell `i` reads:

```text
row[(i + 255) mod 256], row[i], row[(i + 1) mod 256].
```

Indices wrap cyclically, so cells 0 and 255 are neighbors. Zero steps returns
the initial row unchanged.

## Input

The Lean parameter `n : Nat`, not standard-input text, packs:

```text
n     = (steps << 32) | seed
steps = n >>> 32
seed  = n &&& 0xffffffff
```

The 256 cells are indexed 0 through 255. Initially:

```text
cell 0 = true
cell 1 = false
```

For every `i ≥ 2`, the initial cell is bit 31 of:

```text
caMix32(seed + (i + 1) * 0x9e3779b9).
```

The trusted xor-shift/multiply `caMix32` uses `0x7feb352d` and `0x846ca68b`,
masking intermediate products to 32 bits.

## Output

Encode the final row as a `Nat`:

```text
cell 0   = bit 0, the least-significant bit
cell i   = bit i
cell 255 = bit 255
```

Return this exact encoding, not a population count, checksum, or reversed bit
string. Bits above 255 are zero. Preserve the 256-bit width, cyclic boundaries,
and neighborhood order.

## Examples

```text
Input n:
4294967297

Output:
62412942364118713680778432052760708221590981514164502482365323362230212198349
```

Here `4294967297 = (1 << 32) | 1`: seed 1 followed by one cyclic step, encoded
with cell `i` at bit `i`.

## Constraints and Scoring

The [configuration](../../evaluation/problems/ca-rule110/config.json) has three
groups and **six hidden cases**:

| Group | Evolution steps | Hidden cases | Target watchdog per repetition |
| --- | ---: | ---: | ---: |
| C1 | 2 | 2 | 30 s |
| C2 | 4 | 2 | 60 s |
| C3 | 8 | 2 | 120 s |

Each group uses two distinct hidden 32-bit seeds. A cohort uses one hidden plan
for every submission.

Memory: **4096 MiB (4 GiB)**. The [shared scoring rules](README.md#scoring)
and [resource limits](README.md#limits) apply.

## Submission Requirements

Submit one `Submission.lean` with these declarations in `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = caSpecN n
```

The theorem covers **every `Nat`**: every decoded seed, zero steps, and step
counts outside the groups. This is core Lean without Mathlib; the
[shared requirements](README.md#submission) apply.

## Starter Code and Local Testing

The editable [starter](../../problems/ca-rule110/Submission.lean) uses `caSpecN`
with a reflexive proof. The complete
[worked example](../../examples/ca-rule110/Submission.lean) uses a bit-packed
row with its own correctness proof.

Install `elan`, then run from the repository root:

```bash
cd problems/ca-rule110
lake build
```

Edit and submit only `Submission.lean`; keep the other files unchanged.
`lake build` checks compilation, not acceptance or performance.
See the [participant guide](../../problems/ca-rule110/README.md) and
[optional kernel evaluation](../../evaluation/README.md).
