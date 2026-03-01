#!/usr/bin/env python3
"""Nightly real-agent smoke for Phase6 pack runner.

Runs one real-agent pack case through `run_pack --mode run` and verifies
that runtime artifacts are emitted.

Configuration:
- Set `LEANATLAS_REAL_AGENT_CMD` to a non-dummy command.
- If unset, this test prints a SKIP marker and exits 0.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_AGENT_CMD_ENV = "LEANATLAS_REAL_AGENT_CMD"


def _run(cmd: list[str], *, cwd: Path) -> None:
    res = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if res.returncode != 0:
        print("[FAIL] cmd:", " ".join(cmd))
        print("[stdout]\n", res.stdout)
        print("[stderr]\n", res.stderr)
        raise SystemExit(res.returncode)


def _load_real_agent_cmd() -> str | None:
    cmd = os.environ.get(REAL_AGENT_CMD_ENV, "").strip()
    if not cmd:
        print(f"[agent-eval-real][SKIP] {REAL_AGENT_CMD_ENV} is not set.")
        return None
    if "dummy_agent.py" in cmd:
        print(f"[agent-eval-real][FAIL] {REAL_AGENT_CMD_ENV} points to dummy agent, expected a real agent command.")
        raise SystemExit(2)
    return cmd


def main() -> int:
    real_agent_cmd = _load_real_agent_cmd()
    if real_agent_cmd is None:
        return 0

    pack_path = REPO_ROOT / "tests" / "agent_eval" / "packs" / "mentor_keywords_v0" / "pack.yaml"
    if not pack_path.exists():
        print(f"[agent-eval-real][FAIL] missing pack: {pack_path}")
        return 2

    with tempfile.TemporaryDirectory(prefix="leanatlas_pack_real_") as td:
        out_root = Path(td) / "out"
        out_root.mkdir(parents=True, exist_ok=True)

        _run(
            [
                sys.executable,
                "tools/agent_eval/run_pack.py",
                "--pack",
                str(pack_path),
                "--mode",
                "run",
                "--limit",
                "1",
                "--out-root",
                str(out_root),
                "--agent-cmd",
                real_agent_cmd,
            ],
            cwd=REPO_ROOT,
        )

        eval_root = out_root / "mentor_keywords_v0"
        stamps = sorted([p for p in eval_root.iterdir() if p.is_dir()]) if eval_root.exists() else []
        if not stamps:
            print("[agent-eval-real][FAIL] run_pack produced no eval dirs")
            return 2

        eval_dir = stamps[-1]
        plan = eval_dir / "Plan.json"
        spans = list(eval_dir.glob("runs/*/*/agent_exec_span.json"))
        if not plan.exists() or not spans:
            print("[agent-eval-real][FAIL] missing Plan.json or agent_exec_span artifacts")
            print(f"  eval_dir={eval_dir}")
            return 2

    print("[agent-eval-real][OK] pack real-agent smoke completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
