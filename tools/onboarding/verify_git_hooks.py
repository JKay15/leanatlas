#!/usr/bin/env python3
"""Verify repo-local git hooks are installed and wired to pre-commit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REQUIRED_HOOKS = ("pre-commit", "commit-msg", "pre-push")


def _require(cond: bool, msg: str, errors: list[str]) -> None:
    if not cond:
        errors.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".", help="Repository root path")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    errors: list[str] = []

    git_dir = repo / ".git"
    _require(git_dir.exists() and git_dir.is_dir(), "missing .git directory", errors)

    pre_commit_cfg = repo / ".pre-commit-config.yaml"
    _require(pre_commit_cfg.exists(), "missing .pre-commit-config.yaml", errors)
    if pre_commit_cfg.exists():
        text = pre_commit_cfg.read_text(encoding="utf-8", errors="replace")
        _require("commit-msg-conventional" in text, "missing commit-msg-conventional hook in config", errors)
        _require("branch-name-policy" in text, "missing branch-name-policy hook in config", errors)

    for hook in REQUIRED_HOOKS:
        hp = git_dir / "hooks" / hook
        _require(hp.exists(), f"missing git hook file: .git/hooks/{hook}", errors)
        if hp.exists():
            htxt = hp.read_text(encoding="utf-8", errors="replace")
            _require("pre-commit" in htxt, f"hook not managed by pre-commit: .git/hooks/{hook}", errors)

    if errors:
        print("[git-hooks][FAIL]")
        for e in errors:
            print(f" - {e}")
        return 2

    print("[git-hooks][PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
