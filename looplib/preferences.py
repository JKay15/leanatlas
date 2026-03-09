"""Reusable LOOP preference-policy model without LeanAtlas-local persistence."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

DEFAULT_ASSURANCE_PRESETS = ("Budget Saver", "Balanced", "Auditable")
DEFAULT_ASSURANCE_PRESET = "Budget Saver"
DEFAULT_FAST_REVIEWER_PROFILES = ("low", "medium")
DEFAULT_FAST_REVIEWER_PROFILE = "low"
DEFAULT_REVIEW_TIER_POLICIES = ("LOW_ONLY", "LOW_PLUS_MEDIUM")
DEFAULT_REVIEW_TIER_POLICY = "LOW_PLUS_MEDIUM"
DEFAULT_AGENT_PROVIDER_ID = "codex_cli"
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


def normalize_preference_defaults(
    *,
    assurance_preset: Any = DEFAULT_ASSURANCE_PRESET,
    agent_provider_id: Any = DEFAULT_AGENT_PROVIDER_ID,
    fast_reviewer_profile: Any = DEFAULT_FAST_REVIEWER_PROFILE,
    review_tier_policy: Any = DEFAULT_REVIEW_TIER_POLICY,
    allow_pyramid_review_for_large_scope: Any = DEFAULT_ALLOW_PYRAMID_REVIEW_FOR_LARGE_SCOPE,
) -> dict[str, Any]:
    return {
        "assurance_preset": _normalize_preset(assurance_preset),
        "agent_provider_id": _normalize_provider(agent_provider_id),
        "fast_reviewer_profile": _normalize_fast_profile(fast_reviewer_profile),
        "review_tier_policy": _normalize_review_tier_policy(review_tier_policy),
        "allow_pyramid_review_for_large_scope": _normalize_bool(allow_pyramid_review_for_large_scope),
    }


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


def resolve_effective_defaults(
    *,
    stored_defaults: Mapping[str, Any] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = normalize_preference_defaults(
        assurance_preset=(stored_defaults or {}).get("assurance_preset", DEFAULT_ASSURANCE_PRESET),
        agent_provider_id=(stored_defaults or {}).get("agent_provider_id", DEFAULT_AGENT_PROVIDER_ID),
        fast_reviewer_profile=(stored_defaults or {}).get("fast_reviewer_profile", DEFAULT_FAST_REVIEWER_PROFILE),
        review_tier_policy=(stored_defaults or {}).get("review_tier_policy", DEFAULT_REVIEW_TIER_POLICY),
        allow_pyramid_review_for_large_scope=(stored_defaults or {}).get(
            "allow_pyramid_review_for_large_scope",
            DEFAULT_ALLOW_PYRAMID_REVIEW_FOR_LARGE_SCOPE,
        ),
    )
    effective = deepcopy(base)
    for key, value in (overrides or {}).items():
        if value is None:
            continue
        if key == "assurance_preset":
            effective[key] = _normalize_preset(value)
        elif key == "agent_provider_id":
            effective[key] = _normalize_provider(value)
        elif key == "fast_reviewer_profile":
            effective[key] = _normalize_fast_profile(value)
        elif key == "review_tier_policy":
            effective[key] = _normalize_review_tier_policy(value)
        elif key == "allow_pyramid_review_for_large_scope":
            effective[key] = _normalize_bool(value)
        else:
            raise ValueError(f"unsupported LOOP preference override: {key}")
    return effective


def build_effective_runtime(*, effective_defaults: Mapping[str, Any]) -> dict[str, Any]:
    defaults = normalize_preference_defaults(
        assurance_preset=effective_defaults.get("assurance_preset", DEFAULT_ASSURANCE_PRESET),
        agent_provider_id=effective_defaults.get("agent_provider_id", DEFAULT_AGENT_PROVIDER_ID),
        fast_reviewer_profile=effective_defaults.get("fast_reviewer_profile", DEFAULT_FAST_REVIEWER_PROFILE),
        review_tier_policy=effective_defaults.get("review_tier_policy", DEFAULT_REVIEW_TIER_POLICY),
        allow_pyramid_review_for_large_scope=effective_defaults.get(
            "allow_pyramid_review_for_large_scope",
            DEFAULT_ALLOW_PYRAMID_REVIEW_FOR_LARGE_SCOPE,
        ),
    )
    return {
        "assurance_level": _ASSURANCE_LEVEL_BY_PRESET[defaults["assurance_preset"]],
        "agent_provider_id": defaults["agent_provider_id"],
        "fast_reviewer_profile": defaults["fast_reviewer_profile"],
        "review_tier_policy": defaults["review_tier_policy"],
        "allow_pyramid_review_for_large_scope": defaults["allow_pyramid_review_for_large_scope"],
    }


__all__ = [
    "DEFAULT_AGENT_PROVIDER_ID",
    "DEFAULT_ALLOW_PYRAMID_REVIEW_FOR_LARGE_SCOPE",
    "DEFAULT_ASSURANCE_PRESET",
    "DEFAULT_ASSURANCE_PRESETS",
    "DEFAULT_FAST_REVIEWER_PROFILE",
    "DEFAULT_FAST_REVIEWER_PROFILES",
    "DEFAULT_MEDIUM_ESCALATION_POLICY",
    "DEFAULT_MEDIUM_ESCALATION_PROFILE",
    "DEFAULT_REVIEW_TIER_POLICIES",
    "DEFAULT_REVIEW_TIER_POLICY",
    "DEFAULT_STRICT_EXCEPTION_POLICY",
    "build_default_review_policy",
    "build_effective_runtime",
    "normalize_preference_defaults",
    "resolve_effective_defaults",
]
