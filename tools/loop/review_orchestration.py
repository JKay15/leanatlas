#!/usr/bin/env python3
"""Compile staged review strategies into executable LOOP review-orchestration graphs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .review_runner import compute_review_scope_fingerprint
from .review_strategy import _canonical_partitioning_policy_for_strategy_fingerprint, partition_review_scope_paths

_GRAPH_MODE_VALUES = {"STATIC_USER_MODE", "SYSTEM_EXCEPTION_MODE"}
_RESOURCE_CLASS_VALUES = {"IMMUTABLE", "APPEND_ONLY", "MUTABLE_CONTROLLED"}
_TOKEN_SANITIZER = re.compile(r"[^A-Za-z0-9._-]+")
_PARTITION_ID_SEQUENCE = re.compile(r"^part_(\d+)(?:_|$)")
_PYRAMID_STRATEGY_ID = "review.pyramid_partition.v1"
_LEGACY_FINGERPRINT_OMITTABLE_TOP_LEVEL_KEYS = (
    "bounded_medium_profile",
    "strict_exception_profile",
    "partitioning_policy",
)
_SUPPORTED_LEGACY_FINGERPRINT_OMIT_KEY_SETS = (
    frozenset({"bounded_medium_profile", "strict_exception_profile", "partitioning_policy"}),
    frozenset({"bounded_medium_profile", "strict_exception_profile"}),
    frozenset({"strict_exception_profile", "partitioning_policy"}),
)
_PRE_TIER_PROVENANCE_STRICT_OMIT_KEYS = frozenset(
    {"bounded_medium_profile", "strict_exception_profile", "partitioning_policy"}
)
_REQUIRED_STAGE_IDS = (
    "fast_partition_scan",
    "deep_partition_followup",
    "final_integrated_closeout",
)
_STAGE_ALLOWED_KEYS = {
    "fast_partition_scan": frozenset(
        {
            "stage_id",
            "review_tier",
            "agent_profile",
            "partition_ids",
            "closeout_eligible",
            "finding_policy",
            "selection_policy",
        }
    ),
    "deep_partition_followup": frozenset(
        {
            "stage_id",
            "review_tier",
            "agent_profile",
            "candidate_partition_ids",
            "partition_ids",
            "scope_paths",
            "scope_fingerprint",
            "scope_source",
            "closeout_eligible",
            "finding_policy",
            "selection_policy",
        }
    ),
    "final_integrated_closeout": frozenset(
        {
            "stage_id",
            "review_tier",
            "agent_profile",
            "scope_paths",
            "scope_fingerprint",
            "closeout_eligible",
            "finding_policy",
            "selection_policy",
            "scope_source",
        }
    ),
}
_STAGE_STATIC_FIELDS = {
    "fast_partition_scan": {
        "review_tier": "FAST",
        "closeout_eligible": False,
        "finding_policy": "ADVISORY_CONFIRM_REQUIRED",
        "selection_policy": "ALL_PARTITIONS",
    },
    "deep_partition_followup": {
        "review_tier": "DEEP",
        "closeout_eligible": False,
        "finding_policy": "CONFIRM_OR_DISMISS_BEFORE_CLOSEOUT",
        "selection_policy": "PARTITIONS_WITH_FINDINGS_OR_MANUAL_SELECTION",
    },
    "final_integrated_closeout": {
        "closeout_eligible": True,
        "finding_policy": "TERMINAL_DECISION_AUTHORITY",
        "selection_policy": "INTEGRATED_MAIN_SCOPE",
    },
}
_CLOSEOUT_POLICY_REQUIRED_KEYS = frozenset(
    {
        "final_stage_id",
        "intermediate_rounds_are_advisory",
        "requires_integrated_scope_closeout",
    }
)
_CLOSEOUT_POLICY_ALLOWED_KEYS = frozenset(
    {
        *_CLOSEOUT_POLICY_REQUIRED_KEYS,
        "review_tier_policy",
    }
)
_PARTITIONING_POLICY_ALLOWED_KEYS = frozenset({"group_by", "max_files_per_partition"})
_FINGERPRINT_PARTITION_KEYS = ("partition_id", "scope_paths", "scope_fingerprint")
_FINGERPRINT_STAGE_KEYS = {
    "fast_partition_scan": (
        "stage_id",
        "agent_profile",
        "partition_ids",
    ),
    "deep_partition_followup": (
        "stage_id",
        "agent_profile",
        "partition_ids",
        "scope_paths",
        "scope_fingerprint",
    ),
    "final_integrated_closeout": (
        "stage_id",
        "review_tier",
        "agent_profile",
        "scope_paths",
        "scope_fingerprint",
        "scope_source",
    ),
}
_EFFECTIVE_SCOPE_SOURCE_VALUES = frozenset(
    {
        "MERGED_SELECTED_PARTITIONS",
        "FULL_SCOPE_AFTER_EMPTY_FOLLOWUP",
        "INFERRED_FROM_EFFECTIVE_SCOPE",
        "MANUAL_EFFECTIVE_SCOPE_OVERRIDE",
    }
)


def _fingerprint_stage_payload(
    stage: Mapping[str, Any],
    *,
    omit_final_stage_review_tier: bool = False,
) -> dict[str, Any]:
    stage_id = str(stage.get("stage_id") or "")
    keys = _FINGERPRINT_STAGE_KEYS.get(stage_id)
    if keys is None:
        return dict(stage)
    if stage_id == "deep_partition_followup" and not [str(pid) for pid in stage.get("partition_ids") or []]:
        keys = (
            "stage_id",
            "partition_ids",
            "scope_paths",
        )
    payload = {key: stage.get(key) for key in keys}
    if stage_id == "final_integrated_closeout" and omit_final_stage_review_tier:
        payload.pop("review_tier", None)
    return payload


def _slug_token(raw: str, *, fallback: str) -> str:
    token = _TOKEN_SANITIZER.sub("-", str(raw).strip()).strip(".-_")
    return token or fallback


def _canonical_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _normalize_repo_root(repo_root: str | Path) -> Path:
    resolved = Path(repo_root).resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("repo_root must exist and be a directory")
    return resolved


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


def _canonicalize_scope_paths(
    *,
    repo_root: Path,
    scope_paths: Sequence[str | Path],
    field_name: str,
    require_non_empty: bool = False,
) -> list[str]:
    canonical = [
        _resolve_repo_file(repo_root, raw).relative_to(repo_root.resolve()).as_posix()
        for raw in scope_paths
    ]
    if require_non_empty and not canonical:
        raise ValueError(f"{field_name} must be non-empty")
    return canonical


def _expected_strategy_fingerprint(
    plan: dict[str, Any],
    *,
    omit_top_level_keys: Sequence[str] = (),
    canonicalize_partitioning_policy: bool = True,
    omit_final_stage_review_tier: bool = False,
) -> str:
    authoritative_partitions = [
        {key: part.get(key) for key in _FINGERPRINT_PARTITION_KEYS}
        for part in plan.get("partitions") or []
    ]
    authoritative_stages = [
        _fingerprint_stage_payload(
            dict(stage),
            omit_final_stage_review_tier=omit_final_stage_review_tier,
        )
        for stage in plan.get("stages") or []
    ]
    payload = {
        "version": str(plan.get("version") or ""),
        "strategy_id": str(plan.get("strategy_id") or ""),
        "agent_provider_id": str(plan.get("agent_provider_id") or ""),
        "bounded_medium_profile": str(plan.get("bounded_medium_profile") or ""),
        "strict_exception_profile": str(plan.get("strict_exception_profile") or ""),
        "partitioning_policy": (
            _canonical_partitioning_policy_for_strategy_fingerprint(plan)
            if canonicalize_partitioning_policy
            else dict(plan.get("partitioning_policy") or {})
        ),
        "full_scope_paths": [str(path) for path in plan.get("full_scope_paths") or []],
        "full_scope_fingerprint": str(plan.get("full_scope_fingerprint") or ""),
        "partitions": authoritative_partitions,
        "selected_partition_ids": [str(pid) for pid in plan.get("selected_partition_ids") or []],
        "effective_scope_paths": [str(path) for path in plan.get("effective_scope_paths") or []],
        "effective_scope_fingerprint": str(plan.get("effective_scope_fingerprint") or ""),
        "effective_scope_source": str(plan.get("effective_scope_source") or ""),
        "stages": authoritative_stages,
        "closeout_policy": dict(plan.get("closeout_policy") or {}),
    }
    for key in omit_top_level_keys:
        payload.pop(str(key), None)
    return _canonical_hash(payload)


def _matching_legacy_fingerprint_omit_keys(
    *,
    plan: dict[str, Any],
    strategy_fingerprint: str,
    eligible_omit_keys: Sequence[str],
) -> list[str]:
    eligible = set(str(key) for key in eligible_omit_keys)
    for combo in _SUPPORTED_LEGACY_FINGERPRINT_OMIT_KEY_SETS:
        if not combo.issubset(eligible):
            continue
        ordered_combo = [key for key in _LEGACY_FINGERPRINT_OMITTABLE_TOP_LEVEL_KEYS if key in combo]
        if strategy_fingerprint in _legacy_candidate_strategy_fingerprints(plan, omit_top_level_keys=ordered_combo):
            return ordered_combo
    return []


def _legacy_candidate_strategy_fingerprints(
    plan: dict[str, Any],
    *,
    omit_top_level_keys: Sequence[str],
) -> list[str]:
    candidates = [_expected_strategy_fingerprint(plan, omit_top_level_keys=omit_top_level_keys)]
    final_stage = next(
        (
            dict(stage)
            for stage in plan.get("stages") or []
            if str(stage.get("stage_id") or "") == "final_integrated_closeout"
        ),
        {},
    )
    if (
        set(str(key) for key in omit_top_level_keys) == _PRE_TIER_PROVENANCE_STRICT_OMIT_KEYS
        and str(final_stage.get("review_tier") or "").strip() == "STRICT"
    ):
        candidates.append(
            _expected_strategy_fingerprint(
                plan,
                omit_top_level_keys=omit_top_level_keys,
                omit_final_stage_review_tier=True,
            )
        )
    return list(dict.fromkeys(candidates))


def _normalize_supported_legacy_omit_keys(raw_keys: Sequence[str] | None) -> list[str]:
    if not raw_keys:
        return []
    normalized = {str(key) for key in raw_keys if str(key)}
    for combo in _SUPPORTED_LEGACY_FINGERPRINT_OMIT_KEY_SETS:
        if normalized == combo:
            return [key for key in _LEGACY_FINGERPRINT_OMITTABLE_TOP_LEVEL_KEYS if key in combo]
    return []


def _legacy_omit_keys_consistent_with_plan(
    *,
    repo_root: Path,
    plan: dict[str, Any],
    omit_keys: Sequence[str],
) -> bool:
    omit = set(str(key) for key in omit_keys)
    if "bounded_medium_profile" in omit:
        expected_bounded = (
            _legacy_stage_profile(plan, stage_id="final_integrated_closeout", review_tier="MEDIUM")
            or _legacy_stage_profile(plan, stage_id="deep_partition_followup")
        )
        if str(plan.get("bounded_medium_profile") or "") != expected_bounded:
            return False
    if "strict_exception_profile" in omit:
        expected_strict = _legacy_strict_exception_profile(
            plan,
            bounded_medium_profile=str(plan.get("bounded_medium_profile") or ""),
        )
        if str(plan.get("strict_exception_profile") or "") != expected_strict:
            return False
    if "partitioning_policy" in omit:
        expected_partitioning_policy = _infer_partitioning_policy(
            repo_root=repo_root,
            full_scope_paths=[str(path) for path in plan.get("full_scope_paths") or []],
            partitions=[dict(part) for part in plan.get("partitions") or []],
        )
        if not expected_partitioning_policy:
            return False
        if dict(plan.get("partitioning_policy") or {}) != expected_partitioning_policy:
            return False
    return True


def _legacy_stage_profile(plan: dict[str, Any], *, stage_id: str, review_tier: str | None = None) -> str:
    for stage in plan.get("stages") or []:
        if str(stage.get("stage_id") or "") != stage_id:
            continue
        if review_tier is not None and str(stage.get("review_tier") or "") != review_tier:
            continue
        profile = str(stage.get("agent_profile") or "").strip()
        if profile:
            return profile
    return ""


def _legacy_strict_exception_profile(plan: dict[str, Any], *, bounded_medium_profile: str) -> str:
    strict_profile = _legacy_stage_profile(
        plan,
        stage_id="final_integrated_closeout",
        review_tier="STRICT",
    )
    if strict_profile:
        return strict_profile
    final_stage = next(
        (
            dict(stage)
            for stage in plan.get("stages") or []
            if str(stage.get("stage_id") or "") == "final_integrated_closeout"
        ),
        {},
    )
    final_review_tier = str(final_stage.get("review_tier") or "").strip()
    if final_review_tier == "MEDIUM":
        return bounded_medium_profile or str(final_stage.get("agent_profile") or "").strip()
    return ""


def _duplicate_paths(scope_paths: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for path in scope_paths:
        rel = str(path)
        if rel in seen:
            duplicates.add(rel)
            continue
        seen.add(rel)
    return sorted(duplicates)


def _validate_distinct_scope_paths(
    *,
    repo_root: Path,
    field_name: str,
    scope_paths: Sequence[str | Path],
    require_non_empty: bool = False,
) -> list[str]:
    canonical_scope_paths = _canonicalize_scope_paths(
        repo_root=repo_root,
        scope_paths=scope_paths,
        field_name=field_name,
        require_non_empty=require_non_empty,
    )
    duplicates = _duplicate_paths(canonical_scope_paths)
    if duplicates:
        raise ValueError(f"{field_name} must not repeat paths; duplicates: {', '.join(duplicates)}")
    return canonical_scope_paths


def _validate_scope_fingerprint(
    *,
    repo_root: Path,
    scope_paths: Sequence[str],
    fingerprint: str,
    field_name: str,
) -> None:
    expected = compute_review_scope_fingerprint(repo_root=repo_root, scope_paths=scope_paths)
    if fingerprint != expected:
        raise ValueError(
            f"{field_name} must match the repository-byte fingerprint of its scope_paths"
        )


def _node(
    node_id: str,
    loop_id: str,
    *,
    role: str | None = None,
    allow_terminal_predecessors: bool = False,
) -> dict[str, Any]:
    node: dict[str, Any] = {"node_id": node_id, "loop_id": loop_id}
    if role is not None:
        node["role"] = role
    if allow_terminal_predecessors:
        node["allow_terminal_predecessors"] = True
    return node


def _edge(src: str, dst: str, kind: str) -> dict[str, str]:
    return {"from": src, "to": dst, "kind": kind}


def _resource(resource_id: str, resource_class: str) -> dict[str, str]:
    if resource_class not in _RESOURCE_CLASS_VALUES:
        raise ValueError(f"unsupported resource class: {resource_class}")
    return {"resource_id": resource_id, "resource_class": resource_class}


def _bundle(
    *,
    preset_id: str,
    graph_spec: dict[str, Any],
    resource_manifest: list[dict[str, str]],
    composition_notes: dict[str, Any],
    stage_manifest: list[dict[str, Any]],
    reconciliation_contract: dict[str, Any],
) -> dict[str, Any]:
    return {
        "preset_id": preset_id,
        "graph_spec": _validate_graph_shape(graph_spec),
        "resource_manifest": list(resource_manifest),
        "composition_notes": dict(composition_notes),
        "stage_manifest": [dict(entry) for entry in stage_manifest],
        "reconciliation_contract": dict(reconciliation_contract),
    }


def _validate_graph_shape(graph_spec: dict[str, Any]) -> dict[str, Any]:
    graph = dict(graph_spec)
    if graph.get("version") != "1":
        raise ValueError("graph_spec.version must be '1'")
    if graph.get("graph_mode") not in _GRAPH_MODE_VALUES:
        raise ValueError("graph_spec.graph_mode must be STATIC_USER_MODE or SYSTEM_EXCEPTION_MODE")
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    if not nodes:
        raise ValueError("graph_spec.nodes must be non-empty")

    node_ids: set[str] = set()
    for node in nodes:
        node_id = str(node.get("node_id") or "").strip()
        loop_id = str(node.get("loop_id") or "").strip()
        if not node_id or not loop_id:
            raise ValueError("each node requires node_id and loop_id")
        if node_id in node_ids:
            raise ValueError(f"duplicate node_id: {node_id}")
        node_ids.add(node_id)

    for edge in edges:
        src = str(edge.get("from") or "").strip()
        dst = str(edge.get("to") or "").strip()
        kind = str(edge.get("kind") or "").strip()
        if not src or not dst or not kind:
            raise ValueError("each edge requires from/to/kind")
        if src not in node_ids or dst not in node_ids:
            raise ValueError(f"edge references unknown node: {src}->{dst}")

    return graph


def _required_stage(strategy_plan: dict[str, Any], stage_id: str) -> dict[str, Any]:
    matches = [
        dict(stage)
        for stage in strategy_plan.get("stages") or []
        if str(stage.get("stage_id") or "") == stage_id
    ]
    if not matches:
        raise ValueError(f"strategy_plan missing required stage `{stage_id}`")
    if len(matches) != 1:
        raise ValueError(f"strategy_plan.stages must contain exactly one `{stage_id}` entry")
    return matches[0]


def _validate_stage_descriptor(stage_id: str, stage: dict[str, Any]) -> None:
    actual_keys = set(stage)
    allowed_keys = _STAGE_ALLOWED_KEYS[stage_id]
    missing_keys = sorted(allowed_keys - actual_keys)
    unexpected_keys = sorted(actual_keys - allowed_keys)
    if missing_keys or unexpected_keys:
        detail: list[str] = []
        if missing_keys:
            detail.append("missing keys: " + ", ".join(missing_keys))
        if unexpected_keys:
            detail.append("unexpected keys: " + ", ".join(unexpected_keys))
        raise ValueError(
            f"strategy_plan.{stage_id} must preserve the helper-authored stage descriptor shape exactly; "
            + "; ".join(detail)
        )
    for field_name, expected_value in _STAGE_STATIC_FIELDS[stage_id].items():
        actual_value = stage.get(field_name)
        if actual_value != expected_value:
            raise ValueError(
                f"strategy_plan.{stage_id}.{field_name} must remain `{expected_value}` in authoritative replay plans"
            )
    if stage_id == "final_integrated_closeout":
        review_tier = str(stage.get("review_tier") or "")
        if review_tier not in {"LOW", "MEDIUM", "STRICT"}:
            raise ValueError(
                "strategy_plan.final_integrated_closeout.review_tier must be `LOW`, `MEDIUM`, or `STRICT`"
            )


def _set_stage(strategy_plan: dict[str, Any], stage: dict[str, Any]) -> None:
    stage_id = str(stage.get("stage_id") or "")
    strategy_plan["stages"] = [
        dict(stage) if str(existing.get("stage_id") or "") == stage_id else dict(existing)
        for existing in strategy_plan.get("stages") or []
    ]


def _merge_partition_scope_paths(
    *,
    partitions: Sequence[dict[str, Any]],
    partition_ids: Sequence[str],
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    partitions_by_id = {str(part.get("partition_id") or ""): dict(part) for part in partitions}
    for partition_id in [str(pid) for pid in partition_ids]:
        part = partitions_by_id.get(partition_id)
        if part is None:
            continue
        for raw in part.get("scope_paths") or []:
            rel = str(raw)
            if rel in seen:
                continue
            seen.add(rel)
            merged.append(rel)
    return merged


def _partition_order_key(partition_id: str) -> tuple[int, str]:
    match = _PARTITION_ID_SEQUENCE.match(str(partition_id))
    if match:
        return (int(match.group(1)), str(partition_id))
    return (10**9, str(partition_id))


def _helper_partition_group_slug(group: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(group).strip())
    safe = safe.strip("._")
    return safe or "scope"


def _partition_scope_group(scope_paths: Sequence[str]) -> str:
    groups = sorted({str(path).split("/", 1)[0] for path in scope_paths})
    if len(groups) != 1:
        raise ValueError(
            "strategy_plan.partitions.*.scope_paths must stay within exactly one helper-derived top-level group"
        )
    return groups[0]


def _partition_boundary_projection(partitions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "scope_paths": [str(path) for path in part.get("scope_paths") or []],
            "scope_fingerprint": str(part.get("scope_fingerprint") or ""),
        }
        for part in partitions
    ]


def _infer_partitioning_policy(
    *,
    repo_root: Path,
    full_scope_paths: Sequence[str],
    partitions: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    if not full_scope_paths or not partitions:
        return None
    max_candidate = max(len(full_scope_paths), 1)
    expected_projection = _partition_boundary_projection(partitions)
    for max_files_per_partition in range(1, max_candidate + 1):
        candidate = partition_review_scope_paths(
            repo_root=repo_root,
            scope_paths=full_scope_paths,
            max_files_per_partition=max_files_per_partition,
        )
        if _partition_boundary_projection(candidate) == expected_projection:
            return {
                "group_by": "TOP_LEVEL_SCOPE_PREFIX",
                "max_files_per_partition": max_files_per_partition,
            }
    return None


def _expected_helper_partition_ids(
    *,
    partitions: Sequence[dict[str, Any]],
    full_scope_paths: Sequence[str],
) -> tuple[list[int], list[str]]:
    total_partitions = len(partitions)
    width = max(2, len(str(total_partitions)))
    grouped_entries: dict[str, list[tuple[int, list[str]]]] = {}
    for idx, part in enumerate(partitions):
        scope_paths = [str(path) for path in part.get("scope_paths") or []]
        group = _partition_scope_group(scope_paths)
        grouped_entries.setdefault(group, []).append((idx, scope_paths))

    canonical_indices: list[int] = []
    expected_partition_ids: list[str] = []
    counter = 1
    for group in sorted(grouped_entries):
        entries = sorted(grouped_entries[group], key=lambda item: item[1][0])
        expected_group_scope = [
            str(path)
            for path in full_scope_paths
            if str(path).split("/", 1)[0] == group
        ]
        actual_group_scope = [path for _, scope_paths in entries for path in scope_paths]
        group_scope_mismatch = _exact_scope_sequence_mismatch(
            expected=expected_group_scope,
            actual=actual_group_scope,
        )
        if group_scope_mismatch is not None:
            raise ValueError(
                "strategy_plan.partitions must preserve the helper-derived scope chunking exactly within each "
                f"top-level group `{group}`; {group_scope_mismatch}"
            )
        group_slug = _helper_partition_group_slug(group)
        multi_chunk_group = len(entries) > 1
        for chunk_idx, (original_index, _) in enumerate(entries, start=1):
            canonical_indices.append(original_index)
            suffix = f"_{chunk_idx:02d}" if multi_chunk_group else ""
            expected_partition_ids.append(
                f"part_{counter:0{width}d}_{group_slug}{suffix}"
            )
            counter += 1
    return canonical_indices, expected_partition_ids


def _exact_scope_sequence_mismatch(*, expected: Sequence[str], actual: Sequence[str]) -> str | None:
    expected_list = [str(path) for path in expected]
    actual_list = [str(path) for path in actual]
    if actual_list == expected_list:
        return None
    unexpected = sorted(set(actual_list) - set(expected_list))
    missing = sorted(set(expected_list) - set(actual_list))
    detail: list[str] = []
    if unexpected:
        detail.append("unexpected paths: " + ", ".join(unexpected))
    if missing:
        detail.append("missing expected paths: " + ", ".join(missing))
    if not unexpected and not missing:
        detail.append("path order differs from the frozen authoritative lineage")
    return "; ".join(detail)


def _canonical_selected_partition_lineage(
    *,
    partitions: Sequence[dict[str, Any]],
    authoritative_partition_ids: Sequence[str],
    selected_partition_ids: Sequence[str],
    narrowed_scope_paths: Sequence[str],
) -> list[str]:
    narrowed_scope_set = {str(path) for path in narrowed_scope_paths}
    partitions_by_id = {str(part.get("partition_id") or ""): dict(part) for part in partitions}
    selected_partition_id_set = {str(pid) for pid in selected_partition_ids}
    lineage: list[str] = []
    seen: set[str] = set()
    for partition_id in [str(pid) for pid in authoritative_partition_ids]:
        if partition_id not in selected_partition_id_set:
            continue
        part = partitions_by_id.get(partition_id)
        if part is None:
            continue
        for raw in sorted(dict.fromkeys(str(path) for path in (part.get("scope_paths") or []))):
            rel = str(raw)
            if rel not in narrowed_scope_set or rel in seen:
                continue
            seen.add(rel)
            lineage.append(rel)
    return lineage


def _validate_strategy_plan(
    *,
    repo_root: str | Path,
    strategy_plan: dict[str, Any],
    allow_historical_strategy_replay: bool = False,
) -> dict[str, Any]:
    repo_root = _normalize_repo_root(repo_root)
    raw_plan = dict(strategy_plan)
    plan = dict(strategy_plan)
    plan.pop("_legacy_strategy_fingerprint_omit_keys", None)
    raw_closeout_policy = raw_plan.get("closeout_policy", {})
    raw_closeout_policy = raw_closeout_policy if isinstance(raw_closeout_policy, dict) else {}
    caller_legacy_fingerprint_omit_keys = _normalize_supported_legacy_omit_keys(
        strategy_plan.get("_legacy_strategy_fingerprint_omit_keys") or []
    )
    current_policy_provenance_present = bool(str(raw_closeout_policy.get("review_tier_policy") or "").strip())
    plan["partitions"] = [dict(part) for part in plan.get("partitions") or []]
    plan["stages"] = [dict(stage) for stage in plan.get("stages") or []]
    legacy_fingerprint_omit_keys: list[str] = []
    eligible_legacy_omit_keys: list[str] = []
    for key in _LEGACY_FINGERPRINT_OMITTABLE_TOP_LEVEL_KEYS:
        if key not in raw_plan:
            eligible_legacy_omit_keys.append(key)
    eligible_legacy_omit_key_set = set(eligible_legacy_omit_keys)
    if current_policy_provenance_present:
        missing_or_blank_profile_keys = [
            key
            for key in ("bounded_medium_profile", "strict_exception_profile")
            if not str(raw_plan.get(key) or "").strip()
        ]
        if missing_or_blank_profile_keys:
            raise ValueError(
                "current strategies with closeout_policy.review_tier_policy must preserve explicit top-level reviewer-profile provenance; missing or blank: "
                + ", ".join(missing_or_blank_profile_keys)
            )
        raw_partitioning_policy = raw_plan.get("partitioning_policy")
        if not isinstance(raw_partitioning_policy, dict) or not raw_partitioning_policy:
            raise ValueError(
                "current strategies with closeout_policy.review_tier_policy must preserve explicit top-level partitioning_policy provenance"
            )
    if str(plan.get("version") or "") != "1":
        raise ValueError("strategy_plan.version must be '1'")
    if str(plan.get("strategy_id") or "").strip() != _PYRAMID_STRATEGY_ID:
        raise ValueError(f"strategy_plan.strategy_id must be `{_PYRAMID_STRATEGY_ID}`")
    if not str(plan.get("agent_provider_id") or "").strip():
        raise ValueError("strategy_plan.agent_provider_id must be non-empty")
    bounded_medium_profile = str(plan.get("bounded_medium_profile") or "").strip()
    if not bounded_medium_profile:
        bounded_medium_profile = (
            _legacy_stage_profile(plan, stage_id="final_integrated_closeout", review_tier="MEDIUM")
            or _legacy_stage_profile(plan, stage_id="deep_partition_followup")
        )
        if not bounded_medium_profile:
            raise ValueError("strategy_plan.bounded_medium_profile must be non-empty")
        plan["bounded_medium_profile"] = bounded_medium_profile
    strict_exception_profile = str(plan.get("strict_exception_profile") or "").strip()
    if not strict_exception_profile:
        strict_exception_profile = _legacy_strict_exception_profile(
            plan,
            bounded_medium_profile=bounded_medium_profile,
        )
        if not strict_exception_profile:
            raise ValueError("strategy_plan.strict_exception_profile must be non-empty")
        plan["strict_exception_profile"] = strict_exception_profile
    full_scope_paths = _validate_distinct_scope_paths(
        repo_root=repo_root,
        field_name="strategy_plan.full_scope_paths",
        scope_paths=[str(path) for path in plan.get("full_scope_paths") or []],
        require_non_empty=True,
    )
    canonical_full_scope_paths = sorted(full_scope_paths)
    if full_scope_paths != canonical_full_scope_paths:
        raise ValueError(
            "strategy_plan.full_scope_paths must preserve canonical repo-relative file order"
        )
    plan["full_scope_paths"] = full_scope_paths
    if not str(plan.get("full_scope_fingerprint") or "").strip():
        raise ValueError("strategy_plan.full_scope_fingerprint must be non-empty")
    partitioning_policy = dict(plan.get("partitioning_policy") or {})
    if not partitioning_policy:
        inferred_partitioning_policy = _infer_partitioning_policy(
            repo_root=repo_root,
            full_scope_paths=full_scope_paths,
            partitions=plan["partitions"],
        )
        if inferred_partitioning_policy is not None:
            partitioning_policy = inferred_partitioning_policy
            plan["partitioning_policy"] = dict(inferred_partitioning_policy)
    actual_partitioning_policy_keys = set(partitioning_policy)
    missing_partitioning_policy_keys = sorted(_PARTITIONING_POLICY_ALLOWED_KEYS - actual_partitioning_policy_keys)
    unexpected_partitioning_policy_keys = sorted(actual_partitioning_policy_keys - _PARTITIONING_POLICY_ALLOWED_KEYS)
    if missing_partitioning_policy_keys or unexpected_partitioning_policy_keys:
        detail: list[str] = []
        if missing_partitioning_policy_keys:
            detail.append("missing keys: " + ", ".join(missing_partitioning_policy_keys))
        if unexpected_partitioning_policy_keys:
            detail.append("unexpected keys: " + ", ".join(unexpected_partitioning_policy_keys))
        raise ValueError(
            "strategy_plan.partitioning_policy must preserve the helper-authored partitioning policy shape exactly; "
            + "; ".join(detail)
        )
    if str(partitioning_policy.get("group_by") or "") != "TOP_LEVEL_SCOPE_PREFIX":
        raise ValueError(
            "strategy_plan.partitioning_policy.group_by must remain `TOP_LEVEL_SCOPE_PREFIX` in authoritative replay plans"
        )
    raw_max_files_per_partition = partitioning_policy.get("max_files_per_partition")
    if isinstance(raw_max_files_per_partition, bool) or not isinstance(raw_max_files_per_partition, int):
        raise ValueError(
            "strategy_plan.partitioning_policy.max_files_per_partition must remain a positive integer policy field"
        )
    max_files_per_partition = int(raw_max_files_per_partition)
    if max_files_per_partition <= 0:
        raise ValueError(
            "strategy_plan.partitioning_policy.max_files_per_partition must be an integer >= 1"
        )
    partitions = [dict(part) for part in plan.get("partitions") or []]
    if not partitions:
        raise ValueError("strategy_plan.partitions must be non-empty")
    partition_id_list = [str(part.get("partition_id") or "") for part in partitions]
    partition_ids = set(partition_id_list)
    if "" in partition_ids:
        raise ValueError("strategy_plan.partitions entries must carry non-empty partition_id")
    duplicate_partition_ids = sorted(pid for pid in partition_ids if pid and partition_id_list.count(pid) > 1)
    if duplicate_partition_ids:
        raise ValueError(
            "strategy_plan.partitions entries must carry unique partition_id values; duplicate ids: "
            + ", ".join(duplicate_partition_ids)
        )
    empty_partition_scopes = sorted(
        str(part.get("partition_id") or "")
        for part in partitions
        if not [str(path) for path in part.get("scope_paths") or []]
    )
    if empty_partition_scopes:
        raise ValueError(
            "strategy_plan.partitions.*.scope_paths must be non-empty; empty for: "
            + ", ".join(empty_partition_scopes)
        )
    blank_partition_scope_fingerprints = sorted(
        str(part.get("partition_id") or "")
        for part in partitions
        if not str(part.get("scope_fingerprint") or "").strip()
    )
    if blank_partition_scope_fingerprints:
        raise ValueError(
            "strategy_plan.partitions.*.scope_fingerprint must be non-empty; blank for: "
            + ", ".join(blank_partition_scope_fingerprints)
        )
    partition_scope_index: dict[str, set[str]] = {}
    for idx, part in enumerate(partitions):
        partition_id = str(part.get("partition_id") or "")
        scope_paths = _validate_distinct_scope_paths(
            repo_root=repo_root,
            field_name="strategy_plan.partitions.*.scope_paths",
            scope_paths=[str(path) for path in part.get("scope_paths") or []],
            require_non_empty=True,
        )
        canonical_partition_scope_paths = sorted(scope_paths)
        if scope_paths != canonical_partition_scope_paths:
            raise ValueError(
                "strategy_plan.partitions.*.scope_paths must preserve canonical repo-relative "
                "file order within each partition"
            )
        part["scope_paths"] = scope_paths
        partitions[idx] = part
        partition_scope_index[partition_id] = set(scope_paths)
        _validate_scope_fingerprint(
            repo_root=repo_root,
            scope_paths=scope_paths,
            fingerprint=str(part.get("scope_fingerprint") or ""),
            field_name="strategy_plan.partitions.*.scope_fingerprint",
        )
    overlapping_partition_paths = sorted(
        path
        for path in sorted({rel for paths in partition_scope_index.values() for rel in paths})
        if sum(1 for scope_paths in partition_scope_index.values() if path in scope_paths) > 1
    )
    if overlapping_partition_paths:
        raise ValueError(
            "strategy_plan.partitions must be disjoint across partition_id values; overlapping paths: "
            + ", ".join(overlapping_partition_paths)
        )
    partition_scope_union = sorted({rel for paths in partition_scope_index.values() for rel in paths})
    partition_scope_outside_full = sorted(set(partition_scope_union) - set(full_scope_paths))
    missing_partition_scope_paths = sorted(set(full_scope_paths) - set(partition_scope_union))
    if partition_scope_outside_full or missing_partition_scope_paths:
        detail: list[str] = []
        if partition_scope_outside_full:
            detail.append("unexpected paths: " + ", ".join(partition_scope_outside_full))
        if missing_partition_scope_paths:
            detail.append("missing full-scope paths: " + ", ".join(missing_partition_scope_paths))
        raise ValueError(
            "strategy_plan.partitions.*.scope_paths must form an exact cover of full_scope_paths; "
            + "; ".join(detail)
        )
    expected_partitions = partition_review_scope_paths(
        repo_root=repo_root,
        scope_paths=full_scope_paths,
        max_files_per_partition=max_files_per_partition,
    )
    if _partition_boundary_projection(partitions) != _partition_boundary_projection(expected_partitions):
        raise ValueError(
            "strategy_plan.partitions must match the helper-generated partition boundaries exactly for the declared "
            "partitioning_policy"
        )
    if not str(plan.get("full_scope_fingerprint") or "").strip():
        raise ValueError("strategy_plan.full_scope_fingerprint must be non-empty")
    _validate_scope_fingerprint(
        repo_root=repo_root,
        scope_paths=full_scope_paths,
        fingerprint=str(plan.get("full_scope_fingerprint") or ""),
        field_name="strategy_plan.full_scope_fingerprint",
    )
    canonical_partition_indices, canonical_partition_id_list = _expected_helper_partition_ids(
        partitions=partitions,
        full_scope_paths=full_scope_paths,
    )
    if canonical_partition_indices != list(range(len(partitions))):
        raise ValueError(
            "strategy_plan.partitions must preserve canonical helper-derived partition order from "
            "partition scope chunking"
        )
    if partition_id_list != canonical_partition_id_list:
        raise ValueError(
            "strategy_plan.partitions[*].partition_id must preserve the canonical helper-derived routing ids "
            "exactly, including zero-padded numeric prefixes and safe slug formatting"
        )
    plan["partitions"] = partitions
    stage_id_list = [str(stage.get("stage_id") or "") for stage in plan.get("stages") or []]
    if not stage_id_list:
        raise ValueError("strategy_plan.stages must be non-empty")
    if "" in stage_id_list:
        raise ValueError("strategy_plan.stages entries must carry non-empty stage_id")
    duplicate_stage_ids = sorted(
        stage_id
        for stage_id in set(stage_id_list)
        if stage_id and stage_id_list.count(stage_id) > 1
    )
    if duplicate_stage_ids:
        raise ValueError(
            "strategy_plan.stages must contain unique stage_id values; duplicate ids: "
            + ", ".join(duplicate_stage_ids)
        )
    unknown_stage_ids = sorted(set(stage_id_list) - set(_REQUIRED_STAGE_IDS))
    if unknown_stage_ids:
        raise ValueError(
            "strategy_plan.stages must only contain supported stage_id values; unknown ids: "
            + ", ".join(unknown_stage_ids)
        )
    missing_stage_ids = sorted(set(_REQUIRED_STAGE_IDS) - set(stage_id_list))
    if missing_stage_ids:
        raise ValueError(
            "strategy_plan.stages must contain exactly one each of the required stage ids; missing: "
            + ", ".join(missing_stage_ids)
        )
    if stage_id_list != list(_REQUIRED_STAGE_IDS):
        raise ValueError(
            "strategy_plan.stages must preserve the canonical helper-authored stage order exactly"
        )
    for stage_id in _REQUIRED_STAGE_IDS:
        _validate_stage_descriptor(stage_id, _required_stage(plan, stage_id))
    effective_scope_paths = _validate_distinct_scope_paths(
        repo_root=repo_root,
        field_name="strategy_plan.effective_scope_paths",
        scope_paths=[str(path) for path in plan.get("effective_scope_paths") or []],
        require_non_empty=True,
    )
    plan["effective_scope_paths"] = effective_scope_paths
    effective_scope_fingerprint = str(plan.get("effective_scope_fingerprint") or "")
    if not effective_scope_fingerprint.strip():
        raise ValueError("strategy_plan.effective_scope_fingerprint must be non-empty")
    _validate_scope_fingerprint(
        repo_root=repo_root,
        scope_paths=effective_scope_paths,
        fingerprint=effective_scope_fingerprint,
        field_name="strategy_plan.effective_scope_fingerprint",
    )
    for stage_id in ("fast_partition_scan", "deep_partition_followup", "final_integrated_closeout"):
        _required_stage(plan, stage_id)
    fast_stage = _required_stage(plan, "fast_partition_scan")
    if not str(fast_stage.get("agent_profile") or "").strip():
        raise ValueError("strategy_plan.fast_partition_scan.agent_profile must be non-empty")
    fast_partition_ids = [str(pid) for pid in fast_stage.get("partition_ids") or []]
    if not fast_partition_ids:
        raise ValueError("strategy_plan.fast_partition_scan.partition_ids must be non-empty")
    missing_fast_partition_ids = sorted(set(fast_partition_ids) - partition_ids)
    if missing_fast_partition_ids:
        raise ValueError(
            "strategy_plan.fast_partition_scan.partition_ids must be a subset of strategy_plan.partitions; "
            f"unknown ids: {', '.join(missing_fast_partition_ids)}"
        )
    canonical_fast_partition_ids = [pid for pid in canonical_partition_id_list if pid in set(fast_partition_ids)]
    if fast_partition_ids != canonical_fast_partition_ids:
        raise ValueError(
            "strategy_plan.fast_partition_scan.partition_ids must preserve the canonical "
            "strategy_plan.partitions order exactly"
        )
    fast_partition_scope_paths = {
        str(path)
        for part in partitions
        if str(part.get("partition_id") or "") in set(fast_partition_ids)
        for path in (part.get("scope_paths") or [])
    }
    fast_partition_scope_lineage = _merge_partition_scope_paths(
        partitions=partitions,
        partition_ids=fast_partition_ids,
    )
    fast_scope_paths_outside_full = sorted(fast_partition_scope_paths - set(str(path) for path in plan.get("full_scope_paths") or []))
    if fast_scope_paths_outside_full:
        raise ValueError(
            "strategy_plan.fast_partition_scan lineage must stay within full_scope_paths; "
            f"unexpected paths: {', '.join(fast_scope_paths_outside_full)}"
        )
    deep_stage = _required_stage(plan, "deep_partition_followup")
    deep_partition_ids = [str(pid) for pid in deep_stage.get("partition_ids") or []]
    if deep_partition_ids and not str(deep_stage.get("agent_profile") or "").strip():
        raise ValueError("strategy_plan.deep_partition_followup.agent_profile must be non-empty")
    if [str(pid) for pid in plan.get("selected_partition_ids") or []] != deep_partition_ids:
        raise ValueError(
            "strategy_plan.selected_partition_ids must match deep_partition_followup.partition_ids exactly"
        )
    deep_scope_paths = _validate_distinct_scope_paths(
        repo_root=repo_root,
        field_name="strategy_plan.deep_partition_followup.scope_paths",
        scope_paths=[str(path) for path in deep_stage.get("scope_paths") or []],
    )
    deep_stage["scope_paths"] = deep_scope_paths
    _set_stage(plan, deep_stage)
    deep_scope_fingerprint = str(deep_stage.get("scope_fingerprint") or "")
    if deep_partition_ids and not deep_scope_fingerprint.strip():
        raise ValueError("strategy_plan.deep_partition_followup.scope_fingerprint must be non-empty when partition_ids is non-empty")
    if deep_partition_ids:
        _validate_scope_fingerprint(
            repo_root=repo_root,
            scope_paths=deep_scope_paths,
            fingerprint=deep_scope_fingerprint,
            field_name="strategy_plan.deep_partition_followup.scope_fingerprint",
        )
    missing_deep_partition_ids = sorted(set(deep_partition_ids) - partition_ids)
    if missing_deep_partition_ids:
        raise ValueError(
            "strategy_plan.deep_partition_followup.partition_ids must be a subset of strategy_plan.partitions; "
            f"unknown ids: {', '.join(missing_deep_partition_ids)}"
        )
    deep_partition_ids_outside_fast_stage = sorted(set(deep_partition_ids) - set(fast_partition_ids))
    if deep_partition_ids_outside_fast_stage:
        raise ValueError(
            "strategy_plan.deep_partition_followup.partition_ids must stay within the frozen "
            "fast_partition_scan.partition_ids subset; "
            f"unexpected ids: {', '.join(deep_partition_ids_outside_fast_stage)}"
        )
    canonical_deep_partition_ids = [pid for pid in fast_partition_ids if pid in set(deep_partition_ids)]
    if deep_partition_ids != canonical_deep_partition_ids:
        raise ValueError(
            "strategy_plan.deep_partition_followup.partition_ids must preserve the frozen "
            "fast_partition_scan.partition_ids order exactly"
        )
    deep_candidate_partition_ids = [str(pid) for pid in deep_stage.get("candidate_partition_ids") or []]
    missing_deep_candidate_partition_ids = sorted(set(deep_candidate_partition_ids) - partition_ids)
    if missing_deep_candidate_partition_ids:
        raise ValueError(
            "strategy_plan.deep_partition_followup.candidate_partition_ids must be a subset of strategy_plan.partitions; "
            f"unknown ids: {', '.join(missing_deep_candidate_partition_ids)}"
        )
    deep_candidate_partition_ids_outside_fast_stage = sorted(set(deep_candidate_partition_ids) - set(fast_partition_ids))
    if deep_candidate_partition_ids_outside_fast_stage:
        raise ValueError(
            "strategy_plan.deep_partition_followup.candidate_partition_ids must stay within the frozen "
            "fast_partition_scan.partition_ids subset; "
            f"unexpected ids: {', '.join(deep_candidate_partition_ids_outside_fast_stage)}"
        )
    missing_selected_deep_candidate_partition_ids = sorted(set(deep_partition_ids) - set(deep_candidate_partition_ids))
    if missing_selected_deep_candidate_partition_ids:
        raise ValueError(
            "strategy_plan.deep_partition_followup.candidate_partition_ids must cover every selected deep partition id; "
            f"missing ids: {', '.join(missing_selected_deep_candidate_partition_ids)}"
        )
    final_stage = _required_stage(plan, "final_integrated_closeout")
    if not str(final_stage.get("agent_profile") or "").strip():
        raise ValueError("strategy_plan.final_integrated_closeout.agent_profile must be non-empty")
    final_review_tier = str(final_stage.get("review_tier") or "")
    final_agent_profile = str(final_stage.get("agent_profile") or "")
    closeout_policy = dict(plan.get("closeout_policy") or {})
    review_tier_policy = str(closeout_policy.get("review_tier_policy") or "").strip()
    if "review_tier_policy" in closeout_policy and not review_tier_policy:
        raise ValueError("strategy_plan.closeout_policy.review_tier_policy must be non-empty when provided")
    if (
        final_review_tier in {"MEDIUM", "STRICT"}
        and not review_tier_policy
        and not allow_historical_strategy_replay
    ):
        raise ValueError(
            "missing strategy_plan.closeout_policy.review_tier_policy is rejected on the default authoritative replay path; "
            "pass allow_historical_strategy_replay=True only for supported legacy strategy plans"
        )
    if review_tier_policy == "LOW_ONLY" and final_review_tier != "LOW":
        raise ValueError(
            "LOW_ONLY closeout policy requires strategy_plan.final_integrated_closeout.review_tier=`LOW`"
        )
    if final_review_tier == "MEDIUM" and bounded_medium_profile and final_agent_profile != bounded_medium_profile:
        raise ValueError(
            "strategy_plan.final_integrated_closeout.agent_profile must match the bounded medium "
            "escalation profile exactly when review_tier is `MEDIUM`"
        )
    if final_review_tier == "LOW":
        if review_tier_policy != "LOW_ONLY":
            raise ValueError(
                "LOW closeout strategies require closeout_policy.review_tier_policy=`LOW_ONLY`"
            )
        if deep_partition_ids:
            raise ValueError(
                "LOW authoritative closeout requires deep_partition_followup.partition_ids to be empty"
            )
        fast_stage_profile = str(fast_stage.get("agent_profile") or "").strip()
        if final_agent_profile != fast_stage_profile:
            raise ValueError(
                "strategy_plan.final_integrated_closeout.agent_profile must match "
                "strategy_plan.fast_partition_scan.agent_profile exactly when review_tier is `LOW`"
            )
    if final_review_tier == "STRICT":
        if final_agent_profile != strict_exception_profile:
            raise ValueError(
                "strategy_plan.final_integrated_closeout.agent_profile must match "
                "strategy_plan.strict_exception_profile exactly when review_tier is `STRICT`"
            )
    final_scope_paths = _validate_distinct_scope_paths(
        repo_root=repo_root,
        field_name="strategy_plan.final_integrated_closeout.scope_paths",
        scope_paths=[str(path) for path in final_stage.get("scope_paths") or []],
    )
    final_stage["scope_paths"] = final_scope_paths
    _set_stage(plan, final_stage)
    final_scope_mismatch = _exact_scope_sequence_mismatch(
        expected=effective_scope_paths,
        actual=final_scope_paths,
    )
    if final_scope_mismatch is not None:
        raise ValueError(
            "strategy_plan.final_integrated_closeout.scope_paths must match the effective main scope exactly; "
            + final_scope_mismatch
        )
    final_scope_fingerprint = str(final_stage.get("scope_fingerprint") or "")
    if not final_scope_fingerprint:
        raise ValueError("strategy_plan.final_integrated_closeout.scope_fingerprint must be non-empty")
    _validate_scope_fingerprint(
        repo_root=repo_root,
        scope_paths=final_scope_paths,
        fingerprint=final_scope_fingerprint,
        field_name="strategy_plan.final_integrated_closeout.scope_fingerprint",
    )
    if effective_scope_fingerprint and final_scope_fingerprint != effective_scope_fingerprint:
        raise ValueError(
            "strategy_plan.final_integrated_closeout.scope_fingerprint must match effective_scope_fingerprint"
        )
    effective_scope_source = str(plan.get("effective_scope_source") or "")
    if not effective_scope_source:
        raise ValueError("strategy_plan.effective_scope_source must be non-empty")
    final_scope_source = str(final_stage.get("scope_source") or "")
    if effective_scope_source != final_scope_source:
        raise ValueError(
            "strategy_plan.effective_scope_source must match final_integrated_closeout.scope_source"
        )
    if effective_scope_source not in _EFFECTIVE_SCOPE_SOURCE_VALUES:
        raise ValueError(
            "strategy_plan.effective_scope_source/final_integrated_closeout.scope_source must use a canonical "
            "helper-authored provenance label"
        )
    if deep_partition_ids and effective_scope_source == "FULL_SCOPE_AFTER_EMPTY_FOLLOWUP":
        raise ValueError(
            "strategy_plan.effective_scope_source/final_integrated_closeout.scope_source must not be "
            "`FULL_SCOPE_AFTER_EMPTY_FOLLOWUP` when deep_partition_followup.partition_ids is non-empty"
        )
    if not deep_partition_ids:
        if effective_scope_source != "FULL_SCOPE_AFTER_EMPTY_FOLLOWUP":
            raise ValueError(
                "strategy_plan.effective_scope_source/final_integrated_closeout.scope_source must be "
                "`FULL_SCOPE_AFTER_EMPTY_FOLLOWUP` when deep_partition_followup.partition_ids=[]"
            )
        if deep_scope_paths:
            raise ValueError(
                "strategy_plan.deep_partition_followup.scope_paths must be empty when deep_partition_followup.partition_ids is empty"
            )
        no_followup_lineage_mismatch = _exact_scope_sequence_mismatch(
            expected=fast_partition_scope_lineage,
            actual=effective_scope_paths,
        )
        if no_followup_lineage_mismatch is not None:
            raise ValueError(
                "strategy_plan.effective_scope_paths must match the frozen fast_partition_scan lineage exactly when "
                "deep_partition_followup.partition_ids is empty; "
                + no_followup_lineage_mismatch
            )
    if deep_partition_ids:
        selected_partition_scope_paths = {
            str(path)
            for part in partitions
            if str(part.get("partition_id") or "") in set(deep_partition_ids)
            for path in (part.get("scope_paths") or [])
        }
        deep_scope_paths_outside_selected = sorted(set(deep_scope_paths) - selected_partition_scope_paths)
        if deep_scope_paths_outside_selected:
            raise ValueError(
                "strategy_plan.deep_partition_followup.scope_paths must stay within the selected "
                "deep_partition_followup.partition_ids lineage; "
                f"unexpected paths: {', '.join(deep_scope_paths_outside_selected)}"
            )
        partitions_without_deep_scope = sorted(
            str(part.get("partition_id") or "")
            for part in partitions
            if str(part.get("partition_id") or "") in set(deep_partition_ids)
            and not set(str(path) for path in (part.get("scope_paths") or [])) & set(deep_scope_paths)
        )
        if partitions_without_deep_scope:
            raise ValueError(
                "strategy_plan.deep_partition_followup.scope_paths must include at least one file from every selected "
                "deep_partition_followup.partition_ids partition; "
                f"missing coverage for: {', '.join(partitions_without_deep_scope)}"
            )
        canonical_selected_partition_lineage = _canonical_selected_partition_lineage(
            partitions=partitions,
            authoritative_partition_ids=fast_partition_ids,
            selected_partition_ids=deep_partition_ids,
            narrowed_scope_paths=deep_scope_paths,
        )
        deep_selected_partition_lineage_mismatch = _exact_scope_sequence_mismatch(
            expected=canonical_selected_partition_lineage,
            actual=deep_scope_paths,
        )
        if deep_selected_partition_lineage_mismatch is not None:
            raise ValueError(
                "strategy_plan.deep_partition_followup.scope_paths must match the canonical selected partition lineage exactly "
                "when deep_partition_followup.partition_ids is non-empty; "
                + deep_selected_partition_lineage_mismatch
            )
        final_scope_paths_outside_selected = sorted(set(final_scope_paths) - selected_partition_scope_paths)
        if final_scope_paths_outside_selected:
            raise ValueError(
                "strategy_plan.final_integrated_closeout.scope_paths must stay within the selected "
                "deep_partition_followup.partition_ids lineage; "
                f"unexpected paths: {', '.join(final_scope_paths_outside_selected)}"
            )
        deep_effective_mismatch = _exact_scope_sequence_mismatch(
            expected=deep_scope_paths,
            actual=effective_scope_paths,
        )
        if deep_effective_mismatch is not None:
            raise ValueError(
                "strategy_plan.effective_scope_paths and strategy_plan.deep_partition_followup.scope_paths must "
                "match exactly when deep_partition_followup.partition_ids is non-empty; "
                + deep_effective_mismatch
            )
    actual_closeout_policy_keys = set(closeout_policy)
    missing_closeout_policy_keys = sorted(_CLOSEOUT_POLICY_REQUIRED_KEYS - actual_closeout_policy_keys)
    unexpected_closeout_policy_keys = sorted(actual_closeout_policy_keys - _CLOSEOUT_POLICY_ALLOWED_KEYS)
    if missing_closeout_policy_keys or unexpected_closeout_policy_keys:
        detail: list[str] = []
        if missing_closeout_policy_keys:
            detail.append("missing keys: " + ", ".join(missing_closeout_policy_keys))
        if unexpected_closeout_policy_keys:
            detail.append("unexpected keys: " + ", ".join(unexpected_closeout_policy_keys))
        raise ValueError(
            "strategy_plan.closeout_policy must preserve the helper-authored closeout policy shape exactly; "
            + "; ".join(detail)
        )
    if str(closeout_policy.get("final_stage_id") or "") != "final_integrated_closeout":
        raise ValueError("strategy_plan.closeout_policy.final_stage_id must be `final_integrated_closeout`")
    if closeout_policy.get("intermediate_rounds_are_advisory") is not True:
        raise ValueError(
            "strategy_plan.closeout_policy.intermediate_rounds_are_advisory must remain `true` in authoritative replay plans"
        )
    if closeout_policy.get("requires_integrated_scope_closeout") is not True:
        raise ValueError(
            "strategy_plan.closeout_policy.requires_integrated_scope_closeout must remain `true` in authoritative replay plans"
        )
    review_tier_policy = str(closeout_policy.get("review_tier_policy") or "").strip()
    if review_tier_policy and review_tier_policy not in {"LOW_ONLY", "LOW_PLUS_MEDIUM"}:
        raise ValueError(
            "strategy_plan.closeout_policy.review_tier_policy must be `LOW_ONLY` or `LOW_PLUS_MEDIUM`"
        )
    historical_replay_allowed = allow_historical_strategy_replay and not current_policy_provenance_present
    strategy_fingerprint = str(plan.get("strategy_fingerprint") or "")
    if not strategy_fingerprint:
        raise ValueError("strategy_plan.strategy_fingerprint must be non-empty")
    expected_strategy_fingerprint = _expected_strategy_fingerprint(plan)
    legacy_boundary_equivalent_strategy_fingerprint = _expected_strategy_fingerprint(
        plan,
        canonicalize_partitioning_policy=False,
    )
    if strategy_fingerprint != expected_strategy_fingerprint:
        if (
            strategy_fingerprint == legacy_boundary_equivalent_strategy_fingerprint
            and legacy_boundary_equivalent_strategy_fingerprint != expected_strategy_fingerprint
            and dict(plan.get("partitioning_policy") or {})
            != _canonical_partitioning_policy_for_strategy_fingerprint(plan)
        ):
            pass
        elif (
            historical_replay_allowed
            and caller_legacy_fingerprint_omit_keys
            and set(caller_legacy_fingerprint_omit_keys).issubset(
            eligible_legacy_omit_key_set
            )
        ):
            if _legacy_omit_keys_consistent_with_plan(
                repo_root=repo_root,
                plan=plan,
                omit_keys=caller_legacy_fingerprint_omit_keys,
            ):
                candidate_fingerprint = _expected_strategy_fingerprint(
                    plan,
                    omit_top_level_keys=caller_legacy_fingerprint_omit_keys,
                )
                if strategy_fingerprint in _legacy_candidate_strategy_fingerprints(
                    plan,
                    omit_top_level_keys=caller_legacy_fingerprint_omit_keys,
                ):
                    legacy_fingerprint_omit_keys = caller_legacy_fingerprint_omit_keys
                else:
                    raise ValueError(
                        "strategy_plan.strategy_fingerprint must match the canonical hash of the authoritative "
                        "strategy-plan content that executable orchestration artifacts actually consume"
                    )
        elif historical_replay_allowed and not legacy_fingerprint_omit_keys:
            legacy_fingerprint_omit_keys = _matching_legacy_fingerprint_omit_keys(
                plan=plan,
                strategy_fingerprint=strategy_fingerprint,
                eligible_omit_keys=eligible_legacy_omit_keys,
            )
            legacy_expected_strategy_fingerprints = (
                _legacy_candidate_strategy_fingerprints(plan, omit_top_level_keys=legacy_fingerprint_omit_keys)
                if legacy_fingerprint_omit_keys
                else []
            )
            if not legacy_expected_strategy_fingerprints or strategy_fingerprint not in legacy_expected_strategy_fingerprints:
                raise ValueError(
                    "strategy_plan.strategy_fingerprint must match the canonical hash of the authoritative "
                    "strategy-plan content that executable orchestration artifacts actually consume"
                )
        else:
            raise ValueError(
                "strategy_plan.strategy_fingerprint must match the canonical hash of the authoritative "
                "strategy-plan content that executable orchestration artifacts actually consume"
            )
    if (
        final_review_tier in {"MEDIUM", "STRICT"}
        and not review_tier_policy
        and not legacy_fingerprint_omit_keys
    ):
        raise ValueError(
            "missing strategy_plan.closeout_policy.review_tier_policy may be replayed only for supported legacy strategy plans"
        )
    for key in legacy_fingerprint_omit_keys:
        if key in eligible_legacy_omit_key_set:
            plan.pop(key, None)
    return plan


def _partition_index(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(part["partition_id"]): dict(part) for part in plan.get("partitions") or []}


def _stage_manifest(*, repo_root: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    partitions = _partition_index(plan)
    fast_stage = _required_stage(plan, "fast_partition_scan")
    deep_stage = _required_stage(plan, "deep_partition_followup")
    final_stage = _required_stage(plan, "final_integrated_closeout")
    agent_provider_id = str(plan.get("agent_provider_id") or "")
    has_post_dedupe_advisory_stages = bool(deep_stage.get("partition_ids") or [])
    fast_stage_scope_paths = _merge_partition_scope_paths(
        partitions=list(partitions.values()),
        partition_ids=[str(pid) for pid in fast_stage.get("partition_ids") or []],
    )

    manifest: list[dict[str, Any]] = [
        {
            "node_id": "review_intake",
            "stage_id": "review_intake",
            "review_tier": "INTAKE",
            "agent_provider_id": agent_provider_id,
            "scope_paths": [str(path) for path in plan.get("full_scope_paths") or []],
            "scope_fingerprint": str(plan.get("full_scope_fingerprint") or ""),
            "closeout_authority": "NON_AUTHORITATIVE",
        }
    ]

    for partition_id in [str(pid) for pid in fast_stage.get("partition_ids") or []]:
        part = partitions[partition_id]
        manifest.append(
            {
                "node_id": f"fast_partition_scan__{partition_id}",
                "stage_id": "fast_partition_scan",
                "review_tier": "FAST",
                "agent_provider_id": agent_provider_id,
                "agent_profile": str(fast_stage.get("agent_profile") or ""),
                "partition_id": partition_id,
                "scope_paths": [str(path) for path in part.get("scope_paths") or []],
                "scope_fingerprint": str(part.get("scope_fingerprint") or ""),
                "closeout_authority": "ADVISORY_CONFIRM_REQUIRED",
            }
        )

    manifest.append(
        {
            "node_id": "finding_dedupe",
            "stage_id": "finding_dedupe",
            "review_tier": "RECONCILE",
            "agent_provider_id": agent_provider_id,
            "scope_paths": fast_stage_scope_paths,
            "scope_fingerprint": compute_review_scope_fingerprint(
                repo_root=repo_root,
                scope_paths=fast_stage_scope_paths,
            ),
            "selected_partition_ids": [str(pid) for pid in deep_stage.get("partition_ids") or []],
            "effective_scope_paths": [str(path) for path in final_stage.get("scope_paths") or []],
            "effective_scope_fingerprint": str(final_stage.get("scope_fingerprint") or ""),
            "closeout_authority": "NON_AUTHORITATIVE",
            "reconciliation_resource_id": "review.reconciliation_state",
        }
    )

    for partition_id in [str(pid) for pid in deep_stage.get("partition_ids") or []]:
        part = partitions[partition_id]
        partition_scope_paths = sorted(dict.fromkeys(str(path) for path in part.get("scope_paths") or []))
        narrowed_scope_paths = [
            path for path in partition_scope_paths if path in {str(x) for x in deep_stage.get("scope_paths") or []}
        ]
        if not narrowed_scope_paths:
            raise ValueError(
                "strategy_plan.deep_partition_followup.scope_paths must include at least one file from every selected "
                "deep_partition_followup.partition_ids partition; "
                f"missing coverage for: {partition_id}"
            )
        narrowed_scope_fingerprint = (
            str(part.get("scope_fingerprint") or "")
            if narrowed_scope_paths == partition_scope_paths
            else _canonical_hash({"scope_paths": narrowed_scope_paths})
        )
        narrowed_scope_fingerprint_basis = (
            "REPO_FILE_BYTES" if narrowed_scope_paths == partition_scope_paths else "PATH_SET"
        )
        manifest.append(
            {
                "node_id": f"deep_partition_followup__{partition_id}",
                "stage_id": "deep_partition_followup",
                "review_tier": "DEEP",
                "agent_provider_id": agent_provider_id,
                "agent_profile": str(deep_stage.get("agent_profile") or ""),
                "partition_id": partition_id,
                "scope_paths": narrowed_scope_paths,
                "scope_fingerprint": narrowed_scope_fingerprint,
                "scope_fingerprint_basis": narrowed_scope_fingerprint_basis,
                "partition_scope_paths": partition_scope_paths,
                "partition_scope_fingerprint": str(part.get("scope_fingerprint") or ""),
                "effective_scope_paths": [str(path) for path in final_stage.get("scope_paths") or []],
                "effective_scope_fingerprint": str(final_stage.get("scope_fingerprint") or ""),
                "closeout_authority": "ADVISORY_CONFIRM_REQUIRED",
            }
        )

    final_manifest_entry = {
        "node_id": "final_integrated_closeout",
        "stage_id": "final_integrated_closeout",
        "review_tier": str(final_stage.get("review_tier") or ""),
        "agent_provider_id": agent_provider_id,
        "agent_profile": str(final_stage.get("agent_profile") or ""),
        "scope_paths": [str(path) for path in final_stage.get("scope_paths") or []],
        "scope_fingerprint": str(final_stage.get("scope_fingerprint") or ""),
        "closeout_authority": "TERMINAL_DECISION_AUTHORITY",
    }
    if has_post_dedupe_advisory_stages:
        final_manifest_entry["allow_terminal_predecessors"] = True
    manifest.append(final_manifest_entry)
    return manifest


def build_review_orchestration_graph(
    *,
    repo_root: str | Path,
    review_id: str,
    strategy_plan: dict[str, Any],
    max_parallel_branches: int = 4,
    allow_historical_strategy_replay: bool = False,
) -> dict[str, Any]:
    repo_root = _normalize_repo_root(repo_root)
    plan = _validate_strategy_plan(
        repo_root=repo_root,
        strategy_plan=strategy_plan,
        allow_historical_strategy_replay=allow_historical_strategy_replay,
    )
    if int(max_parallel_branches) <= 0:
        raise ValueError("max_parallel_branches must be >= 1")

    review_token = _slug_token(review_id, fallback="review")
    fast_stage = _required_stage(plan, "fast_partition_scan")
    deep_stage = _required_stage(plan, "deep_partition_followup")
    fast_partition_ids = [str(pid) for pid in fast_stage.get("partition_ids") or []]
    selected_partition_ids = [str(pid) for pid in deep_stage.get("partition_ids") or []]
    has_post_dedupe_advisory_stages = bool(selected_partition_ids)

    nodes: list[dict[str, Any]] = [
        _node("review_intake", "loop.review_orchestration.review_intake", role="PROPOSER"),
    ]
    edges: list[dict[str, str]] = []

    fast_node_ids: list[str] = []
    for partition_id in fast_partition_ids:
        node_id = f"fast_partition_scan__{partition_id}"
        fast_node_ids.append(node_id)
        nodes.append(
            _node(
                node_id,
                "loop.review_orchestration.fast_partition_scan",
                role="REVIEWER",
            )
        )
        edges.append(_edge("review_intake", node_id, "SERIAL"))

    nodes.append(_node("finding_dedupe", "loop.review_orchestration.finding_dedupe", role="JUDGE"))
    for node_id in fast_node_ids:
        edges.append(_edge(node_id, "finding_dedupe", "BARRIER"))

    deep_node_ids: list[str] = []
    for partition_id in selected_partition_ids:
        node_id = f"deep_partition_followup__{partition_id}"
        deep_node_ids.append(node_id)
        nodes.append(
            _node(
                node_id,
                "loop.review_orchestration.deep_partition_followup",
                role="REVIEWER",
            )
        )
        edges.append(_edge("finding_dedupe", node_id, "NESTED"))

    nodes.append(
        _node(
            "final_integrated_closeout",
            "loop.review_orchestration.final_integrated_closeout",
            role="REVIEWER",
            allow_terminal_predecessors=has_post_dedupe_advisory_stages,
        )
    )
    if deep_node_ids:
        for node_id in deep_node_ids:
            edges.append(_edge(node_id, "final_integrated_closeout", "BARRIER"))
    else:
        edges.append(_edge("finding_dedupe", "final_integrated_closeout", "SERIAL"))

    return _validate_graph_shape(
        {
            "version": "1",
            "graph_id": f"graph.loop.review_orchestration.{review_token}",
            "graph_mode": "STATIC_USER_MODE",
            "scheduler": {"max_parallel_branches": int(max_parallel_branches)},
            "nodes": nodes,
            "edges": edges,
            "merge_policy": {
                "review_orchestration": {
                    "strategy_id": str(plan["strategy_id"]),
                    "strategy_fingerprint": str(plan.get("strategy_fingerprint") or ""),
                    "fast_partition_ids": [str(pid) for pid in fast_stage.get("partition_ids") or []],
                    "selected_partition_ids": selected_partition_ids,
                    "effective_scope_source": str(plan.get("effective_scope_source") or ""),
                    "authoritative_closeout_stage_id": "final_integrated_closeout",
                }
            },
        }
    )


def build_review_orchestration_bundle(
    *,
    repo_root: str | Path,
    review_id: str,
    strategy_plan: dict[str, Any],
    max_parallel_branches: int = 4,
    allow_historical_strategy_replay: bool = False,
) -> dict[str, Any]:
    repo_root = _normalize_repo_root(repo_root)
    plan = _validate_strategy_plan(
        repo_root=repo_root,
        strategy_plan=strategy_plan,
        allow_historical_strategy_replay=allow_historical_strategy_replay,
    )
    graph = build_review_orchestration_graph(
        repo_root=repo_root,
        review_id=review_id,
        strategy_plan=plan,
        max_parallel_branches=max_parallel_branches,
        allow_historical_strategy_replay=allow_historical_strategy_replay,
    )
    fast_stage = _required_stage(plan, "fast_partition_scan")
    deep_stage = _required_stage(plan, "deep_partition_followup")
    final_stage = _required_stage(plan, "final_integrated_closeout")
    return _bundle(
        preset_id="review_orchestration_v2",
        graph_spec=graph,
        resource_manifest=[
            _resource("review.strategy_plan", "IMMUTABLE"),
            _resource("review.partition_findings", "APPEND_ONLY"),
            _resource("review.reconciliation_state", "MUTABLE_CONTROLLED"),
            _resource("review.closeout_journal", "APPEND_ONLY"),
        ],
        composition_notes={
            "review_id": review_id,
            "strategy_id": str(plan["strategy_id"]),
            "strategy_fingerprint": str(plan.get("strategy_fingerprint") or ""),
            "selected_partition_ids": [str(pid) for pid in deep_stage.get("partition_ids") or []],
            "effective_scope_paths": [str(path) for path in final_stage.get("scope_paths") or []],
            "effective_scope_fingerprint": str(final_stage.get("scope_fingerprint") or ""),
            "authoritative_closeout_stage_id": "final_integrated_closeout",
            "fast_partition_node_ids": [
                f"fast_partition_scan__{str(pid)}" for pid in (fast_stage.get("partition_ids") or [])
            ],
            "deep_followup_node_ids": [
                f"deep_partition_followup__{str(pid)}" for pid in (deep_stage.get("partition_ids") or [])
            ],
        },
        stage_manifest=_stage_manifest(repo_root=repo_root, plan=plan),
        reconciliation_contract={
            "resource_id": "review.reconciliation_state",
            "producer_node_id": "finding_dedupe",
            "artifact_schema_ref": "docs/schemas/ReviewSupersessionReconciliation.schema.json",
            "authoritative_closeout_stage_id": "final_integrated_closeout",
            "finding_disposition_enum": ["CONFIRMED", "DISMISSED", "SUPERSEDED"],
            "late_output_disposition_enum": [
                "APPLIED",
                "NOOP_ALREADY_COVERED",
                "REJECTED_WITH_RATIONALE",
            ],
            "required_fields": [
                "finding_key",
                "finding_group_key",
                "scope_lineage_key",
                "source_stage_id",
                "source_partition_id",
                "disposition",
                "selected_partition_ids",
                "effective_scope_paths",
                "effective_scope_fingerprint",
            ],
        },
    )


__all__ = [
    "build_review_orchestration_bundle",
    "build_review_orchestration_graph",
]
