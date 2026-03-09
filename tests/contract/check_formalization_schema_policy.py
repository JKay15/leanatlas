#!/usr/bin/env python3
"""Contract check: formalization contracts/schemas remain aligned."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fail(msg: str) -> int:
    print(f"[formalization-schema-policy][FAIL] {msg}", file=sys.stderr)
    return 2


def _require_snippets(path: Path, snippets: list[str]) -> list[str]:
    txt = path.read_text(encoding="utf-8")
    missing: list[str] = []
    for s in snippets:
        if s not in txt:
            missing.append(s)
    return missing


def main() -> int:
    governance_contract = ROOT / "docs" / "contracts" / "FORMALIZATION_GOVERNANCE_CONTRACT.md"
    ledger_contract = ROOT / "docs" / "contracts" / "FORMALIZATION_LEDGER_CONTRACT.md"

    worklist_schema = ROOT / "docs" / "schemas" / "ProofCompletionWorklist.schema.json"
    decision_schema = ROOT / "docs" / "schemas" / "ProofCompletionDecisionApplyReport.schema.json"
    review_schema = ROOT / "docs" / "schemas" / "AgentFidelityReview.schema.json"
    gate_schema = ROOT / "docs" / "schemas" / "FormalizationGateReport.schema.json"
    ledger_schema = ROOT / "docs" / "schemas" / "FormalizationLedger.schema.json"

    required_files = [
        governance_contract,
        ledger_contract,
        worklist_schema,
        decision_schema,
        review_schema,
        gate_schema,
        ledger_schema,
    ]
    missing = [str(p.relative_to(ROOT)) for p in required_files if not p.exists()]
    if missing:
        print("[formalization-schema-policy][FAIL] missing required files:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 2

    bad = 0

    missing_gov = _require_snippets(
        governance_contract,
        [
            "Canonical completion states",
            "TRIAGED_UNPROVABLE_CANDIDATE",
            "REVIEW_RUN",
            "REVIEW_SKIPPED",
            "Formalization gate",
            "Mapping gate",
        ],
    )
    if missing_gov:
        print("[formalization-schema-policy][FAIL] governance contract missing snippets:", file=sys.stderr)
        for s in missing_gov:
            print(f"  - {s}", file=sys.stderr)
        bad += 1

    missing_ledger = _require_snippets(
        ledger_contract,
        [
            "adapters MAY read experimental v0.2/v0.3/v0.4",
            "Mapping from experimental ledger v0.2",
            "Mapping from experimental ledger v0.3",
            "Mapping from experimental ledger v0.4",
            "claim_proof_links",
            "formalization_bindings",
        ],
    )
    if missing_ledger:
        print("[formalization-schema-policy][FAIL] ledger contract missing snippets:", file=sys.stderr)
        for s in missing_ledger:
            print(f"  - {s}", file=sys.stderr)
        bad += 1

    worklist = _load_json(worklist_schema)
    decision = _load_json(decision_schema)
    review = _load_json(review_schema)
    gate = _load_json(gate_schema)
    ledger = _load_json(ledger_schema)

    completion_states = [
        "NEW",
        "CODEX_ATTEMPTED",
        "GPT52PRO_ESCALATED",
        "TRIAGED_UNPROVABLE_CANDIDATE",
        "COMPLETED",
    ]

    worklist_enum = worklist["$defs"]["item"]["properties"]["state"].get("enum")
    if worklist_enum != completion_states:
        return _fail("ProofCompletionWorklist.item.state enum drifted from canonical completion states")

    decision_from_enum = decision["$defs"]["decision"]["properties"]["from"].get("enum")
    decision_to_enum = decision["$defs"]["decision"]["properties"]["to"].get("enum")
    if decision_from_enum != completion_states or decision_to_enum != completion_states:
        return _fail("ProofCompletionDecisionApplyReport.from/to enums drifted from canonical completion states")

    review_required = set(review.get("required", []))
    if "review_closeout" not in review_required:
        return _fail("AgentFidelityReview must require review_closeout")
    if "prompt_ref" in review_required or "response_ref" in review_required:
        return _fail("AgentFidelityReview must not require top-level prompt_ref/response_ref")

    closeout_run = review["$defs"]["closeoutRun"]
    closeout_skip = review["$defs"]["closeoutSkipped"]
    closeout_run_req = set(closeout_run.get("required", []))
    closeout_skip_req = set(closeout_skip.get("required", []))
    if closeout_run["properties"]["mode"].get("const") != "REVIEW_RUN":
        return _fail("AgentFidelityReview.closeoutRun.mode must be const REVIEW_RUN")
    if closeout_skip["properties"]["mode"].get("const") != "REVIEW_SKIPPED":
        return _fail("AgentFidelityReview.closeoutSkipped.mode must be const REVIEW_SKIPPED")
    for f in ("mode", "prompt_ref", "response_ref", "evidence_refs"):
        if f not in closeout_run_req:
            return _fail(f"AgentFidelityReview.closeoutRun missing required `{f}`")
    for f in ("mode", "skip_reason_code", "evidence_refs"):
        if f not in closeout_skip_req:
            return _fail(f"AgentFidelityReview.closeoutSkipped missing required `{f}`")

    gate_required = set(gate.get("required", []))
    for req in ("formalization_gate", "mapping_gate", "gate_pass", "issues", "checks", "counts"):
        if req not in gate_required:
            return _fail(f"FormalizationGateReport missing required `{req}`")
    gate_sub_required = set(gate["$defs"]["gate"].get("required", []))
    for req in ("pass", "checks", "counts", "issues"):
        if req not in gate_sub_required:
            return _fail(f"FormalizationGateReport.$defs.gate missing required `{req}`")
    if len(gate.get("allOf", [])) < 2:
        return _fail("FormalizationGateReport must enforce gate_pass consistency via allOf rules")

    ledger_required = set(ledger.get("required", []))
    for req in (
        "ledger_meta",
        "review_workflow",
        "source_spans",
        "claims",
        "proofs",
        "external_results",
        "claim_proof_links",
        "formalization_bindings",
        "lean_reverse_links",
        "clause_atoms",
        "lean_anchors",
        "atom_mappings",
        "index",
        "audit",
    ):
        if req not in ledger_required:
            return _fail(f"FormalizationLedger missing top-level required `{req}`")

    claim_req = set(ledger["$defs"]["claim"].get("required", []))
    link_req = set(ledger["$defs"]["claimProofLink"].get("required", []))
    binding_req = set(ledger["$defs"]["formalizationBinding"].get("required", []))
    proof_req = set(ledger["$defs"]["proof"].get("required", []))
    review_req = set(ledger["$defs"]["review"].get("required", []))
    review_state_enum = ledger["$defs"]["review"]["properties"]["state"].get("enum", [])

    for req in ("dependency_ids",):
        if req not in claim_req:
            return _fail(f"FormalizationLedger.claim missing required `{req}`")
    for req in ("confidence", "evidence_span_ids"):
        if req not in link_req:
            return _fail(f"FormalizationLedger.claimProofLink missing required `{req}`")
    for req in ("external_dependency_result_ids", "external_dependency_status", "lean_target"):
        if req not in binding_req:
            return _fail(f"FormalizationLedger.formalizationBinding missing required `{req}`")
    for req in ("body_span_ids", "uses_external_result_ids", "uses_internal_claim_ids"):
        if req not in proof_req:
            return _fail(f"FormalizationLedger.proof missing required `{req}`")
    for req in ("state", "confidence", "uncertainty_score", "last_updated_utc", "reviewer", "note"):
        if req not in review_req:
            return _fail(f"FormalizationLedger.review missing required `{req}`")

    expected_review_states = [
        "AUTO_EXTRACTED",
        "NEEDS_REVIEW",
        "HUMAN_CONFIRMED",
        "HUMAN_EDITED",
        "HUMAN_REJECTED",
        "LOCKED",
    ]
    if review_state_enum != expected_review_states:
        return _fail("FormalizationLedger.review.state enum drifted from contract")

    if bad:
        return 2

    print("[formalization-schema-policy] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
