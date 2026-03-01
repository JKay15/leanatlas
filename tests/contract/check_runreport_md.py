#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs" / "examples" / "reports"

REQUIRED_HEADINGS = ["## Targets", "## Stages", "## Hotspots", "## Next actions"]

def main():
  bad = 0
  for md in sorted(EXAMPLES.glob("*/RunReport.md")):
    txt = md.read_text(encoding="utf-8")
    for h in REQUIRED_HEADINGS:
      if h not in txt:
        bad += 1
        print(f"[runreport-md][FAIL] {md}: missing heading {h}")
    if bad == 0:
      print(f"[runreport-md][OK]   {md}")
  return 1 if bad else 0

if __name__ == "__main__":
  raise SystemExit(main())
