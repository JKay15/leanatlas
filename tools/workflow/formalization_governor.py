#!/usr/bin/env python3
"""Deterministic governor for formalization dual-gate decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


NON_FIXABLE_CODES_DEFAULT = {
    "EXTERNAL_DEPENDENCY_PENDING",
    "UNRESOLVED_EXTERNAL_RESULT",
    "MISSING_EXTERNAL_THEOREM_BODY",
    "PAPER_PROOF_MISSING_NON_EXTERNAL",
}


def _canon_issue(issue: dict[str, Any]) -> dict[str, Any]:
    code = str(issue.get("code", "")).strip()
    severity = str(issue.get("severity", "")).strip()
    message = str(issue.get("message", "")).strip()
    ref = issue.get("ref")
    if not isinstance(ref, (dict, list, str, int, float, bool)) and ref is not None:
        ref = str(ref)
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "ref": ref,
    }


def _collect_issues(report: dict[str, Any]) -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    for key in ("issues",):
        arr = report.get(key)
        if isinstance(arr, list):
            raw.extend([x for x in arr if isinstance(x, dict)])
    for gate_key in ("formalization_gate", "mapping_gate"):
        gate = report.get(gate_key)
        if not isinstance(gate, dict):
            continue
        arr = gate.get("issues")
        if isinstance(arr, list):
            raw.extend([x for x in arr if isinstance(x, dict)])

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for issue in raw:
        canon = _canon_issue(issue)
        key = json.dumps(canon, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(canon)
    out.sort(key=lambda x: (x["severity"], x["code"], json.dumps(x.get("ref"), ensure_ascii=False, sort_keys=True)))
    return out


def issue_fingerprint(issues: list[dict[str, Any]]) -> str:
    material = json.dumps(issues, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _next_actions(
    *,
    formalization_pass: bool,
    mapping_pass: bool,
    has_external_pending: bool,
    has_s1: bool,
) -> list[str]:
    actions: list[str] = []
    if not formalization_pass:
        actions.append("repair_formalization_gate")
    if not mapping_pass:
        actions.append("repair_mapping_gate")
    if has_external_pending:
        actions.append("resolve_external_dependency")
    if has_s1:
        actions.append("escalate_human_or_gpt52pro")
    if not actions:
        actions.append("no_action")
    return actions


def decide_formalization_cycle(
    *,
    gate_report: dict[str, Any],
    iteration_index: int,
    max_repair_rounds: int = 3,
    repeated_fingerprint_count: int = 1,
    max_same_fingerprint_rounds: int = 2,
    non_fixable_codes: set[str] | None = None,
) -> dict[str, Any]:
    non_fixable = set(non_fixable_codes or NON_FIXABLE_CODES_DEFAULT)
    formalization_gate = gate_report.get("formalization_gate") if isinstance(gate_report.get("formalization_gate"), dict) else {}
    mapping_gate = gate_report.get("mapping_gate") if isinstance(gate_report.get("mapping_gate"), dict) else {}
    formalization_pass = bool(formalization_gate.get("pass", False))
    mapping_pass = bool(mapping_gate.get("pass", False))
    gate_pass = bool(gate_report.get("gate_pass", False))

    issues = _collect_issues(gate_report)
    fingerprint = issue_fingerprint(issues)
    codes = sorted({str(x.get("code", "")).strip() for x in issues if str(x.get("code", "")).strip()})
    has_s1 = any(str(x.get("severity", "")).strip() == "S1_CRITICAL" for x in issues)
    has_non_fixable = has_s1 or any(code in non_fixable for code in codes)
    has_external_pending = "EXTERNAL_DEPENDENCY_PENDING" in codes

    reason_code = "DUAL_GATE_PASS"
    decision = "PASSED"
    fixable = True

    if not gate_pass:
        decision = "CONTINUE"
        reason_code = "FIXABLE_GATE_FAILURE"
        if has_non_fixable:
            decision = "TRIAGED"
            reason_code = "NON_FIXABLE_BLOCKER"
            fixable = False
        elif int(repeated_fingerprint_count) >= int(max_same_fingerprint_rounds):
            decision = "TRIAGED"
            reason_code = "GOVERNOR_STAGNATION"
            fixable = False
        elif int(iteration_index) >= int(max_repair_rounds):
            decision = "TRIAGED"
            reason_code = "GOVERNOR_REPAIR_BUDGET_EXHAUSTED"
            fixable = False

    counts = {
        "issues_total": len(issues),
        "s1_critical_count": sum(1 for x in issues if x["severity"] == "S1_CRITICAL"),
        "s2_major_count": sum(1 for x in issues if x["severity"] == "S2_MAJOR"),
    }
    return {
        "decision": decision,
        "judge_decision": "SUCCESS" if decision == "PASSED" else ("TRIAGED" if decision == "TRIAGED" else "CONTINUE"),
        "reason_code": reason_code,
        "fixable": bool(fixable),
        "gate_pass": gate_pass,
        "formalization_gate_pass": formalization_pass,
        "mapping_gate_pass": mapping_pass,
        "iteration_index": int(iteration_index),
        "max_repair_rounds": int(max_repair_rounds),
        "repeated_fingerprint_count": int(repeated_fingerprint_count),
        "max_same_fingerprint_rounds": int(max_same_fingerprint_rounds),
        "issue_fingerprint": fingerprint,
        "blocking_issue_codes": codes,
        "counts": counts,
        "next_actions": _next_actions(
            formalization_pass=formalization_pass,
            mapping_pass=mapping_pass,
            has_external_pending=has_external_pending,
            has_s1=has_s1,
        ),
        "issues": issues,
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Decide formalization dual-gate cycle deterministically")
    ap.add_argument("--gate-report", required=True, help="FormalizationGateReport JSON path")
    ap.add_argument("--output", required=True, help="output decision JSON path")
    ap.add_argument("--iteration-index", type=int, required=True)
    ap.add_argument("--max-repair-rounds", type=int, default=3)
    ap.add_argument("--repeated-fingerprint-count", type=int, default=1)
    ap.add_argument("--max-same-fingerprint-rounds", type=int, default=2)
    ap.add_argument(
        "--non-fixable-codes",
        default=",".join(sorted(NON_FIXABLE_CODES_DEFAULT)),
        help="comma-separated issue codes that force TRIAGED",
    )
    args = ap.parse_args()

    gate_report = _load_json(Path(args.gate_report).resolve())
    non_fixable_codes = {x.strip() for x in str(args.non_fixable_codes).split(",") if x.strip()}
    decision = decide_formalization_cycle(
        gate_report=gate_report,
        iteration_index=int(args.iteration_index),
        max_repair_rounds=int(args.max_repair_rounds),
        repeated_fingerprint_count=int(args.repeated_fingerprint_count),
        max_same_fingerprint_rounds=int(args.max_same_fingerprint_rounds),
        non_fixable_codes=non_fixable_codes,
    )
    _dump_json(Path(args.output).resolve(), decision)
    print(
        json.dumps(
            {
                "output": str(Path(args.output).resolve()),
                "decision": decision["decision"],
                "reason_code": decision["reason_code"],
                "issue_fingerprint": decision["issue_fingerprint"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
