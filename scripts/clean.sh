#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rm -rf "$ROOT/artifacts" "$ROOT/.cache/leanatlas" || true
find "$ROOT/Problems" -type d -name Reports -print0 2>/dev/null | while IFS= read -r -d '' d; do
  rm -rf "$d"/*
  if [ -f "$d/.gitignore" ]; then
    git checkout -- "$d/.gitignore" 2>/dev/null || true
  fi
done
find "$ROOT" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
echo "[clean] done."
