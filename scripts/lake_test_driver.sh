#!/usr/bin/env bash
set -euo pipefail

# Lake passes `testDriverArgs` first, then any CLI args after `lake test --`.
# We forward everything to the Python test runner.

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

exec "$PY" tests/run.py --profile core "$@"
