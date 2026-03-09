#!/usr/bin/env python3
"""Canonical provider review payload extraction for maintainer LOOP closeout."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_TERMINAL_EVENT_TOKENS = {"completed", "complete", "final", "done"}
_ASSISTANTISH_TYPES = {"assistant_message", "agent_message"}
_FIELD_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")
_RUNTIME_BANNER_RE = re.compile(
    r"^\s*(model|provider|reasoning(?:\s+|[-_])effort)\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)


def _resolve_observation_path(raw_path: str, *, evidence_root: Path) -> Path | None:
    if not raw_path.strip():
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = evidence_root / path
    return path


def _extract_observed_runtime_metadata(*, stdout_path: Path | None) -> dict[str, str] | None:
    if stdout_path is None or not stdout_path.exists():
        return None
    observed: dict[str, str] = {}
    for raw_line in stdout_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _RUNTIME_BANNER_RE.match(raw_line)
        if match is None:
            continue
        raw_key = match.group(1).strip().lower().replace("-", " ").replace("_", " ")
        key = "reasoning_effort" if raw_key == "reasoning effort" else raw_key
        value = match.group("value").strip()
        if value:
            observed[key] = value
    return observed or None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def provider_adapter(agent_provider_id: str) -> dict[str, Any]:
    if agent_provider_id == "codex_cli":
        return {
            "adapter_id": "codex_cli_v2",
            "semantic_sources": ["response_file", "provider_event_jsonl"],
            "provider_event_jsonl_stream": "stdout",
            "default_timeout_s": 3600,
            "default_idle_timeout_s": 600,
            "default_semantic_idle_timeout_s": 1200,
            "minimum_observation_window_s": 600,
        }
    return {
        "adapter_id": "generic_response_file_v1",
        "semantic_sources": ["response_file"],
        "provider_event_jsonl_stream": None,
        "default_timeout_s": 1800,
        "default_idle_timeout_s": 300,
        "default_semantic_idle_timeout_s": 600,
        "minimum_observation_window_s": 300,
    }


def _flatten_terminal_text(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        text = value.strip()
        if text:
            out.append(text)
        return out
    if isinstance(value, list):
        for item in value:
            out.extend(_flatten_terminal_text(item))
        return out
    if isinstance(value, dict):
        for key in (
            "text",
            "content",
            "parts",
            "items",
            "item",
            "output",
            "result",
            "payload",
            "data",
            "final_message",
            "last_message",
            "message",
        ):
            if key in value:
                out.extend(_flatten_terminal_text(value[key]))
        return out
    return out


def _event_tokens(obj: Mapping[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("type", "event", "kind", "name", "status", "phase"):
        raw = str(obj.get(key) or "").strip().lower()
        if not raw:
            continue
        for token in _FIELD_TOKEN_SPLIT.split(raw):
            if token:
                tokens.add(token)
    return tokens


def _is_terminal_event(obj: Mapping[str, Any], *, inherited_terminal: bool) -> bool:
    if inherited_terminal or obj.get("final") is True:
        return True
    return bool(_event_tokens(obj) & _TERMINAL_EVENT_TOKENS)


def _message_role(obj: Any) -> str | None:
    if not isinstance(obj, dict):
        return None
    role = str(obj.get("role") or "").strip().lower()
    return role or None


def _assistantish_type(obj: Mapping[str, Any]) -> str | None:
    raw = str(obj.get("type") or "").strip().lower()
    if not raw:
        return None
    if raw in _ASSISTANTISH_TYPES:
        return raw
    if "assistant" in _event_tokens({"type": raw}):
        return raw
    return None


def _extract_terminal_message_from_event(
    obj: Any,
    *,
    inherited_terminal: bool = False,
    path: str = "event",
) -> tuple[str | None, str | None]:
    if not isinstance(obj, dict):
        return None, None

    is_terminal = _is_terminal_event(obj, inherited_terminal=inherited_terminal)

    message_obj = obj.get("message")
    if isinstance(message_obj, dict) and _message_role(message_obj) == "assistant" and is_terminal:
        parts = _flatten_terminal_text(message_obj.get("content"))
        if not parts:
            parts = _flatten_terminal_text(message_obj)
        joined = "\n".join(part for part in parts if part).strip()
        if joined:
            return joined, f"{path}.message.assistant"

    assistantish_type = _assistantish_type(obj)
    if assistantish_type is not None and is_terminal:
        parts = _flatten_terminal_text(obj)
        joined = "\n".join(part for part in parts if part).strip()
        if joined:
            return joined, f"{path}.{assistantish_type}"

    for key in ("item", "items", "output", "result", "payload", "data"):
        nested = obj.get(key)
        next_path = f"{path}.{key}"
        if isinstance(nested, list):
            for idx, item in enumerate(nested):
                text, kind = _extract_terminal_message_from_event(
                    item,
                    inherited_terminal=is_terminal,
                    path=f"{next_path}[{idx}]",
                )
                if text:
                    return text, kind
        else:
            text, kind = _extract_terminal_message_from_event(
                nested,
                inherited_terminal=is_terminal,
                path=next_path,
            )
            if text:
                return text, kind
    return None, None


def extract_canonical_response(
    *,
    agent_provider_id: str,
    span: Mapping[str, Any],
    evidence_root: Path,
) -> dict[str, Any]:
    adapter = provider_adapter(agent_provider_id)
    stdout_path = _resolve_observation_path(str(span.get("stdout_path") or ""), evidence_root=evidence_root)
    observed_runtime_metadata = _extract_observed_runtime_metadata(stdout_path=stdout_path)
    if adapter.get("provider_event_jsonl_stream") != "stdout":
        return {
            "response_text": None,
            "provider_event_ref": None,
            "semantic_response_source": None,
            "extraction_kind": None,
            "observed_runtime_metadata": observed_runtime_metadata,
        }
    if stdout_path is None:
        return {
            "response_text": None,
            "provider_event_ref": None,
            "semantic_response_source": None,
            "extraction_kind": None,
            "observed_runtime_metadata": observed_runtime_metadata,
        }
    if not stdout_path.exists():
        return {
            "response_text": None,
            "provider_event_ref": None,
            "semantic_response_source": None,
            "extraction_kind": None,
            "observed_runtime_metadata": observed_runtime_metadata,
        }

    terminal_message: str | None = None
    extraction_kind: str | None = None
    for raw_line in stdout_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        candidate, candidate_kind = _extract_terminal_message_from_event(obj, path="event")
        if candidate:
            terminal_message = candidate
            extraction_kind = candidate_kind
    if terminal_message:
        return {
            "response_text": terminal_message,
            "provider_event_ref": str(stdout_path),
            "semantic_response_source": "provider_event_jsonl",
            "extraction_kind": extraction_kind,
            "observed_runtime_metadata": observed_runtime_metadata,
        }
    return {
        "response_text": None,
        "provider_event_ref": str(stdout_path),
        "semantic_response_source": None,
        "extraction_kind": None,
        "observed_runtime_metadata": observed_runtime_metadata,
    }


def build_canonical_review_result(
    *,
    review_id: str,
    attempt_index: int,
    agent_provider_id: str,
    provider_adapter_id: str,
    status: str,
    reason_code: str,
    response_ref: str,
    response_exists: bool,
    response_bytes: int,
    semantic_response_source: str | None,
    extraction_kind: str | None,
    provider_event_ref: str | None,
    stdout_ref: str | None,
    stderr_ref: str | None,
    observed_runtime_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "version": "1",
        "review_id": review_id,
        "attempt_index": int(attempt_index),
        "generated_at_utc": _utc_now(),
        "agent_provider_id": agent_provider_id,
        "provider_adapter_id": provider_adapter_id,
        "status": status,
        "reason_code": reason_code,
        "terminal": status == "SUCCEEDED",
        "response_ref": response_ref,
        "response_exists": bool(response_exists),
        "response_bytes": int(response_bytes),
        "semantic_response_source": semantic_response_source,
        "extraction_kind": extraction_kind,
        "provider_event_ref": provider_event_ref,
        "stdout_ref": stdout_ref,
        "stderr_ref": stderr_ref,
        "observed_runtime_metadata": dict(observed_runtime_metadata or {}) or None,
    }


def load_canonical_review_result(path: Path) -> dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


__all__ = [
    "build_canonical_review_result",
    "extract_canonical_response",
    "load_canonical_review_result",
    "provider_adapter",
]
