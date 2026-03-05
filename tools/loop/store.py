#!/usr/bin/env python3
"""Deterministic append-only filesystem store for LOOP runtime (Wave-B M1)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_HEX64 = re.compile(r"^[a-f0-9]{64}$")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _canonical_jsonl_line(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n"


class LoopStore:
    """Two-stream store: cache (rebuildable) and artifacts (append-only audit)."""

    def __init__(self, *, repo_root: Path, run_key: str) -> None:
        if not _HEX64.fullmatch(run_key):
            raise ValueError("run_key must be 64-char lowercase hex")
        self.repo_root = repo_root.resolve()
        self.run_key = run_key
        self.cache_root = self.repo_root / ".cache" / "leanatlas" / "loop_runtime" / "by_key" / run_key
        self.artifact_root = self.repo_root / "artifacts" / "loop_runtime" / "by_key" / run_key

    def ensure_layout(self) -> None:
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True)

    def _stream_root(self, stream: str) -> Path:
        if stream == "cache":
            return self.cache_root
        if stream == "artifact":
            return self.artifact_root
        raise ValueError("stream must be 'cache' or 'artifact'")

    def cache_path(self, rel: str) -> Path:
        return self.cache_root / rel

    def artifact_path(self, rel: str) -> Path:
        return self.artifact_root / rel

    def append_jsonl(self, rel: str, obj: Any, *, stream: str = "cache") -> Path:
        root = self._stream_root(stream)
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(_canonical_jsonl_line(obj))
        return path

    def write_once_json(self, rel: str, obj: Any, *, stream: str = "cache") -> Path:
        root = self._stream_root(stream)
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"write-once path already exists: {path}")
        path.write_text(_canonical_json(obj), encoding="utf-8")
        return path

    def read_json(self, rel: str, *, stream: str = "cache") -> Any:
        root = self._stream_root(stream)
        return json.loads((root / rel).read_text(encoding="utf-8"))
