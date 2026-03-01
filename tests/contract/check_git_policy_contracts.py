#!/usr/bin/env python3
"""Contract: git policy linters behave deterministically for valid/invalid samples."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMMIT_CHECK = ROOT / "tools" / "onboarding" / "check_commit_message.py"
BRANCH_CHECK = ROOT / "tools" / "onboarding" / "check_branch_name.py"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _check_commit_samples() -> None:
    samples = ROOT / "artifacts" / "_tmp_git_policy"
    samples.mkdir(parents=True, exist_ok=True)

    valid = samples / "commit_valid.txt"
    invalid = samples / "commit_invalid.txt"
    valid.write_text("feat(onboarding): install repo-local git hooks\n", encoding="utf-8")
    invalid.write_text("update stuff quickly\n", encoding="utf-8")

    p_ok = _run([sys.executable, str(COMMIT_CHECK), str(valid)])
    _assert(p_ok.returncode == 0, f"valid commit message should pass; stderr={p_ok.stderr.strip()}")

    p_bad = _run([sys.executable, str(COMMIT_CHECK), str(invalid)])
    _assert(p_bad.returncode != 0, "invalid commit message must fail")


def _check_branch_samples() -> None:
    valid = [
        "feat/LA-1234-add-policy-bundle",
        "hotfix/LA-99-critical-patch",
        "codex/repair-core-profile",
    ]
    invalid = [
        "feature/LA-1234-not-allowed-prefix",
        "feat/no-trace-id",
        "fix/LA-abc-invalid-id",
    ]

    for b in valid:
        p = _run([sys.executable, str(BRANCH_CHECK), "--branch", b])
        _assert(p.returncode == 0, f"valid branch should pass ({b}); stderr={p.stderr.strip()}")

    for b in invalid:
        p = _run([sys.executable, str(BRANCH_CHECK), "--branch", b])
        _assert(p.returncode != 0, f"invalid branch must fail ({b})")


def main() -> int:
    if not COMMIT_CHECK.exists() or not BRANCH_CHECK.exists():
        print("[git-policy-contract][FAIL] missing git policy checker scripts")
        return 2

    try:
        _check_commit_samples()
        _check_branch_samples()
    except AssertionError as ex:
        print(f"[git-policy-contract][FAIL] {ex}")
        return 2

    print("[git-policy-contract][PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
