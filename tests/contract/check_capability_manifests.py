#!/usr/bin/env python3
"""
Core contract test: tools/capabilities/phase{3,4,5}.yaml must exist and validate against docs/schemas/CapabilityManifest.schema.json.

Rationale:
- skills/automation is cross-cutting; Phase5 must not "guess" other phases.
- capability manifests are the machine-readable interface layer.

Phase5 extension (platform guardrail):
- run deterministic `skills_regen` audit to catch repo-local entrypoint drift.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import validate, Draft202012Validator


def load_schema(repo_root: Path) -> dict:
    schema_path = repo_root / "docs" / "schemas" / "CapabilityManifest.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    schema = load_schema(repo_root)
    Draft202012Validator.check_schema(schema)

    for phase in ("phase3", "phase4", "phase5"):
        p = repo_root / "tools" / "capabilities" / f"{phase}.yaml"
        if not p.exists():
            print(f"[FAIL] missing capability manifest: {p}")
            return 1
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        try:
            validate(instance=data, schema=schema)
        except Exception as e:
            print(f"[FAIL] schema validation failed for {p}: {e}")
            return 1

    # Deterministic regen + audit (no LLM)
    regen = repo_root / "tools" / "coordination" / "skills_regen.py"
    if not regen.exists():
        print(f"[FAIL] missing skills_regen tool: {regen}")
        return 1

    cmd = [sys.executable, str(regen), "--repo-root", str(repo_root), "--check"]
    p = subprocess.run(cmd, cwd=str(repo_root))
    if p.returncode != 0:
        print(f"[FAIL] skills_regen audit failed (rc={p.returncode})")
        return 1

    print("[OK] capability manifests exist, are schema-valid, and pass skills_regen audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
