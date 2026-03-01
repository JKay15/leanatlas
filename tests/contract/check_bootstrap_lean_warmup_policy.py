#!/usr/bin/env python3
"""Contract: bootstrap must prepare Lean workspace for first-time users.

Fail conditions:
- missing `--skip-lean-warmup` option
- missing Repo-B skills readiness check
- missing Repo-B skills auto-recovery check
- missing importGraph dependency check
- missing Lean warmup commands (`lake build LeanAtlas`, `lake lint`)
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "bootstrap.sh"


def _require(cond: bool, msg: str, errors: list[str]) -> None:
    if not cond:
        errors.append(msg)


def main() -> int:
    if not SCRIPT.exists():
        print("[bootstrap-lean-warmup-policy][FAIL] missing scripts/bootstrap.sh")
        return 2

    text = SCRIPT.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []

    _require("--skip-lean-warmup" in text, "missing --skip-lean-warmup option", errors)
    _require("skills_repo_ready()" in text, "missing skills_repo_ready function", errors)
    _require("recover_skills_submodule()" in text, "missing recover_skills_submodule function", errors)
    _require(
        "git submodule update --init --recursive .agents/skills" in text,
        "missing Repo-B skills submodule recovery command",
        errors,
    )
    _require(
        "missing .agents/skills SKILL.md files after auto-recovery attempt" in text,
        "missing hard failure message after Repo-B skills auto-recovery",
        errors,
    )
    _require(
        '[[ -d ".lake/packages/importGraph" ]]' in text,
        "missing importGraph package presence check",
        errors,
    )
    _require("lake build LeanAtlas" in text, "missing lake build LeanAtlas warmup", errors)
    _require("lake lint" in text, "missing lake lint warmup gate", errors)
    _require("skip Lean warmup by user request" in text, "missing skip-lean-warmup log branch", errors)

    if errors:
        print("[bootstrap-lean-warmup-policy][FAIL]")
        for e in errors:
            print(" -", e)
        return 2

    print("[bootstrap-lean-warmup-policy][PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
