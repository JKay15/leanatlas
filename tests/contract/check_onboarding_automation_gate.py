#!/usr/bin/env python3
"""Contract: onboarding must enforce automation readiness as a hard gate."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    verify_script = ROOT / "tools" / "onboarding" / "verify_automation_install.py"
    _require(verify_script.exists(), "missing tools/onboarding/verify_automation_install.py")

    onboarding = (ROOT / "docs" / "agents" / "ONBOARDING.md").read_text(encoding="utf-8")
    _require("operational_ready" in onboarding, "ONBOARDING.md must define operational_ready")
    _require(
        "tools/onboarding/verify_automation_install.py --mark-done" in onboarding,
        "ONBOARDING.md must include automation readiness mark command",
    )
    _require(
        "do not proceed with normal proof/maintainer tasks" in onboarding.lower(),
        "ONBOARDING.md must block normal tasks before automation readiness",
    )

    quickstart = (ROOT / "docs" / "setup" / "QUICKSTART.md").read_text(encoding="utf-8")
    _require("hard operational gate" in quickstart.lower(), "QUICKSTART.md must label automation step as hard gate")
    _require(
        "./.venv/bin/python tools/onboarding/verify_automation_install.py --mark-done" in quickstart,
        "QUICKSTART.md must include automation readiness verification command",
    )

    skill = (ROOT / ".agents" / "skills" / "leanatlas-onboard" / "SKILL.md").read_text(encoding="utf-8")
    _require(
        "verify_automation_install.py --mark-done" in skill,
        "leanatlas-onboard skill must include automation verification command",
    )
    _require(
        "block normal task work until verified" in skill.lower(),
        "leanatlas-onboard skill must include blocking behavior",
    )

    checklist = (
        ROOT / "docs" / "agents" / "templates" / "AUTOMATION_INSTALL_CHECKLIST.md"
    ).read_text(encoding="utf-8")
    _require(
        "Do not ask me to author prompt text manually" in checklist,
        "automation install checklist must enforce Codex-generated install blocks",
    )

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    _require("operational_ready != true" in agents, "AGENTS onboarding block must gate on operational_ready")
    _require('steps.automations != "ok"' in agents, "AGENTS onboarding block must gate on steps.automations")

    print("[onboarding.automation-gate][PASS]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[onboarding.automation-gate][FAIL] {ex}")
        raise SystemExit(1)
