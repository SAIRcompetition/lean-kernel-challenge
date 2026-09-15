# Stage 1 — Problems and Scoring

Stage 1 has eight independent problem leaderboards. Submit a Lean function and a
proof, not a program that reads standard input. Each page below defines the task,
examples, and its three evaluation groups.

## Problems

| Problem | Input | Output |
| --- | --- | --- |
| [Fibonacci (`fib`)](fib.md) | Fibonacci index | `Nat` |
| [Integer partitions (`partition`)](partition.md) | Integer to partition | `Nat` |
| [Mertens function (`mertens`)](mertens.md) | Inclusive Möbius-sum bound | `Int` |
| [Prime counting (`primecount`)](primecount.md) | Inclusive prime-counting bound | `Nat` |
| [Matrix permanent (`permanent`)](permanent.md) | Packed dimension and seed | `Nat` |
| [Rule 110 (`ca-rule110`)](ca-rule110.md) | Packed evolution steps and seed | `Nat` |
| [SHA-256 chain (`sha256`)](sha256.md) | Packed chain length and seed | `Nat` |
| [Polynomial discriminant (`polydisc`)](polydisc.md) | Degree-24 width-band and instance selector | `Int` |

## Quick start

Install [elan](https://github.com/leanprover/elan), then run from the repository root:

```bash
cd problems/partition
lake build
```

Replace `partition` with your problem. For **fib, mertens, and primecount**, also
install Git and Python 3.9+, and run `python3 setup.py` in that problem's folder
before building to prepare pinned Mathlib dependencies. First setup needs network
access. All packages use Lean 4.33.1.

Edit and submit only `Submission.lean`. Keep `Spec.lean` and environment files
unchanged. The starter implementation and proof already compile, but a starter
is not guaranteed to finish every performance case within its limits.

`lake build` checks compilation and proofs, not the official interface, axiom
policy, or performance. The evaluator is optional for development; follow
[local evaluation](../../evaluation/README.md) to run it separately.

## Submission

Submit one `Submission.lean` file, at most 1 MiB, containing these declarations
and any helpers inside `namespace Submission`:

```text
impl : Nat → Output
impl_correct : ∀ n, impl n = spec n
```

Use the concrete output type and specification name from your problem page.
The proof covers **every `n : Nat`**, not just test cases. For packed inputs, this
means all instances produced by the fixed decoder and generator, not every
possible matrix or byte string.

Submitted code must be human-readable. Compressed data and bytecode are not allowed.
You may change the algorithm or representation within these rules; the proof
need not use `rfl`.
The implementation must be total and kernel-reducible to its output literal.
Use only locked dependencies. Permitted proof axioms are `propext`, `Quot.sound`,
and `Classical.choice`; `sorry` and `native_decide` are not accepted.
See [Rules R1–R5](../overview.md#rules).

For fib, mertens, and primecount, local setup checks out pinned Mathlib packages.
Official evaluation supplies only the modules and compiled artifacts from those
packages recorded in that problem's `evaluation/problems/<id>/dependency-lock.json`. An additional
Mathlib import may compile locally without being available in the official workspace.

The fixed files in `evaluation/problems/<id>/` define the contract:

- `Spec.lean`: formal target, decoder, and generator; participant copies are identical.
- `Challenge.lean` and `Solution.lean`: required interface and submission bridge.
- `config.json`: test groups, sampling, limits, and the versioned ranking contract.

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

Each problem page links to its exact definitions. Mathlib's `Nat.Partition`,
`Matrix.permanent`, and `Polynomial.discr` are possible future targets, not the
current specifications: no all-input equivalence bridge is supplied. Rule 110
and SHA-256 use custom specifications rather than dedicated Mathlib implementations.

## Scoring

The judge first checks the interface, permitted axioms, and universal proof
`∀ n, impl n = spec n`. Only a pass is **Accepted** and proceeds to performance
evaluation. Passing sampled tests alone does not establish correctness.

Record two separate replay metrics. **Correctness replay** checks the verified
definitions and universal proof; its metric C is the median instruction count
over three repetitions. **Computation replay** checks `impl n` against the exact
official output for each case; its metric T is the sum of the per-case medians:

```text
C = median(correctness_instructions_1, correctness_instructions_2, correctness_instructions_3)
I_i = median(instructions_i,1, instructions_i,2, instructions_i,3)
T = I_1 + I_2 + ... + I_N
```

- Rank by **T, lowest first**, only when all cases pass and required verification
  completes. Equal totals tie. There are no group weights or point conversions.
- C is **verification only**: report it separately and never add it to T or use
  it for tie-breaking, for **all eight problems**. The per-case kernel check
  reducing `impl n` to the exact output remains measured.
- Performance failures, timeouts, or resource-limit failures leave an otherwise
  Accepted submission without a complete total or rank. Partial totals are not ranked.
- Leaderboards are independent; there is no cross-problem total.

Reports list **every planned case**: ID, group, outcome, and median computation
instruction count. Failed or unattempted cases show `—`, never zero. Show T only
for complete passes. Also report the correctness-replay outcome and C separately,
labeled **verification only**; if any of its three repetitions fails or is
unattempted, show C as `—`. Do not merge correctness and computation replay into
a single cost. Replay-specific wall-time and memory measurements must also
identify their phase and units.
Case IDs must not reveal hidden input values.

Infrastructure failures require review or re-evaluation and are not contestant
performance failures. See [evaluation](../evaluation.md) for measurement boundaries.

## Limits

The complete test-group table appears on each problem page. Groups define
workloads, not separate awards. Every submission in one cohort receives the same
resolved plan. Exact final inputs and the seed are released after evaluation;
this does not apply to provisional reference inputs or seeds.

| Check | Time limit |
| --- | --- |
| Universal correctness comparator | 600 s |
| Correctness axiom audit | 60 s |
| Correctness replay | 300 s per repetition; all three must finish |
| Per-case theorem build and export | 600 s shared by build and export together |
| Per-case performance-export binding and axiom audits | 300 s shared by both checks together |
| Target replay | 30, 60, or 120 s per repetition, as specified by the problem's test group |

All three target replays must finish within their watchdog; any published
instruction limit applies to the median. Watchdogs include whole-process overhead,
while instruction counts cover only target replay. Build/export, case axiom-audit,
and target-replay timeouts do not consume later cases' limits or stop them being
attempted. A failed or unfinished performance-export binding check stops
the run for review, as described in [evaluation](../evaluation.md#evaluation-process).
Reference-answer preparation is independent of submissions and outside these budgets.

These revised budgets are the proposed deployment contract, not a guarantee that
every valid proof or implementation completes. They require a rebuilt evaluator,
aligned platform consumers, and a new sealed cohort before use. Previously sealed
budgets remain unchanged; a comparison set must be re-evaluated together when its
budgets change. See [budget migration and task deadlines](../../evaluation/maintainers.md#stage-budgets-and-task-deadlines).

Memory is **8192 MiB (8 GiB) for permanent** and provisionally **4096 MiB (4 GiB)
for each other problem**, with no extra swap. Limits cover the entire evaluation
job and are fixed in each `evaluation/problems/<id>/config.json`. Official-host
validation remains pending; limits do not guarantee baseline completion. Changing
a limit requires a new cohort and a complete rescore of that problem's comparison set.

Sampling terms:

- **Geometric range:** distinct, increasing integers in the inclusive range, with
  deterministic 15% seed-derived jitter. For two cases the endpoints are jittered
  inward; unseeded local runs use the endpoints.
- **Uniform integer:** distinct, unbiased seed-derived integers in the inclusive range.
- **Packed:** public scale in the high bits and a distinct seed-derived 32-bit
  instance seed in the low bits. Different seeds may generate the same instance.

## Implementation status

The checked-in evaluator, scorer, and reports implement `computation-total-v1`
for all eight problem configurations. Complete verified plans rank only by T;
C is reported separately as verification only. Failed or incomplete plans have
no total or rank. Reports retain every planned case using IDs that do not encode
inputs. Official successful series must retain all three instruction measurements
and their exact median.

Previously sealed `full-plan-v1` and `group-points-v1` cohorts retain their original
scoring, including any proof-work charge. They must not be relabeled or mixed with
the new policy. Deployment requires a rebuilt evaluator and aligned platform
consumers, a new sealed cohort, and a complete re-evaluation of the comparison set.
This source implementation does not establish that a hosted deployment has upgraded
or passed official-host acceptance.
