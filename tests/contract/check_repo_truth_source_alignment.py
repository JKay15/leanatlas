#!/usr/bin/env python3
"""Contract: retained repo truth sources must stay aligned for OPERATOR mode and DedupGate V0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(rel)
    return path.read_text(encoding="utf-8")


def _fail(msg: str) -> int:
    print(f"[repo-truth-source][FAIL] {msg}", file=sys.stderr)
    return 2


def _require(text: str, snippet: str, rel: str) -> None:
    if snippet not in text:
        raise AssertionError(f"{rel} missing required snippet `{snippet}`")


def _forbid(text: str, snippet: str, rel: str) -> None:
    if snippet in text:
        raise AssertionError(f"{rel} contains forbidden stale snippet `{snippet}`")


def main() -> int:
    try:
        agents = _read("AGENTS.md")
        operator = _read("docs/agents/OPERATOR_WORKFLOW.md")
        operator_skill = _read(".agents/skills/leanatlas-operator-proof-loop/SKILL.md")
        override_minimal = _read("docs/agents/templates/AGENTS.override.minimal.md")
        dedup_skill = _read(".agents/skills/leanatlas-dedup/SKILL.md")
        dedup_readme = _read("tools/dedup/README.md")
        dedup_py = _read("tools/dedup/dedup.py")
        phase3 = _read("tools/capabilities/phase3.yaml")
        status = _read("docs/agents/STATUS.md")
        automation_registry = _read("automations/registry.json")
    except FileNotFoundError as exc:
        return _fail(f"missing required file: {exc}")

    try:
        _require(agents, "- **OPERATOR (default)**: No `AGENTS.override.md` in repo root.", "AGENTS.md")
        _require(agents, "- **MAINTAINER**: A human created a local `AGENTS.override.md` in repo root", "AGENTS.md")
        _require(operator, "Default mode is OPERATOR.", "docs/agents/OPERATOR_WORKFLOW.md")
        _require(
            operator,
            "MAINTAINER is enabled only when a human has created a local root `AGENTS.override.md` (gitignored).",
            "docs/agents/OPERATOR_WORKFLOW.md",
        )
        _require(
            operator_skill,
            "- Confirm OPERATOR (no root `AGENTS.override.md`).",
            ".agents/skills/leanatlas-operator-proof-loop/SKILL.md",
        )
        _require(
            override_minimal,
            "Copying this file to repository root as `AGENTS.override.md` enables MAINTAINER mode.",
            "docs/agents/templates/AGENTS.override.minimal.md",
        )
        _require(
            override_minimal,
            "Deleting the root `AGENTS.override.md` restores OPERATOR mode.",
            "docs/agents/templates/AGENTS.override.minimal.md",
        )
        _forbid(operator, ".cache/leanatlas/mode.json", "docs/agents/OPERATOR_WORKFLOW.md")
        _forbid(override_minimal, ".cache/leanatlas/mode.json", "docs/agents/templates/AGENTS.override.minimal.md")

        _require(
            dedup_skill,
            "Current V0 implementation is the source-backed Python scan in `tools/dedup/dedup.py`.",
            ".agents/skills/leanatlas-dedup/SKILL.md",
        )
        _require(
            dedup_skill,
            "Compiled-environment DedupGate scanning is follow-on work, not current behavior.",
            ".agents/skills/leanatlas-dedup/SKILL.md",
        )
        _require(
            dedup_skill,
            "- `.cache/leanatlas/dedup/scan/DedupReport.json`",
            ".agents/skills/leanatlas-dedup/SKILL.md",
        )
        _require(
            dedup_skill,
            "- `.cache/leanatlas/dedup/scan/DedupReport.md`",
            ".agents/skills/leanatlas-dedup/SKILL.md",
        )
        _forbid(
            dedup_skill,
            ".cache/leanatlas/dedup/scan/<stamp>/DedupReport.json",
            ".agents/skills/leanatlas-dedup/SKILL.md",
        )
        _forbid(
            dedup_skill,
            ".cache/leanatlas/dedup/scan/<stamp>/DedupReport.md",
            ".agents/skills/leanatlas-dedup/SKILL.md",
        )
        _forbid(dedup_skill, "docs/contracts/DEDUP_GATE_CONTRACT.md", ".agents/skills/leanatlas-dedup/SKILL.md")
        _forbid(dedup_skill, "Truth source is the Lean environment.", ".agents/skills/leanatlas-dedup/SKILL.md")

        _require(
            dedup_readme,
            "Current V0 implementation: deterministic source-backed scan for duplicate `instance` declarations in `LeanAtlas/**`.",
            "tools/dedup/README.md",
        )
        _require(
            dedup_readme,
            "Follow-on goal: replace the source-backed scan with compiled-environment scanning plus stronger canonicalization.",
            "tools/dedup/README.md",
        )
        _forbid(dedup_readme, "scan declarations in the **compiled environment**", "tools/dedup/README.md")

        _require(dedup_py, "Phase-3 V0 currently uses a source-backed scan", "tools/dedup/dedup.py")
        _require(
            phase3,
            "description: Produce DedupReport (DedupGate). V0 implementation scans source for instance duplicates.",
            "tools/capabilities/phase3.yaml",
        )
        _require(
            status,
            "- DedupGate V0 current implementation: source-backed instance scan via `tools/dedup/dedup.py`.",
            "docs/agents/STATUS.md",
        )
        _require(
            status,
            "- Compiled-environment DedupGate scanning remains follow-on work.",
            "docs/agents/STATUS.md",
        )
        _require(
            automation_registry,
            "\"purpose\": \"Nightly: run the source-backed DedupGate V0 instance scan and open a PR if duplicates are detected.\"",
            "automations/registry.json",
        )
        _forbid(
            automation_registry,
            "scan environment for duplicate instances using permutation-invariant key",
            "automations/registry.json",
        )
    except AssertionError as exc:
        return _fail(str(exc))

    print("[repo-truth-source] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
