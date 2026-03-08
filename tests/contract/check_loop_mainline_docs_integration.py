#!/usr/bin/env python3
"""Contract: LOOP mainline productization must expose a canonical doc + skill entrypoint."""

from __future__ import annotations

import re
import sys
from datetime import date
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
    if "- stable maintainer session bookkeeping and closeout refs" in mainline_doc.split("### LeanAtlas adapters", 1)[0]:
        return _fail("docs/agents/LOOP_MAINLINE.md must not classify maintainer closeout refs as LOOP core semantics")
    if "stable maintainer session bookkeeping and closeout refs" not in mainline_doc.split("### LeanAtlas adapters", 1)[-1]:
        return _fail("docs/agents/LOOP_MAINLINE.md must classify maintainer closeout refs under LeanAtlas adapters")

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

    onboarding_doc = _read("docs/agents/ONBOARDING.md")
    onboard_skill = _read(".agents/skills/leanatlas-onboard/SKILL.md")
    discoverability_snippets = [
        "reviewer exhaustiveness",
        "tools/loop/review_prompting.py",
        "review.prompt.exhaustive.v1",
    ]
    for snippet in discoverability_snippets:
        if snippet not in onboarding_doc:
            return _fail(f"docs/agents/ONBOARDING.md must surface reviewer exhaustiveness via `{snippet}`")
        if snippet not in onboard_skill:
            return _fail(f".agents/skills/leanatlas-onboard/SKILL.md must surface reviewer exhaustiveness via `{snippet}`")

    agents_readme = _read("docs/agents/README.md")
    if ".agents/skills/leanatlas-dedup|promote|gc/SKILL.md" in agents_readme:
        return _fail("docs/agents/README.md must not advertise the non-resolvable combined Phase3 skill path")
    for skill_ref in (
        ".agents/skills/leanatlas-dedup/SKILL.md",
        ".agents/skills/leanatlas-promote/SKILL.md",
        ".agents/skills/leanatlas-gc/SKILL.md",
    ):
        if skill_ref not in agents_readme:
            return _fail(f"docs/agents/README.md must route Phase3 readers to {skill_ref}")

    status_doc = _read("docs/agents/STATUS.md")
    header_match = re.search(r"## Where are we now \(as of (\d{4}-\d{2}-\d{2})\)", status_doc)
    if not header_match:
        return _fail("docs/agents/STATUS.md must carry an `as of YYYY-MM-DD` snapshot header")
    try:
        snapshot_date = date.fromisoformat(header_match.group(1))
    except ValueError:
        return _fail("docs/agents/STATUS.md snapshot header must use ISO date format")
    mentioned_dates = [date.fromisoformat(raw) for raw in re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", status_doc)]
    if not mentioned_dates:
        return _fail("docs/agents/STATUS.md must mention at least one dated project update")
    if snapshot_date != max(mentioned_dates):
        return _fail("docs/agents/STATUS.md snapshot date must match the newest dated update in the document")

    skills_index = _read(".agents/skills/README.md")
    if skill_rel not in skills_index:
        return _fail(".agents/skills/README.md must index the LOOP mainline skill")

    print("[loop-mainline-docs] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
