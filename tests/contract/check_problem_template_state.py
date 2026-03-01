#!/usr/bin/env python3
"""Contract: template problem library must not be tracked in Repo A."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
  cmd = ["git", "ls-files", "--", "Problems/_template"]
  p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
  if p.returncode != 0:
    print("[problem-template-state][FAIL] cannot query git ls-files", file=sys.stderr)
    if p.stderr.strip():
      print(p.stderr.strip(), file=sys.stderr)
    return 2

  tracked = [line.strip() for line in p.stdout.splitlines() if line.strip()]
  if tracked:
    print("[problem-template-state][FAIL] Problems/_template must not be tracked in main repo.", file=sys.stderr)
    for path in tracked:
      print(f" - {path}", file=sys.stderr)
    return 2

  print("[problem-template-state] OK")
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
