# Lean Kernel Challenge — Stage 1

*Stage 1 of a multi-stage competition on improving the performance of verified
computation in the Lean 4 kernel.*

## Co-organizers

Stage 1 is co-organized by (in alphabetical order by surname):

- Joachim Breitner
- Leonardo de Moura
- Kim Morrison
- Terence Tao

The co-organizing institutions are [Lean FRO](https://lean-fro.org/) and the
[SAIR Foundation](https://sair.foundation/).

## Background

The Lean Kernel Challenge brings the community together to improve the performance
of verified computation in the Lean kernel. Stage 1 is experimental and starts with
fundamental computational problems; later stages will cover more mathematical and
scientific fields and more complex problems.

The algorithms, representations, and open-source results and benchmark data produced
through the competition will contribute to Lean's development and benefit Lean users
worldwide. See the [competition introduction](rules/prelaunch.md) for registration,
dates, participation policies, and the release of code and data.

## Quick start

Install [elan](https://github.com/leanprover/elan), choose a problem below, and run
from the repository root:

```bash
cd problems/partition
lake build
```

Replace `partition` with your chosen problem. For **fib only**, also install Git
and Python 3.9+, then run `python3 setup.py` before `lake build` to prepare the
pinned Mathlib dependencies. The other seven tasks use core Lean and need no
separate setup.

Edit only `Submission.lean`. Each starter already contains a working implementation
and correctness proof, with two short TODOs. After edits, repeat `lake build`.
Keep the fixed specification and environment files unchanged. Submit only
`Submission.lean` through [SAIR](https://competition.sair.foundation/) when
submissions open.

Building checks your code and proofs; it does not independently check the official
interface or permitted axioms, measure kernel performance, or award a score.
No judge tools or Docker are required for this participant workflow.

### Optional kernel evaluation

To evaluate the same file locally, separately prepare the judge tools. From the
repository root:

```bash
bash evaluation/setup.sh --problem partition
python3 evaluation/run.py --problem partition --submission problems/partition/Submission.lean
```

Replace `partition` in both commands. This runs the complete public plan with one
wall-time measurement per case, not official instruction-count scoring.
See the [local evaluation guide](evaluation/README.md) for prerequisites, timeout
behavior, and how to read the result.

## Problems (Stage 1)

The eight problems have independent leaderboards. Each has three evaluation groups;
the linked statements define its input, output, examples, limits, and ranking cost.

| Problem statement | Computation | Starter |
| --- | --- | --- |
| [Fibonacci (`fib`)](rules/problems/fib.md) | The n-th Fibonacci number | [Submission](problems/fib/Submission.lean) |
| [Integer partitions (`partition`)](rules/problems/partition.md) | The partition function p(n) | [Submission](problems/partition/Submission.lean) |
| [Mertens function (`mertens`)](rules/problems/mertens.md) | The sum of the Möbius function up to n | [Submission](problems/mertens/Submission.lean) |
| [Prime counting (`primecount`)](rules/problems/primecount.md) | The number of primes up to n | [Submission](problems/primecount/Submission.lean) |
| [Matrix permanent (`permanent`)](rules/problems/permanent.md) | The permanent of a generated 0/1 matrix | [Submission](problems/permanent/Submission.lean) |
| [Rule 110 (`ca-rule110`)](rules/problems/ca-rule110.md) | Evolution of a seeded 256-cell cyclic row | [Submission](problems/ca-rule110/Submission.lean) |
| [SHA-256 chain (`sha256`)](rules/problems/sha256.md) | Repeated hashing of a 32-byte digest | [Submission](problems/sha256/Submission.lean) |
| [Polynomial discriminant (`polydisc`)](rules/problems/polydisc.md) | The exact discriminant of a generated monic degree-24 polynomial | [Submission](problems/polydisc/Submission.lean) |

## The task

Provide a fast, total, kernel-reducible implementation and prove that it equals the
fixed specification for every natural-number input:

```text
impl : Nat → Output
impl_correct : ∀ n, impl n = spec n
```

The output type, specification, and input encoding are problem-specific. For fib,
the target is Mathlib v4.33.1's `Nat.fib`; see the
[official declaration and pinned source](rules/problems/fib.md#mathlib-specification).
The other seven tasks use their repository-defined core-Lean specifications.

The proof need not use `rfl`, and the implementation need not use the specification's
algorithm. The starter may be submitted unchanged, but a correct starter is not a
promise that every performance case finishes within its limits.

## What you submit

Submit exactly one **`Submission.lean`**, at most 1 MiB. Keep the namespace,
declaration names, types, and theorem statement unchanged; put all helpers inside
`namespace Submission`.

Participant packages live in `problems/<id>/`. The judge supplies its own fixed
`Spec.lean`, `Challenge.lean`, `Solution.lean`, and configuration from
`evaluation/problems/<id>/`. Core-Lean participant packages include a generated
Spec copy for compilation; fib imports its pinned Mathlib dependency directly.

## Rules in brief

Use only the problem's supplied dependencies. The implementation must be total and
kernel-reducible; its proof may use only `propext`, `Quot.sound`, and
`Classical.choice` as axioms. `sorry` and `native_decide` are not accepted.
See the [binding rules](rules/overview.md#rules) and
[shared submission requirements](rules/problems/README.md#what-a-submission-must-establish).

## How judging works

The judge checks the universal correctness proof, then checks a direct equation
`impl n = v` for each selected input using an independently prepared exact output
`v`. Checking that equation forces kernel reduction of the submitted implementation.

Official evaluation measures kernel instructions, not compiled execution. The timer
counts inside the kernel-replay boundaries; process startup, export parsing, and
per-input dependency preload are excluded. See the
[evaluation rules](rules/evaluation.md) for the precise boundaries and verdicts.

## Scoring

There is no cross-problem total. On each problem, an otherwise scoreable submission
earns **100 points only if every hidden case passes**. Any failed case gives
**0 points and infinite ranking cost**; there is no partial credit. Infrastructure
errors and incomplete evaluations remain unscored.

Full-plan passes rank by lower instruction cost:

- **Target work (`T`):** the sum of the per-input replay medians, used by six problems.
- **Combined work (`T + C`):** target work plus the correctness-closure replay median
  once, used by `ca-rule110` and `sha256`.

Each median comes from three replays. Equal costs remain tied, without an additional
proof-cost comparison. Local wall-time measurements are not official scores.
See [Problem Leaderboards](rules/problem-scoring.md) for all groups, cases, and
limits, and [Evaluation](rules/evaluation.md) for daily and final evaluation rules.

## Maintainer regression and judge checks

Participants do not need this workflow. Maintainers should use the separate
[regression and image-build guide](evaluation/maintainers.md), including dependency
synchronization and the distinction between a regression pass and production acceptance.

### Isolated evaluation of untrusted submissions

Use the official wrapper on a supported Linux PMU host. Follow the
[reference-answer and isolated-evaluation instructions](docs/reference-answers.md)
and [production acceptance checklist](docs/pre-launch-checklist.md).
Do not run untrusted submissions through the unsandboxed local evaluation path.

## Repository layout

- `problems/<id>/`: eight participant packages; edit only `Submission.lean`.
- `evaluation/`: optional local evaluator, maintainer guide, and fixed problem workspaces.
- `rules/`: competition policies, problem statements, and scoring rules.
- `examples/submissions/`: worked implementations and rejection examples.
- `judge/`, `scripts/`, `pipeline/`: evaluation implementation and pinned configuration.
- `tests/`: regression tests and the example-submission manifest.
- `results/`: local generated artifacts, not tracked by Git.

## Toolchain

Lean **v4.33.1**, comparator `3927ad3` plus the
[emit-export patch](patches/comparator-emit-export.patch), and lean4export `15f6055`
are pinned in [pipeline/config.json](pipeline/config.json). Setup builds the tools
from these pins; third-party checkouts are not committed.

## Status

The eight problem schedules and scoring policies are published. Local build and
correctness checks do not establish official PMU, full-plan performance, or container
acceptance. Production validation and unresolved platform policies remain tracked in
the [pre-launch checklist](docs/pre-launch-checklist.md); local results must not be
presented as completion of those checks.
