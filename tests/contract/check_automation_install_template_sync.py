#!/usr/bin/env python3
"""Contract: automation install checklist template must track active registry ids."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "automations" / "registry.json"
TEMPLATE = ROOT / "docs" / "agents" / "templates" / "AUTOMATION_INSTALL_CHECKLIST.md"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _active_ids(reg: Dict[str, object]) -> List[str]:
    autos = reg.get("automations")
    if not isinstance(autos, list):
        return []
    out: List[str] = []
    for a in autos:
        if not isinstance(a, dict):
            continue
        if a.get("status") != "active":
            continue
        aid = a.get("id")
        if isinstance(aid, str) and aid.strip():
            out.append(aid)
    return sorted(set(out))


def main() -> int:
    _require(REGISTRY.exists(), "missing automations/registry.json")
    _require(TEMPLATE.exists(), "missing docs/agents/templates/AUTOMATION_INSTALL_CHECKLIST.md")

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    active = _active_ids(reg)
    _require(active, "no active automations found in registry")

    text = TEMPLATE.read_text(encoding="utf-8")
    _require("## Install order (required)" in text, "template missing 'Install order' section")
    _require("## Post-install verification (required)" in text, "template missing post-install verification section")

    missing = [aid for aid in active if f"`{aid}`" not in text]
    _require(not missing, f"template missing active automation ids: {missing}")

    print(f"[automation-install-template][PASS] active_ids={len(active)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[automation-install-template][FAIL] {ex}")
        raise SystemExit(1)
