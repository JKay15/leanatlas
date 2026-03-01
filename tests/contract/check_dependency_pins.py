#!/usr/bin/env python3
"""Dependency pinning contract checks (core).

Goal:
- Prevent dependency drift from silently breaking the repo.
- Ensure we have a machine-readable pin registry (tools/deps/pins.json).
- Ensure setup docs include the critical pin strings (so humans + Codex install the right thing).

This is doc/metadata-level and does NOT require the external tools to be installed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINS = ROOT / "tools" / "deps" / "pins.json"
PYPROJECT = ROOT / "pyproject.toml"
UVLOCK = ROOT / "uv.lock"
SETUP_DEPS = ROOT / "docs" / "setup" / "DEPENDENCIES.md"
LSP_DOC = ROOT / "docs" / "setup" / "external" / "lean-lsp-mcp.md"
DOMAIN_MCP_DOC = ROOT / "docs" / "setup" / "external" / "domain-mcp.md"
LAKEFILE = ROOT / "lakefile.lean"

BANNED_SUBSTRINGS = [
  "@main",
  "@master",
  "latest",
  "Latest",
  "LATEST",
]

REQUIRED_DEP_IDS = [
  "import_graph",
  "lean_toolchain",
  "mathlib",
  "python",
  "python_uv_project",
  "uv",
  "ripgrep",
  "lean_lsp_mcp",
  "lean_domain_mcp",
]


def die(msg: str) -> int:
  print(f"[deps.pins] ERROR: {msg}", file=sys.stderr)
  return 2


def load_json(p: Path) -> dict:
  try:
    return json.loads(p.read_text(encoding="utf-8"))
  except Exception as e:
    raise RuntimeError(f"Failed to parse {p}: {e}")


def _must_contain(text: str, pattern: str, label: str) -> None:
  if not re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
    raise AssertionError(f"{label} must contain pattern: {pattern!r}")


def main() -> int:
  if not PINS.exists():
    return die("Missing tools/deps/pins.json (machine-readable dependency pins)")
  pins = load_json(PINS)

  if pins.get("version") != "1":
    return die(f"pins.json version must be '1' but got {pins.get('version')!r}")

  deps = pins.get("dependencies")
  if not isinstance(deps, dict):
    return die("pins.json must contain object field: dependencies")

  for dep_id in REQUIRED_DEP_IDS:
    if dep_id not in deps:
      return die(f"pins.json missing required dependency id: {dep_id}")

  # Enforce: no drift-y strings anywhere in pinned metadata.
  blob = json.dumps(pins, ensure_ascii=False)
  for bad in BANNED_SUBSTRINGS:
    if bad in blob:
      return die(f"pins.json contains banned drift substring: {bad!r}")

  # lean-lsp-mcp must be commit pinned.
  lsp = deps["lean_lsp_mcp"]
  commit = lsp.get("pin", {}).get("commit", "")
  if not re.fullmatch(r"[0-9a-f]{40}", commit):
    return die(f"lean_lsp_mcp.pin.commit must be a 40-hex SHA, got: {commit!r}")

  tag = lsp.get("pin", {}).get("tag")
  if not isinstance(tag, str) or not tag.startswith("v"):
    return die(f"lean_lsp_mcp.pin.tag must look like 'vX.Y.Z', got: {tag!r}")

  uvx_from = lsp.get("run", {}).get("uvx_from", "")
  if commit not in uvx_from:
    return die("lean_lsp_mcp.run.uvx_from must include the pinned commit SHA")

  domain = deps["lean_domain_mcp"]
  domain_commit = domain.get("pin", {}).get("commit", "")
  if not re.fullmatch(r"[0-9a-f]{40}", domain_commit):
    return die(f"lean_domain_mcp.pin.commit must be a 40-hex SHA, got: {domain_commit!r}")
  domain_uvx_from = domain.get("run", {}).get("uvx_from", "")
  if domain_commit not in domain_uvx_from:
    return die("lean_domain_mcp.run.uvx_from must include the pinned commit SHA")
  domain_cmd = domain.get("run", {}).get("command", "")
  if domain_cmd != "domain-mcp":
    return die(f"lean_domain_mcp.run.command must be 'domain-mcp', got: {domain_cmd!r}")

  # Python tooling must follow uv project standard.
  if not PYPROJECT.exists():
    return die("Missing pyproject.toml (uv project manifest for repo-local Python tooling)")
  if not UVLOCK.exists():
    return die("Missing uv.lock (locked Python toolchain for deterministic tests)")

  pyproject_text = PYPROJECT.read_text(encoding="utf-8")
  uvlock_text = UVLOCK.read_text(encoding="utf-8")

  direct_pins = deps["python_uv_project"].get("direct_pins", {})
  if not isinstance(direct_pins, dict) or not direct_pins:
    return die("pins.json python_uv_project.direct_pins must be a non-empty object")

  # Ensure pyproject declares the pinned direct dependencies.
  try:
    for name, ver in direct_pins.items():
      # Expect something like "name==ver" inside pyproject.toml.
      _must_contain(pyproject_text, rf"{re.escape(name)}\s*==\s*{re.escape(ver)}", "pyproject.toml")
  except AssertionError as e:
    return die(str(e))

  # Ensure uv.lock pins the same versions (uv normalizes names to lowercase in lockfile).
  try:
    for name, ver in direct_pins.items():
      lock_name = name.lower()
      # Match a package block in uv.lock.
      _must_contain(
        uvlock_text,
        rf"\[\[package\]\]\s*\nname\s*=\s*\"{re.escape(lock_name)}\"\s*\nversion\s*=\s*\"{re.escape(ver)}\"",
        "uv.lock",
      )
  except AssertionError as e:
    return die(str(e))

  # Setup docs must mention the pin sources (so humans/Codex find them)
  if not SETUP_DEPS.exists():
    return die("Missing docs/setup/DEPENDENCIES.md")
  setup_text = SETUP_DEPS.read_text(encoding="utf-8")
  if "tools/deps/pins.json" not in setup_text:
    return die("DEPENDENCIES.md must mention tools/deps/pins.json as pin truth source")
  if "pyproject.toml" not in setup_text or "uv.lock" not in setup_text:
    return die("DEPENDENCIES.md must mention pyproject.toml + uv.lock for Python tooling")

  # Critical Lean-side wheels we call directly must be documented + pinned.
  ig = deps.get("import_graph")
  if not isinstance(ig, dict):
    return die("pins.json missing import_graph dependency metadata")
  ig_rev = ((ig.get("pin") or {}).get("rev") or "").strip()
  if not ig_rev:
    return die("import_graph.pin.rev must be a non-empty string")
  if "import-graph" not in setup_text or ig_rev not in setup_text:
    return die("DEPENDENCIES.md must mention import-graph and its pinned rev")

  # lakefile.lean must be consistent with pins.json (no silent drift).
  if not LAKEFILE.exists():
    return die("Missing lakefile.lean")
  lake_text = LAKEFILE.read_text(encoding="utf-8")

  math_rev = (deps.get("mathlib") or {}).get("pin", {}).get("rev", "")
  if math_rev and math_rev not in lake_text:
    return die("lakefile.lean must contain mathlib pinned rev from pins.json")
  if ig_rev and ig_rev not in lake_text:
    return die("lakefile.lean must contain import-graph pinned rev from pins.json")

  if not LSP_DOC.exists():
    return die("Missing docs/setup/external/lean-lsp-mcp.md")
  lsp_text = LSP_DOC.read_text(encoding="utf-8")
  if commit not in lsp_text:
    return die("lean-lsp-mcp install doc must contain the pinned commit SHA")
  if tag not in lsp_text:
    return die("lean-lsp-mcp install doc must contain the pinned tag string")

  if not DOMAIN_MCP_DOC.exists():
    return die("Missing docs/setup/external/domain-mcp.md")
  domain_text = DOMAIN_MCP_DOC.read_text(encoding="utf-8")
  if domain_commit not in domain_text:
    return die("domain-mcp install doc must contain the pinned commit SHA")

  print("[deps.pins] OK")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
