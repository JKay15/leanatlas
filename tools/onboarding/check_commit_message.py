#!/usr/bin/env python3
"""Validate commit messages using LeanAtlas conventional policy."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOWED_TYPES = (
    "feat",
    "fix",
    "docs",
    "chore",
    "refactor",
    "test",
    "build",
    "ci",
    "perf",
    "revert",
    "security",
)

TYPE_RE = "|".join(ALLOWED_TYPES)
HEADER_RE = re.compile(
    rf"^(?P<type>{TYPE_RE})(\([a-z0-9][a-z0-9._/-]*\))?(!)?: (?P<subject>.+)$"
)
BYPASS_PREFIXES = (
    "Merge ",
    "fixup! ",
    "squash! ",
    "Revert ",
)


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        return s
    return ""


def _error(msg: str) -> int:
    print(f"[commit-policy][FAIL] {msg}", file=sys.stderr)
    print("Expected format: <type>(<scope>): <subject>", file=sys.stderr)
    print("Example: feat(onboarding): install repo-local git hooks", file=sys.stderr)
    print("Allowed <type>: " + ", ".join(ALLOWED_TYPES), file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("commit_msg_file", nargs="?", help="Path to commit message file")
    args = ap.parse_args()

    if not args.commit_msg_file:
        return _error("missing commit message file argument")

    path = Path(args.commit_msg_file)
    if not path.exists():
        return _error(f"commit message file does not exist: {path}")

    header = _first_meaningful_line(path.read_text(encoding="utf-8", errors="replace"))
    if not header:
        return _error("commit header is empty")

    if any(header.startswith(prefix) for prefix in BYPASS_PREFIXES):
        print(f"[commit-policy][PASS] bypass header accepted: {header}")
        return 0

    m = HEADER_RE.match(header)
    if not m:
        return _error(f"header does not match conventional policy: {header}")

    if len(header) > 72:
        return _error(f"header too long ({len(header)} > 72): {header}")

    subject = m.group("subject").strip()
    if subject.endswith("."):
        return _error("subject must not end with '.'")

    print(f"[commit-policy][PASS] {header}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
