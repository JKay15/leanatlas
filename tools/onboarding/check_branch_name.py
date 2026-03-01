#!/usr/bin/env python3
"""Validate branch names using LeanAtlas branch naming policy."""

from __future__ import annotations

import argparse
import os
import re
import sys

ALLOWED_PATTERNS = [
    r"^main$",
    r"^develop$",
    r"^release/.+$",
    r"^dependabot/.+$",
    r"^renovate/.+$",
    r"^codex/.+$",
    r"^hotfix/LA-[0-9]+-[a-z0-9][a-z0-9-]*$",
    r"^(feat|fix|docs|chore|refactor|test|build|ci|perf|revert|security)/LA-[0-9]+-[a-z0-9][a-z0-9-]*$",
]


def _detect_branch() -> str:
    if os.environ.get("GITHUB_HEAD_REF"):
        return os.environ["GITHUB_HEAD_REF"].strip()
    if os.environ.get("GITHUB_REF_NAME"):
        return os.environ["GITHUB_REF_NAME"].strip()

    with os.popen("git rev-parse --abbrev-ref HEAD 2>/dev/null") as pipe:
        return pipe.read().strip()


def _matches(branch: str) -> bool:
    return any(re.fullmatch(rx, branch) for rx in ALLOWED_PATTERNS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="", help="Branch name override for tests/CI")
    args = ap.parse_args()

    branch = args.branch.strip() or _detect_branch()
    if not branch:
        print("[branch-policy][FAIL] could not detect current branch", file=sys.stderr)
        return 1
    if branch == "HEAD":
        print("[branch-policy][FAIL] detached HEAD is not allowed", file=sys.stderr)
        return 1

    if not _matches(branch):
        print(f"[branch-policy][FAIL] branch '{branch}' violates policy", file=sys.stderr)
        print("Allowed patterns:", file=sys.stderr)
        for rx in ALLOWED_PATTERNS:
            print(f" - {rx}", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print(" - feat/LA-1234-add-policy-bundle", file=sys.stderr)
        print(" - hotfix/LA-9999-critical-patch", file=sys.stderr)
        return 1

    print(f"[branch-policy][PASS] {branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
