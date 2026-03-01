#!/usr/bin/env python3
"""Soak-tier executable smoke: run E2E golden cases (smoke tier).

This is a thin wrapper so it can be registered in tests/manifest.json.

It is expected to be run only when a local Lean/Lake environment is available.
If `lake` is not found, the underlying runner will skip with exit code 0.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [sys.executable, "tests/e2e/run_cases.py", "--profile", "smoke"]
    print(f"[exec_cases_smoke] running: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
