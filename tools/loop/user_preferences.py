#!/usr/bin/env python3
"""Deterministic post-onboarding LOOP user preference presets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from looplib.preferences import (
    DEFAULT_AGENT_PROVIDER_ID,
    DEFAULT_ALLOW_PYRAMID_REVIEW_FOR_LARGE_SCOPE,
    DEFAULT_ASSURANCE_PRESET,
    DEFAULT_ASSURANCE_PRESETS,
    DEFAULT_FAST_REVIEWER_PROFILE,
    DEFAULT_FAST_REVIEWER_PROFILES,
    DEFAULT_MEDIUM_ESCALATION_POLICY,
    DEFAULT_MEDIUM_ESCALATION_PROFILE,
    DEFAULT_REVIEW_TIER_POLICIES,
    DEFAULT_REVIEW_TIER_POLICY,
    DEFAULT_STRICT_EXCEPTION_POLICY,
    build_default_review_policy,
    build_effective_runtime,
    normalize_preference_defaults,
    resolve_effective_defaults,
)

DEFAULT_PREFERENCE_ARTIFACT_REL = ".cache/leanatlas/onboarding/loop_preferences.json"
PREFERENCE_SCHEMA = "leanatlas.loop_user_preferences"
PREFERENCE_SCHEMA_VERSION = "0.1.0"


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def default_preference_artifact_path(repo_root: Path) -> Path:
    return Path(repo_root) / Path(DEFAULT_PREFERENCE_ARTIFACT_REL)


def ensure_preference_record(*, repo_root: Path) -> Path:
    path = default_preference_artifact_path(repo_root)
    if path.exists():
        normalized = load_preference_record(repo_root=repo_root)
        path.write_text(_canonical_json(normalized), encoding="utf-8")
        return path
    return write_preference_record(repo_root=repo_root, record=build_preference_record())


def build_preference_record(
    *,
    assurance_preset: str = DEFAULT_ASSURANCE_PRESET,
    agent_provider_id: str = DEFAULT_AGENT_PROVIDER_ID,
    fast_reviewer_profile: str = DEFAULT_FAST_REVIEWER_PROFILE,
    review_tier_policy: str = DEFAULT_REVIEW_TIER_POLICY,
    allow_pyramid_review_for_large_scope: bool = DEFAULT_ALLOW_PYRAMID_REVIEW_FOR_LARGE_SCOPE,
) -> dict[str, Any]:
    defaults = normalize_preference_defaults(
        assurance_preset=assurance_preset,
        agent_provider_id=agent_provider_id,
        fast_reviewer_profile=fast_reviewer_profile,
        review_tier_policy=review_tier_policy,
        allow_pyramid_review_for_large_scope=allow_pyramid_review_for_large_scope,
    )
    return {
        "schema": PREFERENCE_SCHEMA,
        "schema_version": PREFERENCE_SCHEMA_VERSION,
        "defaults": defaults,
    }


def load_preference_record(*, repo_root: Path) -> dict[str, Any]:
    path = default_preference_artifact_path(repo_root)
    if not path.exists():
        return build_preference_record()
    raw = json.loads(path.read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {}) if isinstance(raw, dict) else {}
    return build_preference_record(
        assurance_preset=defaults.get("assurance_preset", DEFAULT_ASSURANCE_PRESET),
        agent_provider_id=defaults.get("agent_provider_id", DEFAULT_AGENT_PROVIDER_ID),
        fast_reviewer_profile=defaults.get("fast_reviewer_profile", DEFAULT_FAST_REVIEWER_PROFILE),
        review_tier_policy=defaults.get("review_tier_policy", DEFAULT_REVIEW_TIER_POLICY),
        allow_pyramid_review_for_large_scope=defaults.get(
            "allow_pyramid_review_for_large_scope",
            DEFAULT_ALLOW_PYRAMID_REVIEW_FOR_LARGE_SCOPE,
        ),
    )


def write_preference_record(*, repo_root: Path, record: dict[str, Any]) -> Path:
    normalized = build_preference_record(
        assurance_preset=record.get("defaults", {}).get(
            "assurance_preset",
            record.get("assurance_preset", DEFAULT_ASSURANCE_PRESET),
        ),
        agent_provider_id=record.get("defaults", {}).get("agent_provider_id", record.get("agent_provider_id", DEFAULT_AGENT_PROVIDER_ID)),
        fast_reviewer_profile=record.get("defaults", {}).get(
            "fast_reviewer_profile",
            record.get("fast_reviewer_profile", DEFAULT_FAST_REVIEWER_PROFILE),
        ),
        review_tier_policy=record.get("defaults", {}).get(
            "review_tier_policy",
            record.get("review_tier_policy", DEFAULT_REVIEW_TIER_POLICY),
        ),
        allow_pyramid_review_for_large_scope=record.get("defaults", {}).get(
            "allow_pyramid_review_for_large_scope",
            record.get(
                "allow_pyramid_review_for_large_scope",
                DEFAULT_ALLOW_PYRAMID_REVIEW_FOR_LARGE_SCOPE,
            ),
        ),
    )
    path = default_preference_artifact_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(normalized), encoding="utf-8")
    return path


def resolve_effective_preferences(*, repo_root: Path, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    stored = load_preference_record(repo_root=repo_root)
    effective_defaults = resolve_effective_defaults(stored_defaults=stored["defaults"], overrides=overrides)
    effective_runtime = build_effective_runtime(effective_defaults=effective_defaults)
    return {
        "artifact_path": str(default_preference_artifact_path(repo_root)),
        "stored_defaults": dict(stored["defaults"]),
        "effective_defaults": effective_defaults,
        "effective_runtime": effective_runtime,
    }
