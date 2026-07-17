# Lean Competition — Kernel Computation Track: Official Rules

Status: **finalized for Stage 1**. Version 1.0 (2026-07-13).

The task of this track is simple to state: **for a given problem, compute the
answer and prove it correct, such that the official Lean kernel re-checks your
proof as fast as possible.** The kernel's re-checking of your proof *is* the
computation being timed — so the whole game is finding an algorithm and an
encoding that the kernel can verify with the fewest instructions.

---

## 1. What you submit

For each problem you submit **one file, `Submission.lean`** (optionally with
additional Lean files under a `Submission/` directory). Nothing else.

The organizers give you a locked workspace per problem. You may edit **only**
`Submission.lean` and files under `Submission/`. You fill in two holes:

```lean
namespace Submission

def answer : Nat := 37338                                   -- ① the computed value

theorem answer_correct :                                    -- ② its correctness
    partitionSpec partitionInstance = answer := by
  ...                                                       -- your proof

end Submission
```

A submission therefore bundles three things, all inside this one file:

1. **Your algorithm** — an efficient computation, written as ordinary Lean
   definitions that the kernel can reduce.
2. **The answer** — the final value, written as a literal.
3. **The correctness proof** — that your answer equals the problem's spec, in
   which the kernel actually performs the computation.

---

## 2. Rules

**R1 — Locked files.** You may edit only `Submission.lean` and files you add
under `Submission/`. The trusted files (`Spec.lean`, `Challenge.lean`,
`Solution.lean`, `config.json`, `lakefile.toml`, `lean-toolchain`) are fixed;
the judge supplies its own copies and ignores any changes you make to them.

**R2 — The answer is a literal.** `Submission.answer` must elaborate to a raw
numeral literal (e.g. `37338`, or a negative `Int` where the problem's answer
type is `Int`). It may **not** be a compound expression such as
`partitionSpec partitionInstance`. (Otherwise the theorem would hold by
syntactic `rfl` with zero computation.) This is checked structurally on the
exported term.

**R3 — Standard axioms only.** `answer_correct` may depend only on the three
standard Lean axioms: `propext`, `Quot.sound`, `Classical.choice`. Any other
axiom is rejected. In particular:
- `sorry` (introduces `sorryAx`) — rejected.
- `native_decide` (introduces per-computation axioms and routes evaluation
  through the compiler, not the kernel) — rejected.

**R4 — The computation happens in the kernel.** The correctness of your answer
must be established by the **official Lean kernel actually performing the
computation** (e.g. by kernel reduction / `decide +kernel`). You may not rely
on any value computed outside the kernel and imported as a certificate or
axiom. *(R4 is a consequence of R2 + R3 + the scoring in §4, but is stated
explicitly so the track's intent is unambiguous: this is a kernel-computation
track, not a certificate track. Certificate-style problems are Track 1, a
separate future stage.)*

**R5 — No Mathlib; core Lean only.** `Submission.lean` and `Submission/` may
import the problem's provided modules (e.g. `Spec`) and the Lean core library.
They may **not** import Mathlib or any external dependency. This keeps exports
small and timing noise low, and removes Mathlib's compiled `native` paths as an
attack surface. (Everything you need for these problems — `Nat`/`Int`
arithmetic, `List`, structural recursion, `omega`, `decide +kernel` — is in
core Lean.)

**R6 — Total termination.** Every definition your proof depends on must be a
total Lean definition. `partial`, `unsafe`, `@[extern]`, and `@[implemented_by]`
are not usable here anyway — the kernel does not reduce them — and are
disallowed for clarity.

---

## 3. What "computing in the kernel" looks like in practice

Because the kernel evaluates by call-by-name reduction and the elaborator caps
recursion depth, the standard pattern is: write your fast algorithm as total,
structurally-recursive Lean definitions, prove it equal to the naive spec, and
close the final numeric goal with **`decide +kernel`**, which hands the
evaluation to the kernel. See `submissions/fib/doubling/` for a worked example
(fast doubling with a full core-Lean equivalence proof). Idioms that matter
(accumulator forcing, the fuel pattern for non-structural recursion) are
documented in `README.md`.

---

## 4. Scoring

- A submission is **accepted** iff it passes, in order: comparator (the
  statement matches the locked challenge, axioms are within R3, the proof
  kernel-checks), the R2 literal audit, and the R3 axiom re-audit on the exact
  export that is timed.
- The **score** of an accepted submission is the **instruction count** for the
  official kernel to re-check the exported `Solution` (Linux `perf`, normalized
  to virtual CPU time; lower is better). Peak memory is recorded as a tiebreaker
  and reported. Wall-clock is used only for local development.
- A rejected submission does not score. There is no partial credit within a
  problem: the answer must be correct *and* proven under these rules.
- Each problem has its own leaderboard. The overall standing aggregates your
  best **N** problems with a relative-placement component; the exact aggregation
  formula is published separately in the scoring appendix and may be finalized
  mid-competition (per SAIR convention) once the field's distribution is known.

---

## 5. Evaluation environment

- Official evaluation runs on a fixed Linux host (bare-metal, PMU access for
  `perf`) inside a sandboxed container. Toolchain is pinned: **Lean
  v4.32.0-rc1**, comparator `71b52ec`, lean4export `3de59f1`, Lean4Checker
  `b73981`. The pinned versions are frozen for the duration of a stage.
- Each judged stage has a wall-clock cap (build, and per-timing-rep); exceeding
  it rejects the submission. Timing is the median of N reps.
- Submissions run without network access and under resource limits. Do not
  attempt to escape the sandbox or exploit the harness; such submissions are
  disqualified.

---

## 6. Submission logistics

- One `Submission.lean` (+ optional `Submission/` directory of `.lean` files)
  per problem, per submission. Symlinks are rejected; total payload is capped.
- You may submit to as many problems as you like and resubmit; your best
  accepted result per problem stands.
- Submit through the competition platform (details in the problem pack). The
  local judge (`judge/judge.py`) reproduces the exact evaluation pipeline so you
  can check a submission before sending it.

---

*Questions about rule intent go to the competition discussion group. Rules may
be clarified during Stage 1; any change will be announced and versioned here.*
