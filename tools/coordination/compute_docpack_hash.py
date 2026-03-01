#!/usr/bin/env python3
"""
Compute the deterministic DocPack content hash.

Definition (V0):
- Walk repo root, stable-sorted.
- Exclude volatile paths (DOC_PACK_ID.json, artifacts/, .cache/, .lake/, build/, dist/, __pycache__/, and common build outputs).
- Hash = sha256( for each file: relpath + sha256(filebytes) ).

Rationale:
Parallel GPT threads must be able to state the exact same Base without ambiguity,
even when zips are repacked or line endings differ externally.
"""
from __future__ import annotations

import fnmatch
import hashlib
import os
from pathlib import Path


EXCLUDE_GLOBS = [
    "DOC_PACK_ID.json",
    "artifacts/**",
    ".cache/**",
    ".lake/**",
    "build/**",
    "dist/**",
    "**/__pycache__/**",
    "**/*.olean",
    "**/*.ilean",
    "**/*.c",
    "**/*.o",
    "**/*.a",
    "**/*.so",
    "**/*.dylib",
    "**/*.exe",
]


def is_excluded(rel: str) -> bool:
    rel = rel.replace(os.sep, "/")
    return any(fnmatch.fnmatch(rel, pat) for pat in EXCLUDE_GLOBS)


def compute(root: Path) -> str:
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        for fn in filenames:
            path = Path(dirpath) / fn
            rel = os.path.relpath(path, root)
            if is_excluded(rel):
                continue
            rel_norm = rel.replace(os.sep, "/")
            h.update(rel_norm.encode("utf-8"))
            h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    print(compute(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
