#!/usr/bin/env python3
"""Contract: onboarding environment completion must compact root AGENTS.md.

Checks:
1) archive docs exist (verbose + compact blocks)
2) finalize script marks completion only after bootstrap+doctor+real_agent_cmd
3) operational readiness requires the extra `automations` step
3) finalize script rewrites AGENTS onboarding block to compact form
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "onboarding" / "finalize_onboarding.py"
AGENTS = ROOT / "AGENTS.md"
VERBOSE_ARCHIVE = ROOT / "docs" / "agents" / "archive" / "AGENTS_ONBOARDING_VERBOSE.md"
COMPACT_ARCHIVE = ROOT / "docs" / "agents" / "archive" / "AGENTS_ONBOARDING_COMPACT.md"

START = "<!-- ONBOARDING_BLOCK_START -->"
END = "<!-- ONBOARDING_BLOCK_END -->"


def _run(step: str, repo_root: Path) -> None:
    cmd = [sys.executable, str(SCRIPT), "--step", step, "--repo-root", str(repo_root)]
    p = subprocess.run(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise SystemExit(f"[onboarding.compaction][FAIL] finalize script failed ({step})\n{p.stdout}")


def main() -> int:
    missing = [p for p in (SCRIPT, AGENTS, VERBOSE_ARCHIVE, COMPACT_ARCHIVE) if not p.exists()]
    if missing:
        print("[onboarding.compaction][FAIL] missing required files:")
        for p in missing:
            print(f" - {p.relative_to(ROOT)}")
        return 2

    with tempfile.TemporaryDirectory(prefix="leanatlas_onboarding_compaction_") as td:
        tmp_root = Path(td)
        (tmp_root / "docs" / "agents" / "archive").mkdir(parents=True, exist_ok=True)
        shutil.copy2(AGENTS, tmp_root / "AGENTS.md")
        shutil.copy2(VERBOSE_ARCHIVE, tmp_root / "docs" / "agents" / "archive" / VERBOSE_ARCHIVE.name)
        shutil.copy2(COMPACT_ARCHIVE, tmp_root / "docs" / "agents" / "archive" / COMPACT_ARCHIVE.name)

        _run("bootstrap", tmp_root)
        state_path = tmp_root / ".cache" / "leanatlas" / "onboarding" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("completed"):
            print("[onboarding.compaction][FAIL] completed=true after bootstrap only")
            return 2

        _run("doctor", tmp_root)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("completed"):
            print("[onboarding.compaction][FAIL] completed=true before real_agent_cmd is set")
            return 2

        _run("real_agent_cmd", tmp_root)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not state.get("completed"):
            print("[onboarding.compaction][FAIL] completed=false after bootstrap+doctor+real_agent_cmd")
            return 2
        if state.get("operational_ready"):
            print("[onboarding.compaction][FAIL] operational_ready=true before automations step")
            return 2

        _run("automations", tmp_root)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not state.get("operational_ready"):
            print("[onboarding.compaction][FAIL] operational_ready=false after automations step")
            return 2

        agents_text = (tmp_root / "AGENTS.md").read_text(encoding="utf-8")
        if START not in agents_text or END not in agents_text:
            print("[onboarding.compaction][FAIL] onboarding markers missing after compaction")
            return 2
        if "Print the LeanAtlas banner" in agents_text:
            print("[onboarding.compaction][FAIL] verbose onboarding text still present after compaction")
            return 2
        if "AGENTS_ONBOARDING_VERBOSE.md" not in agents_text:
            print("[onboarding.compaction][FAIL] compact block not applied")
            return 2
        if "including greetings like `hi`" not in agents_text:
            print("[onboarding.compaction][FAIL] compact block missing first-message greeting trigger rule")
            return 2
        if "Do not reply with a generic question before onboarding routing." not in agents_text:
            print("[onboarding.compaction][FAIL] compact block missing generic-reply guard")
            return 2
        if "operational_ready != true" not in agents_text:
            print("[onboarding.compaction][FAIL] compact block missing operational readiness gate")
            return 2
        if "steps.automations != \"ok\"" not in agents_text:
            print("[onboarding.compaction][FAIL] compact block missing automations step gate")
            return 2
        if "Do not proceed with normal task execution until automation readiness is verified." not in agents_text:
            print("[onboarding.compaction][FAIL] compact block missing automation blocking rule")
            return 2

    print("[onboarding.compaction] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
