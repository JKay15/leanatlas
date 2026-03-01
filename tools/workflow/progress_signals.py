#!/usr/bin/env python3
"""Deterministic progress-signal helpers.

These helpers intentionally avoid any LLM dependency.
They operate only on facts produced by the Lean environment / tools.
"""

from __future__ import annotations

from typing import Iterable, Dict, Any, List, Optional, Tuple
import hashlib
import json


def diagnostic_fingerprint(error_diags: Iterable[Dict[str, Any]]) -> str:
    """Compute a stable fingerprint over error diagnostics.

    Uses only: file + range + message.

    Input diagnostics are expected to already be normalized:
    - repo-relative POSIX file paths
    - range: {start:{line,col}, end:{line,col}}
    """
    items: List[Tuple[str, str, str]] = []
    for d in error_diags:
        f = str(d.get("file", ""))
        r = d.get("range", None)
        msg = str(d.get("message", ""))
        items.append((f, json.dumps(r, sort_keys=True, ensure_ascii=False), msg))
    items.sort()
    raw = json.dumps(items, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def is_stagnant(*, diag_changed: bool, new_retrieval_hit: bool, imports_changed: bool, goal_changed: Optional[bool] = None) -> bool:
    """Compute stagnation deterministically from progress signals."""
    if goal_changed is None:
        return (not diag_changed) and (not new_retrieval_hit) and (not imports_changed)
    return (not diag_changed) and (not new_retrieval_hit) and (not imports_changed) and (not goal_changed)
