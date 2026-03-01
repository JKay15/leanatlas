#!/usr/bin/env python3
"""Contract: mine_attempt_logs must expose deterministic tool usage accounting.

Coverage:
- Tool usage is computed from AttemptLog.exec_spans[*].cmd (runtime evidence).
- binary_counts and command_counts must match fixture expectations.
- total_exec_spans must equal the number of valid exec spans.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "bench" / "mine_attempt_logs.py"
FIXTURE = ROOT / "tests" / "fixtures" / "bench_tool_usage"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    _assert(TOOL.exists(), f"missing tool: {TOOL}")
    _assert(FIXTURE.exists(), f"missing fixture root: {FIXTURE}")

    with tempfile.TemporaryDirectory(prefix="leanatlas_tool_usage_") as td:
        out = Path(td) / "latest.json"
        proc = _run(
            [
                sys.executable,
                str(TOOL),
                "--in",
                str(FIXTURE),
                "--out",
                str(out),
            ]
        )
        _assert(proc.returncode == 0, f"mine_attempt_logs failed:\n{proc.stdout}")
        _assert(out.exists(), "missing report output")

        obj = _read_json(out)
        _assert(obj.get("schema") == "leanatlas.bench.mine_attempt_logs", "unexpected bench schema")
        summary = obj.get("summary") or {}
        _assert(int(summary.get("run_count", -1)) == 2, "fixture should produce run_count=2")

        usage = obj.get("tool_usage")
        _assert(isinstance(usage, dict), "missing tool_usage block")
        _assert(str(usage.get("source")) == "AttemptLog.exec_spans[*].cmd", "unexpected tool_usage source")
        _assert(int(usage.get("total_exec_spans", -1)) == 3, "expected total_exec_spans=3")

        expected_binaries = {
            "lake": 2,
            "python": 1,
        }
        expected_commands = {
            "lake build": 1,
            "lake test": 1,
            "python tools/coordination/skills_regen.py": 1,
        }
        _assert((usage.get("binary_counts") or {}) == expected_binaries, "binary_counts mismatch")
        _assert((usage.get("command_counts") or {}) == expected_commands, "command_counts mismatch")

        top = usage.get("top_commands")
        _assert(isinstance(top, list) and len(top) == 3, "top_commands must include the 3 fixture commands")
        top_keys = sorted(str(x.get("command")) for x in top if isinstance(x, dict))
        _assert(top_keys == sorted(expected_commands.keys()), "top_commands keys mismatch")

    print("[tool-usage-accounting-policy][PASS]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[tool-usage-accounting-policy][FAIL] {ex}")
        raise SystemExit(1)
