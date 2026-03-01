#!/usr/bin/env python3
"""
Deterministically reconcile Problems/<slug>/State.json using a RunReport.json.

This tool is intentionally small and boring:
- It MUST be runnable without Lean/LLM.
- It MUST be deterministic: same inputs -> same outputs.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]

def canonical_dump(obj) -> str:
  return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

def load_json(p: Path):
  return json.loads(p.read_text(encoding="utf-8"))

def save_json(p: Path, obj):
  p.write_text(canonical_dump(obj), encoding="utf-8")

def die(msg: str, code: int = 2) -> int:
  print(msg, file=sys.stderr)
  return code

def main(argv: list[str]) -> int:
  import argparse
  ap = argparse.ArgumentParser()
  ap.add_argument("--problem", required=True, help="problem_slug, e.g. am_gm_ineq_2026_01")
  ap.add_argument("--run-report", required=True, help="repo-relative path to RunReport.json (inside the problem Reports dir)")
  args = ap.parse_args(argv)

  problem_slug = args.problem
  rr_path = (ROOT / args.run_report).resolve()
  if not rr_path.exists():
    return die(f"RunReport not found: {rr_path}")

  rr = load_json(rr_path)
  rr_status = rr.get("status")
  if rr_status not in ("SUCCESS", "TRIAGED"):
    return die(f"RunReport.status must be SUCCESS or TRIAGED, got: {rr_status}")

  problem_dir = ROOT / "Problems" / problem_slug
  state_path = problem_dir / "State.json"
  if not state_path.exists():
    # Create a minimal default state deterministically
    state = {
      "version": "0.1",
      "problem_slug": problem_slug,
      "domain": {"domain_id": "UNKNOWN", "msc": [], "confidence": 0.0, "source": "manual"},
      "status": "NEW",
      "ever_succeeded": False,
      "counters": {"attempts": 0, "success": 0, "triaged": 0},
      "last_run": None,
    }
  else:
    state = load_json(state_path)

  # Counters
  counters = state.get("counters") or {}
  counters["attempts"] = int(counters.get("attempts", 0)) + 1
  if rr_status == "SUCCESS":
    counters["success"] = int(counters.get("success", 0)) + 1
    state["ever_succeeded"] = True
    state["status"] = "SUCCESS"
  else:
    counters["triaged"] = int(counters.get("triaged", 0)) + 1
    state["status"] = "TRIAGED"
  state["counters"] = counters

  # last_run pointer (avoid filesystem heuristics)
  state["last_run"] = {
    "run_id": rr.get("run_id", ""),
    "status": rr_status,
    "run_report_path": str(Path(args.run_report).as_posix()),
    "retrieval_trace_path": rr.get("retrieval_trace_path", ""),
  }

  # Keep problem_slug stable
  state["problem_slug"] = problem_slug
  # Keep version if present; else set
  state["version"] = state.get("version", "0.1")

  save_json(state_path, state)
  return 0

if __name__ == "__main__":
  raise SystemExit(main(sys.argv[1:]))
