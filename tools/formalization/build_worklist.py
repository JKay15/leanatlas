#!/usr/bin/env python3
"""Build deterministic proof-completion worklists from FormalizationLedger."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

COMPLETION_STATES = {
    "NEW",
    "CODEX_ATTEMPTED",
    "GPT52PRO_ESCALATED",
    "TRIAGED_UNPROVABLE_CANDIDATE",
    "COMPLETED",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def normalize(text: str) -> str:
    return " ".join(str(text).strip().split())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _review_confidence(entity: dict[str, Any]) -> float:
    review = entity.get("review") if isinstance(entity.get("review"), dict) else {}
    conf = review.get("confidence", 0.5)
    try:
        return clamp01(float(conf))
    except Exception:
        return 0.5


def _review_uncertainty(entity: dict[str, Any], confidence: float) -> float:
    review = entity.get("review") if isinstance(entity.get("review"), dict) else {}
    raw = review.get("uncertainty_score", 1.0 - confidence)
    try:
        return clamp01(float(raw))
    except Exception:
        return clamp01(1.0 - confidence)


def _proof_by_id(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(p.get("proof_id", "")).strip(): p
        for p in ledger.get("proofs", [])
        if isinstance(p, dict) and str(p.get("proof_id", "")).strip()
    }


def _claims_by_id(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(c.get("claim_id", "")).strip(): c
        for c in ledger.get("claims", [])
        if isinstance(c, dict) and str(c.get("claim_id", "")).strip()
    }


def _claim_proof_link_by_claim(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for link in ledger.get("claim_proof_links", []):
        if not isinstance(link, dict):
            continue
        cid = str(link.get("claim_id", "")).strip()
        if cid and cid not in out:
            out[cid] = link
    return out


def _completion_state(binding: dict[str, Any]) -> str:
    for key in ("completion_state", "proof_completion_state", "workflow_state"):
        raw = str(binding.get(key, "")).strip().upper()
        if raw in COMPLETION_STATES:
            return raw
    formalization_status = str(binding.get("formalization_status", "")).strip().upper()
    if formalization_status in {"FORMALIZED", "COMPLETE", "COMPLETED"}:
        return "COMPLETED"
    return "NEW"


def _reason_codes(
    *,
    binding: dict[str, Any],
    claim: dict[str, Any] | None,
    proof: dict[str, Any] | None,
) -> list[str]:
    out: list[str] = []

    fstatus = str(binding.get("formalization_status", "")).strip().upper()
    if fstatus not in {"FORMALIZED", "COMPLETE", "COMPLETED"}:
        out.append("BINDING_NOT_FORMALIZED")

    ext_ids = [str(x).strip() for x in binding.get("external_dependency_result_ids", []) if str(x).strip()]
    ext_status = str(binding.get("external_dependency_status", "")).strip().upper()
    if ext_ids and ext_status not in {"FORMALIZED", "RESOLVED"}:
        out.append("EXTERNAL_DEPENDENCY_PENDING")

    claim_obj = claim or {}
    proof_status = str(claim_obj.get("in_paper_proof_status", "")).strip().upper()
    if proof_status in {"IMPLICIT", "NONE", "OUTLINE", "SKETCH"}:
        out.append(f"PAPER_PROOF_STATUS_{proof_status}")

    if proof is not None and str(proof.get("proof_type", "")).strip().upper() == "IMPLICIT_ARGUMENT":
        out.append("PROOF_OBJECT_IMPLICIT_ARGUMENT")

    lean_target = binding.get("lean_target") if isinstance(binding.get("lean_target"), dict) else {}
    if lean_target and lean_target.get("line") is None:
        out.append("DECLARATION_LINE_MISSING")

    note = normalize(str(binding.get("notes", ""))).lower()
    if "analogous" in note:
        out.append("SOURCE_ONLY_ANALOGOUS_IDEA")
    if "triaged" in note:
        out.append("TRIAGED_NOTE_PRESENT")

    if not out:
        out.append("REVIEW_REQUIRED")
    return sorted(set(out))


def _risk_score(issue_count: int, confidence: float, uncertainty: float) -> float:
    issue_signal = clamp01(float(issue_count) / 5.0)
    confidence_gap = clamp01(1.0 - confidence)
    return round(clamp01(max(uncertainty, issue_signal, confidence_gap)), 4)


def _suggested_action(issue_codes: list[str], state: str) -> str:
    if state == "COMPLETED" and not issue_codes:
        return "NO_ACTION"
    if "EXTERNAL_DEPENDENCY_PENDING" in issue_codes:
        return "RESOLVE_EXTERNAL_DEPENDENCY"
    if any(code.startswith("PAPER_PROOF_STATUS_") for code in issue_codes):
        return "COMPLETE_FORMALIZATION_PROOF"
    if "DECLARATION_LINE_MISSING" in issue_codes:
        return "FIX_LEAN_TARGET"
    if state == "GPT52PRO_ESCALATED":
        return "HUMAN_OR_GPT52PRO_REVIEW"
    return "ATTEMPT_FORMALIZATION"


def build_worklist(
    ledger: dict[str, Any],
    *,
    threshold: float = 0.5,
    focus_entity_types: list[str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    threshold = clamp01(threshold)
    claims_by_id = _claims_by_id(ledger)
    proofs_by_id = _proof_by_id(ledger)
    links_by_claim = _claim_proof_link_by_claim(ledger)

    allowed_types = {x.strip() for x in (focus_entity_types or []) if x.strip()}
    items: list[dict[str, Any]] = []

    for binding in ledger.get("formalization_bindings", []):
        if not isinstance(binding, dict):
            continue
        entity_type = "FORMALIZATION_BINDING"
        if allowed_types and entity_type not in allowed_types:
            continue

        claim_id = str(binding.get("claim_id", "")).strip()
        binding_id = str(binding.get("binding_id", "")).strip()
        entity_id = binding_id or claim_id
        if not entity_id:
            continue

        claim = claims_by_id.get(claim_id)
        link = links_by_claim.get(claim_id, {})
        proof = proofs_by_id.get(str(link.get("proof_id", "")).strip()) if isinstance(link, dict) else None

        issue_codes = _reason_codes(binding=binding, claim=claim, proof=proof)
        issue_count = len(issue_codes)
        confidence = _review_confidence(binding)
        uncertainty = _review_uncertainty(binding, confidence)
        risk_score = _risk_score(issue_count, confidence, uncertainty)
        state = _completion_state(binding)

        include = (issue_count > 0 and risk_score >= threshold) or state != "COMPLETED"
        if not include:
            continue

        ext_ids = [str(x).strip() for x in binding.get("external_dependency_result_ids", []) if str(x).strip()]
        item = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "parent_id": claim_id or None,
            "state": state,
            "confidence": round(confidence, 4),
            "uncertainty_score": round(uncertainty, 4),
            "risk_score": risk_score,
            "issue_codes": issue_codes,
            "issue_count": issue_count,
            "suggested_action": _suggested_action(issue_codes, state),
            "reasons": issue_codes,
            "pointers": {
                "binding_id": binding_id,
                "claim_id": claim_id,
                "proof_id": str(link.get("proof_id", "")).strip() if isinstance(link, dict) else "",
                "external_result_ids": ext_ids,
                "formalization_status": str(binding.get("formalization_status", "")),
                "external_dependency_status": str(binding.get("external_dependency_status", "")),
            },
        }
        items.append(item)

    items.sort(key=lambda x: (-x["risk_score"], x["entity_type"], x["entity_id"]))
    counts = Counter(x["state"] for x in items)

    return {
        "schema_version": "0.1",
        "generated_at_utc": generated_at_utc or utc_now_iso(),
        "threshold": threshold,
        "focus_entity_types": sorted(allowed_types) if allowed_types else [],
        "params": {
            "source": "tools.formalization.build_worklist",
            "ledger_schema_version": str(ledger.get("ledger_meta", {}).get("ledger_schema_version", "")),
        },
        "count": len(items),
        "counts": dict(sorted(counts.items())),
        "items": items,
    }


def _parse_focus_types(raw: str) -> list[str]:
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description="Build proof-completion worklist from FormalizationLedger")
    ap.add_argument("--ledger", required=True, help="input FormalizationLedger JSON")
    ap.add_argument("--output", required=True, help="output ProofCompletionWorklist JSON")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--focus-entity-types", default="", help="comma-separated entity types")
    args = ap.parse_args()

    ledger_path = Path(args.ledger).resolve()
    output_path = Path(args.output).resolve()
    ledger = load_json(ledger_path)
    worklist = build_worklist(
        ledger,
        threshold=float(args.threshold),
        focus_entity_types=_parse_focus_types(args.focus_entity_types),
    )
    dump_json(output_path, worklist)
    print(json.dumps({"output": str(output_path), "count": worklist["count"]}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
