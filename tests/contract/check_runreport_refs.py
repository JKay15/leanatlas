#!/usr/bin/env python3
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs" / "examples" / "reports"

def uniq(ids, label, path):
  if len(ids) != len(set(ids)):
    dup = [x for x in set(ids) if ids.count(x) > 1]
    raise ValueError(f"{path}: duplicate {label} ids: {dup}")

def main():
  bad = 0
  for rr_path in sorted(EXAMPLES.glob("*/RunReport.json")):
    try:
      rr = json.loads(rr_path.read_text(encoding="utf-8"))
      run_dir = rr_path.parent
      # collect ids
      target_ids = [t["id"] for t in rr.get("targets", [])]
      diag_ids = [d["id"] for d in rr.get("diagnostics", [])]
      hotspot_ids = [h["id"] for h in rr.get("hotspots", [])] if "hotspots" in rr else []
      uniq(target_ids, "target", rr_path)
      uniq(diag_ids, "diagnostic", rr_path)
      uniq(hotspot_ids, "hotspot", rr_path)

      # TRIAGED must reference at least one diagnostic
      if rr.get("status") == "TRIAGED":
        tri = rr.get("triage", {})
        ev = tri.get("evidence", {})
        ref_diags = ev.get("diagnostic_ids", [])
        if not ref_diags:
          raise ValueError(f"{rr_path}: TRIAGED requires triage.evidence.diagnostic_ids")
        for did in ref_diags:
          if did not in diag_ids:
            raise ValueError(f"{rr_path}: triage references missing diagnostic id {did}")
        # hotspots
        hs = rr.get("hotspots", [])
        if not hs:
          raise ValueError(f"{rr_path}: TRIAGED requires hotspots")
        for h in hs:
          for did in h.get("diagnostic_ids", []):
            if did not in diag_ids:
              raise ValueError(f"{rr_path}: hotspot references missing diagnostic id {did}")
          tid = h.get("target_id")
          if tid and tid not in target_ids:
            raise ValueError(f"{rr_path}: hotspot references missing target id {tid}")
      print(f"[runreport-refs][OK]   {rr_path}")
    except Exception as e:
      bad += 1
      print(f"[runreport-refs][FAIL] {rr_path}: {e}", file=sys.stderr)
  return 1 if bad else 0

if __name__ == "__main__":
  raise SystemExit(main())
