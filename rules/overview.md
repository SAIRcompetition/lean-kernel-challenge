# Lean Kernel Challenge

*A multi-stage competition on improving the performance of verified computation
in the Lean 4 kernel.*

## Co-organizers

Stage 1 is co-organized by (in alphabetical order by surname):

- Joachim Breitner
- Leonardo de Moura
- Kim Morrison
- Terence Tao

The co-organizing institutions are [Lean FRO](https://lean-fro.org/) and the
[SAIR Foundation](https://sair.foundation/).

<p align="center">
  <a href="https://lean-fro.org/"><img src="assets/lean-fro-logo.svg" alt="Lean FRO" width="260"></a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://sair.foundation/"><img src="assets/sair-foundation-logo.png" alt="SAIR Foundation" width="260"></a>
</p>

## Background

The Lean Kernel Challenge brings the community together to develop faster algorithms
and better representations for verified computation. Through these collective
contributions, the competition aims to support Lean's development and benefit
Lean users worldwide.

Verified computation uses the Lean kernel to check computational results as part
of a proof. Stage 1 is the first, experimental stage of the series, beginning with
fundamental problems. Later stages will cover a broader range of mathematical and
scientific fields and more complex problems.

We acknowledge the
[Lean Kernel Arena](https://github.com/leanprover/lean-kernel-arena), which informed
the challenge's design. Arena benchmarks alternative Lean proof checkers; Stage 1
instead optimizes algorithms for fixed computational tasks, with correctness
proved against supplied specifications and computation measured using a fixed kernel.

## Problems

Stage 1 has eight problems covering algebra, number theory, combinatorics,
cryptography, and discrete mathematics. Each provides a trusted Lean specification.
Participants optimize an implementation and prove that it matches the specification
for every input.

Find the [problem statements, test groups, and scoring rules](problems/README.md)
in `rules/problems/`, the [participant templates](../problems/) in `problems/`,
and [one complete example submission per problem](../examples/README.md) in
`examples/<problem>/Submission.lean`.

## Key Dates

- Stage 1 registration and team formation open: **August 26, 2026**
- Stage 1 official launch: **September 15, 2026**
- Stage 1 submission deadline: **November 20, 2026, 23:59 AoE (UTC−12)**
- Stage 2 begins: **December 2026**; the exact date will be announced

## Registration & Teams

Register individually or as a team on [SAIR](https://competition.sair.foundation/).
Participants must have a SAIR account, complete the required profile information,
and agree to the SAIR competition terms before registering for Stage 1.

## Official Repository & Playground

The official repository is
[SAIRcompetition/lean-kernel-challenge](https://github.com/SAIRcompetition/lean-kernel-challenge).
The SAIR Playground and submission system open together on
[SAIR](https://competition.sair.foundation/) at the Stage 1 official launch.
Playground runs and edits do not constitute or replace a formal submission.

Playground Standard mode allows **2 runs per day**, resetting at 00:00 UTC.
Before launch, organizers will clarify whether this limit applies per team or
per team/problem, whether formal submissions share the Standard allowance, and
how failures or cancellations affect usage.

## Submission

For each problem, submit one **`Submission.lean`** file, at most **1 MiB**, containing:

- `impl`: your algorithm.
- `impl_correct`: a complete Lean proof that the algorithm matches the problem's
  fixed specification for every input.

Keep these declarations and any helpers in `namespace Submission`, and leave the
fixed specification and environment files unchanged. See the
[quick start](../README.md#quick-start) and
[exact submission interface](problems/README.md#submission).

Formal submissions may be updated before the cutoff. For each team and problem,
the latest formal submission by recorded submission time is selected, even if an
older submission performed better. A rejected, unscored, or failed latest entry
does not restore an older result. Post-deadline submissions cannot replace the
selected entry.

## Rules

- **R1 — Format.** Submit only the single file described above; keep the fixed workspace unchanged.
- **R2 — Computation.** Use a total, kernel-reducible implementation and only the locked
  dependencies. `partial` and `unsafe` are not permitted. Well-founded recursion is
  allowed only when the result remains kernel-reducible to an output literal.
- **R3 — Correctness.** Provide a complete, kernel-checked proof of
  `∀ n, impl n = spec n`. Passing test cases is not a substitute for this proof.
- **R4 — Proof restrictions.** Submissions using `sorry`, `admit`, `native_decide`,
  or unapproved axioms are rejected.
- **R5 — Ranking.** Rank by computation instructions only. Correctness-proof checking
  never contributes to the total or breaks ties.

Different algorithms, representations, hardcoded tables, and special cases are
allowed when covered by the universal proof. All implementations and proofs must
still satisfy the published resource limits. Inputs are selected under the
published problem policy.

## Evaluation

A submission is **Accepted** after its interface, universal proof, and permitted
axioms pass verification. Each problem has an independent leaderboard. Report each
test case's median computation instruction count over three kernel replays; rank
complete passes by their sum, lowest first. Equal totals tie. Correctness-replay
measurements are reported separately, for verification only.

An Accepted submission with incomplete verification or a failed performance case
has no complete total or rank. Daily standings are provisional and publish only
complete editions; final results use a separate evaluation after the deadline.

See [Evaluation](evaluation.md) for measurement boundaries, Lean and hardware
specifications, resource limits, local deployment, and publication procedures.
Official use requires the [deployment checks](problems/README.md#implementation-status)
and production-host validation. Local wall-time checks are not
official instruction-count rankings.

## Team Participation and Anti-Cheating Policy

- Each individual or organization can participate in only one team.
- Teams must register members and sponsors in advance.
- If coordinated cheating is detected (including sockpuppet teams), all related teams will be disqualified.

## Experimental Status

Stage 1 of the Lean Kernel Challenge is experimental. Participants are
responsible for any computing costs they incur while developing, testing,
submitting, or otherwise participating in Stage 1. The co-organizers do not
reimburse these costs.

## Community Feedback

Community feedback and contributions are welcome. Join the
[SAIR Foundation Zulip community](https://zulip.sair.foundation/) for discussion
and collaboration.
