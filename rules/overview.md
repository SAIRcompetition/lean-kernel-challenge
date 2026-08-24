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

| | |
|---|---|
| **Stage** | Stage 1 (experimental) |
| **Status** | Pre-launch |
| **Registration and team formation** | Opens August 26, 2026 |
| **Official launch** | September 15, 2026 |
| **Submission deadline** | November 20, 2026, 23:59 AoE (UTC−12) |
| **Stage 2** | Begins December 2026 (exact date TBD) |
| **Submission platform** | [SAIR](https://competition.sair.foundation/) |

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

Each problem provides a trusted core-Lean specification `spec : Nat → Output`, where `Output` is
the problem-specific output type. Participants submit:

1. an implementation `impl : Nat → Output` optimized for kernel verification; and
2. a proof `impl_correct : ∀ n, impl n = spec n`.

The judge first checks the proof of correctness. It then measures the work performed by a pinned
Lean kernel when replaying the complete verified correctness artifact and checking `impl` at
hidden, judge-selected inputs.

Because correctness holds for every input, the judge may select any input. Hardcoded tables and
special cases are permitted, but their proof and replay costs count toward the score. See
[`evaluation.md`](evaluation.md) for the complete measurement and ranking rules.

## Submission

Submit exactly one **`Submission.lean`** file, at most **1 MiB**. It must contain `impl`,
`impl_correct`, and every helper definition or lemma used by the proof, all inside
`namespace Submission`. All other workspace files are locked.

The trusted files (`Spec.lean`, `Challenge.lean`, `Solution.lean`, and `config.json`) are fixed,
and the judge supplies its own copies. The simplest valid submission defines `impl` as the trusted
specification and proves correctness with `rfl`. It is correct but intentionally slow.

## Rules

Participation is also subject to the team, anti-cheating, and participant-cost policies in
[`prelaunch.md`](prelaunch.md).

- **R1 — Submission format.** Submit exactly one `Submission.lean` file, at most 1 MiB. All other
  workspace files are locked.
- **R2 — Reducible total function.** `impl` must be total, written in core Lean without Mathlib,
  and reducible by the kernel to an output literal for every input. It may not be `partial` or
  `unsafe`. Well-founded recursion is permitted only if the resulting definition remains
  kernel-reducible.
- **R3 — Universal correctness.** `impl_correct` must prove `∀ n, impl n = spec n`.
- **R4 — Standard axioms only.** The proof may depend only on `propext`, `Quot.sound`, and
  `Classical.choice`; `sorry` and `native_decide` are rejected.
- **R5 — Kernel replay is scored.** Ranking uses completed input slots and measured kernel work.
  Scored work includes the complete verified correctness artifact and the successful generated
  checks at judge-selected inputs. Parsing, dependency loading, and process startup are not
  counted. See [`evaluation.md`](evaluation.md) for the exact ranking contract.

> `#eval` measures compiled execution and does not predict kernel-reduction performance. Use
> `scripts/perf_eval.py` for local checks that follow the judge's measurement boundary.

## Stage 1 Problems

Stage 1 begins with fundamental computational problems from algebra, number theory,
combinatorics, cryptography, discrete mathematics, and related fields. The specific problems will
be announced at the official launch.

## Status

Stage 1 is in pre-launch. All problem workspaces compile, and the judge runs the correctness and
performance pipeline end to end. Before the official launch, the organizers will finalize the
official input ranges, evaluation method, and cross-problem scoring formula, validate the
official evaluation hardware, and publish the final rules.
