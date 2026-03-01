#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES = 32 * 1024

def main():
  bad = 0
  for p in ROOT.rglob("AGENTS*.md"):
    if "/.lake/" in str(p):
      continue
    size = p.stat().st_size
    if size >= MAX_BYTES:
      bad += 1
      print(f"[agents-size][FAIL] {p}: {size} bytes >= {MAX_BYTES}")
    else:
      print(f"[agents-size][OK]   {p}: {size} bytes")
  return 1 if bad else 0

if __name__ == "__main__":
  raise SystemExit(main())
