# Stage 1 — Problem Statements

Each page below presents one of the eight scored problems in contest-statement format:
problem statement, input, output, examples, constraints and scoring, and submission requirements.
Starter-code and local-testing instructions follow the statement. Unlike a standard-input /
standard-output programming contest, a submission here is a Lean function and a proof.
The pages do not add tasks or change their three evaluation groups.

## Choose a problem

| Problem | Computation | Input | Output | Ranking work |
| --- | --- | --- | --- | --- |
| [Fibonacci (`fib`)](fib.md) | Fibonacci number | Index | `Nat` | Target |
| [Integer partitions (`partition`)](partition.md) | Number of unordered integer partitions | Integer to partition | `Nat` | Target |
| [Mertens function (`mertens`)](mertens.md) | Sum of the Möbius function | Inclusive upper bound | `Int` | Target |
| [Prime counting (`primecount`)](primecount.md) | Number of primes up to a bound | Inclusive upper bound | `Nat` | Target |
| [Matrix permanent (`permanent`)](permanent.md) | Permanent of a generated 0/1 matrix | Packed dimension and seed | `Nat` | Target |
| [Rule 110 (`ca-rule110`)](ca-rule110.md) | Evolution of a 256-cell cyclic row | Packed steps and seed | `Nat` | Combined |
| [SHA-256 chain (`sha256`)](sha256.md) | Repeated hashing of a 32-byte digest | Packed chain length and seed | `Nat` | Combined |
| [Polynomial discriminant (`polydisc`)](polydisc.md) | Discriminant of a generated monic degree-24 polynomial | Width-band and instance selector | `Int` | Target |

The full schedule and common resource limits are in
[Problem Leaderboards](../problem-scoring.md). The exact judging and failure rules are in
[Evaluation](../evaluation.md).

## Read the specification before implementing

The fixed evaluation files define the interface. All eight scored tasks keep them
in `evaluation/problems/<id>/`, separately from participant files:

- `Spec.lean` defines or imports the function the implementation must equal, including any
  input decoder and instance generator. `fib`, `mertens`, and `primecount` use
  APIs from the pinned Mathlib v4.33.1 dependency; their problem pages identify
  the exact declarations and fixed-version sources.
- `Challenge.lean` states the implementation and theorem to provide.
- `Solution.lean` connects the submitted declarations to that fixed statement.
- `config.json` specifies the evaluation groups, sampling policy, resource limits, and ranking
  policy.

The eight participant packages contain runnable `Submission.lean` files
with two short TODOs and a generated fixed `Spec.lean` dependency; do not edit
the latter. Fib, Mertens, and prime counting additionally provide their own
pinned Mathlib dependency setup. No participant package contains the judge
interfaces or scoring configuration.

The completed starting implementations are under `examples/submissions/<id>/baseline/`.
Some problems also have another example implementation. A baseline is a starting point, not a
promise that it completes every official case within the configured limits.

Mathematical descriptions explain the intended computation. The formal correctness target is
the definition supplied or imported by the locked `Spec.lean`, not every related definition
that happens to exist in Mathlib.

## Mathlib status

This table records the current target separately from possible future library bridges.
“Candidate” does not change the competition target and does not claim that the repository
algorithm has already been certified against that Mathlib definition.

| Problem | Current formal target | Mathlib status |
| --- | --- | --- |
| `fib` | `Nat.fib` | Direct Mathlib v4.33.1 target. |
| `primecount` | `primeCountSpec`, backed by `Nat.primeCounting` | Direct Mathlib v4.33.1 target. |
| `mertens` | `mertensSpec`, an inclusive sum of `ArithmeticFunction.moebius` | Uses Mathlib's Möbius function in the current target. |
| `partition` | Repository `partitionSpec` recurrence | Mathlib has `Nat.Partition`; `Fintype.card (Nat.Partition n)` is a future candidate, but no all-`n` bridge from `partitionSpec` is supplied. |
| `permanent` | Repository `permanentSpecN` mask traversal | Mathlib has `Matrix.permanent`, but no all-input bridge from the current traversal and generated matrices is supplied. |
| `polydisc` | Repository `discSpec` resultant algorithms | Mathlib has `Polynomial.discr`, but no all-input bridge from the generated polynomial and current algorithms is supplied. |
| `ca-rule110` | Repository `caSpecN` | Mathlib has generic iteration tools, but no dedicated Rule 110 specification. |
| `sha256` | Repository `sha256Spec` | Mathlib has general fixed-width bit-vector APIs, but no dedicated SHA-256 implementation. |

## What a submission must establish

Submit one `Submission.lean` file, at most 1 MiB, with the implementation, proof, and helpers
inside `namespace Submission`. The interface is:

```text
impl : Nat → Output
impl_correct : ∀ n, impl n = spec n
```

`Output` and `spec` stand for the concrete type and specification name listed on each problem
page. They are not declarations to add to the submission.

The proof covers **every natural-number input**, not just the three scored groups or the
worked examples. For packed-input problems, this means all instances defined by the locked
decoder and generator; it does not mean all possible matrices, graphs, or byte strings.

The implementation may use a different algorithm or representation. The correctness proof may
use induction, rewriting, and other permitted Lean reasoning; it need not be `rfl`. Separately,
the implementation must be total and kernel-reducible to its output literal. Use only the
dependencies supplied by the locked problem workspace: fib, Mertens, and prime counting
include pinned Mathlib import closures; the other five tasks remain core-Lean-only. Only `propext`,
`Quot.sound`, and `Classical.choice` are permitted proof axioms; `sorry` and `native_decide`
are not accepted. See
[Rules R1–R5](../overview.md#rules).

## How performance and scores are determined

The judge first checks the universal correctness proof. It then checks a generated direct
equation `impl n = v` for each hidden input, where `v` is the official standard output.
Checking that equation forces the kernel to compute the submitted implementation; it does not
require the implementation to follow the specification's algorithm.

For an otherwise scoreable submission:

- Every case must pass to earn **100 points**. Any failed case gives **0 points** and infinite
  ranking cost; there is no partial credit for a group or a subset of cases.
- Among full-plan passes, lower instruction cost ranks better. Equal costs remain tied.
- **Target work** sums the median kernel instruction count for each target declaration.
- **Combined work** adds the correctness-closure replay median once to target work.

Official medians use three repetitions. Every submission must complete all correctness
replays, including on target-work problems where that cost is not added to ranking work.
Infrastructure errors and incomplete runs are unscored, not zero-point contestant failures.
The eight problem leaderboards are independent; there is no combined competition score.

The tables on individual pages give per-repetition target-process watchdogs, not a time budget
shared by a whole group. Preparation and correctness checks have their own limits. The official
metric counts kernel instructions, not compiled runtime or total process wall time. Refer to
[Evaluation](../evaluation.md) for the precise measurement boundary and resource rules.

## Local participant build

For any scored task, install `elan` and run from the repository root:

```bash
cd problems/partition
lake build
```

Replace `partition` with the chosen task. For fib, Mertens, and prime counting,
install Git and Python 3.9+ and run `python3 setup.py` before building; each
participant package documents that step. The other five need only core Lean.
Edit `Submission.lean` and repeat `lake build`.
Building compiles definitions and proofs; it does not independently check the official
interface or permitted axioms, benchmark, or score the submission.

For optional kernel measurements, follow the separate
[evaluation setup](../../evaluation/README.md). It uses the canonical judge on the
selected task's complete unseeded public plan with one wall-time repetition,
not official scores. Only `Submission.lean` is passed to the judge.
