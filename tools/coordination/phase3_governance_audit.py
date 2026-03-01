#!/usr/bin/env python3
"""Deterministic Phase3 governance audit (Promotion + GC).

Purpose
-------
Provide one automation-friendly entrypoint that continuously checks whether
Phase3 governance primitives still behave as expected:

- Phase3 scenario coverage contract remains valid.
- GC propose path still runs and emits plan/report artifacts.
- Promotion gate still runs against the minimal fixture plan.

The script is deterministic and writes all evidence under artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.workflow.run_cmd import run_cmd


@dataclass(frozen=True)
class Step:
    name: str
    cmd: List[str]
    timeout_s: int


def _deep_get(obj: Dict[str, Any], dotted: str) -> Any:
    cur: Any = obj
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _rel_to_root(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return path.as_posix()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".", help="Repository root used by underlying commands.")
    ap.add_argument(
        "--out-root",
        default="artifacts/phase3_governance/latest",
        help="Output root for audit artifacts.",
    )
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out_root = Path(args.out_root)
    if not out_root.is_absolute():
        out_root = (repo_root / out_root).resolve()
    logs_dir = out_root / "Cmd"
    out_root.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    py = sys.executable
    steps: List[Step] = [
        Step(
            name="phase3_scenario_contract",
            cmd=[py, str(ROOT / "tests" / "contract" / "check_phase3_e2e_scenarios.py")],
            timeout_s=120,
        ),
        Step(
            name="gc_propose",
            cmd=[
                py,
                str(ROOT / "tools" / "gc" / "gc.py"),
                "propose",
                "--repo-root",
                str(repo_root),
                "--out-root",
                str(out_root / "gc_propose"),
                "--mode",
                "OPERATOR",
            ],
            timeout_s=480,
        ),
        Step(
            name="promotion_gate",
            cmd=[
                py,
                str(ROOT / "tools" / "promote" / "promote.py"),
                "--repo-root",
                str(repo_root),
                "--plan",
                str(ROOT / "tools" / "promote" / "fixtures" / "plan_minimal.json"),
                "--out-root",
                str(out_root / "promotion"),
                "--mode",
                "MAINTAINER",
            ],
            timeout_s=480,
        ),
    ]

    findings: List[Dict[str, Any]] = []
    step_results: List[Dict[str, Any]] = []

    for i, step in enumerate(steps):
        label = f"{i:02d}_{step.name}"
        res = run_cmd(
            cmd=step.cmd,
            cwd=repo_root,
            log_dir=logs_dir,
            label=label,
            timeout_s=step.timeout_s,
            capture_text=False,
        )
        rc = int(res.span.get("exit_code", 1))
        ok = (rc == 0)
        step_results.append(
            {
                "name": step.name,
                "ok": ok,
                "exit_code": rc,
                "cmd": step.cmd,
                "evidence": res.span,
            }
        )
        if not ok:
            findings.append(
                {
                    "id": f"cmd_fail_{step.name}",
                    "kind": "command_failure",
                    "severity": "high",
                    "message": f"{step.name} returned non-zero exit code ({rc}).",
                }
            )

    # Parse gate-level findings when command-level execution succeeded.
    promotion_report = _load_json(out_root / "promotion" / "PromotionReport.json")
    if promotion_report is not None:
        passed = bool(_deep_get(promotion_report, "decision.passed"))
        if not passed:
            findings.append(
                {
                    "id": "promotion_gate_not_passed",
                    "kind": "promotion_gate",
                    "severity": "medium",
                    "message": "Promotion gate completed but decision.passed is false.",
                    "path": _rel_to_root(out_root / "promotion" / "PromotionReport.json"),
                }
            )

    gc_plan = _load_json(out_root / "gc_propose" / "GCPlan.json")
    gc_actions = gc_plan.get("actions") if isinstance(gc_plan, dict) else None
    action_count = len(gc_actions) if isinstance(gc_actions, list) else 0

    command_failures = [f for f in findings if f.get("kind") == "command_failure"]
    status = "FAIL" if command_failures else ("OK_WITH_FINDINGS" if findings else "OK")

    report: Dict[str, Any] = {
        "schema": "leanatlas.phase3_governance_audit",
        "schema_version": "0.1.0",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo_root": str(repo_root),
        "out_root": str(out_root),
        "status": status,
        "summary": {
            "step_count": len(step_results),
            "failed_steps": len([s for s in step_results if not s.get("ok")]),
            "finding_count": len(findings),
            "gc_action_count": int(action_count),
        },
        "steps": step_results,
        "findings": findings,
    }

    report_path = out_root / "GovernanceAudit.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[phase3-governance] status={status} report={_rel_to_root(report_path)}")
    return 1 if command_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
