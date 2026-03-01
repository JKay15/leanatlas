#!/usr/bin/env python3
"""Contract: repository docs/instructions/code comments must be English-only.

Current enforcement is lexical and deterministic:
- FAIL when CJK ideographs / CJK punctuation / Kana are detected in scanned text files.

This gate protects prompt context quality and avoids mixed-language drift.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[2]

SCAN_EXTS = {
    ".md",
    ".py",
    ".sh",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".lean",
}

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".lake",
    ".cache",
    "artifacts",
}

EXCLUDED_FILES = {
    "leanatlas_clean_en_only_v0_50_13.zip",
}

CJK_RE = re.compile(r"[\u3000-\u303F\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")


def iter_files(root: Path) -> Iterable[Path]:
    for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        if not p.is_file():
            continue
        if p.name in EXCLUDED_FILES:
            continue
        if any(part in EXCLUDED_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in SCAN_EXTS:
            continue
        yield p


def find_non_english(path: Path) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return out

    for i, line in enumerate(text.splitlines(), start=1):
        if CJK_RE.search(line):
            out.append((i, line.strip()))
    return out


def main() -> int:
    violations: List[str] = []
    for path in iter_files(ROOT):
        hits = find_non_english(path)
        for line_no, line in hits:
            rel = path.relative_to(ROOT).as_posix()
            violations.append(f"{rel}:{line_no}: {line[:120]}")
            if len(violations) >= 200:
                break
        if len(violations) >= 200:
            break

    if violations:
        print("[english-only][FAIL] detected CJK text in repository files:")
        for v in violations:
            print(" -", v)
        return 1

    print("[english-only][PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
