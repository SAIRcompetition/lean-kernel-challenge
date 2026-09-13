# Pre-launch checklist

Outstanding production checks for the Lean Kernel Challenge Stage 1. Every item is a launch
blocker unless marked otherwise.

## 0. Implement the September 9 rules review

The September 9 organizer decisions are recorded at the start of
[`wording-review-2026-09-08.md`](wording-review-2026-09-08.md). They supersede the earlier
partial-credit scoring and contestant-derived output preparation. This follow-up implements
independent reference answers and `full-plan-v1` scoring in LKC, updates all nine configurations,
and synchronizes the published rules. Platform integration and production acceptance remain:

- Prepare and validate official answer bundles on the pinned image using
  [`reference-answers.md`](reference-answers.md). Integrate the wrapper's required
  `--reference-answers` argument into platform orchestration. Test the private stdin transport
  in the real container. Local checks compare Python answers with trusted Lean specifications,
  including the largest polydisc width and a well-founded implementation; they do not establish
  production acceptance of every official batch.
- Align platform scoring with the sealed `full-plan-v1` contract. LKC regression tests cover full
  passes, equal infinite-cost failures with different successful subsets, preserved per-problem
  work policies, invalid reference seals, and incomplete records. Verify that platform fields and
  displayed rankings agree with the canonical scorer, and never mix old and new cohorts.
- Matrix permanent now has an organizer-confirmed `evaluation.memory_mb` of 8192 MiB (8 GiB).
  Confirm and publish the final values for the other eight problems; their 4096 MiB entries
  remain transitional values from the earlier envelope, not calibrated approvals.
  The wrapper now enforces the selected problem's cap with zero extra swap; the judge checks
  the image policy and actual cgroup, remote replay requests use the problem's cap, and the
  scorer checks the sealed limit. Rebuild the image after policy changes; a host/image mismatch
  is an infrastructure error before contestant code runs. Exercise each final cap on the PMU
  host, including permanent R3, and confirm both success and OOM behavior. Revisions require
  a new cohort and a complete rescore of that problem's comparison set.
- Verify the platform's entry selection: use the latest formal submission by recorded submission
  time for each team/problem, including when it is rejected or unscored. Pending evaluation and
  infrastructure retries must not cause fallback to an older submission.
  Exercise missing, unreadable, and corrupt retained source: preserve the selected identity,
  neither omit the team/problem nor use an older submission, and block complete final freeze
  until the original formal source is recovered and verified. Later Playground edits and
  post-deadline submissions must not substitute for that source.
- Verify a daily edition containing accepted, rejected, accepted-but-unscored, and classified
  terminal-error outcomes. Terminal errors count as processed, displace older successes without
  a public failure row, and create no score or rank. The entitled team must be able to query a
  sanitized error status/reason instead of seeing the task remain waiting. Once all selected
  entries are terminal, later dates must proceed without first recovering errors successfully.
  Pending, running, retrying, missing, or unknown outcomes must still prevent completion; a
  missing result or elapsed time alone must not classify an error. Retain error evidence and
  verify that daily settlement does not change final-evaluation or scoring requirements.
- Apply the confirmed daily mode limits: Standard 2 and Light 5. First resolve whether limits are
  per team across all problems or per team/problem, whether formal submissions share the Standard
  allowance, and how rejected submissions, cancellations, and infrastructure retries affect it.
- Use UTC calendar days for daily submission cutoffs, including the complete last second
  `23:59:59`; implement the interval as inclusive midnight to exclusive next midnight. Display
  each leaderboard edition's generation timestamp with its time zone. Also identify its submission
  cutoff or coverage date so users can distinguish publication time from submission coverage.
  Specify the publication lag and handling of editions that finish after their planned publication
  time; neither the cutoff nor the publication target is an evaluation timeout. Verify that an
  unfinished edition retains the previous complete board with a delay notice, or a preparation
  notice before the first edition, without publishing partial results or shortening resource limits.
- Complete the published code-release policy by specifying the submission versions covered,
  license, and applicable participation terms. Private during competition / public afterward is
  already stated in the rules.
- Resolve the organization/team scope: the referenced Equational Theories Stage 2 rules use the
  same sentence as LKC and do not define a university exception or the organizational unit.
- Align platform opening with the published tentative launch time: September 15, 2026, 22:00 PT
  (`America/Los_Angeles`), equivalent to September 16, 2026, 05:00 UTC. The time may be revised;
  update the rules and platform together before opening submissions or the Playground.
  The final evaluation window and publication schedule may remain explicitly pending at launch;
  announce them when determined. Platform answers must not supply a default opening time or an
  early Playground opening.

The six target-work problem configurations use `work: curve, proof: gate`; `saw`, `ca-rule110`,
and `sha256` retain `work: total, proof: include`. Regression checks exercise these policies
through the full-plan scorer. The official cohort dry run below must verify the production
rankings and answer-bundle integration.

Then exercise the revised policies through the official wrapper. The image-build harness checks
manifest verdicts, record structure, and declared minimum performance coverage in development
mode; passing it does not establish full performance coverage or per-problem memory enforcement.

## 1. Official PMU evaluation sweep

The nine scored problems have published input groups, generators, case counts, and limits in
[`../rules/problem-scoring.md`](../rules/problem-scoring.md). Use the complete competition plans
rather than local smoke ranges. `conv` is excluded from the nine leaderboards.

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

Prove the PMU path itself first. The judge preflights `perf stat -e instructions` after the
correctness gate and axiom audit, before timed replay. It refuses a user-only (`instructions:u`)
downgrade, so a broken
counter fails loudly — but the host must still pass that preflight: confirm the Ubuntu
`linux-tools` wrapper has a perf build for the *running* kernel (it resolves via `uname -r`, so a
host kernel update without an image rebuild breaks it), and that `--perfmon` plus the host
`perf_event_paranoid` setting deliver kernel-scope counts to the non-root container user. Pin
`EVALUATION_EXECUTOR_ID`/`EVALUATION_EXECUTOR_VERSION` explicitly for the fleet: the default
derivation hashes `/proc/cpuinfo` including microcode, so a routine host security update mid-round
would rotate the cohort id and fork the leaderboard.

Also measure the preparation overhead for every current group using a trivial implementation.
Check reference-answer preparation, theorem build/export, axiom audit, and replay separately
against their applicable limits. Validate that at least one known implementation can pass the
complete plan for each problem, and record the tested commit, problem policy, host, and
measurements. Historical measurements from retired groups do not establish feasibility for the
current policies.

If this check reveals an infrastructure defect, fix it and publish any required policy revision
before creating the first official cohort. Do not silently change the scoring policy, cases, or
limits after evaluation begins.

## 2. Resource-failure behavior

The grouped policies publish per-case target-replay time limits. The production environment must
enforce the problem's configured memory limit; item 0 still requires final values and host acceptance. Each grouped case has
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
unreachability, process containment, a bounded memory canary with a success control, and refusal of an official run without
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

- full-plan passes score 100 points with finite cost;
- a complete, valid plan with any failed case scores 0 points with infinite ranking cost,
  regardless of how many other cases pass or which groups they belong to;
- incomplete runs and infrastructure failures remain unscored;
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
full-plan ranking; revise and publish the policy before sealing if a change is needed. Do not infer
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
