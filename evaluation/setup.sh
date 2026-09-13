#!/usr/bin/env bash
# Optional judge tools and fixed evaluation dependencies; not needed for participant builds.
set -euo pipefail

EVALUATION_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUPPORTED=(fib ca-rule110 mertens partition permanent polydisc primecount sha256)
SELECTED=()

usage() {
  echo "Usage: bash evaluation/setup.sh [--problem PROBLEM ...]"
  echo "Default: prepare all eight supported problems (${SUPPORTED[*]})."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --problem)
      [[ $# -ge 2 ]] || { echo "ERROR: --problem requires a value" >&2; exit 2; }
      case " ${SUPPORTED[*]} " in
        *" $2 "*) ;;
        *) echo "ERROR: unsupported problem: $2" >&2; exit 2 ;;
      esac
      case " ${SELECTED[*]-} " in
        *" $2 "*) ;;
        *) SELECTED+=("$2") ;;
      esac
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${#SELECTED[@]} -eq 0 ]]; then
  SELECTED=("${SUPPORTED[@]}")
fi

# Resolve every trusted workspace before building shared tools or downloading dependencies.
PROBLEM_DIRS=()
for problem in "${SELECTED[@]}"; do
  PROBLEM_DIRS+=("$(python3 "$EVALUATION_ROOT/scripts/problem_layout.py" --problem "$problem")")
done

bash "$EVALUATION_ROOT/scripts/setup.sh" --tools-only
for problem_dir in "${PROBLEM_DIRS[@]}"; do
  if [[ -f "$problem_dir/dependency-lock.json" ]]; then
    python3 "$EVALUATION_ROOT/scripts/prepare_problem_dependencies.py" --problem "$(basename "$problem_dir")"
  fi
done
echo "Evaluator setup complete: ${SELECTED[*]}"
