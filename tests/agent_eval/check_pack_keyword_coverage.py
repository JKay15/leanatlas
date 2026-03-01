#!/usr/bin/env python3
"""Check mentor keyword coverage for Phase6 agent eval pack (deterministic).

Goal: ensure that the mentor-provided keyword set is actually represented in the
task definitions, so we don't silently "forget to test" an entire topic area.
"""

from __future__ import annotations

import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "tests" / "agent_eval" / "packs" / "mentor_keywords_v0" / "pack.yaml"
TASKS_DIR = ROOT / "tests" / "agent_eval" / "tasks"

def main() -> int:
    if not PACK.exists():
        print(f"[coverage] pack not found: {PACK}", file=sys.stderr)
        return 2

    pack = yaml.safe_load(PACK.read_text(encoding="utf-8"))
    required = set(pack.get("required_keywords", []) or [])
    task_ids = pack.get("tasks", []) or []
    if not required:
        print("[coverage] required_keywords is empty", file=sys.stderr)
        return 2
    if not task_ids:
        print("[coverage] tasks list is empty", file=sys.stderr)
        return 2

    seen = set()
    missing_tasks = []
    for tid in task_ids:
        tpath = TASKS_DIR / tid / "task.yaml"
        if not tpath.exists():
            missing_tasks.append(str(tpath))
            continue
        t = yaml.safe_load(tpath.read_text(encoding="utf-8"))
        kws = t.get("keywords", []) or []
        for k in kws:
            if isinstance(k, str):
                seen.add(k)

    if missing_tasks:
        print("[coverage] missing task.yaml files:", file=sys.stderr)
        for p in missing_tasks:
            print(f"  - {p}", file=sys.stderr)
        return 2

    missing = sorted(required - seen)
    if missing:
        print("[coverage] missing required keywords:", file=sys.stderr)
        for k in missing:
            print(f"  - {k}", file=sys.stderr)
        print("[coverage] seen keywords:", sorted(seen), file=sys.stderr)
        return 1

    print("[coverage] mentor keyword coverage OK")
    print("[coverage] required:", sorted(required))
    print("[coverage] seen:", sorted(seen))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
