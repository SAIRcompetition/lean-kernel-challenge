# Lean Kernel Challenge Stage 1 — Overview

*Stage 1 of a multi-stage competition on the performance of verified computation in the Lean 4
kernel.*

**Individual co-organizers:** Joachim Breitner, Leonardo de Moura, Kim Morrison,
and Terence Tao.

**Co-organizing institutions:** [Lean FRO](https://lean-fro.org/) and the
[SAIR Foundation](https://sair.foundation/).

| | |
|---|---|
| **Stage** | Stage 1 — Kernel Computation Track |
| **Status** | Pre-launch; remaining scoring and logistics details will be finalized before launch |
| **Registration and team formation open** | 2026-08-26 |
| **Official launch** | 2026-09-15, 12:00 UTC |
| **Submission deadline** | 2026-11-15, 23:59 AoE (UTC−12) |
| **Submission platform** | [SAIR](https://competition.sair.foundation/) |

---

## Background

Lean Kernel Challenge Stage 1 is the Kernel Computation Track. Further stages will be announced
separately.

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

The judge then evaluates `impl` on a rotating hidden schedule. It charges one complete replay of
the verified correctness closure, then at each sampled input charges only replay of the generated
target declaration that reduces `impl n`. Process startup, export parsing, and per-input dependency
preloading are outside the counter. Correctness for all `n` lets the judge choose any input; it
does not make a proved table or special case logically impossible. Such implementations are legal,
but they must survive the hidden schedule and their scored replay work is charged. See
`evaluation.md` for the canonical measurement contract and ranking.

## What you submit

Exactly one file, **`Submission.lean`**, at most **1 MiB**. Every lemma your proof needs lives in
that file, inside `namespace Submission` — there is no separate helper module to manage. You fill
two holes in a locked workspace:

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

Participation is also subject to the team, anti-cheating, and participant-cost policies in
[`prelaunch.md`](prelaunch.md).

A submission has two parts — a function `impl` and a proof `impl_correct` — and the rules follow
that shape: what you may edit, what `impl` must be, what `impl_correct` must prove, what the proof
may rely on, and what is scored.

- **R1 — One file.** A submission is exactly one file, `Submission.lean`. Every other file in the
  workspace is locked and the judge supplies its own copy.
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
  charges one full replay of the comparator-verified correctness closure plus the successful
  per-input target-declaration replays that force the kernel to reduce `impl n`. Parsing,
  dependency preloading, and outer-process startup are not scored; checking the exact output
  literal is.

> **Do not measure speed with `#eval`.** Use it to check that your function returns the *right
> answer*, never to judge how fast it is. `#eval` runs the **compiled** path; the judge times
> **kernel reduction**, and the two diverge exponentially *in both directions*. The naive `fibSpec`
> is the classic trap: the equation compiler encodes it via `Nat.brecOn`, so the kernel reduces it
> in linear time (`n = 2000` in ~0.06 s), while codegen emits an exponential call tree —
> `#eval fibSpec 2000` would need on the order of φ²⁰⁰⁰ steps and never finishes. The reverse trap
> is quieter: well-founded recursion compiles to fast native code (so `#eval` looks great) but
> reduces poorly in the kernel. Measure locally with `scripts/perf_eval.py`, which uses the same
> measurement boundary as the official judge.

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
| `sha256` | the SHA-256 hash chain digest after n steps | linear (~0.3 s/step, word-per-Nat) |
| `polydisc` | the discriminant of a monic degree-min(2+n/2,24) integer polynomial (Int; coefficient width grows past n=44) | factorial in the degree (Laplace) |
| `conv` | the packed integer convolution of two length-n 16-bit sequences (a NN conv layer / polynomial product) | ~n^2.5 (naive double sum, list walks) |

Each spec is intentionally naive, so reducing it directly in the kernel blows up as n grows;
competitive submissions need a better algorithm *and* a kernel-friendly encoding. The worked `fib`
example ships baseline + fast doubling (with a full `∀ n` proof); on a mid-size n the naive spec
times out in the kernel while fast doubling is checked in well under a second.

## Status

**Prototype / pre-launch.** All 10 problems are functionalized and compile; the judge runs the full
pipeline end-to-end — correctness gate plus a new-paradigm performance phase that times the kernel
reducing `impl n` at judge-chosen inputs into a scaling curve (local timing or the remote KTP/2
executor, measurement contract `kernel-replay-v2`). Not yet finalized: perf instruction-counting
on PMU hardware and the scoring aggregation (best-N + relative placement). Rule text may still
change before launch.
