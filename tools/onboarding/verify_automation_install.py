#!/usr/bin/env python3
"""Verify active Codex App automations produced local artifacts, then mark onboarding ready.

This script is intentionally deterministic:
- source of truth: automations/registry.json (status=active)
- verification: each active automation must match at least one declared artifact glob
- optional state update: finalize_onboarding.py --step automations
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


def _die(msg: str, code: int = 2) -> int:
    print(f"[onboarding.automation][FAIL] {msg}", file=sys.stderr)
    return code


def _load_registry(path: Path) -> Dict[str, object]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("registry root must be an object")
    return obj


def _active_automations(reg: Dict[str, object]) -> List[Dict[str, object]]:
    autos = reg.get("automations")
    if not isinstance(autos, list):
        return []
    out: List[Dict[str, object]] = []
    for a in autos:
        if not isinstance(a, dict):
            continue
        if a.get("status") != "active":
            continue
        aid = a.get("id")
        det = a.get("deterministic")
        if not isinstance(aid, str) or not aid.strip():
            continue
        if not isinstance(det, dict):
            continue
        arts = det.get("artifacts")
        if not isinstance(arts, list):
            continue
        pats = [p for p in arts if isinstance(p, str) and p.strip()]
        out.append({"id": aid, "artifacts": pats})
    return out


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_state(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {
            "schema": "leanatlas.onboarding_state",
            "schema_version": "0.1.0",
            "completed": False,
            "operational_ready": False,
            "steps": {},
        }
    obj = json.loads(path.read_text(encoding="utf-8"))
    return obj if isinstance(obj, dict) else {}


def _write_state(path: Path, state: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pattern_has_match(repo_root: Path, pattern: str) -> bool:
    matches = list(repo_root.glob(pattern))
    return len(matches) > 0


def _verify(repo_root: Path, active: List[Dict[str, object]]) -> Tuple[List[str], List[str]]:
    missing: List[str] = []
    ok: List[str] = []
    for a in active:
        aid = str(a["id"])
        pats = list(a["artifacts"])  # type: ignore[index]
        if not pats:
            missing.append(f"{aid}: no artifact patterns declared")
            continue
        if any(_pattern_has_match(repo_root, p) for p in pats):
            ok.append(aid)
            continue
        missing.append(f"{aid}: no artifacts found for declared globs {pats}")
    return ok, missing


def _mark_done(repo_root: Path) -> int:
    state_path = repo_root / ".cache" / "leanatlas" / "onboarding" / "state.json"
    state = _load_state(state_path)
    steps = state.get("steps")
    if not isinstance(steps, dict):
        steps = {}
        state["steps"] = steps
    steps["automations"] = "ok"
    state["updated_at"] = _utc_now()

    completed = (
        steps.get("bootstrap") == "ok"
        and steps.get("doctor") == "ok"
        and steps.get("real_agent_cmd") == "ok"
    )
    operational_ready = bool(completed and steps.get("automations") == "ok")
    state["completed"] = bool(completed)
    state["operational_ready"] = operational_ready

    if completed and not state.get("completed_at"):
        state["completed_at"] = _utc_now()
    if operational_ready and not state.get("operational_ready_at"):
        state["operational_ready_at"] = _utc_now()

    _write_state(state_path, state)
    rel = state_path.relative_to(repo_root)
    print(
        "[onboarding.automation] marked "
        f"completed={state.get('completed')} operational_ready={state.get('operational_ready')} state={rel}"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=None, help="Override repository root")
    ap.add_argument("--mark-done", action="store_true", help="Write onboarding automations step on success")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    registry = repo_root / "automations" / "registry.json"
    if not registry.exists():
        return _die(f"missing {registry.relative_to(repo_root)}")

    reg = _load_registry(registry)
    active = _active_automations(reg)
    if not active:
        return _die("no active automations found in registry")

    ok, missing = _verify(repo_root, active)
    if missing:
        print("[onboarding.automation] Missing automation evidence:")
        for line in missing:
            print(f" - {line}")
        return _die("active automation verification failed")

    print(f"[onboarding.automation][PASS] verified {len(ok)} active automations")
    if args.mark_done:
        return _mark_done(repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
