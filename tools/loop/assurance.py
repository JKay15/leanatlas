#!/usr/bin/env python3
"""Assurance-level policy helpers for LOOP execution/reporting."""

from __future__ import annotations

from enum import Enum
from typing import Any


class AssuranceLevel(str, Enum):
    FAST = "FAST"
    LIGHT = "LIGHT"
    STRICT = "STRICT"


STRICT_PASSED_REQUIRED_EVIDENCE_KEYS = (
    "ai_review_prompt_ref",
    "ai_review_response_ref",
    "ai_review_summary_ref",
)


def normalize_assurance_level(raw: str | None) -> AssuranceLevel:
    if raw is None:
        return AssuranceLevel.LIGHT
    v = str(raw).strip().upper()
    try:
        return AssuranceLevel(v)
    except Exception as exc:
        raise ValueError(f"invalid assurance_level: {raw}") from exc


def missing_strict_completion_evidence(wave_obj: dict[str, Any]) -> list[str]:
    evidence = wave_obj.get("evidence") or {}
    missing: list[str] = []
    for key in STRICT_PASSED_REQUIRED_EVIDENCE_KEYS:
        if not str(evidence.get(key, "")).strip():
            missing.append(key)
    return missing


def evaluate_wave_completion_gate(wave_obj: dict[str, Any]) -> tuple[bool, str]:
    """Return (allowed, reason_code) for completion claim.

    Deterministic rule:
    - STRICT + PASSED requires all strict AI-review evidence refs.
    - FAST/LIGHT do not hard-block PASSED by this gate.
    """

    level = normalize_assurance_level(wave_obj.get("assurance_level"))
    final = wave_obj.get("final_decision") or {}
    state = str(final.get("state", "")).strip().upper()

    if level == AssuranceLevel.STRICT and state == "PASSED":
        missing = missing_strict_completion_evidence(wave_obj)
        if missing:
            return (False, "STRICT_MISSING_AI_REVIEW_EVIDENCE")
    return (True, "OK")
