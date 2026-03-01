#!/usr/bin/env python3
"""Contract: telemetry-dependent automations must collect telemetry first.

Fail conditions:
- an automation consumes `artifacts/telemetry` without a prior collect step
- telemetry collect step omits `--clean` (stale data risk)
- collect step writes telemetry outside `artifacts/telemetry`
- collect step exists but deterministic.artifacts does not declare telemetry outputs
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "automations" / "registry.json"
COLLECT_SCRIPT = "tools/bench/collect_telemetry.py"


def _script_path_from_cmd(cmd: List[str]) -> Optional[str]:
    if not cmd:
        return None
    if cmd[0] in {"python", "python3"} and len(cmd) >= 2:
        return cmd[1]
    for i, tok in enumerate(cmd):
        if tok in {"python", "python3"} and i + 1 < len(cmd):
            return cmd[i + 1]
    return None


def _consumes_telemetry(cmd: List[str]) -> bool:
    for i, tok in enumerate(cmd):
        if tok == "--in" and i + 1 < len(cmd):
            return cmd[i + 1] == "artifacts/telemetry"
    return False


def _collect_out_root(cmd: List[str]) -> str:
    for i, tok in enumerate(cmd):
        if tok == "--out-root" and i + 1 < len(cmd):
            return cmd[i + 1]
    return "artifacts/telemetry"


def main() -> int:
    if not REGISTRY.exists():
        print("[telemetry-policy][FAIL] missing automations/registry.json")
        return 1
    if not (ROOT / COLLECT_SCRIPT).exists():
        print(f"[telemetry-policy][FAIL] missing {COLLECT_SCRIPT}")
        return 1

    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    autos = list(data.get("automations") or [])
    errors: List[str] = []

    for auto in autos:
        aid = str(auto.get("id") or "?")
        if auto.get("status") == "deprecated":
            continue

        det = auto.get("deterministic") or {}
        steps = list(det.get("steps") or [])
        artifacts = [str(x) for x in list(det.get("artifacts") or []) if isinstance(x, str)]

        telemetry_step_idx = [i for i, step in enumerate(steps) if _consumes_telemetry(list(step.get("cmd") or []))]
        if not telemetry_step_idx:
            continue

        collect_idx: List[int] = []
        collect_out_roots: List[str] = []
        for i, step in enumerate(steps):
            cmd = list(step.get("cmd") or [])
            script = _script_path_from_cmd(cmd)
            if script != COLLECT_SCRIPT:
                continue
            collect_idx.append(i)
            collect_out_roots.append(_collect_out_root(cmd))
            if "--clean" not in cmd:
                errors.append(f"{aid}: collect_telemetry step must include --clean to avoid stale telemetry contamination")

        if not collect_idx:
            errors.append(f"{aid}: consumes artifacts/telemetry but has no prior {COLLECT_SCRIPT} step")
            continue

        first_collect = min(collect_idx)
        first_consume = min(telemetry_step_idx)
        if first_collect >= first_consume:
            errors.append(f"{aid}: collect_telemetry must run before any step that consumes artifacts/telemetry")

        for out_root in collect_out_roots:
            if out_root != "artifacts/telemetry":
                errors.append(f"{aid}: collect_telemetry out-root must be artifacts/telemetry (got {out_root})")

        if "artifacts/telemetry/**" not in artifacts:
            errors.append(f"{aid}: deterministic.artifacts must declare artifacts/telemetry/**")

    if errors:
        print("[telemetry-policy][FAIL]")
        for e in errors:
            print(" -", e)
        return 1

    print("[telemetry-policy][PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
