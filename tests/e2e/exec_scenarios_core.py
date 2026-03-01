#!/usr/bin/env python3
"""Soak-tier execution: run E2E scenarios (core tier)."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [sys.executable, "tests/e2e/run_scenarios.py", "--profile", "core"]
    print(f"[exec_scenarios_core] running: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
