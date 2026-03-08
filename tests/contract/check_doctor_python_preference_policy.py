#!/usr/bin/env python3
"""Contract: doctor must prefer repo-local .venv python and keep deterministic fallback.

Fail conditions:
- scripts/doctor.sh lacks repo-local Python preference branch
- core checks are not executed through $PY_BIN
- doctor finalize step is not executed through $PY_BIN
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "doctor.sh"


def _require(cond: bool, msg: str, errors: list[str]) -> None:
    if not cond:
        errors.append(msg)


def main() -> int:
    if not SCRIPT.exists():
        print("[doctor-python-policy][FAIL] missing scripts/doctor.sh")
        return 2

    text = SCRIPT.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []

    _require('PY_BIN=".venv/bin/python"' in text, "missing PY_BIN repo-local default", errors)
    _require('if [[ -x "$PY_BIN" ]]; then' in text, "missing repo-local python existence check", errors)
    _require("using repo-local python" in text, "missing repo-local python log", errors)
    _require('PY_BIN="python"' in text, "missing system python fallback assignment", errors)

    required_cmds = [
        '"$PY_BIN" tests/contract/check_setup_docs.py',
        '"$PY_BIN" tests/contract/check_dependency_pins.py',
        '"$PY_BIN" tests/setup/deps_smoke.py',
        '"$PY_BIN" tools/onboarding/finalize_onboarding.py --step real_agent_cmd',
        '"$PY_BIN" tools/onboarding/finalize_onboarding.py --step doctor',
    ]
    for cmd in required_cmds:
        _require(cmd in text, f"missing command through $PY_BIN: {cmd}", errors)

    _require(
        '"$PY_BIN" - <<\'PY\'' in text or '"$PY_BIN" - <<\"PY\"' in text,
        "pins.json extraction snippet must run via $PY_BIN",
        errors,
    )
    _require(
        "LEANATLAS_REAL_AGENT_PROVIDER" in text,
        "doctor must support LEANATLAS_REAL_AGENT_PROVIDER for provider-based real-agent config",
        errors,
    )
    _require(
        "LEANATLAS_REAL_AGENT_PROFILE" in text,
        "doctor must support LEANATLAS_REAL_AGENT_PROFILE for profile-based real-agent config",
        errors,
    )

    # Guard against reverting to hardcoded `python tests/...` in execution lines.
    for i, line in enumerate(text.splitlines(), start=1):
        ls = line.strip()
        if ls.startswith("python tests/") or ls.startswith("python tools/"):
            errors.append(f"hardcoded python execution found at line {i}: {ls}")
        if re.search(r"^\s*python\s+-\s+<<'PY'", line):
            errors.append(f"hardcoded python heredoc found at line {i}")

    if errors:
        print("[doctor-python-policy][FAIL]")
        for e in errors:
            print(" -", e)
        return 2

    print("[doctor-python-policy][PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
