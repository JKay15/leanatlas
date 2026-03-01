#!/usr/bin/env python3
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Enforce a canonical JSON format (indent=2, sort_keys, UTF-8) on a small set of
# committed JSON artifacts that are treated as truth sources.
SCAN_DIRS = [
  ROOT / "docs" / "examples",
  ROOT / "docs" / "schemas",
  ROOT / "tools" / "deps",
  ROOT / "tools" / "index",
  ROOT / "Problems" / "_template",
  ROOT / "tests" / "schema" / "fixtures",
  ROOT / "tests" / "manifest.json",
]


def canonical_dump(obj) -> str:
  return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def read_text(p: Path) -> str:
  return p.read_text(encoding="utf-8")


def main() -> int:
  bad = 0
  # Expand scan dirs (manifest.json is a file)
  files: list[Path] = []
  for d in SCAN_DIRS:
    if d.is_file():
      files.append(d)
    elif d.is_dir():
      files.extend([p for p in d.rglob("*.json") if p.is_file()])

  for p in sorted(set(files)):
    try:
      txt = read_text(p)
      obj = json.loads(txt)
      canon = canonical_dump(obj)
      if txt != canon:
        bad += 1
        print(
          f"[canonical-json][FAIL] {p}: not canonical (keys/order/format). Reformat with canonical dump.",
          file=sys.stderr,
        )
      else:
        print(f"[canonical-json][OK]   {p}")
    except Exception as e:
      bad += 1
      print(f"[canonical-json][FAIL] {p}: {e}", file=sys.stderr)

  return 1 if bad else 0


if __name__ == "__main__":
  raise SystemExit(main())
