#!/usr/bin/env python3
"""Python command policy check (core).

This repo currently allows:
- `./.venv/bin/python ...`
- `uv run --locked python ...`
- `python ...` (for user-facing setup docs and portable shell scripts)

Policy enforced here:
- `python3` command forms are forbidden in docs/skills/automations (use `python`).
- Legacy `--tier` flag is forbidden in critical onboarding/setup entry docs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCAN_MD_ROOTS = [
    ROOT / "docs",
    ROOT / ".agents" / "skills",
]

CRITICAL_FILES = [
    ROOT / "AGENTS.md",
    ROOT / "INIT_FOR_CODEX.md",
    ROOT / "docs" / "agents" / "ONBOARDING.md",
    ROOT / "docs" / "agents" / "CODEX_APP_PROMPTS.md",
    ROOT / "docs" / "setup" / "QUICKSTART.md",
]

RE_PY3_LINE = re.compile(r"^\s*python3\s+")
RE_PY3_INLINE = re.compile(r"`python3\s+")


def _iter_md_files():
    for base in SCAN_MD_ROOTS:
        if not base.exists():
            continue
        for p in base.rglob("*.md"):
            yield p


def _scan_python3_violations(path: Path) -> list[str]:
    out: list[str] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for i, line in enumerate(text.splitlines(), start=1):
        if RE_PY3_LINE.search(line) or RE_PY3_INLINE.search(line):
            out.append(f"{path.relative_to(ROOT)}:{i}: {line.rstrip()}")
    return out


def _scan_legacy_tier(path: Path) -> list[str]:
    out: list[str] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for i, line in enumerate(text.splitlines(), start=1):
        if "--tier" in line:
            lower = line.lower()
            # Allow explanatory text such as "legacy --tier" migration notes.
            if "legacy" in lower or "use `--profile`" in lower:
                continue
            out.append(f"{path.relative_to(ROOT)}:{i}: {line.rstrip()}")
    return out


def _scan_registry_python3() -> list[str]:
    reg = ROOT / "automations" / "registry.json"
    if not reg.exists():
        return []
    obj = json.loads(reg.read_text(encoding="utf-8"))
    autos = obj.get("automations") or []
    out: list[str] = []
    for a in autos:
        aid = a.get("id", "<unknown>")
        for section in ("deterministic", "verify"):
            steps = ((a.get(section) or {}).get("steps")) or []
            for s in steps:
                cmd = s.get("cmd") or []
                if isinstance(cmd, list) and cmd and cmd[0] == "python3":
                    out.append(f"automations/registry.json: {aid}.{section}.{s.get('name')} starts with python3")
        tdd = a.get("tdd") or {}
        dry = (tdd.get("dry_run") or {}).get("cmd") or []
        if isinstance(dry, list) and dry and dry[0] == "python3":
            out.append(f"automations/registry.json: {aid}.tdd.dry_run starts with python3")
    return out


def main() -> int:
    violations: list[str] = []

    for p in _iter_md_files():
        violations.extend(_scan_python3_violations(p))

    for p in CRITICAL_FILES:
        if p.exists():
            violations.extend(_scan_legacy_tier(p))

    violations.extend(_scan_registry_python3())

    if violations:
        print("[python-policy] FAIL", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 2

    print("[python-policy] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
