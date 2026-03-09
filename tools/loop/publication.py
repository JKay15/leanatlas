#!/usr/bin/env python3
"""Append-only publication, ingress, and context-rematerialization helpers."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

_TOKEN_SANITIZER = re.compile(r"[^A-Za-z0-9._-]+")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _canonical_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _slug_token(raw: str, *, fallback: str) -> str:
    token = _TOKEN_SANITIZER.sub("-", str(raw).strip()).strip(".-_")
    return token or fallback


def _resolve_repo_path(repo_root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    path = path.resolve()
    repo_root = repo_root.resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"path must stay under repo_root: {raw}") from exc
    if not path.exists() or not path.is_file():
        raise ValueError(f"path must exist and be a file: {raw}")
    return path


def _normalize_relative_repo_refs(*, repo_root: Path, refs: Sequence[str | Path]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in refs:
        resolved = _resolve_repo_path(repo_root, raw)
        rel = resolved.relative_to(repo_root.resolve()).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        normalized.append(rel)
    return normalized


def _normalize_mixed_repo_refs(*, repo_root: Path, refs: Sequence[str | Path]) -> list[str]:
    # Mixed absolute/repo-relative refs must collapse onto one canonical repo-relative identity
    # so deterministic context-pack hashes do not fork on path spelling alone.
    return _normalize_relative_repo_refs(repo_root=repo_root, refs=refs)


def _write_once_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_canonical_json(obj), encoding="utf-8")


def _append_unique_jsonl(path: Path, key: str, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_keys: set[str] = set()
    if path.exists():
        existing_keys = {
            str(json.loads(line).get(key) or "")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    row_key = str(row.get(key) or "")
    if row_key in existing_keys:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _event_paths(*, repo_root: Path, event_kind: str, event_id: str, digest: str) -> tuple[Path, Path]:
    kind_slug = _slug_token(event_kind.lower(), fallback="event")
    id_slug = _slug_token(event_id, fallback="event")
    event_ref = (
        repo_root.resolve()
        / "artifacts"
        / "loop_runtime"
        / "publications"
        / "by_kind"
        / kind_slug
        / id_slug
        / f"{digest}.json"
    )
    journal_ref = (
        repo_root.resolve()
        / "artifacts"
        / "loop_runtime"
        / "publications"
        / "journal"
        / kind_slug
        / f"{id_slug}.jsonl"
    )
    return event_ref, journal_ref


def publish_capability_event(
    *,
    repo_root: Path,
    publication_id: str,
    producer_id: str,
    summary: str,
    resource_refs: Sequence[str | Path],
    capability_kind: str = "CAPABILITY",
) -> dict[str, str]:
    repo_root = Path(repo_root).resolve()
    normalized_resource_refs = _normalize_relative_repo_refs(repo_root=repo_root, refs=resource_refs)
    payload = {
        "version": "1",
        "event_kind": str(capability_kind or "").strip().upper() or "CAPABILITY",
        "publication_id": str(publication_id).strip(),
        "producer_id": str(producer_id).strip(),
        "summary": str(summary).strip(),
        "resource_refs": normalized_resource_refs,
    }
    if not payload["publication_id"] or not payload["producer_id"] or not payload["summary"]:
        raise ValueError("publication_id, producer_id, and summary must be non-empty")
    digest = _canonical_hash(payload)
    event_ref, journal_ref = _event_paths(
        repo_root=repo_root,
        event_kind=payload["event_kind"],
        event_id=payload["publication_id"],
        digest=digest,
    )
    event = {
        **payload,
        "digest": digest,
        "published_at_utc": _utc_now(),
        "event_ref": str(event_ref),
    }
    _write_once_json(event_ref, event)
    _append_unique_jsonl(
        journal_ref,
        "digest",
        {
            "digest": digest,
            "event_kind": payload["event_kind"],
            "publication_id": payload["publication_id"],
            "producer_id": payload["producer_id"],
            "summary": payload["summary"],
            "event_ref": str(event_ref),
            "published_at_utc": event["published_at_utc"],
        },
    )
    return {
        "event_kind": payload["event_kind"],
        "event_ref": str(event_ref),
        "journal_ref": str(journal_ref),
        "digest": digest,
    }


def publish_supervisor_guidance_event(
    *,
    repo_root: Path,
    guidance_id: str,
    producer_id: str,
    summary: str,
    reminder_message: str = "",
    known_conclusion_refs: Sequence[str | Path] = (),
    non_goal_refs: Sequence[str | Path] = (),
) -> dict[str, str]:
    repo_root = Path(repo_root).resolve()
    normalized_known_conclusion_refs = _normalize_relative_repo_refs(
        repo_root=repo_root,
        refs=known_conclusion_refs,
    )
    normalized_non_goal_refs = _normalize_relative_repo_refs(
        repo_root=repo_root,
        refs=non_goal_refs,
    )
    payload = {
        "version": "1",
        "event_kind": "SUPERVISOR_GUIDANCE",
        "guidance_id": str(guidance_id).strip(),
        "producer_id": str(producer_id).strip(),
        "summary": str(summary).strip(),
        "reminder_message": str(reminder_message).strip(),
        "known_conclusion_refs": normalized_known_conclusion_refs,
        "non_goal_refs": normalized_non_goal_refs,
    }
    if not payload["guidance_id"] or not payload["producer_id"] or not payload["summary"]:
        raise ValueError("guidance_id, producer_id, and summary must be non-empty")
    digest = _canonical_hash(payload)
    event_ref, journal_ref = _event_paths(
        repo_root=repo_root,
        event_kind=payload["event_kind"],
        event_id=payload["guidance_id"],
        digest=digest,
    )
    event = {
        **payload,
        "digest": digest,
        "published_at_utc": _utc_now(),
        "event_ref": str(event_ref),
    }
    _write_once_json(event_ref, event)
    _append_unique_jsonl(
        journal_ref,
        "digest",
        {
            "digest": digest,
            "event_kind": payload["event_kind"],
            "guidance_id": payload["guidance_id"],
            "producer_id": payload["producer_id"],
            "summary": payload["summary"],
            "event_ref": str(event_ref),
            "published_at_utc": event["published_at_utc"],
        },
    )
    return {
        "event_kind": payload["event_kind"],
        "event_ref": str(event_ref),
        "journal_ref": str(journal_ref),
        "digest": digest,
    }


def record_human_external_input(
    *,
    repo_root: Path,
    ingress_id: str,
    producer_id: str,
    source_label: str,
    summary: str,
    evidence_refs: Sequence[str | Path],
    related_context_refs: Sequence[str | Path] = (),
) -> dict[str, str]:
    repo_root = Path(repo_root).resolve()
    normalized_evidence_refs = _normalize_relative_repo_refs(repo_root=repo_root, refs=evidence_refs)
    normalized_related_context_refs = _normalize_relative_repo_refs(
        repo_root=repo_root,
        refs=related_context_refs,
    )
    payload = {
        "version": "1",
        "event_kind": "HUMAN_EXTERNAL_INPUT",
        "ingress_id": str(ingress_id).strip(),
        "producer_id": str(producer_id).strip(),
        "source_label": str(source_label).strip(),
        "summary": str(summary).strip(),
        "evidence_refs": normalized_evidence_refs,
        "related_context_refs": normalized_related_context_refs,
    }
    if not payload["ingress_id"] or not payload["producer_id"] or not payload["source_label"] or not payload["summary"]:
        raise ValueError("ingress_id, producer_id, source_label, and summary must be non-empty")
    digest = _canonical_hash(payload)
    event_ref, journal_ref = _event_paths(
        repo_root=repo_root,
        event_kind=payload["event_kind"],
        event_id=payload["ingress_id"],
        digest=digest,
    )
    event = {
        **payload,
        "digest": digest,
        "published_at_utc": _utc_now(),
        "event_ref": str(event_ref),
    }
    _write_once_json(event_ref, event)
    _append_unique_jsonl(
        journal_ref,
        "digest",
        {
            "digest": digest,
            "event_kind": payload["event_kind"],
            "ingress_id": payload["ingress_id"],
            "producer_id": payload["producer_id"],
            "source_label": payload["source_label"],
            "event_ref": str(event_ref),
            "published_at_utc": event["published_at_utc"],
        },
    )
    return {
        "event_kind": payload["event_kind"],
        "event_ref": str(event_ref),
        "journal_ref": str(journal_ref),
        "digest": digest,
    }


def rematerialize_context_pack(
    *,
    repo_root: Path,
    context_id: str,
    consumer_id: str,
    base_context_refs: Sequence[str | Path],
    publication_event_refs: Sequence[str | Path] = (),
    human_ingress_event_refs: Sequence[str | Path] = (),
    supervisor_guidance_event_refs: Sequence[str | Path] = (),
) -> dict[str, str]:
    repo_root = Path(repo_root).resolve()
    normalized_base_context_refs = _normalize_relative_repo_refs(repo_root=repo_root, refs=base_context_refs)
    normalized_publication_event_refs = _normalize_mixed_repo_refs(
        repo_root=repo_root,
        refs=publication_event_refs,
    )
    normalized_human_ingress_event_refs = _normalize_mixed_repo_refs(
        repo_root=repo_root,
        refs=human_ingress_event_refs,
    )
    normalized_supervisor_guidance_event_refs = _normalize_mixed_repo_refs(
        repo_root=repo_root,
        refs=supervisor_guidance_event_refs,
    )
    required_context_refs: list[str] = []
    seen: set[str] = set()
    for item in (
        *normalized_base_context_refs,
        *normalized_human_ingress_event_refs,
        *normalized_publication_event_refs,
        *normalized_supervisor_guidance_event_refs,
    ):
        if item in seen:
            continue
        seen.add(item)
        required_context_refs.append(item)
    payload = {
        "version": "1",
        "context_id": str(context_id).strip(),
        "consumer_id": str(consumer_id).strip(),
        "base_context_refs": normalized_base_context_refs,
        "publication_event_refs": normalized_publication_event_refs,
        "human_ingress_event_refs": normalized_human_ingress_event_refs,
        "supervisor_guidance_event_refs": normalized_supervisor_guidance_event_refs,
        "required_context_refs": required_context_refs,
    }
    if not payload["context_id"] or not payload["consumer_id"]:
        raise ValueError("context_id and consumer_id must be non-empty")
    if not required_context_refs:
        raise ValueError("rematerialized context pack must include at least one required_context_ref")
    digest = _canonical_hash(payload)
    context_ref = (
        repo_root
        / "artifacts"
        / "loop_runtime"
        / "context_packs"
        / "by_consumer"
        / _slug_token(payload["consumer_id"], fallback="consumer")
        / _slug_token(payload["context_id"], fallback="context")
        / f"{digest}.json"
    )
    context_pack = {
        **payload,
        "context_key": digest,
        "rematerialized_at_utc": _utc_now(),
        "context_pack_ref": str(context_ref),
    }
    _write_once_json(context_ref, context_pack)
    return {
        "context_pack_ref": str(context_ref),
        "context_key": digest,
    }


__all__ = [
    "publish_capability_event",
    "publish_supervisor_guidance_event",
    "record_human_external_input",
    "rematerialize_context_pack",
]
