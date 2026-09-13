# Stage 1 — Problem Statements

Each page below presents one of the nine scored problems in contest-statement format:
problem statement, input, output, examples, constraints and scoring, and submission requirements.
Starter-code and local-testing instructions follow the statement. Unlike a standard-input /
standard-output programming contest, a submission here is a Lean function and a proof.
The pages do not add tasks or change their three evaluation groups. The experimental `conv`
workspace is not a scored Stage 1 problem.

## Choose a problem

| Problem | Computation | Input | Output | Ranking work |
| --- | --- | --- | --- | --- |
| [Fibonacci (`fib`)](fib.md) | Fibonacci number | Index | `Nat` | Target |
| [Integer partitions (`partition`)](partition.md) | Number of unordered integer partitions | Integer to partition | `Nat` | Target |
| [Mertens function (`mertens`)](mertens.md) | Sum of the Möbius function | Inclusive upper bound | `Int` | Target |
| [Prime counting (`primecount`)](primecount.md) | Number of primes up to a bound | Inclusive upper bound | `Nat` | Target |
| [Matrix permanent (`permanent`)](permanent.md) | Permanent of a generated 0/1 matrix | Packed dimension and seed | `Nat` | Target |
| [Self-avoiding walks (`saw`)](saw.md) | Count of walks avoiding revisits and generated obstacles | Packed length and seed | `Nat` | Combined |
| [Rule 110 (`ca-rule110`)](ca-rule110.md) | Evolution of a 256-cell cyclic row | Packed steps and seed | `Nat` | Combined |
| [SHA-256 chain (`sha256`)](sha256.md) | Repeated hashing of a 32-byte digest | Packed chain length and seed | `Nat` | Combined |
| [Polynomial discriminant (`polydisc`)](polydisc.md) | Discriminant of a generated monic degree-24 polynomial | Width-band and instance selector | `Int` | Target |

The full schedule and common resource limits are in
[Problem Leaderboards](../problem-scoring.md). The exact judging and failure rules are in
[Evaluation](../evaluation.md).

## Read the specification before implementing

The fixed evaluation files define the interface. For fib they live separately in
`evaluation/problems/fib/`; for the other eight problems they remain in `problems/<id>/`:

- `Spec.lean` defines or imports the function the implementation must equal, including any
  input decoder and instance generator. `fib` imports Mathlib v4.33.1's official
  [Nat.fib](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Data/Nat/Fib/Basic.html#Nat.fib)
  from `Mathlib.Data.Nat.Fib.Basic`; its [specification reference](fib.md#mathlib-specification)
  links the fixed-version source and dependency pin.
- `Challenge.lean` states the implementation and theorem to provide.
- `Solution.lean` connects the submitted declarations to that fixed statement.
- `config.json` specifies the evaluation groups, sampling policy, resource limits, and ranking
  policy.

Fib's [participant workspace](../../problems/fib/README.md) contains a completed,
runnable `Submission.lean` with implementation and proof TODOs, plus its own quick
test and dependency setup. It has no judge files. The other eight problem workspaces
still contain `Submission.lean` templates with placeholders.

The completed starting implementations are under `examples/submissions/<id>/baseline/`.
Some problems also have another example implementation. A baseline is a starting point, not a
promise that it completes every official case within the configured limits.

Mathematical descriptions explain the intended computation. The formal correctness target is
the definition supplied or imported by the locked `Spec.lean`. For `fib`, it is `Nat.fib`
itself. The other eight tasks still use their repository-defined specs; no separate equivalence
theorem to Mathlib is supplied for them.

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
public demo inputs. For packed-input problems, this means all instances defined by the locked
decoder and generator; it does not mean all possible matrices, graphs, or byte strings.

The implementation may use a different algorithm or representation. The correctness proof may
use induction, rewriting, and other permitted Lean reasoning; it need not be `rfl`. Separately,
the implementation must be total and kernel-reducible to its output literal. Use only the
dependencies supplied by the locked problem workspace: `fib` includes the pinned Mathlib
Fibonacci import closure; the other eight tasks remain core-Lean-only. Only `propext`,
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
The nine problem leaderboards are independent; there is no combined competition score.

The tables on individual pages give per-repetition target-process watchdogs, not a time budget
shared by a whole group. Preparation and correctness checks have their own limits. The official
metric counts kernel instructions, not compiled runtime or total process wall time. Refer to
[Evaluation](../evaluation.md) for the precise measurement boundary and resource rules.

## Quick test before using the judge

Install Git, Python 3.9 or later, and `elan`. To start fib, run from the repository root:

```bash
cd problems/fib
python3 setup.py
lake build
lake exe quick_test
```

First-time setup downloads the pinned Lean/Mathlib dependencies, without building
evaluation tools. Edit `Submission.lean` and repeat the last two commands. The quick
test checks the required all-input theorem and compiled outputs on `0`, `1`, `2`,
`10`, and `20`. See the [participant guide](../../problems/fib/README.md).

The existing helper still checks all nine example baselines. Run from the
repository root, after fib's participant setup:

```bash
python3 scripts/quick_test.py
python3 scripts/quick_test.py --problem fib
python3 scripts/quick_test.py --problem fib --submission path/to/Submission.lean
```

Replace `fib` with the problem ID from the table. The helper creates a temporary workspace,
builds the submitted implementation and universal proof, and compares compiled outputs against
the specification on fixed public inputs. It does not submit anything, invoke the official
judge, audit permitted axioms, use hidden inputs or PMU counters, or produce a score.
Passing the demo does not establish official acceptance or kernel performance.

For optional fib kernel measurements, follow the separate
[evaluation setup](../../evaluation/README.md). It uses the canonical judge on the
six-case unseeded public plan with one wall-time repetition, not official scores.
For the other tasks, see [Local development](../evaluation.md#local-development)
and the [judge setup](../../README.md#maintainer-regression-and-judge-checks).
Keep compiled quick tests, local kernel measurements, and official PMU scores separate.
