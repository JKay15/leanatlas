#!/usr/bin/env python3
"""Wave-C resource-contention stress entrypoint.

Runs a short core soak with per-iteration full build to amplify shared-cache/contention pressure.
"""

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
        "--build_all_each_iter",
        "--lake-timeout-s",
        "600",
    ]
    print(f"[loop-resource-contention-stress] running: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
