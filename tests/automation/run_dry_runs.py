#!/usr/bin/env python3
"""Run dry-runs for all ACTIVE automations with tdd.profile == core.

This is the *core tier* safety net: automations cannot silently rot.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "automations" / "registry.json"


def main() -> int:
  data = json.loads(REG.read_text(encoding="utf-8"))
  autos = data.get("automations") or []

  active_core = []
  for a in autos:
    if a.get("status") != "active":
      continue
    tdd = a.get("tdd") or {}
    profile = tdd.get("profile")
    if profile != "core":
      continue
    dry = (tdd.get("dry_run") or {}).get("cmd")
    if isinstance(dry, list) and dry:
      active_core.append((a.get("id"), dry))

  if not active_core:
    print("[automation.dryrun] No active core automations")
    return 0

  rc = 0
  for aid, cmd in active_core:
    run_cmd = list(cmd)
    if run_cmd and run_cmd[0] in {"python", "python3"}:
      run_cmd[0] = sys.executable
    print(f"[automation.dryrun] RUN {aid} => {' '.join(run_cmd)}")
    p = subprocess.run(run_cmd, cwd=str(ROOT))
    if p.returncode != 0:
      rc = p.returncode
      break

  return rc


if __name__ == "__main__":
  raise SystemExit(main())
