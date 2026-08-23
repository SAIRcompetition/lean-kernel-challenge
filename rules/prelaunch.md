# Lean Kernel Challenge — Pre-launch & Registration

*A competition on the performance of verified computation in the Lean 4 kernel.*

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

Pre-registration is open on the [SAIR competition
platform](https://competition.sair.foundation/) from August 26. You may
participate individually or as a team; teams can be formed and named from
pre-registration onward. Platform accounts are required for submission once
the competition launches; team composition and size rules are stated on the
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

## Co-organizers

The Lean Kernel Challenge is co-organized by (in alphabetical order by
surname):

- Joachim Breitner
- Leonardo de Moura
- Kim Morrison
- Terence Tao

The challenge is run in collaboration with the [Lean
FRO](https://lean-fro.org/) and organized by the [SAIR
Foundation](https://sair.foundation/).
