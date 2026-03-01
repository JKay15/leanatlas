#!/usr/bin/env python3
import json, sys
from pathlib import Path

try:
  import jsonschema
except Exception:
  print("[attemptlog] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
  raise

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs" / "examples" / "reports"
SCHEMA_PATH = ROOT / "docs" / "schemas" / "AttemptLogLine.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)

def validate_line(obj, ctx):
  errors = sorted(VALIDATOR.iter_errors(obj), key=lambda e: e.path)
  if errors:
    for e in errors:
      path = "/" + "/".join(str(p) for p in e.absolute_path)
      print(f"[attemptlog][FAIL] {ctx}:{path}: {e.message}")
    return False
  return True

def main():
  if not EXAMPLES.exists():
    print(f"[attemptlog][FAIL] missing {EXAMPLES}", file=sys.stderr)
    return 2

  bad = 0
  for run_dir in sorted([p for p in EXAMPLES.iterdir() if p.is_dir()]):
    p = run_dir / "AttemptLog.jsonl"
    if not p.exists():
      bad += 1
      print(f"[attemptlog][FAIL] {run_dir}: missing AttemptLog.jsonl")
      continue
    lines = p.read_text(encoding="utf-8").splitlines()
    if not lines:
      bad += 1
      print(f"[attemptlog][FAIL] {p}: empty")
      continue
    for i, line in enumerate(lines):
      if not line.strip():
        continue
      try:
        obj = json.loads(line)
      except Exception as e:
        bad += 1
        print(f"[attemptlog][FAIL] {p}: line {i+1} invalid JSON: {e}")
        continue
      ok = validate_line(obj, f"{p.name}:line{i+1}")
      if not ok:
        bad += 1
  return 1 if bad else 0

if __name__ == "__main__":
  raise SystemExit(main())
