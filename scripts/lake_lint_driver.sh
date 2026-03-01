#!/usr/bin/env bash
set -euo pipefail

# Keep `lake lint` separate from `lake test` so we can tighten it later.
# For now it runs the deterministic core gates (fast, no Lean needed).

if [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
  export VIRTUAL_ENV="$(pwd)/.venv"
  export PATH="$(pwd)/.venv/bin:$PATH"
else
  PY="${PYTHON:-python3}"
  if ! command -v "$PY" >/dev/null 2>&1; then
    PY="python"
  fi
fi

export PYTHON="$PY"

exec "$PY" tests/lint.py "$@"
