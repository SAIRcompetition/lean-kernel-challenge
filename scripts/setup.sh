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
LEAN4CHECKER_REV="$(jqget lean4checker_rev)"

command -v elan >/dev/null || { echo "ERROR: elan (Lean toolchain manager) not found. Install from https://github.com/leanprover/elan"; exit 1; }
command -v gtimeout >/dev/null || echo "WARN: gtimeout not found (macOS: brew install coreutils). Needed by the landrun/timeout shim path."

mkdir -p "$TOOLS_DIR"

clone_build() {
  local name="$1" url="$2" rev="$3" target="$4"
  local dir="$TOOLS_DIR/$name"
  if [ ! -d "$dir/.git" ]; then git clone "$url" "$dir"; fi
  ( cd "$dir" && git checkout "$rev" && lake build "$target" )
}

echo "== building comparator @ $COMPARATOR_REV =="
clone_build comparator https://github.com/leanprover/comparator.git "$COMPARATOR_REV" comparator
echo "== building lean4export @ $LEAN4EXPORT_REV =="
clone_build lean4export https://github.com/leanprover/lean4export.git "$LEAN4EXPORT_REV" lean4export

echo "== building timer-kernel =="
( cd "$HERE/judge/timer-kernel" && lake build )

cat <<EOF

Setup complete. Point the judge at the tools with:
  export COMPARATOR_BIN=$TOOLS_DIR/comparator/.lake/build/bin/comparator
  export LEAN4EXPORT_BIN=$TOOLS_DIR/lean4export/.lake/build/bin
  export TIMER_BIN=$HERE/judge/timer-kernel/.lake/build/bin/kernel
(Defaults already resolve to $TOOLS_DIR when it is the sibling 'repro/' dir.)

Smoke test:
  python3 scripts/run_harness.py --quick --only fib
EOF
