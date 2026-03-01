#!/usr/bin/env python3
"""Guardrail: docs/contracts/HARD_REQUIREMENTS.md must exist and include key sections.

We use this as a deterministic backstop so non-negotiables do not silently drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "contracts" / "HARD_REQUIREMENTS.md"

REQUIRED_SNIPPETS = [
  "Truth and verification",
  "Workflow discipline",
  "Evidence chain",
  "Test-driven development",
  "External dependencies",
  "Library growth",
  "Domain-driven retrieval",
]


def main() -> int:
  if not DOC.exists():
    print("[hard_requirements] FAIL: missing docs/contracts/HARD_REQUIREMENTS.md", file=sys.stderr)
    return 2

  text = DOC.read_text(encoding="utf-8")
  missing = [s for s in REQUIRED_SNIPPETS if s not in text]
  if missing:
    print("[hard_requirements] FAIL: missing required sections:", file=sys.stderr)
    for s in missing:
      print(f"  - {s}", file=sys.stderr)
    return 2

  print("[hard_requirements] OK")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
