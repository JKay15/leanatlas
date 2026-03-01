#!/usr/bin/env python3
"""Ensure AgentEval scenarios cover INTERLEAVING/REGRESSION/PRESSURE.

This prevents the scenario catalog from silently drifting to only one class.
"""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "tests" / "agent_eval" / "scenarios"


def main() -> int:
    want = {"INTERLEAVING", "REGRESSION", "PRESSURE"}
    got = set()
    for p in SCENARIOS.rglob("scenario.yaml"):
        y = yaml.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(y, dict) and y.get("schema") == "leanatlas.agent_eval_scenario":
            c = y.get("scenario_class")
            if isinstance(c, str):
                got.add(c)

    missing = sorted(want - got)
    if missing:
        print(f"[agent-eval][scenario][FAIL] missing scenario_class coverage: {missing}")
        return 1
    print(f"[agent-eval][scenario][OK] scenario_class coverage: {sorted(got)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
