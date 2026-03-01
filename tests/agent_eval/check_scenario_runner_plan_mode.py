#!/usr/bin/env python3
"""Smoke test: scenario runner plan mode.

This ensures the CLI works end-to-end without requiring Lean or an agent.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    out_root = ROOT / "artifacts" / "_test_tmp_agent_scenarios"
    if out_root.exists():
        shutil.rmtree(out_root)

    scenario = ROOT / "tests" / "agent_eval" / "scenarios" / "mentor_keywords_interleaving_v0" / "scenario.yaml"
    cmd = [
        sys.executable,
        "tools/agent_eval/run_scenario.py",
        "--scenario",
        str(scenario),
        "--mode",
        "plan",
        "--out-root",
        str(out_root),
        "--eval-id",
        "_smoke",
    ]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print("[agent-eval][scenario][FAIL] run_scenario plan mode failed")
        print(r.stdout)
        print(r.stderr)
        return 1

    # Find Plan.json (ScenarioPlan.json is kept for backwards-compat)
    plans = list(out_root.rglob("Plan.json"))
    if not plans:
        plans = list(out_root.rglob("ScenarioPlan.json"))
    if not plans:
        print("[agent-eval][scenario][FAIL] no Plan.json produced")
        return 1
    plan = json.loads(plans[0].read_text(encoding="utf-8"))
    if plan.get("scenario_id") != "mentor_keywords_interleaving_v0":
        print("[agent-eval][scenario][FAIL] wrong scenario_id in plan")
        return 1
    print(f"[agent-eval][scenario][OK] plan created: {plans[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
