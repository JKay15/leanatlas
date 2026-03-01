#!/usr/bin/env python3
"""Validate AgentEval task YAML files.

Phase6 runner will execute tasks, but CI must at least guarantee:
- task.yaml exists
- schema-valid
- no obvious structural footguns (duplicate variant_id)
- any declared fixture overlays exist and are safe

This script is deterministic and does not call any LLM.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "docs" / "schemas" / "AgentEvalTask.schema.json").read_text(encoding="utf-8"))
TASKS = Path(__file__).resolve().parent / "tasks"


def validate_one(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(SCHEMA)
    errs = sorted(v.iter_errors(data), key=lambda e: list(e.absolute_path))
    msgs: list[str] = []
    for e in errs:
        loc = "/" + "/".join(str(p) for p in e.absolute_path)
        msgs.append(f"{path}:{loc}: {e.message}")

    # extra invariants
    if not isinstance(data, dict):
        return msgs

    task_id = str(data.get("task_id", ""))

    if isinstance(data.get("variants"), list):
        seen: set[str] = set()
        for i, var in enumerate(data["variants"]):
            if not isinstance(var, dict):
                continue
            vid = var.get("variant_id")
            if isinstance(vid, str) and vid:
                if vid in seen:
                    msgs.append(f"{path}:/variants/{i}/variant_id: duplicate variant_id '{vid}'")
                seen.add(vid)

            # fixture overlay safety checks (optional)
            o = var.get("fixture_overlay_dir")
            if o is None:
                continue
            if not isinstance(o, str) or not o.strip():
                msgs.append(f"{path}:/variants/{i}/fixture_overlay_dir: must be a non-empty string if present")
                continue

            p = Path(o)
            if p.is_absolute():
                msgs.append(f"{path}:/variants/{i}/fixture_overlay_dir: must be repo-relative (no leading '/')")
                continue
            if ".." in p.parts:
                msgs.append(f"{path}:/variants/{i}/fixture_overlay_dir: must not contain '..'")
                continue

            overlay = (ROOT / p).resolve()
            root_resolved = ROOT.resolve()
            if not str(overlay).startswith(str(root_resolved)):
                msgs.append(f"{path}:/variants/{i}/fixture_overlay_dir: resolves outside repo root")
                continue
            if not overlay.exists() or not overlay.is_dir():
                msgs.append(f"{path}:/variants/{i}/fixture_overlay_dir: directory not found: {ROOT / p}")
                continue

            # Recommended convention: keep overlays under the task directory.
            expected_root = (path.parent / "variants" / str(vid) / "fixture_overlay").resolve() if vid else None
            if expected_root is not None and overlay != expected_root:
                msgs.append(
                    f"{path}:/variants/{i}/fixture_overlay_dir: should be '{expected_root.relative_to(ROOT)}' (got '{(ROOT / p).as_posix()}')"
                )

            # Safety: overlays should only contain .lean files (problem-level deltas).
            for f in overlay.rglob("*"):
                if f.is_dir():
                    continue
                if f.suffix != ".lean":
                    rel = f.relative_to(ROOT) if f.is_absolute() and str(f).startswith(str(ROOT)) else f
                    msgs.append(
                        f"{path}:/variants/{i}/fixture_overlay_dir: overlay contains non-.lean file: {rel}"
                    )

    return msgs


def main() -> int:
    if not TASKS.exists():
        print("[agent-eval] tasks directory missing", file=sys.stderr)
        return 2

    yamls = sorted(TASKS.glob("**/task.yaml"))
    if not yamls:
        print("[agent-eval] no task.yaml files found", file=sys.stderr)
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
