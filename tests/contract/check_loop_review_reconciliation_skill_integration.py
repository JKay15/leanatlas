#!/usr/bin/env python3
"""Guardrail: review reconciliation must expose a generic LOOP skill plus LeanAtlas routing."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _fail(msg: str) -> int:
    print(f"[loop-reconciliation-skill][FAIL] {msg}", file=sys.stderr)
    return 2


def _read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(rel)
    return path.read_text(encoding="utf-8")


def main() -> int:
    plan_rel = "docs/agents/execplans/20260308_loop_review_reconciliation_generic_skill_v0.md"
    generic_skill_rel = ".agents/skills/loop-review-reconciliation/SKILL.md"
    loop_mainline_doc_rel = "docs/agents/LOOP_MAINLINE.md"
    loop_mainline_skill_rel = ".agents/skills/leanatlas-loop-mainline/SKILL.md"
    maintainer_skill_rel = ".agents/skills/leanatlas-loop-maintainer-ops/SKILL.md"
    agents_readme_rel = "docs/agents/README.md"
    skills_index_rel = ".agents/skills/README.md"

    plan = _read(plan_rel)
    if re.search(r"^status:\s+\S", plan, re.MULTILINE) is None:
        return _fail(f"{plan_rel} must carry an explicit status")

    generic_skill = _read(generic_skill_rel)
    required_skill_snippets = [
        "Review supersession / reconciliation runtime",
        "CONFIRMED",
        "DISMISSED",
        "SUPERSEDED",
        "finding_group_key",
        "scope_lineage_key",
    ]
    for snippet in required_skill_snippets:
        if snippet not in generic_skill:
            return _fail(f"{generic_skill_rel} missing required snippet `{snippet}`")

    skills_index = _read(skills_index_rel)
    if generic_skill_rel not in skills_index:
        return _fail(f"{skills_index_rel} must index {generic_skill_rel}")

    loop_mainline_doc = _read(loop_mainline_doc_rel)
    if generic_skill_rel not in loop_mainline_doc:
        return _fail(f"{loop_mainline_doc_rel} must reference {generic_skill_rel}")

    loop_mainline_skill = _read(loop_mainline_skill_rel)
    if generic_skill_rel not in loop_mainline_skill:
        return _fail(f"{loop_mainline_skill_rel} must route reconciliation-specific work to {generic_skill_rel}")

    maintainer_skill = _read(maintainer_skill_rel)
    if generic_skill_rel not in maintainer_skill:
        return _fail(f"{maintainer_skill_rel} must reference {generic_skill_rel} for generic reconciliation semantics")

    agents_readme = _read(agents_readme_rel)
    if generic_skill_rel not in agents_readme:
        return _fail(f"{agents_readme_rel} must reference {generic_skill_rel}")

    print("[loop-reconciliation-skill] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
