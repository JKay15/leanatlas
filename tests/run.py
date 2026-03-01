#!/usr/bin/env python3
import argparse, json, subprocess, sys, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "manifest.json"

def load_manifest():
  data = json.loads(MANIFEST.read_text(encoding="utf-8"))
  if str(data.get("version")) not in {"1", "2"}:
    raise RuntimeError(f"Unsupported manifest version: {data.get('version')}")
  return data["tests"]

def run_script(rel_script: str) -> int:
  script_path = ROOT / rel_script
  venv_python = ROOT / ".venv" / "bin" / "python"
  if venv_python.exists():
    cmd = [str(venv_python), str(script_path)]
  else:
    uv = shutil.which("uv")
    if uv:
      cmd = [uv, "run", "--locked", "python", str(script_path)]
    else:
      print("[tests] warning: neither repo .venv nor uv found; falling back to current python", file=sys.stderr)
      cmd = [sys.executable, str(script_path)]
  print(f"[tests] running: {' '.join(cmd)}")
  p = subprocess.run(cmd, cwd=str(ROOT))
  return p.returncode

def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--profile", default="core", choices=["core", "nightly", "soak"])
  # Backward compatibility for legacy callers.
  ap.add_argument("--tier", dest="legacy_tier", choices=["core", "nightly", "soak"], help=argparse.SUPPRESS)
  args = ap.parse_args()
  selected_profile = args.legacy_tier or args.profile

  tests = load_manifest()

  tier_rank = {"core": 0, "nightly": 1, "soak": 2}
  max_rank = tier_rank[selected_profile]
  selected = [
    t
    for t in tests
    if tier_rank.get(str(t.get("profile") or t.get("tier") or ""), 99) <= max_rank
  ]

  rc = 0
  for t in selected:
    if t.get("kind") != "python_script":
      print(f"[tests] unsupported kind: {t}", file=sys.stderr)
      rc = 2
      continue
    r = run_script(t["script"])
    if r != 0:
      rc = r
  return rc

if __name__ == "__main__":
  raise SystemExit(main())
