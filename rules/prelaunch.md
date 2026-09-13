# Lean Kernel Challenge — Stage 1

*Stage 1 of a multi-stage competition on improving the performance of verified
computation in the Lean 4 kernel.*

## Co-organizers

Stage 1 of the Lean Kernel Challenge is co-organized by (in alphabetical order
by surname):

- Joachim Breitner
- Leonardo de Moura
- Kim Morrison
- Terence Tao

The co-organizing institutions are [Lean FRO](https://lean-fro.org/) and the
[SAIR Foundation](https://sair.foundation/).

<p align="center">
  <a href="https://lean-fro.org/"><img src="../assets/lean-fro-logo.svg" alt="Lean FRO" width="260"></a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://sair.foundation/"><img src="../assets/sair-foundation-logo.png" alt="SAIR Foundation" width="260"></a>
</p>

## Background

The Lean Kernel Challenge is a competition series that brings the community
together to improve the performance of verified computation in the Lean
kernel.

Stage 1 is the first, experimental stage of the series. It begins with a set of
fundamental computational problems. Later stages will cover a broader range of
mathematical and scientific fields and more complex problems.

The Lean 4 kernel is the trusted component that checks every proof accepted by
Lean. It checks definitional equality by reducing expressions; when a proof
depends on a computed result, that computation becomes part of proof
verification.

After the final official evaluation phase, its results and benchmark data will be
released publicly under an open-source license. Together with the algorithms and
representations developed through the challenge, they will form a collective
contribution to Lean's development that the global Lean community can
reproduce, reuse, and build on. Contestant code will remain private during the
competition and will be published afterward. The submission versions covered,
code license, and applicable authorization terms will be specified before launch;
the repository license alone does not establish the license of platform submissions.

## Task

For each problem, the organizers provide a trusted Lean specification.
Participants submit:

1. an implementation optimized for kernel verification; and
2. a machine-checked proof that the implementation agrees with the
   specification on every input.

The judge first checks the proof of correctness for all inputs. Scoring
measures the work performed by a pinned Lean kernel when replaying the complete
verified correctness artifact and the generated checks for judge-selected
inputs.

The problem set spans areas of computational mathematics including algebra,
number theory, combinatorics, cryptography, and discrete mathematics. The eight
Stage 1 problems and their scoring groups are published in this repository
(see [`problem-scoring.md`](problem-scoring.md)); submissions open at the
official launch.

## Key Dates

- Registration and team formation open: **August 26, 2026**
- Official launch: **September 15, 2026, 22:00 PT (America/Los_Angeles)**, equivalent to September 16, 2026, 05:00 UTC; tentative and subject to change
- Submission deadline: **November 20, 2026, 23:59 AoE (UTC−12)**
- Final evaluation: after the submission deadline; evaluation window to be announced
- Final results publication: after final evaluation completes; publication date and time to be announced
- Stage 2 begins: **December 2026**; the exact date will be announced

The [overview schedule](overview.md#schedule) records these dates and pending announcements.

## Registration & Teams

Registration and team management take place on
[SAIR](https://competition.sair.foundation/). Participants must have a SAIR
account, complete the required profile information, and agree to the SAIR
competition terms before registering. They may compete individually or form a
team on SAIR.

## Official Repository & Playground

The official repository, SAIR Playground, and submission system will be available
on [SAIR](https://competition.sair.foundation/) from the official launch.

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
