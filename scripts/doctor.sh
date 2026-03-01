#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DOMAIN_MCP_FROM="${LEANATLAS_DOMAIN_MCP_UVX_FROM:-}"
DOMAIN_MCP_CMD="${LEANATLAS_DOMAIN_MCP_COMMAND:-}"
STRICT="${LEANATLAS_STRICT_DEPS:-0}"
REAL_AGENT_CMD="${LEANATLAS_REAL_AGENT_CMD:-}"
ONBOARDING_DIR=".cache/leanatlas/onboarding"
REAL_AGENT_ENV_FILE="$ONBOARDING_DIR/real_agent_cmd.env"

usage() {
  cat <<'USAGE'
Usage: bash scripts/doctor.sh [options]

Options:
  --domain-mcp-from <spec>   Override domain MCP uvx source (also via LEANATLAS_DOMAIN_MCP_UVX_FROM)
  --domain-mcp-cmd <name>    Override domain MCP command name (default: domain-mcp)
  --strict                   Enable strict deps smoke mode
  -h, --help                 Show this help
USAGE
}

log() { printf '[doctor] %s\n' "$*"; }
warn() { printf '[doctor][WARN] %s\n' "$*"; }
fail() { printf '[doctor][FAIL] %s\n' "$*" >&2; exit 2; }

load_real_agent_cmd() {
  if [[ -n "$REAL_AGENT_CMD" ]]; then
    return 0
  fi
  if [[ -f "$REAL_AGENT_ENV_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$REAL_AGENT_ENV_FILE"
    REAL_AGENT_CMD="${LEANATLAS_REAL_AGENT_CMD:-}"
  fi
}

persist_real_agent_cmd() {
  mkdir -p "$ONBOARDING_DIR"
  printf 'export LEANATLAS_REAL_AGENT_CMD=%q\n' "$REAL_AGENT_CMD" > "$REAL_AGENT_ENV_FILE"
}

require_real_agent_cmd() {
  load_real_agent_cmd
  if [[ -z "$REAL_AGENT_CMD" ]]; then
    if [[ -t 0 ]]; then
      log "real agent command is required for Phase6 nightly real-agent tests."
      printf "Use Codex CLI as LEANATLAS_REAL_AGENT_CMD? [Y/n]: "
      read -r use_codex
      if [[ -z "$use_codex" || "$use_codex" =~ ^[Yy]$ ]]; then
        REAL_AGENT_CMD='codex exec - < "$LEANATLAS_EVAL_PROMPT"'
      else
        printf "Enter LEANATLAS_REAL_AGENT_CMD (must not reference dummy_agent.py): "
        read -r REAL_AGENT_CMD
      fi
    else
      fail "LEANATLAS_REAL_AGENT_CMD is required. Set it (recommended: codex exec - < \"\\$LEANATLAS_EVAL_PROMPT\") and rerun doctor."
    fi
  fi

  if [[ -z "$REAL_AGENT_CMD" ]]; then
    fail "LEANATLAS_REAL_AGENT_CMD cannot be empty."
  fi
  if [[ "$REAL_AGENT_CMD" == *"dummy_agent.py"* ]]; then
    fail "LEANATLAS_REAL_AGENT_CMD cannot point to dummy_agent.py."
  fi

  export LEANATLAS_REAL_AGENT_CMD="$REAL_AGENT_CMD"
  persist_real_agent_cmd
  "$PY_BIN" tools/onboarding/finalize_onboarding.py --step real_agent_cmd
  log "real agent command configured and persisted: $REAL_AGENT_ENV_FILE"
}

while (($# > 0)); do
  case "$1" in
    --domain-mcp-from)
      [[ $# -ge 2 ]] || fail "--domain-mcp-from requires a value"
      DOMAIN_MCP_FROM="$2"
      shift 2
      ;;
    --domain-mcp-cmd)
      [[ $# -ge 2 ]] || fail "--domain-mcp-cmd requires a value"
      DOMAIN_MCP_CMD="$2"
      shift 2
      ;;
    --strict)
      STRICT=1
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

for cmd in uv uvx lake; do
  command -v "$cmd" >/dev/null 2>&1 || fail "missing required command: $cmd"
done

PY_BIN=".venv/bin/python"
if [[ -x "$PY_BIN" ]]; then
  log "using repo-local python: $PY_BIN"
else
  command -v python >/dev/null 2>&1 || fail "missing required command: python"
  PY_BIN="python"
  warn "repo-local .venv/bin/python not found; using system python"
fi

if ! command -v rg >/dev/null 2>&1; then
  warn "rg not found. Recommended for fallback search performance."
fi

log "running setup docs contract"
"$PY_BIN" tests/contract/check_setup_docs.py

log "running dependency pin contract"
"$PY_BIN" tests/contract/check_dependency_pins.py

log "running deps smoke"
if [[ "$STRICT" == "1" ]]; then
  LEANATLAS_STRICT_DEPS=1 "$PY_BIN" tests/setup/deps_smoke.py
else
  "$PY_BIN" tests/setup/deps_smoke.py
fi

log "verifying repo-local git hooks"
if ! "$PY_BIN" tools/onboarding/verify_git_hooks.py >/dev/null 2>&1; then
  warn "git hooks missing or stale; reinstalling repo-local hooks"
  bash scripts/install_repo_git_hooks.sh
fi
"$PY_BIN" tools/onboarding/verify_git_hooks.py

read -r LSP_UVX_FROM LSP_CMD < <("$PY_BIN" - <<'PY'
import json
from pathlib import Path
pins = json.loads(Path("tools/deps/pins.json").read_text(encoding="utf-8"))
d = pins["dependencies"]["lean_lsp_mcp"]
print(d["run"]["uvx_from"], d["run"]["command"])
PY
)

read -r PIN_DOMAIN_FROM PIN_DOMAIN_CMD < <("$PY_BIN" - <<'PY'
import json
from pathlib import Path
pins = json.loads(Path("tools/deps/pins.json").read_text(encoding="utf-8"))
d = pins["dependencies"].get("lean_domain_mcp", {})
run = d.get("run", {})
print(run.get("uvx_from", ""), run.get("command", "domain-mcp"))
PY
)

if [[ -z "$DOMAIN_MCP_FROM" ]]; then
  DOMAIN_MCP_FROM="$PIN_DOMAIN_FROM"
fi
if [[ -z "$DOMAIN_MCP_CMD" ]]; then
  DOMAIN_MCP_CMD="$PIN_DOMAIN_CMD"
fi
if [[ -z "$DOMAIN_MCP_CMD" ]]; then
  DOMAIN_MCP_CMD="domain-mcp"
fi

log "checking pinned lean-lsp-mcp command"
uvx --from "$LSP_UVX_FROM" "$LSP_CMD" --help >/dev/null

if [[ -n "$DOMAIN_MCP_FROM" ]]; then
  log "checking domain MCP via uvx source"
  uvx --from "$DOMAIN_MCP_FROM" "$DOMAIN_MCP_CMD" --smoke >/dev/null
elif command -v "$DOMAIN_MCP_CMD" >/dev/null 2>&1; then
  log "checking installed domain MCP command"
  "$DOMAIN_MCP_CMD" --smoke >/dev/null
else
  warn "domain MCP not externally installed; using repo dev fallback smoke"
  "$PY_BIN" tools/lean_domain_mcp/domain_mcp_server.py --msc2020-mini --smoke >/dev/null
fi

require_real_agent_cmd

"$PY_BIN" tools/onboarding/finalize_onboarding.py --step doctor
log "doctor passed"
