#!/usr/bin/env python3
"""Smoke test: Phase6 agent-eval runner can materialize a workspace.

This test must stay fast enough for the core tier.

We run with `--limit 1` to materialize exactly one (task, variant) workspace
and verify that the expected files exist.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    out_root = REPO / "artifacts" / "_tmp_agent_eval_materialize"
    if out_root.exists():
        shutil.rmtree(out_root)

    cmd = [
        sys.executable,
        "tools/agent_eval/run_pack.py",
        "--pack",
        "tests/agent_eval/packs/mentor_keywords_v0/pack.yaml",
        "--mode",
        "materialize",
        "--limit",
        "1",
        "--out-root",
        str(out_root),
        "--eval-id",
        "_materialize_smoke",
    ]
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if p.returncode != 0:
        print("runner failed")
        print("stdout:\n", p.stdout)
        print("stderr:\n", p.stderr)
        return 1

    plans = list((out_root / "_materialize_smoke").glob("*/Plan.json"))
    if not plans:
        print("Plan.json not found")
        return 1

    plan_path = plans[0]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    runs = plan.get("runs")
    if not isinstance(runs, list) or not runs:
        print("Plan.json malformed")
        return 1

    r0 = runs[0]
    ws_rel = r0.get("workspace_rel")
    prompt_rel = r0.get("prompt_rel")
    if not ws_rel or not prompt_rel:
        print("Plan.json missing workspace_rel/prompt_rel")
        return 1

    base_dir = plan_path.parent
    ws_dir = base_dir / ws_rel
    prompt_path = base_dir / prompt_rel
    ctx_path = prompt_path.parent / "CONTEXT.json"
    baseline_path = prompt_path.parent / "BaselineToolSurface.json"

    if not ws_dir.exists():
        print(f"workspace missing: {ws_dir}")
        return 1
    if not prompt_path.exists():
        print(f"PROMPT.md missing: {prompt_path}")
        return 1
    if not ctx_path.exists():
        print(f"CONTEXT.json missing: {ctx_path}")
        return 1
    if not baseline_path.exists():
        print(f"BaselineToolSurface.json missing: {baseline_path}")
        return 1

    # Minimal repo skeleton sanity.
    if not (ws_dir / "AGENTS.md").exists():
        print("workspace missing AGENTS.md")
        return 1
    if not (ws_dir / "Problems").exists():
        print("workspace missing Problems/")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
