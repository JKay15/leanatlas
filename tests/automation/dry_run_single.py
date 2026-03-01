#!/usr/bin/env python3
"""Dry-run a single automation.

This executes ONLY the automation's deterministic steps.
It does NOT invoke Codex.

Purpose:
- Ensure the deterministic pre-step remains runnable.
- Provide a stable harness that Codex App / codex exec automation can rely on.

This script is used as the tdd.dry_run.cmd entry for active automations.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "automations" / "registry.json"


def die(msg: str) -> int:
  print(f"[automation.dryrun] ERROR: {msg}", file=sys.stderr)
  return 2


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--id", required=True)
  args = ap.parse_args()

  if not REG.exists():
    return die("automations/registry.json not found")

  data = json.loads(REG.read_text(encoding="utf-8"))
  autos = data.get("automations") or []
  target = None
  for a in autos:
    if a.get("id") == args.id:
      target = a
      break

  if target is None:
    return die(f"automation id not found: {args.id}")

  det = target.get("deterministic") or {}
  steps = det.get("steps") or []
  if not steps:
    return die(f"automation has no deterministic steps: {args.id}")

  rc = 0
  for s in steps:
    cmd = s.get("cmd")
    if not isinstance(cmd, list) or not cmd:
      return die(f"invalid cmd in step: {args.id}")

    run_cmd = list(cmd)
    if run_cmd and run_cmd[0] in {"python", "python3"}:
      run_cmd[0] = sys.executable
    print(f"[automation.dryrun] {args.id}:{s.get('name')} -> {' '.join(run_cmd)}")
    p = subprocess.run(run_cmd, cwd=str(ROOT))
    if p.returncode != 0:
      rc = p.returncode
      break

  return rc


if __name__ == "__main__":
  raise SystemExit(main())
