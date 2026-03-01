#!/usr/bin/env python3
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

cmd = [sys.executable, str(ROOT / "tests" / "run.py"), "--profile", "core"]
print(f"[lint] running: {' '.join(cmd)}")
raise SystemExit(subprocess.run(cmd, cwd=str(ROOT)).returncode)
