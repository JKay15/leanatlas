#!/usr/bin/env python3
"""Contract check: formalization governor policy is deterministic and gate-aligned."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.workflow.formalization_governor import decide_formalization_cycle


def _fail(msg: str) -> int:
    print(f"[formalization-governor-policy][FAIL] {msg}", file=sys.stderr)
    return 2


def _base_gate_report() -> dict:
    return {
        "generated_at_utc": "2026-03-06T00:00:00Z",
        "policy_version": "0.1",
        "stage": "draft",
        "gate_pass": True,
        "formalization_gate": {"pass": True, "checks": [], "counts": {}, "issues": []},
        "mapping_gate": {"pass": True, "checks": [], "counts": {}, "issues": []},
        "checks": [],
        "counts": {},
        "issues": [],
    }


def main() -> int:
    gov_contract = ROOT / "docs" / "contracts" / "FORMALIZATION_GOVERNANCE_CONTRACT.md"
    workflow_contract = ROOT / "docs" / "contracts" / "WORKFLOW_CONTRACT.md"
    governor_path = ROOT / "tools" / "workflow" / "formalization_governor.py"
    for p in (gov_contract, workflow_contract, governor_path):
        if not p.exists():
            return _fail(f"missing required file: {p.relative_to(ROOT)}")

    gov_txt = gov_contract.read_text(encoding="utf-8")
    wf_txt = workflow_contract.read_text(encoding="utf-8")
    required_gov_snippets = [
        "formalization_governor.py",
        "DUAL_GATE_PASS",
        "FIXABLE_GATE_FAILURE",
        "NON_FIXABLE_BLOCKER",
    ]
    for snippet in required_gov_snippets:
        if snippet not in gov_txt:
            return _fail(f"FORMALIZATION_GOVERNANCE_CONTRACT missing `{snippet}`")
    if "formalization governor" not in wf_txt.lower():
        return _fail("WORKFLOW_CONTRACT must mention formalization governor integration")

    # Case A: both gates pass.
    pass_report = _base_gate_report()
    a = decide_formalization_cycle(gate_report=pass_report, iteration_index=1)
    if a["decision"] != "PASSED" or a["reason_code"] != "DUAL_GATE_PASS":
        return _fail("dual-pass gate report must produce PASSED/DUAL_GATE_PASS")

    # Case B: repairable gate failure -> CONTINUE.
    repairable = _base_gate_report()
    repairable["gate_pass"] = False
    repairable["formalization_gate"]["pass"] = False
    repairable["formalization_gate"]["issues"] = [
        {"code": "OPAQUE_HYPOTHESIS_PATTERN", "severity": "S2_MAJOR", "message": "opaque hypothesis detected"}
    ]
    b = decide_formalization_cycle(gate_report=repairable, iteration_index=1, max_repair_rounds=3)
    if b["decision"] != "CONTINUE" or b["reason_code"] != "FIXABLE_GATE_FAILURE":
        return _fail("repairable failure should continue with FIXABLE_GATE_FAILURE")
    if "repair_formalization_gate" not in b["next_actions"]:
        return _fail("repairable formalization failure should suggest repair_formalization_gate")

    # Case C: unresolved external dependency forces TRIAGED.
    external_block = _base_gate_report()
    external_block["gate_pass"] = False
    external_block["mapping_gate"]["pass"] = False
    external_block["issues"] = [
        {"code": "EXTERNAL_DEPENDENCY_PENDING", "severity": "S2_MAJOR", "message": "external theorem unresolved"}
    ]
    c = decide_formalization_cycle(gate_report=external_block, iteration_index=1)
    if c["decision"] != "TRIAGED" or c["reason_code"] != "NON_FIXABLE_BLOCKER":
        return _fail("external dependency pending must triage as NON_FIXABLE_BLOCKER")

    # Case D: stagnation cap forces TRIAGED.
    d = decide_formalization_cycle(
        gate_report=repairable,
        iteration_index=1,
        repeated_fingerprint_count=2,
        max_same_fingerprint_rounds=2,
    )
    if d["decision"] != "TRIAGED" or d["reason_code"] != "GOVERNOR_STAGNATION":
        return _fail("repeated same fingerprint at cap must TRIAGE with GOVERNOR_STAGNATION")

    # Case E: repair budget exhausted forces TRIAGED.
    e = decide_formalization_cycle(gate_report=repairable, iteration_index=3, max_repair_rounds=3)
    if e["decision"] != "TRIAGED" or e["reason_code"] != "GOVERNOR_REPAIR_BUDGET_EXHAUSTED":
        return _fail("repair budget cap must TRIAGE with GOVERNOR_REPAIR_BUDGET_EXHAUSTED")

    # Determinism check: identical inputs => identical output.
    b2 = decide_formalization_cycle(gate_report=repairable, iteration_index=1, max_repair_rounds=3)
    if b != b2:
        return _fail("governor output must be deterministic for identical input")

    print("[formalization-governor-policy] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
