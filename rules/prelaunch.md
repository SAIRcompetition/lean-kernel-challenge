# Lean Kernel Challenge — Pre-launch & Registration

*A competition on the performance of verified computation in the Lean 4 kernel.*

## Co-organizers

The Lean Kernel Challenge is co-organized by:

- Joachim Breitner
- Leonardo de Moura
- Kim Morrison
- Terence Tao
- [Lean FRO](https://lean-fro.org/)
- [SAIR Foundation](https://sair.foundation/)

<p align="center">
  <a href="https://lean-fro.org/"><img src="../assets/lean-fro-logo.svg" alt="Lean FRO" width="260"></a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://sair.foundation/"><img src="../assets/sair-foundation-logo.png" alt="SAIR Foundation" width="260"></a>
</p>

## Background

The Lean 4 kernel is the small trusted core that type-checks every proof the
system accepts. Type-checking includes definitional-equality checking, which
the kernel discharges by reduction — so when a proof depends on a computed
result, verifying the proof and performing the computation are one and the
same operation. This makes the kernel a well-defined, deterministic model of
computation with its own performance characteristics, and raises a concrete,
largely unstudied question:

> **How efficiently can a computation be expressed so that the kernel
> *verifies* it, and which algorithmic and encoding techniques scale within
> the kernel's reduction model?**

The Lean Kernel Challenge is a competition on exactly this question. Each
problem provides a trusted specification; you submit a **function** (your fast
algorithm) together with a **machine-checked proof** that it agrees with the
specification on *every* input. What is scored is not how fast your compiled
code runs — the official Lean kernel replays your submission, and the kernel's
own work is measured. Stronger algorithms and kernel-friendly encodings win;
bypassing the computation is impossible, because the measurement *is* the
proof check.

No prior familiarity with the problem domains is needed or revealed here: the
problem set is published at the official launch. Until then, the shape above —
one function, one `∀`-proof, kernel replay as the metric — is everything a
team needs to know to prepare.

## Key Dates

- Pre-registration and team formation open: **August 26, 2026**
- Official launch — problems, binding rules, and judge published: **September 15, 2026, 12:00 UTC**
- Submission deadline: **November 15, 2026, 23:59 AoE**

## Registration & Teams

Registration and team management take place on
[SAIR](https://competition.sair.foundation/) beginning August 26. To register,
create or sign in to your SAIR account, complete the required profile and
participant information, and agree to SAIR's competition terms. You may
participate individually or as a team; teams can be formed and named from
registration onward. Team composition and size rules are stated on the
competition page.

## What you can do now

- Install [Lean 4](https://lean-lang.org/) and get comfortable with core-Lean
  programming (the competition pins a specific toolchain, announced at
  launch).
- Build intuition for the kernel's reduction model. A caution that will save
  you time later: `#eval` runs *compiled* code, while the judge measures
  *kernel reduction* — the two can diverge exponentially, in both directions.
- Form your team, and watch the competition page for launch-day announcements.

## Prizes

To be announced before launch.

## Official Repository

The official repository — locked problem workspaces, the judge, worked
examples, and the binding rule texts — will be published at the official
launch on September 15, 2026.
