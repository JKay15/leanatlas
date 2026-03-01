#!/usr/bin/env python3
"""Test registry contract (core).

Goals:
1) tests/manifest.json must conform to docs/schemas/TestManifest.schema.json
2) every registered script must exist
3) every test script (by convention) must be registered
4) ids must be unique

Rationale: if a test isn't registered, it effectively doesn't exist for CI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Set

try:
    import jsonschema
except Exception:
    print("[test-registry] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests" / "manifest.json"
SCHEMA = ROOT / "docs" / "schemas" / "TestManifest.schema.json"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_scripts() -> List[Path]:
    """Return repo-relative Paths that should be registered as tests."""
    candidates: List[Path] = []

    # Directories where every .py script (except explicit helpers) is a test.
    must_register_roots = [
        ROOT / "tests" / "contract",
        ROOT / "tests" / "schema",
        ROOT / "tests" / "determinism",
        ROOT / "tests" / "setup",
        ROOT / "tests" / "agent_eval",
        ROOT / "tests" / "e2e",
        ROOT / "tests" / "stress",
        ROOT / "tests" / "automation",
    ]

    for d in must_register_roots:
        if not d.exists():
            continue
        for p in d.rglob("*.py"):
            if p.name in {"__init__.py"}:
                continue
            candidates.append(p)

    # Exclusions: runners/helpers
    excluded_names = {
        "run.py",
        "lint.py",
        "dry_run_single.py",
    }

    out: List[Path] = []
    for p in sorted(set(candidates)):
        if p.name in excluded_names:
            continue
        # We only register tests under `tests/`.
        if "tests" not in p.parts:
            continue
        out.append(p)
    return out


def main() -> int:
    manifest = load_json(MANIFEST)
    schema = load_json(SCHEMA)

    # 1) Schema validation
    v = jsonschema.Draft202012Validator(schema)
    errors = sorted(v.iter_errors(manifest), key=lambda e: list(e.absolute_path))
    if errors:
        print("[test-registry][FAIL] manifest schema errors:", file=sys.stderr)
        for e in errors:
            path = "/" + "/".join(str(p) for p in e.absolute_path)
            print(f"  - {path}: {e.message}", file=sys.stderr)
        return 2

    tests: List[Dict[str, Any]] = list(manifest["tests"])

    # 2) Unique ids and existing scripts
    ids: Set[str] = set()
    scripts: Set[str] = set()
    bad = 0

    for t in tests:
        tid = t["id"]
        if tid in ids:
            print(f"[test-registry][FAIL] duplicate test id: {tid}", file=sys.stderr)
            bad += 1
        ids.add(tid)

        script = t["script"]
        scripts.add(script)
        sp = ROOT / script
        if not sp.exists():
            print(f"[test-registry][FAIL] missing script for {tid}: {script}", file=sys.stderr)
            bad += 1

    # 3) Ensure all candidate scripts are registered
    missing: List[str] = []
    for p in candidate_scripts():
        rel = p.relative_to(ROOT).as_posix()
        if rel not in scripts:
            missing.append(rel)

    if missing:
        print("[test-registry][FAIL] unregistered test scripts:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        bad += 1

    if bad:
        print("[test-registry] Fix by adding entries to tests/manifest.json and regenerating docs/testing/TEST_MATRIX.md", file=sys.stderr)
        return 2

    print("[test-registry] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
