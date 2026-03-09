#!/usr/bin/env python3
"""Deterministic formalization mapping triage / review todo builder."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

SUPPORTED_FOCUS = {"ATOM_MAPPING", "LEAN_ANCHOR", "CLAUSE_ATOM"}

STATE_WEIGHT = {
    "NEEDS_REVIEW": 0.50,
    "AUTO_EXTRACTED": 0.30,
    "HUMAN_EDITED": 0.16,
    "HUMAN_CONFIRMED": 0.06,
    "HUMAN_REJECTED": 0.12,
    "LOCKED": -1.0,
}

SEVERITY_WEIGHT = {"ERROR": 1.0, "WARN": 0.30, "INFO": 0.08}

ISSUE_CODE_BONUS = {
    "TEMPLATE_REGEX_UNSAT": 0.35,
    "UNREFERENCED_ANCHOR": 0.40,
    "UNMAPPED_ATOM": 0.40,
    "MAPPING_RELATION_MISMATCH_KIND_CONFLICT": 0.35,
    "MAPPING_ANCHOR_MISSING": 0.80,
    "MAPPING_ATOM_MISSING": 0.80,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def normalize(text: Any) -> str:
    return " ".join(str(text).strip().split())


def optional_id(value: Any) -> str | None:
    if value is None:
        return None
    text = normalize(value)
    return text or None


def review_of(entity: dict[str, Any]) -> dict[str, Any]:
    review = entity.get("review", {})
    return review if isinstance(review, dict) else {}


def state_of(entity: dict[str, Any]) -> str:
    return str(review_of(entity).get("state", "NEEDS_REVIEW"))


def confidence_of(entity: dict[str, Any]) -> float:
    try:
        return float(review_of(entity).get("confidence", 0.0))
    except Exception:
        return 0.0


def uncertainty_of(entity: dict[str, Any]) -> float:
    try:
        return float(review_of(entity).get("uncertainty_score", 1.0))
    except Exception:
        return 1.0


def normalize_mismatch_kind(value: Any) -> str | None:
    if value is None:
        return None
    text = normalize(value)
    if not text:
        return None
    return "NONE" if text.upper() == "NONE" else text


def binding_ids_by_clause(ledger: dict[str, Any]) -> dict[str, list[str]]:
    by_clause: dict[str, list[str]] = defaultdict(list)
    for binding in ledger.get("formalization_bindings", []):
        if not isinstance(binding, dict):
            continue
        binding_id = optional_id(binding.get("binding_id"))
        if not binding_id:
            continue
        for clause in binding.get("clause_links", []):
            if not isinstance(clause, dict):
                continue
            clause_id = optional_id(clause.get("clause_id"))
            if not clause_id:
                continue
            if binding_id not in by_clause[clause_id]:
                by_clause[clause_id].append(binding_id)
    return {clause_id: sorted(binding_ids) for clause_id, binding_ids in by_clause.items()}


def unambiguous_binding_id(binding_ids_for_clause: dict[str, list[str]], clause_id: str | None) -> str | None:
    if not clause_id:
        return None
    binding_ids = binding_ids_for_clause.get(clause_id, [])
    if len(binding_ids) != 1:
        return None
    return binding_ids[0]


def mapping_context(
    *,
    mapping: dict[str, Any],
    atom_by_id: dict[str, dict[str, Any]],
    anchor_by_id: dict[str, dict[str, Any]],
    binding_ids_for_clause: dict[str, list[str]],
) -> dict[str, Any]:
    atom_id = str(mapping.get("atom_id", ""))
    anchor_id = str(mapping.get("anchor_id", ""))
    atom = atom_by_id.get(atom_id, {})
    anchor = anchor_by_id.get(anchor_id, {})
    evidence = mapping.get("evidence", [])
    claim_id = optional_id(anchor.get("claim_id")) or optional_id(atom.get("claim_id"))
    clause_id = optional_id(anchor.get("clause_id")) or optional_id(atom.get("parent_clause_id"))
    span_id = optional_id(anchor.get("span_id")) or optional_id(atom.get("span_id"))
    binding_id = unambiguous_binding_id(binding_ids_for_clause, clause_id)
    if isinstance(evidence, dict):
        claim_id = claim_id or optional_id(evidence.get("claim_id"))
        clause_id = clause_id or optional_id(evidence.get("clause_id"))
        span_id = span_id or optional_id(evidence.get("span_id"))
        binding_id = binding_id or optional_id(evidence.get("binding_id"))
    elif isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, dict):
                claim_id = claim_id or optional_id(item.get("claim_id"))
                clause_id = clause_id or optional_id(item.get("clause_id"))
                span_id = span_id or optional_id(item.get("span_id"))
                binding_id = binding_id or optional_id(item.get("binding_id"))
            elif span_id is None:
                span_id = optional_id(item)
    if clause_id and binding_id is None:
        binding_id = unambiguous_binding_id(binding_ids_for_clause, clause_id)
    return {
        "claim_id": claim_id,
        "clause_id": clause_id,
        "span_id": span_id,
        "binding_id": binding_id,
    }


def collect_issue_refs(
    *,
    consistency_report: dict[str, Any] | None,
    atom_map_by_id: dict[str, dict[str, Any]],
    atom_by_id: dict[str, dict[str, Any]],
    anchor_by_id: dict[str, dict[str, Any]],
    binding_ids_for_clause: dict[str, list[str]],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
]:
    by_mapping: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_anchor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_atom: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_by_mapping: dict[str, set[int]] = defaultdict(set)
    seen_by_anchor: dict[str, set[int]] = defaultdict(set)
    seen_by_atom: dict[str, set[int]] = defaultdict(set)
    if not consistency_report:
        return by_mapping, by_anchor, by_atom

    def add_mapping_issue(mapping_id: str, issue: dict[str, Any]) -> None:
        issue_token = id(issue)
        if issue_token in seen_by_mapping[mapping_id]:
            return
        seen_by_mapping[mapping_id].add(issue_token)
        by_mapping[mapping_id].append(issue)

    def add_anchor_issue(anchor_id: str, issue: dict[str, Any]) -> None:
        issue_token = id(issue)
        if issue_token in seen_by_anchor[anchor_id]:
            return
        seen_by_anchor[anchor_id].add(issue_token)
        by_anchor[anchor_id].append(issue)

    def add_atom_issue(atom_id: str, issue: dict[str, Any]) -> None:
        issue_token = id(issue)
        if issue_token in seen_by_atom[atom_id]:
            return
        seen_by_atom[atom_id].add(issue_token)
        by_atom[atom_id].append(issue)

    mapping_by_clause: dict[str, list[str]] = defaultdict(list)
    mapping_by_binding: dict[str, list[str]] = defaultdict(list)
    mapping_by_atom: dict[str, list[str]] = defaultdict(list)
    for mapping_id, mapping in atom_map_by_id.items():
        context = mapping_context(
            mapping=mapping,
            atom_by_id=atom_by_id,
            anchor_by_id=anchor_by_id,
            binding_ids_for_clause=binding_ids_for_clause,
        )
        clause_id = optional_id(context.get("clause_id"))
        binding_id = optional_id(context.get("binding_id"))
        if clause_id:
            mapping_by_clause[clause_id].append(mapping_id)
        if binding_id:
            mapping_by_binding[binding_id].append(mapping_id)
        mapping_by_atom[str(mapping.get("atom_id", ""))].append(mapping_id)

    anchor_by_clause: dict[str, list[str]] = defaultdict(list)
    anchor_by_claim: dict[str, list[str]] = defaultdict(list)
    atom_by_clause: dict[str, list[str]] = defaultdict(list)
    for anchor_id, anchor in anchor_by_id.items():
        clause_id = optional_id(anchor.get("clause_id"))
        claim_id = optional_id(anchor.get("claim_id"))
        if clause_id:
            anchor_by_clause[clause_id].append(anchor_id)
        if claim_id:
            anchor_by_claim[claim_id].append(anchor_id)
    for atom_id, atom in atom_by_id.items():
        clause_id = optional_id(atom.get("parent_clause_id"))
        if clause_id:
            atom_by_clause[clause_id].append(atom_id)

    for issue in consistency_report.get("issues", []):
        if not isinstance(issue, dict):
            continue
        ref = issue.get("ref", {})
        ref = ref if isinstance(ref, dict) else {}
        mapping_id = optional_id(ref.get("mapping_id")) or ""
        anchor_id = optional_id(ref.get("anchor_id")) or ""
        clause_id = optional_id(ref.get("clause_id")) or ""
        binding_id = optional_id(ref.get("binding_id")) or ""
        claim_id = optional_id(ref.get("claim_id")) or ""
        atom_id = optional_id(ref.get("atom_id")) or ""
        code = str(issue.get("code", ""))

        if mapping_id and mapping_id in atom_map_by_id:
            add_mapping_issue(mapping_id, issue)
        if anchor_id and anchor_id in anchor_by_id:
            add_anchor_issue(anchor_id, issue)
        if binding_id:
            for item in mapping_by_binding.get(binding_id, []):
                add_mapping_issue(item, issue)
        elif clause_id:
            for item in mapping_by_clause.get(clause_id, []):
                add_mapping_issue(item, issue)
        if clause_id:
            for item in anchor_by_clause.get(clause_id, []):
                add_anchor_issue(item, issue)
            for item in atom_by_clause.get(clause_id, []):
                add_atom_issue(item, issue)
        if claim_id:
            for item in anchor_by_claim.get(claim_id, []):
                add_anchor_issue(item, issue)
        if atom_id:
            add_atom_issue(atom_id, issue)
            for item in mapping_by_atom.get(atom_id, []):
                add_mapping_issue(item, issue)
        if code == "UNREFERENCED_ANCHOR" and anchor_id and anchor_id in anchor_by_id:
            add_anchor_issue(anchor_id, issue)

    return by_mapping, by_anchor, by_atom


def issue_risk(issues: list[dict[str, Any]]) -> tuple[float, list[str], Counter]:
    if not issues:
        return 0.0, [], Counter()
    weight = 0.0
    reasons: list[str] = []
    seen_reasons: set[str] = set()
    codes: Counter = Counter()
    for issue in issues:
        severity = str(issue.get("severity", "WARN"))
        code = str(issue.get("code", "UNKNOWN"))
        codes[code] += 1
        weight += SEVERITY_WEIGHT.get(severity, 0.2)
        weight += ISSUE_CODE_BONUS.get(code, 0.0)
        reason = f"{severity}:{code}"
        if reason not in seen_reasons:
            reasons.append(reason)
            seen_reasons.add(reason)
    return weight, reasons, codes


def build_review_todo(
    *,
    ledger: dict[str, Any],
    consistency_report: dict[str, Any] | None,
    focus: list[str],
    min_risk: float,
    top_k: int | None,
    include_locked: bool,
) -> dict[str, Any]:
    focus_set = [item.strip().upper() for item in focus if item.strip()]
    for item in focus_set:
        if item not in SUPPORTED_FOCUS:
            raise ValueError(f"unsupported focus entity type: {item}")
    if not focus_set:
        focus_set = ["ATOM_MAPPING", "LEAN_ANCHOR"]

    threshold = float(ledger.get("review_workflow", {}).get("thresholds", {}).get("auto_extracted_min_confidence", 0.78))
    atom_map_by_id = {
        str(mapping.get("mapping_id", "")): mapping
        for mapping in ledger.get("atom_mappings", [])
        if isinstance(mapping, dict) and str(mapping.get("mapping_id", ""))
    }
    anchor_by_id = {
        str(anchor.get("anchor_id", "")): anchor
        for anchor in ledger.get("lean_anchors", [])
        if isinstance(anchor, dict) and str(anchor.get("anchor_id", ""))
    }
    atom_by_id = {
        str(atom.get("atom_id", "")): atom
        for atom in ledger.get("clause_atoms", [])
        if isinstance(atom, dict) and str(atom.get("atom_id", ""))
    }
    binding_ids_for_clause = binding_ids_by_clause(ledger)
    mapping_issues, anchor_issues, atom_issues = collect_issue_refs(
        consistency_report=consistency_report,
        atom_map_by_id=atom_map_by_id,
        atom_by_id=atom_by_id,
        anchor_by_id=anchor_by_id,
        binding_ids_for_clause=binding_ids_for_clause,
    )

    items: list[dict[str, Any]] = []

    def add_item(item: dict[str, Any]) -> None:
        if item["risk_score"] >= min_risk:
            items.append(item)

    if "ATOM_MAPPING" in focus_set:
        for mapping_id in sorted(atom_map_by_id):
            mapping = atom_map_by_id[mapping_id]
            state = state_of(mapping)
            if state == "LOCKED" and not include_locked:
                continue
            confidence = confidence_of(mapping)
            uncertainty = uncertainty_of(mapping)
            issues = mapping_issues.get(mapping_id, [])
            mismatch_kind = normalize_mismatch_kind(mapping.get("mismatch_kind", "NONE"))
            relation = str(mapping.get("relation", "HEURISTIC"))
            has_mismatch = mismatch_kind not in {None, "NONE"}
            mismatch_bonus = 0.24 if has_mismatch else 0.0
            if relation == "HEURISTIC":
                mismatch_bonus += 0.18
            elif relation in {"IMPLIES", "CONVERSE"}:
                mismatch_bonus += 0.14
            issue_weight, issue_reasons, issue_codes = issue_risk(issues)
            risk = round(
                STATE_WEIGHT.get(state, 0.22)
                + (1.0 - clamp01(confidence)) * 0.68
                + clamp01(uncertainty) * 0.26
                + mismatch_bonus
                + issue_weight,
                4,
            )
            if not issues and state in {"AUTO_EXTRACTED", "HUMAN_CONFIRMED"} and confidence >= threshold and not has_mismatch:
                continue
            context = mapping_context(
                mapping=mapping,
                atom_by_id=atom_by_id,
                anchor_by_id=anchor_by_id,
                binding_ids_for_clause=binding_ids_for_clause,
            )
            atom_id = str(mapping.get("atom_id", ""))
            atom = atom_by_id.get(atom_id, {})
            reasons = [*issue_reasons, f"state={state}", f"relation={relation}"]
            if has_mismatch:
                reasons.append(f"mismatch={mismatch_kind}")
            if confidence < threshold:
                reasons.append(f"low_confidence<{threshold:.2f}")
            add_item(
                {
                    "entity_type": "ATOM_MAPPING",
                    "entity_id": mapping_id,
                    "parent_id": atom_id,
                    "state": state,
                    "confidence": round(confidence, 4),
                    "uncertainty_score": round(uncertainty, 4),
                    "risk_score": risk,
                    "issue_count": len(issues),
                    "issue_codes": dict(sorted(issue_codes.items())),
                    "reasons": reasons,
                    "suggested_action": "verify atom-clause semantics against Lean anchor; refine relation and mismatch if needed",
                    "pointers": {
                        "claim_id": context.get("claim_id"),
                        "clause_id": context.get("clause_id"),
                        "span_id": context.get("span_id"),
                        "binding_id": context.get("binding_id"),
                        "anchor_id": mapping.get("anchor_id"),
                        "mismatch_kind": mismatch_kind,
                        "relation": relation,
                        "atom_text": atom.get("text", ""),
                    },
                }
            )

    if "LEAN_ANCHOR" in focus_set:
        for anchor_id in sorted(anchor_by_id):
            anchor = anchor_by_id[anchor_id]
            state = state_of(anchor)
            if state == "LOCKED" and not include_locked:
                continue
            confidence = confidence_of(anchor)
            uncertainty = uncertainty_of(anchor)
            issues = anchor_issues.get(anchor_id, [])
            issue_weight, issue_reasons, issue_codes = issue_risk(issues)
            origin = str(anchor.get("origin", "AUTO_FROM_REVERSE_LINK"))
            role = str(anchor.get("anchor_role", "DECL_POINT"))
            anchor_bonus = 0.28 if origin == "AUTO_SYNTHETIC_DECL" else 0.0
            if role in {"DECL_SCOPE", "TACTIC_STEP"}:
                anchor_bonus += 0.10
            risk = round(
                STATE_WEIGHT.get(state, 0.22)
                + (1.0 - clamp01(confidence)) * 0.60
                + clamp01(uncertainty) * 0.22
                + anchor_bonus
                + issue_weight,
                4,
            )
            if not issues and state in {"AUTO_EXTRACTED", "HUMAN_CONFIRMED"} and confidence >= threshold:
                continue
            reasons = [*issue_reasons, f"state={state}", f"origin={origin}"]
            if confidence < threshold:
                reasons.append(f"low_confidence<{threshold:.2f}")
            lean_ref = anchor.get("lean_ref", {})
            lean_ref = lean_ref if isinstance(lean_ref, dict) else {}
            add_item(
                {
                    "entity_type": "LEAN_ANCHOR",
                    "entity_id": anchor_id,
                    "parent_id": anchor.get("claim_id"),
                    "state": state,
                    "confidence": round(confidence, 4),
                    "uncertainty_score": round(uncertainty, 4),
                    "risk_score": risk,
                    "issue_count": len(issues),
                    "issue_codes": dict(sorted(issue_codes.items())),
                    "reasons": reasons,
                    "suggested_action": "check anchor location and whether this anchor should participate in atom_mappings",
                    "pointers": {
                        "claim_id": anchor.get("claim_id"),
                        "clause_id": anchor.get("clause_id"),
                        "span_id": anchor.get("span_id"),
                        "origin": origin,
                        "anchor_role": role,
                        "module": lean_ref.get("module"),
                        "file_path": lean_ref.get("file_path"),
                        "declaration_name": lean_ref.get("declaration_name"),
                        "line": lean_ref.get("line"),
                        "column": lean_ref.get("column"),
                    },
                }
            )

    if "CLAUSE_ATOM" in focus_set:
        atoms = [atom for atom in ledger.get("clause_atoms", []) if isinstance(atom, dict)]
        for atom in sorted(atoms, key=lambda item: str(item.get("atom_id", ""))):
            state = state_of(atom)
            if state == "LOCKED" and not include_locked:
                continue
            atom_id = str(atom.get("atom_id", ""))
            confidence = confidence_of(atom)
            uncertainty = uncertainty_of(atom)
            issues = atom_issues.get(atom_id, [])
            issue_weight, issue_reasons, issue_codes = issue_risk(issues)
            risk = round(
                STATE_WEIGHT.get(state, 0.22)
                + (1.0 - clamp01(confidence)) * 0.65
                + clamp01(uncertainty) * 0.24,
                4,
            )
            risk = round(
                risk + issue_weight,
                4,
            )
            if not issues and state in {"AUTO_EXTRACTED", "HUMAN_CONFIRMED"} and confidence >= threshold:
                continue
            reasons = [*issue_reasons, f"state={state}"]
            if confidence < threshold:
                reasons.append(f"low_confidence<{threshold:.2f}")
            add_item(
                {
                    "entity_type": "CLAUSE_ATOM",
                    "entity_id": atom_id,
                    "parent_id": atom.get("claim_id"),
                    "state": state,
                    "confidence": round(confidence, 4),
                    "uncertainty_score": round(uncertainty, 4),
                    "risk_score": risk,
                    "issue_count": len(issues),
                    "issue_codes": dict(sorted(issue_codes.items())),
                    "reasons": reasons,
                    "suggested_action": "review atom wording and logic_role before mapping",
                    "pointers": {
                        "claim_id": atom.get("claim_id"),
                        "clause_id": atom.get("parent_clause_id"),
                        "span_id": atom.get("span_id"),
                        "logic_role": atom.get("logic_role"),
                        "text": atom.get("text") or atom.get("atom_text", ""),
                    },
                }
            )

    items.sort(key=lambda item: (-item["risk_score"], item["confidence"], item["entity_type"], item["entity_id"]))
    if top_k is not None and top_k >= 0:
        items = items[:top_k]

    return {
        "generated_at_utc": utc_now_iso(),
        "schema_version": "formalization.review_todo.v0.1",
        "focus_entity_types": focus_set,
        "threshold": threshold,
        "count": len(items),
        "counts": {
            "by_entity_type": dict(sorted(Counter(item["entity_type"] for item in items).items())),
            "by_state": dict(sorted(Counter(item["state"] for item in items).items())),
        },
        "params": {
            "min_risk": min_risk,
            "top_k": top_k,
            "include_locked": include_locked,
            "has_consistency_report": consistency_report is not None,
        },
        "items": items,
    }
