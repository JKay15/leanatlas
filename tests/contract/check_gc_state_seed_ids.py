"""Contract test: gc_state.json seed_id keys must be Lean module names.

Why this exists:
- In Lean, *module name* is the identity used by `import` and by compiled-environment tooling.
- Using repo-relative paths as IDs is fragile and diverges from how Lean/LSP/import-graph talk.

This test enforces the LeanAtlas V0.2 rule:
- tools/index/gc_state.json must use Lean module names as keys.
- If path_hint is present, it must match the deterministic module->path mapping.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GC_STATE_PATH = REPO_ROOT / "tools" / "index" / "gc_state.json"

# Conservative module-name regex (ASCII-only): Lean allows more, but we keep it strict for hygiene.
MODULE_RE = re.compile(r"^LeanAtlas(\.[A-Za-z_][A-Za-z0-9_]*)+$")


def module_to_path(module_name: str) -> Path:
    # Lean import name to source file path mapping: dots become '/', '.lean' suffix.
    return Path(*module_name.split(".")) .with_suffix(".lean")


def main() -> None:
    assert GC_STATE_PATH.exists(), f"Missing gc_state.json at {GC_STATE_PATH}"

    data = json.loads(GC_STATE_PATH.read_text(encoding="utf-8"))
    seeds = data.get("seeds", {})
    assert isinstance(seeds, dict), "gc_state.json: seeds must be an object/map"

    for seed_id, record in seeds.items():
        assert isinstance(seed_id, str), "gc_state.json: seed_id key must be a string"
        assert MODULE_RE.match(seed_id), (
            f"gc_state.json: seed_id must be a Lean module name starting with 'LeanAtlas.': {seed_id}"
        )

        derived_rel = module_to_path(seed_id)
        derived_abs = REPO_ROOT / derived_rel

        # For LeanAtlas Seeds GC, seed modules must exist as source files.
        assert derived_abs.exists(), (
            f"gc_state.json: seed_id maps to missing source file: {seed_id} -> {derived_rel}"
        )

        # path_hint, if present, must match derived path.
        if isinstance(record, dict) and "path_hint" in record and record["path_hint"] is not None:
            assert isinstance(record["path_hint"], str), "path_hint must be a string or null"
            assert Path(record["path_hint"]) == derived_rel, (
                f"gc_state.json: path_hint mismatch for {seed_id}: "
                f"expected {derived_rel}, got {record['path_hint']}"
            )


if __name__ == "__main__":
    main()
