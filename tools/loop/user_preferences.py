#!/usr/bin/env python3
"""Deterministic post-onboarding LOOP user preference presets."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_ASSURANCE_PRESETS = ("Balanced", "Budget Saver", "Auditable")
DEFAULT_FAST_REVIEWER_PROFILES = ("low", "medium")
DEFAULT_AGENT_PROVIDER_ID = "codex_cli"
DEFAULT_PREFERENCE_ARTIFACT_REL = ".cache/leanatlas/onboarding/loop_preferences.json"
PREFERENCE_SCHEMA = "leanatlas.loop_user_preferences"
PREFERENCE_SCHEMA_VERSION = "0.1.0"

_ASSURANCE_LEVEL_BY_PRESET = {
    "Balanced": "LIGHT",
    "Budget Saver": "FAST",
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


def build_preference_record(
    *,
    assurance_preset: str = "Balanced",
    agent_provider_id: str = DEFAULT_AGENT_PROVIDER_ID,
    fast_reviewer_profile: str = "low",
    allow_pyramid_review_for_large_scope: bool = True,
) -> dict[str, Any]:
    defaults = {
        "assurance_preset": _normalize_preset(assurance_preset),
        "agent_provider_id": _normalize_provider(agent_provider_id),
        "fast_reviewer_profile": _normalize_fast_profile(fast_reviewer_profile),
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
        assurance_preset=defaults.get("assurance_preset", "Balanced"),
        agent_provider_id=defaults.get("agent_provider_id", DEFAULT_AGENT_PROVIDER_ID),
        fast_reviewer_profile=defaults.get("fast_reviewer_profile", "low"),
        allow_pyramid_review_for_large_scope=defaults.get("allow_pyramid_review_for_large_scope", True),
    )


def write_preference_record(*, repo_root: Path, record: dict[str, Any]) -> Path:
    normalized = build_preference_record(
        assurance_preset=record.get("defaults", {}).get("assurance_preset", record.get("assurance_preset", "Balanced")),
        agent_provider_id=record.get("defaults", {}).get("agent_provider_id", record.get("agent_provider_id", DEFAULT_AGENT_PROVIDER_ID)),
        fast_reviewer_profile=record.get("defaults", {}).get("fast_reviewer_profile", record.get("fast_reviewer_profile", "low")),
        allow_pyramid_review_for_large_scope=record.get("defaults", {}).get(
            "allow_pyramid_review_for_large_scope",
            record.get("allow_pyramid_review_for_large_scope", True),
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
        elif key == "allow_pyramid_review_for_large_scope":
            effective_defaults[key] = _normalize_bool(value)
        else:
            raise ValueError(f"unsupported LOOP preference override: {key}")

    effective_runtime = {
        "assurance_level": _ASSURANCE_LEVEL_BY_PRESET[effective_defaults["assurance_preset"]],
        "agent_provider_id": effective_defaults["agent_provider_id"],
        "fast_reviewer_profile": effective_defaults["fast_reviewer_profile"],
        "allow_pyramid_review_for_large_scope": effective_defaults["allow_pyramid_review_for_large_scope"],
    }
    return {
        "artifact_path": str(default_preference_artifact_path(repo_root)),
        "stored_defaults": deepcopy(stored["defaults"]),
        "effective_defaults": effective_defaults,
        "effective_runtime": effective_runtime,
    }
