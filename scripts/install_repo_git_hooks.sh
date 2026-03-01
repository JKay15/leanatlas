#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CHECK_ONLY=0

usage() {
  cat <<'USAGE'
Usage: bash scripts/install_repo_git_hooks.sh [options]

Options:
  --check       Verify hooks only (do not install)
  -h, --help    Show this help
USAGE
}

log() { printf '[git-hooks] %s\n' "$*"; }
fail() { printf '[git-hooks][FAIL] %s\n' "$*" >&2; exit 2; }

while (($# > 0)); do
  case "$1" in
    --check)
      CHECK_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown option: $1"
      ;;
  esac
done

[[ -d .git ]] || fail "must run inside a git working tree"
[[ -x .venv/bin/python ]] || fail "missing .venv/bin/python (run bootstrap first)"
[[ -f .pre-commit-config.yaml ]] || fail "missing .pre-commit-config.yaml"

export PATH="$ROOT_DIR/.venv/bin:$PATH"
command -v pre-commit >/dev/null 2>&1 || fail "pre-commit not found in .venv; rerun uv sync --locked"

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  .venv/bin/python tools/onboarding/verify_git_hooks.py
  exit 0
fi

log "validating pre-commit config"
pre-commit validate-config

log "installing git hooks (pre-commit, commit-msg, pre-push)"
pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push

.venv/bin/python tools/onboarding/verify_git_hooks.py
log "repo-local git hooks are ready"
