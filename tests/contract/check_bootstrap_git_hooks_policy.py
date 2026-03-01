#!/usr/bin/env python3
"""Contract: onboarding must install repo-local git discipline hooks."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.sh"
DOCTOR = ROOT / "scripts" / "doctor.sh"
INSTALL = ROOT / "scripts" / "install_repo_git_hooks.sh"
PRE_COMMIT_CFG = ROOT / ".pre-commit-config.yaml"


def _require(cond: bool, msg: str, errors: list[str]) -> None:
    if not cond:
        errors.append(msg)


def main() -> int:
    errors: list[str] = []

    _require(BOOTSTRAP.exists(), "missing scripts/bootstrap.sh", errors)
    _require(DOCTOR.exists(), "missing scripts/doctor.sh", errors)
    _require(INSTALL.exists(), "missing scripts/install_repo_git_hooks.sh", errors)
    _require(PRE_COMMIT_CFG.exists(), "missing .pre-commit-config.yaml", errors)

    if BOOTSTRAP.exists():
        bt = BOOTSTRAP.read_text(encoding="utf-8", errors="replace")
        _require("--skip-git-hooks" in bt, "bootstrap missing --skip-git-hooks option", errors)
        _require(
            "bash scripts/install_repo_git_hooks.sh" in bt,
            "bootstrap must invoke scripts/install_repo_git_hooks.sh",
            errors,
        )
        _require("skip git hook installation by user request" in bt, "bootstrap missing skip-git-hooks log branch", errors)

    if DOCTOR.exists():
        dt = DOCTOR.read_text(encoding="utf-8", errors="replace")
        _require(
            '"$PY_BIN" tools/onboarding/verify_git_hooks.py' in dt,
            "doctor must run verify_git_hooks.py via $PY_BIN",
            errors,
        )
        _require(
            "bash scripts/install_repo_git_hooks.sh" in dt,
            "doctor must auto-heal by invoking install_repo_git_hooks.sh",
            errors,
        )

    if INSTALL.exists():
        it = INSTALL.read_text(encoding="utf-8", errors="replace")
        _require("pre-commit validate-config" in it, "hook installer must validate pre-commit config", errors)
        _require("--hook-type pre-commit" in it, "hook installer must install pre-commit hook", errors)
        _require("--hook-type commit-msg" in it, "hook installer must install commit-msg hook", errors)
        _require("--hook-type pre-push" in it, "hook installer must install pre-push hook", errors)

    if PRE_COMMIT_CFG.exists():
        pc = PRE_COMMIT_CFG.read_text(encoding="utf-8", errors="replace")
        _require("commit-msg-conventional" in pc, "pre-commit config missing commit-msg policy hook", errors)
        _require("branch-name-policy" in pc, "pre-commit config missing branch-name policy hook", errors)

    if errors:
        print("[bootstrap-git-hooks-policy][FAIL]")
        for e in errors:
            print(f" - {e}")
        return 2

    print("[bootstrap-git-hooks-policy][PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
