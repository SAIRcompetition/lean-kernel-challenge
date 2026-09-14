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

## Problems

Stage 1 has eight problems covering algebra, number theory, combinatorics,
cryptography, and discrete mathematics. Each provides a trusted Lean specification.
Participants optimize an implementation and prove that it matches the specification
for every input.

See [Problems and Scoring](problems/README.md) for the eight statements,
specifications, test groups, starter code, and scoring details.

## Key Dates

- Stage 1 registration and team formation open: **August 26, 2026**
- Stage 1 official launch: **September 15, 2026, 22:00 PT (America/Los_Angeles)**, equivalent to September 16, 2026, 05:00 UTC; tentative and subject to change
- Stage 1 submission deadline: **November 20, 2026, 23:59 AoE (UTC−12)**
- Stage 1 final evaluation: after the submission deadline; evaluation window to be announced
- Stage 1 final results publication: after final evaluation completes; publication date and time to be announced
- Stage 2 begins: **December 2026**; the exact date will be announced

Any change to the tentative launch time will be announced before opening.

## Registration & Teams

Register individually or as a team on [SAIR](https://competition.sair.foundation/).
Participants must have a SAIR account, complete the required profile information,
and agree to the SAIR competition terms before registering for Stage 1.

## Official Repository & Playground

The official repository is
[SAIRcompetition/lean-kernel-challenge](https://github.com/SAIRcompetition/lean-kernel-challenge).
The SAIR Playground and submission system open together on
[SAIR](https://competition.sair.foundation/) at the Stage 1 official launch.

## Submission

Submit one **`Submission.lean`** file, at most **1 MiB**. All other workspace files
are locked. The [participant quick start](../README.md#quick-start) explains local
builds; [submission requirements](problems/README.md#submission) give the exact
interface, namespace, and permitted dependencies.

Formal submissions may be updated before the cutoff. For each team and problem,
the latest formal submission by recorded submission time is selected, even if an
older submission performed better. A rejected, unscored, or failed latest entry
does not restore an older result. Later Playground edits and post-deadline
submissions cannot replace the selected entry.

Standard mode allows **2 runs per day**, resetting at 00:00 UTC. Before launch,
organizers will clarify whether this limit applies per team or per team/problem,
whether formal submissions share the Standard allowance, and how failures or
cancellations affect usage.

## Rules

- **R1 — Format.** Submit only the single file described above; keep the fixed workspace unchanged.
- **R2 — Computation.** Use a total, kernel-reducible implementation and only the locked
  dependencies. `partial` and `unsafe` are not permitted. Well-founded recursion is
  allowed only when the result remains kernel-reducible to an output literal.
- **R3 — Correctness.** Prove `∀ n, impl n = spec n`, not just correctness on test cases.
- **R4 — Axioms.** Only `propext`, `Quot.sound`, and `Classical.choice` are permitted;
  `sorry` and `native_decide` are not accepted.
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

## Open Source

After Stage 1's final official evaluation, its seed, exact input plan, results,
and benchmark data will be released under an open-source license. Together with
the algorithms and representations developed through the challenge, this record
will support reproducible work and further contributions by the community.

Participant code remains private during Stage 1 and will be published afterward.
The covered submission versions, code license, and authorization terms will be
announced before launch; the repository license does not determine the license
of platform submissions.

## Team Participation and Anti-Cheating Policy

- Each individual or organization can participate in only one team. The organizers
  will clarify the organizational unit before launch, including how independent
  teams sharing a university or parent institution are treated.
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
