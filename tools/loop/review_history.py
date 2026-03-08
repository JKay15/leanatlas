#!/usr/bin/env python3
"""Deterministic review-history summarization utilities."""

from __future__ import annotations

from typing import Any


def _iter_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def summarize_review_history(records: list[dict[str, Any]]) -> dict[str, Any]:
    contradictions: set[str] = set()
    nitpicks: set[str] = set()

    for rec in records:
        for rid in _iter_list(rec.get("contradiction_refs")):
            s = str(rid).strip()
            if s:
                contradictions.add(s)
        for rid in _iter_list(rec.get("nitpick_refs")):
            s = str(rid).strip()
            if s:
                nitpicks.add(s)

        findings = _iter_list(rec.get("findings"))
        for fd in findings:
            if not isinstance(fd, dict):
                continue
            fid = str(fd.get("finding_id", "")).strip()
            flags = {str(x).strip().upper() for x in _iter_list(fd.get("flags"))}
            is_contradiction = bool(fd.get("contradiction")) or ("CONTRADICTION" in flags)
            is_nitpick = bool(fd.get("potential_nitpick")) or bool(fd.get("nitpick")) or ("NITPICK" in flags)
            if fid and is_contradiction:
                contradictions.add(fid)
            if fid and is_nitpick:
                nitpicks.add(fid)

    contradiction_refs = sorted(contradictions)
    nitpick_refs = sorted(nitpicks)
    return {
        "contradiction_count": len(contradiction_refs),
        "potential_nitpick_count": len(nitpick_refs),
        "contradiction_refs": contradiction_refs,
        "nitpick_refs": nitpick_refs,
        "consulted_iteration_count": len(records),
    }
