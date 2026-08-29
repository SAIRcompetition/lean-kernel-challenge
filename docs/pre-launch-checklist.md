# Pre-launch checklist

Outstanding production checks for the Lean Kernel Challenge Stage 1. Every item is a launch
blocker unless marked otherwise.

## 1. Official PMU evaluation sweep

The nine scored problems now have published difficulty groups, generators, case counts,
milestones, and limits in [`../rules/problem-scoring.md`](../rules/problem-scoring.md). These are
the competition contract, not local smoke ranges. `conv` is excluded from the nine leaderboards.

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

## 5. Additional optimized examples — optional

Several problems still ship only a baseline submission. More proved optimized examples would make
the intended algorithmic ladder easier to understand, but they are not part of the scoring
contract and do not block launch.
