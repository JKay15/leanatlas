#!/usr/bin/env python3
"""Contract check: LOOP runtime M1 determinism (run_key + state model + append-only store)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.model import (
    EXEC_ALLOWED,
    ExecutionState,
    require_execution_transition,
)
from tools.loop.run_key import RunKeyInput, compute_run_key
from tools.loop.store import LoopStore


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _test_run_key_determinism() -> None:
    base = RunKeyInput(
        loop_id="loop.wave_b.runtime.v0",
        graph_mode="STATIC_USER_MODE",
        input_projection_hash="a" * 64,
        instruction_chain_hash="b" * 64,
        dependency_pin_set_id="pins.20260305",
    )
    k1 = compute_run_key(base)
    k2 = compute_run_key(base)
    _assert(k1 == k2, "same semantic input must produce same run_key")

    mutated = RunKeyInput(
        loop_id="loop.wave_b.runtime.v0",
        graph_mode="STATIC_USER_MODE",
        input_projection_hash="c" * 64,
        instruction_chain_hash="b" * 64,
        dependency_pin_set_id="pins.20260305",
    )
    k3 = compute_run_key(mutated)
    _assert(k3 != k1, "semantic input change must change run_key")


def _test_state_model() -> None:
    _assert((ExecutionState.RUNNING, ExecutionState.AI_REVIEW) in EXEC_ALLOWED, "RUNNING->AI_REVIEW missing")
    _assert((ExecutionState.AI_REVIEW, ExecutionState.RUNNING) in EXEC_ALLOWED, "AI_REVIEW->RUNNING missing")
    _assert((ExecutionState.RUNNING, ExecutionState.PASSED) not in EXEC_ALLOWED, "RUNNING->PASSED must be forbidden")
    _assert("HUMAN_REVIEW" not in {s.value for s in ExecutionState}, "HUMAN_REVIEW must not be execution state")

    require_execution_transition(ExecutionState.RUNNING, ExecutionState.AI_REVIEW)


def _test_append_only_store() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_runtime_m1_") as td:
        root = Path(td)
        rk = "d" * 64
        st = LoopStore(repo_root=root, run_key=rk)
        st.ensure_layout()

        rel = "attempts/ai_review.jsonl"
        st.append_jsonl(rel, {"i": 1, "msg": "first"}, stream="cache")
        st.append_jsonl(rel, {"i": 2, "msg": "second"}, stream="cache")

        p = st.cache_path(rel)
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        _assert(len(lines) == 2, "append_jsonl must append lines")
        _assert(json.loads(lines[0])["i"] == 1, "first line mismatch")
        _assert(json.loads(lines[1])["i"] == 2, "second line mismatch")

        once_rel = "final/final_decision.json"
        st.write_once_json(once_rel, {"state": "PASSED"}, stream="artifact")
        try:
            st.write_once_json(once_rel, {"state": "FAILED"}, stream="artifact")
        except FileExistsError:
            pass
        else:
            raise AssertionError("write_once_json must reject overwrite")

        data = json.loads(st.artifact_path(once_rel).read_text(encoding="utf-8"))
        _assert(data["state"] == "PASSED", "write_once_json must preserve original content")


def main() -> int:
    _test_run_key_determinism()
    _test_state_model()
    _test_append_only_store()
    print("[loop-runtime-determinism] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
