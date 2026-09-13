# Lean Kernel Challenge — Stage 1: Overview

*Stage 1 of a multi-stage competition on improving the performance of verified computation in the
Lean 4 kernel.*

The [competition introduction](prelaunch.md) lists the co-organizers,
institutions, participation policies, and community links.

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

The Lean Kernel Challenge brings the community together to improve verified
computation in the Lean kernel. This first, experimental stage begins with
fundamental problems; later stages will cover broader and more complex fields.

The Lean 4 kernel is the trusted component that checks every proof accepted by Lean. It checks
definitional equality by reducing expressions; when a proof depends on a computed result, that
computation becomes part of proof verification.

The challenge asks how algorithms and representations can reduce the kernel work required to
verify such computations.

## Task

Each problem provides a trusted `spec : Nat → Output`. Participants submit:

1. an implementation `impl : Nat → Output` optimized for kernel verification; and
2. a proof `impl_correct : ∀ n, impl n = spec n`.

The [problem guide](problems/README.md#submission) gives the exact output types,
declaration names, fixed files, dependencies, and axiom policy.

The judge first checks the universal correctness proof, interface, and permitted axioms.
Only submissions that pass are marked **Accepted** and proceed to performance evaluation.
For each test input, the judge records the kernel instruction count for computing `impl`.
Each problem ranks complete results by the sum of those counts, lowest first;
correctness-proof checking is excluded.

Because correctness holds for every input, the judge may select any input allowed by the published
evaluation policy. Hardcoded tables and special cases are permitted when covered by the universal
proof. Correctness checks must satisfy their resource limits, but their instruction
counts do not contribute to ranking. See the
[evaluation process](evaluation.md#evaluation-process) and unified
[problem and scoring guide](problems/README.md#scoring).

## Submission

Submit exactly one **`Submission.lean`** file, at most **1 MiB**. See the
[shared submission requirements](problems/README.md#submission); all other
workspace files are locked.

Formal submissions may be repeated before the cutoff. Daily mode limits are **2 Standard runs**
and **5 Light runs**, with the UTC day resetting at 00:00 UTC. Before launch, the organizers will
clarify whether allowances apply per team across all problems or per team/problem, whether formal
submissions share the Standard allowance, and how failures or cancellations affect usage.

Each formal submission is a new immutable record. At a cutoff, the platform
selects each team's latest formal submission per problem by its recorded time.
A newer rejected, unscored, or terminal-error submission replaces an older
success; evaluation status and retries do not change the selection.

Source availability and integrity checks cannot change that identity. If source
is missing, unreadable, or fails verification, preserve the selected identity
and record a platform error; do not omit it or restore an older entry. Final
selection is fully frozen only after the original source is recovered and
verified against its original manifest and hash. Later Playground edits and
post-deadline submissions cannot replace it.

## Evaluation and results

During the submission window, the platform may publish a daily provisional board
using separate hidden reference inputs, which organizers may update between
editions and need not later publish. The board updates once per day, not in real
time. Each UTC day runs from 00:00:00 through
23:59:59, including the whole final second (00:00 inclusive to the next 00:00
exclusive). The latest formal submission recorded by that cutoff is selected as
described above, and that selected identity is then fixed for the edition. Each
edition identifies its cutoff or coverage date and displays
its generation timestamp and time zone. Publication lag and missed-edition handling
will be announced before launch. A cutoff selects an entry; it does not promise
that evaluation or publication finishes then. Neither cutoff nor publication time
shortens an evaluation resource limit.

An edition is complete only when every selected submission has a trusted terminal
outcome: accepted, rejected, or an explicitly classified judge or infrastructure
error. Queued, running, retrying, missing, and unknown outcomes remain unfinished;
a failed attempt with a pending retry is not terminal. Elapsed time, missing
metrics, or an approaching publication time cannot make one terminal. A terminal error counts as
processed but receives no total, public board row, or rank and remains subject to
organizer review and recovery. The affected team can privately query a sanitized
status and reason without disclosure of hidden inputs or secrets. Other rejected
or accepted-but-unscored selections likewise do not restore an older result or
create a public failure row; only rankable results appear on the board.

An incomplete edition is never published. The previous complete edition remains
visible with a delay notice; before the first complete edition, the board says it
is being prepared. The last provisional edition may remain after the deadline with
a final-evaluation notice. Complete editions are published without raw verdicts,
hidden inputs, or secrets.

Final results come from a separate cohort evaluated as a batch after the submission
deadline, using the same latest-recorded selection rule. Raw verdicts, exact inputs,
and contestant code remain private during evaluation; no fixed evaluation duration
is promised. An incomplete final run must
be re-evaluated, with fatal evaluator errors reviewed first. Once the cohort closes,
its seed, exact input plan, results, and benchmark data are released under an
open-source license. Contestant code is published afterward under the version and
licensing terms announced before launch. A deliberate re-evaluation uses a new
hidden seed and cohort and rescores the comparison set.

## Local development

Follow the repository [quick start](../README.md#quick-start). Building compiles
definitions and proofs; it does not independently check acceptance or produce an
official benchmark.

## Rules

Participation is also subject to the team, anti-cheating, and participant-cost policies in
[`prelaunch.md`](prelaunch.md).

- **R1 — Submission format.** Submit exactly one `Submission.lean` file, at most 1 MiB. All other
  workspace files are locked.
- **R2 — Reducible total function.** `impl` must be total, use only the dependencies supplied by
  the locked problem workspace, and be reducible by the kernel to an output literal for every
  input. Fib, Mertens, and prime counting include the pinned Mathlib import closures
  described in their [problem statements](problems/README.md); the other five tasks
  remain core-Lean-only.
  It may not be `partial` or
  `unsafe`. Well-founded recursion is permitted only if the resulting definition remains
  kernel-reducible.
- **R3 — Universal correctness.** `impl_correct` must prove `∀ n, impl n = spec n`.
- **R4 — Standard axioms only.** The proof may depend only on `propext`, `Quot.sound`, and
  `Classical.choice`; `sorry` and `native_decide` are rejected.
- **R5 — Computation instructions determine rank.** Each problem lists every test case's
  outcome and computation instruction count, the median of three kernel replays.
  Complete results rank by the sum of all case counts, lowest first; equal totals tie.
  Correctness-proof checking is neither added nor used to break ties. A performance
  failure leaves an Accepted submission without a complete total or rank.
  Parsing, dependency loading, and process startup are not counted. See the
  [evaluation process](evaluation.md#evaluation-process) and
  [scoring rules](problems/README.md#scoring) for the exact contracts.

> Compiled execution, including `#eval`, does not predict kernel-reduction performance.
> Use the optional [local evaluator](../evaluation/README.md) for wall-time checks
> that follow the judge's measurement boundary. These are not official scores.

## Stage 1 Problems

Stage 1 begins with eight problems from algebra, number theory, combinatorics,
cryptography, and discrete mathematics. The [problem guide](problems/README.md)
contains their definitions, scoring groups, statements, constraints, and local
development steps.

## Status

Formal submissions are scheduled to run from the tentative launch through the
deadline above. The workspaces and existing evaluation pipeline run end to end,
but the revised ranking rule still requires the
[listed implementation changes](problems/README.md#implementation-status). Before
launch, the organizers must validate the complete production evaluation on the
pinned PMU hardware and isolated container environment.
