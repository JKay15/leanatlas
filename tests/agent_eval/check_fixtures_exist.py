#!/usr/bin/env python3
"""Contract test: every agent-eval task with a problem_slug must have a fixture.

Why:
- Phase6 runs must be reproducible and not mutate the main repo.
- Fixtures provide a stable starting point and ensure the runner can materialize workspaces.

This is a *fast* check intended for the core tier.
"""

from __future__ import annotations

from pathlib import Path
import sys
import yaml

REPO = Path(__file__).resolve().parents[2]
TASKS_ROOT = REPO / "tests" / "agent_eval" / "tasks"
PACKS_ROOT = REPO / "tests" / "agent_eval" / "packs"
FIX_ROOT = REPO / "tests" / "agent_eval" / "fixtures" / "problems"

REQUIRED_FILES = [
    "Spec.lean",
    "Proof.lean",
    "Cache.lean",
    "Scratch.lean",
    "Tasks.yaml",
    "README.md",
]


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> int:
    errors = []

    # Collect all task_ids from all packs
    task_ids = set()
    for pack in PACKS_ROOT.glob("*/pack.yaml"):
        data = load_yaml(pack)
        entries = data.get("tasks", [])
        if not isinstance(entries, list):
            errors.append(f"{pack}: tasks must be list")
            continue
        for e in entries:
            if isinstance(e, str):
                task_ids.add(e)
                continue
            if isinstance(e, dict) and isinstance(e.get("task_id"), str):
                continue
            errors.append(f"{pack}: task entry must be string or mapping with task_id")

    # For each task, require a fixture if problem_slug is declared.
    for tid in sorted(task_ids):
        task_file = TASKS_ROOT / tid / "task.yaml"
        if not task_file.exists():
            errors.append(f"missing task.yaml for {tid}: {task_file}")
            continue
        task = load_yaml(task_file)
        slug = task.get("problem_slug")
        if not slug:
            # Allowed: some tasks may be "pure" without a problem workspace.
            continue

        fix_dir = FIX_ROOT / str(slug)
        if not fix_dir.exists():
            errors.append(f"task {tid}: missing fixture dir for problem_slug={slug}: {fix_dir}")
            continue

        for rf in REQUIRED_FILES:
            p = fix_dir / rf
            if not p.exists():
                errors.append(f"fixture {slug}: missing required file {rf}")

        # Safety: Proof/Cache must not import Scratch.
        proof_txt = (fix_dir / "Proof.lean").read_text(encoding="utf-8") if (fix_dir / "Proof.lean").exists() else ""
        cache_txt = (fix_dir / "Cache.lean").read_text(encoding="utf-8") if (fix_dir / "Cache.lean").exists() else ""
        if "Scratch" in proof_txt:
            errors.append(f"fixture {slug}: Proof.lean must not reference Scratch")
        if "Scratch" in cache_txt:
            errors.append(f"fixture {slug}: Cache.lean must not reference Scratch")

        # Also check Cache/**.lean if present
        cache_dir = fix_dir / "Cache"
        if cache_dir.exists():
            for f in cache_dir.rglob("*.lean"):
                if "Scratch" in f.read_text(encoding="utf-8"):
                    errors.append(f"fixture {slug}: {f} must not reference Scratch")

    if errors:
        print("FIXTURE CONTRACT FAIL")
        for e in errors:
            print("-", e)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
