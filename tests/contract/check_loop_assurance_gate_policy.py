#!/usr/bin/env python3
"""Contract check: assurance-level gate semantics (FAST/LIGHT/STRICT)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.assurance import AssuranceLevel, evaluate_wave_completion_gate


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _base_wave(level: str, state: str) -> dict:
    return {
        "assurance_level": level,
        "final_decision": {"state": state},
        "evidence": {
            "ai_review_prompt_ref": "artifacts/review_prompt.md",
            "ai_review_response_ref": "artifacts/review_response.md",
            "ai_review_summary_ref": "artifacts/review_summary.json",
        },
    }


def main() -> int:
    # STRICT + PASSED + complete evidence -> pass
    ok, reason = evaluate_wave_completion_gate(_base_wave(AssuranceLevel.STRICT.value, "PASSED"))
    _assert(ok, f"STRICT with complete evidence should pass, got reason={reason}")

    # STRICT + PASSED + missing evidence -> fail
    bad = _base_wave(AssuranceLevel.STRICT.value, "PASSED")
    del bad["evidence"]["ai_review_summary_ref"]
    ok, reason = evaluate_wave_completion_gate(bad)
    _assert(not ok, "STRICT PASSED without summary ref must fail")
    _assert(reason == "STRICT_MISSING_AI_REVIEW_EVIDENCE", f"unexpected reason={reason}")

    # STRICT but non-terminal pass-claim is not blocked by review evidence gate
    triaged = _base_wave(AssuranceLevel.STRICT.value, "TRIAGED")
    triaged["evidence"] = {}
    ok, reason = evaluate_wave_completion_gate(triaged)
    _assert(ok, f"STRICT TRIAGED should not be blocked by completion gate, got reason={reason}")

    # FAST/LIGHT should not hard-block completion when evidence missing
    for level in (AssuranceLevel.FAST.value, AssuranceLevel.LIGHT.value):
        w = _base_wave(level, "PASSED")
        w["evidence"] = {}
        ok, reason = evaluate_wave_completion_gate(w)
        _assert(ok, f"{level} should not be hard-blocked, got reason={reason}")

    print("[loop-assurance-gate-policy] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
