# Pre-launch checklist

Outstanding production checks for the Lean Kernel Challenge Stage 1. Every item is a launch
blocker unless marked otherwise.

## 1. Official PMU evaluation sweep

The nine scored problems now have published difficulty groups, generators, case counts,
milestones, and limits in [`../rules/problem-scoring.md`](../rules/problem-scoring.md). These are
the competition contract, not local smoke ranges. `conv` is excluded from the nine leaderboards.

> **Superseded (2026-09-04):** the five-group policy that the items below reference was
> replaced by a uniform three-group policy arranged by order of magnitude of peak memory
> (about 0.03 / 0.3 / 3 GiB on the baseline solutions, every case under an 8 GiB cap). Group
> ids, ranges, and limits quoted below describe the retired layout; `rules/problem-scoring.md`
> carries the current contract.

The full grouped plans have not yet been measured with `perf -e instructions` on the official
bare-metal Linux executor. Local calibration used wall time and cannot validate production
instruction counts or PMU behavior.

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

Also measure a preparation-only floor for every group using a trivial implementation, because
several sealed watchdogs look inverted against dev measurements: `permanent` R1–R5 seal 2–3 s
whole-process watchdogs while timer startup + export parsing are the same order; `sha256` H5's 512
chain steps measured ≈133 s on dev against a 120 s watchdog; `saw` S4/S5 kernel reduction grew
memory at ~250–300 MB/s on dev, so the 4 GiB envelope binds near ~15 s and their real failure mode
may be OOM rather than the published timeout; `mertens` M5 (10^5–3·10^5) and `primecount` Q5
(3–10·10^6) sit far beyond any measured kernel computation — validate that at least one known
implementation can score there, or expect those 38–45 point blocks to go permanently unawarded.

If this check reveals an infrastructure defect, fix it and publish any required policy revision
before creating the first official cohort. Do not silently change a group's cases, points, or
limits after evaluation begins.

## 2. Resource-failure behavior

The grouped policies publish per-case target-replay time limits. The production environment
supplies the common 4 GiB memory envelope. Each grouped case has independent preparation and
replay limits; there is no order-dependent aggregate performance deadline.
The judge records a case-preparation or target-replay child killed by the attested job cgroup as a
failed `resource-limit` case only when cgroup-v2 `memory.events` records a new OOM kill.
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

`.github/workflows/isolation-wrapper.yml` has a manual job that builds the image and checks network
unreachability, process containment, and refusal of an official run without
`ISOLATION_ATTESTATION`. It has not been executed in the current development environment because
Docker is unavailable there.

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
- the problem-specific kernel-work and proof-work tie-breaks are applied; and
- exact hidden inputs and raw verdicts remain private until the evaluation phase closes.

Rotate the seed and cohort id once and confirm that the complete comparison set is rescored rather
than mixing cohorts.

## 5. ca-rule110 orbit structure — decide before sealing

Measured on the shipped 256-cell seeded spec (Python port cross-checked against the frozen
vectors): roughly three quarters of seeds enter a periodic orbit well below the top groups' step
counts — 44/60 sampled seeds repeat a state within the C5 workload of 131,072 steps, 43 of them
within 8,192 steps, with median first repeat ≈2,100 steps and observed cycle lengths 7–1,536. A
submission can therefore compute a few thousand steps, prove the repeat by kernel computation
(the shipped bit-packed example already provides a proved-equal step), and reduce the step count
modulo the cycle — winning C4/C5 (26 + 36 points) at a few percent of the intended work on
cycling seeds, while the remaining ~27 % of seeds admit no shortcut. With only 2 seeds per group,
top-milestone outcomes then hinge on seed luck rather than kernel speed.

**To close, pick one and land it before the first sealed cohort:** (a) publish cycle-jumping as
intended kernel-fu and re-price C4/C5 accordingly; (b) restore the intended scaling by widening
the row (512–1,024 cells pushes typical transients far beyond 131,072) or capping the ladder near
the typical transient (~8k steps); or (c) filter seeds operator-side at plan time — reject seeds
whose orbit repeats before the largest configured step count (deterministic given the seed, cheap
in Python, and requires no Lean-side change).

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

- Grouped v2 deliberately has no aggregate performance deadline, so the worst-case official job
  is bounded only by the sum of per-case ceilings: ≈21–27 hours for `permanent` (25 cases) or
  `polydisc` (10 cases × up to 900 s watchdog ×3 reps plus preparation ceilings). Give the batch
  orchestrator an outer wall cap computed from the sealed plan (sum of ceilings + margin) that
  maps to `retry`.
- `permanent` R1 (dimension 4) admits only permanents {6, 8, 9} under the three-ones-per-row
  construction; acceptable as a warm-up group, but document it, and never configure dimension ≤ 3
  (dimension 3 degenerates to the all-ones matrix for every seed).

## 8. Additional optimized examples — optional

Several problems still ship only a baseline submission. More proved optimized examples would make
the intended algorithmic ladder easier to understand, but they are not part of the scoring
contract and do not block launch.
