#!/usr/bin/env python3
"""Contract: bootstrap must prefer healthy local .venv and support offline fallback.

Fail conditions:
- --force-uv-sync option is missing
- healthy .venv probe is missing required dependency checks
- bootstrap does not skip redundant uv sync when .venv is healthy
- uv sync failure path does not allow healthy .venv fallback
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "bootstrap.sh"


def _require(cond: bool, msg: str, errors: list[str]) -> None:
    if not cond:
        errors.append(msg)


def main() -> int:
    if not SCRIPT.exists():
        print("[bootstrap-fallback-policy][FAIL] missing scripts/bootstrap.sh")
        return 2

    text = SCRIPT.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []

    # CLI contract
    _require("--force-uv-sync" in text, "missing --force-uv-sync option", errors)

    # Health probe contract
    _require("venv_ready()" in text, "missing venv_ready function", errors)
    _require('for mod in ("yaml", "jsonschema", "drain3")' in text, "venv_ready must check yaml/jsonschema/drain3", errors)

    # Redundant sync skip contract
    _require(
        'if [[ "$FORCE_UV_SYNC" -eq 0 ]] && venv_ready; then' in text,
        "missing healthy .venv skip branch",
        errors,
    )
    _require(
        "existing .venv is healthy; skipping uv sync" in text,
        "missing healthy .venv skip log",
        errors,
    )

    # Offline fallback contract
    _require("if ! uv sync --locked; then" in text, "missing uv sync failure branch", errors)
    _require(
        "Continuing with existing healthy .venv." in text,
        "missing uv sync failure fallback to healthy .venv",
        errors,
    )
    _require(
        "no healthy .venv fallback is available" in text,
        "missing hard failure when uv sync fails and no healthy .venv exists",
        errors,
    )

    # Dependency/onboarding checks must run with repo-local python variable.
    _require(
        '"$PY_BIN" tests/contract/check_dependency_pins.py' in text,
        "dependency pin check must use $PY_BIN",
        errors,
    )
    _require(
        '"$PY_BIN" tools/onboarding/finalize_onboarding.py --step real_agent_cmd' in text,
        "bootstrap must record real_agent_cmd onboarding step via $PY_BIN",
        errors,
    )
    _require(
        '"$PY_BIN" tools/onboarding/finalize_onboarding.py --step bootstrap' in text,
        "bootstrap finalize step must use $PY_BIN",
        errors,
    )

    if errors:
        print("[bootstrap-fallback-policy][FAIL]")
        for e in errors:
            print(" -", e)
        return 2

    print("[bootstrap-fallback-policy][PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
