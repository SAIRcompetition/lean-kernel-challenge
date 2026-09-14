# Evaluator maintenance and deployment

Run commands from the repository root. For prerequisites and single-file evaluation,
see [Local evaluation](README.md). The [ranking rule](../rules/problems/README.md#scoring)
uses `computation-total-v1` in current configurations. Follow the
[implementation status](../rules/problems/README.md#implementation-status) before release:
a passing harness or image build does not establish that the hosted platform has upgraded.

## Scoring and result versions

The sealed `evaluation-policy-v2` contains the existing `grouped-evaluation-v1`
plan with ranking `{"contract":"computation-total-v1","work":"curve","proof":"gate"}`.
There is no points field, partial ranking, or correctness-cost tie-break.
Old `full-plan-v1` and `group-points-v1` policies remain readable under their original
semantics. Upgrade the evaluator image and platform consumers together, using a new
cohort and a complete re-evaluation; do not rewrite historical policies or caches.

Raw `correctness_timing` and `timing.scaling` retain their measurement evidence.
The derived `replay_report` (`replay-report-v1`) contains `metric`, `reps`, `eligible`,
`computation_total`, a `correctness` record labeled `verification_only`, and every
planned entry in `cases`. Case IDs such as `case-0001` are slot identifiers scoped
to one run/cohort, not input encodings. Each record names its measurement boundary,
outcome, metric-specific median, `median_wall_ns`, and `peak_rss_kb`. A failed or
invalid series has null measurements; missing cases are `not-run`. Optional wall
and memory measurements remain null when unavailable. RSS is the process high-water
sampled during replay, including preloaded dependencies, not target-only allocation.
`canonical_work` exposes separate `correctness_median` and `computation_total`,
with `correctness_role: "verification-only"`; it no longer has the old C+T `total`.

`scripts/score.py` produces public reports with only rankable new-policy results.
Raw verdicts and `replay_report` are private until the applicable publication rule
allows release. `judge.py leaderboard` produces local development reports, including
unranked and failed runs; do not publish those files as the public board.

## Tools and regression checks

```bash
python3 scripts/sync_participants.py --check
bash evaluation/setup.sh
python3 scripts/run_harness.py
```

The sync check compares fixed specifications and dependency pins without changing
submissions. The public harness checks `tests/harness_manifest.json`: exactly one
legal worked submission for each of the eight problems, with expected acceptance
and minimum performance coverage. Negative and rejection fixtures remain local-only
and are not distributed. A harness pass does not mean every case completed.
The internal unit suite is not distributed. For a shorter development check, use
`python3 scripts/run_harness.py --quick --jobs 2`. The default is one worker;
each can use several GiB, so measure memory before increasing concurrency.

Judge sources and the timer are in `evaluation/judge/`, shared pins and limits in
`evaluation/config.json`, and the comparator patch in `evaluation/patches/`.
Setup builds the pinned comparator with that patch, lean4export, and the replay timer.
It resets managed tool checkouts. To use a dedicated directory, set `TOOLS_DIR` when
running setup, then apply its printed `COMPARATOR_BIN`, `LEAN4EXPORT_BIN`, and
`TIMER_BIN` exports; `TOOLS_DIR` alone does not configure the judge.

## Build the image

```bash
docker build -t lean-kernel-judge .
```

The Ubuntu 24.04 image pins Lean 4.33.1 and uses a wall-time build gate:
`--quick --count 2 --timeout 120`, with two workers. Use
`--build-arg HARNESS_JOBS=1` for lower concurrency without reducing coverage.
If supplying `prebuilt-tools/`, its binaries must match the image's Linux platform
and pinned sources; otherwise use the source-build path.

`HARNESS_ONLY=<problem>` and `HARNESS_SKIP=1` are development-only build arguments.
Label those images partially gated or ungated; never promote them to production.
Production builds must run the full gate. Even that gate does not validate official
PMU access, full-plan performance, or the per-problem container memory envelope.
Verify those through the official wrapper on the production host.

Rebuild after changes to evaluator sources, paths, pins, patches, or fixed problem
files. These identities enter the cohort: do not relabel or mix old and new results.
Direct integrations now invoke `evaluation/judge/judge.py`.

## Official deployment

Use a Linux host with usable hardware instruction counters, cgroup v2, and Landlock
support for the pinned `landrun` sandbox. The timer
opens its own `perf_event_open` counter around replay; `perf stat` is only a diagnostic,
not the scoring mechanism. Docker availability alone does not establish PMU support.
The repository does not yet specify the production CPU model or host configuration. See the
[environment contract](../rules/evaluation.md#environment); validate it before release.

Prepare a private output directory and a one-line UTF-8 seed file, then run:

```bash
python3 scripts/prepare_reference.py --problem fib --official \
  --output /private/evaluation/fib-answers.json < /private/evaluation/seed.txt

PERF_SEED="$(cat /private/evaluation/seed.txt)" bash scripts/run_isolated.sh \
  --problem fib --submission /absolute/path/to/submission \
  --results /absolute/path/to/results --cohort stage1-round1 \
  --reference-answers /private/evaluation/fib-answers.json --perfmon
```

Replace the problem and paths. Use the same repository revision and fixed files as
the image. The submission directory must contain only `Submission.lean`; the results
directory must be writable by UID 10001. Reference preparation refuses to overwrite
an existing file. Keep seeds and answers out of version control and logs, unset
`PERF_COUNT`, and use the same seed and answer bundle throughout a cohort. The wrapper
sends both through stdin, not through mounts into the submission workspace.

Bundles bind the complete plan, specification, and dependency lock. Regenerate them
when these change. Reference answers are independent of submissions and do not replace
the universal proof or the per-input kernel check of `impl n = v`.

The wrapper enforces non-root execution, no network, read-only submissions, 2 CPUs,
512 processes, and each problem's fixed memory limit with zero extra swap. Permanent
uses 8192 MiB; the other seven currently specify provisional 4096 MiB limits.
`--memory` can assert, not override, that limit. `--perfmon` adds only the PMU capability;
it does not guarantee the host can supply the required counter. Changed limits require
a rebuilt image, a new cohort, and a complete rescore of the comparison set. Official
PMU, resource, and full-plan acceptance remain production-host checks.
