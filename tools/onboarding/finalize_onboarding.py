#!/usr/bin/env python3
"""Finalize onboarding state and compact AGENTS.md after full setup succeeds.

Contract:
- `bootstrap` + `doctor` must both pass before onboarding is marked completed.
- Once completed, keep root AGENTS compact to reduce routine prompt context.
- Preserve the verbose onboarding text in docs/agents/archive/ (committed, low-frequency).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ONBOARDING_START = "<!-- ONBOARDING_BLOCK_START -->"
ONBOARDING_END = "<!-- ONBOARDING_BLOCK_END -->"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _compact_agents(*, repo_root: Path) -> bool:
    agents_path = repo_root / "AGENTS.md"
    compact_path = repo_root / "docs" / "agents" / "archive" / "AGENTS_ONBOARDING_COMPACT.md"

    if not agents_path.exists():
        raise FileNotFoundError(f"Missing {agents_path}")
    if not compact_path.exists():
        raise FileNotFoundError(f"Missing {compact_path}")

    text = agents_path.read_text(encoding="utf-8")
    s = text.find(ONBOARDING_START)
    e = text.find(ONBOARDING_END)
    if s == -1 or e == -1 or e < s:
        raise RuntimeError("AGENTS.md onboarding markers are missing or malformed")

    compact_block = compact_path.read_text(encoding="utf-8").strip()
    replacement = f"{ONBOARDING_START}\n{compact_block}\n{ONBOARDING_END}"

    block_end = e + len(ONBOARDING_END)
    old_block = text[s:block_end]
    if old_block == replacement:
        return False

    new_text = text[:s] + replacement + text[block_end:]
    agents_path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--step",
        required=True,
        choices=["bootstrap", "doctor", "core_tests", "phase6_dummy", "real_agent_cmd"],
    )
    ap.add_argument("--repo-root", default=None, help="Override repository root (for tests)")
    ap.add_argument("--no-compact", action="store_true", help="Do not compact AGENTS.md even when completed")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    state_path = repo_root / ".cache" / "leanatlas" / "onboarding" / "state.json"

    state = _load_json(state_path)
    if not state:
        state = {
            "schema": "leanatlas.onboarding_state",
            "schema_version": "0.1.0",
            "completed": False,
            "steps": {},
        }

    if not isinstance(state.get("steps"), dict):
        state["steps"] = {}
    state["steps"][args.step] = "ok"
    state["updated_at"] = _utc_now()

    steps = state["steps"]
    completed = (
        steps.get("bootstrap") == "ok"
        and steps.get("doctor") == "ok"
        and steps.get("real_agent_cmd") == "ok"
    )
    state["completed"] = bool(completed)
    if completed and not state.get("completed_at"):
        state["completed_at"] = _utc_now()

    _write_json(state_path, state)

    compacted = False
    if completed and not args.no_compact:
        compacted = _compact_agents(repo_root=repo_root)

    print(
        "[onboarding] "
        f"step={args.step} completed={state.get('completed')} "
        f"state={state_path.relative_to(repo_root)} compacted={compacted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
