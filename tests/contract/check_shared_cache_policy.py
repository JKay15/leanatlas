#!/usr/bin/env python3
"""Contract: runner entrypoints must use unified shared cache policy.

Fail conditions:
- required runner file does not import tools.workflow.shared_cache
- required runner file does not call ensure_workspace_lake_packages
- runner file still carries local package seeding implementation
- run_scenario resume/fresh cache semantics markers are missing
"""

from __future__ import annotations

import sys
from pathlib import Path


REQUIRED_FILES = [
    "tools/agent_eval/run_pack.py",
    "tools/agent_eval/run_scenario.py",
    "tests/e2e/run_cases.py",
    "tests/e2e/run_scenarios.py",
    "tests/stress/soak.py",
]

BANNED_SNIPPETS = [
    "def _seed_workspace_lake_packages",
    "def seed_workdir_lake_packages",
    "LEANATLAS_SHARED_LAKE_PACKAGES",
    "LEANATLAS_ALLOW_HEAVY_PACKAGE_COPY",
]


def _check_runner_file(repo_root: Path, rel: str) -> list[str]:
    p = repo_root / rel
    if not p.exists():
        return [f"missing file: {rel}"]

    text = p.read_text(encoding="utf-8", errors="replace")
    errs: list[str] = []

    if "tools.workflow.shared_cache" not in text:
        errs.append(f"{rel}: missing import of tools.workflow.shared_cache")
    if "ensure_workspace_lake_packages(" not in text:
        errs.append(f"{rel}: missing call to ensure_workspace_lake_packages")

    for bad in BANNED_SNIPPETS:
        if bad in text:
            errs.append(f"{rel}: forbidden local cache policy fragment: {bad}")

    if rel == "tests/e2e/run_cases.py":
        ensure_idx = text.find("ensure_workspace_lake_packages(")
        cache_get_idx = text.find("'lake', 'exe', 'cache', 'get'")
        if cache_get_idx != -1 and ensure_idx != -1 and ensure_idx > cache_get_idx:
            errs.append(
                "tests/e2e/run_cases.py: must call ensure_workspace_lake_packages before `lake exe cache get`"
            )

    return errs


def _check_resume_policy(repo_root: Path) -> list[str]:
    rel = "tools/agent_eval/run_scenario.py"
    p = repo_root / rel
    if not p.exists():
        return [f"missing file: {rel}"]
    text = p.read_text(encoding="utf-8", errors="replace")

    errs: list[str] = []

    if "--resume-eval-dir" not in text:
        errs.append("run_scenario: missing --resume-eval-dir")
    if "--from-step" not in text:
        errs.append("run_scenario: missing --from-step")

    has_overlay_replay = ("reapply_overlays" in text) or ("resume_reapply_overlays" in text)
    if not has_overlay_replay:
        errs.append("run_scenario: missing overlay replay path for resume/fresh consistency")

    ensure_calls = text.count("ensure_workspace_lake_packages(")
    if ensure_calls < 2:
        errs.append("run_scenario: expected >=2 ensure_workspace_lake_packages calls (init + runtime)")

    return errs


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    shared_cache = repo_root / "tools" / "workflow" / "shared_cache.py"

    errors: list[str] = []
    if not shared_cache.exists():
        errors.append("missing tools/workflow/shared_cache.py")

    for rel in REQUIRED_FILES:
        errors.extend(_check_runner_file(repo_root, rel))

    errors.extend(_check_resume_policy(repo_root))

    if errors:
        print("[shared-cache-policy][FAIL]")
        for e in errors:
            print(" -", e)
        return 1

    print("[shared-cache-policy][PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
