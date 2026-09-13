# Stage 1 — Evaluation

Test plans and ranking are in [Problems and Scoring](problems/README.md#scoring).
The revised ranking is not yet implemented; see [implementation status](problems/README.md#implementation-status).

## Specification and implementation

The fixed `spec` defines the required mathematical result. The submitted
`impl_correct : ∀ n, impl n = spec n` proves equality for every natural-number
input; the judge checks this proof, rather than establishing correctness by
sampling inputs. Independently, `impl` must be total and kernel-reducible to an
output literal, as required by [R2 and R3](overview.md#rules).

A Mathlib specification fixes the correctness target, not the algorithm you
must execute. For example, the [Fibonacci starter](../problems/fib/Submission.lean)
uses `Nat.fastFib` and proves equality with the fixed `Nat.fib` specification.
Performance measurement computes the submitted implementation. The
[Mathlib status table](problems/README.md#mathlib-status) identifies the three
Mathlib targets and the five repository-defined targets.

## Evaluation process

1. **Build and verify correctness.** Build the submission and check the file,
   locked interface, permitted axioms, and universal proof. Only a pass is
   **Accepted**.
2. **Replay verification.** Replay the verified definitions and universal proof
   three times. Record the median instruction count separately as **correctness
   replay**, labeled **verification only**. These checks must finish, but their
   instruction counts do not affect ranking under the published policy.
3. **Prepare each case.** For the input `n` and exact official output `v`, generate,
   kernel-check, and export a direct theorem `impl n = v`. Reuse the frozen
   compiled submission (`.olean` files); contestant source is not re-elaborated
   for each case. Check that the export binds the verified implementation to
   this input and the judge-generated target, then audit its permitted axioms.
4. **Measure computation.** In three separate replay processes, measure only the
   target declaration's kernel check. It forces computation of `impl n` and
   comparison with the exact output literal.
5. **Report and rank.** List every case's outcome and median instruction count
   over three repetitions as **computation replay**. Keep the correctness-replay
   result separate from these case measurements and their total. Rank complete
   passes by the computation-replay total, lowest first.
   Equal totals tie; universal-proof checking is excluded for all eight problems.

Audits and timed replays consume the same immutable export. The generated case
proof is `Eq.refl v`: to accept it as a proof of `impl n = v`,
the kernel must reduce `impl n` to `v`. This work occurs during target preparation
and again during each measured replay. A contestant-supplied proof of that one
answer does not replace the generated computation target.

Preparation, binding and axiom audits, startup, and export parsing are outside
the ranking counter. Each target-timing process also kernel-checks its dependencies
before opening the counter. These steps still consume time and memory: the process
watchdog includes startup, parsing, and dependency replay, and the problem's memory
limit applies during preparation as well as timed replay. A submission can therefore
exhaust its resources before reaching the measured target. This measures kernel
work, not compiled runtime or whole-process time.

Organizers prepare reference outputs independently before judging. The bundle
must match the specification and full input plan and is shared within a cohort.
Values do not replace kernel checks: a missing or invalid bundle, or failure of
the generated equality check, is an evaluation error, not a contestant failure.

**Verdicts:** `accepted` means correctness passed, not performance; failed cases
or incomplete verification leave it unranked. `rejected` means validation,
correctness, or a rule failed. `retry` requires another attempt; `error` requires
organizer review. Infrastructure failures are not contestant performance failures.

[Check and case limits](problems/README.md#limits) apply independently:

- Comparator timeout fails the correctness gate; correctness axiom-audit timeout
  is an infrastructure error. Timed correctness-replay failure leaves an otherwise
  Accepted submission unranked.
- An attested memory kill in the comparator or correctness axiom audit rejects the
  submission. In timed correctness replay it leaves it Accepted but unranked; in
  case build/export, case axiom audit, or target replay it fails that case with
  `resource-limit`.
  Memory classification requires an increased cgroup OOM counter, not just SIGKILL.
- Performance-export binding must succeed before timing. A failed or unfinished
  binding check, including timeout or memory exhaustion, stops the run with
  `error` for organizer review and re-evaluation. An unfinished check does not
  establish that the implementation changed. Binding and case axiom audits share
  one 300-second budget per case.
- Later cases continue after a case failure. Fatal evaluator failures require review
  and re-evaluation; unattempted cases remain explicitly unattempted. A timeout alone
  does not establish a reducibility violation.

A cohort fixes inputs and seed commitment, answers, Spec and dependencies, ranking
policy, repetitions, budgets, resource limits, toolchain, executor, and measurement
boundaries. Changing these requires a new cohort and complete rescore; different
cohorts or metrics are never mixed. See [competition rules](overview.md#evaluation-and-results)
for daily standings, final evaluation, and data release.

Official evaluation requires a secret `PERF_SEED`, rotated between cohorts. The
isolated wrapper passes it once to the judge through stdin, never to contestant-controlled
Lean processes. Unseeded runs are for local development only.

## Environment

| Component | Configuration |
| --- | --- |
| Lean | **4.33.1** for all eight problems |
| Mathlib | Pinned **v4.33.1** for fib, mertens, and primecount; core Lean for the other five |
| Official OS / metric | Linux PMU host with cgroup v2 and Landlock; Ubuntu 24.04 container; kernel instruction counts |
| CPU allocation | 2 CPUs per evaluation job |
| Memory | 8 GiB for permanent; provisional 4 GiB for the other seven; no extra swap |
| Process limit | 512 per container |
| Isolation | Non-root container, networking disabled, read-only submission files |
| Tools | Comparator `3927ad3` with the [emit-export patch](../evaluation/patches/comparator-emit-export.patch); lean4export `15f6055`; Lean's `Lean.Replay` |

**The official CPU model and complete host hardware specification are not yet
published in this repository.** The CPU allocation above is not a hardware model.
Production-host validation remains pending. The wrapper checks memory and swap
against the fixed problem configuration and records the host identity in the cohort.
Attempting to escape the evaluation environment or exploit the judge leads to disqualification.

[Full tool pins](../evaluation/config.json) and per-problem Mathlib locks fix the
software environment. Official timing uses in-container `local-v2`, contract
`kernel-replay-v2`, correctness boundary `full-closure-replay-v1`, and computation
boundary `target-declaration-replay-v1`; the target-proof encoding is also recorded.
Remote `KTP/3` is non-official validation only and binds requests to the problem's
memory limit.

## Local quick start

Install Python 3.9+, Git, [elan](https://github.com/leanprover/elan), and a C/C++
build toolchain. On macOS, also install GNU coreutils (`brew install coreutils`).
From the repository root:

```bash
bash evaluation/setup.sh --problem partition
python3 evaluation/run.py --problem partition
```

Replace `partition` with your problem ID. This evaluates
`problems/<id>/Submission.lean` on the **full unseeded public plan**, with one
wall-time measurement per case. It checks correctness and kernel computation,
but does not reproduce official PMU counts, isolation, or rankings.

See the [local evaluator guide](../evaluation/README.md) for custom submissions,
timeouts, and results, or [maintainer deployment](../evaluation/maintainers.md)
for Docker and official-host setup. The evaluator is optional for the
[participant workflow](problems/README.md#quick-start).
