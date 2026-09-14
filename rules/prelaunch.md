# Lean Kernel Challenge

*A multi-stage competition on improving the performance of verified computation
in the Lean 4 kernel.*

Stage 1 is the first, experimental stage of the series. This page covers its
registration, schedule, and participation policies.

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
of a proof. Stage 1 begins with fundamental computational problems. Later stages
will cover a broader range of mathematical and scientific fields and more complex
problems.

After Stage 1's final official evaluation, results and benchmark data will be
released under an open-source license. Together with the algorithms and
representations developed through the challenge, they will support reproducible
work and further contributions by the community.

Participant code remains private during Stage 1 and will be published afterward.
The covered submission versions, code license, and authorization terms will be
announced before launch; the repository license does not determine the license
of platform submissions.

## Stage 1 Task

For each problem, the organizers provide a trusted Lean specification.
Participants submit an optimized implementation and a machine-checked proof that
it matches the specification on every input.

A submission is Accepted after correctness verification. Each problem has its own
leaderboard, reporting each test case's computation instruction count. Complete
results rank by the sum of these counts, lowest first. Correctness-proof checking
does not contribute to ranking.

The eight Stage 1 problems cover algebra, number theory, combinatorics,
cryptography, and discrete mathematics. See [Problems and Scoring](problems/README.md)
for the specifications, test groups, and ranking rules.

## Key Dates

- Stage 1 registration and team formation open: **August 26, 2026**
- Stage 1 official launch: **September 15, 2026, 22:00 PT (America/Los_Angeles)**, equivalent to September 16, 2026, 05:00 UTC; tentative and subject to change
- Stage 1 submission deadline: **November 20, 2026, 23:59 AoE (UTC−12)**
- Stage 1 final evaluation: after the submission deadline; evaluation window to be announced
- Stage 1 final results publication: after final evaluation completes; publication date and time to be announced
- Stage 2 begins: **December 2026**; the exact date will be announced

The launch time is tentative; any change will be announced before opening.
See the [Stage 1 rules](stage1-rules.md) for submission and result-publication policies.

## Registration & Teams

Stage 1 registration and team management take place on
[SAIR](https://competition.sair.foundation/). Participants must have a SAIR
account, complete the required profile information, and agree to the SAIR
competition terms before registering. They may compete individually or form a
team on SAIR.

## Official Repository & Playground

The official repository, SAIR Playground, and submission system will be available
on [SAIR](https://competition.sair.foundation/) from the Stage 1 official launch.

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
