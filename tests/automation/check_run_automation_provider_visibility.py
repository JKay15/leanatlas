#!/usr/bin/env python3
"""Contract: automation dry-run must show advisor provider/profile resolution.

Why:
- registry-first defaults reduce manual CLI flags;
- dry-run output must make selected/default advisor executor auditable.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools" / "coordination" / "run_automation.py"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _run(args: list[str]) -> str:
    p = subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    _require(p.returncode == 0, f"run_automation dry-run failed: {p.stderr.strip()}")
    return p.stdout


def main() -> int:
    _require(RUNNER.exists(), "missing tools/coordination/run_automation.py")

    # Registry default path (no CLI override).
    out_default = _run(["--id", "weekly_kb_suggestions", "--advisor-mode", "auto", "--dry-run"])
    _require(
        "provider(selected)=codex_cli [source=registry]" in out_default,
        "dry-run must show selected provider from registry defaults",
    )

    # CLI override path.
    out_override = _run(
        [
            "--id",
            "weekly_kb_suggestions",
            "--advisor-mode",
            "auto",
            "--agent-provider",
            "claude_code",
            "--dry-run",
        ]
    )
    _require(
        "provider(selected)=claude_code [source=cli]" in out_override,
        "dry-run must show selected provider from CLI override",
    )

    print("[automation.provider-visibility][PASS]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[automation.provider-visibility][FAIL] {ex}", file=sys.stderr)
        raise SystemExit(1)
