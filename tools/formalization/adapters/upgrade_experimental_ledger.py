#!/usr/bin/env python3
"""Upgrade experimental theorem/proof ledgers into canonical FormalizationLedger shape."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REVIEW_STATES = {
    "AUTO_EXTRACTED",
    "NEEDS_REVIEW",
    "HUMAN_CONFIRMED",
    "HUMAN_EDITED",
    "HUMAN_REJECTED",
    "LOCKED",
}

DEFAULT_FALLBACK_REVIEW_TS = "1970-01-01T00:00:00Z"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize(text: str) -> str:
    return " ".join(str(text).strip().split())


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(text).strip().lower())
    s = s.strip("_")
    return s or "item"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fallback_review(*, confidence: float = 0.6, note: str = "auto-filled by upgrade adapter") -> dict[str, Any]:
    c = clamp01(confidence)
    state = "AUTO_EXTRACTED" if c >= 0.78 else "NEEDS_REVIEW"
    return {
        "state": state,
        "confidence": round(c, 4),
        "uncertainty_score": round(clamp01(1.0 - c), 4),
        "last_updated_utc": DEFAULT_FALLBACK_REVIEW_TS,
        "reviewer": None,
        "note": note,
    }


def _normalize_review(raw: Any, *, default_confidence: float, note: str) -> dict[str, Any]:
    obj = raw if isinstance(raw, dict) else {}
    out = _fallback_review(confidence=default_confidence, note=note)

    state = str(obj.get("state", "")).strip().upper()
    if state in REVIEW_STATES:
        out["state"] = state

    try:
        out["confidence"] = round(clamp01(float(obj.get("confidence", out["confidence"]))), 4)
    except Exception:
        pass
    try:
        out["uncertainty_score"] = round(clamp01(float(obj.get("uncertainty_score", 1.0 - out["confidence"]))), 4)
    except Exception:
        out["uncertainty_score"] = round(clamp01(1.0 - out["confidence"]), 4)

    ts = str(obj.get("last_updated_utc", "")).strip()
    if ts:
        out["last_updated_utc"] = ts

    reviewer = obj.get("reviewer")
    out["reviewer"] = reviewer if (isinstance(reviewer, str) and reviewer.strip()) else None
    note_val = str(obj.get("note", "")).strip()
    if note_val:
        out["note"] = note_val
    return out


def _ensure_list(raw: Any) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _ensure_dict(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_sha256(raw: Any, text_fallback: str) -> str:
    candidate = str(raw).strip().lower()
    if re.fullmatch(r"[a-f0-9]{64}", candidate):
        return candidate
    return _sha256_text(text_fallback)


def _normalize_optional_span_id(raw: Any) -> str | None:
    if isinstance(raw, str):
        s = raw.strip()
        return s or None
    return None


def _normalize_page_number(raw: Any) -> int:
    try:
        value = int(raw)
    except Exception:
        return 1
    return max(1, value)


def _normalize_claims(claims: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, raw in enumerate(claims, start=1):
        if not isinstance(raw, dict):
            continue
        claim_id = str(raw.get("claim_id", "")).strip() or f"claim.{idx}"
        out.append(
            {
                "claim_id": claim_id,
                "claim_kind": str(raw.get("claim_kind", "CLAIM")),
                "display_label": str(raw.get("display_label", claim_id)),
                "number": str(raw.get("number", "")),
                "section_title": str(raw.get("section_title", "")),
                "heading_span_id": _normalize_optional_span_id(raw.get("heading_span_id")),
                "dependency_ids": [str(x).strip() for x in _ensure_list(raw.get("dependency_ids")) if str(x).strip()],
                "in_paper_proof_status": str(raw.get("in_paper_proof_status", "UNKNOWN")),
                "statement_span_ids": [str(x).strip() for x in _ensure_list(raw.get("statement_span_ids")) if str(x).strip()] or [f"autospan.claim.{idx}"],
                "review": _normalize_review(raw.get("review"), default_confidence=0.75, note="claim review normalized by upgrade adapter"),
            }
        )
    out.sort(key=lambda x: x["claim_id"])
    return out


def _normalize_proofs(proofs: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, raw in enumerate(proofs, start=1):
        if not isinstance(raw, dict):
            continue
        proof_id = str(raw.get("proof_id", "")).strip() or f"proof.{idx}"
        for_claim_ids = [str(x).strip() for x in _ensure_list(raw.get("for_claim_ids")) if str(x).strip()]
        if not for_claim_ids:
            for_claim_ids = [f"claim.autogen.{idx}"]
        out.append(
            {
                "proof_id": proof_id,
                "proof_type": str(raw.get("proof_type", "PROOF")),
                "proof_label": str(raw.get("proof_label", proof_id)),
                "proof_heading_span_id": _normalize_optional_span_id(raw.get("proof_heading_span_id")),
                "completeness": str(raw.get("completeness", "UNKNOWN")),
                "for_claim_ids": for_claim_ids,
                "body_span_ids": [str(x).strip() for x in _ensure_list(raw.get("body_span_ids")) if str(x).strip()] or [f"autospan.proof.{idx}"],
                "uses_internal_claim_ids": [str(x).strip() for x in _ensure_list(raw.get("uses_internal_claim_ids")) if str(x).strip()],
                "uses_external_result_ids": [str(x).strip() for x in _ensure_list(raw.get("uses_external_result_ids")) if str(x).strip()],
                "review": _normalize_review(raw.get("review"), default_confidence=0.65, note="proof review normalized by upgrade adapter"),
            }
        )
    out.sort(key=lambda x: x["proof_id"])
    return out


def _normalize_external_results(results: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, raw in enumerate(results, start=1):
        if not isinstance(raw, dict):
            continue
        ext_id = str(raw.get("external_result_id", "")).strip() or f"external.{idx}"
        out.append(
            {
                "external_result_id": ext_id,
                "name": str(raw.get("name", ext_id)),
                "source_kind": str(raw.get("source_kind", "UNKNOWN")),
                "usage_span_ids": [str(x).strip() for x in _ensure_list(raw.get("usage_span_ids")) if str(x).strip()],
                "used_by_claim_ids": [str(x).strip() for x in _ensure_list(raw.get("used_by_claim_ids")) if str(x).strip()],
                "dependency_status": str(raw.get("dependency_status", "UNRESOLVED")),
                "review": _normalize_review(raw.get("review"), default_confidence=0.6, note="external result review normalized by upgrade adapter"),
            }
        )
    out.sort(key=lambda x: x["external_result_id"])
    return out


def _normalize_claim_proof_links(links: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, raw in enumerate(links, start=1):
        if not isinstance(raw, dict):
            continue
        link_id = str(raw.get("link_id", "")).strip() or f"link.{idx}"
        conf = raw.get("confidence", 0.5)
        try:
            conf_f = round(clamp01(float(conf)), 4)
        except Exception:
            conf_f = 0.5
        out.append(
            {
                "link_id": link_id,
                "claim_id": str(raw.get("claim_id", "")),
                "proof_id": str(raw.get("proof_id", "")),
                "link_type": str(raw.get("link_type", "UNSPECIFIED")),
                "confidence": conf_f,
                "evidence_span_ids": [str(x).strip() for x in _ensure_list(raw.get("evidence_span_ids")) if str(x).strip()],
                "notes": str(raw.get("notes", "")),
                "review": _normalize_review(raw.get("review"), default_confidence=conf_f, note="claim_proof_link review normalized by upgrade adapter"),
            }
        )
    out.sort(key=lambda x: x["link_id"])
    return out


def _map_external_dependency_status(binding: dict[str, Any]) -> str:
    explicit = str(binding.get("external_dependency_status", "")).strip()
    if explicit:
        return explicit
    legacy = binding.get("external_dependency_formalized")
    if isinstance(legacy, bool):
        return "FORMALIZED" if legacy else "UNRESOLVED"
    ext_ids = [str(x).strip() for x in _ensure_list(binding.get("external_dependency_result_ids")) if str(x).strip()]
    return "UNRESOLVED" if ext_ids else "NONE"


def _normalize_formalization_bindings(bindings: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, raw in enumerate(bindings, start=1):
        if not isinstance(raw, dict):
            continue
        binding_id = str(raw.get("binding_id", "")).strip() or f"binding.{idx}"
        ext_ids = [str(x).strip() for x in _ensure_list(raw.get("external_dependency_result_ids")) if str(x).strip()]
        lean_target = _ensure_dict(raw.get("lean_target"))
        out.append(
            {
                "binding_id": binding_id,
                "claim_id": str(raw.get("claim_id", "")),
                "clause_links": [x for x in _ensure_list(raw.get("clause_links")) if isinstance(x, dict)],
                "external_dependency_result_ids": ext_ids,
                "external_dependency_status": _map_external_dependency_status(raw),
                "formalization_status": str(raw.get("formalization_status", "UNKNOWN")),
                "lean_target": dict(lean_target),
                "notes": str(raw.get("notes", "")),
                "review": _normalize_review(raw.get("review"), default_confidence=0.6, note="formalization binding review normalized by upgrade adapter"),
            }
        )
    out.sort(key=lambda x: x["binding_id"])
    return out


def _normalize_lean_reverse_links(reverse_links: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, raw in enumerate(reverse_links, start=1):
        if not isinstance(raw, dict):
            continue
        rid = str(raw.get("reverse_link_id", "")).strip() or f"reverse.{idx}"
        out.append(
            {
                "reverse_link_id": rid,
                "lean_ref": dict(_ensure_dict(raw.get("lean_ref"))),
                "target": dict(_ensure_dict(raw.get("target"))),
                "link_origin": str(raw.get("link_origin", "")),
                "notes": str(raw.get("notes", "")),
                "review": _normalize_review(raw.get("review"), default_confidence=0.55, note="reverse link review normalized by upgrade adapter"),
            }
        )
    out.sort(key=lambda x: x["reverse_link_id"])
    return out


def _materialize_clause_atoms(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    seq = 0
    for binding in bindings:
        claim_id = str(binding.get("claim_id", "")).strip()
        for clause in _ensure_list(binding.get("clause_links")):
            if not isinstance(clause, dict):
                continue
            seq += 1
            clause_id = str(clause.get("clause_id", "")).strip() or f"clause.{seq}"
            span_id = str(clause.get("clause_span_id", "")).strip() or f"autospan.clause.{seq}"
            text = str(clause.get("raw_clause_text", clause.get("lean_fragment", ""))).strip() or f"auto clause {seq}"
            role = str(clause.get("mapping_type", "GENERAL")).strip() or "GENERAL"
            atom_id = f"atom.{slugify(clause_id)}.{seq}"
            atoms.append(
                {
                    "atom_id": atom_id,
                    "parent_clause_id": clause_id,
                    "claim_id": claim_id,
                    "span_id": span_id,
                    "text": text,
                    "logic_role": role,
                    "alignment_hint": str(clause.get("lean_fragment", "")),
                    "source": "AUTO_FROM_CLAUSE_LINK",
                    "review": _normalize_review(clause.get("review"), default_confidence=0.5, note="clause atom materialized from clause_links"),
                    "notes": f"derived from binding_id={binding.get('binding_id', '')}",
                }
            )
    atoms.sort(key=lambda x: x["atom_id"])
    return atoms


def _materialize_lean_anchors(reverse_links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for idx, rev in enumerate(reverse_links, start=1):
        target = _ensure_dict(rev.get("target"))
        clause_id_raw = target.get("clause_id")
        clause_id = str(clause_id_raw) if isinstance(clause_id_raw, str) else None
        anchors.append(
            {
                "anchor_id": f"anchor.{idx}",
                "origin": "AUTO_FROM_REVERSE_LINK",
                "anchor_role": "DECL_POINT",
                "claim_id": str(target.get("claim_id", "")),
                "clause_id": clause_id,
                "span_id": str(target.get("span_id", "")),
                "lean_ref": dict(_ensure_dict(rev.get("lean_ref"))),
                "review": _normalize_review(rev.get("review"), default_confidence=0.55, note="lean anchor materialized from reverse links"),
                "notes": f"derived from reverse_link_id={rev.get('reverse_link_id', '')}",
            }
        )
    anchors.sort(key=lambda x: x["anchor_id"])
    return anchors


def _materialize_atom_mappings(atoms: list[dict[str, Any]], anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    by_claim_clause: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
    for anchor in anchors:
        key = (str(anchor.get("claim_id", "")), anchor.get("clause_id"))
        by_claim_clause.setdefault(key, []).append(anchor)

    seq = 0
    for atom in atoms:
        seq += 1
        key = (str(atom.get("claim_id", "")), atom.get("parent_clause_id"))
        candidates = by_claim_clause.get(key, [])
        if not candidates:
            candidates = by_claim_clause.get((str(atom.get("claim_id", "")), None), [])
        chosen = candidates[0] if candidates else None
        if chosen is None:
            continue

        atom_conf = float(_ensure_dict(atom.get("review")).get("confidence", 0.5))
        anchor_conf = float(_ensure_dict(chosen.get("review")).get("confidence", 0.5))
        conf = round(clamp01(min(atom_conf, anchor_conf)), 4)

        mappings.append(
            {
                "mapping_id": f"map.{seq}",
                "atom_id": str(atom.get("atom_id", "")),
                "anchor_id": str(chosen.get("anchor_id", "")),
                "relation": "EXACT",
                "mismatch_kind": "NONE",
                "confidence": conf,
                "evidence": [
                    str(atom.get("span_id", "")),
                    str(chosen.get("span_id", "")),
                ],
                "review": _normalize_review(atom.get("review"), default_confidence=conf, note="atom mapping materialized by upgrade adapter"),
                "notes": "auto-generated mapping",
            }
        )
    mappings.sort(key=lambda x: x["mapping_id"])
    return mappings


def _normalize_source_spans(raw_spans: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, raw in enumerate(raw_spans, start=1):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text", ""))
        entry = {
            "span_id": str(raw.get("span_id", "")).strip() or f"span.{idx}",
            "page": _normalize_page_number(raw.get("page", 1)),
            "role": str(raw.get("role", "UNKNOWN")),
            "text_sha256": _normalize_sha256(raw.get("text_sha256", ""), text),
            "source_file": str(raw.get("source_file", "")),
            "text_snippet": str(raw.get("text_snippet", text)),
        }
        for key in ("line_start", "line_end", "anchor_start", "anchor_end"):
            value = raw.get(key)
            if isinstance(value, int):
                entry[key] = value
        out.append(entry)
    out.sort(key=lambda x: x["span_id"])
    return out


def _normalize_review_workflow(raw: Any) -> dict[str, Any]:
    workflow = _ensure_dict(raw)
    states = [str(x).strip() for x in _ensure_list(workflow.get("states")) if str(x).strip()]
    if not states:
        states = sorted(REVIEW_STATES)
    return {
        "workflow_version": str(workflow.get("workflow_version", "0.1")),
        "states": states,
        "transitions": [x for x in _ensure_list(workflow.get("transitions")) if isinstance(x, dict)],
        "thresholds": _ensure_dict(workflow.get("thresholds")),
    }


def _normalize_index(raw: Any) -> dict[str, Any]:
    idx = _ensure_dict(raw)
    tokens: list[str] = []
    for entry in _ensure_list(idx.get("tokens")):
        if isinstance(entry, str):
            val = entry.strip()
            if val:
                tokens.append(val)
            continue
        if isinstance(entry, dict):
            token_val = str(entry.get("token", "")).strip()
            if token_val:
                tokens.append(token_val)
            continue
        val = str(entry).strip()
        if val:
            tokens.append(val)
    return {
        "by_kind": _ensure_dict(idx.get("by_kind")),
        "by_section": _ensure_dict(idx.get("by_section")),
        "tokens": tokens,
    }


def _normalize_clause_atoms_existing(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(items, start=1):
        atom_id = str(raw.get("atom_id", "")).strip() or f"atom.{i}"
        claim_id = str(raw.get("claim_id", "")).strip()
        logic_role = str(raw.get("logic_role", "GENERAL")).strip() or "GENERAL"
        span_id = str(raw.get("span_id", "")).strip() or f"autospan.atom.{i}"
        text = str(raw.get("text", "")).strip() or f"auto atom {i}"
        parent_clause_raw = raw.get("parent_clause_id")
        parent_clause = str(parent_clause_raw) if isinstance(parent_clause_raw, str) else None
        entry = {
            "atom_id": atom_id,
            "parent_clause_id": parent_clause,
            "claim_id": claim_id,
            "span_id": span_id,
            "text": text,
            "logic_role": logic_role,
            "alignment_hint": str(raw.get("alignment_hint", "")),
            "source": str(raw.get("source", "AUTO_NORMALIZED")),
            "review": _normalize_review(raw.get("review"), default_confidence=0.55, note="normalized clause atom review"),
            "notes": str(raw.get("notes", "")),
        }
        out.append(entry)
    out.sort(key=lambda x: x["atom_id"])
    return out


def _normalize_lean_anchors_existing(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(items, start=1):
        anchor_id = str(raw.get("anchor_id", "")).strip() or f"anchor.{i}"
        clause_id_raw = raw.get("clause_id")
        clause_id = str(clause_id_raw) if isinstance(clause_id_raw, str) else None
        entry = {
            "anchor_id": anchor_id,
            "anchor_role": str(raw.get("anchor_role", "DECL_POINT")),
            "origin": str(raw.get("origin", "AUTO_NORMALIZED")),
            "claim_id": str(raw.get("claim_id", "")),
            "clause_id": clause_id,
            "span_id": str(raw.get("span_id", "")),
            "lean_ref": dict(_ensure_dict(raw.get("lean_ref"))),
            "review": _normalize_review(raw.get("review"), default_confidence=0.55, note="normalized lean anchor review"),
            "notes": str(raw.get("notes", "")),
        }
        out.append(entry)
    out.sort(key=lambda x: x["anchor_id"])
    return out


def _normalize_atom_mappings_existing(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(items, start=1):
        mapping_id = str(raw.get("mapping_id", "")).strip() or f"map.{i}"
        conf_raw = raw.get("confidence", 0.55)
        try:
            confidence = round(clamp01(float(conf_raw)), 4)
        except Exception:
            confidence = 0.55
        evidence: list[str] = []
        for e in _ensure_list(raw.get("evidence")):
            if isinstance(e, str):
                if e.strip():
                    evidence.append(e.strip())
            elif isinstance(e, dict):
                # Keep deterministic, schema-valid compressed evidence.
                for key in ("span_id", "clause_id", "claim_id", "binding_id"):
                    val = str(e.get(key, "")).strip()
                    if val:
                        evidence.append(val)
            else:
                val = str(e).strip()
                if val:
                    evidence.append(val)
        mismatch_raw = raw.get("mismatch_kind")
        mismatch_kind = str(mismatch_raw) if isinstance(mismatch_raw, str) else None
        entry = {
            "mapping_id": mapping_id,
            "atom_id": str(raw.get("atom_id", "")),
            "anchor_id": str(raw.get("anchor_id", "")),
            "relation": str(raw.get("relation", "EXACT")),
            "mismatch_kind": mismatch_kind,
            "confidence": confidence,
            "evidence": evidence,
            "review": _normalize_review(raw.get("review"), default_confidence=confidence, note="normalized atom mapping review"),
            "notes": str(raw.get("notes", "")),
        }
        out.append(entry)
    out.sort(key=lambda x: x["mapping_id"])
    return out


def _normalize_audit(raw: Any) -> dict[str, Any]:
    audit = _ensure_dict(raw)
    return {
        "coverage": _ensure_dict(audit.get("coverage")),
        "notes": [str(x) for x in _ensure_list(audit.get("notes"))],
    }


def _normalize_ledger_meta(raw: Any) -> dict[str, Any]:
    meta = _ensure_dict(raw)
    return {
        "ledger_schema_version": "0.1",
        "canonical_json": bool(meta.get("canonical_json", True)),
        "doc": _ensure_dict(meta.get("doc")),
        "extraction_pipeline": _ensure_dict(meta.get("extraction_pipeline")),
        "id_policy": _ensure_dict(meta.get("id_policy")),
    }


def upgrade_ledger(experimental_ledger: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    src = copy.deepcopy(experimental_ledger)

    known_top = {
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
    }
    dropped_top = [k for k in src.keys() if k not in known_top]

    claims = _normalize_claims(_ensure_list(src.get("claims")))
    proofs = _normalize_proofs(_ensure_list(src.get("proofs")))
    external_results = _normalize_external_results(_ensure_list(src.get("external_results")))
    claim_proof_links = _normalize_claim_proof_links(_ensure_list(src.get("claim_proof_links")))
    bindings = _normalize_formalization_bindings(_ensure_list(src.get("formalization_bindings")))
    reverse_links = _normalize_lean_reverse_links(_ensure_list(src.get("lean_reverse_links")))

    raw_clause_atoms = [x for x in _ensure_list(src.get("clause_atoms")) if isinstance(x, dict)]
    if not raw_clause_atoms:
        clause_atoms = _materialize_clause_atoms(bindings)
    else:
        clause_atoms = _normalize_clause_atoms_existing(raw_clause_atoms)

    raw_lean_anchors = [x for x in _ensure_list(src.get("lean_anchors")) if isinstance(x, dict)]
    if not raw_lean_anchors:
        lean_anchors = _materialize_lean_anchors(reverse_links)
    else:
        lean_anchors = _normalize_lean_anchors_existing(raw_lean_anchors)

    raw_atom_mappings = [x for x in _ensure_list(src.get("atom_mappings")) if isinstance(x, dict)]
    if not raw_atom_mappings:
        atom_mappings = _materialize_atom_mappings(clause_atoms, lean_anchors)
    else:
        atom_mappings = _normalize_atom_mappings_existing(raw_atom_mappings)

    out = {
        "ledger_meta": _normalize_ledger_meta(src.get("ledger_meta")),
        "review_workflow": _normalize_review_workflow(src.get("review_workflow")),
        "source_spans": _normalize_source_spans(_ensure_list(src.get("source_spans"))),
        "claims": claims,
        "proofs": proofs,
        "external_results": external_results,
        "claim_proof_links": claim_proof_links,
        "formalization_bindings": bindings,
        "lean_reverse_links": reverse_links,
        "clause_atoms": clause_atoms,
        "lean_anchors": lean_anchors,
        "atom_mappings": atom_mappings,
        "index": _normalize_index(src.get("index")),
        "audit": _normalize_audit(src.get("audit")),
    }

    out["index"]["by_kind"].setdefault("claims", [x["claim_id"] for x in claims])
    out["index"]["by_kind"].setdefault("proofs", [x["proof_id"] for x in proofs])
    out["index"]["by_kind"].setdefault("external_results", [x["external_result_id"] for x in external_results])
    out["index"]["by_kind"].setdefault("clause_atoms", [x.get("atom_id", "") for x in clause_atoms])
    out["index"]["by_kind"].setdefault("lean_anchors", [x.get("anchor_id", "") for x in lean_anchors])
    out["index"]["by_kind"].setdefault("atom_mappings", [x.get("mapping_id", "") for x in atom_mappings])

    if not out["source_spans"]:
        out["source_spans"].append(
            {
                "span_id": "span.autogen.1",
                "page": 1,
                "role": "AUTOGEN",
                "text_sha256": _sha256_text(""),
                "source_file": "",
                "text_snippet": "",
            }
        )

    mismatch_counter = Counter(str(x.get("mismatch_kind", "NONE")) for x in atom_mappings)
    relation_counter = Counter(str(x.get("relation", "EXACT")) for x in atom_mappings)
    report = {
        "generated_at_utc": utc_now_iso(),
        "schema_version": "0.1",
        "counts": {
            "claims": len(claims),
            "proofs": len(proofs),
            "external_results": len(external_results),
            "clause_atoms": len(clause_atoms),
            "lean_anchors": len(lean_anchors),
            "atom_mappings": len(atom_mappings),
        },
        "mismatch_kind_counts": dict(sorted(mismatch_counter.items())),
        "relation_counts": dict(sorted(relation_counter.items())),
        "dropped_top_level_keys": sorted(dropped_top),
    }
    return out, report


def main() -> None:
    ap = argparse.ArgumentParser(description="Upgrade experimental theorem-proof ledger into FormalizationLedger")
    ap.add_argument("--input-ledger", required=True)
    ap.add_argument("--output-ledger", required=True)
    ap.add_argument("--report-out", default="")
    args = ap.parse_args()

    input_path = Path(args.input_ledger).resolve()
    output_path = Path(args.output_ledger).resolve()
    src = load_json(input_path)

    upgraded, report = upgrade_ledger(src)
    dump_json(output_path, upgraded)
    if args.report_out:
        dump_json(Path(args.report_out).resolve(), report)

    print(
        json.dumps(
            {
                "input": str(input_path),
                "output": str(output_path),
                "counts": report["counts"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
