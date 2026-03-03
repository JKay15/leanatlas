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
import os
import re
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


def _verify_artifacts(repo_root: Path, active: List[Dict[str, object]]) -> Tuple[List[str], List[str]]:
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


def _candidate_automation_ids(aid: str) -> List[str]:
    out: List[str] = []
    for x in (aid, aid.replace("_", "-"), aid.replace("-", "_")):
        if x not in out:
            out.append(x)
    return out


def _find_automation_toml(codex_home: Path, aid: str) -> Path | None:
    auto_root = codex_home / "automations"
    for cid in _candidate_automation_ids(aid):
        p = auto_root / cid / "automation.toml"
        if p.exists():
            return p
    if not auto_root.exists():
        return None
    needle = f"--id {aid}"
    for p in auto_root.glob("*/automation.toml"):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if needle in text:
            return p
    return None


def _load_toml(path: Path) -> Dict[str, object]:
    text = path.read_text(encoding="utf-8")
    out: Dict[str, object] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+)\s*=\s*(.+)$", line)
        if not m:
            continue
        key = m.group(1)
        val = m.group(2).strip()
        if val.startswith('"') and val.endswith('"'):
            out[key] = val[1:-1]
            continue
        if val.startswith("[") and val.endswith("]"):
            out[key] = re.findall(r'"([^"]*)"', val)
            continue
    return out


def _verify_installation_config(
    *,
    repo_root: Path,
    codex_home: Path,
    active: List[Dict[str, object]],
) -> Tuple[List[str], List[str]]:
    wrapper = (repo_root / "tools" / "coordination" / "run_automation_local.py").as_posix()
    missing: List[str] = []
    ok: List[str] = []
    for a in active:
        aid = str(a["id"])
        toml_path = _find_automation_toml(codex_home, aid)
        if toml_path is None:
            missing.append(f"{aid}: missing automation.toml under {codex_home}/automations/*")
            continue
        cfg = _load_toml(toml_path)
        prompt = str(cfg.get("prompt") or "")
        cwds = cfg.get("cwds")
        if not isinstance(cwds, list):
            missing.append(f"{aid}: invalid cwds in {toml_path}")
            continue
        cwd_values = [str(x) for x in cwds]
        if repo_root.as_posix() not in cwd_values:
            missing.append(f"{aid}: cwds must include source workspace {repo_root.as_posix()} ({toml_path})")
            continue
        if wrapper not in prompt:
            missing.append(f"{aid}: prompt must invoke local wrapper {wrapper} ({toml_path})")
            continue
        if f"--id {aid}" not in prompt:
            missing.append(f"{aid}: prompt must include '--id {aid}' ({toml_path})")
            continue
        if "uv run --locked python tools/coordination/run_automation.py" in prompt:
            missing.append(f"{aid}: prompt still uses worktree-fragile uv run pattern ({toml_path})")
            continue
        ok.append(aid)
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
    ap.add_argument(
        "--codex-home",
        default=None,
        help="Override CODEX_HOME for installed automation config checks (default: $CODEX_HOME or ~/.codex)",
    )
    ap.add_argument(
        "--skip-config-check",
        action="store_true",
        help="Skip installed automation TOML checks (artifacts-only mode)",
    )
    ap.add_argument("--mark-done", action="store_true", help="Write onboarding automations step on success")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    codex_home = (
        Path(args.codex_home).resolve()
        if args.codex_home
        else Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
    )
    registry = repo_root / "automations" / "registry.json"
    if not registry.exists():
        return _die(f"missing {registry.relative_to(repo_root)}")

    reg = _load_registry(registry)
    active = _active_automations(reg)
    if not active:
        return _die("no active automations found in registry")

    cfg_ok: List[str] = []
    cfg_missing: List[str] = []
    if not args.skip_config_check:
        cfg_ok, cfg_missing = _verify_installation_config(repo_root=repo_root, codex_home=codex_home, active=active)
        if cfg_missing:
            print("[onboarding.automation] Invalid automation installation config:")
            for line in cfg_missing:
                print(f" - {line}")
            return _die("active automation config verification failed")

    art_ok, art_missing = _verify_artifacts(repo_root, active)
    if art_missing:
        print("[onboarding.automation] Missing automation evidence:")
        for line in art_missing:
            print(f" - {line}")
        return _die("active automation verification failed")

    if args.skip_config_check:
        print(f"[onboarding.automation][PASS] verified artifacts for {len(art_ok)} active automations")
    else:
        print(
            "[onboarding.automation][PASS] verified "
            f"{len(cfg_ok)} local-wrapper configs + {len(art_ok)} artifact sets"
        )
    if args.mark_done:
        return _mark_done(repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
