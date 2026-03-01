#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SKIP_LAKE_UPDATE=0
SKIP_LEAN_WARMUP=0
SKIP_MCP=0
SKIP_UV_SYNC=0
FORCE_UV_SYNC=0
DOMAIN_MCP_FROM="${LEANATLAS_DOMAIN_MCP_UVX_FROM:-}"
DOMAIN_MCP_CMD="${LEANATLAS_DOMAIN_MCP_COMMAND:-}"
REAL_AGENT_CMD="${LEANATLAS_REAL_AGENT_CMD:-}"
ONBOARDING_DIR=".cache/leanatlas/onboarding"
REAL_AGENT_ENV_FILE="$ONBOARDING_DIR/real_agent_cmd.env"

usage() {
  cat <<'USAGE'
Usage: bash scripts/bootstrap.sh [options]

Options:
  --skip-lake-update         Skip `lake update` warmup
  --skip-lean-warmup         Skip Lean warmup checks (`importGraph` + `lake build` + `lake lint`)
  --skip-mcp                 Skip MCP smoke installation checks
  --skip-uv-sync             Skip `uv sync --locked` (requires existing .venv)
  --force-uv-sync            Force `uv sync --locked` even when .venv already looks healthy
  --domain-mcp-from <spec>   Override domain MCP uvx source (also via LEANATLAS_DOMAIN_MCP_UVX_FROM)
  --domain-mcp-cmd <name>    Override domain MCP command name (default: domain-mcp)
  -h, --help                 Show this help
USAGE
}

log() { printf '[bootstrap] %s\n' "$*"; }
warn() { printf '[bootstrap][WARN] %s\n' "$*"; }
fail() { printf '[bootstrap][FAIL] %s\n' "$*" >&2; exit 2; }

skills_repo_ready() {
  [[ -d ".agents/skills" ]] || return 1
  find ".agents/skills" -name "SKILL.md" -type f | grep -q .
}

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
  # Persist for future doctor/nightly runs.
  printf 'export LEANATLAS_REAL_AGENT_CMD=%q\n' "$REAL_AGENT_CMD" > "$REAL_AGENT_ENV_FILE"
}

configure_real_agent_cmd() {
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
      fail "LEANATLAS_REAL_AGENT_CMD is required. Set it (recommended: codex exec - < \"\\$LEANATLAS_EVAL_PROMPT\") and rerun bootstrap."
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
    --skip-lake-update)
      SKIP_LAKE_UPDATE=1
      shift
      ;;
    --skip-lean-warmup)
      SKIP_LEAN_WARMUP=1
      shift
      ;;
    --skip-mcp)
      SKIP_MCP=1
      shift
      ;;
    --skip-uv-sync)
      SKIP_UV_SYNC=1
      shift
      ;;
    --force-uv-sync)
      FORCE_UV_SYNC=1
      shift
      ;;
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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown option: $1"
      ;;
  esac
done

command -v uv >/dev/null 2>&1 || fail "uv not found. Install uv first (see docs/setup/external/lean-lsp-mcp.md)."
command -v uvx >/dev/null 2>&1 || fail "uvx not found. Install uv first (see docs/setup/external/lean-lsp-mcp.md)."
command -v lake >/dev/null 2>&1 || fail "lake not found. Install Lean toolchain first."

if ! command -v rg >/dev/null 2>&1; then
  warn "rg (ripgrep) not found. It is strongly recommended for MCP local search fallback."
fi

PY_BIN=".venv/bin/python"

venv_ready() {
  [[ -x "$PY_BIN" ]] || return 1
  "$PY_BIN" - <<'PY' >/dev/null 2>&1
import importlib
for mod in ("yaml", "jsonschema", "drain3"):
  importlib.import_module(mod)
PY
}

if [[ "$SKIP_UV_SYNC" -eq 0 ]]; then
  if [[ "$FORCE_UV_SYNC" -eq 0 ]] && venv_ready; then
    log "existing .venv is healthy; skipping uv sync (use --force-uv-sync to refresh)"
  else
    log "syncing Python environment from uv.lock"
    if ! uv sync --locked; then
      if [[ "$FORCE_UV_SYNC" -eq 0 ]] && venv_ready; then
        warn "uv sync --locked failed (likely network/proxy). Continuing with existing healthy .venv."
        warn "To force reproducibility refresh: fix network and rerun with --force-uv-sync."
      else
        fail "uv sync --locked failed and no healthy .venv fallback is available. Check network/proxy and retry."
      fi
    fi
    if [[ ! -x "$PY_BIN" ]]; then
      fail "expected $PY_BIN after uv sync"
    fi
  fi
else
  if [[ ! -x "$PY_BIN" ]]; then
    fail "--skip-uv-sync requires an existing .venv/bin/python"
  fi
  log "skip uv sync by user request"
fi

log "verifying pinned Python deps"
"$PY_BIN" tests/contract/check_dependency_pins.py

log "checking Repo-B skills mount (.agents/skills)"
if ! skills_repo_ready; then
  fail "missing .agents/skills SKILL.md files. Initialize Repo-B skills first (recommended: git submodule update --init --recursive)."
fi

log "checking Lean toolchain"
lake --version >/dev/null

if [[ "$SKIP_LAKE_UPDATE" -eq 0 ]]; then
  log "warming Lean dependencies (lake update)"
  lake update
else
  log "skip lake update by user request"
fi

if [[ "$SKIP_LEAN_WARMUP" -eq 0 ]]; then
  log "verifying importGraph dependency"
  [[ -d ".lake/packages/importGraph" ]] || fail "importGraph package is missing under .lake/packages/importGraph (run lake update)."

  log "warming Lean build graph (lake build LeanAtlas)"
  lake build LeanAtlas

  log "running lake lint gate"
  lake lint
else
  log "skip Lean warmup by user request"
fi

if [[ "$SKIP_MCP" -eq 1 ]]; then
  log "skip MCP checks by user request"
  log "bootstrap completed (partial)"
  exit 0
fi

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

log "checking pinned lean-lsp-mcp"
uvx --from "$LSP_UVX_FROM" "$LSP_CMD" --help >/dev/null

if [[ -n "$DOMAIN_MCP_FROM" ]]; then
  log "checking domain MCP via uvx source"
  uvx --from "$DOMAIN_MCP_FROM" "$DOMAIN_MCP_CMD" --smoke >/dev/null
elif command -v "$DOMAIN_MCP_CMD" >/dev/null 2>&1; then
  log "checking installed domain MCP command"
  "$DOMAIN_MCP_CMD" --smoke >/dev/null
else
  warn "domain MCP external source not configured."
  warn "Set LEANATLAS_DOMAIN_MCP_UVX_FROM (or add lean_domain_mcp pin in tools/deps/pins.json) and rerun bootstrap."
  warn "Fallback dev check: python tools/lean_domain_mcp/domain_mcp_server.py --msc2020-mini --smoke"
fi

configure_real_agent_cmd

"$PY_BIN" tools/onboarding/finalize_onboarding.py --step bootstrap
log "bootstrap completed"
