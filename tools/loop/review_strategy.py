#!/usr/bin/env python3
"""Deterministic helpers for staged narrowing and pyramid-review planning."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Sequence

from .review_prompting import EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID
from .review_runner import compute_review_scope_fingerprint
from .user_preferences import (
    DEFAULT_ASSURANCE_PRESET,
    DEFAULT_FAST_REVIEWER_PROFILE,
    DEFAULT_MEDIUM_ESCALATION_POLICY,
    DEFAULT_MEDIUM_ESCALATION_PROFILE,
    DEFAULT_REVIEW_TIER_POLICY,
    DEFAULT_STRICT_EXCEPTION_POLICY,
)

_SUPPORTED_REVIEW_TIER_POLICIES = frozenset({"LOW_ONLY", "LOW_PLUS_MEDIUM"})


def _resolve_repo_file(repo_root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    path = path.resolve()
    repo_root = repo_root.resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"path must stay under repo_root: {raw}") from exc
    if not path.exists():
        raise ValueError(f"path does not exist: {raw}")
    if not path.is_file():
        raise ValueError(f"path must be a file: {raw}")
    return path


def _normalize_scope_paths(*, repo_root: Path, scope_paths: Sequence[str | Path]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in scope_paths:
        resolved = _resolve_repo_file(repo_root, raw)
        rel = resolved.relative_to(repo_root.resolve()).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        normalized.append(rel)
    normalized.sort()
    if not normalized:
        raise ValueError("scope_paths must be a non-empty sequence of repo files")
    return normalized


def _slug(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    safe = safe.strip("._")
    return safe or "scope"


def _canonical_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _partition_ids_for_scope(
    *,
    partitions: Sequence[dict[str, Any]],
    scope_paths: Sequence[str],
) -> list[str]:
    scope_set = {str(rel) for rel in scope_paths}
    return [
        str(part["partition_id"])
        for part in partitions
        if scope_set.intersection({str(rel) for rel in part.get("scope_paths") or []})
    ]


def _scope_fingerprint(*, repo_root: Path, scope_paths: Sequence[str]) -> str:
    if not scope_paths:
        return _canonical_hash({"scope_paths": []})
    return compute_review_scope_fingerprint(repo_root=repo_root, scope_paths=scope_paths)


def _canonical_partitioning_policy_for_strategy_fingerprint(strategy: dict[str, Any]) -> dict[str, Any]:
    policy = dict(strategy.get("partitioning_policy") or {})
    if not policy or str(policy.get("group_by") or "") != "TOP_LEVEL_SCOPE_PREFIX":
        return policy
    full_scope_paths = [str(path) for path in strategy.get("full_scope_paths") or []]
    partitions = [dict(part) for part in strategy.get("partitions") or []]
    if not full_scope_paths or not partitions:
        return policy

    expected_chunks = [[str(path) for path in part.get("scope_paths") or []] for part in partitions]
    grouped_scope_paths: dict[str, list[str]] = {}
    for rel in full_scope_paths:
        grouped_scope_paths.setdefault(str(rel).split("/", 1)[0], []).append(str(rel))

    for max_files_per_partition in range(1, len(full_scope_paths) + 1):
        candidate_chunks: list[list[str]] = []
        for group in sorted(grouped_scope_paths):
            files = grouped_scope_paths[group]
            for start in range(0, len(files), max_files_per_partition):
                candidate_chunks.append(files[start : start + max_files_per_partition])
        if candidate_chunks == expected_chunks:
            return {
                "group_by": "TOP_LEVEL_SCOPE_PREFIX",
                "max_files_per_partition": max_files_per_partition,
            }
    return policy


def _strategy_fingerprint_payload(strategy: dict[str, Any]) -> dict[str, Any]:
    partition_keys = ("partition_id", "scope_paths", "scope_fingerprint")
    stage_keys = {
        "fast_partition_scan": ("stage_id", "agent_profile", "prompt_protocol_id", "partition_ids"),
        "deep_partition_followup": (
            "stage_id",
            "agent_profile",
            "partition_ids",
            "scope_paths",
            "scope_fingerprint",
            "prompt_protocol_id",
        ),
        "final_integrated_closeout": (
            "stage_id",
            "review_tier",
            "agent_profile",
            "scope_paths",
            "scope_fingerprint",
            "scope_source",
            "prompt_protocol_id",
        ),
    }
    authoritative_stages: list[dict[str, Any]] = []
    for stage in strategy.get("stages") or []:
        stage_id = str(stage.get("stage_id") or "")
        keys = stage_keys.get(stage_id)
        if keys is None:
            authoritative_stages.append(dict(stage))
            continue
        if stage_id == "deep_partition_followup" and not [str(pid) for pid in stage.get("partition_ids") or []]:
            keys = (
                "stage_id",
                "partition_ids",
                "scope_paths",
                "prompt_protocol_id",
            )
        authoritative_stages.append({key: stage.get(key) for key in keys})
    return {
        "version": str(strategy.get("version") or ""),
        "strategy_id": str(strategy.get("strategy_id") or ""),
        "agent_provider_id": str(strategy.get("agent_provider_id") or ""),
        "bounded_medium_profile": str(strategy.get("bounded_medium_profile") or ""),
        "strict_exception_profile": str(strategy.get("strict_exception_profile") or ""),
        "partitioning_policy": _canonical_partitioning_policy_for_strategy_fingerprint(strategy),
        "full_scope_paths": [str(path) for path in strategy.get("full_scope_paths") or []],
        "full_scope_fingerprint": str(strategy.get("full_scope_fingerprint") or ""),
        "partitions": [
            {key: part.get(key) for key in partition_keys}
            for part in strategy.get("partitions") or []
        ],
        "selected_partition_ids": [str(pid) for pid in strategy.get("selected_partition_ids") or []],
        "effective_scope_paths": [str(path) for path in strategy.get("effective_scope_paths") or []],
        "effective_scope_fingerprint": str(strategy.get("effective_scope_fingerprint") or ""),
        "effective_scope_source": str(strategy.get("effective_scope_source") or ""),
        "stages": authoritative_stages,
        "closeout_policy": dict(strategy.get("closeout_policy") or {}),
    }


def build_default_tiered_review_policy() -> dict[str, Any]:
    return {
        "policy_id": "review.low_plus_medium_default.v1",
        "review_tier_policy": DEFAULT_REVIEW_TIER_POLICY,
        "baseline_assurance_preset": DEFAULT_ASSURANCE_PRESET,
        "baseline_assurance_level": "FAST",
        "baseline_reviewer_profile": DEFAULT_FAST_REVIEWER_PROFILE,
        "medium_escalation_profile": DEFAULT_MEDIUM_ESCALATION_PROFILE,
        "medium_escalation_policy": DEFAULT_MEDIUM_ESCALATION_POLICY,
        "strict_exception_policy": DEFAULT_STRICT_EXCEPTION_POLICY,
        "large_scope_default_strategy": "PARTITION_LOW_THEN_MEDIUM_IF_HIGH_RISK",
    }


def partition_review_scope_paths(
    *,
    repo_root: Path,
    scope_paths: Sequence[str | Path],
    max_files_per_partition: int = 4,
) -> list[dict[str, Any]]:
    repo_root = repo_root.resolve()
    if int(max_files_per_partition) <= 0:
        raise ValueError("max_files_per_partition must be >= 1")
    normalized = _normalize_scope_paths(repo_root=repo_root, scope_paths=scope_paths)

    groups: dict[str, list[str]] = {}
    for rel in normalized:
        top = rel.split("/", 1)[0]
        groups.setdefault(top, []).append(rel)

    total_partitions = sum(
        (len(files) + int(max_files_per_partition) - 1) // int(max_files_per_partition)
        for files in groups.values()
    )
    partition_id_width = max(2, len(str(total_partitions)))
    partitions: list[dict[str, Any]] = []
    counter = 1
    for group in sorted(groups):
        files = sorted(groups[group])
        for chunk_idx, start in enumerate(range(0, len(files), int(max_files_per_partition)), start=1):
            chunk = files[start : start + int(max_files_per_partition)]
            suffix = f"_{chunk_idx:02d}" if len(files) > int(max_files_per_partition) else ""
            partition_id = f"part_{counter:0{partition_id_width}d}_{_slug(group)}{suffix}"
            partitions.append(
                {
                    "partition_id": partition_id,
                    "partition_group": group,
                    "scope_paths": chunk,
                    "scope_fingerprint": compute_review_scope_fingerprint(
                        repo_root=repo_root,
                        scope_paths=chunk,
                    ),
                }
            )
            counter += 1
    return partitions


def merge_partition_scope_paths(
    *,
    partitions: Sequence[dict[str, Any]],
    partition_ids: Sequence[str],
) -> list[str]:
    selected = {str(pid) for pid in partition_ids}
    by_id = {str(part["partition_id"]): part for part in partitions}
    missing = sorted(selected - set(by_id))
    if missing:
        raise ValueError(f"unknown partition_ids: {', '.join(missing)}")
    merged: list[str] = []
    seen: set[str] = set()
    for part in partitions:
        partition_id = str(part["partition_id"])
        if partition_id not in selected:
            continue
        for rel in part.get("scope_paths") or []:
            rel_str = str(rel)
            if rel_str in seen:
                continue
            seen.add(rel_str)
            merged.append(rel_str)
    return merged


def build_pyramid_review_plan(
    *,
    repo_root: Path,
    scope_paths: Sequence[str | Path],
    fast_profile: str,
    deep_profile: str,
    strict_profile: str,
    final_closeout_tier: str = "MEDIUM",
    review_tier_policy: str = DEFAULT_REVIEW_TIER_POLICY,
    agent_provider_id: str = "codex_cli",
    max_files_per_partition: int = 4,
    followup_partition_ids: Sequence[str] | None = None,
    effective_scope_paths: Sequence[str | Path] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    final_closeout_tier = str(final_closeout_tier or "").strip().upper()
    if final_closeout_tier not in {"LOW", "MEDIUM", "STRICT"}:
        raise ValueError("final_closeout_tier must be LOW, MEDIUM, or STRICT")
    review_tier_policy = str(review_tier_policy or "").strip().upper()
    if review_tier_policy not in _SUPPORTED_REVIEW_TIER_POLICIES:
        raise ValueError("review_tier_policy must be LOW_ONLY or LOW_PLUS_MEDIUM")
    if review_tier_policy == "LOW_ONLY" and final_closeout_tier != "LOW":
        raise ValueError("LOW_ONLY review_tier_policy requires final_closeout_tier=LOW")
    normalized_scope = _normalize_scope_paths(repo_root=repo_root, scope_paths=scope_paths)
    partitions = partition_review_scope_paths(
        repo_root=repo_root,
        scope_paths=normalized_scope,
        max_files_per_partition=max_files_per_partition,
    )
    partition_ids = [str(part["partition_id"]) for part in partitions]
    merged_selected_scope: list[str]
    effective_scope_source: str
    deep_scope_source: str

    if followup_partition_ids is not None:
        requested_followup_partition_ids = {str(pid) for pid in followup_partition_ids}
        selected_partition_ids = [pid for pid in partition_ids if pid in requested_followup_partition_ids]
        missing_partition_ids = sorted(set(selected_partition_ids) - set(partition_ids))
        if not missing_partition_ids:
            missing_partition_ids = sorted(requested_followup_partition_ids - set(partition_ids))
        if missing_partition_ids:
            raise ValueError(
                "followup_partition_ids must be a subset of plan partitions; "
                f"unknown ids: {', '.join(missing_partition_ids)}"
            )
        if selected_partition_ids:
            merged_selected_scope = merge_partition_scope_paths(
                partitions=partitions,
                partition_ids=selected_partition_ids,
            )
            effective_scope_source = "MERGED_SELECTED_PARTITIONS"
            deep_scope_source = effective_scope_source
        else:
            merged_selected_scope = []
            effective_scope_source = "FULL_SCOPE_AFTER_EMPTY_FOLLOWUP"
            deep_scope_source = "NO_FOLLOWUP_SELECTION"
    elif effective_scope_paths is None:
        selected_partition_ids = list(partition_ids)
        merged_selected_scope = list(normalized_scope)
        effective_scope_source = "MERGED_SELECTED_PARTITIONS"
        deep_scope_source = effective_scope_source
    else:
        normalized_effective_scope = _normalize_scope_paths(repo_root=repo_root, scope_paths=effective_scope_paths)
        effective_scope_set = set(normalized_effective_scope)
        selected_partition_ids = [
            str(part["partition_id"])
            for part in partitions
            if effective_scope_set.intersection({str(rel) for rel in part.get("scope_paths") or []})
        ]
        if not selected_partition_ids:
            raise ValueError("effective_scope_paths must intersect at least one review partition")
        merged_selected_scope = merge_partition_scope_paths(
            partitions=partitions,
            partition_ids=selected_partition_ids,
        )
        effective_scope_source = "INFERRED_FROM_EFFECTIVE_SCOPE"
        deep_scope_source = effective_scope_source

    if effective_scope_paths is None:
        if followup_partition_ids is not None and not selected_partition_ids:
            effective_scope = list(normalized_scope)
        else:
            effective_scope = list(merged_selected_scope)
    else:
        if followup_partition_ids is not None and not selected_partition_ids and len(effective_scope_paths) == 0:
            effective_scope = list(normalized_scope)
            effective_scope_source = "FULL_SCOPE_AFTER_EMPTY_FOLLOWUP"
            deep_scope_source = "NO_FOLLOWUP_SELECTION"
        else:
            effective_scope = _normalize_scope_paths(repo_root=repo_root, scope_paths=effective_scope_paths)
            if not set(effective_scope).issubset(set(merged_selected_scope)):
                unexpected_scope = sorted(set(effective_scope) - set(merged_selected_scope))
                raise ValueError(
                    "effective_scope_paths must stay within the merged selected partitions; "
                    f"unexpected paths: {', '.join(unexpected_scope)}"
                )
            selected_partition_ids = _partition_ids_for_scope(
                partitions=partitions,
                scope_paths=effective_scope,
            )
            if not selected_partition_ids:
                raise ValueError("effective_scope_paths must keep at least one selected follow-up partition")
            if followup_partition_ids is not None:
                if effective_scope == merged_selected_scope:
                    effective_scope_source = "MERGED_SELECTED_PARTITIONS"
                    deep_scope_source = effective_scope_source
                else:
                    effective_scope_source = "MANUAL_EFFECTIVE_SCOPE_OVERRIDE"
                    deep_scope_source = effective_scope_source

    if final_closeout_tier == "LOW" and review_tier_policy != "LOW_ONLY":
        raise ValueError("LOW final_closeout_tier requires review_tier_policy=LOW_ONLY")
    if final_closeout_tier == "LOW" and selected_partition_ids:
        raise ValueError(
            "LOW final_closeout_tier requires the explicit no-escalation path "
            "(deep follow-up must be empty; pass followup_partition_ids=[] to encode that state)"
        )

    deep_stage_scope = list(effective_scope if selected_partition_ids else [])
    if final_closeout_tier == "LOW":
        final_closeout_agent_profile = fast_profile
    elif final_closeout_tier == "MEDIUM":
        final_closeout_agent_profile = deep_profile
    else:
        final_closeout_agent_profile = strict_profile

    strategy = {
        "version": "1",
        "strategy_id": "review.pyramid_partition.v1",
        "agent_provider_id": agent_provider_id,
        "bounded_medium_profile": deep_profile,
        "strict_exception_profile": strict_profile,
        "partitioning_policy": {
            "group_by": "TOP_LEVEL_SCOPE_PREFIX",
            "max_files_per_partition": int(max_files_per_partition),
        },
        "full_scope_paths": normalized_scope,
        "full_scope_fingerprint": compute_review_scope_fingerprint(
            repo_root=repo_root,
            scope_paths=normalized_scope,
        ),
        "partitions": partitions,
        "selected_partition_ids": selected_partition_ids,
        "effective_scope_paths": effective_scope,
        "effective_scope_fingerprint": _scope_fingerprint(repo_root=repo_root, scope_paths=effective_scope),
        "effective_scope_source": effective_scope_source,
        "stages": [
            {
                "stage_id": "fast_partition_scan",
                "review_tier": "FAST",
                "agent_profile": fast_profile,
                "prompt_protocol_id": EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
                "partition_ids": partition_ids,
                "closeout_eligible": False,
                "finding_policy": "ADVISORY_CONFIRM_REQUIRED",
                "selection_policy": "ALL_PARTITIONS",
            },
            {
                "stage_id": "deep_partition_followup",
                "review_tier": "DEEP",
                "agent_profile": deep_profile,
                "prompt_protocol_id": EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
                "candidate_partition_ids": partition_ids,
                "partition_ids": selected_partition_ids,
                "scope_paths": deep_stage_scope,
                "scope_fingerprint": _scope_fingerprint(repo_root=repo_root, scope_paths=deep_stage_scope),
                "scope_source": deep_scope_source,
                "closeout_eligible": False,
                "finding_policy": "CONFIRM_OR_DISMISS_BEFORE_CLOSEOUT",
                "selection_policy": "PARTITIONS_WITH_FINDINGS_OR_MANUAL_SELECTION",
            },
            {
                "stage_id": "final_integrated_closeout",
                "review_tier": final_closeout_tier,
                "agent_profile": final_closeout_agent_profile,
                "prompt_protocol_id": EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
                "scope_paths": effective_scope,
                "scope_fingerprint": _scope_fingerprint(repo_root=repo_root, scope_paths=effective_scope),
                "closeout_eligible": True,
                "finding_policy": "TERMINAL_DECISION_AUTHORITY",
                "selection_policy": "INTEGRATED_MAIN_SCOPE",
                "scope_source": effective_scope_source,
            },
        ],
        "closeout_policy": {
            "final_stage_id": "final_integrated_closeout",
            "intermediate_rounds_are_advisory": True,
            "requires_integrated_scope_closeout": True,
            "review_tier_policy": review_tier_policy,
        },
    }
    strategy["strategy_fingerprint"] = _canonical_hash(_strategy_fingerprint_payload(strategy))
    return strategy


__all__ = [
    "build_pyramid_review_plan",
    "merge_partition_scope_paths",
    "partition_review_scope_paths",
]
