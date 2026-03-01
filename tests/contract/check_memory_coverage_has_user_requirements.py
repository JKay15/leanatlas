#!/usr/bin/env python3
"""Sanity-check docs/agents/MEMORY_COVERAGE.md contains the user's hard requirements section.

Rationale:
- The project has a long running discussion history.
- We don't want key user constraints to 'rot' or disappear from the doc-pack.
- This is deliberately lightweight and deterministic.

This is NOT the external 'project memory' document; it's a guardrail inside the repo.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "agents" / "MEMORY_COVERAGE.md"

REQUIRED_SNIPPETS = [
  "User’s hard requirements for",
  "TDD",
  "uv",
  "Don’t reinvent the wheel",
]

def main() -> int:
  if not DOC.exists():
    print("[memory_coverage] FAIL: docs/agents/MEMORY_COVERAGE.md missing", file=sys.stderr)
    return 2

  s = DOC.read_text(encoding="utf-8")
  missing = [x for x in REQUIRED_SNIPPETS if x not in s]
  if missing:
    print("[memory_coverage] FAIL: missing required snippets:", file=sys.stderr)
    for m in missing:
      print(f"  - {m}", file=sys.stderr)
    return 2

  print("[memory_coverage] OK")
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
