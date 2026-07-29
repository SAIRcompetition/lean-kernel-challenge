#!/usr/bin/env bash
# Run exactly one official evaluation job inside the Docker sandbox.
#
# This is the supported entry point for untrusted submissions.  It deliberately
# exposes no "extra docker arguments" escape hatch: the isolation and resource
# flags below are part of the evaluation contract, not caller suggestions.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
DOCKER_BIN="${DOCKER_BIN:-docker}"

IMAGE="${JUDGE_IMAGE:-lean-kernel-judge}"
MEMORY="${JUDGE_MEMORY:-4g}"
CPUS="${JUDGE_CPUS:-2}"
PIDS_LIMIT="${JUDGE_PIDS_LIMIT:-512}"
PERF_SEED_VALUE="${PERF_SEED:-}"
COHORT="${EVALUATION_COHORT:-}"
PROBLEM=""
SUBMISSION=""
RESULTS_DIR=""
TAG=""
REPS=""
ENABLE_PERFMON=0

usage() {
  cat <<'EOF'
Usage:
  scripts/run_isolated.sh \
    --problem SLUG \
    --submission /absolute/path/to/submission \
    --results /absolute/path/to/results \
    --perf-seed SECRET \
    --cohort ROUND_ID \
    [--tag SLUG] [--reps N] [--image IMAGE] \
    [--memory 4g] [--cpus 2] [--pids-limit 512] [--perfmon]

PERF_SEED may be supplied in the environment instead of --perf-seed.
EVALUATION_COHORT may be supplied in the environment instead of --cohort.
The results directory is bind-mounted read/write and must be writable by the
image's non-root `judge` user (UID 10001 on a native Linux Docker host).
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

need_value() {
  [[ $# -ge 2 && -n "$2" ]] || die "$1 requires a value"
}

valid_slug() {
  [[ "$1" =~ ^[A-Za-z0-9_.-]+$ && "$1" != "." && "$1" != ".." ]]
}

canonical_dir() {
  (cd -- "$1" && pwd -P)
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --problem)
      need_value "$@"
      PROBLEM="$2"
      shift 2
      ;;
    --submission)
      need_value "$@"
      SUBMISSION="$2"
      shift 2
      ;;
    --results)
      need_value "$@"
      RESULTS_DIR="$2"
      shift 2
      ;;
    --perf-seed)
      need_value "$@"
      PERF_SEED_VALUE="$2"
      shift 2
      ;;
    --tag)
      need_value "$@"
      TAG="$2"
      shift 2
      ;;
    --cohort)
      need_value "$@"
      COHORT="$2"
      shift 2
      ;;
    --reps)
      need_value "$@"
      REPS="$2"
      shift 2
      ;;
    --image)
      need_value "$@"
      IMAGE="$2"
      shift 2
      ;;
    --memory)
      need_value "$@"
      MEMORY="$2"
      shift 2
      ;;
    --cpus)
      need_value "$@"
      CPUS="$2"
      shift 2
      ;;
    --pids-limit)
      need_value "$@"
      PIDS_LIMIT="$2"
      shift 2
      ;;
    --perfmon)
      ENABLE_PERFMON=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      die "positional or pass-through arguments are not supported"
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ -n "$PROBLEM" ]] || die "--problem is required"
[[ -n "$SUBMISSION" ]] || die "--submission is required"
[[ -n "$RESULTS_DIR" ]] || die "--results is required"
[[ -n "$PERF_SEED_VALUE" ]] || die "--perf-seed (or non-empty PERF_SEED) is required"
[[ -n "$COHORT" ]] || die "--cohort (or non-empty EVALUATION_COHORT) is required"

valid_slug "$PROBLEM" || die "invalid problem slug: $PROBLEM"
valid_slug "$COHORT" || die "invalid cohort slug: $COHORT"
[[ -f "$ROOT/problems/$PROBLEM/config.json" ]] || die "unknown problem: $PROBLEM"
[[ "$SUBMISSION" == /* ]] || die "--submission must be an absolute path"
[[ "$RESULTS_DIR" == /* ]] || die "--results must be an absolute path"
[[ -d "$SUBMISSION" ]] || die "submission directory does not exist: $SUBMISSION"
[[ -f "$SUBMISSION/Submission.lean" && ! -L "$SUBMISSION/Submission.lean" ]] ||
  die "submission must contain a regular, non-symlink Submission.lean"

mkdir -p -- "$RESULTS_DIR"
[[ -d "$RESULTS_DIR" && -w "$RESULTS_DIR" ]] ||
  die "results directory is not writable by the host runner: $RESULTS_DIR"

SUBMISSION="$(canonical_dir "$SUBMISSION")"
RESULTS_DIR="$(canonical_dir "$RESULTS_DIR")"
[[ "$RESULTS_DIR" != "/" ]] || die "refusing to use the filesystem root as --results"

# Docker's --mount syntax uses commas as separators.  Reject ambiguous sources
# instead of letting Docker parse a different mount from the one we validated.
case "$SUBMISSION$RESULTS_DIR" in
  *","*|*$'\n'*) die "mount paths may not contain commas or newlines" ;;
esac

# Keep the read-only input and writable output trees disjoint on the host.
case "$RESULTS_DIR/" in
  "$SUBMISSION/"*) die "--results may not be inside the submission directory" ;;
esac
case "$SUBMISSION/" in
  "$RESULTS_DIR/"*) die "--submission may not be inside the results directory" ;;
esac

SUBMISSION_NAME="$(basename "$SUBMISSION")"
if [[ -n "$TAG" ]]; then
  valid_slug "$TAG" || die "invalid tag slug: $TAG"
  VERDICT_NAME="$TAG"
else
  valid_slug "$SUBMISSION_NAME" ||
    die "submission directory name is not a safe slug; pass --tag"
  VERDICT_NAME="$SUBMISSION_NAME"
fi

[[ "$IMAGE" =~ ^[A-Za-z0-9][A-Za-z0-9._/@:-]*$ ]] ||
  die "invalid Docker image reference: $IMAGE"
[[ "$MEMORY" =~ ^[1-9][0-9]*([bBkKmMgGtTpP]|[kKmMgGtTpP][bB])?$ ]] ||
  die "invalid non-zero --memory value: $MEMORY"
[[ "$CPUS" =~ ^(0\.[0-9]*[1-9][0-9]*|[1-9][0-9]*([.][0-9]+)?)$ ]] ||
  die "invalid positive --cpus value: $CPUS"
[[ "$PIDS_LIMIT" =~ ^[1-9][0-9]*$ ]] ||
  die "invalid positive --pids-limit value: $PIDS_LIMIT"
if [[ -n "$REPS" ]]; then
  [[ "$REPS" =~ ^[1-9][0-9]*$ ]] || die "invalid positive --reps value: $REPS"
fi
[[ "$PERF_SEED_VALUE" != *$'\n'* ]] || die "PERF_SEED may not contain a newline"
(( ${#PERF_SEED_VALUE} <= 1024 )) || die "PERF_SEED is unreasonably long"
command -v -- "$DOCKER_BIN" >/dev/null 2>&1 || die "Docker executable not found: $DOCKER_BIN"

# The cohort is public. The secret seed is sent once on the evaluation container's
# stdin below; it never enters Docker argv or the container/process environment.
unset PERF_SEED
export EVALUATION_COHORT="$COHORT"
export OFFICIAL_EVAL=1

CONTAINER_RESULTS="/work/lean-kernel-challenge/results"
DOCKER_ARGS=(
  run --rm
  --network none
  --memory "$MEMORY"
  --cpus "$CPUS"
  --pids-limit "$PIDS_LIMIT"
  --security-opt no-new-privileges:true
  --user judge
  --env OFFICIAL_EVAL
  --env EVALUATION_COHORT
  --env TIMING_METRIC=perf_instructions
  --env SANDBOX_MODE=container
  --mount "type=bind,src=$SUBMISSION,dst=/submission,readonly"
  --mount "type=bind,src=$RESULTS_DIR,dst=$CONTAINER_RESULTS"
)
if (( ENABLE_PERFMON )); then
  DOCKER_ARGS+=(--cap-add PERFMON)
fi

# Fail before elaborating untrusted code if UID 10001 cannot write through the
# bind mount.  The preflight uses the exact same isolation/resource envelope.
if ! "$DOCKER_BIN" "${DOCKER_ARGS[@]}" --entrypoint /usr/bin/test "$IMAGE" \
    -w "$CONTAINER_RESULTS"; then
  die "results mount is not writable by container user 'judge' (UID 10001)"
fi

JUDGE_ARGS=(
  python3 judge/judge.py run
  --problem "$PROBLEM"
  --submission /submission
  # `/submission` has a constant basename, so always pin the validated host
  # basename (or explicit --tag) into the verdict filename.
  --tag "$VERDICT_NAME"
)
if [[ -n "$REPS" ]]; then
  JUDGE_ARGS+=(--reps "$REPS")
fi

set +e
printf '%s\n' "$PERF_SEED_VALUE" | \
  "$DOCKER_BIN" "${DOCKER_ARGS[@]}" --interactive --env PERF_SEED_STDIN=1 \
    "$IMAGE" "${JUDGE_ARGS[@]}"
STATUS=${PIPESTATUS[1]}
set -e

VERDICT="$RESULTS_DIR/$PROBLEM/$VERDICT_NAME.json"
if [[ -f "$VERDICT" ]]; then
  echo "verdict preserved at: $VERDICT"
else
  echo "WARNING: container exited $STATUS without writing the expected verdict: $VERDICT" >&2
fi
exit "$STATUS"
