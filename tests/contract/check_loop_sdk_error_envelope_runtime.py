#!/usr/bin/env python3
"""Contract check: LOOP SDK runtime error envelope semantics."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.sdk import loop, resume, run


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loop_sdk_m5_") as td:
        repo = Path(td)

        spec = loop(
            loop_id="loop.sdk.runtime.v1",
            graph_mode="STATIC_USER_MODE",
            input_projection_hash="1" * 64,
            instruction_chain_hash="2" * 64,
            dependency_pin_set_id="pins.20260305",
            wave_id="loop.wave_b.sdk.v1",
        )
        ok = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-ok-001",
            agent_provider="codex_cli",
            agent_profile="profiles/codex_review.json",
            instruction_scope_refs=[str(ROOT / "AGENTS.md")],
            review_history=[{"round": 0, "summary": "cold start"}],
        )
        _assert(ok["response"]["status"] == "OK", "run() should succeed for valid input")

        missing = resume(
            run_key="f" * 64,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-err-001",
            agent_provider="codex_cli",
            instruction_scope_refs=[str(ROOT / "AGENTS.md")],
        )
        _assert(missing["response"]["status"] == "ERROR", "resume() on unknown run_key should return ERROR envelope")
        err = missing["response"]["error"]
        _assert(err["error_code"] == "CHECKPOINT_NOT_FOUND", "missing checkpoint must map to CHECKPOINT_NOT_FOUND")
        _assert(err["error_class"] == "NON_RETRYABLE_CONTRACT", "error_class mismatch")
        _assert(err["retryable"] is False, "CHECKPOINT_NOT_FOUND should be non-retryable")
        _assert(
            len(missing["response"].get("trace_refs", [])) >= 1,
            "error envelope should carry trace_refs for evidence",
        )

    print("[loop-sdk-error-envelope-runtime] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
