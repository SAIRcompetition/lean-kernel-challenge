# Lean Kernel Challenge — Stage 1: Overview

*Stage 1 of a multi-stage competition on improving the performance of verified computation in the
Lean 4 kernel.*

## Co-organizers

Stage 1 of the Lean Kernel Challenge is co-organized by (in alphabetical order by surname):

- Joachim Breitner
- Leonardo de Moura
- Kim Morrison
- Terence Tao

The co-organizing institutions are [Lean FRO](https://lean-fro.org/) and the
[SAIR Foundation](https://sair.foundation/).

## Schedule

| | |
|---|---|
| **Stage** | Stage 1 (experimental) |
| **Status** | Pre-launch — submissions open September 15, 2026 |
| **Registration and team formation** | Opens August 26, 2026 |
| **Official launch** | September 15, 2026, 22:00 PT (America/Los_Angeles), equivalent to September 16, 2026, 05:00 UTC; tentative and subject to change |
| **Submission deadline** | November 20, 2026, 23:59 AoE (UTC−12) |
| **Final evaluation** | After the submission deadline; evaluation window to be announced |
| **Final results publication** | After final evaluation completes; publication date and time to be announced |
| **Stage 2** | Begins December 2026; the exact date will be announced |
| **Submission platform** | [SAIR](https://competition.sair.foundation/) |

Formal submissions and the SAIR Playground open together at the official launch. The time
above is tentative; any revision will be announced before opening.

---

## Background

The Lean Kernel Challenge is a competition series that brings the community together to
improve the performance of verified computation in the Lean kernel.

Stage 1 is the first, experimental stage of the series. It begins with a set of fundamental
computational problems. Later stages will cover a broader range of mathematical and scientific
fields and more complex problems.

The Lean 4 kernel is the trusted component that checks every proof accepted by Lean. It checks
definitional equality by reducing expressions; when a proof depends on a computed result, that
computation becomes part of proof verification.

The challenge asks how algorithms and representations can reduce the kernel work required to
verify such computations.

## Task

Each problem provides a trusted specification `spec : Nat → Output`, where `Output` is
the problem-specific output type. For `fib`, the spec is Mathlib v4.33.1's `Nat.fib`
from `Mathlib.Data.Nat.Fib.Basic`; see its [official API and pinned source](problems/fib.md#mathlib-specification).
The other seven scored tasks use their repository-defined core-Lean specs. Participants submit:

1. an implementation `impl : Nat → Output` optimized for kernel verification; and
2. a proof `impl_correct : ∀ n, impl n = spec n`.

The judge first checks the proof of correctness. It then measures the work performed by a pinned
Lean kernel when replaying the complete verified correctness artifact and checking `impl` at
hidden, judge-selected inputs.

Because correctness holds for every input, the judge may select any input allowed by the published
evaluation policy. Hardcoded tables and special cases are permitted when covered by the universal
proof. Their correctness replays must satisfy the resource limits, and their instruction costs
enter ranking according to the problem's declared work policy. See
[`evaluation.md`](evaluation.md) for the common measurement rules and
[`problem-scoring.md`](problem-scoring.md) for the eight independent leaderboards.

## Submission

Submit exactly one **`Submission.lean`** file, at most **1 MiB**. It must contain `impl`,
`impl_correct`, and every helper you add, all inside `namespace Submission`.
You may also use the locked workspace's library declarations. All other workspace files are locked.

The trusted files (`Spec.lean`, `Challenge.lean`, `Solution.lean`, and `config.json`) are fixed,
and the judge supplies its own copies. For all eight scored tasks, these live
in `evaluation/problems/<id>/`, separately from the runnable participant package in
`problems/<id>/`. Core-Lean participant packages include a generated fixed Spec copy;
fib imports Mathlib directly. The simplest valid submission defines `impl` as the trusted
specification and proves correctness with `rfl`. This adds no optimization and does not
guarantee that every performance case passes within its limits.

Formal submissions may be repeated before the cutoff. Daily mode limits are **2 Standard runs**
and **5 Light runs**, with the UTC day resetting at 00:00 UTC. Before launch, the organizers will
clarify whether allowances apply per team across all problems or per team/problem, whether formal
submissions share the Standard allowance, and how failures or cancellations affect usage.

Each formal submission is stored as a new immutable record. At the cutoff,
the platform selects each team's latest formal submission for each problem, based on the time it
was recorded by the platform before the deadline. This selection does not fall back to an older
submission if the latest submission is rejected or unscored. Pending evaluation or infrastructure
retries apply to the selected submission and do not change that selection.

Source availability or integrity-check results must not change which submission is selected.
If the stored source is missing, unreadable, or fails integrity verification, preserve the
selected submission's identity and record a platform error. Do not omit the team/problem or substitute an older
submission. The final selection is not completely frozen until the original formal source is
recovered and verified against its original manifest and hash. Later Playground edits or
post-deadline submissions cannot replace it.

## Local development

For all eight tasks, run `lake build` inside `problems/<id>/`; fib alone
needs `python3 setup.py` first. No evaluation tools are needed. See the
[participant guide](problems/README.md). Building compiles your definitions and proofs; it does not independently
check the official interface or permitted axioms, benchmark, or score the submission.

## Rules

Participation is also subject to the team, anti-cheating, and participant-cost policies in
[`prelaunch.md`](prelaunch.md).

- **R1 — Submission format.** Submit exactly one `Submission.lean` file, at most 1 MiB. All other
  workspace files are locked.
- **R2 — Reducible total function.** `impl` must be total, use only the dependencies supplied by
  the locked problem workspace, and be reducible by the kernel to an output literal for every
  input. `fib` includes the pinned Mathlib Fibonacci import closure described in its
  [problem statement](problems/fib.md); the other seven scored tasks remain core-Lean-only.
  It may not be `partial` or
  `unsafe`. Well-founded recursion is permitted only if the resulting definition remains
  kernel-reducible.
- **R3 — Universal correctness.** `impl_correct` must prove `∀ n, impl n = spec n`.
- **R4 — Standard axioms only.** The proof may depend only on `propext`, `Quot.sound`, and
  `Classical.choice`; `sorry` and `native_decide` are rejected.
- **R5 — Kernel replay is scored.** A complete pass of every hidden case earns 100 points;
  any failed case gives an otherwise scoreable submission 0 points and infinite ranking cost.
  Full-plan passes compete on the problem's declared instruction cost. The judge measures
  the complete verified correctness artifact and successful generated checks at hidden inputs.
  Parsing, dependency loading, and process startup are not counted. See
  [`evaluation.md`](evaluation.md) and [`problem-scoring.md`](problem-scoring.md) for the exact
  contracts.

> Compiled execution, including `#eval`, does not predict kernel-reduction performance.
> Use the optional [local evaluator](../evaluation/README.md) for wall-time checks
> that follow the judge's measurement boundary. These are not official scores.

## Stage 1 Problems

Stage 1 begins with eight computational problems from algebra, number theory, combinatorics,
cryptography, discrete mathematics, and related fields. Their public definitions and scoring
groups are listed in [`problem-scoring.md`](problem-scoring.md).
See the [Problem Statements](problems/README.md) for each problem's description, input and
output formats, examples, constraints, submission requirements, and local development steps.

## Status

Stage 1 is scheduled to launch at the tentative time in the schedule above, with formal submissions open from launch
until the deadline above.
All problem workspaces compile, and the judge runs the correctness and grouped performance
pipeline end to end. The eight per-problem group schedules and scoring rules are published in
[`problem-scoring.md`](problem-scoring.md); there is no cross-problem total. The organizers
must validate the complete production evaluation on the pinned PMU hardware and isolated container
environment before launch.
