#!/usr/bin/env python3
"""Validate E2E scenario structure (deterministic gate).

Scenarios are *sequential* and may require local Lean/Lake to execute.
This validator only checks:
- schema conformance
- references to golden cases
- overlay path existence
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List

import yaml  # type: ignore
import jsonschema  # type: ignore


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "docs" / "schemas" / "E2EScenario.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    scenarios_root = repo_root / "tests" / "e2e" / "scenarios"
    golden_root = repo_root / "tests" / "e2e" / "golden"

    errors: List[str] = []
    if not scenarios_root.exists():
        print("[e2e-scenarios-validate] missing tests/e2e/scenarios")
        return 1

    for sc_dir in sorted(p for p in scenarios_root.iterdir() if p.is_dir()):
        sc_yaml = sc_dir / "scenario.yaml"
        if not sc_yaml.exists():
            continue
        meta = load_yaml(sc_yaml)
        for e in validator.iter_errors(meta):
            errors.append(f"{sc_dir.name}: schema error: {e.message}")

        if meta.get("id") != sc_dir.name:
            errors.append(f"{sc_dir.name}: id must match folder name")

        # validate references
        for i, step in enumerate(meta.get("steps", []) or []):
            kind = step.get("kind")
            if kind == "run_case":
                case_id = step.get("case_id")
                if not case_id:
                    errors.append(f"{sc_dir.name}: step {i}: missing case_id")
                    continue
                case_dir = golden_root / case_id
                if not case_dir.exists():
                    errors.append(f"{sc_dir.name}: step {i}: missing golden case: {case_id}")
                    continue
                # if scenario is executable, referenced case should be executable too
                if meta.get("execution", {}).get("enabled", False):
                    case_yaml = case_dir / "case.yaml"
                    if case_yaml.exists():
                        cm = load_yaml(case_yaml)
                        if not (cm.get("execution", {}) or {}).get("enabled", False):
                            errors.append(f"{sc_dir.name}: step {i}: referenced case not executable: {case_id}")
            elif kind == "apply_overlay":
                overlay_ref = step.get("overlay")
                if overlay_ref:
                    overlay_path = sc_dir / overlay_ref
                    if not overlay_path.exists():
                        errors.append(f"{sc_dir.name}: step {i}: overlay path missing: {overlay_ref}")
            elif kind == "lake_build":
                if not step.get("target"):
                    errors.append(f"{sc_dir.name}: step {i}: lake_build missing target")
            elif kind == "run_cmd":
                cmd = step.get("cmd")
                if not cmd or not isinstance(cmd, list):
                    errors.append(f"{sc_dir.name}: step {i}: run_cmd missing cmd[]")
                # If expect_outputs specifies a JSON schema path, ensure it exists (repo-relative).
                for eo in (step.get("expect_outputs") or []):
                    schema_ref = (eo or {}).get("schema")
                    if schema_ref:
                        sp = repo_root / schema_ref
                        if not sp.exists():
                            errors.append(f"{sc_dir.name}: step {i}: schema path missing: {schema_ref}")

    if errors:
        print("[e2e-scenarios-validate] FAIL")
        for e in errors:
            print(" -", e)
        return 1

    print("[e2e-scenarios-validate] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
