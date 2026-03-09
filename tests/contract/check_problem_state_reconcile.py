#!/usr/bin/env python3
import json, sys, shutil
from pathlib import Path
from jsonschema import Draft202012Validator
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "docs" / "schemas" / "ProblemState.schema.json").read_text(encoding="utf-8"))

EXAMPLE_RR = ROOT / "docs" / "examples" / "reports" / "sample_run_001" / "RunReport.json"

def canonical_dump(obj) -> str:
  return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

def rmtree_missing_ok(path: Path) -> None:
  def _onerror(_func, _entry, exc_info):
    if exc_info and issubclass(exc_info[0], FileNotFoundError):
      return
    raise exc_info[1]
  try:
    shutil.rmtree(path, onerror=_onerror)
  except FileNotFoundError:
    return

def main() -> int:
  slug = "__test_problem_state__"
  pdir = ROOT / "Problems" / slug
  # Clean if left over from a crashed run
  if pdir.exists():
    rmtree_missing_ok(pdir)
  try:
    (pdir / "Reports").mkdir(parents=True, exist_ok=True)
    # Write a copy of the example RunReport into this problem reports dir
    rr_path = pdir / "Reports" / "RunReport_test.json"
    rr = json.loads(EXAMPLE_RR.read_text(encoding="utf-8"))
    rr_path.write_text(canonical_dump(rr), encoding="utf-8")

    # Run reconcile
    cmd = [sys.executable, str(ROOT / "tools" / "problem_state" / "reconcile.py"),
           "--problem", slug,
           "--run-report", str(rr_path.relative_to(ROOT))]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if proc.returncode != 0:
      print(proc.stdout, file=sys.stderr)
      print(proc.stderr, file=sys.stderr)
      return 2

    state_path = pdir / "State.json"
    if not state_path.exists():
      print("State.json not created", file=sys.stderr)
      return 2
    state_text = state_path.read_text(encoding="utf-8")
    state = json.loads(state_text)

    # Schema validate
    v = Draft202012Validator(SCHEMA)
    errs = sorted(v.iter_errors(state), key=lambda e: e.path)
    if errs:
      for e in errs:
        print(f"Schema error: {list(e.path)}: {e.message}", file=sys.stderr)
      return 2

    # Canonical JSON check
    if state_text != canonical_dump(state):
      print("State.json is not canonical JSON", file=sys.stderr)
      return 2

    # Sanity: status should match RunReport.status (sample_run_001 is TRIAGED)
    if state.get("status") != "TRIAGED":
      print(f"Expected status TRIAGED, got {state.get('status')}", file=sys.stderr)
      return 2
    return 0
  finally:
    if pdir.exists():
      rmtree_missing_ok(pdir)

if __name__ == "__main__":
  raise SystemExit(main())
