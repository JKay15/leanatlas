#!/usr/bin/env python3
"""Contract: required automation closed loops must stay present.

This guards three long-running loops:
- Phase3 governance loop (promotion/gc continuous audit)
- Skills growth loop (telemetry -> KB suggestions -> regen/stub checks)
- Chat feedback deposition loop (prompt/user feedback -> structured backlog)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "automations" / "registry.json"


REQUIRED_ACTIVE_IDS = {
    "nightly_reporting_integrity",
    "nightly_mcp_healthcheck",
    "nightly_trace_mining",
    "weekly_kb_suggestions",
    "nightly_dedup_instances",
    "weekly_docpack_memory_audit",
    "nightly_phase3_governance_audit",
    "nightly_chat_feedback_deposition",
}


def _script_path_from_cmd(cmd: List[str]) -> Optional[str]:
    if not cmd:
        return None
    if cmd[0] in {"python", "python3"} and len(cmd) >= 2:
        return cmd[1]
    for i, tok in enumerate(cmd):
        if tok in {"python", "python3"} and i + 1 < len(cmd):
            return cmd[i + 1]
    return None


def _find_auto(data: Dict[str, Any], aid: str) -> Dict[str, Any]:
    for auto in data.get("automations") or []:
        if isinstance(auto, dict) and auto.get("id") == aid:
            return auto
    raise AssertionError(f"missing automation id={aid}")


def _step_scripts(auto: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for step in (auto.get("deterministic") or {}).get("steps") or []:
        if not isinstance(step, dict):
            continue
        cmd = list(step.get("cmd") or [])
        script = _script_path_from_cmd(cmd)
        if script:
            out.append(script)
    return out


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    autos = [a for a in data.get("automations") or [] if isinstance(a, dict)]
    active_ids = {str(a.get("id")) for a in autos if a.get("status") == "active"}

    missing_active = sorted(REQUIRED_ACTIVE_IDS - active_ids)
    _require(not missing_active, f"required active automations missing: {missing_active}")

    # Skills closed-loop: weekly_kb_suggestions must include full deterministic chain.
    kb = _find_auto(data, "weekly_kb_suggestions")
    kb_scripts = set(_step_scripts(kb))
    _require(
        {
            "tools/bench/collect_telemetry.py",
            "tools/bench/mine_kb_suggestions.py",
            "tools/coordination/skills_regen.py",
            "tools/coordination/skills_stubgen.py",
        }.issubset(kb_scripts),
        "weekly_kb_suggestions must include collect_telemetry + mine_kb_suggestions + skills_regen + skills_stubgen",
    )
    kb_artifacts = set((kb.get("deterministic") or {}).get("artifacts") or [])
    _require("artifacts/telemetry/**" in kb_artifacts, "weekly_kb_suggestions must declare artifacts/telemetry/**")
    _require("artifacts/skills_regen/**" in kb_artifacts, "weekly_kb_suggestions must declare artifacts/skills_regen/**")

    # Phase3 governance loop.
    p3 = _find_auto(data, "nightly_phase3_governance_audit")
    p3_scripts = set(_step_scripts(p3))
    _require(
        "tools/coordination/phase3_governance_audit.py" in p3_scripts,
        "nightly_phase3_governance_audit must execute tools/coordination/phase3_governance_audit.py",
    )
    p3_probe = ((p3.get("advisor") or {}).get("probe") or {})
    _require(
        p3_probe.get("path") == "artifacts/phase3_governance/latest/GovernanceAudit.json",
        "nightly_phase3_governance_audit advisor.probe.path must point to GovernanceAudit.json",
    )
    _require(
        p3_probe.get("field") == "findings",
        "nightly_phase3_governance_audit advisor.probe.field must be findings",
    )
    p3_script = ROOT / "tools" / "coordination" / "phase3_governance_audit.py"
    _require(p3_script.exists(), "missing tools/coordination/phase3_governance_audit.py")
    p3_text = p3_script.read_text(encoding="utf-8")
    _require("gc.py" in p3_text, "phase3_governance_audit.py must run gc.py")
    _require("promote.py" in p3_text, "phase3_governance_audit.py must run promote.py")

    # Chat feedback deposition loop.
    fb = _find_auto(data, "nightly_chat_feedback_deposition")
    fb_scripts = set(_step_scripts(fb))
    _require(
        "tools/feedback/mine_chat_feedback.py" in fb_scripts,
        "nightly_chat_feedback_deposition must execute tools/feedback/mine_chat_feedback.py",
    )
    _require(
        "tools/feedback/append_feedback_ledger.py" in fb_scripts,
        "nightly_chat_feedback_deposition must execute tools/feedback/append_feedback_ledger.py",
    )
    _require(
        "tools/feedback/build_traceability_matrix.py" in fb_scripts,
        "nightly_chat_feedback_deposition must execute tools/feedback/build_traceability_matrix.py",
    )
    fb_steps = list((fb.get("deterministic") or {}).get("steps") or [])
    trace_steps = [s for s in fb_steps if isinstance(s, dict) and s.get("name") == "build_traceability_matrix"]
    _require(trace_steps, "nightly_chat_feedback_deposition must define build_traceability_matrix step by name")
    trace_cmd = list((trace_steps[0].get("cmd") or []))
    _require("--strict-closed" in trace_cmd, "build_traceability_matrix step must include --strict-closed")
    fb_probe = ((fb.get("advisor") or {}).get("probe") or {})
    _require(
        fb_probe.get("path") == "artifacts/feedback/ledger/latest_append_summary.json",
        "nightly_chat_feedback_deposition advisor.probe.path must point to ledger append summary",
    )
    _require(
        fb_probe.get("field") == "new_items_count",
        "nightly_chat_feedback_deposition advisor.probe.field must be new_items_count",
    )
    _require(
        fb_probe.get("kind") == "json_field_gt",
        "nightly_chat_feedback_deposition advisor.probe.kind must be json_field_gt",
    )
    _require(
        float(fb_probe.get("threshold", -1)) == 0.0,
        "nightly_chat_feedback_deposition advisor.probe.threshold must be 0",
    )
    fb_artifacts = set((fb.get("deterministic") or {}).get("artifacts") or [])
    _require(
        "artifacts/feedback/chat_feedback/**" in fb_artifacts,
        "nightly_chat_feedback_deposition must declare artifacts/feedback/chat_feedback/**",
    )
    _require(
        "artifacts/feedback/ledger/**" in fb_artifacts,
        "nightly_chat_feedback_deposition must declare artifacts/feedback/ledger/**",
    )
    _require(
        "artifacts/feedback/traceability/**" in fb_artifacts,
        "nightly_chat_feedback_deposition must declare artifacts/feedback/traceability/**",
    )
    _require((ROOT / "tools" / "feedback" / "mine_chat_feedback.py").exists(), "missing tools/feedback/mine_chat_feedback.py")
    _require((ROOT / "tools" / "feedback" / "append_feedback_ledger.py").exists(), "missing tools/feedback/append_feedback_ledger.py")
    _require((ROOT / "tools" / "feedback" / "build_traceability_matrix.py").exists(), "missing tools/feedback/build_traceability_matrix.py")

    print("[automation.closed-loops][PASS]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[automation.closed-loops][FAIL] {ex}")
        raise SystemExit(1)
