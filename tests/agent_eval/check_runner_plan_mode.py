#!/usr/bin/env python3
"""Smoke test: Phase6 agent-eval runner can produce a plan.

We deliberately run in `--mode plan` to avoid copying workspaces or running external agents.
This must be fast enough for the core tier.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    out_root = REPO / "artifacts" / "_tmp_agent_eval_plan"
    if out_root.exists():
        # Clean up from a previous run
        for p in out_root.rglob("*"):
            if p.is_file():
                p.unlink()
            else:
                try:
                    p.rmdir()
                except OSError:
                    pass

    cmd = [
        sys.executable,
        "tools/agent_eval/run_pack.py",
        "--pack",
        "tests/agent_eval/packs/mentor_keywords_v0/pack.yaml",
        "--mode",
        "plan",
        "--limit",
        "1",
        "--out-root",
        str(out_root),
        "--eval-id",
        "_plan_smoke",
        "--agent-provider",
        "codex_cli",
    ]
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if p.returncode != 0:
        print("runner failed")
        print("stdout:\n", p.stdout)
        print("stderr:\n", p.stderr)
        return 1

    # Find Plan.json
    plans = list((out_root / "_plan_smoke").glob("*/Plan.json"))
    if not plans:
        print("Plan.json not found")
        return 1

    data = json.loads(plans[0].read_text(encoding="utf-8"))
    if "runs" not in data or not isinstance(data["runs"], list) or not data["runs"]:
        print("Plan.json malformed")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
