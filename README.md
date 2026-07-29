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
not the objective — a submission is a general algorithm plus a machine-verifiable proof
that it matches the spec on every input, so progress comes from stronger algorithms and
kernel-level encodings rather than from bypassing the computation.

This repository holds **Stage 1**, the kernel-computation track.

---

## The task

Each problem gives you a **trusted spec** — a deliberately naive but correct definition
`spec : Nat → Output` in core Lean (e.g. the partition function `p(n)`). You submit:

1. a **function** `impl : Nat → Output` — your fast algorithm, and
2. a **proof** `impl_correct : ∀ n, impl n = spec n` — that it agrees with the spec on
   *every* input.

What is timed is **not how fast your code runs**. It is **how many instructions the
official Lean kernel spends reducing `impl n`** at inputs the judge chooses — because to
check the computation, the kernel is forced to carry it out. Lower is better.

Because correctness is proved for all `n`, the judge picks the inputs — possibly hidden,
at several sizes. Hardcoding or table lookup is therefore pointless: only a genuinely
good general algorithm scales. The simplest submission is `impl := spec` with
`impl_correct := fun _ => rfl` — correct but slow, since the kernel then reduces the naive
spec. Beating that baseline is the whole game.

## What you submit

One file, **`Submission.lean`** (optionally with helper files under `Submission/`).
Nothing else. You fill two holes in a locked workspace:

```lean
namespace Submission

def impl : Nat → Nat := sorry                       -- ① your fast algorithm (a total function)

theorem impl_correct : ∀ n, impl n = fibSpec n :=   -- ② proof it equals the spec on every n
  sorry

end Submission
```

The trusted files (`Spec.lean`, `Challenge.lean`, `Solution.lean`, `config.json`) are
fixed; the judge supplies its own copies. See **[`rules/overview.md`](rules/overview.md)**
for the binding rules and **[`rules/evaluation.md`](rules/evaluation.md)** for how judging
and scoring work.

## Rules in brief

A submission has two parts — a function `impl` and a proof `impl_correct` — and the rules
follow that shape (full text in [`rules/overview.md`](rules/overview.md)):

- **R1** Edit only `Submission.lean` and files under `Submission/`.
- **R2** `impl` is a total, structurally-recursive function in core Lean only (no
  `partial`/`unsafe`/`@[extern]`/`@[implemented_by]`, no Mathlib), so the kernel can
  reduce it on any input.
- **R3** `impl_correct` proves `∀ n, impl n = spec n` — correctness for *all* inputs.
- **R4** The proof may depend only on the standard axioms `propext`, `Quot.sound`,
  `Classical.choice`; `sorry` and `native_decide` are rejected.
- **R5** Only kernel checking is scored; how you find `impl` and its proof is unconstrained.

## Problems (Stage 1)

Every problem is parametric in `n : Nat`; the judge evaluates `impl` along that axis.

| Problem | `impl n` computes | Naive spec cost |
|---|---|---|
| `fib` *(tutorial)* | the n-th Fibonacci number | linear (`brecOn`) |
| `partition` | the partition function p(n) | ~p(n)·n |
| `mertens` | the Mertens function M(n) | quadratic |
| `primecount` | the prime-counting function π(n) | quadratic |
| `permanent` | the permanent of a deterministic n×n 0/1 matrix | n! |
| `saw` | count of self-avoiding walks of length n on ℤ² | exponential |
| `ca-rule110` | a Rule 110 automaton's state after n steps | linear (list-based) |

Each spec is intentionally naive: reducing it directly in the kernel blows up as `n`
grows, so competitive submissions require both better algorithms and kernel-level
encodings that reduce efficiently. The worked `fib` example ships two submissions — a
baseline (`impl := spec`) and fast doubling with a full `∀ n` proof.

## How judging works

```
Submission.lean
  → validate (slugs, symlinks, size caps)
  → correctness : build the locked Solution (references impl_correct : ∀ n, impl n = spec n)
  → performance : for each judge-chosen input n, time the kernel reducing `impl n`
  → scaling data + verdict
```

Correctness is proved once for all n, so the performance phase evaluates `impl` at inputs
of the judge's choosing — possibly hidden, and at several sizes to reveal a scaling curve.

## Scoring

The score of an accepted submission is the **kernel instruction count** to reduce `impl n`
on the Linux evaluation host (`perf -e instructions`, median of N reps). The fixed host and
pinned toolchain make it reproducible, and instruction counts avoid the wall-clock noise of
shared machines (the same methodology the Lean community uses in the Arena and Mathlib
Speedcenter) — though they are not literally hardware-independent. Submissions are **ranked
by scaling reach first** (the largest judge input completed within the timeout), then by
instruction count at that input; slow-but-correct submissions are accepted but unscored.

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

The local judge reproduces the evaluation pipeline, so you can check a submission before
sending it. (Note: the local sandbox is a pass-through shim — never run untrusted
submissions on your own machine; real sandboxing lives in the Docker image.)

## Repository layout

```
lean-kernel-challenge/
├─ rules/           overview.md (binding rules) · evaluation.md (judging + I/O contract)
├─ problems/<id>/   7 locked problem workspaces (Spec / Challenge / Solution / config)
├─ examples/submissions/<problem>/<name>/   worked + adversarial example submissions
├─ judge/           judge.py (the judge) · timer-kernel/ (kernel replay + axiom audit)
├─ pipeline/        config.json (budgets, sandbox mode, toolchain pins)
├─ tests/           harness_manifest.json (expected verdicts — the green gate)
├─ scripts/         setup.sh · run_harness.py · perf_eval.py · score.py · shims/
├─ Dockerfile       Linux evaluation image (pinned toolchain, perf, landrun sandbox)
└─ results/         verdict JSONs + leaderboard.md (generated)
```

## Toolchain

Pinned and frozen for the stage: **Lean v4.32.0-rc1**, comparator `71b52ec`,
lean4export `3de59f1`, Lean4Checker `b73981`. `scripts/setup.sh` rebuilds the tools from
these pins; the third-party checkouts are not committed.

## Status

**Prototype / pre-launch.** All 7 problems are functionalized and compile; the correctness
gate (comparator + axiom audit) and the green-gate harness are in place (7 baselines +
3 proven optimized submissions — `fib/doubling`, `ca-rule110/bitpacked`, `primecount/sqrt` —
accepted; three fib cheat classes — `sorry`, illegal axiom, Mathlib — rejected). The main judge (`judge/judge.py`) now runs the new-paradigm performance phase
end-to-end — timing the kernel reducing `impl n` at judge-chosen inputs into a scaling
curve (local perf or the remote KTP/1 executor); `scripts/perf_eval.py` is a lighter
standalone reproduction. Inputs are config-driven and hidden-jitterable (`PERF_SEED`), and
`scripts/score.py` reports the log–log slope + efficiency. Not yet finalized: a PMU-hardware
run; the cross-problem scoring aggregation (best-N + relative placement); the four remaining
optimized example submissions; prizes, timeline, and the submission platform.
Rule text may still change before launch (see `rules/overview.md`). Track 1 (certificate
verification) and Track 3 (open problems) are planned for later stages.
