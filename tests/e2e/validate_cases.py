#!/usr/bin/env python3
"""Validate E2E case structure, schemas, and coverage.

This is a *deterministic* gate. It does not execute Lean.
Executable cases are handled by `run_cases.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List

import yaml  # type: ignore
import jsonschema  # type: ignore

REQUIRED_FAMILIES = [
    "IMPORT",
    "NAME",
    "TYPE",
    "TACTIC",
    "ASSUMPTION",
    "DEFINITION",
    "STATEMENT",
    "TOOLING",
    "BUDGET",
]


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_patch_ref(case_dir: Path, ref: str) -> Path:
    """Resolve a patch ref to a path.

    Compatibility:
      - Legacy refs like `001.patch` are resolved as `patches/001.patch`
      - New refs may include subpaths, e.g. `patches/001` or `patches/001/overlay`
    """
    if "/" not in ref:
        return case_dir / "patches" / ref
    return case_dir / ref


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "docs" / "schemas" / "E2ECase.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    golden_root = repo_root / "tests" / "e2e" / "golden"
    if not golden_root.exists():
        print("[e2e-validate] missing tests/e2e/golden")
        return 1

    seen_families = {f: 0 for f in REQUIRED_FAMILIES}
    errors: List[str] = []

    for case_dir in sorted(p for p in golden_root.iterdir() if p.is_dir()):
        case_yaml = case_dir / "case.yaml"
        if not case_yaml.exists():
            continue

        meta = load_yaml(case_yaml)
        for e in validator.iter_errors(meta):
            errors.append(f"{case_dir.name}: schema error: {e.message}")

        # id must match folder
        if meta.get("id") != case_dir.name:
            errors.append(f"{case_dir.name}: id must match folder name")

        # patch_sequence references must exist (file OR directory)
        for ref in meta.get("patch_sequence", []) or []:
            p = resolve_patch_ref(case_dir, ref)
            if not p.exists():
                errors.append(f"{case_dir.name}: patch_sequence ref not found: {ref} -> {p}")

        # coverage tags family
        for tag in meta.get("coverage_tags", []) or []:
            if isinstance(tag, str) and tag.startswith("family:"):
                fam = tag.split(":", 1)[1]
                if fam in seen_families:
                    seen_families[fam] += 1

        # executable fixture presence check (if enabled)
        exec_meta = meta.get("execution", {}) or {}
        if exec_meta.get("enabled", False):
            fixture_dir = case_dir / exec_meta.get("fixture_dir", "fixture")
            if not fixture_dir.exists():
                errors.append(f"{case_dir.name}: execution enabled but fixture dir missing: {fixture_dir}")
            else:
                prob = fixture_dir / "Problems" / meta["id"]
                for fn in ["Spec.lean", "Proof.lean", "Cache.lean", "Scratch.lean"]:
                    if not (prob / fn).exists():
                        errors.append(f"{case_dir.name}: missing fixture file: {prob / fn}")

    # Coverage requirement (smoke+core)
    missing = [f for f, c in seen_families.items() if c == 0]
    if missing:
        errors.append(f"coverage missing families: {missing}")

    if errors:
        print("[e2e-validate] FAIL")
        for e in errors:
            print(" -", e)
        return 1

    print("[e2e-validate] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
