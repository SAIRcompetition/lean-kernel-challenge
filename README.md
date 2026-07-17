# Lean Competition — Kernel Computation Track: E2E Flow & Judge (prototype)

Stage 1 prototype: contestants submit Lean proofs, and **the official kernel's
re-checking of that proof is itself the timed computation**. Assembled from
lean-eval (comparator verification) and lean-kernel-arena (timing methodology).

**Official rules: [`docs/rules.md`](docs/rules.md)** (finalized v1.0) ·
**track spec: [`docs/kernel_track.md`](docs/kernel_track.md)**. This README is the
implementation/how-it-works companion.

## Repository layout (SAIR competition-pack convention)

```
lean-kernel-challenge/
├─ README.md            this file (how it works)
├─ Dockerfile           Linux evaluation image (pinned tools, perf, landrun sandbox)
├─ LICENSE  CONTRIBUTING.md  lean-toolchain
├─ docs/                rules.md (binding rules) · kernel_track.md (I/O contract, budgets)
├─ judge/               judge.py (the judge) · timer-kernel/ (kernel replay + audits)
├─ pipeline/            config.json (judge budgets, sandbox mode, toolchain pins)
├─ problems/<id>/       7 locked problem workspaces (Spec/Challenge/Solution/config)
├─ examples/submissions/<problem>/<name>/   14 example submissions
├─ tests/               harness_manifest.json (expected verdicts, the green gate)
├─ scripts/             setup.sh (build pinned tools) · run_harness.py (green gate)
└─ results/             verdict JSONs + leaderboard.md (generated)
```

Bootstrap: `scripts/setup.sh` builds the pinned tools; `python3 scripts/run_harness.py`
is the regression gate; `docker build -t lean-kernel-judge .` is the eval image.

## Submission shape

One locked workspace per problem (lean-eval's def-hole pattern):

| File | Editable? | Contents |
|---|---|---|
| `Spec.lean` | 🔒 locked | Trusted spec: textbook definition (deliberately naive) + instance parameters. **No Mathlib import** (small exports, low timing noise) |
| `Challenge.lean` | 🔒 locked | Two holes: `answer` (def-hole, the computed value) and `answer_correct : spec instance = answer` |
| `Solution.lean` | 🔒 locked | Fixed bridge into the `Submission` namespace |
| `Submission.lean` + `Submission/` | ✏️ contestant | Fill the holes: fast implementation + equivalence proof + final value |
| `config.json` | 🔒 locked | Axiom whitelist (the three standard axioms) + hole list |

## Rules

- **R1** Only `Submission.lean` and files under `Submission/` may be edited/added.
- **R2** `Submission.answer` must be a raw numeral literal (blocks the
  zero-computation cheat `answer := spec instance` + `rfl`; enforced by a
  structural check on the exported term).
- **R3** Only the standard axioms (`propext`, `Quot.sound`, `Classical.choice`).
  `native_decide` (per-computation axioms since Lean 4.29) and `sorry`
  (`sorryAx`) are rejected by the axiom audit.

## Judge pipeline (`judge/judge.py`)

```
contestant Submission
  │ 1. validate inputs (slug checks; reject symlinks/oversized trees; containment)
  │ 2. assemble workspace (locked template + contestant files)
  │ 3. comparator: build → statement match → axiom whitelist → kernel replay   [correctness gate]
  │ 4. lean4export: export the Solution closure
  │ 5. R2 audit: timer-kernel --check-literal Submission.answer
  │ 6. axiom re-audit: timer-kernel --check-axioms on the exact timed export
  │ 7. timing: official-kernel replay of the export × N reps, median           [the scored event]
  ▼
verdict JSON → results/<problem>/<submission>.json → leaderboard.md
```

- Judgement outcomes (accepted/rejected) and infrastructure failures are
  separate channels (exit 0 vs 2); every infra failure still writes a verdict
  JSON and exits 2 rather than crashing.
- Each stage runs in its own process group, killed as a group on timeout.
- Timing metric: wall time on this dev machine (macOS); production evaluation
  should run on Linux with `perf` instruction counting (same methodology as
  lean-kernel-arena / Mathlib Speedcenter, 6.0 Ginstr/s normalization).
- Sandbox: local development uses a pass-through landrun shim (**no
  sandboxing**); production = Linux + landrun + a container.

```bash
# judge one submission
python3 judge/judge.py run --problem partition --submission submissions/partition/baseline
# rebuild the leaderboard
python3 judge/judge.py leaderboard
```

## Problems (Kim's pure-kernel-reduction list, plus a tutorial problem)

| Problem | Spec | Instance | Official answer (#eval of the spec) | Baseline median |
|---|---|---|---|---|
| `fib` (tutorial) | naive double recursion | n = 100000 | 20899-digit number | loop 6.49 s / **doubling 0.53 s (12×)** |
| `partition` | largest-part recurrence, no memoization | n = 40 | 37338 ✓ known value | 41.9 s |
| `mertens` | μ by trial division, summed (Int-valued) | n = 250 | **−1** (exercises the Int literal path) | 4.8 s |
| `primecount` | trial division | n = 600 | 109 ✓ | 6.7 s |
| `permanent` | sum over all permutations | 7×7 0/1 (seed 20260709) | 187 | 4.0 s |
| `saw` | brute-force self-avoiding-walk extension | length 8 | 5916 ✓ literature value | 12.2 s |
| `ca-rule110` | list-based cell-by-cell evolution | width 32 × 128 steps | 527562713 | 4.1 s |

## Example submissions (`submissions/`)

- `<problem>/baseline` — zero-cleverness baseline: `decide +kernel` grinds the
  naive spec directly (7 problems).
- `fib/loop` — tail-recursive pair loop with a correctness proof; demonstrates
  the accumulator-forcing idiom.
- `fib/doubling` — fast doubling with a full inductive proof of the Fibonacci
  addition formula (~150 lines, core Lean only); 12× faster than the loop.
  Doubles as contestant example code.
- `permanent/multifile` — proof split into `Submission/Helpers.lean`
  (multi-file submission path).
- Adversarial (all correctly rejected): `fib/cheat-sorry` (`sorryAx`),
  `partition/cheat-native` (`native_decide` per-computation axiom),
  `permanent/cheat-rfl` (zero-computation R2 violation),
  `permanent/cheat-statement` (proves a different statement; bridge fails closed).

## Kernel-reduction idioms discovered while building this

1. **Kernel reduction is call-by-name**: a tail-recursive accumulator piles up
   O(n) nested `+`-thunks and overflows the reduction stack. Idiom: force the
   accumulator to a literal each step by matching it against the `Nat`
   constructors (`match a + b with | 0 => … | c+1 => …`).
2. **The elaborator cannot do big computations**: elaborator-side whnf burns
   `maxRecDepth` per unfolding step, so a 10⁵-step `rfl` dies during
   elaboration. Idiom: **`decide +kernel`** hands the computation straight to
   the C++ kernel — which is precisely the timed event of this track.
3. **Specs must use structural recursion**: well-founded recursion compiles to
   `WF.fix`, which the kernel does not reduce definitionally. For non-structural
   recursion (e.g. `n → n/2` in fast doubling) use the fuel pattern.
4. **Literals aren't free**: a 20899-digit `answer` literal has real export and
   replay cost; rule R2 also guarantees the kernel actually produced the number.

## Toolchain pins

Lean v4.32.0-rc1 · comparator 71b52ec · lean4export 3de59f1 · Lean4Checker b73981
(identical to lean-eval's pin set — no export-format drift).

## TODO (priority order)

1. Linux evaluation host: `perf` instruction counting + containerized sandbox.
2. Multi-tier instances per problem + hidden-input generator framework (Stage 2).
3. Optimized example submissions for the remaining problems (memoized
   partition, Ryser permanent, bit-packed CA) — also pre-launch tutorial material.
4. Scoring layer: per-problem instruction counts → rank points → best-N
   aggregation (all raw data already in the verdict JSONs).
5. Starter pack: tutorial problem + one real problem + local judge instructions.
