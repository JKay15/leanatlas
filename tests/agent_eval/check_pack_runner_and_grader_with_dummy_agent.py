#!/usr/bin/env python3
"""Core TDD: run_pack --mode run with the deterministic dummy agent, then grade_pack.

This test exercises:
- repo skeleton materialization
- fixture overlay application
- unified run_cmd wrapper usage
- report emission into Problems/<slug>/Reports/<run_id>
- deterministic grading logic (schema + expected status)
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
    pack_path = REPO_ROOT / "tests" / "agent_eval" / "packs" / "core_smoke_dummy" / "pack.yaml"
    if not pack_path.exists():
        print(f"Missing pack: {pack_path}")
        return 2

    with tempfile.TemporaryDirectory(prefix="leanatlas_pack_dummy_") as td:
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
                "--out-root",
                str(out_root),
                "--agent-cmd",
                "python tools/agent_eval/dummy_agent.py",
            ],
            cwd=REPO_ROOT,
        )

        eval_root = out_root / "core_smoke_dummy"
        stamps = sorted([p for p in eval_root.iterdir() if p.is_dir()])
        if not stamps:
            print("[FAIL] run_pack produced no eval dirs")
            return 2
        eval_dir = stamps[-1]

        _run([sys.executable, "tools/agent_eval/grade_pack.py", "--eval-dir", str(eval_dir)], cwd=REPO_ROOT)

    print("[OK] pack runner + grader dummy e2e")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
