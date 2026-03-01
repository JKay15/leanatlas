#!/usr/bin/env python3
"""Enforce SKILL.md standard headers.

Rationale: Skills are routing + procedure. Without explicit routing blocks and
must-run checks, agents drift into 'vibes' and hallucinate capabilities.

Contract: docs/contracts/SKILLS_GROWTH_CONTRACT.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".agents" / "skills"

REQUIRED_HEADINGS = [
    "## Use when",
    "## Don't use when",
    "## Outputs",
    "## Must-run checks",
]


def section_text(md: str, heading: str) -> str | None:
    # naive but deterministic markdown section extraction
    idx = md.find(heading)
    if idx < 0:
        return None
    after = md[idx + len(heading) :]
    # stop at next level-2 heading
    m = re.search(r"\n## ", after)
    if not m:
        return after
    return after[: m.start()]


def bullet_count(block: str) -> int:
    if block is None:
        return 0
    return len([ln for ln in block.splitlines() if ln.strip().startswith("-")])


def main() -> int:
    if not SKILLS.exists():
        print("[skills] .agents/skills missing", file=sys.stderr)
        return 2

    skill_files = sorted(SKILLS.glob("**/SKILL.md"))
    if not skill_files:
        print("[skills] No SKILL.md files found", file=sys.stderr)
        return 2

    bad = 0
    for f in skill_files:
        md = f.read_text(encoding="utf-8")
        missing = [h for h in REQUIRED_HEADINGS if h not in md]
        if missing:
            bad += 1
            print(f"[skills][FAIL] {f.relative_to(ROOT)} missing headings: {missing}", file=sys.stderr)
            continue

        use_when = section_text(md, "## Use when")
        dont = section_text(md, "## Don't use when")
        out = section_text(md, "## Outputs")
        checks = section_text(md, "## Must-run checks")

        # routing should be short but non-empty
        if not (1 <= bullet_count(use_when) <= 3):
            bad += 1
            print(f"[skills][FAIL] {f.relative_to(ROOT)}: Use when must have 1-3 bullets", file=sys.stderr)

        if not (1 <= bullet_count(dont) <= 3):
            bad += 1
            print(f"[skills][FAIL] {f.relative_to(ROOT)}: Don't use when must have 1-3 bullets", file=sys.stderr)

        if bullet_count(out) < 1:
            bad += 1
            print(f"[skills][FAIL] {f.relative_to(ROOT)}: Outputs must list at least 1 bullet", file=sys.stderr)

        if bullet_count(checks) < 2:
            bad += 1
            print(f"[skills][FAIL] {f.relative_to(ROOT)}: Must-run checks must list at least 2 bullets", file=sys.stderr)

        if not missing:
            print(f"[skills][OK] {f.relative_to(ROOT)}")

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
