# Pre-launch checklist

Outstanding production checks for the Lean Kernel Challenge Stage 1. Every item is a launch
blocker unless marked otherwise.

## 0. Implement the September 9 rules review

The reviewed rule text includes policy changes whose implementation must be aligned before
official evaluation. Updating the documents does not complete these items:

- Publish and configure a separate memory limit for each problem. The values are not yet set.
  Replace the current fixed 4 GiB assumptions in the wrapper, scorer, OOM attribution, and remote
  validation requests with the applicable problem policy. Each cohort must seal its limit;
  revisions require a new cohort and a complete rescore of that problem's comparison set.
- Verify the platform's entry selection: use the latest formal submission by recorded submission
  time for each team/problem, including when it is rejected or unscored. Pending evaluation and
  infrastructure retries must not cause fallback to an older submission.
- Announce the exact launch time and time zone before opening submissions or the Playground.
  The final evaluation window and publication schedule may remain explicitly pending at launch;
  announce them when determined. Platform answers must not supply a default opening time or an
  early Playground opening.

The six target-work problem configurations use `work: curve, proof: gate`; `saw`, `ca-rule110`,
and `sha256` retain `work: total, proof: include`. Regression checks exercise these policies
through the scorer. The official cohort dry run below must also verify their rankings.

Then exercise the revised policies through the official wrapper. The image-build harness checks
manifest verdicts, record structure, and declared minimum performance coverage in development
mode; passing it does not establish full performance coverage or per-problem memory enforcement.

## 1. Official PMU evaluation sweep

The nine scored problems now have published difficulty groups, generators, case counts,
milestones, and limits in [`../rules/problem-scoring.md`](../rules/problem-scoring.md). These are
the competition contract, not local smoke ranges. `conv` is excluded from the nine leaderboards.

Historical scales, memory assumptions, and development measurements are preserved in
[`history/prelaunch-calibration-2026-09-07.md`](history/prelaunch-calibration-2026-09-07.md).
Use the current problem configurations and published policies for every check below.

The full grouped plans must be measured with `perf -e instructions` on the official bare-metal
Linux executor. Record acceptance for the current policies. Local wall-time calibration cannot
validate production instruction counts or PMU behavior.

**To close:** run every official group through `scripts/run_isolated.sh` with the pinned executor,
three timing repetitions, an official seed, and an official cohort. Confirm that:

- every verdict contains the sealed `evaluation-policy-v2` plan and its hash;
- every planned group/case has an explicit outcome;
- instruction counts are stable enough for deterministic ranking; and
- the published replay limits, independent preparation caps, and memory envelope are
  operationally feasible.

Prove the PMU path itself first. The judge now preflights `perf stat -e instructions` before
elaborating any submission and refuses a user-only (`instructions:u`) downgrade, so a broken
counter fails loudly — but the host must still pass that preflight: confirm the Ubuntu
`linux-tools` wrapper has a perf build for the *running* kernel (it resolves via `uname -r`, so a
host kernel update without an image rebuild breaks it), and that `--perfmon` plus the host
`perf_event_paranoid` setting deliver kernel-scope counts to the non-root container user. Pin
`EVALUATION_EXECUTOR_ID`/`EVALUATION_EXECUTOR_VERSION` explicitly for the fleet: the default
derivation hashes `/proc/cpuinfo` including microcode, so a routine host security update mid-round
would rotate the cohort id and fork the leaderboard.

Also measure the preparation overhead for every current group using a trivial implementation.
Check value generation, theorem build/export, axiom audit, and replay separately against their
applicable limits. Validate that at least one known implementation can score each intended
milestone, and record the tested commit, problem policy, host, and measurements. Historical
measurements from retired groups do not establish feasibility for the current policies.

If this check reveals an infrastructure defect, fix it and publish any required policy revision
before creating the first official cohort. Do not silently change a group's cases, points, or
limits after evaluation begins.

## 2. Resource-failure behavior

The grouped policies publish per-case target-replay time limits. The production environment must
enforce the problem's published memory limit once item 0 is implemented. Each grouped case has
independent preparation and replay limits; there is no order-dependent aggregate performance
deadline. Required behavior: record a case-preparation or target-replay child killed by the attested
job cgroup as a failed `resource-limit` case only when cgroup-v2 `memory.events` records a new OOM kill.
Non-official KTP/3 has the same outcome for replay only; case preparation remains local. Correctness-gate
memory exhaustion is a rejection, while timed correctness-replay exhaustion is accepted but
unscored. The complete failure path has not yet been exercised on the official host.

**To close:** test representative preparation steps and target replays that time out, plus jobs
that exceed memory. A contestant case that exceeds its limit must receive a recorded unsuccessful
outcome, while a genuine judge or executor failure must remain an infrastructure error. Confirm
that one case's timeout does not shorten or suppress any later case.

The wrapper now pins `--memory-swap` to the memory limit (zero extra swap), closing the path where
an over-limit job thrashed into swap instead of OOM-killing; the canary must still prove a real
over-limit child inside the wrapper yields a `memory.events` `oom_kill` delta plus SIGKILL and the
published per-case classification. Two attribution caveats to verify operationally: `oom_kill`
counts the whole envelope, so run official jobs on an otherwise idle host (a host-global OOM kill
inside the bracket would be misattributed to the submission), and an escaped same-UID descendant
surviving the comparator stage can shift OOM attribution across later cases — consider a
stage-boundary process sweep before the performance phase.

## 3. Real-container isolation

`.github/workflows/isolation-wrapper.yml` runs on pull requests, pushes, and manual dispatch. It
builds the image and checks network
unreachability, process containment, and refusal of an official run without
`ISOLATION_ATTESTATION`. A passing CI run checks that runner's container environment; production
host acceptance must be recorded separately.

**To close:** run the workflow, or the same commands on the production Docker host, and confirm all
negative tests and positive controls. Also verify the non-root user, read-only submission mount,
result-directory ownership, CPU and memory limits, disabled network, and immutable image digest.

## 4. Official cohort dry run

The grouped scorer separates every problem, metric, executor, measurement contract, and cohort.
It does not compute a cross-problem standing.

**To close:** perform one end-to-end dry cohort with at least two submissions per scored problem.
Regenerate the canonical tables with `scripts/score.py` and verify, for each independent
leaderboard:

- milestone points match the sealed policy;
- harder-group points and harder-case outcomes break ties in the documented order;
- the problem-specific target-work or combined-work comparison is applied without an additional
  correctness-cost tie-break; and
- exact hidden inputs and raw verdicts remain private until the evaluation phase closes.

Rotate the seed and cohort id once and confirm that the complete comparison set is rescored rather
than mixing cohorts.

## 5. Generator and workload review

The old Rule 110 cycle-jumping analysis concerned retired high-step groups. Current C1/C2/C3
use 2/4/8 steps. The old analysis is archived above and does not require a row-width change,
seed filter, or repricing of nonexistent C4/C5 groups before launch.

**To close:** review the generators and workloads against the current problem tables during the
PMU sweep. Record any remaining shortcut or degeneracy that materially affects the current
milestones; revise and publish the policy before sealing if a change is needed. Do not infer
current behavior from the retired Rule 110 scales or the old dimension-4 permanent warm-up.

## 6. Sealed-verdict authority — remaining hardening

The scorer now pins official budgets and the toolchain to the checked-in `pipeline/config.json`,
refuses one round spanning multiple official cohorts (`ALLOW_COHORT_SPLIT=1` overrides), requires
full policy-hash agreement inside each ranking table, and only accepts a verdict under the problem
whose `results/` directory contains it. Still open: the seals are plain unkeyed hashes over data
carried inside the same verdict, so `problem_bundle_sha256`, `evaluator_bundle_sha256`, and
`seed_commitment` are validated for shape but not authenticity. Closing that requires an
out-of-band cohort registry (or an operator-key MAC over the sealed policy) that the scorer reads
and matches, plus verifying the seed commitment against the published seed when a cohort closes.
Until then, custody of `results/` is part of the trust boundary. Not a launch blocker if the
results tree is operator-controlled, but decide explicitly.

## 7. Operational notes — non-blocking

Grouped v2 deliberately has no aggregate performance deadline. Derive an orchestrator wall
limit from the sealed plan's case counts, per-phase ceilings, replay repetitions, correctness
budgets, and an explicit overhead margin. An interruption leaves the run incomplete and requires
re-evaluation of the same selected submission; do not turn omitted cases into scored failures.
Retired case counts and the historical 21–27 hour estimate are not scheduling defaults.

## 8. Additional optimized examples — optional

Several problems still ship only a baseline submission. More proved optimized examples would make
the intended algorithmic ladder easier to understand, but they are not part of the scoring
contract and do not block launch.
