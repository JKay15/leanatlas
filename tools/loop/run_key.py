#!/usr/bin/env python3
"""Deterministic run-key derivation for LOOP runtime (Wave-B M1)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

_HEX64 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class RunKeyInput:
    loop_id: str
    graph_mode: str
    input_projection_hash: str
    instruction_chain_hash: str
    dependency_pin_set_id: str


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_payload(payload: Mapping[str, Any]) -> None:
    loop_id = str(payload.get("loop_id", "")).strip()
    graph_mode = str(payload.get("graph_mode", "")).strip()
    dep = str(payload.get("dependency_pin_set_id", "")).strip()
    iph = str(payload.get("input_projection_hash", "")).strip()
    ich = str(payload.get("instruction_chain_hash", "")).strip()

    if not loop_id:
        raise ValueError("loop_id must be non-empty")
    if graph_mode not in {"STATIC_USER_MODE", "SYSTEM_EXCEPTION_MODE"}:
        raise ValueError("graph_mode must be STATIC_USER_MODE or SYSTEM_EXCEPTION_MODE")
    if not dep:
        raise ValueError("dependency_pin_set_id must be non-empty")
    if not _HEX64.fullmatch(iph):
        raise ValueError("input_projection_hash must be 64-char lowercase hex")
    if not _HEX64.fullmatch(ich):
        raise ValueError("instruction_chain_hash must be 64-char lowercase hex")


def compute_run_key(inp: RunKeyInput | Mapping[str, Any]) -> str:
    payload = asdict(inp) if isinstance(inp, RunKeyInput) else dict(inp)
    _validate_payload(payload)
    canonical = _canonical_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
