# Lean Kernel Challenge

*A competition on the performance of verified computation in the Lean 4 kernel.*

Co-organized by Joachim Breitner, Leonardo de Moura, Kim Morrison, and Terence Tao —
with the **Lean FRO** and the **SAIR Foundation**.

## Background

The Lean 4 kernel is the trusted core that type-checks every proof the system accepts.
Type-checking includes definitional-equality checking, which the kernel discharges by
reduction (β/δ/ι reduction and evaluation to weak head normal form). When a proof
depends on a computed result — for instance an equation `f x = y` closed by `rfl` — the
kernel establishes it by reducing `f x` and comparing. Verifying such a proof and
performing the computation are therefore one and the same operation.

This makes the kernel a well-defined, deterministic model of computation with its own
performance characteristics: reduction is call-by-name, natural-number literals are
backed by GMP with a fixed set of native `Nat` operations, and evaluation strategy,
term representation, and sharing all bear directly on cost. The resulting question is
concrete and largely unstudied:

> **How efficiently can a computation be expressed so that the kernel *verifies* it,
> and which algorithmic and encoding techniques scale within the kernel's reduction
> model?**

The Lean FRO's [Lean Kernel Arena](https://arena.lean-lang.org/) measures kernel
*implementations* — how fast different checkers verify a fixed corpus of proofs. This
competition addresses the orthogonal axis: the official kernel is fixed as the judge,
and submissions compete on how few instructions it takes to check them. Speed alone is
not the objective — every answer must be accompanied by a machine-verifiable Lean proof
of its correctness, so progress comes from stronger algorithms and kernel-level encodings
rather than from bypassing the computation.

The intended outcomes are a corpus of efficient verified computations, transferable
techniques for kernel-level performance, and benchmarks that can inform ongoing work on
the kernel. This repository holds **Stage 1**, the kernel-computation track.

---

## The task

Each problem gives you a **trusted spec** — a deliberately naive but correct definition
in core Lean (e.g. the partition function `p(n)`) — and a specific instance. You must:

1. **compute the answer**, and
2. **prove it correct** against the spec.

What is timed is **not how fast your code runs**. It is **how many instructions the
official Lean kernel spends re-checking your proof** — because to check it, the kernel
is forced to carry out the computation. Lower is better.

An answer without a proof does not score. Attempts to bypass the kernel computation —
evaluating outside the kernel with `native_decide`, leaving a `sorry`, or defining the
answer as the spec expression itself so that `rfl` performs no work — are rejected by
the judge.

## What you submit

One file, **`Submission.lean`** (optionally with helper files under `Submission/`).
Nothing else. You fill two holes in a locked workspace:



The trusted files (`Spec.lean`, `Challenge.lean`, `Solution.lean`, `config.json`) are
fixed; the judge supplies its own copies. See **[`rules/overview.md`](rules/overview.md)** for the
binding rules and **[`rules/evaluation.md`](rules/evaluation.md)** for the full I/O contract.

## Rules in brief

The computation must happen **inside the kernel** — this is a kernel-computation track,
not a certificate track. Concretely (full text in [`rules/overview.md`](rules/overview.md)):

- **R1** Edit only `Submission.lean` and `Submission/`.
- **R2** `answer` must be a raw numeral literal (no `answer := spec instance` + `rfl`).
- **R3** Only the standard axioms `propext`, `Quot.sound`, `Classical.choice`;
  `native_decide` and `sorry` are rejected.
- **R4** Correctness must be established by the kernel actually doing the computation,
  not by an imported certificate.
- **R5** Core Lean only — no Mathlib, no external dependencies.
- **R6** Total definitions only (no `partial`/`extern`/`implemented_by`).

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

Each spec is intentionally naive: reducing it directly in the kernel is slow or
infeasible, so competitive submissions require both better algorithms and kernel-level
encodings that reduce efficiently. The worked `fib` example includes two submissions, a
linear loop and fast doubling; the latter is checked roughly **12× faster**.

## How judging works

```
Submission.lean
  → validate (slugs, symlinks, size caps)
  → comparator   : statement matches the locked challenge? axioms within R3? proof kernel-checks?
                   → emits the exact verified export (no separate re-export step)
  → R2 audit     : `answer` is a literal
  → R3 re-audit  : the exact verified export declares only whitelisted axioms
  → timing       : official kernel replays that export, N reps, median   ← the score
  → verdict JSON + leaderboard
```

The judge times the export comparator itself verified, byte-for-byte — there is no
independent re-export, so what is measured is exactly what was statement-matched and
kernel-replayed.

A submission is **accepted** (and scored) only if it clears every gate; otherwise it is
**rejected** with a reason. Infrastructure failures are a separate channel and never
count as a verdict.

## Scoring

The score of an accepted submission is the **kernel re-check instruction count** on the
Linux evaluation host (`perf -e instructions`, median of N reps; lower is better).
Instruction counts are hardware-independent and reproducible — the same methodology the
Lean community uses in the Arena and Mathlib Speedcenter.

Each problem has its own leaderboard. Your overall standing aggregates your best problems
with a relative-placement component; the exact formula is published with the scoring
appendix and may be finalized mid-competition once the field is known.

## Quick start

```bash
scripts/setup.sh                                  # build the pinned tools (comparator, lean4export, timer-kernel)
python3 scripts/run_harness.py                    # green gate: judge every example, check verdicts
python3 judge/judge.py run --problem fib --submission examples/submissions/fib/doubling
python3 judge/judge.py leaderboard
```

The local judge reproduces the exact evaluation pipeline, so you can check a submission
before sending it. (Note: the local sandbox is a pass-through shim — never run untrusted
submissions on your own machine; real sandboxing lives in the Docker image.)

## Repository layout

```
lean-kernel-challenge/
├─ docs/            rules.md (binding rules) · kernel_track.md (I/O contract, budgets)
├─ problems/<id>/   7 locked problem workspaces (Spec / Challenge / Solution / config)
├─ examples/submissions/<problem>/<name>/   worked + adversarial example submissions
├─ judge/           judge.py (the judge) · timer-kernel/ (kernel replay + R2/R3 audits)
├─ pipeline/        config.json (budgets, sandbox mode, toolchain pins)
├─ tests/           harness_manifest.json (expected verdicts — the green gate)
├─ scripts/         setup.sh · run_harness.py · shims/
├─ Dockerfile       Linux evaluation image (pinned toolchain, perf, landrun sandbox)
└─ results/         verdict JSONs + leaderboard.md (generated)
```

## Toolchain

Pinned and frozen for the stage: **Lean v4.32.0-rc1**, comparator `71b52ec`,
lean4export `3de59f1`, Lean4Checker `b73981`. `scripts/setup.sh` rebuilds the tools from
these pins; the third-party checkouts are not committed.

## Status

**Prototype / pre-launch.** The judging pipeline is complete and self-audited (7 problems,
15 example submissions, green-gate harness). Not yet finalized for a live competition:
the perf instruction-counting path and container isolation are implemented but not yet
run on PMU hardware; multi-tier / hidden instances and the scoring layer (best-N +
relative placement) are not built; prizes, timeline, and the submission platform are TBD.
Rule text may still change before launch (see `rules/overview.md`). Track 1 (certificate
verification) and Track 3 (open problems) are planned for later stages.