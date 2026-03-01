#!/usr/bin/env python3
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs" / "examples" / "reports"
REQ = ["RunReport.json", "RunReport.md", "RetrievalTrace.json", "AttemptLog.jsonl"]

def main():
  if not EXAMPLES.exists():
    print(f"[reports-layout][FAIL] missing {EXAMPLES}", file=sys.stderr)
    return 2
  bad = 0
  for d in sorted([p for p in EXAMPLES.iterdir() if p.is_dir()]):
    run_id = d.name
    for f in REQ:
      if not (d/f).exists():
        bad += 1
        print(f"[reports-layout][FAIL] {d}: missing {f}")
    rr = d/"RunReport.json"
    if rr.exists():
      data = json.loads(rr.read_text(encoding="utf-8"))
      if data.get("run_id") != run_id:
        bad += 1
        print(f"[reports-layout][FAIL] {d}: run_id mismatch {data.get('run_id')} != {run_id}")
      if data.get("retrieval_trace_path") != "RetrievalTrace.json":
        bad += 1
        print(f"[reports-layout][FAIL] {d}: retrieval_trace_path must be RetrievalTrace.json")
    if bad == 0:
      print(f"[reports-layout][OK]   {d}")
  return 1 if bad else 0

if __name__ == "__main__":
  raise SystemExit(main())
