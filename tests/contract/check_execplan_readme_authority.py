#!/usr/bin/env python3
"""Contract: execplan README must not pretend to be the authoritative active-plan source."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "docs" / "agents" / "execplans" / "README.md"


def _fail(msg: str) -> int:
    print(f"[execplan-readme-authority][FAIL] {msg}", file=sys.stderr)
    return 2


def main() -> int:
    if not README.exists():
        return _fail(f"missing file: {README.relative_to(ROOT)}")

    text = README.read_text(encoding="utf-8")
    if "## Current plans" in text:
        return _fail("README must not present a hand-maintained `Current plans` section as if it were authoritative")

    required_snippets = [
        "non-authoritative",
        "`status:` front matter",
        "maintainer LOOP",
        "artifacts/loop_runtime/by_execplan/<stable_execplan_id>/MaintainerCloseoutRef.json",
        "if no stable closeout alias exists yet",
        "artifacts/loop_runtime/by_key/**",
    ]
    for snippet in required_snippets:
        if snippet not in text:
            return _fail(f"README missing required authority-boundary snippet `{snippet}`")

    print("[execplan-readme-authority] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
