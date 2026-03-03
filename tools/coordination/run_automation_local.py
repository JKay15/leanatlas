#!/usr/bin/env python3
"""Run automation runner in the source workspace (even when caller is in a worktree).

This wrapper is intentionally stdlib-only so it can start from generic Python in
Codex App worktree threads, then hop into repo-local `.venv` for real execution.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path
from typing import List


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools" / "coordination" / "run_automation.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.workflow.run_cmd import run_cmd


def _repo_python(repo_root: Path) -> str:
    venv_python = repo_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _build_cmd(args: argparse.Namespace) -> List[str]:
    cmd: List[str] = [_repo_python(ROOT), str(RUNNER), "--id", args.automation_id, "--advisor-mode", args.advisor_mode]
    if args.verify:
        cmd.append("--verify")
    if args.allow_planned:
        cmd.append("--allow-planned")
    if args.list:
        cmd = [_repo_python(ROOT), str(RUNNER), "--list"]
    if args.dry_runner:
        cmd.append("--dry-run")
    return cmd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="List automations only")
    ap.add_argument("--id", dest="automation_id", default=None, help="Automation id")
    ap.add_argument("--verify", action="store_true", help="Pass --verify to runner")
    ap.add_argument("--allow-planned", action="store_true", help="Pass --allow-planned to runner")
    ap.add_argument("--dry-run", action="store_true", help="Print command only; do not execute")
    ap.add_argument("--dry-runner", action="store_true", help="Execute runner in --dry-run mode")
    ap.add_argument(
        "--advisor-mode",
        choices=["off", "auto", "force"],
        default="off",
        help="Pass --advisor-mode to runner",
    )
    args = ap.parse_args()

    if not args.list and not args.automation_id:
        ap.error("--id is required unless --list is used")

    if not RUNNER.exists():
        raise SystemExit(f"missing runner: {RUNNER}")

    cmd = _build_cmd(args)
    print(f"[automation.local] repo_root={ROOT}")
    print(f"[automation.local] cmd={shlex.join(cmd)}")
    if args.dry_run:
        return 0

    logs_dir = ROOT / "artifacts" / "automation" / "_local_wrapper_logs"
    res = run_cmd(
        cmd=cmd,
        cwd=ROOT,
        log_dir=logs_dir,
        label="local_wrapper_exec",
        timeout_s=1800,
        capture_text=False,
    )
    return int(res.span.get("exit_code", 1))


if __name__ == "__main__":
    raise SystemExit(main())
