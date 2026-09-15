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

## Stage budgets and task deadlines

The proposed stage-budget revision keeps `evaluation-policy-v2` and
`computation-total-v1`. It expands the sealed `budgets` record from four fields
to six so correctness replay and case preparation have separate limits:

| Budget field | Revised official value | Scope |
| --- | --- | --- |
| `comparator_timeout_seconds` | 600 | Correctness comparator |
| `audit_timeout_seconds` | 60 | Correctness axiom audit; separately, the shared binding-plus-axiom budget for each case |
| `correctness_replay_timeout_seconds` | 300 | Each of the three correctness replay processes |
| `case_build_export_timeout_seconds` | 600 | One shared deadline across the case theorem's build and export |
| `timing_timeout_seconds` | 1800 | Retained generic/legacy timing ceiling; not the new correctness or case-preparation budget |
| `perf_phase_budget_seconds` | 0 | No shared aggregate deadline across grouped cases |

The per-group target watchdogs remain 30, 60, and 120 seconds **per repetition**.
They include the timing process's startup, parsing, and dependency replay even
though those steps are outside its instruction counter. Case binding must succeed;
an unfinished binding check remains fatal. The axiom check receives the remainder
of that case's shared 60-second audit deadline. A case build/export timeout or a
nonfatal case failure does not consume later cases' budgets.

Both new fields must appear together. Official historical v2 records with only
the original four fields retain exactly their frozen 3600/300/1800/0 budget tuple;
v1 retains its four-field schema. Do not add fields to, relabel, or recompute the
identity of historical policies. Consumers must recognize the new six-field
record and reject incomplete or mixed profiles before importing new results.
Rebuild the evaluator image, update platform validators and runtime compatibility,
prepare a new sealed candidate/cohort, and re-evaluate the comparison set together.
The proposed values are reviewable configuration limits, not evidence of hosted
activation or a guarantee that all valid proofs meet them.

For scheduling, the main watchdog allowances for one full official run sum to:

```text
600 comparator + 60 correctness audit + 3 × 300 correctness replay
+ sum_over_cases(600 shared build/export + 60 shared audits + 3 × group_target_limit)
```

With the current three groups, this is **6,780 seconds (1 h 53 min)** for six
cases, two per group. For permanent's fifteen cases, five per group, it is
**14,610 seconds (4 h 3 min 30 s)**. These are planning totals for the named stages,
not complete end-to-end wall-time bounds or typical runtimes: setup, independent
reference-answer preparation, auxiliary checks, orchestration, and cleanup need
their own allowance. Do not blindly reuse or raise one global timeout. Check the
actual plan and every encompassing task/container/executor deadline so the
declared stages and those allowances fit. A shorter outer deadline must not
silently truncate later cases or turn an incomplete run into a completed result.

Development `TIMING_TIMEOUT_SECONDS` retains its existing override semantics:
a valid positive value replaces the correctness-replay, case build/export, and
generic timing/legacy value-evaluation budgets, and can increase or decrease them.
Target replay uses the smaller of that value and its group's watchdog. Comparator
and audit limits are unaffected and remain 600 and 60 seconds. The local wrapper's
`--timeout` and the harness's `--timeout` use this override. It is forbidden for
official runs and must not be used to make a new cohort fit an undersized platform
deadline.

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

## Export a complete formal-plan candidate

`scripts/export_formal_plan.py` generates the complete policy map needed by a
platform's formal preparation step. It calls the judge's canonical plan and cohort
builders, the independent Python reference-answer implementations, and the scorer's
official-policy validator. It does not run submissions, Lean, or kernel replay.
No dependency cache or prebuilt `.olean` is required for this data-only step.
All eight active problems are mandatory; each uses every case in its committed
configuration, including its own memory limit. Environment overrides such as
`PERF_COUNT`, shortened timeouts, and remote executors do not change the export.

Use a dedicated clean host checkout at the **same full commit SHA as the image**.
The command verifies that SHA against Git, refuses tracked modifications and extra
files in the hashed problem workspaces, and checks again before publishing. Run it
on the host checkout, not inside the runtime image, which has no Git metadata.
The image build remains self-contained: it retains all eight evaluator workspaces
and worked examples, prepares the three locked Mathlib dependency bundles, and runs
the build gate. It does not retain a reusable `Submission.olean` for each problem;
Standard evaluation builds each submitted file separately. This procedure does not
prepare or enable Light submissions.

After building the exact checkout with the full gate, obtain the immutable image ID:

```bash
REVISION="$(git rev-parse HEAD)"
docker build --build-arg HARNESS_JOBS=1 \
  --label org.opencontainers.image.revision="$REVISION" \
  -t "lean-kernel-judge:$REVISION" .
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "lean-kernel-judge:$REVISION")"
```

Archive the build log, image ID, platform, and host-acceptance evidence privately.
An image label is an operator assertion, not proof that its bytes came from a
particular checkout. The exporter validates the supplied image ID's format but does
not inspect Docker, execute that image, or certify PMU/resource availability.
Verify that association and the executor's identity/version before preparing the
candidate. Supply the same explicit `EVALUATION_EXECUTOR_ID` and
`EVALUATION_EXECUTOR_VERSION` to subsequent `run_isolated.sh` jobs; do not let the
wrapper independently derive a different identity. Fleet integrations must use
their configured executor pair and the same image ID.

Create a fresh directory outside the repository with mode `0700` and a nonempty, newline-terminated UTF-8
seed file with mode `0600`, at most 1024 bytes before the newline. Keep secrets out
of command arguments, shell tracing, and logs. Set the public round label and the
verified executor pair, then run from the clean checkout:

```bash
# PRIVATE_DIR names the new mode-0700 directory; seed.txt is already mode 0600.
# ROUND, EXECUTOR_ID, and EXECUTOR_VERSION are the operator's verified values.
python3 -B scripts/export_formal_plan.py \
  --revision "$REVISION" --cohort "$ROUND" --image-id "$IMAGE_ID" \
  --executor-id "$EXECUTOR_ID" --executor-version "$EXECUTOR_VERSION" \
  --output "$PRIVATE_DIR/formal-plan.json" < "$PRIVATE_DIR/seed.txt"
```

Output inside the repository is refused, including through a symlinked parent, so
private data cannot enter the image context or change a sealed problem digest.
The output is one atomically published mode-`0600` JSON file; an existing path,
including a symlink, is never overwritten. Failed generation does not expose a
partial export. Keep the entire file private: it contains the seed, inputs, and
answers. Standard output contains only a count and preparation status.
`formal-plan-export-v1` contains:

- `prepare`: the request body `{cohortId, seed, policies}`, with each complete
  `evaluation-policy-v2` exactly as the judge will seal it.
- `reference_answers`: one `reference-answers-v1` bundle for each problem. Its
  canonical hash is sealed in the corresponding policy.
- `provenance`: the committed source revision, supplied image and executor identity,
  fixed toolchain/checker/protocol, evaluator hash, canonical preparation-request
  hash, and each problem's cohort, policy, plan, and answer identities.

The file is a **prepared, sealed candidate**, not a frozen or active server cohort.
It performs no network requests and changes no service state. The platform must
separately satisfy its selection-freeze, runtime-compatibility, acceptance, and
authorization requirements before consuming `prepare`. Do not send the whole
export file to the API, and do not replace `policies` with problem `config.json`
files or reference-answer bundles. Subsequent accepted results must reproduce
the exact prepared policy, including the seed commitment and answer seal.

If separate files are needed, this extraction creates a new mode-`0700` directory
and exclusive mode-`0600` files without printing their contents:

```bash
python3 - "$PRIVATE_DIR/formal-plan.json" "$PRIVATE_DIR/extracted" <<'PY'
import json, os, pathlib, sys
source, dest = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
data = json.loads(source.read_text())
assert data["schema"] == "formal-plan-export-v1"
os.mkdir(dest, 0o700)  # Existing destinations are errors, never reused.
items = {"prepare.json": data["prepare"], "provenance.json": data["provenance"]}
items.update({f"{problem}-answers.json": bundle
              for problem, bundle in data["reference_answers"].items()})
for name, value in items.items():
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    fd = os.open(dest / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(payload)
PY
```

Archive the original export as the authoritative artifact. If extraction is
interrupted, use a new destination directory; do not publish partial extracted
files. A source, input plan, answer, resource, toolchain, image, or executor change
requires a newly prepared candidate and the corresponding platform transition.

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
