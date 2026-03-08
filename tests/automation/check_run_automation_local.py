#!/usr/bin/env python3
"""Contract: local automation wrapper must force source-workspace execution."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "tools" / "coordination" / "run_automation_local.py"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    _require(WRAPPER.exists(), "missing tools/coordination/run_automation_local.py")

    cmd = [
        sys.executable,
        str(WRAPPER),
        "--id",
        "nightly_reporting_integrity",
        "--advisor-mode",
        "off",
        "--agent-provider",
        "codex_cli",
        "--verify",
        "--dry-run",
    ]
    p = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
    _require(p.returncode == 0, f"wrapper dry-run failed: {p.stderr.strip()}")

    lines = [line.strip() for line in p.stdout.splitlines() if line.strip()]
    _require(lines, "wrapper dry-run produced no output")
    cmd_lines = [line for line in lines if line.startswith("[automation.local] cmd=")]
    _require(cmd_lines, "wrapper dry-run missing cmd output")
    rendered = cmd_lines[-1].split("=", 1)[1].strip()
    argv = shlex.split(rendered)

    runner = str(ROOT / "tools" / "coordination" / "run_automation.py")
    _require(runner in argv, "wrapper must invoke source-workspace run_automation.py by absolute path")
    runner_idx = argv.index(runner)
    _require("--id" in argv and "nightly_reporting_integrity" in argv, "wrapper must forward automation id")
    _require("--advisor-mode" in argv and "off" in argv, "wrapper must forward advisor mode")
    _require("--agent-provider" in argv and "codex_cli" in argv, "wrapper must forward agent provider")
    _require("--verify" in argv, "wrapper must forward --verify")

    venv_python = str(ROOT / ".venv" / "bin" / "python")
    if Path(venv_python).exists():
        _require(argv[0] == venv_python, "wrapper must prefer repo-local .venv python when available")
        _require(runner_idx == 1, "runner must be the first script after .venv python")

    print("[automation.local-wrapper][PASS]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[automation.local-wrapper][FAIL] {ex}", file=sys.stderr)
        raise SystemExit(1)
