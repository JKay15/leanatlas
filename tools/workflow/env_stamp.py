#!/usr/bin/env python3
"""Deterministic environment stamp helpers.

Environment Stamp
-----------------
A RunReport should be self-describing:
- which Lean toolchain
- which mathlib rev
- which pinned external tools

This module reads *pinned* values from repo files.
It does not run networked commands.

Contracts
---------
- docs/contracts/RUNREPORT_CONTRACT.md
- docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _parse_mathlib_rev(lakefile_text: str) -> Optional[str]:
    # lakefile.lean: require mathlib from git ... @ "v4.xx.x"
    m = re.search(
        r"require\s+mathlib\s+from\s+git\s*\n\s*\"[^\"]+\"\s*@\s*\"([^\"]+)\"",
        lakefile_text,
        re.MULTILINE,
    )
    if m:
        return m.group(1).strip()
    # lakefile.toml: mathlib = { git = ..., rev = "..." }
    m2 = re.search(r"mathlib\s*=\s*\{[^}]*rev\s*=\s*\"([^\"]+)\"", lakefile_text)
    if m2:
        return m2.group(1).strip()
    return None


def get_environment_stamp(repo_root: Path) -> Dict[str, Any]:
    repo_root = repo_root.resolve()

    toolchain_path = repo_root / "lean-toolchain"
    lakefile_path = repo_root / "lakefile.lean"
    pins_path = repo_root / "tools" / "deps" / "pins.json"

    lean_toolchain = _read_text(toolchain_path).strip() if toolchain_path.exists() else "unknown"

    mathlib_rev = "unknown"
    if lakefile_path.exists():
        rev = _parse_mathlib_rev(_read_text(lakefile_path))
        if rev:
            mathlib_rev = rev

    pins_sha256 = "unknown"
    pinned_tools: Dict[str, Any] = {}
    if pins_path.exists():
        raw = pins_path.read_bytes()
        pins_sha256 = _sha256_bytes(raw)
        try:
            obj = json.loads(raw.decode("utf-8", errors="replace"))
            deps = obj.get("dependencies") or {}
            if isinstance(deps, dict):
                for dep_id, dep in deps.items():
                    if not isinstance(dep, dict):
                        continue
                    item: Dict[str, Any] = {}
                    if "kind" in dep:
                        item["kind"] = dep.get("kind")
                    if "pin" in dep:
                        item["pin"] = dep.get("pin")
                    if "value" in dep:
                        item["value"] = dep.get("value")
                    if "tested_version" in dep:
                        item["tested_version"] = dep.get("tested_version")
                    if item:
                        pinned_tools[str(dep_id)] = item
        except Exception:
            pinned_tools = {}

    return {
        "lean_toolchain": lean_toolchain,
        "mathlib_rev": mathlib_rev,
        "pins_sha256": pins_sha256,
        "pinned_tools": pinned_tools,
    }
