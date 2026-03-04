#!/usr/bin/env python3
"""Contract: FILE_INDEX generator must ignore untracked local files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "tools" / "docs" / "generate_file_index.py"
PROBE = ROOT / ".tmp_file_index_untracked_probe.txt"


def _fail(msg: str, code: int = 2) -> int:
    print(f"[file-index][FAIL] {msg}", file=sys.stderr)
    return code


def main() -> int:
    rel = PROBE.relative_to(ROOT).as_posix()
    if PROBE.exists():
        return _fail(f"probe file already exists, clean it first: {rel}")

    PROBE.write_text("probe\n", encoding="utf-8")
    try:
        p = subprocess.run([sys.executable, str(GEN)], cwd=str(ROOT), capture_output=True, text=True)
        if p.returncode != 0:
            return _fail(f"generator failed:\n{p.stdout}\n{p.stderr}")
        if f"- `{rel}`" in p.stdout:
            return _fail(f"untracked file leaked into generated index: {rel}")
    finally:
        PROBE.unlink(missing_ok=True)

    print("[file-index] untracked-file guard OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
