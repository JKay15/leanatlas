#!/usr/bin/env python3
"""Contract check: dynamic exception graph entry/exit policy."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.graph_runtime import DynamicEntryViolation, LoopGraphRuntime


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _always_pass(_node: dict) -> dict:
    return {"state": "PASSED", "reason_code": "REVIEW_PASS"}


def _base_graph(mode: str) -> dict:
    return {
        "version": "1",
        "graph_id": "graph.loop.wave_b.m4",
        "graph_mode": mode,
        "nodes": [
            {"node_id": "n1", "loop_id": "loop.node.1"},
            {"node_id": "n2", "loop_id": "loop.node.2"},
        ],
        "edges": [
            {"from": "n1", "to": "n2", "kind": "SERIAL"},
        ],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loop_graph_m4_") as td:
        repo = Path(td)
        run_key = "b" * 64
        rt = LoopGraphRuntime(repo_root=repo, run_key=run_key)

        summary_static = rt.execute(
            graph_spec=_base_graph("STATIC_USER_MODE"),
            node_executor=_always_pass,
        )
        _assert(summary_static["graph_mode"] == "STATIC_USER_MODE", "static graph_mode mismatch")
        _assert(summary_static["final_status"] == "PASSED", "static graph should pass")

        dynamic_graph = _base_graph("SYSTEM_EXCEPTION_MODE")
        dynamic_graph["exception_context"] = {
            "trigger_reason": "UNRESOLVED_EXCEPTION",
            "root_cause_signature": "missing-proof-contract",
            "source_run_key": "c" * 64,
        }

        try:
            rt.execute(
                graph_spec=dynamic_graph,
                node_executor=_always_pass,
                unresolved_exception=False,
            )
        except DynamicEntryViolation:
            pass
        else:
            raise AssertionError("dynamic graph must not start without unresolved_exception")

        summary_dynamic = rt.execute(
            graph_spec=dynamic_graph,
            node_executor=_always_pass,
            unresolved_exception=True,
        )
        _assert(summary_dynamic["graph_mode"] == "SYSTEM_EXCEPTION_MODE", "dynamic graph_mode mismatch")
        _assert(summary_dynamic["final_status"] == "PASSED", "dynamic recovery should pass in this fixture")
        _assert(
            summary_dynamic["return_to_static_flow"] is True,
            "successful dynamic recovery must return to static flow",
        )

    print("[loop-dynamic-exception-entry-policy] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
