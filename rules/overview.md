# Lean Kernel Challenge — Overview

*A competition on the performance of verified computation in the Lean 4 kernel.*

**Co-organized by** Joachim Breitner, Leonardo de Moura, Kim Morrison, and Terence Tao —
with the **Lean FRO** and the **SAIR Foundation**.

| | |
|---|---|
| **Stage** | Stage 1 — Kernel Computation Track |
| **Status** | Pre-launch draft (rules R1–R6 stable; scoring & logistics TBD) |
| **Start** | 2026-09-01 |
| **End** | TBD |
| **Prizes** | TBD |
| **Submission platform** | TBD |

---

## Background

The Lean 4 kernel is the trusted core that type-checks every proof the system accepts.
Type-checking includes definitional-equality checking, which the kernel discharges by reduction
(β/δ/ι reduction and evaluation to weak head normal form). When a proof depends on a computed
result — for instance an equation `f x = y` closed by `rfl` — the kernel establishes it by
reducing `f x`. Verifying such a proof and performing the computation are therefore one and the
same operation.

This makes the kernel a well-defined, deterministic model of computation with its own
performance characteristics: reduction is call-by-name, natural-number literals are backed by GMP
with a fixed set of native `Nat` operations, and evaluation strategy, term representation, and
sharing all bear directly on cost. The challenge asks a concrete, largely unstudied question:

> **How efficiently can a computation be expressed so that the kernel *verifies* it, and which
> algorithmic and encoding techniques scale within the kernel's reduction model?**

The [Lean Kernel Arena](https://arena.lean-lang.org/) measures kernel *implementations*; this
competition fixes the official kernel as the judge and has submissions compete on how few
instructions it takes to check them. Speed alone is not the objective — every answer must carry a
machine-verifiable Lean proof of correctness, so progress comes from stronger algorithms and
kernel-level encodings rather than from bypassing the computation.

## The task

Each problem gives you a **trusted spec** — a deliberately naive but correct definition in core
Lean (e.g. the partition function `p(n)`) — and a specific instance. You must:

1. **compute the answer**, and
2. **prove it correct** against the spec.

What is timed is **how many instructions the official Lean kernel spends re-checking your proof**
— because to check it, the kernel is forced to carry out the computation. Lower is better. See
[`evaluation.md`](evaluation.md) for exactly how judging and scoring work.

## What you submit

One file, **`Submission.lean`** (optionally with helper files under `Submission/`). Nothing else.
You fill two holes in a locked workspace:

```lean
namespace Submission

def answer : Nat := 37338                                   -- ① the computed value (a literal)

theorem answer_correct :                                    -- ② its proof of correctness
    partitionSpec partitionInstance = answer := by
  ...                                                       -- your fast algorithm, proved equal
                                                            --   to the spec, checked by the kernel

end Submission
```

The trusted files (`Spec.lean`, `Challenge.lean`, `Solution.lean`, `config.json`) are fixed; the
judge supplies its own copies.

## Rules

- **R1 — Locked files.** You may edit only `Submission.lean` and files you add under
  `Submission/`. The trusted files are fixed; the judge ignores any changes to them.
- **R2 — The answer is a literal.** `Submission.answer` must elaborate to a raw numeral literal
  (e.g. `37338`, or a negative `Int` where the answer type is `Int`), not a compound expression
  like `partitionSpec partitionInstance` (which would hold by `rfl` with zero computation).
- **R3 — Standard axioms only.** `answer_correct` may depend only on `propext`, `Quot.sound`,
  `Classical.choice`. `native_decide` (per-computation axioms) and `sorry` (`sorryAx`) are
  rejected.
- **R4 — Only kernel checking is scored.** How you find the proof is unconstrained; what is
  measured is the cost for the kernel to re-check it. There is no attempt to police whether the
  proof was "computed in the kernel" vs generated externally — that is not machine-decidable.
- **R5 — No Mathlib; core Lean only.** `Submission.lean` and `Submission/` may import the
  problem's provided modules and the Lean core library, but not Mathlib or any external
  dependency.
- **R6 — Total termination.** Every definition your proof depends on must be total. `partial`,
  `unsafe`, `@[extern]`, and `@[implemented_by]` are disallowed (the kernel does not reduce them
  anyway).

## Problems (Stage 1)

| Problem | What you compute | Instance |
|---|---|---|
| `fib` *(tutorial)* | a Fibonacci number | F(100000) |
| `partition` | the partition function p(n) | n = 40 |
| `mertens` | the Mertens function M(n) | n = 250 |
| `primecount` | the prime-counting function π(n) | n = 600 |
| `permanent` | the permanent of a 0/1 matrix | 7×7 |
| `saw` | count of self-avoiding walks on ℤ² | length 8 |
| `ca-rule110` | a Rule 110 automaton's state | 32 cells × 128 steps |

Each spec is intentionally naive: reducing it directly in the kernel is slow or infeasible, so
competitive submissions require both better algorithms and kernel-level encodings that reduce
efficiently. The worked `fib` example includes a linear loop and fast doubling; the latter is
checked roughly **12× faster**.

## Status

**Prototype / pre-launch.** The judging pipeline is complete and self-audited across three
security reviews (7 problems, 15 example submissions, green-gate harness). Not yet finalized: the
perf instruction-counting path and container isolation are implemented but not yet run on PMU
hardware; multi-tier / hidden instances and the scoring aggregation (best-N + relative placement)
are not built; prizes, the end date, and the submission platform are TBD. Rule text may still
change before launch.
