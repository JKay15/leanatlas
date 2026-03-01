#!/usr/bin/env python3
"""Contract test: ensure Phase3 is represented in executable E2E scenarios.

Problem this prevents:
- We design Phase3 contracts (Dedup/Promotion/GC) but never exercise the tool entrypoints
  in the workflow-level test harness.

This test is **structural** (core-tier):
- It does not run Lean.
- It only checks that at least one smoke-tier executable scenario includes `run_cmd` steps
  that call Phase3 tool entrypoints.

Rationale:
- Smoke-tier scenario execution is what developers actually run locally first.
- If Phase3 isn't in smoke scenarios, it will rot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml  # type: ignore


PHASE3_TOOL_FRAGMENTS = [
    "tools/gc/gc.py",
    "tools/dedup/dedup.py",
    "tools/promote/promote.py",
]


PHASE3_SKILLS = [
    "leanatlas-gc",
    "leanatlas-dedup",
    "leanatlas-promote",
]


def parse_frontmatter(md: str) -> Tuple[Dict[str, Any] | None, str]:
    """Return (frontmatter_yaml, error)."""

    lines = md.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "missing frontmatter start '---'"
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, "missing frontmatter end '---'"
    raw = "\n".join(lines[1:end])
    try:
        obj = yaml.safe_load(raw)  # type: ignore
    except Exception as e:  # noqa: BLE001
        return None, f"frontmatter yaml parse error: {type(e).__name__}: {e}"
    if not isinstance(obj, dict):
        return None, "frontmatter yaml is not a mapping"
    return obj, ""


def check_execplan_codex_skeleton(text: str) -> str:
    """Minimal structural checks for a Codex-style ExecPlan.

    From the official Codex ExecPlan guidance:
    - when stored as a standalone .md file, the plan should omit triple backticks
    - plans must include Progress / Surprises & Discoveries / Decision Log / Outcomes & Retrospective

    We enforce only what is cheaply checkable in core-tier tests.
    """

    if "```" in text:
        return "ExecPlan must omit triple backticks in a standalone .md file"

    required_snippets = [
        "# Phase3 PromotionGate",
        "Owner:",
        "Status:",
        "Created:",
        "## Purpose / Big Picture",
        "## Progress",
        "## Surprises & Discoveries",
        "## Decision Log",
        "## Outcomes & Retrospective",
        "## Context and Orientation",
        "## Plan of Work",
        "## Concrete Steps",
        "## Validation and Acceptance",
        "## Idempotence and Recovery",
        "## Artifacts and Notes",
    ]
    for s in required_snippets:
        if s not in text:
            return f"missing required section/snippet: {s}"
    return ""


def load_yaml(p: Path) -> Dict[str, Any]:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def check_skill(repo_root: Path, skill_name: str) -> str:
    """Return empty string on success; otherwise an error message."""

    skill_path = repo_root / ".agents" / "skills" / skill_name / "SKILL.md"
    if not skill_path.exists():
        return f"missing skill file {skill_path}"
    skill_text = skill_path.read_text(encoding="utf-8")
    fm, err = parse_frontmatter(skill_text)
    if fm is None:
        return f"{skill_name} SKILL.md {err}"
    if fm.get("name") != skill_name or not str(fm.get("description") or "").strip():
        return f"{skill_name} SKILL.md must set frontmatter name and description"
    if "TODO" in skill_text:
        return f"{skill_name} SKILL.md still contains TODO placeholders"
    return ""


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    scenarios_root = repo_root / "tests" / "e2e" / "scenarios"

    frag_hits: Dict[str, List[str]] = {f: [] for f in PHASE3_TOOL_FRAGMENTS}

    for sc_dir in sorted(scenarios_root.iterdir()):
        if not sc_dir.is_dir():
            continue
        y = sc_dir / "scenario.yaml"
        if not y.exists():
            continue
        meta = load_yaml(y)
        if meta.get("tier") != "smoke":
            continue
        if not (meta.get("execution", {}) or {}).get("enabled", False):
            continue
        for step in (meta.get("steps") or []):
            if (step or {}).get("kind") != "run_cmd":
                continue
            cmd = (step or {}).get("cmd") or []
            if not isinstance(cmd, list):
                continue
            cmd_str = " ".join(str(x) for x in cmd)

            for frag in PHASE3_TOOL_FRAGMENTS:
                if frag in cmd_str:
                    frag_hits[frag].append(f"{sc_dir.name}: {cmd_str}")

    missing = [frag for frag, hs in frag_hits.items() if not hs]
    if missing:
        print("[phase3-scenarios] FAIL: Phase3 smoke scenarios do not cover all Phase3 tool entrypoints")
        print("Missing run_cmd coverage for:")
        for f in missing:
            print(" -", f)
        return 1

    # Capability manifest must expose Phase3 commands (so Phase5 automation/skills regen can consume it).
    cap_path = repo_root / "tools" / "capabilities" / "phase3.yaml"
    cap = load_yaml(cap_path)
    cmds = cap.get("commands") or []
    cmd_by_id: Dict[str, Dict[str, Any]] = {}
    for c in cmds:
        if isinstance(c, dict) and isinstance(c.get("id"), str):
            cmd_by_id[str(c["id"])] = c

    for cmd_id in ["promote.gate", "dedup.gate"]:
        if cmd_id not in cmd_by_id:
            print(f"[phase3-scenarios] FAIL: tools/capabilities/phase3.yaml is missing command id={cmd_id}")
            return 1

    smoke = cmd_by_id["promote.gate"].get("smoke") or []
    smoke_str = "\n".join(str(x) for x in smoke)
    if "--plan" not in smoke_str or "--mode" not in smoke_str:
        print("[phase3-scenarios] FAIL: promote.gate smoke command must include --plan and --mode")
        return 1

    # Skills must be discoverable by Codex (frontmatter name/description).
    for s in PHASE3_SKILLS:
        err = check_skill(repo_root, s)
        if err:
            print(f"[phase3-scenarios] FAIL: {err}")
            return 1

    # ExecPlan must exist for the structural signals workstream.
    plan_path = repo_root / "docs" / "agents" / "execplans" / "phase3_promotion_structural_signals_v1.md"
    if not plan_path.exists():
        print("[phase3-scenarios] FAIL: missing ExecPlan phase3_promotion_structural_signals_v1.md")
        return 1
    plan_text = plan_path.read_text(encoding="utf-8")
    perr = check_execplan_codex_skeleton(plan_text)
    if perr:
        print(f"[phase3-scenarios] FAIL: ExecPlan format {perr}")
        return 1

    print("[phase3-scenarios] OK")
    for frag in PHASE3_TOOL_FRAGMENTS:
        for h in frag_hits[frag]:
            print(" -", h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
