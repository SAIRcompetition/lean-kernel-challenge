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

The Lean Kernel Challenge brings the community together to improve verified
computation in the Lean kernel. Stage 1 is experimental and begins with eight
fundamental computational problems. See the [competition overview](rules/overview.md)
for dates and rules, and the [competition introduction](rules/prelaunch.md) for
registration, team, cost, and publication policies.

## Quick start

Install [elan](https://github.com/leanprover/elan), choose a problem below, and run
from the repository root:

```bash
cd problems/partition
lake build
```

Replace `partition` with your chosen problem. For **fib**, **mertens**, and
**primecount**, also install Git and Python 3.9+, then run `python3 setup.py`
before `lake build` to prepare the pinned Mathlib dependencies. The other five
tasks use core Lean and need no separate setup.

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

## Problems

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

## Submission

Provide a fast, total, kernel-reducible implementation and prove that it equals the
fixed specification for every natural-number input:

```text
impl : Nat → Output
impl_correct : ∀ n, impl n = spec n
```

Submit exactly one **`Submission.lean`**, at most 1 MiB. The proof must cover
every natural-number input, but need not use `rfl`; the implementation may use a
different algorithm from the specification. See the
[shared submission requirements](rules/problems/README.md#submission) for the
exact names, types, dependencies, namespace, and axiom policy, and the
[binding rules](rules/stage1-rules.md#rules) for acceptance requirements.

## Scoring

Each problem has an independent leaderboard. Every case reports the median of
three kernel-replay instruction counts; complete results rank by their sum,
lowest first. Correctness-proof work is excluded, and a performance failure
leaves an Accepted submission without a complete total or rank. There is no
cross-problem total. The unified
[problem and scoring guide](rules/problems/README.md#scoring) gives all cases,
limits, and the current [implementation status](rules/problems/README.md#implementation-status).
The checked-in evaluator still uses the previous ranking policy.

## Evaluator reproduction

Evaluator checks are optional for participants. The
[image-build and replay guide](evaluation/maintainers.md) covers reproducible setup
and isolated evaluation. Never run untrusted submissions through the unsandboxed
local evaluation path.

## Repository layout

- `problems/<id>/`: eight participant packages; edit only `Submission.lean`.
- `evaluation/`: evaluator, fixed problem workspaces, and reproduction guide.
- `rules/`: competition policies and problem statements.
- `examples/submissions/`: worked implementations and rejection examples.
- `scripts/`: setup, dependency preparation, evaluation wrappers, and result reporting.
- `tests/harness_manifest.json`: expected example results for the image-build check.
- `results/`: local generated artifacts, not tracked by Git.

Internal unit tests, CI workflows, development notes, and release checklists are
local-only and ignored by Git. They are not required to build submissions or
reproduce evaluation.
