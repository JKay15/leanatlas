#!/usr/bin/env python3
"""External dependency smoke checks (nightly).

Purpose:
- Verify that the installation instructions in docs/setup are actually satisfiable on a real machine.
- Fail loudly if required external commands are missing.
- In STRICT mode, actually run pinned external tools to catch upstream breakage early.

This is intentionally *nightly* because it depends on the local machine environment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINS = ROOT / "tools" / "deps" / "pins.json"

REQUIRED_CMDS = [
  ("lake", "Lean+Lake is required (truth source)."),
  ("python", "Python is required for deterministic gates."),
  ("rg", "ripgrep is strongly recommended (fallback search; MCP backends). See docs/setup/external/ripgrep.md"),
  ("uv", "uv is recommended to run lean-lsp-mcp. See docs/setup/external/lean-lsp-mcp.md"),
  ("uvx", "uvx is required to run pinned MCP tools. See docs/setup/external/lean-lsp-mcp.md"),
]

def die(msg: str) -> int:
  print(f"[deps] ERROR: {msg}", file=sys.stderr)
  return 2

def load_pins() -> dict:
  if not PINS.exists():
    raise RuntimeError(f"Missing pins: {PINS}")
  return json.loads(PINS.read_text(encoding="utf-8"))

def main() -> int:
  missing = []
  for cmd, hint in REQUIRED_CMDS:
    if shutil.which(cmd) is None:
      missing.append((cmd, hint))

  if missing:
    print("[deps] Missing external commands:", file=sys.stderr)
    for cmd, hint in missing:
      print(f"  - {cmd}: {hint}", file=sys.stderr)
    print("\n[deps] Fix: follow docs/setup/DEPENDENCIES.md and docs/setup/external/*", file=sys.stderr)
    return 2

  pins = load_pins()
  lsp = pins["dependencies"]["lean_lsp_mcp"]
  uvx_from = lsp["run"]["uvx_from"]
  tool = lsp["run"]["command"]
  domain = pins["dependencies"].get("lean_domain_mcp", {})
  domain_run = domain.get("run", {}) if isinstance(domain, dict) else {}
  pinned_domain_cmd = str(domain_run.get("command", "domain-mcp")).strip() or "domain-mcp"
  pinned_domain_from = str(domain_run.get("uvx_from", "")).strip()
  domain_cmd = os.environ.get("LEANATLAS_DOMAIN_MCP_COMMAND", pinned_domain_cmd).strip() or pinned_domain_cmd
  domain_from = os.environ.get("LEANATLAS_DOMAIN_MCP_UVX_FROM", pinned_domain_from).strip()

  # Optional stronger checks (may require network on first run).
  strict = os.environ.get("LEANATLAS_STRICT_DEPS", "0") == "1"
  if strict:
    # uv project lock must be up-to-date (do NOT auto-update in CI/automation).
    print('[deps] STRICT: checking uv.lock matches pyproject.toml ...')
    try:
      subprocess.run(['uv', 'lock', '--check'], check=True, timeout=180, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
      return die('uv lock --check timed out')
    except subprocess.CalledProcessError as e:
      return die(f'uv lock --check failed: {e}')

    # Ensure the project environment can be reproduced from uv.lock.
    print('[deps] STRICT: syncing .venv from uv.lock (may take a while on first run) ...')
    try:
      subprocess.run(['uv', 'sync', '--locked'], check=True, timeout=600, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
      return die('uv sync --locked timed out')
    except subprocess.CalledProcessError as e:
      return die(f'uv sync --locked failed: {e}')
    print("[deps] STRICT mode enabled: running pinned lean-lsp-mcp --help ...")
    cmd = ["uvx", "--from", uvx_from, tool, "--help"]
    try:
      subprocess.run(cmd, check=True, timeout=180, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
      return die("Pinned lean-lsp-mcp --help timed out (increase timeout or prefetch in your environment)")
    except subprocess.CalledProcessError as e:
      return die(f"Pinned lean-lsp-mcp --help failed: {e}")

    # Domain MCP strict check:
    # - if LEANATLAS_DOMAIN_MCP_UVX_FROM provided: enforce uvx --from smoke
    # - else if command exists: run command smoke
    # - else fail with explicit setup hint
    print("[deps] STRICT mode: checking domain MCP smoke ...")
    if domain_from:
      dcmd = ["uvx", "--from", domain_from, domain_cmd, "--smoke"]
    elif shutil.which(domain_cmd):
      dcmd = [domain_cmd, "--smoke"]
    else:
      return die(
        "Domain MCP not found. Set LEANATLAS_DOMAIN_MCP_UVX_FROM or install "
        f"`{domain_cmd}` before STRICT deps smoke."
      )
    try:
      subprocess.run(dcmd, check=True, timeout=180, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
      return die("Domain MCP smoke timed out")
    except subprocess.CalledProcessError as e:
      return die(f"Domain MCP smoke failed: {e}")

  print("[deps] OK")
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
