#!/usr/bin/env python3
"""Setup docs completeness checks (core).

Goal:
- Ensure every external dependency we reference has:
  - a local install doc (docs/setup/external/*.md)
  - a verification command section
- Ensure operator workflow points to setup docs (so Codex can actually find them).

This test is *doc-level* and does not require any external tools to be installed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETUP = ROOT / "docs" / "setup"
EXT = SETUP / "external"

REQUIRED_FILES = [
  SETUP / "DEPENDENCIES.md",
  SETUP / "README.md",
  SETUP / "QUICKSTART.md",
  SETUP / "SUBMODULES.md",
  SETUP / "TEST_ENV_INVENTORY.md",
  EXT / "lean-lsp-mcp.md",
  EXT / "domain-mcp.md",
  EXT / "pre-commit.md",
  EXT / "ripgrep.md",
]

def die(msg: str) -> int:
  print(f"[setup.docs] ERROR: {msg}", file=sys.stderr)
  return 2

def has_heading_kw(text: str, kw: str) -> bool:
  for line in text.splitlines():
    if re.match(r"^#{1,6}\s+.*", line) and kw in line:
      return True
  return False

def has_fenced_code(text: str) -> bool:
  return "```" in text

def main() -> int:
  missing = [str(p.relative_to(ROOT)) for p in REQUIRED_FILES if not p.exists()]
  if missing:
    print("[setup.docs] Missing required setup docs:", file=sys.stderr)
    for m in missing:
      print(f"  - {m}", file=sys.stderr)
    return 2

  # For each external doc, require headings mentioning install and verify (not necessarily numbered).
  for p in EXT.glob("*.md"):
    text = p.read_text(encoding="utf-8")
    if not has_heading_kw(text.lower(), "install"):
      return die(f"{p.relative_to(ROOT)} missing a heading containing 'install'")
    if "verify" not in text.lower() and "verification" not in text.lower():
      return die(f"{p.relative_to(ROOT)} missing verification guidance (must contain 'verify' or 'verification')")
    if not has_fenced_code(text):
      return die(f"{p.relative_to(ROOT)} should include fenced code blocks (install/verify commands)")
    if "<your-" in text:
      return die(f"{p.relative_to(ROOT)} contains placeholder command text like '<your-...>'")

  quickstart = (SETUP / "QUICKSTART.md").read_text(encoding="utf-8")
  if "scripts/bootstrap.sh" not in quickstart:
    return die("QUICKSTART.md must include scripts/bootstrap.sh")
  if "scripts/doctor.sh" not in quickstart:
    return die("QUICKSTART.md must include scripts/doctor.sh")
  if ".cache/leanatlas/onboarding/state.json" not in quickstart:
    return die("QUICKSTART.md must mention onboarding state path")
  if "AGENTS_ONBOARDING_VERBOSE.md" not in quickstart:
    return die("QUICKSTART.md must mention archived verbose onboarding doc")
  if "./.venv/bin/python tests/run.py --profile core" not in quickstart:
    return die("QUICKSTART.md must use repo-local .venv command for core tests")
  if "uv run --locked python tests/run.py --profile core" not in quickstart:
    return die("QUICKSTART.md must include uv fallback command for core tests")
  if "LEANATLAS_REAL_AGENT_CMD" not in quickstart:
    return die("QUICKSTART.md must explain LEANATLAS_REAL_AGENT_CMD setup for Phase6 real-agent checks")
  if "LEANATLAS_REAL_AGENT_PROVIDER" not in quickstart:
    return die("QUICKSTART.md must explain LEANATLAS_REAL_AGENT_PROVIDER setup for provider-based Phase6 real-agent checks")
  if "LEANATLAS_REAL_AGENT_PROFILE" not in quickstart:
    return die("QUICKSTART.md must explain LEANATLAS_REAL_AGENT_PROFILE setup for profile-based Phase6 real-agent checks")
  if "scripts/install_repo_git_hooks.sh" not in quickstart:
    return die("QUICKSTART.md must explain repo-local git hook installer usage")
  if "TLS" not in quickstart and "handshake" not in quickstart:
    return die("QUICKSTART.md must document TLS/handshake fallback behavior")

  # Operator workflow must reference setup docs.
  op = (ROOT / "docs" / "agents" / "OPERATOR_WORKFLOW.md").read_text(encoding="utf-8")
  if "docs/setup" not in op:
    return die("OPERATOR_WORKFLOW.md must point to docs/setup so Codex can find install steps")
  if "lean-lsp-mcp" not in op:
    return die("OPERATOR_WORKFLOW.md should mention lean-lsp-mcp (MCP acceleration)")

  print("[setup.docs] OK")
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
