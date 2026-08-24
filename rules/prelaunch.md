# Lean Kernel Challenge — Pre-launch & Registration

*A competition on the performance of verified computation in the Lean 4 kernel.*

## Co-organizers

**Individual co-organizers:** Joachim Breitner, Leonardo de Moura, Kim Morrison,
and Terence Tao.

**Co-organizing institutions:** [Lean FRO](https://lean-fro.org/) and the
[SAIR Foundation](https://sair.foundation/).

<p align="center">
  <a href="https://lean-fro.org/"><img src="../assets/lean-fro-logo.svg" alt="Lean FRO" width="260"></a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://sair.foundation/"><img src="../assets/sair-foundation-logo.png" alt="SAIR Foundation" width="260"></a>
</p>

## Background

The Lean 4 kernel is the trusted component that checks every proof accepted by
Lean. Some proofs require the kernel to reduce expressions when checking
definitional equality. When an equality depends on a computed value, this
reduction performs the computation as part of proof verification.

The primary goal of the Lean Kernel Challenge is to bring the community
together to improve the performance of verified computation in the Lean
kernel. The resulting algorithms, representations, and benchmarks form a
collective contribution to Lean's continued development.

## Task

For each problem, the organizers provide a trusted Lean specification.
Participants submit:

1. an implementation optimized for kernel verification; and
2. a machine-checked proof that the implementation agrees with the
   specification on every input.

The judge verifies the universal correctness proof. Scoring measures the work
performed by a pinned Lean kernel when it replays the verified correctness
artifact and checks the implementation at selected inputs. Compiled execution,
including `#eval`, is not the competition metric.

The problem set draws from algebra, number theory, combinatorics, cryptography,
discrete mathematics, and other areas of computational mathematics. The
specific problems will be announced at the official launch.

## Key Dates

- Registration and team formation open: **August 26, 2026**
- Official launch: **September 15, 2026, 12:00 UTC**
- Submission deadline: **November 15, 2026, 23:59 AoE**

## Registration & Teams

Registration and team management take place on
[SAIR](https://competition.sair.foundation/). To register, participants must
create a SAIR account, complete the required profile information, and agree to
the SAIR competition terms. Participants may compete individually or form a
team through the SAIR platform.

## Prizes

Prize details will be announced before the official launch.

## Official Repository & Playground

The official repository, SAIR Playground, and submission system will become
available at the official launch.
