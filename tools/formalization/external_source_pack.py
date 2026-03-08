#!/usr/bin/env python3
"""Committed mainline ExternalSourcePack builder for formalization ingress."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize(text: Any) -> str:
    return " ".join(str(text).strip().split())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def path_info(path_text: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    path_text = normalize(path_text)
    if not path_text:
        return None
    path = Path(path_text).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = (base_dir / path).expanduser()
    exists = path.exists()
    return {
        "path": str(path.resolve() if exists else path),
        "exists": bool(exists),
        "kind": "directory" if exists and path.is_dir() else "file",
        "sha256": sha256_file(path) if exists and path.is_file() else None,
    }


def _load_user_entries(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    doc = load_json(path)
    raw_entries = doc.get("entries", []) if isinstance(doc, dict) else []
    entries: list[dict[str, str]] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        entries.append(
            {
                "external_result_id": normalize(raw.get("external_result_id", "")),
                "citation_key": normalize(raw.get("citation_key", "")),
                "latex_root": normalize(raw.get("latex_root", "")),
                "pdf_path": normalize(raw.get("pdf_path", "")),
                "note": normalize(raw.get("note", "")),
            }
        )
    return entries


def _collect_claim_usage(ledger: dict[str, Any]) -> dict[str, set[str]]:
    usage: dict[str, set[str]] = defaultdict(set)
    for proof in ledger.get("proofs", []):
        if not isinstance(proof, dict):
            continue
        claim_ids = [normalize(x) for x in proof.get("for_claim_ids", []) if normalize(x)]
        external_ids = [normalize(x) for x in proof.get("uses_external_result_ids", []) if normalize(x)]
        for ext_id in external_ids:
            usage[ext_id].update(claim_ids)
    for binding in ledger.get("formalization_bindings", []):
        if not isinstance(binding, dict):
            continue
        claim_id = normalize(binding.get("claim_id", ""))
        for ext_id in binding.get("external_dependency_result_ids", []):
            ext_norm = normalize(ext_id)
            if ext_norm and claim_id:
                usage[ext_norm].add(claim_id)
    return usage


def _select_material(item: dict[str, Any]) -> dict[str, Any]:
    user_latex = item["materials"]["user_latex_roots"]
    user_pdf = item["materials"]["user_pdfs"]
    for asset in user_latex:
        if asset.get("exists"):
            return {
                "mode": "LATEX_USER",
                "path_or_url": asset.get("path", ""),
                "reason": "user provided LaTeX root",
                "confidence": 0.98,
            }
    for asset in user_pdf:
        if asset.get("exists"):
            return {
                "mode": "PDF_USER",
                "path_or_url": asset.get("path", ""),
                "reason": "user provided PDF",
                "confidence": 0.90,
            }
    if item["discovery"].get("metadata_only_ref"):
        return {
            "mode": "METADATA_ONLY",
            "path_or_url": item["discovery"]["metadata_only_ref"],
            "reason": "metadata available but no local user assets",
            "confidence": 0.45,
        }
    return {
        "mode": "NONE",
        "path_or_url": "",
        "reason": "no explicit user assets or retrieved source material",
        "confidence": 0.0,
    }


def build_external_source_pack(
    ledger: dict[str, Any],
    *,
    ledger_path: Path,
    user_inputs_path: Path | None = None,
    cache_dir: Path | None = None,
    max_queries_per_item: int = 2,
    max_results_per_provider: int = 3,
    min_arxiv_relevance: float = 0.75,
    min_generic_relevance: float = 0.65,
    network_enabled: bool = False,
    openalex_enabled: bool = False,
    semanticscholar_enabled: bool = False,
    download_latex: bool = False,
    download_pdf: bool = False,
) -> dict[str, Any]:
    claim_usage = _collect_claim_usage(ledger)
    user_entries = _load_user_entries(user_inputs_path)
    user_inputs_dir = user_inputs_path.resolve().parent if user_inputs_path is not None else None
    entries_by_external_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    entries_by_citation_key: dict[str, list[dict[str, str]]] = defaultdict(list)
    for entry in user_entries:
        if entry["external_result_id"]:
            entries_by_external_id[entry["external_result_id"]].append(entry)
        if entry["citation_key"]:
            entries_by_citation_key[entry["citation_key"]].append(entry)

    items: list[dict[str, Any]] = []
    for external in ledger.get("external_results", []):
        if not isinstance(external, dict):
            continue
        external_result_id = normalize(external.get("external_result_id", ""))
        if not external_result_id:
            continue
        citation_keys = [normalize(x) for x in external.get("citation_keys_detected", []) if normalize(x)]
        matching_entries = list(entries_by_external_id.get(external_result_id, []))
        for key in citation_keys:
            matching_entries.extend(entries_by_citation_key.get(key, []))
        deduped_matching_entries: list[dict[str, str]] = []
        seen_entries: set[tuple[str, str, str, str, str]] = set()
        for entry in matching_entries:
            entry_key = (
                entry["external_result_id"],
                entry["citation_key"],
                entry["latex_root"],
                entry["pdf_path"],
                entry["note"],
            )
            if entry_key in seen_entries:
                continue
            seen_entries.add(entry_key)
            deduped_matching_entries.append(entry)
        matching_entries = deduped_matching_entries

        user_latex_roots = [
            path_info(entry["latex_root"], base_dir=user_inputs_dir)
            for entry in matching_entries
            if path_info(entry["latex_root"], base_dir=user_inputs_dir)
        ]
        user_pdfs = [
            path_info(entry["pdf_path"], base_dir=user_inputs_dir)
            for entry in matching_entries
            if path_info(entry["pdf_path"], base_dir=user_inputs_dir)
        ]
        user_latex_roots = [x for x in user_latex_roots if x is not None]
        user_pdfs = [x for x in user_pdfs if x is not None]
        existing_entry_count = sum(
            1
            for entry in matching_entries
            if any(
                asset.get("exists")
                for asset in (
                    path_info(entry["latex_root"], base_dir=user_inputs_dir) or {},
                    path_info(entry["pdf_path"], base_dir=user_inputs_dir) or {},
                )
            )
        )
        existing_asset_count = sum(1 for asset in [*user_latex_roots, *user_pdfs] if asset.get("exists"))

        retrieval_queries = [normalize(x) for x in external.get("retrieval_queries", []) if normalize(x)]
        if not retrieval_queries:
            label = normalize(external.get("citation_label", "") or external.get("name", external_result_id))
            if label:
                retrieval_queries.append(label)
        retrieval_queries = retrieval_queries[: max(1, max_queries_per_item)]

        item = {
            "external_result_id": external_result_id,
            "citation_label": normalize(external.get("citation_label", "")),
            "source_kind": normalize(external.get("source_kind", "")),
            "used_by_claim_ids": sorted(claim_usage.get(external_result_id, set())),
            "citation_keys_detected": citation_keys,
            "retrieval_queries": retrieval_queries,
            "user_inputs": {
                "entry_count": len(matching_entries),
                "valid_path_entry_count": sum(
                    1 for entry in matching_entries if entry["latex_root"] or entry["pdf_path"]
                ),
                "existing_entry_count": existing_entry_count,
                "existing_asset_count": existing_asset_count,
                "notes": [entry["note"] for entry in matching_entries if entry["note"]],
            },
            "discovery": {
                "network_enabled": bool(network_enabled),
                "network_used": False,
                "metadata_only_ref": normalize(external.get("citation_label", "") or external.get("name", "")),
                "provider_results": {},
                "notes": (
                    ["network retrieval disabled; using explicit human ingress only"]
                    if not network_enabled
                    else ["network retrieval not implemented in the committed MVP; using explicit human ingress only"]
                ),
            },
            "materials": {
                "user_latex_roots": user_latex_roots,
                "user_pdfs": user_pdfs,
                "latex_candidate_urls": [],
                "pdf_candidate_urls": [],
                "downloaded_latex_archive": None,
                "downloaded_pdf": None,
            },
        }
        item["selected_material"] = _select_material(item)
        items.append(item)

    with_latex = sum(1 for item in items if str(item["selected_material"]["mode"]).startswith("LATEX"))
    with_pdf = sum(1 for item in items if str(item["selected_material"]["mode"]).startswith("PDF"))
    unresolved = sum(1 for item in items if item["selected_material"]["mode"] == "NONE")
    with_user_declared = sum(1 for item in items if item["user_inputs"]["entry_count"] > 0)
    with_user_assets = sum(1 for item in items if item["user_inputs"]["existing_entry_count"] > 0)

    return {
        "schema": "leanatlas.external_source_pack",
        "schema_version": "0.1.0",
        "generated_at_utc": utc_now_iso(),
        "ledger_path": str(ledger_path),
        "user_inputs_path": str(user_inputs_path) if user_inputs_path else None,
        "settings": {
            "max_queries_per_item": int(max_queries_per_item),
            "max_results_per_provider": int(max_results_per_provider),
            "min_arxiv_relevance": float(min_arxiv_relevance),
            "min_generic_relevance": float(min_generic_relevance),
            "network_enabled": bool(network_enabled),
            "openalex_enabled": bool(openalex_enabled),
            "semanticscholar_enabled": bool(semanticscholar_enabled),
            "download_latex": bool(download_latex),
            "download_pdf": bool(download_pdf),
            "cache_dir": str(cache_dir) if cache_dir else "",
        },
        "summary": {
            "external_results_total": len(items),
            "with_user_declared_entries": with_user_declared,
            "with_user_assets": with_user_assets,
            "with_latex_material": with_latex,
            "with_pdf_material": with_pdf,
            "unresolved_count": unresolved,
        },
        "items": items,
    }
