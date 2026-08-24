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
Lean. It checks definitional equality by reducing expressions; when a proof
depends on a computed result, that computation becomes part of proof
verification.

The primary goal of the Lean Kernel Challenge is to bring the community
together to improve the performance of verified computation in the Lean
kernel. After each evaluation cohort closes, all results and benchmark data
from that cohort will be released publicly under an open license. Together with
the algorithms and representations developed through the challenge, this open
record will support the Lean community, contribute to Lean's continued
development, and allow Lean users worldwide to reproduce, reuse, and build on
the community's work.

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
number theory, combinatorics, cryptography, and discrete mathematics. Specific
problems will be announced at the official launch.

## Key Dates

- Registration and team formation open: **August 26, 2026**
- Official launch: **September 15, 2026, 12:00 UTC**
- Submission deadline: **November 15, 2026, 23:59 AoE (UTC−12)**

## Registration & Teams

Registration and team management take place on
[SAIR](https://competition.sair.foundation/). Participants must have a SAIR
account, complete the required profile information, and agree to the SAIR
competition terms before registering. They may compete individually or form a
team on SAIR.

## Official Repository & Playground

The official repository, SAIR Playground, and submission system will become
available at the official launch.
