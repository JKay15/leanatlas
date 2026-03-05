#!/usr/bin/env python3
"""Contract check: deterministic RACE/QUORUM merge semantics in LOOP graph runtime."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.graph_runtime import LoopGraphRuntime


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def _race_graph() -> dict:
    return {
        "version": "1",
        "graph_id": "graph.loop.wave_c.race",
        "graph_mode": "STATIC_USER_MODE",
        "nodes": [
            {"node_id": "n1", "loop_id": "loop.n1"},
            {"node_id": "n2", "loop_id": "loop.n2"},
            {"node_id": "n3", "loop_id": "loop.n3"},
        ],
        "edges": [
            {"from": "n1", "to": "n3", "kind": "RACE"},
            {"from": "n2", "to": "n3", "kind": "RACE"},
        ],
    }


def _quorum_graph(*, min_passes: int) -> dict:
    return {
        "version": "1",
        "graph_id": "graph.loop.wave_c.quorum",
        "graph_mode": "STATIC_USER_MODE",
        "merge_policy": {"quorum": {"min_passes": min_passes}},
        "nodes": [
            {"node_id": "q1", "loop_id": "loop.q1"},
            {"node_id": "q2", "loop_id": "loop.q2"},
            {"node_id": "q3", "loop_id": "loop.q3"},
            {"node_id": "q4", "loop_id": "loop.q4"},
        ],
        "edges": [
            {"from": "q1", "to": "q4", "kind": "QUORUM"},
            {"from": "q2", "to": "q4", "kind": "QUORUM"},
            {"from": "q3", "to": "q4", "kind": "QUORUM"},
        ],
    }


def _executor(state_map: dict[str, str]):
    def _run(node: dict) -> dict:
        node_id = str(node["node_id"])
        state = state_map.get(node_id, "FAILED")
        return {"state": state, "reason_code": f"NODE_{state}"}

    return _run


def _find_target_record(records: list[dict], node_id: str) -> dict:
    for rec in records:
        if rec.get("target_node_id") == node_id:
            return rec
    raise AssertionError(f"missing arbitration record for target_node_id={node_id}")


def _assert_race_semantics() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_graph_race_") as td:
        repo = Path(td)
        rt = LoopGraphRuntime(repo_root=repo, run_key="a" * 64)
        summary = rt.execute(
            graph_spec=_race_graph(),
            node_executor=_executor({"n1": "FAILED", "n2": "PASSED", "n3": "PASSED"}),
        )
        _assert(summary["final_status"] == "PASSED", "RACE should pass when any predecessor passes")

        arbitration = _read_jsonl(
            repo / "artifacts" / "loop_runtime" / "by_key" / ("a" * 64) / "graph" / "arbitration.jsonl"
        )
        n3 = _find_target_record(arbitration, "n3")
        _assert(n3.get("winner_rule") == "FIRST_PASS_LEXICOGRAPHIC", "unexpected RACE winner_rule")
        _assert(n3.get("winner_nodes") == ["n2"], "RACE winner should be the passed predecessor")


def _assert_quorum_semantics() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_graph_quorum_") as td:
        repo = Path(td)
        rt = LoopGraphRuntime(repo_root=repo, run_key="b" * 64)

        summary_ok = rt.execute(
            graph_spec=_quorum_graph(min_passes=2),
            node_executor=_executor({"q1": "PASSED", "q2": "PASSED", "q3": "FAILED", "q4": "PASSED"}),
        )
        _assert(summary_ok["final_status"] == "PASSED", "QUORUM should pass when threshold is met")

        summary_blocked = rt.execute(
            graph_spec=_quorum_graph(min_passes=3),
            node_executor=_executor({"q1": "PASSED", "q2": "FAILED", "q3": "TRIAGED", "q4": "PASSED"}),
        )
        _assert(summary_blocked["final_status"] == "TRIAGED", "QUORUM should triage when threshold is unmet")

        arbitration = _read_jsonl(
            repo / "artifacts" / "loop_runtime" / "by_key" / ("b" * 64) / "graph" / "arbitration.jsonl"
        )
        q4_records = [r for r in arbitration if r.get("target_node_id") == "q4"]
        _assert(len(q4_records) >= 2, "expected two q4 arbitration records from two executions")
        _assert(
            any(r.get("winner_rule") == "QUORUM_AT_LEAST_2" and r.get("winner_state") == "PASSED" for r in q4_records),
            "missing quorum-met arbitration record",
        )
        _assert(
            any(r.get("winner_rule") == "QUORUM_AT_LEAST_3" and r.get("winner_state") == "TRIAGED" for r in q4_records),
            "missing quorum-unmet arbitration record",
        )


def main() -> int:
    _assert_race_semantics()
    _assert_quorum_semantics()
    print("[loop-graph-merge-semantics] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
