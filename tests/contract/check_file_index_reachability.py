#!/usr/bin/env python3
"""Contract: root navigation must reach a full repository file index.

This enforces file-level discoverability without bloating root AGENTS context.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
INDEX = ROOT / "docs" / "navigation" / "FILE_INDEX.md"
GEN = ROOT / "tools" / "docs" / "generate_file_index.py"

ITEM_RE = re.compile(r"^- `(.+?)`\s*$")


def _die(msg: str, code: int = 2) -> int:
    print(f"[file-index][FAIL] {msg}", file=sys.stderr)
    return code


def _parse_index_paths(text: str) -> set[str]:
    out: set[str] = set()
    for line in text.splitlines():
        m = ITEM_RE.match(line)
        if m:
            out.add(m.group(1))
    return out


def main() -> int:
    for p in (AGENTS, INDEX, GEN):
        if not p.exists():
            return _die(f"missing required file: {p.relative_to(ROOT)}")

    agents_text = AGENTS.read_text(encoding="utf-8")
    if "docs/navigation/FILE_INDEX.md" not in agents_text:
        return _die("AGENTS.md must reference docs/navigation/FILE_INDEX.md")

    index_text = INDEX.read_text(encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(GEN)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if proc.returncode != 0:
        return _die(f"file index generator failed:\n{proc.stdout}")

    generated = proc.stdout
    if index_text != generated:
        return _die(
            "FILE_INDEX.md is out of date. Regenerate with:\n"
            "  ./.venv/bin/python tools/docs/generate_file_index.py --write"
        )

    listed = _parse_index_paths(index_text)
    if not listed:
        return _die("FILE_INDEX.md has no indexed file entries")

    missing = []
    for rel in sorted(listed):
        p = ROOT / rel
        if not p.exists() or not p.is_file():
            missing.append(rel)
    if missing:
        return _die(f"indexed paths missing on disk: {missing[:10]}")

    print(f"[file-index] OK ({len(listed)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
