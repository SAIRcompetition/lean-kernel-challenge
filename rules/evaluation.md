# Stage 1 — Evaluation

Test plans and ranking are in [Problems and Scoring](problems/README.md#scoring).
The revised ranking is not yet implemented; see [implementation status](problems/README.md#implementation-status).

## Evaluation process

1. **Verify correctness.** Check the file, locked interface, permitted axioms, and
   proof `∀ n, impl n = spec n`. Only a pass is **Accepted**.
2. **Replay verification.** Replay the verified definitions and universal proof.
   These checks must finish, but their instruction counts do not affect ranking.
3. **Measure computation.** For each hidden input, check a direct theorem
   `impl n = v`, where `v` is the exact official output. Measure only that target
   declaration's kernel replay, forcing computation of `impl n` and comparison
   with the output literal.
4. **Report and rank.** List every case's outcome and median instruction count
   over three repetitions. Rank complete passes by the sum, lowest first.
   Equal totals tie; universal-proof checking is excluded.

Measurements use immutable exports from the verified build, without re-elaborating
contestant source for each case. Startup, export parsing, and dependency preload
are outside the counter; output-literal checking is inside. This measures kernel
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
  case preparation, audit, or replay it fails that case with `resource-limit`.
  Memory classification requires an increased cgroup OOM counter, not just SIGKILL.
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
