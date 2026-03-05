#!/usr/bin/env python3
"""Contract: nightly real-agent entrypoints must support provider/profile config.

This keeps nightly execution compatible with provider abstraction rollout while
preserving legacy command-based configuration.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "tests" / "agent_eval" / "exec_pack_real_agent_nightly.py"
SCENARIO = ROOT / "tests" / "agent_eval" / "exec_scenario_real_agent_nightly.py"


def _require(cond: bool, msg: str, errors: list[str]) -> None:
    if not cond:
        errors.append(msg)


def _check_file(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing file: {path.relative_to(ROOT)}")
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = str(path.relative_to(ROOT))

    _require("LEANATLAS_REAL_AGENT_CMD" in text, f"{rel}: missing legacy cmd env support", errors)
    _require("LEANATLAS_REAL_AGENT_PROVIDER" in text, f"{rel}: missing provider env support", errors)
    _require("LEANATLAS_REAL_AGENT_PROFILE" in text, f"{rel}: missing profile env support", errors)
    _require("resolve_agent_invocation" in text, f"{rel}: must use shared resolver", errors)
    _require("--agent-provider" in text, f"{rel}: runner args must include --agent-provider path", errors)


def main() -> int:
    errors: list[str] = []
    _check_file(PACK, errors)
    _check_file(SCENARIO, errors)

    if errors:
        print("[agent-eval.real-agent-provider][FAIL]")
        for e in errors:
            print(" -", e)
        return 2

    print("[agent-eval.real-agent-provider][PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
