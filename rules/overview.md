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

The judge then evaluates `impl` on inputs of its own choosing (possibly hidden, at several sizes)
and times **how many instructions the kernel spends reducing `impl n`**. Because correctness holds
for all n, the judge can pick any input; because inputs may be hidden and large, hardcoding or
table lookup is pointless — only a genuinely good general algorithm scales. Lower is better. See
`evaluation.md` for how judging and scoring work.

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

- **R1 — Locked files.** You may edit only `Submission.lean` and files under `Submission/`.
- **R2 — Total, core-Lean function.** `impl` must be total and structurally recursive (no
  `partial`, `unsafe`, `@[extern]`, `@[implemented_by]`), so the kernel can reduce it on any input.
- **R3 — Standard axioms only.** `impl_correct` may depend only on `propext`, `Quot.sound`,
  `Classical.choice`. `native_decide` and `sorry` are rejected.
- **R4 — No Mathlib; core Lean only.**
- **R5 — Prove correctness for all inputs.** `impl_correct` must have type `∀ n, impl n = spec n`,
  so the judge can evaluate `impl` at inputs you do not see.
- **R6 — Only kernel checking is scored.** How you find impl and its proof is unconstrained; what
  is measured is the cost for the kernel to reduce `impl n`.

> The earlier "answer must be a raw numeral literal" rule is retired — submissions are functions
> now, evaluated by the judge at inputs of its choosing, so there is nothing to hardcode.

## Problems (Stage 1)

Every problem is parametric in `n : Nat`; the judge evaluates `impl` along that axis.

| Problem | `impl n` computes | Naive spec cost |
|---|---|---|
| `fib` *(tutorial)* | the n-th Fibonacci number | exponential |
| `partition` | the partition function p(n) | ~p(n)·n |
| `mertens` | the Mertens function M(n) (Int) | quadratic |
| `primecount` | the prime-counting function π(n) | quadratic |
| `permanent` | the permanent of the n-th seeded 0/1 matrix | n! |
| `saw` | count of self-avoiding walks of length n on ℤ² | exponential |
| `ca-rule110` | a Rule 110 automaton's state after n steps | linear (list-based) |

Each spec is intentionally naive, so reducing it directly in the kernel blows up as n grows;
competitive submissions need a better algorithm *and* a kernel-friendly encoding. The worked `fib`
example ships baseline + fast doubling (with a full `∀ n` proof); on a mid-size n the naive spec
times out in the kernel while fast doubling is checked in well under a second.

## Status

**Prototype / pre-launch.** All 7 problems are functionalized and compile; the judging pipeline is
under active development. Not yet finalized: perf instruction-counting on real hardware; the scoring
aggregation (best-N + relative placement); the submission platform; prizes and end date. Rule text
may still change before launch.
