#!/usr/bin/env bash
# Optional judge tools and fixed evaluation dependencies; not needed for quick tests.
set -euo pipefail

EVALUATION_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$EVALUATION_ROOT/scripts/setup.sh" "$@"
