#!/usr/bin/env python3
"""Validate AgentEval scenario YAML files.

Scenarios are phase6.2 objects that compose multiple agent-eval runs + maintainer overlays.
This script is deterministic (no LLM calls) and checks:
- schema-valid
- referenced tasks/variants exist
- referenced packs exist
- overlay directories exist
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "docs" / "schemas" / "AgentEvalScenario.schema.json").read_text(encoding="utf-8"))
SCENARIOS = ROOT / "tests" / "agent_eval" / "scenarios"
TASKS = ROOT / "tests" / "agent_eval" / "tasks"
PACKS = ROOT / "tests" / "agent_eval" / "packs"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _task_variants(task_id: str) -> set[str]:
    task_yaml = TASKS / task_id / "task.yaml"
    if not task_yaml.exists():
        return set()
    data = _load_yaml(task_yaml)
    vs = set()
    for v in data.get("variants", []) if isinstance(data, dict) else []:
        if isinstance(v, dict) and isinstance(v.get("variant_id"), str):
            vs.add(v["variant_id"])
    return vs


def _pack_tasks(pack_id: str) -> list[dict]:
    pack_yaml = PACKS / pack_id / "pack.yaml"
    if not pack_yaml.exists():
        return []
    data = _load_yaml(pack_yaml)
    tasks = data.get("tasks") if isinstance(data, dict) else None
    return tasks if isinstance(tasks, list) else []


def validate_one(path: Path) -> list[str]:
    data = _load_yaml(path)
    v = jsonschema.Draft202012Validator(SCHEMA)
    errs = sorted(v.iter_errors(data), key=lambda e: list(e.absolute_path))
    msgs: list[str] = []
    for e in errs:
        loc = "/" + "/".join(str(p) for p in e.absolute_path)
        msgs.append(f"{path}:{loc}: {e.message}")

    if not isinstance(data, dict):
        return msgs

    scenario_id = data.get("scenario_id")
    if isinstance(scenario_id, str):
        if path.parent.name != scenario_id:
            msgs.append(
                f"{path}:/scenario_id: directory name '{path.parent.name}' must match scenario_id '{scenario_id}'"
            )

    steps = data.get("steps")
    if not isinstance(steps, list):
        return msgs

    scenario_dir = path.parent

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            msgs.append(f"{path}:/steps/{i}: step must be an object")
            continue
        kind = step.get("kind")

        if kind == "run_task":
            tid = step.get("task_id")
            vid = step.get("variant_id")
            if not isinstance(tid, str) or not (TASKS / tid / "task.yaml").exists():
                msgs.append(f"{path}:/steps/{i}: unknown task_id '{tid}'")
            else:
                variants = _task_variants(tid)
                if not isinstance(vid, str) or vid not in variants:
                    msgs.append(f"{path}:/steps/{i}: unknown variant_id '{vid}' for task '{tid}'")

            eo = step.get("expected_override")
            if isinstance(eo, dict) and eo.get("final_status") == "TRIAGED":
                if "triage_family" not in eo or "triage_code" not in eo:
                    msgs.append(
                        f"{path}:/steps/{i}/expected_override: TRIAGED requires triage_family and triage_code"
                    )

        elif kind == "apply_overlay":
            overlay = step.get("overlay")
            if not isinstance(overlay, str) or not overlay:
                msgs.append(f"{path}:/steps/{i}: overlay must be a non-empty string")
            else:
                p = (scenario_dir / overlay).resolve()
                if not str(p).startswith(str(scenario_dir.resolve())):
                    msgs.append(f"{path}:/steps/{i}: overlay resolves outside scenario dir")
                elif not p.exists() or not p.is_dir():
                    msgs.append(f"{path}:/steps/{i}: overlay directory not found: {scenario_dir / overlay}")

        elif kind == "run_pack":
            pack_id = step.get("pack_id")
            if not isinstance(pack_id, str) or not (PACKS / pack_id / "pack.yaml").exists():
                msgs.append(f"{path}:/steps/{i}: unknown pack_id '{pack_id}'")
            else:
                # validate variant selectors
                tv = step.get("task_variants")
                if isinstance(tv, dict):
                    for tid, vids in tv.items():
                        if not isinstance(tid, str):
                            continue
                        variants = _task_variants(tid)
                        if not variants:
                            msgs.append(f"{path}:/steps/{i}: task_variants references unknown task '{tid}'")
                            continue
                        if not isinstance(vids, list):
                            msgs.append(f"{path}:/steps/{i}: task_variants['{tid}'] must be a list")
                            continue
                        for vid in vids:
                            if not isinstance(vid, str) or vid not in variants:
                                msgs.append(
                                    f"{path}:/steps/{i}: task_variants references unknown variant '{vid}' for task '{tid}'"
                                )

                # validate that pack tasks exist
                for ref in _pack_tasks(pack_id):
                    if not isinstance(ref, dict):
                        continue
                    tid = ref.get("task_id")
                    if isinstance(tid, str) and not (TASKS / tid / "task.yaml").exists():
                        msgs.append(f"{path}:/steps/{i}: pack '{pack_id}' references missing task '{tid}'")

        # other kinds are syntactic only at this stage

    return msgs


def main() -> int:
    if not SCENARIOS.exists():
        print("[agent-eval] scenarios directory missing", file=sys.stderr)
        return 2

    yamls = sorted(SCENARIOS.glob("**/scenario.yaml"))
    if not yamls:
        print("[agent-eval] no scenario.yaml files found", file=sys.stderr)
        return 2

    bad = 0
    for y in yamls:
        errs = validate_one(y)
        if errs:
            bad += 1
            print("[agent-eval][FAIL]", *errs, sep="\n  ")
        else:
            print(f"[agent-eval][OK] {y.relative_to(ROOT)}")

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
