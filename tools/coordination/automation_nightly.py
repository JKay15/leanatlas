#!/usr/bin/env python3
"""Nightly automation runner (deterministic).

This tool is intended to be called by automation (cron / CI schedule) to:
- verify pins are still valid
- run a small smoke suite
- produce a single run manifest for audit

Evidence-chain upgrade:
- Do NOT call subprocess directly.
- Use tools/workflow/run_cmd.py so logs are captured + hashed.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `from tools.*` imports when executing as a script (sys.path[0] == tools/...).
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from tools.workflow.run_cmd import run_cmd


ARTIFACTS = ROOT / "artifacts" / "automation_nightly"


@dataclass
class Step:
    name: str
    argv: List[str]
    timeout_s: int = 300


DEFAULT_STEPS: List[Step] = [
    Step("deps_smoke", ["python", "tests/setup/deps_smoke.py"], timeout_s=300),
    Step("core_tests", ["python", "tests/run.py", "--profile", "core"], timeout_s=600),
]


def main() -> int:
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = ARTIFACTS / run_id
    logs_dir = run_dir / "logs"
    run_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {
        "schema": "leanatlas.automation_nightly_manifest",
        "schema_version": "0.2.0",
        "run_id": run_id,
        "started_utc": run_id,
        "steps": [],
        "status": "RUNNING",
    }

    overall_ok = True

    for i, step in enumerate(DEFAULT_STEPS):
        label = f"{i:02d}_{step.name}"
        res = run_cmd(
            cmd=step.argv,
            cwd=ROOT,
            log_dir=logs_dir,
            label=label,
            timeout_s=step.timeout_s,
            capture_text=False,
        )
        rc = int(res.span.get("exit_code", 1))
        ok = (rc == 0)
        overall_ok = overall_ok and ok

        manifest["steps"].append(
            {
                "name": step.name,
                "argv": step.argv,
                "timeout_s": step.timeout_s,
                "ok": ok,
                "exit_code": rc,
                "evidence": res.span,
            }
        )

        # Fail fast on dependency smoke failures
        if step.name == "deps_smoke" and not ok:
            break

    manifest["status"] = "OK" if overall_ok else "FAIL"
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
