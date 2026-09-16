# Stage 1 — Problems and Scoring

Stage 1 has eight problems, each with its own leaderboard and three test groups.
Each problem page gives its specification, examples, and test sizes.

## Problems

| Problem | Input | Output |
| --- | --- | --- |
| [Fibonacci (`fib`)](fib.md) | Fibonacci index | `Nat` |
| [Integer partitions (`partition`)](partition.md) | Integer to partition | `Nat` |
| [Mertens function (`mertens`)](mertens.md) | Inclusive Möbius-sum bound | `Int` |
| [Prime counting (`primecount`)](primecount.md) | Inclusive prime-counting bound | `Nat` |
| [Matrix permanent (`permanent`)](permanent.md) | Packed dimension and seed | `Nat` |
| [Rule 110 (`ca-rule110`)](ca-rule110.md) | Packed evolution steps and seed | `Nat` |
| [SHA-256 (`sha256`)](sha256.md) | Packed chain length and seed | `Nat` |
| [Polynomial discriminant (`polydisc`)](polydisc.md) | Degree-24 width-band and instance selector | `Int` |

## Quick start

Edit `problems/<id>/Submission.lean`; keep `Spec.lean` and environment files
unchanged. A complete example for each problem is in
[`examples/<id>/Submission.lean`](../../examples/README.md).

Install [elan](https://github.com/leanprover/elan). For **fib, mertens, and
primecount**, also install Git and Python 3.9+, then run `python3 setup.py` in
the problem folder before `lake build`. First setup needs network access.

For example, from the repository root:

```bash
cd problems/partition
lake build
```

Replace `partition` with your problem ID. All packages currently use Lean 4.33.1.
`lake build` checks compilation and proofs, not official acceptance or performance.
Starters compile but may exceed performance limits. For optional local evaluation,
see the [evaluator guide](../../evaluation/README.md).

## Submission

Submit one `Submission.lean` file, at most 1 MiB, containing these declarations
and any helpers inside `namespace Submission`:

```text
impl : Nat → Output
impl_correct : ∀ n, impl n = spec n
```

Keep the exact types and theorem statement from the starter. The proof must
cover **every `n : Nat`**, not just test cases. For packed inputs, this covers
all instances produced by the fixed decoder and generator, not every possible
matrix or byte string.

Code must be human-readable; compressed data and bytecode are prohibited.
Precomputed answer lookup tables and hardcoded input-specific answers are also
prohibited, including answers encoded in conditional branches. Fixed algorithm
constants, local transition rules, recurrence base cases, and tables generated
during the measured kernel computation are allowed under [R2](../overview.md#rules).
Use a total, kernel-reducible implementation and a complete proof. Different
algorithms and proofs are allowed; `rfl` is not required. See
[Rules R1–R5](../overview.md#rules) for submission restrictions.
Permitted proof axioms are `propext`, `Quot.sound`, and `Classical.choice`.

Use only the locked dependencies. For the three Mathlib problems, permitted
modules are recorded in `evaluation/problems/<id>/dependency-lock.json`.
Additional imports may compile locally but be unavailable in official evaluation.

## Mathlib status

| Problem | Current formal target | Dependency |
| --- | --- | --- |
| `fib` | `Nat.fib` | Mathlib v4.33.1 |
| `mertens` | `mertensSpec`, summing `ArithmeticFunction.moebius` | Mathlib v4.33.1 |
| `primecount` | `primeCountSpec`, backed by `Nat.primeCounting` | Mathlib v4.33.1 |
| `partition` | Custom `partitionSpec` recurrence | Core Lean |
| `permanent` | Custom `permanentSpecN` mask traversal | Core Lean |
| `ca-rule110` | Custom `caSpecN` | Core Lean |
| `sha256` | Custom `sha256Spec` | Core Lean |
| `polydisc` | Custom `discSpec` resultant algorithms | Core Lean |

Each problem page links to its fixed `Spec.lean`. The specification defines the
required result, not the algorithm participants must use.

## Scoring

Acceptance requires a valid interface, permitted axioms, and a universal proof.
For each test case, measure kernel computation three times:

```text
I_i = median(instructions_i,1, instructions_i,2, instructions_i,3)
T = I_1 + I_2 + ... + I_N
```

Rank by **T, lowest first**; equal totals tie. All cases and required verification
must pass, or there is no total or rank. There are no weights, point conversions,
or cross-problem totals.

Report each planned case's ID, group, outcome, and median. Correctness replay
is reported separately as **verification only** and never affects rank.
Failed or unattempted measurements show `—`, not zero; case IDs must not reveal
hidden inputs. See [Evaluation](../evaluation.md) for details.

## Limits

Each problem page lists its test groups and sizes. Submissions in the same
evaluation cohort use the same test plan.

| Check | Time limit |
| --- | --- |
| Universal correctness comparator | 600 s |
| Correctness axiom audit | 60 s |
| Correctness replay | 300 s per repetition |
| Case build and export | 600 s shared per case |
| Case binding and axiom audits | 300 s shared per case |
| Target replay | 30, 60, or 120 s per repetition, by test group |

The whole-job memory cap is **8 GiB for permanent**, provisionally **4 GiB for
each other problem**, with no extra swap. See [Evaluation](../evaluation.md)
for failure handling and hardware requirements.
