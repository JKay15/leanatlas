#!/usr/bin/env python3
"""Soak-tier executable stress smoke.

Runs 1 iteration of the soak runner over smoke-tier executable cases.

If `lake` is not found, the underlying runner skips with exit code 0.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [sys.executable, "tests/stress/soak.py", "--iterations", "1", "--profile", "smoke"]
    print(f"[exec_soak_smoke] running: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
