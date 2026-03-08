#!/usr/bin/env python3
"""Deterministic post-onboarding LOOP user preference presets."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_ASSURANCE_PRESETS = ("Budget Saver", "Balanced", "Auditable")
DEFAULT_ASSURANCE_PRESET = "Budget Saver"
DEFAULT_FAST_REVIEWER_PROFILES = ("low", "medium")
DEFAULT_FAST_REVIEWER_PROFILE = "low"
DEFAULT_REVIEW_TIER_POLICIES = ("LOW_ONLY", "LOW_PLUS_MEDIUM")
DEFAULT_REVIEW_TIER_POLICY = "LOW_PLUS_MEDIUM"
DEFAULT_AGENT_PROVIDER_ID = "codex_cli"
DEFAULT_PREFERENCE_ARTIFACT_REL = ".cache/leanatlas/onboarding/loop_preferences.json"
PREFERENCE_SCHEMA = "leanatlas.loop_user_preferences"
PREFERENCE_SCHEMA_VERSION = "0.1.0"
DEFAULT_ALLOW_PYRAMID_REVIEW_FOR_LARGE_SCOPE = True
DEFAULT_MEDIUM_ESCALATION_PROFILE = "medium"
DEFAULT_MEDIUM_ESCALATION_POLICY = "SMALL_SCOPE_HIGH_RISK_CORE_LOGIC_ONLY"
DEFAULT_STRICT_EXCEPTION_POLICY = "EXPLICIT_EXCEPTION_ONLY"

_ASSURANCE_LEVEL_BY_PRESET = {
    "Budget Saver": "FAST",
    "Balanced": "LIGHT",
    "Auditable": "STRICT",
}


def _normalize_preset(value: Any) -> str:
    text = " ".join(str(value).strip().split())
    if text not in DEFAULT_ASSURANCE_PRESETS:
        raise ValueError(f"unsupported assurance preset: {value!r}")
    return text


def _normalize_provider(value: Any) -> str:
    text = " ".join(str(value).strip().split())
    if not text:
        raise ValueError("agent provider id must be non-empty")
    return text


def _normalize_fast_profile(value: Any) -> str:
    text = " ".join(str(value).strip().split())
    if text not in DEFAULT_FAST_REVIEWER_PROFILES:
        raise ValueError(f"unsupported FAST reviewer profile: {value!r}")
    return text


def _normalize_review_tier_policy(value: Any) -> str:
    text = " ".join(str(value).strip().split())
    if text not in DEFAULT_REVIEW_TIER_POLICIES:
        raise ValueError(f"unsupported review tier policy: {value!r}")
    return text


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "enabled"}:
            return True
        if lowered in {"false", "0", "no", "disabled"}:
            return False
    raise ValueError(f"expected boolean preference value, got: {value!r}")


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def default_preference_artifact_path(repo_root: Path) -> Path:
    return repo_root / Path(DEFAULT_PREFERENCE_ARTIFACT_REL)


def build_default_review_policy() -> dict[str, Any]:
    return {
        "assurance_preset": DEFAULT_ASSURANCE_PRESET,
        "assurance_level": _ASSURANCE_LEVEL_BY_PRESET[DEFAULT_ASSURANCE_PRESET],
        "agent_provider_id": DEFAULT_AGENT_PROVIDER_ID,
        "fast_reviewer_profile": DEFAULT_FAST_REVIEWER_PROFILE,
        "review_tier_policy": DEFAULT_REVIEW_TIER_POLICY,
        "allow_pyramid_review_for_large_scope": DEFAULT_ALLOW_PYRAMID_REVIEW_FOR_LARGE_SCOPE,
        "medium_escalation_profile": DEFAULT_MEDIUM_ESCALATION_PROFILE,
        "medium_escalation_policy": DEFAULT_MEDIUM_ESCALATION_POLICY,
        "strict_exception_policy": DEFAULT_STRICT_EXCEPTION_POLICY,
    }


def build_preference_record(
    *,
    assurance_preset: str = DEFAULT_ASSURANCE_PRESET,
    agent_provider_id: str = DEFAULT_AGENT_PROVIDER_ID,
    fast_reviewer_profile: str = DEFAULT_FAST_REVIEWER_PROFILE,
    review_tier_policy: str = DEFAULT_REVIEW_TIER_POLICY,
    allow_pyramid_review_for_large_scope: bool = DEFAULT_ALLOW_PYRAMID_REVIEW_FOR_LARGE_SCOPE,
) -> dict[str, Any]:
    defaults = {
        "assurance_preset": _normalize_preset(assurance_preset),
        "agent_provider_id": _normalize_provider(agent_provider_id),
        "fast_reviewer_profile": _normalize_fast_profile(fast_reviewer_profile),
        "review_tier_policy": _normalize_review_tier_policy(review_tier_policy),
        "allow_pyramid_review_for_large_scope": _normalize_bool(allow_pyramid_review_for_large_scope),
    }
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
    effective_defaults = deepcopy(stored["defaults"])
    for key, value in (overrides or {}).items():
        if value is None:
            continue
        if key == "assurance_preset":
            effective_defaults[key] = _normalize_preset(value)
        elif key == "agent_provider_id":
            effective_defaults[key] = _normalize_provider(value)
        elif key == "fast_reviewer_profile":
            effective_defaults[key] = _normalize_fast_profile(value)
        elif key == "review_tier_policy":
            effective_defaults[key] = _normalize_review_tier_policy(value)
        elif key == "allow_pyramid_review_for_large_scope":
            effective_defaults[key] = _normalize_bool(value)
        else:
            raise ValueError(f"unsupported LOOP preference override: {key}")

    effective_runtime = {
        "assurance_level": _ASSURANCE_LEVEL_BY_PRESET[effective_defaults["assurance_preset"]],
        "agent_provider_id": effective_defaults["agent_provider_id"],
        "fast_reviewer_profile": effective_defaults["fast_reviewer_profile"],
        "review_tier_policy": effective_defaults["review_tier_policy"],
        "allow_pyramid_review_for_large_scope": effective_defaults["allow_pyramid_review_for_large_scope"],
    }
    return {
        "artifact_path": str(default_preference_artifact_path(repo_root)),
        "stored_defaults": deepcopy(stored["defaults"]),
        "effective_defaults": effective_defaults,
        "effective_runtime": effective_runtime,
    }
