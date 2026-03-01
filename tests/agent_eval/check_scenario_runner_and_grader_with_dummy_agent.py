#!/usr/bin/env python3
"""Core TDD: run_scenario --mode run with dummy agent, then grade_scenario.

This test validates the scenario harness itself (single workspace with interleaving steps),
including maintainer overlays and snapshot-based grading.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str], *, cwd: Path) -> None:
    res = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if res.returncode != 0:
        print("[FAIL] cmd:", " ".join(cmd))
        print("[stdout]\n", res.stdout)
        print("[stderr]\n", res.stderr)
        raise SystemExit(res.returncode)


def main() -> int:
    scenario_path = (
        REPO_ROOT
        / "tests"
        / "agent_eval"
        / "scenarios"
        / "core_dummy_smoke_v0"
        / "scenario.yaml"
    )
    if not scenario_path.exists():
        print(f"Missing scenario: {scenario_path}")
        return 2

    with tempfile.TemporaryDirectory(prefix="leanatlas_scn_dummy_") as td:
        out_root = Path(td) / "out"
        out_root.mkdir(parents=True, exist_ok=True)

        _run(
            [
                sys.executable,
                "tools/agent_eval/run_scenario.py",
                "--scenario",
                str(scenario_path),
                "--mode",
                "run",
                "--out-root",
                str(out_root),
                "--agent-cmd",
                "python tools/agent_eval/dummy_agent.py",
            ],
            cwd=REPO_ROOT,
        )

        eval_root = out_root / "core_dummy_smoke_v0"
        stamps = sorted([p for p in eval_root.iterdir() if p.is_dir()])
        if not stamps:
            print("[FAIL] run_scenario produced no eval dirs")
            return 2
        eval_dir = stamps[-1]

        _run(
            [sys.executable, "tools/agent_eval/grade_scenario.py", "--eval-dir", str(eval_dir)],
            cwd=REPO_ROOT,
        )

    print("[OK] scenario runner + grader dummy e2e")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
