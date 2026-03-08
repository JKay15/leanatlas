#!/usr/bin/env python3
"""Contract: LOOP mainline productization must expose a canonical doc + skill entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _fail(msg: str) -> int:
    print(f"[loop-mainline-docs][FAIL] {msg}", file=sys.stderr)
    return 2


def _read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(rel)
    return path.read_text(encoding="utf-8")


def main() -> int:
    plan_rel = "docs/agents/execplans/20260307_loop_mainline_productization_integration_v0.md"
    mainline_doc_rel = "docs/agents/LOOP_MAINLINE.md"
    skill_rel = ".agents/skills/leanatlas-loop-mainline/SKILL.md"

    try:
        plan = _read(plan_rel)
    except FileNotFoundError:
        return _fail(f"missing child ExecPlan: {plan_rel}")
    if not any(token in plan for token in ("status: planned", "status: active", "status: done")):
        return _fail(f"{plan_rel} must carry an explicit status while remaining the authoritative child plan")

    try:
        mainline_doc = _read(mainline_doc_rel)
    except FileNotFoundError:
        return _fail(f"missing canonical LOOP mainline doc: {mainline_doc_rel}")

    required_doc_snippets = [
        "## Capability Matrix",
        "Implemented",
        "Partial",
        "Planned",
        "LOOP core",
        "LeanAtlas adapters",
        ".cache/leanatlas/tmp",
    ]
    for snippet in required_doc_snippets:
        if snippet not in mainline_doc:
            return _fail(f"{mainline_doc_rel} missing required snippet `{snippet}`")

    project_entry_docs = [
        "docs/agents/STATUS.md",
        "docs/agents/README.md",
        "docs/agents/MAINTAINER_WORKFLOW.md",
        "docs/agents/OPERATOR_WORKFLOW.md",
    ]
    for rel in project_entry_docs:
        text = _read(rel)
        if mainline_doc_rel not in text:
            return _fail(f"{rel} must reference {mainline_doc_rel}")

    try:
        skill = _read(skill_rel)
    except FileNotFoundError:
        return _fail(f"missing LOOP mainline skill: {skill_rel}")
    if "LOOP mainline" not in skill:
        return _fail(f"{skill_rel} must describe LOOP mainline usage explicitly")

    skills_index = _read(".agents/skills/README.md")
    if skill_rel not in skills_index:
        return _fail(".agents/skills/README.md must index the LOOP mainline skill")

    print("[loop-mainline-docs] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
