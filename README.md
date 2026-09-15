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

Stage 1 is experimental and begins with eight computational problems. See the
[competition overview](rules/overview.md) for dates, registration, and rules.

## Quick start

Install [elan](https://github.com/leanprover/elan). For **fib**, **mertens**, and
**primecount**, also install Git and Python 3.9+, and run `python3 setup.py` in
the problem folder before `lake build`. Other problems need no separate setup.

Choose a problem below. For example, from the repository root:

```bash
cd problems/partition
lake build
```

Replace `partition` with your problem ID. Edit only `Submission.lean`, then
repeat `lake build`. Keep `Spec.lean` and environment files unchanged. Submit
only `Submission.lean` through [SAIR](https://competition.sair.foundation/)
when submissions open.

Starters include an implementation and proof, but may exceed performance limits.
`lake build` checks code and proofs, not official acceptance or performance.
No evaluator or Docker is required.

### Optional kernel evaluation

From the repository root:

```bash
bash evaluation/setup.sh --problem partition
python3 evaluation/run.py --problem partition --submission problems/partition/Submission.lean
```

Replace `partition` in both commands. Local evaluation uses the complete unseeded
public plan with one wall-time measurement per case, not official scoring.
It is unsandboxed: run only code you trust. See [local evaluation](evaluation/README.md)
for prerequisites and results, or [deployment](evaluation/maintainers.md) for
isolated reproduction.

## Problems

Each problem has its own leaderboard and three test groups. The statements give
the specification, examples, and limits.

| Problem statement | Computation | Starter |
| --- | --- | --- |
| [Fibonacci (`fib`)](rules/problems/fib.md) | The n-th Fibonacci number | [Submission](problems/fib/Submission.lean) |
| [Integer partitions (`partition`)](rules/problems/partition.md) | The partition function p(n) | [Submission](problems/partition/Submission.lean) |
| [Mertens function (`mertens`)](rules/problems/mertens.md) | The sum of the Möbius function up to n | [Submission](problems/mertens/Submission.lean) |
| [Prime counting (`primecount`)](rules/problems/primecount.md) | The number of primes up to n | [Submission](problems/primecount/Submission.lean) |
| [Matrix permanent (`permanent`)](rules/problems/permanent.md) | The permanent of a generated 0/1 matrix | [Submission](problems/permanent/Submission.lean) |
| [Rule 110 (`ca-rule110`)](rules/problems/ca-rule110.md) | Evolution of a seeded 256-cell cyclic row | [Submission](problems/ca-rule110/Submission.lean) |
| [SHA-256 (`sha256`)](rules/problems/sha256.md) | Repeated hashing of a 32-byte digest | [Submission](problems/sha256/Submission.lean) |
| [Polynomial discriminant (`polydisc`)](rules/problems/polydisc.md) | The exact discriminant of a generated monic degree-24 polynomial | [Submission](problems/polydisc/Submission.lean) |

There is also one [worked example](examples/README.md) per problem at
`examples/<id>/Submission.lean`.

## Submission

Submit one human-readable **`Submission.lean`** file, at most **1 MiB**, with a
total, kernel-reducible algorithm and proof in `namespace Submission`:

```text
impl : Nat → Output
impl_correct : ∀ n, impl n = spec n
```

Keep the starter's exact types and theorem statement. See the
[submission requirements](rules/problems/README.md#submission) and
[rules](rules/overview.md#rules).

## Scoring

Rank each problem by the sum of per-case median instruction counts over three
kernel replays, lowest first; equal totals tie. Correctness replay is verification
only. Only submissions passing every case and all required checks receive a total
and rank. See [Scoring](rules/problems/README.md#scoring) and
[Limits](rules/problems/README.md#limits).

## Repository layout

- `problems/<id>/`: participant packages.
- `evaluation/`: evaluator, fixed problem workspaces, and reproduction guide.
- `rules/`: competition policies and problem statements.
- `examples/<id>/Submission.lean`: complete worked examples.
- `scripts/`: setup, evaluation, and reporting utilities.
- `tests/harness_manifest.json`: expected example results for the image-build check.
- `results/`: local generated artifacts, not tracked by Git.
