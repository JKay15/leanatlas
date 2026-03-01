#!/usr/bin/env python3
"""Soak-tier executable smoke: run E2E scenarios (smoke tier).

Registered wrapper for tests/manifest.json.

If `lake` is not found, the underlying runner skips with exit code 0.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [sys.executable, "tests/e2e/run_scenarios.py", "--profile", "smoke"]
    print(f"[exec_scenarios_smoke] running: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
