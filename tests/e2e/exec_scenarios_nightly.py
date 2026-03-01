#!/usr/bin/env python3
"""Soak-tier execution: run E2E scenarios (nightly tier).

This is intentionally heavier than smoke:
- It may include longer chains, regressions, cleanup/idempotence, Phase3 tool calls, etc.

If `lake` is not found, the underlying runner skips with exit code 0.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [sys.executable, "tests/e2e/run_scenarios.py", "--profile", "nightly"]
    print(f"[exec_scenarios_nightly] running: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
