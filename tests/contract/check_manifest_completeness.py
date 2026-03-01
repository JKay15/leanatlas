#!/usr/bin/env python3
"""Contract: tests/manifest.json must fully register executable assets.

Fail conditions:
- executable assets are discovered but not declared in manifest expands
- manifest expands references assets that do not exist
- expands_spec-derived expected set differs from declared expands set
- unregistered Phase6 executable tool entrypoints (0_50_1 baseline) are not
  covered by manifest-declared tests
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml


def _as_set(xs: Any) -> Set[str]:
    if not isinstance(xs, list):
        return set()
    out: Set[str] = set()
    for x in xs:
        if isinstance(x, str) and x.strip():
            out.add(x.strip())
    return out


def _load_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data
    return {}


def _discover_e2e_cases(repo_root: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    root = repo_root / "tests" / "e2e" / "golden"
    if not root.exists():
        return out
    for case_yaml in sorted(root.glob("*/case.yaml")):
        meta = _load_yaml(case_yaml)
        enabled = bool((meta.get("execution") or {}).get("enabled", False))
        if not enabled:
            continue
        cid = str(meta.get("id") or "").strip()
        if not cid:
            continue
        tier = str(meta.get("tier") or "core").strip() or "core"
        out[cid] = tier
    return out


def _discover_e2e_scenarios(repo_root: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    root = repo_root / "tests" / "e2e" / "scenarios"
    if not root.exists():
        return out
    for sc_yaml in sorted(root.glob("*/scenario.yaml")):
        meta = _load_yaml(sc_yaml)
        enabled = bool((meta.get("execution") or {}).get("enabled", False))
        if not enabled:
            continue
        sid = str(meta.get("id") or "").strip()
        if not sid:
            continue
        tier = str(meta.get("tier") or "core").strip() or "core"
        out[sid] = tier
    return out


def _discover_agent_eval_packs(repo_root: Path) -> Set[str]:
    out: Set[str] = set()
    root = repo_root / "tests" / "agent_eval" / "packs"
    if not root.exists():
        return out
    for pack_yaml in sorted(root.glob("*/pack.yaml")):
        meta = _load_yaml(pack_yaml)
        pid = str(meta.get("pack_id") or "").strip()
        if pid:
            out.add(pid)
    return out


def _discover_agent_eval_scenarios(repo_root: Path) -> Set[str]:
    out: Set[str] = set()
    root = repo_root / "tests" / "agent_eval" / "scenarios"
    if not root.exists():
        return out
    for sc_yaml in sorted(root.glob("*/scenario.yaml")):
        meta = _load_yaml(sc_yaml)
        sid = str(meta.get("scenario_id") or "").strip()
        if sid:
            out.add(sid)
    return out


def _discover_phase6_executable_tools(repo_root: Path) -> Set[str]:
    """Discover executable agent-eval tool entrypoints.

    These are 0_50_1 Phase6 assets under tools/agent_eval/*.py that expose
    a script entrypoint (`if __name__ == "__main__"`). They are not test
    scripts themselves, but they must be covered by registered tests.
    """
    root = repo_root / "tools" / "agent_eval"
    out: Set[str] = set()
    if not root.exists():
        return out
    for py in sorted(root.glob("*.py")):
        try:
            txt = py.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "__main__" not in txt:
            continue
        out.add(py.relative_to(repo_root).as_posix())
    return out


def _expected_ids(
    *,
    spec: Dict[str, Any],
    e2e_cases: Dict[str, str],
    e2e_scenarios: Dict[str, str],
    agent_eval_packs: Set[str],
    agent_eval_scenarios: Set[str],
) -> tuple[str, Set[str]]:
    kind = str(spec.get("kind") or "").strip()

    if kind == "e2e_cases_all":
        return ("cases", set(e2e_cases.keys()))
    if kind == "e2e_scenarios_all":
        return ("scenarios", set(e2e_scenarios.keys()))
    if kind == "e2e_cases_tier":
        tier = str(spec.get("tier") or "").strip()
        return ("cases", {k for k, v in e2e_cases.items() if v == tier})
    if kind == "e2e_scenarios_tier":
        tier = str(spec.get("tier") or "").strip()
        return ("scenarios", {k for k, v in e2e_scenarios.items() if v == tier})
    if kind == "agent_eval_packs_all":
        return ("agent_eval_packs", set(agent_eval_packs))
    if kind == "agent_eval_scenarios_all":
        return ("agent_eval_scenarios", set(agent_eval_scenarios))
    if kind == "agent_eval_packs_explicit":
        return ("agent_eval_packs", _as_set(spec.get("ids")))
    if kind == "agent_eval_scenarios_explicit":
        return ("agent_eval_scenarios", _as_set(spec.get("ids")))

    raise ValueError(f"unknown expands_spec.kind={kind!r}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "tests" / "manifest.json"
    if not manifest_path.exists():
        print("[manifest-completeness][FAIL] missing tests/manifest.json", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tests = list(manifest.get("tests") or [])

    e2e_cases = _discover_e2e_cases(repo_root)
    e2e_scenarios = _discover_e2e_scenarios(repo_root)
    agent_eval_packs = _discover_agent_eval_packs(repo_root)
    agent_eval_scenarios = _discover_agent_eval_scenarios(repo_root)

    declared_cases: Set[str] = set()
    declared_scenarios: Set[str] = set()
    declared_agent_eval_packs: Set[str] = set()
    declared_agent_eval_scenarios: Set[str] = set()
    declared_phase6_exec_tools: Set[str] = set()

    errors: List[str] = []

    for t in tests:
        tid = str(t.get("id") or "?")
        script = str(t.get("script") or "")
        expands = t.get("expands")

        if isinstance(expands, dict):
            declared_cases |= _as_set(expands.get("cases"))
            declared_scenarios |= _as_set(expands.get("scenarios"))
            declared_agent_eval_packs |= _as_set(expands.get("agent_eval_packs"))
            declared_agent_eval_scenarios |= _as_set(expands.get("agent_eval_scenarios"))
        declared_phase6_exec_tools |= _as_set(t.get("covers_phase6_executables"))

        is_wrapper = script.startswith("tests/e2e/exec_") or script.startswith("tests/stress/exec_")
        if is_wrapper and not isinstance(t.get("expands_spec"), dict):
            errors.append(f"{tid}: wrapper test missing expands_spec")

        spec = t.get("expands_spec")
        if not isinstance(spec, dict):
            continue

        if not isinstance(expands, dict):
            errors.append(f"{tid}: has expands_spec but missing expands")
            continue

        try:
            key, expected = _expected_ids(
                spec=spec,
                e2e_cases=e2e_cases,
                e2e_scenarios=e2e_scenarios,
                agent_eval_packs=agent_eval_packs,
                agent_eval_scenarios=agent_eval_scenarios,
            )
        except Exception as ex:
            errors.append(f"{tid}: {ex}")
            continue

        declared = _as_set(expands.get(key))
        if declared != expected:
            miss = sorted(expected - declared)
            extra = sorted(declared - expected)
            errors.append(
                f"{tid}: expands.{key} mismatch (missing={miss[:8]} extra={extra[:8]})"
            )

    missing_cases = sorted(set(e2e_cases.keys()) - declared_cases)
    missing_scenarios = sorted(set(e2e_scenarios.keys()) - declared_scenarios)
    missing_agent_eval_packs = sorted(agent_eval_packs - declared_agent_eval_packs)
    missing_agent_eval_scenarios = sorted(agent_eval_scenarios - declared_agent_eval_scenarios)
    phase6_exec_tools = _discover_phase6_executable_tools(repo_root)
    missing_phase6_exec_tools = sorted(phase6_exec_tools - declared_phase6_exec_tools)

    extra_cases = sorted(declared_cases - set(e2e_cases.keys()))
    extra_scenarios = sorted(declared_scenarios - set(e2e_scenarios.keys()))
    extra_agent_eval_packs = sorted(declared_agent_eval_packs - agent_eval_packs)
    extra_agent_eval_scenarios = sorted(declared_agent_eval_scenarios - agent_eval_scenarios)
    extra_phase6_exec_tools = sorted(declared_phase6_exec_tools - phase6_exec_tools)

    if missing_cases:
        errors.append(f"unregistered executable e2e cases: {missing_cases}")
    if missing_scenarios:
        errors.append(f"unregistered executable e2e scenarios: {missing_scenarios}")
    if missing_agent_eval_packs:
        errors.append(f"unregistered executable agent_eval packs: {missing_agent_eval_packs}")
    if missing_agent_eval_scenarios:
        errors.append(f"unregistered executable agent_eval scenarios: {missing_agent_eval_scenarios}")
    if missing_phase6_exec_tools:
        errors.append(f"unregistered phase6 executable tools (0_50_1 baseline): {missing_phase6_exec_tools}")

    if extra_cases:
        errors.append(f"manifest points to missing e2e cases: {extra_cases}")
    if extra_scenarios:
        errors.append(f"manifest points to missing e2e scenarios: {extra_scenarios}")
    if extra_agent_eval_packs:
        errors.append(f"manifest points to missing agent_eval packs: {extra_agent_eval_packs}")
    if extra_agent_eval_scenarios:
        errors.append(f"manifest points to missing agent_eval scenarios: {extra_agent_eval_scenarios}")
    if extra_phase6_exec_tools:
        errors.append(f"manifest points to missing phase6 executable tools: {extra_phase6_exec_tools}")

    if errors:
        print("[manifest-completeness][FAIL]")
        for e in errors:
            print(" -", e)
        return 1

    print(
        "[manifest-completeness][PASS] "
        f"e2e_cases={len(e2e_cases)} e2e_scenarios={len(e2e_scenarios)} "
        f"agent_eval_packs={len(agent_eval_packs)} agent_eval_scenarios={len(agent_eval_scenarios)} "
        f"phase6_exec_tools={len(phase6_exec_tools)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
