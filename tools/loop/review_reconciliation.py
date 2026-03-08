"""Deterministic review supersession / reconciliation runtime."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .store import LoopStore

_UTC_TS = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_TOKEN_SANITIZER = re.compile(r"[^A-Za-z0-9._-]+")
_INGESTION_DISPOSITIONS = frozenset(
    {
        "APPLIED",
        "NOOP_ALREADY_COVERED",
        "REJECTED_WITH_RATIONALE",
    }
)
_FINDING_DISPOSITIONS = frozenset({"CONFIRMED", "DISMISSED", "SUPERSEDED"})


def _canonical_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _slug_token(raw: str, *, fallback: str) -> str:
    token = _TOKEN_SANITIZER.sub("-", str(raw).strip()).strip(".-_")
    return token or fallback


def _stable_reconciliation_ledger_path(*, repo_root: Path, review_slug: str, digest: str) -> Path:
    return (
        Path(repo_root).resolve()
        / "artifacts"
        / "loop_runtime"
        / "review_reconciliation"
        / "by_digest"
        / review_slug
        / f"ReviewSupersessionReconciliation.{digest}.json"
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _require_non_empty_string(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _require_utc_timestamp(value: Any, field_name: str) -> str:
    text = _require_non_empty_string(value, field_name)
    if not _UTC_TS.fullmatch(text):
        raise ValueError(f"{field_name} must match deterministic UTC `YYYY-MM-DDTHH:MM:SSZ` format")
    return text


def _normalize_string_list(values: Sequence[Any], field_name: str) -> list[str]:
    normalized = [str(item) for item in values]
    if any(not item for item in normalized):
        raise ValueError(f"{field_name} entries must be non-empty strings")
    return normalized


def _scope_lineage_key(scope_paths: Sequence[str]) -> str:
    normalized_paths = sorted(dict.fromkeys(str(item) for item in scope_paths))
    if not normalized_paths:
        raise ValueError("scope lineage requires at least one scope path")
    return _canonical_hash({"scope_paths": normalized_paths})


def _stage_manifest_index(orchestration_bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    entries = [dict(item) for item in orchestration_bundle.get("stage_manifest") or []]
    if not entries:
        raise ValueError("orchestration_bundle.stage_manifest must be non-empty")
    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        node_id = _require_non_empty_string(entry.get("node_id"), "orchestration_bundle.stage_manifest[*].node_id")
        if node_id in index:
            raise ValueError(f"orchestration_bundle.stage_manifest must not repeat node_id `{node_id}`")
        index[node_id] = entry
    return index


def _composition_notes(orchestration_bundle: Mapping[str, Any]) -> dict[str, Any]:
    notes = dict(orchestration_bundle.get("composition_notes") or {})
    if not notes:
        raise ValueError("orchestration_bundle.composition_notes must be present")
    return notes


def _reconciliation_contract(orchestration_bundle: Mapping[str, Any]) -> dict[str, Any]:
    contract = dict(orchestration_bundle.get("reconciliation_contract") or {})
    if not contract:
        raise ValueError("orchestration_bundle.reconciliation_contract must be present")
    return contract


def _finding_key(finding: Mapping[str, Any], *, review_round_id: str) -> str:
    if str(finding.get("finding_id") or "").strip():
        return str(finding["finding_id"])
    if str(finding.get("finding_fingerprint") or "").strip():
        return str(finding["finding_fingerprint"])
    raise ValueError(
        f"review round `{review_round_id}` findings must carry either `finding_id` or `finding_fingerprint`"
    )


def _round_sort_key(round_record: Mapping[str, Any]) -> tuple[str, int, str]:
    return (
        str(round_record["at_utc"]),
        int(round_record["_input_index"]),
        str(round_record["review_round_id"]),
    )


def _normalize_review_rounds(
    *,
    orchestration_bundle: Mapping[str, Any],
    review_rounds: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    stage_manifest = _stage_manifest_index(orchestration_bundle)
    composition_notes = _composition_notes(orchestration_bundle)
    reconciliation_contract = _reconciliation_contract(orchestration_bundle)

    normalized: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for input_index, raw_round in enumerate(review_rounds):
        round_record = dict(raw_round)
        review_round_id = _require_non_empty_string(round_record.get("review_round_id"), "review_round_id")
        if review_round_id in by_id:
            raise ValueError(f"review_rounds must not repeat review_round_id `{review_round_id}`")
        node_id = _require_non_empty_string(round_record.get("node_id"), f"{review_round_id}.node_id")
        if node_id not in stage_manifest:
            raise ValueError(f"review round `{review_round_id}` references unknown orchestration node `{node_id}`")
        stage_entry = dict(stage_manifest[node_id])
        at_utc = _require_utc_timestamp(round_record.get("at_utc"), f"{review_round_id}.at_utc")
        findings = [dict(item) for item in round_record.get("findings") or []]
        finding_keys = [_finding_key(item, review_round_id=review_round_id) for item in findings]
        if len(finding_keys) != len(set(finding_keys)):
            raise ValueError(f"review round `{review_round_id}` must not repeat the same finding key twice")
        scope_paths = _normalize_string_list(stage_entry.get("scope_paths") or [], f"{review_round_id}.scope_paths")

        normalized_round: dict[str, Any] = {
            "review_round_id": review_round_id,
            "node_id": node_id,
            "stage_id": _require_non_empty_string(stage_entry.get("stage_id"), f"{review_round_id}.stage_id"),
            "review_tier": _require_non_empty_string(stage_entry.get("review_tier"), f"{review_round_id}.review_tier"),
            "at_utc": at_utc,
            "scope_paths": scope_paths,
            "scope_fingerprint": _require_non_empty_string(
                stage_entry.get("scope_fingerprint"), f"{review_round_id}.scope_fingerprint"
            ),
            "scope_lineage_key": _scope_lineage_key(scope_paths),
            "finding_keys": finding_keys,
            "ingestion_disposition": "APPLIED",
            "closeout_authority": _require_non_empty_string(
                stage_entry.get("closeout_authority"), f"{review_round_id}.closeout_authority"
            ),
            "_input_index": int(input_index),
            "_findings": findings,
        }
        if "partition_id" in stage_entry:
            normalized_round["partition_id"] = stage_entry.get("partition_id")
        if "scope_fingerprint_basis" in stage_entry:
            normalized_round["scope_fingerprint_basis"] = stage_entry.get("scope_fingerprint_basis")
        if "partition_scope_paths" in stage_entry:
            normalized_round["partition_scope_paths"] = list(stage_entry.get("partition_scope_paths") or [])
        if "partition_scope_fingerprint" in stage_entry:
            normalized_round["partition_scope_fingerprint"] = stage_entry.get("partition_scope_fingerprint")
        if "selected_partition_ids" in stage_entry:
            normalized_round["selected_partition_ids"] = list(stage_entry.get("selected_partition_ids") or [])
        if "effective_scope_paths" in stage_entry:
            normalized_round["effective_scope_paths"] = list(stage_entry.get("effective_scope_paths") or [])
        if "effective_scope_fingerprint" in stage_entry:
            normalized_round["effective_scope_fingerprint"] = stage_entry.get("effective_scope_fingerprint")

        normalized.append(normalized_round)
        by_id[review_round_id] = normalized_round

    normalized.sort(key=_round_sort_key)
    authoritative_rounds = [
        item for item in normalized if item.get("closeout_authority") == "TERMINAL_DECISION_AUTHORITY"
    ]
    if not authoritative_rounds:
        raise ValueError("reconciliation runtime requires at least one authoritative closeout round")
    authoritative_round = authoritative_rounds[-1]

    if "authoritative_closeout_stage_id" in reconciliation_contract:
        expected_stage_id = str(reconciliation_contract["authoritative_closeout_stage_id"])
        if authoritative_round["stage_id"] != expected_stage_id:
            raise ValueError(
                "authoritative closeout round must come from the orchestration bundle's authoritative closeout stage"
            )

    return normalized, by_id, composition_notes, {
        **reconciliation_contract,
        "authoritative_round": authoritative_round,
    }


def _normalize_supersession_records(
    *,
    supersession_records: Sequence[Mapping[str, Any]],
    review_round_index: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_superseded: set[str] = set()
    for raw_record in supersession_records:
        record = dict(raw_record)
        superseded_review_round_id = _require_non_empty_string(
            record.get("superseded_review_round_id"), "supersession_records[*].superseded_review_round_id"
        )
        superseding_review_round_id = _require_non_empty_string(
            record.get("superseding_review_round_id"), "supersession_records[*].superseding_review_round_id"
        )
        if superseded_review_round_id not in review_round_index:
            raise ValueError(f"supersession record references unknown superseded round `{superseded_review_round_id}`")
        if superseding_review_round_id not in review_round_index:
            raise ValueError(f"supersession record references unknown superseding round `{superseding_review_round_id}`")
        if superseded_review_round_id == superseding_review_round_id:
            raise ValueError("supersession record must not self-supersede")
        if superseded_review_round_id in seen_superseded:
            raise ValueError(
                f"supersession_records must not repeat superseded_review_round_id `{superseded_review_round_id}`"
            )
        seen_superseded.add(superseded_review_round_id)
        supersede_reason = _require_non_empty_string(
            record.get("supersede_reason"), "supersession_records[*].supersede_reason"
        )
        supersede_created_at_utc = _require_utc_timestamp(
            record.get("supersede_created_at_utc"), "supersession_records[*].supersede_created_at_utc"
        )

        superseded_round = review_round_index[superseded_review_round_id]
        superseding_round = review_round_index[superseding_review_round_id]
        if _round_sort_key(superseding_round) <= _round_sort_key(superseded_round):
            raise ValueError(
                "supersession record must point to a newer superseding review round; "
                f"`{superseding_review_round_id}` is not newer than `{superseded_review_round_id}`"
            )
        explicit_ingestion_disposition = str(record.get("late_output_disposition") or "").strip()
        late_output_rationale = str(record.get("late_output_rationale") or "").strip()
        if explicit_ingestion_disposition:
            if explicit_ingestion_disposition not in _INGESTION_DISPOSITIONS:
                raise ValueError(
                    "supersession_records[*].late_output_disposition must be one of "
                    + ", ".join(sorted(_INGESTION_DISPOSITIONS))
                )
            ingestion_disposition = explicit_ingestion_disposition
        else:
            superseded_keys = set(str(key) for key in superseded_round["finding_keys"])
            superseding_keys = set(str(key) for key in superseding_round["finding_keys"])
            ingestion_disposition = (
                "NOOP_ALREADY_COVERED" if superseded_keys and superseded_keys <= superseding_keys else "APPLIED"
            )
        if ingestion_disposition == "REJECTED_WITH_RATIONALE" and not late_output_rationale:
            raise ValueError(
                "supersession_records[*].late_output_rationale is required when late_output_disposition is "
                "`REJECTED_WITH_RATIONALE`"
            )

        normalized_record = {
            "superseded_review_round_id": superseded_review_round_id,
            "superseding_review_round_id": superseding_review_round_id,
            "supersede_reason": supersede_reason,
            "supersede_created_at_utc": supersede_created_at_utc,
            "late_output_disposition": ingestion_disposition,
        }
        if late_output_rationale:
            normalized_record["late_output_rationale"] = late_output_rationale
        superseded_round["superseded_by_review_round_id"] = superseding_review_round_id
        superseded_round["supersede_reason"] = supersede_reason
        superseded_round["supersede_created_at_utc"] = supersede_created_at_utc
        superseded_round["ingestion_disposition"] = ingestion_disposition
        if late_output_rationale:
            superseded_round["late_output_rationale"] = late_output_rationale
        normalized.append(normalized_record)

    normalized.sort(
        key=lambda item: (
            str(item["supersede_created_at_utc"]),
            str(item["superseded_review_round_id"]),
            str(item["superseding_review_round_id"]),
        )
    )
    return normalized


def _derive_generated_at_utc(
    *,
    review_rounds: Sequence[dict[str, Any]],
    supersession_records: Sequence[Mapping[str, Any]],
) -> str:
    timestamps = [str(item["at_utc"]) for item in review_rounds]
    timestamps.extend(str(item["supersede_created_at_utc"]) for item in supersession_records)
    if not timestamps:
        raise ValueError("reconciliation runtime requires at least one evidence timestamp")
    return max(timestamps)


def _build_finding_records(
    *,
    review_rounds: Sequence[dict[str, Any]],
    review_round_index: Mapping[str, dict[str, Any]],
    supersession_records: Sequence[Mapping[str, Any]],
    authoritative_round: Mapping[str, Any],
    selected_partition_ids: Sequence[str],
    effective_scope_paths: Sequence[str],
    effective_scope_fingerprint: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    authoritative_round_id = str(authoritative_round["review_round_id"])
    authoritative_keys = set(str(key) for key in authoritative_round["finding_keys"])

    def _base_group_key(*, finding_key: str, round_record: Mapping[str, Any]) -> tuple[str, str]:
        return (finding_key, str(round_record["scope_lineage_key"]))

    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def _find(group_key: tuple[str, str]) -> tuple[str, str]:
        parent.setdefault(group_key, group_key)
        current = parent[group_key]
        if current != group_key:
            parent[group_key] = _find(current)
        return parent[group_key]

    def _union(left: tuple[str, str], right: tuple[str, str]) -> None:
        left_root = _find(left)
        right_root = _find(right)
        if left_root == right_root:
            return
        canonical_root = min(left_root, right_root)
        other_root = right_root if canonical_root == left_root else left_root
        parent[other_root] = canonical_root
        parent[left_root] = canonical_root
        parent[right_root] = canonical_root

    occurrences: list[dict[str, Any]] = []
    for round_record in review_rounds:
        for finding in round_record["_findings"]:
            key = _finding_key(finding, review_round_id=str(round_record["review_round_id"]))
            group_key = _base_group_key(finding_key=key, round_record=round_record)
            parent.setdefault(group_key, group_key)
            occurrences.append(
                {
                    "finding_key": key,
                    "base_group_key": group_key,
                    "sort_key": _round_sort_key(round_record),
                    "round_record": round_record,
                    "finding": dict(finding),
                }
            )

    for record in supersession_records:
        superseded_round = review_round_index[str(record["superseded_review_round_id"])]
        superseding_round = review_round_index[str(record["superseding_review_round_id"])]
        for finding_key in sorted(set(str(key) for key in superseded_round["finding_keys"]) & set(str(key) for key in superseding_round["finding_keys"])):
            _union(
                _base_group_key(finding_key=finding_key, round_record=superseded_round),
                _base_group_key(finding_key=finding_key, round_record=superseding_round),
            )

    occurrences_by_group: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for occurrence in occurrences:
        root_key = _find(occurrence["base_group_key"])
        occurrences_by_group.setdefault(root_key, []).append(occurrence)

    finding_records: list[dict[str, Any]] = []
    authoritative_findings: list[dict[str, Any]] = []
    for root_key in sorted(occurrences_by_group):
        grouped_occurrences = sorted(occurrences_by_group[root_key], key=lambda item: item["sort_key"])
        finding_key = str(grouped_occurrences[0]["finding_key"])
        latest_occurrence_round = grouped_occurrences[-1]["round_record"]
        authoritative_occurrences = [
            item
            for item in grouped_occurrences
            if str(item["round_record"]["review_round_id"]) == authoritative_round_id and finding_key in authoritative_keys
        ]
        lineage_scope_keys = sorted(
            dict.fromkeys(str(item["round_record"]["scope_lineage_key"]) for item in grouped_occurrences)
        )
        finding_group_key = _canonical_hash(
            {
                "finding_key": finding_key,
                "scope_lineage_keys": lineage_scope_keys,
            }
        )

        if authoritative_occurrences:
            authoritative_disposition = "CONFIRMED"
            authoritative_basis = "AUTHORITATIVE_CLOSEOUT_INCLUDED_FINDING"
            authoritative_source_review_round_id = authoritative_round_id
        else:
            authoritative_disposition = "DISMISSED"
            if latest_occurrence_round.get("ingestion_disposition") == "REJECTED_WITH_RATIONALE":
                authoritative_basis = "REJECTED_SUPERSEDED_LATE_OUTPUT"
            else:
                authoritative_basis = "ABSENT_FROM_AUTHORITATIVE_CLOSEOUT"
            authoritative_source_review_round_id = str(latest_occurrence_round["review_round_id"])

        for occurrence in grouped_occurrences:
            round_record = occurrence["round_record"]
            finding = occurrence["finding"]
            source_review_round_id = str(round_record["review_round_id"])
            is_authoritative_occurrence = source_review_round_id == authoritative_round_id and bool(authoritative_occurrences)
            is_latest_occurrence = round_record is latest_occurrence_round
            if is_authoritative_occurrence:
                disposition = "CONFIRMED"
                basis = "AUTHORITATIVE_CLOSEOUT_INCLUDED_FINDING"
            elif authoritative_disposition == "DISMISSED" and is_latest_occurrence:
                disposition = "DISMISSED"
                basis = authoritative_basis
            else:
                disposition = "SUPERSEDED"
                basis = (
                    "AUTHORITATIVE_CLOSEOUT_CONFIRMED_FINDING"
                    if authoritative_disposition == "CONFIRMED"
                    else "LATER_REVIEW_CONTEXT"
                )

            finding_record: dict[str, Any] = {
                "finding_key": finding_key,
                "finding_group_key": finding_group_key,
                "scope_lineage_key": str(round_record["scope_lineage_key"]),
                "source_review_round_id": source_review_round_id,
                "source_stage_id": str(round_record["stage_id"]),
                "source_partition_id": round_record.get("partition_id"),
                "source_finding_id": finding.get("finding_id"),
                "source_finding_fingerprint": finding.get("finding_fingerprint"),
                "disposition": disposition,
                "disposition_basis": basis,
                "settled_by_review_round_id": authoritative_round_id,
                "selected_partition_ids": [str(item) for item in selected_partition_ids],
                "effective_scope_paths": [str(item) for item in effective_scope_paths],
                "effective_scope_fingerprint": str(effective_scope_fingerprint),
            }
            if round_record.get("superseded_by_review_round_id"):
                finding_record["superseded_by_review_round_id"] = str(round_record["superseded_by_review_round_id"])
            if round_record.get("late_output_rationale"):
                finding_record["late_output_rationale"] = str(round_record["late_output_rationale"])
            if "severity" in finding:
                finding_record["severity"] = finding.get("severity")
            finding_records.append(finding_record)

        authoritative_findings.append(
            {
                "finding_key": finding_key,
                "finding_group_key": finding_group_key,
                "scope_lineage_keys": lineage_scope_keys,
                "final_disposition": authoritative_disposition,
                "disposition_basis": authoritative_basis,
                "settled_by_review_round_id": authoritative_round_id,
                "authoritative_source_review_round_id": authoritative_source_review_round_id,
            }
        )

    finding_records.sort(
        key=lambda item: (
            str(item["finding_group_key"]),
            str(item["source_review_round_id"]),
            str(item["disposition"]),
        )
    )
    authoritative_findings.sort(key=lambda item: str(item["finding_group_key"]))
    return finding_records, authoritative_findings


def reconcile_review_rounds(
    *,
    review_id: str,
    orchestration_bundle: Mapping[str, Any],
    review_rounds: Sequence[Mapping[str, Any]],
    supersession_records: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Reconcile staged review rounds into an authoritative finding ledger."""

    normalized_rounds, review_round_index, composition_notes, reconciliation_contract = _normalize_review_rounds(
        orchestration_bundle=orchestration_bundle,
        review_rounds=review_rounds,
    )
    normalized_supersession_records = _normalize_supersession_records(
        supersession_records=supersession_records,
        review_round_index=review_round_index,
    )

    authoritative_round = dict(reconciliation_contract["authoritative_round"])
    selected_partition_ids = _normalize_string_list(
        composition_notes.get("selected_partition_ids") or [],
        "orchestration_bundle.composition_notes.selected_partition_ids",
    )
    effective_scope_paths = _normalize_string_list(
        composition_notes.get("effective_scope_paths") or [],
        "orchestration_bundle.composition_notes.effective_scope_paths",
    )
    effective_scope_fingerprint = _require_non_empty_string(
        composition_notes.get("effective_scope_fingerprint"),
        "orchestration_bundle.composition_notes.effective_scope_fingerprint",
    )
    finding_records, authoritative_findings = _build_finding_records(
        review_rounds=normalized_rounds,
        review_round_index=review_round_index,
        supersession_records=normalized_supersession_records,
        authoritative_round=authoritative_round,
        selected_partition_ids=selected_partition_ids,
        effective_scope_paths=effective_scope_paths,
        effective_scope_fingerprint=effective_scope_fingerprint,
    )

    artifact = {
        "version": "1",
        "review_id": _require_non_empty_string(review_id, "review_id"),
        "generated_at_utc": _derive_generated_at_utc(
            review_rounds=normalized_rounds,
            supersession_records=normalized_supersession_records,
        ),
        "resource_id": _require_non_empty_string(
            reconciliation_contract.get("resource_id"),
            "orchestration_bundle.reconciliation_contract.resource_id",
        ),
        "producer_node_id": _require_non_empty_string(
            reconciliation_contract.get("producer_node_id"),
            "orchestration_bundle.reconciliation_contract.producer_node_id",
        ),
        "authoritative_closeout_review_round_id": str(authoritative_round["review_round_id"]),
        "selected_partition_ids": selected_partition_ids,
        "effective_scope_paths": effective_scope_paths,
        "effective_scope_fingerprint": effective_scope_fingerprint,
        "closeout_ready": True,
        "review_rounds": [
            {
                key: value
                for key, value in round_record.items()
                if not key.startswith("_")
            }
            for round_record in normalized_rounds
        ],
        "supersession_records": normalized_supersession_records,
        "finding_records": finding_records,
        "authoritative_findings": authoritative_findings,
    }
    assert_review_reconciliation_ready(artifact)
    return artifact


def assert_review_reconciliation_ready(reconciliation: Mapping[str, Any]) -> None:
    if reconciliation.get("closeout_ready") is not True:
        raise ValueError("reconciliation.closeout_ready must be true before authoritative closeout may proceed")
    authoritative_closeout_review_round_id = _require_non_empty_string(
        reconciliation.get("authoritative_closeout_review_round_id"),
        "reconciliation.authoritative_closeout_review_round_id",
    )
    finding_records = [dict(item) for item in reconciliation.get("finding_records") or []]
    unsettled = [
        item
        for item in finding_records
        if str(item.get("disposition") or "") not in _FINDING_DISPOSITIONS
    ]
    if unsettled:
        raise ValueError("reconciliation.finding_records contains unsettled dispositions")
    authoritative_round_rows = [
        item
        for item in reconciliation.get("review_rounds") or []
        if str(item.get("review_round_id") or "") == authoritative_closeout_review_round_id
    ]
    if not authoritative_round_rows:
        raise ValueError("reconciliation must retain the authoritative closeout round row")
    if str(authoritative_round_rows[0].get("closeout_authority") or "") != "TERMINAL_DECISION_AUTHORITY":
        raise ValueError("authoritative closeout round must carry TERMINAL_DECISION_AUTHORITY")
    authoritative_finding_rows = [dict(item) for item in reconciliation.get("authoritative_findings") or []]
    finding_group_keys = [str(item.get("finding_group_key") or "") for item in authoritative_finding_rows]
    if any(not item for item in finding_group_keys):
        raise ValueError("authoritative findings must include finding_group_key")
    if len(finding_group_keys) != len(set(finding_group_keys)):
        raise ValueError("authoritative findings must not repeat finding_group_key")


def persist_review_reconciliation(
    *,
    repo_root: Path,
    run_key: str,
    reconciliation: Mapping[str, Any],
) -> dict[str, str]:
    """Persist reconciliation ledger + append-only journal under LOOP runtime artifacts."""

    assert_review_reconciliation_ready(reconciliation)
    store = LoopStore(repo_root=Path(repo_root), run_key=run_key)
    store.ensure_layout()
    digest = _canonical_hash(reconciliation)
    review_slug = _slug_token(str(reconciliation.get("review_id") or "review"), fallback="review")
    journal_rel = f"review/reconciliation/{review_slug}/ReconciliationJournal.jsonl"
    ledger_path = _stable_reconciliation_ledger_path(
        repo_root=repo_root,
        review_slug=review_slug,
        digest=digest,
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if not ledger_path.exists():
        ledger_path.write_text(_canonical_json(reconciliation), encoding="utf-8")
    journal_row = {
        "at_utc": _utc_now(),
        "review_id": str(reconciliation["review_id"]),
        "resource_id": str(reconciliation["resource_id"]),
        "ledger_ref": str(ledger_path),
        "digest": digest,
    }
    journal_path = store.append_jsonl(journal_rel, journal_row, stream="artifact")
    return {
        "ledger_ref": str(ledger_path),
        "journal_ref": str(journal_path),
    }


__all__ = [
    "assert_review_reconciliation_ready",
    "persist_review_reconciliation",
    "reconcile_review_rounds",
]
