#!/usr/bin/env python3
"""Canonical review prompt protocols and controlled prompt experiments."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Sequence

BASELINE_REVIEW_PROMPT_PROTOCOL_ID = "review.prompt.baseline.v1"
EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID = "review.prompt.exhaustive.v1"

_PROTOCOL_MARKER = re.compile(r"^<!-- LOOP_REVIEW_PROTOCOL_ID:\s*([A-Za-z0-9._-]+)\s*-->$")
_PROMPT_SHA_MARKER = re.compile(r"^<!-- LOOP_REVIEW_PROMPT_SHA256:\s*([a-f0-9]{64})\s*-->$")
_BASELINE_SECTIONS = (
    "## Review Mission",
    "## Frozen Inputs",
    "## Output Contract",
)
_EXHAUSTIVE_ONLY_SECTIONS = (
    "## Coverage Axes",
    "## Anti-Dribble Requirements",
    "## Finalization Checklist",
)
_KNOWN_PROTOCOLS = {
    BASELINE_REVIEW_PROMPT_PROTOCOL_ID: {
        "is_exhaustive": False,
        "required_sections": _BASELINE_SECTIONS,
    },
    EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID: {
        "is_exhaustive": True,
        "required_sections": (*_BASELINE_SECTIONS, *_EXHAUSTIVE_ONLY_SECTIONS),
    },
}

_MISSION_PREFIXES = (
    "- review_id: `",
    "- review_tier: `",
    "- agent_provider_id: `",
    "- agent_profile: `",
)
_MISSION_SUFFIX = "`"
_REPORT_ONLY_LINE = "- Report only actionable findings backed by the frozen inputs."
_SCOPE_HEADER = "- Scope files:"
_INSTRUCTION_SCOPE_HEADER = "- Instruction scope refs:"
_REQUIRED_CONTEXT_HEADER = "- Required context refs:"
_SCOPE_ITEM_PREFIX = "  - `"
_SCOPE_ITEM_SUFFIX = "`"
_EXHAUSTIVE_BLOCK = (
    "",
    "## Coverage Axes",
    "- Check correctness, contract drift, replay and closeout semantics, scope lineage, tests, and docs routing.",
    "- Do not stop after the first few findings if materially distinct findings are plausibly discoverable.",
    "",
    "## Anti-Dribble Requirements",
    "- Batch materially distinct findings into this response instead of dribbling them across later rounds.",
    "- Deduplicate overlapping findings and prefer the highest-signal framing for each root issue.",
    "- If one category looks clean, keep scanning the other categories before finalizing.",
    "",
    "## Finalization Checklist",
    "- Do an omission self-check across all coverage axes before finalizing.",
    "- Confirm that repeated or contradicted findings were merged, dismissed, or explicitly separated.",
    "- If you still suspect uncovered areas, say so explicitly instead of ending early.",
)
_OUTPUT_BLOCK = (
    "",
    "## Output Contract",
    "- Return only findings that are actionable and evidence-backed.",
    "- If there are no findings, reply exactly `No findings.`",
)


def _canonical_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _normalize_refs(name: str, refs: Sequence[str]) -> list[str]:
    normalized = [str(ref).strip() for ref in refs if str(ref).strip()]
    if not normalized:
        raise ValueError(f"{name} must be a non-empty sequence")
    return sorted(dict.fromkeys(normalized))


def _prompt_sha256(protocol_id: str, body_text: str) -> str:
    return _canonical_hash(
        {
            "protocol_id": protocol_id,
            "body_text": body_text,
        }
    )


def _normalize_line_endings(text: str) -> str:
    return str(text).replace("\r\n", "\n").replace("\r", "\n")


def _parse_prompt_ref_list(lines: list[str], start: int, header: str) -> tuple[list[str], int]:
    if start >= len(lines) or lines[start] != header:
        raise ValueError(f"expected header `{header}`")
    index = start + 1
    refs: list[str] = []
    while index < len(lines) and lines[index].startswith(_SCOPE_ITEM_PREFIX):
        line = lines[index]
        if not line.endswith(_SCOPE_ITEM_SUFFIX):
            raise ValueError(f"malformed ref line `{line}`")
        refs.append(line[len(_SCOPE_ITEM_PREFIX) : -len(_SCOPE_ITEM_SUFFIX)])
        index += 1
    if not refs:
        raise ValueError(f"`{header}` must include at least one entry")
    return refs, index


def _parse_review_prompt_components(prompt_text: str) -> dict[str, Any]:
    text = str(prompt_text)
    lines = text.splitlines()
    if len(lines) < 10:
        raise ValueError("prompt is too short to be canonical")
    protocol_match = _PROTOCOL_MARKER.match(lines[0])
    sha_match = _PROMPT_SHA_MARKER.match(lines[1])
    if protocol_match is None or sha_match is None:
        raise ValueError("canonical prompt markers must occupy the first two lines")
    protocol_id = protocol_match.group(1)
    protocol = _KNOWN_PROTOCOLS.get(protocol_id)
    if protocol is None:
        raise ValueError(f"unknown prompt protocol `{protocol_id}`")

    body_start = 3 if len(lines) > 2 and lines[2] == "" else 2
    body_lines = lines[body_start:]
    body_text = "\n".join(body_lines)
    if text.endswith("\n"):
        body_text += "\n"

    index = 0
    if body_lines[index] != "## Review Mission":
        raise ValueError("missing `## Review Mission`")
    index += 1
    mission_values: list[str] = []
    for prefix in _MISSION_PREFIXES:
        if index >= len(body_lines) or not body_lines[index].startswith(prefix) or not body_lines[index].endswith(_MISSION_SUFFIX):
            raise ValueError(f"malformed mission line for prefix `{prefix}`")
        mission_values.append(body_lines[index][len(prefix) : -len(_MISSION_SUFFIX)])
        index += 1
    if index >= len(body_lines) or body_lines[index] != _REPORT_ONLY_LINE:
        raise ValueError("missing report-only mission line")
    index += 1
    if index >= len(body_lines) or body_lines[index] != "":
        raise ValueError("expected blank line after mission block")
    index += 1
    if index >= len(body_lines) or body_lines[index] != "## Frozen Inputs":
        raise ValueError("missing `## Frozen Inputs`")
    index += 1
    scope_paths, index = _parse_prompt_ref_list(body_lines, index, _SCOPE_HEADER)
    instruction_scope_refs, index = _parse_prompt_ref_list(body_lines, index, _INSTRUCTION_SCOPE_HEADER)
    required_context_refs, index = _parse_prompt_ref_list(body_lines, index, _REQUIRED_CONTEXT_HEADER)

    if protocol["is_exhaustive"]:
        exhaustive_lines = list(_EXHAUSTIVE_BLOCK)
        if body_lines[index : index + len(exhaustive_lines)] != exhaustive_lines:
            raise ValueError("exhaustive protocol body does not match the canonical exhaustive block")
        index += len(exhaustive_lines)
    output_lines = list(_OUTPUT_BLOCK)
    if body_lines[index : index + len(output_lines)] != output_lines:
        raise ValueError("output contract block does not match canonical output block")
    index += len(output_lines)
    if index != len(body_lines):
        raise ValueError("canonical prompt contains unexpected trailing content")

    rebuilt_prompt = build_review_prompt(
        review_id=mission_values[0],
        prompt_protocol_id=protocol_id,
        review_tier=mission_values[1],
        agent_provider_id=mission_values[2],
        agent_profile=mission_values[3],
        scope_paths=scope_paths,
        instruction_scope_refs=instruction_scope_refs,
        required_context_refs=required_context_refs,
    )

    return {
        "protocol_id": protocol_id,
        "declared_prompt_sha256": sha_match.group(1),
        "expected_prompt_sha256": _prompt_sha256(protocol_id, body_text),
        "body_text": body_text,
        "rebuilt_prompt": rebuilt_prompt,
        "review_id": mission_values[0],
        "review_tier": mission_values[1],
        "agent_provider_id": mission_values[2],
        "agent_profile": mission_values[3],
        "scope_paths": scope_paths,
        "instruction_scope_refs": instruction_scope_refs,
        "required_context_refs": required_context_refs,
    }


def build_review_prompt(
    *,
    review_id: str,
    prompt_protocol_id: str,
    review_tier: str,
    agent_provider_id: str,
    agent_profile: str,
    scope_paths: Sequence[str],
    instruction_scope_refs: Sequence[str],
    required_context_refs: Sequence[str],
) -> str:
    protocol_id = str(prompt_protocol_id).strip()
    protocol = _KNOWN_PROTOCOLS.get(protocol_id)
    if protocol is None:
        raise ValueError(f"unknown prompt_protocol_id: {prompt_protocol_id}")
    normalized_scope = _normalize_refs("scope_paths", scope_paths)
    normalized_instruction_scope = _normalize_refs("instruction_scope_refs", instruction_scope_refs)
    normalized_required_context = _normalize_refs("required_context_refs", required_context_refs)
    review_id = str(review_id).strip()
    review_tier = str(review_tier).strip().upper()
    provider = str(agent_provider_id).strip()
    profile = str(agent_profile).strip()
    if not review_id:
        raise ValueError("review_id must be non-empty")
    if not review_tier:
        raise ValueError("review_tier must be non-empty")
    if not provider or not profile:
        raise ValueError("agent_provider_id and agent_profile must be non-empty")

    body_lines: list[str] = [
        "## Review Mission",
        f"- review_id: `{review_id}`",
        f"- review_tier: `{review_tier}`",
        f"- agent_provider_id: `{provider}`",
        f"- agent_profile: `{profile}`",
        "- Report only actionable findings backed by the frozen inputs.",
        "",
        "## Frozen Inputs",
        "- Scope files:",
        *[f"  - `{path}`" for path in normalized_scope],
        "- Instruction scope refs:",
        *[f"  - `{ref}`" for ref in normalized_instruction_scope],
        "- Required context refs:",
        *[f"  - `{ref}`" for ref in normalized_required_context],
    ]
    if protocol["is_exhaustive"]:
        body_lines.extend(
            [
                "",
                "## Coverage Axes",
                "- Check correctness, contract drift, replay and closeout semantics, scope lineage, tests, and docs routing.",
                "- Do not stop after the first few findings if materially distinct findings are plausibly discoverable.",
                "",
                "## Anti-Dribble Requirements",
                "- Batch materially distinct findings into this response instead of dribbling them across later rounds.",
                "- Deduplicate overlapping findings and prefer the highest-signal framing for each root issue.",
                "- If one category looks clean, keep scanning the other categories before finalizing.",
                "",
                "## Finalization Checklist",
                "- Do an omission self-check across all coverage axes before finalizing.",
                "- Confirm that repeated or contradicted findings were merged, dismissed, or explicitly separated.",
                "- If you still suspect uncovered areas, say so explicitly instead of ending early.",
            ]
        )
    body_lines.extend(
        [
            "",
            "## Output Contract",
            "- Return only findings that are actionable and evidence-backed.",
            "- If there are no findings, reply exactly `No findings.`",
        ]
    )
    body_text = "\n".join(body_lines) + "\n"
    prompt_sha256 = _prompt_sha256(protocol_id, body_text)
    prefix_lines = [
        f"<!-- LOOP_REVIEW_PROTOCOL_ID: {protocol_id} -->",
        f"<!-- LOOP_REVIEW_PROMPT_SHA256: {prompt_sha256} -->",
        "",
    ]
    return "\n".join(prefix_lines) + body_text


def inspect_review_prompt_protocol(prompt_text: str) -> dict[str, Any]:
    text = str(prompt_text)
    lines = text.splitlines()
    protocol_id = None
    if lines:
        protocol_match = _PROTOCOL_MARKER.match(lines[0])
        if protocol_match:
            protocol_id = protocol_match.group(1)
    protocol = _KNOWN_PROTOCOLS.get(protocol_id or "")
    required_sections = list(protocol["required_sections"]) if protocol else []
    missing_sections = [section for section in required_sections if section not in text]
    sections_present = [
        section for section in (*_BASELINE_SECTIONS, *_EXHAUSTIVE_ONLY_SECTIONS) if section in text
    ]
    parsed: dict[str, Any] | None = None
    parse_error: str | None = None
    try:
        parsed = _parse_review_prompt_components(text)
    except ValueError as exc:
        parse_error = str(exc)
    declared_prompt_sha256 = parsed.get("declared_prompt_sha256") if parsed else None
    expected_prompt_sha256 = parsed.get("expected_prompt_sha256") if parsed else None
    checksum_match = bool(parsed and declared_prompt_sha256 and expected_prompt_sha256 == declared_prompt_sha256)
    normalized_text = _normalize_line_endings(text)
    exact_prompt_match = bool(parsed and parsed.get("rebuilt_prompt") == normalized_text)
    return {
        "protocol_id": protocol_id,
        "declared_prompt_sha256": declared_prompt_sha256,
        "expected_prompt_sha256": expected_prompt_sha256,
        "checksum_match": checksum_match,
        "exact_prompt_match": exact_prompt_match,
        "parse_error": parse_error,
        "is_canonical": bool(protocol and checksum_match and exact_prompt_match and not missing_sections),
        "is_exhaustive": bool(protocol and protocol["is_exhaustive"]),
        "missing_sections": missing_sections,
        "sections_present": sections_present,
        "review_id": parsed.get("review_id") if parsed else None,
        "review_tier": parsed.get("review_tier") if parsed else None,
        "agent_provider_id": parsed.get("agent_provider_id") if parsed else None,
        "agent_profile": parsed.get("agent_profile") if parsed else None,
        "scope_paths": list(parsed.get("scope_paths") or []) if parsed else [],
        "instruction_scope_refs": list(parsed.get("instruction_scope_refs") or []) if parsed else [],
        "required_context_refs": list(parsed.get("required_context_refs") or []) if parsed else [],
    }


def build_controlled_review_prompt_experiment(
    *,
    review_id: str,
    review_tier: str,
    agent_provider_id: str,
    agent_profile: str,
    scope_paths: Sequence[str],
    instruction_scope_refs: Sequence[str],
    required_context_refs: Sequence[str],
) -> dict[str, Any]:
    shared_context = {
        "review_id": str(review_id).strip(),
        "review_tier": str(review_tier).strip().upper(),
        "agent_provider_id": str(agent_provider_id).strip(),
        "agent_profile": str(agent_profile).strip(),
        "scope_paths": _normalize_refs("scope_paths", scope_paths),
        "instruction_scope_refs": _normalize_refs("instruction_scope_refs", instruction_scope_refs),
        "required_context_refs": _normalize_refs("required_context_refs", required_context_refs),
    }
    shared_context_fingerprint = _canonical_hash(shared_context)
    variants: list[dict[str, Any]] = []
    for variant_id, prompt_protocol_id in (
        ("baseline", BASELINE_REVIEW_PROMPT_PROTOCOL_ID),
        ("exhaustive", EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID),
    ):
        prompt_text = build_review_prompt(
            review_id=shared_context["review_id"],
            prompt_protocol_id=prompt_protocol_id,
            review_tier=shared_context["review_tier"],
            agent_provider_id=shared_context["agent_provider_id"],
            agent_profile=shared_context["agent_profile"],
            scope_paths=shared_context["scope_paths"],
            instruction_scope_refs=shared_context["instruction_scope_refs"],
            required_context_refs=shared_context["required_context_refs"],
        )
        variants.append(
            {
                "variant_id": variant_id,
                "prompt_protocol_id": prompt_protocol_id,
                "prompt_text": prompt_text,
                "prompt_fingerprint": _canonical_hash(
                    {
                        "prompt_protocol_id": prompt_protocol_id,
                        "prompt_text": prompt_text,
                    }
                ),
                "shared_context_fingerprint": shared_context_fingerprint,
                **shared_context,
            }
        )
    return {
        "experiment_id": f"{shared_context['review_id']}.prompt_protocol_control",
        "control_variable": "PROMPT_PROTOCOL_ONLY",
        "delta_policy": "PROMPT_PROTOCOL_ONLY",
        "shared_context_fingerprint": shared_context_fingerprint,
        "variants": variants,
    }


__all__ = [
    "BASELINE_REVIEW_PROMPT_PROTOCOL_ID",
    "EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID",
    "build_controlled_review_prompt_experiment",
    "build_review_prompt",
    "inspect_review_prompt_protocol",
]
