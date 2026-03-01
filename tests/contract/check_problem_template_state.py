#!/usr/bin/env python3
import json, sys
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "docs" / "schemas" / "ProblemState.schema.json"
TEMPLATE_STATE = ROOT / "Problems" / "_template" / "State.json"

def main() -> int:
  if not TEMPLATE_STATE.exists():
    print("Missing Problems/_template/State.json", file=sys.stderr)
    return 2
  schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
  data = json.loads(TEMPLATE_STATE.read_text(encoding="utf-8"))
  v = Draft202012Validator(schema)
  errors = sorted(v.iter_errors(data), key=lambda e: e.path)
  if errors:
    for e in errors:
      print(f"Schema error: {list(e.path)}: {e.message}", file=sys.stderr)
    return 2
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
