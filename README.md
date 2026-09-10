# Lean Kernel Challenge — Stage 1

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

## Background

The Lean Kernel Challenge is a competition series that brings the community together to
improve the performance of verified computation in the Lean kernel.

Stage 1 is the first, experimental stage of the series. It begins with a set of fundamental
computational problems. Later stages will cover a broader range of mathematical and scientific
fields and more complex problems.

The Lean 4 kernel is the trusted core that type-checks every proof the system accepts.
Type-checking includes definitional-equality checking, which the kernel discharges by
reduction (β/δ/ι reduction and evaluation to weak head normal form). When a proof
depends on a computed result — for instance an equation `f x = y` closed by `rfl` — the
kernel establishes it by reducing `f x` and comparing. Verifying such a proof and
performing the computation are therefore one and the same operation.

The algorithms, representations, and open-source results and benchmark
data produced through the competition will form a collective contribution to
Lean's continued development and benefit Lean users worldwide.

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

---

## The task

Each problem gives you a **trusted spec** — a deliberately naive but correct definition
`spec : Nat → Output` in core Lean (e.g. the partition function `p(n)`). You submit:

1. a **function** `impl : Nat → Output` — your fast algorithm, and
2. a **proof** `impl_correct : ∀ n, impl n = spec n` — that it agrees with the spec on
   *every* input.

What is timed is **not how fast your compiled code runs**. The official Lean kernel measures three
complete replays of the verified correctness closure and three replays of each hidden case's
generated target declaration, recording each median. Process startup, export parsing, and
per-input dependency preloading are outside the counter. Each problem defines how these
measurements determine instruction cost after the complete hidden plan passes.

Correctness for all `n` lets the judge rotate hidden inputs, but it does not make literal
tables logically impossible: a contestant can derive constants through another verified
algorithm. The scoring contract therefore records both the correctness-closure replay and each
successful target-declaration replay, and each problem specifies how they enter its tie-breaks.
The simplest submission is `impl := spec` with
`impl_correct := fun _ => rfl` — correct but slow because the kernel reduces the naïve spec.

## What you submit

Exactly one file, **`Submission.lean`**, at most 1 MiB. Nothing else — every lemma your
proof needs lives in that file, inside `namespace Submission`. You fill two holes in a
locked workspace:

```lean
namespace Submission

def impl : Nat → Nat := sorry                       -- ① your fast algorithm (a total function)

theorem impl_correct : ∀ n, impl n = fibSpec n :=   -- ② proof it equals the spec on every n
  sorry

end Submission
```

The trusted files (`Spec.lean`, `Challenge.lean`, `Solution.lean`, `config.json`) are
fixed; the judge supplies its own copies. For the timeline, registration,
participation policies, and co-organizers see
**[`rules/prelaunch.md`](rules/prelaunch.md)**. See
**[`rules/overview.md`](rules/overview.md)**
for the binding rules, **[`rules/evaluation.md`](rules/evaluation.md)** for the common judging
contract, and **[`rules/problem-scoring.md`](rules/problem-scoring.md)** for every problem's
input groups, cases, limits, and instruction-cost policies.

## Rules in brief

A submission has two parts — a function `impl` and a proof `impl_correct` — and the rules
follow that shape (full text in [`rules/overview.md`](rules/overview.md)):

- **R1** Submit exactly one file, `Submission.lean`; every other file is locked.
- **R2** `impl` is a total core-Lean function that the kernel can reduce on every input
  (structural recursion is recommended; well-founded recursion is also permitted; no Mathlib).
- **R3** `impl_correct` proves `∀ n, impl n = spec n` — correctness for *all* inputs.
- **R4** The proof may depend only on the standard axioms `propext`, `Quot.sound`,
  `Classical.choice`; `sorry` and `native_decide` are rejected.
- **R5** Kernel replay is measured: one full correctness-closure median and the successful
  per-case target-declaration medians. Each problem gives 100 points for a complete pass
  and 0 points with infinite ranking cost for any failed case; full passes compare instruction
  cost. Parsing, dependency preload, and process startup are excluded; exact output-literal
  checking remains included.

## Problems (Stage 1)

Each scored problem still exposes `impl : Nat → Output`. Some problems pack a public scale and a
hidden 32-bit seed into that `Nat`; their generators and encodings are part of the trusted spec.

| Problem | `impl n` computes | Naive spec cost |
|---|---|---|
| `fib` *(tutorial)* | the n-th Fibonacci number | linear (`brecOn`) |
| `partition` | the partition function p(n) | ~p(n)·n |
| `mertens` | the Mertens function M(n) | quadratic |
| `primecount` | the prime-counting function π(n) | quadratic |
| `permanent` | the permanent of a seeded fixed-row-degree 0/1 matrix; input packs dimension and seed | exponential in dimension (pruned DFS) |
| `saw` | seeded-obstacle self-avoiding walks; input packs walk length and seed | exponential in the walk length |
| `ca-rule110` | a seeded 256-cell Rule 110 evolution; input packs step count and seed | linear in steps, list-based |
| `sha256` | a seed-specific SHA-256 digest chain; input packs step count and seed | linear in steps, word-per-`Nat` |
| `polydisc` | the discriminant of a monic degree-24 integer polynomial across three coefficient-scale bands | normal subresultant PRS; reduced Bareiss fallback |

These nine problems have independent Stage 1 leaderboards. The repository also retains `conv` as
an experimental development task; it is not part of the nine scored leaderboards.

Most specs intentionally leave substantial algorithmic or representation overhead, so
competitive submissions require better algorithms, kernel-level encodings, or both. The worked
`fib` example ships two submissions — a
baseline (`impl := spec`) and fast doubling with a full `∀ n` proof.

## How judging works

```
Submission.lean
  → validate the official precomputed input/output bundle
  → validate submission structure and size
  → correctness : parse outside the counter, then replay the full verified closure three times
  → performance : replay each grouped case's target declaration three times
  → correctness timing + complete group/case record + verdict
```

This is measurement contract `kernel-replay-v2`, with boundaries
`full-closure-replay-v1` and `target-declaration-replay-v1`. Scoped counters remove fixed
harness cost without subtracting noisy process totals. Target replay still reduces `impl n` and
compares the exact result, so checking a large `Nat`/`Int` literal remains input-dependent scored
work. The verdict also pins the direct target-proof encoding
`direct-rfl-v1-experimental`, preventing extracted-proof wrapper timings from mixing in.

Official outputs are computed independently of submissions using Python reference algorithms or
precomputed data. The judge validates and loads the private bundle before contestant code runs,
then still checks the direct `impl n = output` theorem by kernel reduction.
See [`docs/reference-answers.md`](docs/reference-answers.md) for preparation and transport.

For official evaluation, `PERF_SEED` is a secret rotation token. The judge derives the hidden
cases from it and the published problem, group, and case coordinates, so every submission in one
evaluation cohort receives the same plan. The sealed cohort records the complete plan and a seed
commitment. Operators rotate the token and cohort id for a new round or deliberate rescore; an
unset seed is allowed only for deterministic local development. The production wrapper injects
the seed once over stdin, never into the submission's elaboration environment. Raw verdicts and
exact inputs remain private throughout the evaluation phase. After the final official cohort closes,
its resolution seed, exact input plan, results, and benchmark data are released publicly under an
open-source license. Provisional standings use separate hidden sampled inputs that organizers may
update; the reference input plans and seeds are outside this publication commitment.

## Scoring

Stage 1 has **nine independent 100-point problem leaderboards**. There is no cross-problem total
or relative-placement aggregation, and `conv` is excluded. Each problem publishes three input
groups. An otherwise scoreable submission earns **100 points only when every hidden case passes**;
**any failed case gives 0 points and infinite ranking cost**. There is no partial credit or
comparison by harder groups or successful subsets. Infrastructure failures and incomplete runs
remain unscored and require investigation or re-evaluation.

Among full-plan passes, lower instruction cost wins. Target work sums all target-declaration
replay medians. Combined work adds the correctness-closure replay median once; `saw`,
`ca-rule110`, and `sha256` use this policy. The other six problems use target work. Equal costs
remain tied, with no additional proof-cost comparison. All scoreable failed plans are tied.
A baseline may score 100; reducing instruction cost is what improves its competitive position.

The official metric is **kernel instructions** on the pinned Linux evaluation host
(`perf -e instructions`, median of three repetitions). Stage 1 official cohorts use the local PMU
inside the network-disabled evaluation container. Wall time and resource-bound remote **KTP/3**
timing are non-official validation modes and are never mixed with official scores. Verdicts commit to
the protocol, `kernel-replay-v2`, both boundary versions, target-proof encoding, exact grouped
plan, reference-answer bundle, toolchain, timing policy, and executor. A change to any of these
fields creates a new cohort and requires a full rescore. Run `python3 scripts/score.py` to generate the canonical tables.

See **[`rules/problem-scoring.md`](rules/problem-scoring.md)** for the published input ranges or
generators, case counts, resource limits, and instruction-cost policy
for each problem.

Each problem's memory limit will be published before it is used for official evaluation.
Organizers may revise these limits during the competition. A limit is fixed within its evaluation
cohort; revising it requires a new cohort and a complete rescore of that problem's comparison set.

## Quick start

```bash
scripts/setup.sh                                  # build the pinned tools (comparator, lean4export, timer-kernel)
python3 scripts/run_harness.py                    # green gate: judge every example, check verdicts
python3 scripts/run_harness.py --quick --jobs 2     # same worker count as the image build; shorter smoke checks
python3 judge/judge.py run --problem fib --submission examples/submissions/fib/doubling
python3 scripts/score.py                          # canonical metric-separated scoring tables
```

Each harness worker can consume several GiB during Lean compilation (the
heaviest cases peak at 2.3–4.9 GiB each).  The command defaults to one worker;
the image-build gate runs two workers everywhere, the one setting measured to
fit a 16 GiB builder with the worst pair near 8 GiB, so CI and deployment
builds use the same configuration.  A smaller builder can pass
`docker build --build-arg HARNESS_JOBS=1 -t lean-kernel-judge .`; raise the
count only after measuring the target host.
The image-build regression check uses `--quick --count 2 --timeout 120`.
It checks expected submission verdicts, measurement-record structure, and the
minimum performance coverage declared in `tests/harness_manifest.json`.
A slow baseline may pass this check even when its performance inputs time out;
the image build fails when a manifest requirement is not met. These checks run
in local development mode and do not establish that every performance input
passes under the official per-problem memory limits. Verify those limits using
the built image through `scripts/run_isolated.sh` after the per-problem policy
has been implemented and configured.
To run a subset of the regression checks, use
`docker build --build-arg HARNESS_ONLY=mertens ...`, which judges only the
manifest cases whose problem contains the substring (`run_harness.py --only`):
a development and test-rehearsal shortcut, never a release build.  Such an
image has not been proven on every problem, so a deployment pipeline that
passes it must label the image as partially gated and must never promote it
beyond its test environment.  The full opt-out is
`docker build --build-arg HARNESS_SKIP=1 ...`: the gate does not run at all.
It exists for non-production deployment builds (test and beta environments)
whose iteration time the serial gate dominates; the pinned commit is still
green-gated by this repository's CI.  Such an image has not been proven at
build time, so a deployment pipeline that consumes it must label the image as
not gated and must never promote it to a production environment, whose builds
always run the full gate.

The local judge reproduces the evaluation pipeline, so you can check a submission before
sending it. (Note: the local sandbox is a pass-through shim — never run untrusted
submissions on your own machine; real sandboxing is enforced by the wrapper-launched
Docker container.)

### Isolated evaluation of untrusted submissions

Build the evaluation image once, then run every untrusted submission through the
host-side wrapper:

```bash
docker build -t lean-kernel-judge .
LKC_REFERENCE_DIR=$(mktemp -d)
printf '%s\n' 'official-secret-seed' | python3 scripts/prepare_reference.py \
  --problem fib --official --output "$LKC_REFERENCE_DIR/fib.json"
scripts/run_isolated.sh \
  --problem fib \
  --submission "$PWD/examples/submissions/fib/doubling" \
  --results "$PWD/results" \
  --perf-seed 'official-secret-seed' \
  --reference-answers "$LKC_REFERENCE_DIR/fib.json" \
  --cohort stage1-round1 \
  --perfmon
```

`scripts/run_isolated.sh` is the supported production entry point. It always runs one
submission per container with networking disabled, bounded memory/CPU/process counts,
`no-new-privileges`, and the non-root `judge` user. The submission is mounted read-only
and verdicts are written through a persistent results mount. The seed and private reference-answer
bundle are consumed from a one-shot stdin pipe before any untrusted Lean process starts; `--cohort` is the public round
identifier used to prevent cross-round scores from being mixed. `--perfmon` is optional on
hosts whose `perf_event_paranoid` setting already permits instruction counting. On a native
Linux Docker host, the results directory must be writable by the image's judge UID 10001;
the wrapper checks this before it starts elaborating the submission.

Memory is configured independently in each `problems/<id>/config.json` as
`evaluation.memory_mb` (MiB). The wrapper reads the chosen problem, applies the same value to
`--memory` and `--memory-swap` (zero extra swap), and the judge checks it against both the image's
problem policy and the actual cgroup. `--memory` / `JUDGE_MEMORY` can only assert that value;
they cannot override it. **Matrix permanent (`permanent`) uses 8192 MiB (8 GiB)**. The other
eight problems retain provisional 4096 MiB (4 GiB) limits pending organizer confirmation.
See the [launch checklist](docs/pre-launch-checklist.md) for host acceptance. Changing a limit
requires a rebuilt image, a new cohort, and rescoring that problem's comparison set.

## Repository layout

```
lean-kernel-challenge/
├─ rules/           overview.md (rules) · evaluation.md (judge) · problem-scoring.md (leaderboards)
├─ problems/<id>/   10 locked workspaces: 9 scored problems + experimental conv
├─ examples/submissions/<problem>/<name>/   worked + adversarial example submissions
├─ judge/           judge.py (the judge) · timer-kernel/ (kernel replay + axiom audit)
├─ pipeline/        config.json (budgets, sandbox mode, toolchain pins)
├─ tests/           harness_manifest.json (expected verdicts — the green gate)
├─ scripts/         setup.sh · run_harness.py · run_isolated.sh · perf_eval.py · score.py · shims/
├─ Dockerfile       Linux evaluation image (pinned toolchain, perf, landrun sandbox)
└─ results/         verdict JSONs + scoring index + one generated leaderboard per problem
```

## Toolchain

Pinned and frozen for the stage: **Lean v4.33.1**, comparator `3927ad3`,
lean4export `15f6055`, kernel replay via Lean's built-in `Lean.Replay`. `scripts/setup.sh` rebuilds the tools from
these pins; the third-party checkouts are not committed.

## Status

The nine per-problem group schedules and scoring rules are published in
**[`rules/problem-scoring.md`](rules/problem-scoring.md)** and encoded in each problem's
`config.json`. Before launch, the production PMU measurements and container path still require
end-to-end validation; see **[`docs/pre-launch-checklist.md`](docs/pre-launch-checklist.md)**.

**Prototype / pre-launch.** All 10 workspaces compile, while nine are included in the Stage 1
scoring contract. The correctness gate, axiom audit, grouped judge, canonical per-problem scorer,
and green-gate harness are in place. The performance phase imports the byte-pinned `.olean` graph
produced by the comparator instead of re-elaborating contestant source. Hidden cases are
config-driven and shared within a cohort through a rotating official `PERF_SEED`; the seed is
never exposed to elaboration. `scripts/score.py` applies the sealed `full-plan-v1` ranking
contract and per-problem work policy. Remaining launch work includes production PMU and container
acceptance, per-problem memory enforcement, and the platform policies listed in the launch
checklist. Additional optimized examples are useful but not part of
the scoring contract. Rule text may still change before launch (see `rules/overview.md`).

The September 9 review implements independent standard answers and full-plan scoring in this
repository. Platform integration and other launch work remain:
replace the fixed 4 GiB runtime checks with per-problem memory policies, and verify that platform
entry selection always uses the latest formal submission. The final memory values are not yet set.
These pending updates are tracked in [`docs/pre-launch-checklist.md`](docs/pre-launch-checklist.md).
The six target-work problem configurations now use correctness work only as a completion gate;
the three combined-work problems retain correctness-plus-target ranking.
