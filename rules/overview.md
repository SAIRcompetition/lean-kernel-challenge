# Lean Kernel Challenge — Overview

*A competition on the performance of verified computation in the Lean 4 kernel.*

**Co-organized by** Joachim Breitner, Leonardo de Moura, Kim Morrison, and Terence Tao —
with the **Lean FRO** and the **SAIR Foundation**.

| | |
|---|---|
| **Stage** | Stage 1 — Kernel Computation Track |
| **Status** | Pre-launch draft (rules stable; scoring & logistics TBD) |
| **Start** | 2026-09-01 |
| **End** | TBD |
| **Prizes** | TBD |
| **Submission platform** | TBD |

---

## Background

The Lean 4 kernel type-checks every proof the system accepts. Type-checking includes
definitional-equality checking, which the kernel discharges by reduction. When a proof depends
on a computed result, the kernel establishes it by reducing the computation — so verifying such
a proof and performing the computation are one and the same operation. This makes the kernel a
deterministic model of computation with its own performance characteristics, and raises a
concrete, largely unstudied question:

> **How efficiently can a computation be expressed so that the kernel *verifies* it, and which
> algorithmic and encoding techniques scale within the kernel's reduction model?**

## The task

Each problem provides a **trusted spec** — a deliberately naive but correct definition
`spec : Nat → Output` in core Lean. You submit:

1. a **function** `impl : Nat → Output` — your fast algorithm, and
2. a **proof** `impl_correct : ∀ n, impl n = spec n` — that it agrees with the spec on *every*
   input.

The judge then evaluates `impl` on a rotating hidden schedule and measures the kernel work needed
to replay the verified correctness export and reduce `impl n` at each sampled input. Correctness
for all `n` lets the judge choose any input; it does not make a proved table or special case
logically impossible. Such implementations are legal, but they must survive the hidden schedule
and all of their replay work is charged. See `evaluation.md` for the canonical ranking.

## What you submit

One file, **`Submission.lean`** (optionally with helpers under `Submission/`). You fill two holes
in a locked workspace:

```lean
namespace Submission

def impl : Nat → Nat := sorry                       -- ① your fast algorithm (a total function)

theorem impl_correct : ∀ n, impl n = fibSpec n :=   -- ② proof it equals the spec on every n
  sorry

end Submission
```

The trusted files (`Spec.lean`, `Challenge.lean`, `Solution.lean`, `config.json`) are fixed; the
judge supplies its own copies. The simplest submission is `impl := spec` with
`impl_correct := fun _ => rfl` — correct but slow, because the judge's kernel evaluation then runs
the naive spec. Beating that baseline is the whole game.

## Rules

A submission has two parts — a function `impl` and a proof `impl_correct` — and the rules follow
that shape: what you may edit, what `impl` must be, what `impl_correct` must prove, what the proof
may rely on, and what is scored.

- **R1 — Locked files.** You may edit only `Submission.lean` and files under `Submission/`.
- **R2 — `impl` is a total core-Lean function the kernel can reduce.** It must be total and in core
  Lean (no Mathlib), and the kernel must reduce `impl n` to a literal on any input. This is enforced
  by the model, not a stylistic rule: a `partial` or `unsafe` `impl` is opaque to the kernel, so it
  neither reduces to a value nor supports the `∀ n` proof; and `@[extern]` / `@[implemented_by]` are
  irrelevant, because the judge times the kernel's reduction of the *logical* definition — the
  compiled/native path is never used, so they give no advantage. Structural recursion is recommended
  (well-founded recursion also reduces in the kernel, but usually far more slowly).
- **R3 — `impl_correct` proves `∀ n, impl n = spec n`.** Correctness must hold for *every* input, so
  the judge can evaluate `impl` at inputs you do not see.
- **R4 — Standard axioms only.** The proof may depend only on `propext`, `Quot.sound`, and
  `Classical.choice`; `sorry` and `native_decide` are rejected.
- **R5 — Kernel replay is scored.** How you find `impl` and its proof is unconstrained. The score
  charges one replay of the comparator-verified correctness export plus the successful per-input
  replays that force the kernel to reduce `impl n`.

## Problems (Stage 1)

Every problem is parametric in `n : Nat`; the judge evaluates `impl` along that axis.

| Problem | `impl n` computes | Naive spec cost |
|---|---|---|
| `fib` *(tutorial)* | the n-th Fibonacci number | linear (`brecOn`) |
| `partition` | the partition function p(n) | ~p(n)·n |
| `mertens` | the Mertens function M(n) (Int) | quadratic |
| `primecount` | the prime-counting function π(n) | quadratic |
| `permanent` | the permanent of a deterministic n×n 0/1 matrix | n! |
| `saw` | count of self-avoiding walks of length n on ℤ² | exponential |
| `ca-rule110` | a Rule 110 automaton's state after n steps | linear (list-based) |

Each spec is intentionally naive, so reducing it directly in the kernel blows up as n grows;
competitive submissions need a better algorithm *and* a kernel-friendly encoding. The worked `fib`
example ships baseline + fast doubling (with a full `∀ n` proof); on a mid-size n the naive spec
times out in the kernel while fast doubling is checked in well under a second.

## Status

**Prototype / pre-launch.** All 7 problems are functionalized and compile; the judge runs the full
pipeline end-to-end — correctness gate plus a new-paradigm performance phase that times the kernel
reducing `impl n` at judge-chosen inputs into a scaling curve (local perf or the remote KTP/1
executor). Not yet finalized: perf instruction-counting on PMU hardware; the scoring aggregation
(best-N + relative placement); the submission platform; prizes and end date. Rule text may still
change before launch.
