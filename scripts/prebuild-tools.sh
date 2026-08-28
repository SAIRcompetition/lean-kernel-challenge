#!/usr/bin/env bash
# Build the pinned verification tools on the HOST into <repo>/prebuilt-tools/,
# which the judge image Dockerfile copies instead of compiling them inside the
# image. The produced tree is gitignored; deleting it makes the Dockerfile fall
# back to the historical in-image source build, so image content is unchanged
# either way. Idempotent: re-running rebuilds only what the pinned revisions
# require.
#
# Requirements on the host: elan with the repo's pinned toolchain, git, python3.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # lean-kernel-challenge/
OUT="${1:-$HERE/prebuilt-tools}"
mkdir -p "$OUT"

# comparator + lean4export land in prebuilt-tools/tools (setup.sh honors
# TOOLS_DIR); setup.sh also builds the repo-local timer-kernel in place.
TOOLS_DIR="$OUT/tools" bash "$HERE/scripts/setup.sh"

# The image resolves TIMER_BIN at
# /work/lean-kernel-challenge/judge/timer-kernel/.lake/build/bin/kernel; ship
# only the built binaries — the kernel source already travels with the repo.
mkdir -p "$OUT/timer-kernel/.lake/build"
cp -a "$HERE/judge/timer-kernel/.lake/build/bin" "$OUT/timer-kernel/.lake/build/"

echo "prebuilt verification tools staged at $OUT"
