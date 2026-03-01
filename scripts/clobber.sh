#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$ROOT/scripts/clean.sh"
rm -rf "$ROOT/.lake" || true
rm -rf "$ROOT/.venv" || true
echo "[clobber] done."
