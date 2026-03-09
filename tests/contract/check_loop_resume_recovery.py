#!/usr/bin/env python3
"""Contract check: LOOP runtime resume/recovery semantics (Wave-B M2)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.run_key import RunKeyInput, compute_run_key
from tools.loop.runtime import LoopRuntime


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loop_resume_m2_") as td:
        repo = Path(td)
        run_key = compute_run_key(
            RunKeyInput(
                loop_id="loop.wave_b.runtime.v0",
                graph_mode="STATIC_USER_MODE",
                input_projection_hash="1" * 64,
                instruction_chain_hash="2" * 64,
                dependency_pin_set_id="pins.20260305",
            )
        )

        rt = LoopRuntime.start(
            repo_root=repo,
            run_key=run_key,
            wave_id="loop.wave_b.runtime.v0",
        )
        rt.submit_for_review(at_utc="2026-03-05T10:00:00Z")

        # Simulate interruption: reconstruct runtime from persisted checkpoints.
        rt = LoopRuntime.resume(repo_root=repo, run_key=run_key)
        rt.apply_review(
            verdict="REPAIRABLE",
            finding_fingerprint="a" * 64,
            wall_clock_used_minutes=5,
            at_utc="2026-03-05T10:01:00Z",
        )

        rt = LoopRuntime.resume(repo_root=repo, run_key=run_key)
        rt.submit_for_review(at_utc="2026-03-05T10:02:00Z")
        rt.apply_review(
            verdict="PASS",
            finding_fingerprint="b" * 64,
            wall_clock_used_minutes=9,
            at_utc="2026-03-05T10:03:00Z",
        )

        rt = LoopRuntime.resume(repo_root=repo, run_key=run_key)
        state = rt.state

        _assert(state["current_state"] == "PASSED", "final state should be PASSED")
        _assert(state["used_ai_review_rounds"] == 2, "used_ai_review_rounds should be 2")

        iterations = rt.read_iterations()
        idxs = [rec["iteration_index"] for rec in iterations]
        _assert(idxs == [1, 2], "iteration_index should be contiguous without duplicates")

        transitions = rt.read_transitions()
        _assert(len(transitions) == 5, "expected 5 transitions for start->review->repair->review->pass")

    print("[loop-resume-recovery] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
