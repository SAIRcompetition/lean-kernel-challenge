#!/usr/bin/env bash
# One-command environment bootstrap for the kernel-computation track.
# Builds the pinned verification tools (comparator, lean4export, timer-kernel)
# and reports where the judge will find them. Idempotent.
#
# Env:
#   TOOLS_DIR   where to clone/build comparator + lean4export (default: ../repro)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # lean-kernel-challenge/
CFG="$HERE/pipeline/config.json"
TOOLS_DIR="${TOOLS_DIR:-$(cd "$HERE/.." && pwd)/repro}"

jqget() { python3 -c "import json,sys;print(json.load(open('$CFG'))['toolchain']['$1'])"; }
COMPARATOR_REV="$(jqget comparator_rev)"
LEAN4EXPORT_REV="$(jqget lean4export_rev)"

command -v elan >/dev/null || { echo "ERROR: elan (Lean toolchain manager) not found. Install from https://github.com/leanprover/elan"; exit 1; }
command -v gtimeout >/dev/null || echo "WARN: gtimeout not found (macOS: brew install coreutils). Needed by the landrun/timeout shim path."

mkdir -p "$TOOLS_DIR"

clone_build() {
  local name="$1" url="$2" rev="$3" target="$4" patch="${5:-}"   # patch optional (set -u safe)
  local dir="$TOOLS_DIR/$name"
  if [ ! -d "$dir/.git" ]; then git clone "$url" "$dir"; fi
  ( cd "$dir"
    # Existing tool checkouts may predate a newly pinned revision. Fetch that exact
    # commit (only when it is not already local, so offline re-runs keep working),
    # then hard-reset so a previously applied patch cannot survive in the index or
    # worktree — `git apply` stages nothing, but an interrupted run or an older
    # `--3way` apply may have; `checkout -- .` restores from the index and would
    # keep it, breaking both same-pin re-runs and in-place upgrades.
    git cat-file -e "$rev^{commit}" 2>/dev/null || git fetch --quiet origin "$rev"
    git reset --hard --quiet
    git checkout --quiet "$rev"
    if [ -n "$patch" ]; then
      echo "   applying $patch"
      git apply "$HERE/$patch" || { echo "ERROR: failed to apply $patch"; exit 1; }
    fi
    # Tool tags may lag the challenge toolchain (e.g. v4.33.0 tools on v4.33.1).
    # Build them with the challenge Lean so .olean headers match problem workspaces.
    cp "$HERE/lean-toolchain" lean-toolchain
    lake build "$target" )
}

echo "== building comparator @ $COMPARATOR_REV (+ emit-export patch) =="
# The Lean Kernel Challenge requires comparator to emit the exact export it verified,
# so the judge can time that immutable file (closes the comparator→timed-export TOCTOU).
clone_build comparator https://github.com/leanprover/comparator.git "$COMPARATOR_REV" comparator patches/comparator-emit-export.patch
echo "== building lean4export @ $LEAN4EXPORT_REV =="
clone_build lean4export https://github.com/leanprover/lean4export.git "$LEAN4EXPORT_REV" lean4export

echo "== building timer-kernel =="
( cd "$HERE/judge/timer-kernel" && lake build )

echo "== preparing fib's pinned Mathlib dependency closure =="
python3 "$HERE/scripts/prepare_problem_dependencies.py" --problem fib

cat <<EOF

Setup complete. Point the judge at the tools with:
  export COMPARATOR_BIN=$TOOLS_DIR/comparator/.lake/build/bin/comparator
  export LEAN4EXPORT_BIN=$TOOLS_DIR/lean4export/.lake/build/bin
  export TIMER_BIN=$HERE/judge/timer-kernel/.lake/build/bin/kernel
(Defaults already resolve to $TOOLS_DIR when it is the sibling 'repro/' dir.)

Smoke test:
  python3 scripts/run_harness.py --quick --only fib
EOF
