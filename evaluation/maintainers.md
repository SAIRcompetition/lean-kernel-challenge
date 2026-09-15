# Evaluator maintenance and deployment

Run commands from the repository root. See [Local evaluation](README.md) for
prerequisites and single-file checks. Current configurations rank with
`computation-total-v1`; a passing harness or image build does not show that the
hosted platform has upgraded.

## Scoring and result versions

`evaluation-policy-v2` seals the `grouped-evaluation-v1` plan and ranking
`{"contract":"computation-total-v1","work":"curve","proof":"gate"}`. It has no
points, partial ranking, or correctness-cost tie-break. Keep old `full-plan-v1`
and `group-points-v1` records readable under their original semantics. An
upgrade requires a new cohort, upgraded image and consumers, and a complete
re-evaluation; never rewrite historical policies or caches.

Raw `correctness_timing` and `timing.scaling` preserve measurement evidence.
Derived `replay_report` (`replay-report-v1`) records the metric, repetitions,
eligibility, computation total, verification-only correctness, and every planned
case. Case IDs such as `case-0001` identify slots within one run/cohort, not
inputs. Each case records its boundary, outcome, metric median, `median_wall_ns`,
and `peak_rss_kb`. Failed series have null measurements and missing cases are
`not-run`; optional wall time and memory stay null when unavailable. RSS is the
process high-water mark including dependencies, not target-only allocation.
`canonical_work` keeps correctness and computation totals separate, never the
old C+T total.

Use `scripts/score.py` for public reports containing only rankable current-policy
results. `judge.py leaderboard` is for local development and includes failed or
unranked runs; do not publish it as the public board.

## Stage budgets and task deadlines

The revised `evaluation-policy-v2` has this seven-field sealed budget record:

| Budget field | Official value | Scope |
| --- | --- | --- |
| `comparator_timeout_seconds` | 600 | Correctness comparator |
| `audit_timeout_seconds` | 60 | Correctness axiom audit |
| `correctness_replay_timeout_seconds` | 300 | Each of three correctness replay processes |
| `case_build_export_timeout_seconds` | 600 | Shared by one case build and export |
| `case_audit_timeout_seconds` | 300 | Shared by one case binding check and axiom audit |
| `timing_timeout_seconds` | 1800 | Generic/legacy timing ceiling |
| `perf_phase_budget_seconds` | 0 | No aggregate deadline for grouped cases |

Each target replay gets its group's 30-, 60-, or 120-second limit **per
repetition**. Its watchdog includes startup, parsing, and dependency replay even
though the instruction counter does not. Binding must finish successfully and
is fatal otherwise; its axiom audit receives the remainder of the shared 300 seconds.
Nonfatal case failures and build/export timeouts do not consume later cases'
budgets.

All three added fields must appear together. Historical v2 records keep exactly
`comparator/audit/timing/phase = 3600/300/1800/0`; v1 keeps its four-field schema.
Never mix cohorts or add fields to, relabel, or recompute historical policy
identities. Consumers
must accept the historical profiles and the new seven-field profile, but reject
incomplete or mixed forms. Activating new budgets requires an aligned image,
validators, runtime, new cohort, and full comparison-set rescore.
These are configuration limits, not proof of hosted activation or a guarantee
that every valid proof finishes.

Plan outer deadlines from:

```text
600 comparator + 60 correctness audit + 3 × 300 correctness replay
+ sum_over_cases(600 shared build/export + 300 shared case audits + 3 × group_target_limit)
```

The named stages total **8,220 seconds (2 h 17 min)** for a six-case problem and
**18,210 seconds (5 h 3 min 30 s)** for permanent's fifteen cases. Add setup,
reference preparation, auxiliary checks, orchestration, and cleanup. Every outer
task/container/executor deadline must fit the plan; never truncate later cases or
treat an incomplete run as complete.

For development, positive `TIMING_TIMEOUT_SECONDS` (the local and harness
`--timeout`) replaces correctness-replay, case build/export, and generic/legacy
value-evaluation budgets. Target replay uses the smaller override or group limit;
comparator 600, correctness audit 60, and shared case audit 300 stay fixed.
Official runs forbid this override.

## Tools and regression checks

```bash
python3 scripts/sync_participants.py --check
bash evaluation/setup.sh
python3 scripts/run_harness.py
```

The sync check compares fixed specifications and pins without changing
submissions. The harness checks one legal worked submission for all eight
problems against `tests/harness_manifest.json`; negative fixtures and the unit
suite are local-only and not distributed. A pass does not mean every performance
case completed.
For a shorter check, run `python3 scripts/run_harness.py --quick --jobs 2`.
The default is one worker; each may use several GiB, so raise concurrency only
after measuring available memory.

Judge and timer sources are in `evaluation/judge/`, shared pins in
`evaluation/config.json`, and the comparator patch in `evaluation/patches/`.
Setup builds comparator, lean4export, and the timer at pinned revisions and
hard-resets its managed tool checkouts. For a dedicated location, set `TOOLS_DIR`
during setup and then apply its printed `COMPARATOR_BIN`, `LEAN4EXPORT_BIN`, and
`TIMER_BIN` exports; `TOOLS_DIR` alone does not configure the judge.

## Build the image

```bash
docker build -t lean-kernel-judge .
```

The Ubuntu 24.04 image pins Lean 4.33.1 and gates with
`--quick --count 2 --timeout 120` using two workers. Use
`--build-arg HARNESS_JOBS=1` to lower concurrency without reducing coverage.
Any `prebuilt-tools/` binaries must match the image's Linux platform and pinned
sources; otherwise build them from source.

`HARNESS_ONLY=<problem>` and `HARNESS_SKIP=1` are development-only. Mark those
images partially gated or ungated and never promote them. Even the full gate
does not validate official PMU access, full-plan performance, or container
memory; verify those on the production host through the official wrapper.

Rebuild after changing evaluator code, paths, pins, patches, or fixed problem
files. These identities enter the cohort, so never relabel an image or mix its
results with another. Direct integrations invoke `evaluation/judge/judge.py`.

## Export a complete formal-plan candidate

`scripts/export_formal_plan.py` generates a private candidate containing all
**eight problems and 57 configured cases**. It uses the judge's canonical plan
and cohort builders, independent Python reference implementations, and the
official scorer validator. Every configured case and problem memory limit is
included. It needs no dependency cache or prebuilt `.olean`, runs no submission,
Lean process, or kernel replay, and ignores development environment overrides
such as `PERF_COUNT`, shortened timeouts, and remote-executor settings.

Use a dedicated clean host checkout at the **same full commit SHA as the image**.
The exporter verifies the Git revision and tracked state before and after
generation and refuses extra files in hashed problem workspaces. Run it on the
host, not inside the image, which lacks Git metadata. The full image must retain
all eight evaluator workspaces, worked examples, three Mathlib dependency
closures, and the full build gate. Standard evaluation builds each submitted
file; this process neither stores reusable submission `.olean` files nor enables
Light submissions.

Build the exact checkout and obtain its immutable image ID:

```bash
REVISION="$(git rev-parse HEAD)"
docker build --build-arg HARNESS_JOBS=1 \
  --label org.opencontainers.image.revision="$REVISION" \
  -t "lean-kernel-judge:$REVISION" .
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "lean-kernel-judge:$REVISION")"
```

Privately archive the build log, image ID, platform, and host-acceptance evidence.
The revision label alone does not prove the image's source. The exporter checks
only image-ID syntax; it does not inspect Docker or certify PMU/resources. Verify
the source-image association and executor identity/version first. Use the same
`IMAGE_ID`, `EVALUATION_EXECUTOR_ID`, and `EVALUATION_EXECUTOR_VERSION` for later
`run_isolated.sh` jobs and across a managed fleet.

Create a fresh directory outside the repository with mode `0700`. In it, create
a nonempty, newline-terminated UTF-8 `seed.txt` with mode `0600`, at most 1024
bytes before the newline and without NUL. Keep the seed out of arguments,
tracing, and logs. Set the public round and verified executor pair, then run
from the clean checkout:

```bash
# PRIVATE_DIR is the new mode-0700 directory; seed.txt is already mode 0600.
# ROUND, EXECUTOR_ID, and EXECUTOR_VERSION are verified operator values.
python3 -B scripts/export_formal_plan.py \
  --revision "$REVISION" --cohort "$ROUND" --image-id "$IMAGE_ID" \
  --executor-id "$EXECUTOR_ID" --executor-version "$EXECUTOR_VERSION" \
  --output "$PRIVATE_DIR/formal-plan.json" < "$PRIVATE_DIR/seed.txt"
```

Output inside the repository is refused. The destination must not exist; the
exporter atomically creates one mode-`0600` file and exposes no partial output.
Keep it private because it contains the seed, inputs, and answers. Its
`formal-plan-export-v1` fields are:

- `prepare`: `{cohortId, seed, policies}`, with each complete sealed policy;
- `reference_answers`: one `reference-answers-v1` bundle per problem, whose hash
  is sealed in its policy;
- `provenance`: source revision, image, executor, fixed toolchain/checker/protocol,
  evaluator and preparation hashes, and each problem's cohort, policy, plan, and
  answer identities.

This is a prepared candidate, **not** a frozen or active service cohort. It makes
no network request or service change. Before consuming `prepare`, the platform
must separately freeze selection and verify runtime compatibility, acceptance,
and authorization. Send only `prepare`, never the entire export or a replacement
built from problem configs or answer bundles. Accepted results must reproduce
the exact policy. Archive the original export as authoritative; any source,
plan, answer, resource, toolchain, image, or executor change requires a new
candidate and platform transition.

## Official deployment

Use a Linux host with usable hardware instruction counters, cgroup v2, and
Landlock for the pinned sandbox. The timer opens `perf_event_open` itself;
`perf stat` is diagnostic only. Docker alone does not establish PMU support.
The production CPU and full host specification are not yet published; validate
the [environment contract](../rules/evaluation.md#environment) first.

Prepare a private directory and one-line UTF-8 seed file, then run one problem:

```bash
python3 scripts/prepare_reference.py --problem fib --official \
  --output /private/evaluation/fib-answers.json < /private/evaluation/seed.txt

EVALUATION_EXECUTOR_ID="$EXECUTOR_ID" \
EVALUATION_EXECUTOR_VERSION="$EXECUTOR_VERSION" \
PERF_SEED="$(cat /private/evaluation/seed.txt)" bash scripts/run_isolated.sh \
  --problem fib --submission /absolute/path/to/submission \
  --results /absolute/path/to/results --cohort "$ROUND" \
  --reference-answers /private/evaluation/fib-answers.json \
  --image "$IMAGE_ID" --perfmon
```

Pass `--image "$IMAGE_ID"` and use the repository revision, fixed files, cohort,
and executor pair verified for the formal candidate. The submission directory
must contain only `Submission.lean`; the results directory must be writable by
UID 10001.
Reference preparation never overwrites an existing file. Keep seeds and answers
out of version control and logs, unset `PERF_COUNT`, and use one seed and answer
bundle throughout the cohort. The wrapper streams both through stdin rather than
mounting them in the submission workspace.

Bundles bind the complete plan, specification, and dependency lock; regenerate
them when any changes. They are independent of submissions and never replace
the universal proof or per-input kernel check of `impl n = v`.

The wrapper enforces non-root execution, no network, read-only submissions, two
CPUs, 512 processes, fixed per-problem memory, and no extra swap. Permanent uses
8192 MiB; the other seven provisionally use 4096 MiB. `--memory` only asserts the
configured value. `--perfmon` adds the PMU capability but cannot guarantee a
usable counter. Changed limits require a rebuilt image, new cohort, and full
rescore. Official PMU, resource, and full-plan acceptance remain production-host
checks.
