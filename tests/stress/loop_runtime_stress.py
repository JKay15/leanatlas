#!/usr/bin/env python3
"""Wave-C runtime stress entrypoint (core profile, short deterministic run)."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [
        sys.executable,
        "tests/stress/soak.py",
        "--iterations",
        "1",
        "--profile",
        "core",
        "--shuffle",
        "--seed",
        "20260305",
        "--lake-timeout-s",
        "600",
    ]
    print(f"[loop-runtime-stress] running: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
