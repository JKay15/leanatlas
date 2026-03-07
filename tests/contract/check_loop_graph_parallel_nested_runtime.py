#!/usr/bin/env python3
"""Contract: LOOP graph runtime must distinguish real parallel execution from graph semantics and emit nested lineage."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.graph_runtime import LoopGraphRuntime


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _parallel_graph(*, max_parallel_branches: int) -> dict:
    return {
        "version": "1",
        "graph_id": f"graph.loop.parallel_runtime.{max_parallel_branches}",
        "graph_mode": "STATIC_USER_MODE",
        "scheduler": {"max_parallel_branches": max_parallel_branches},
        "nodes": [
            {"node_id": "left", "loop_id": "loop.left"},
            {"node_id": "right", "loop_id": "loop.right"},
            {"node_id": "join", "loop_id": "loop.join"},
        ],
        "edges": [
            {"from": "left", "to": "join", "kind": "PARALLEL"},
            {"from": "right", "to": "join", "kind": "PARALLEL"},
        ],
    }


def _nested_graph(*, child_suffix: str, allow_terminal_predecessors: bool = False) -> dict:
    return {
        "version": "1",
        "graph_id": f"graph.loop.nested_runtime.{child_suffix}",
        "graph_mode": "STATIC_USER_MODE",
        "nodes": [
            {"node_id": "parent_a", "loop_id": "loop.parent_a"},
            {"node_id": "parent_b", "loop_id": "loop.parent_b"},
            {
                "node_id": "child",
                "loop_id": "loop.child",
                **({"allow_terminal_predecessors": True} if allow_terminal_predecessors else {}),
            },
        ],
        "edges": [
            {"from": "parent_a", "to": "child", "kind": "NESTED"},
            {"from": "parent_b", "to": "child", "kind": "NESTED"},
        ],
    }


def _terminal_closeout_chain(*, suffix: str) -> dict:
    return {
        "version": "1",
        "graph_id": f"graph.loop.terminal_closeout_chain.{suffix}",
        "graph_mode": "STATIC_USER_MODE",
        "nodes": [
            {"node_id": "root", "loop_id": "loop.root"},
            {"node_id": "middle", "loop_id": "loop.middle"},
            {"node_id": "closeout", "loop_id": "loop.closeout", "allow_terminal_predecessors": True},
        ],
        "edges": [
            {"from": "root", "to": "middle", "kind": "SERIAL"},
            {"from": "middle", "to": "closeout", "kind": "SERIAL"},
        ],
    }


def _make_parallel_executor(*, tracker: dict[str, int]):
    lock = threading.Lock()

    def _run(node: dict) -> dict:
        node_id = str(node["node_id"])
        if node_id in {"left", "right"}:
            with lock:
                tracker["active"] += 1
                tracker["max_active"] = max(tracker["max_active"], tracker["active"])
            time.sleep(0.2)
            with lock:
                tracker["active"] -= 1
            return {"state": "PASSED", "reason_code": f"{node_id.upper()}_DONE"}
        return {"state": "PASSED", "reason_code": "JOIN_DONE"}

    return _run


def _assert_real_parallelism() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_parallel_runtime_") as td:
        repo = Path(td)

        tracker_parallel = {"active": 0, "max_active": 0}
        summary_parallel = LoopGraphRuntime(repo_root=repo, run_key="1" * 64).execute(
            graph_spec=_parallel_graph(max_parallel_branches=2),
            node_executor=_make_parallel_executor(tracker=tracker_parallel),
        )
        _assert(summary_parallel["final_status"] == "PASSED", "parallel graph should pass")
        _assert(
            tracker_parallel["max_active"] >= 2,
            "max_parallel_branches=2 must allow real concurrent execution of dependency-free nodes",
        )
        scheduler_records = _read_jsonl(repo / "artifacts" / "loop_runtime" / "by_key" / ("1" * 64) / "graph" / "scheduler.jsonl")
        _assert(
            any(
                rec.get("level_index") == 1
                and rec.get("execution_mode") == "PARALLEL"
                and int(rec.get("parallel_width") or 0) == 2
                for rec in scheduler_records
            ),
            "scheduler evidence must record parallel execution for the root batch",
        )

        tracker_serial = {"active": 0, "max_active": 0}
        summary_serial = LoopGraphRuntime(repo_root=repo, run_key="2" * 64).execute(
            graph_spec=_parallel_graph(max_parallel_branches=1),
            node_executor=_make_parallel_executor(tracker=tracker_serial),
        )
        _assert(summary_serial["final_status"] == "PASSED", "serial fallback graph should pass")
        _assert(
            tracker_serial["max_active"] == 1,
            "max_parallel_branches=1 must keep execution serial even for dependency-free nodes",
        )
        scheduler_serial = _read_jsonl(repo / "artifacts" / "loop_runtime" / "by_key" / ("2" * 64) / "graph" / "scheduler.jsonl")
        _assert(
            any(
                rec.get("level_index") == 1
                and rec.get("execution_mode") == "SERIAL"
                and int(rec.get("parallel_width") or 0) == 1
                for rec in scheduler_serial
            ),
            "scheduler evidence must record serial fallback when max_parallel_branches=1",
        )


def _assert_nested_lineage() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_nested_runtime_") as td:
        repo = Path(td)

        summary_ok = LoopGraphRuntime(repo_root=repo, run_key="3" * 64).execute(
            graph_spec=_nested_graph(child_suffix="ok"),
            node_executor=lambda node: {"state": "PASSED", "reason_code": f"{node['node_id']}.ok"},
        )
        _assert(summary_ok["final_status"] == "PASSED", "nested graph should pass when parents pass")
        nested_ok = _read_jsonl(repo / "artifacts" / "loop_runtime" / "by_key" / ("3" * 64) / "graph" / "nested_lineage.jsonl")
        _assert(len(nested_ok) == 1, "nested graph should emit one nested lineage record for the child node")
        _assert(
            nested_ok[0]["child_node_id"] == "child" and nested_ok[0]["parent_node_ids"] == ["parent_a", "parent_b"],
            "nested lineage must bind the child node to all nested parent predecessors",
        )
        _assert(nested_ok[0]["executed"] is True, "nested lineage must record executed=True for passing nested child")

        summary_blocked = LoopGraphRuntime(repo_root=repo, run_key="4" * 64).execute(
            graph_spec=_nested_graph(child_suffix="blocked"),
            node_executor=lambda node: {
                "parent_a": {"state": "PASSED", "reason_code": "PARENT_A_OK"},
                "parent_b": {"state": "TRIAGED", "reason_code": "PARENT_B_TRIAGED"},
                "child": {"state": "PASSED", "reason_code": "CHILD_SHOULD_NOT_RUN"},
            }[str(node["node_id"])],
        )
        _assert(summary_blocked["final_status"] == "TRIAGED", "blocked nested graph should preserve upstream triage")
        nested_blocked = _read_jsonl(repo / "artifacts" / "loop_runtime" / "by_key" / ("4" * 64) / "graph" / "nested_lineage.jsonl")
        _assert(len(nested_blocked) == 1, "blocked nested graph should still emit lineage evidence")
        _assert(nested_blocked[0]["executed"] is False, "blocked nested lineage must record executed=False")
        _assert(
            nested_blocked[0]["blocked_state"] == "TRIAGED",
            "blocked nested lineage must preserve the terminal class that blocked child execution",
        )

        summary_allow_terminal = LoopGraphRuntime(repo_root=repo, run_key="5" * 64).execute(
            graph_spec=_nested_graph(child_suffix="allow_terminal", allow_terminal_predecessors=True),
            node_executor=lambda node: {
                "parent_a": {"state": "PASSED", "reason_code": "PARENT_A_OK"},
                "parent_b": {"state": "TRIAGED", "reason_code": "PARENT_B_TRIAGED"},
                "child": {"state": "PASSED", "reason_code": "CHILD_EXECUTED"},
            }[str(node["node_id"])],
        )
        _assert(
            summary_allow_terminal["final_status"] == "TRIAGED",
            "allow_terminal nested graph should preserve propagated upstream terminal state in the final summary",
        )
        nested_allow_terminal = _read_jsonl(
            repo / "artifacts" / "loop_runtime" / "by_key" / ("5" * 64) / "graph" / "nested_lineage.jsonl"
        )
        _assert(len(nested_allow_terminal) == 1, "allow-terminal nested graph should still emit one lineage record")
        _assert(
            nested_allow_terminal[0]["executed"] is True,
            "allow-terminal nested lineage must record executed=True when the child actually ran",
        )
        _assert(
            nested_allow_terminal[0]["child_state"] == "PASSED",
            "nested lineage child_state must preserve the child's actual terminal result, not the propagated effective state",
        )


def _assert_blocked_batch_scheduler_zero_width() -> None:
    graph = {
        "version": "1",
        "graph_id": "graph.loop.blocked_parallel_batch",
        "graph_mode": "STATIC_USER_MODE",
        "scheduler": {"max_parallel_branches": 4},
        "nodes": [
            {"node_id": "root", "loop_id": "loop.root"},
            {"node_id": "left", "loop_id": "loop.left"},
            {"node_id": "right", "loop_id": "loop.right"},
        ],
        "edges": [
            {"from": "root", "to": "left", "kind": "PARALLEL"},
            {"from": "root", "to": "right", "kind": "PARALLEL"},
        ],
    }
    with tempfile.TemporaryDirectory(prefix="loop_blocked_batch_") as td:
        repo = Path(td)
        summary = LoopGraphRuntime(repo_root=repo, run_key="6" * 64).execute(
            graph_spec=graph,
            node_executor=lambda node: {
                "root": {"state": "TRIAGED", "reason_code": "ROOT_TRIAGED"},
                "left": {"state": "PASSED", "reason_code": "LEFT_SHOULD_NOT_RUN"},
                "right": {"state": "PASSED", "reason_code": "RIGHT_SHOULD_NOT_RUN"},
            }[str(node["node_id"])],
        )
        _assert(summary["final_status"] == "TRIAGED", "blocked-parallel graph should preserve upstream triage")
        scheduler_records = _read_jsonl(repo / "artifacts" / "loop_runtime" / "by_key" / ("6" * 64) / "graph" / "scheduler.jsonl")
        level_two = [rec for rec in scheduler_records if int(rec.get("level_index") or 0) == 2]
        _assert(level_two, "blocked parallel batch must still emit scheduler evidence for the blocked level")
        _assert(
            int(level_two[0].get("parallel_width", -1)) == 0,
            "fully blocked batch must record parallel_width=0 because no node executor actually ran",
        )


def _assert_upstream_blocked_does_not_count_as_terminal_predecessor() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_terminal_predecessor_blocked_") as td:
        repo = Path(td)
        summary = LoopGraphRuntime(repo_root=repo, run_key="7" * 64).execute(
            graph_spec=_terminal_closeout_chain(suffix="blocked"),
            node_executor=lambda node: {
                "root": {"state": "TRIAGED", "reason_code": "ROOT_TRIAGED"},
                "middle": {"state": "PASSED", "reason_code": "MIDDLE_SHOULD_NOT_RUN"},
                "closeout": {"state": "PASSED", "reason_code": "CLOSEOUT_SHOULD_NOT_RUN"},
            }[str(node["node_id"])],
        )
        decisions = {str(item["node_id"]): dict(item) for item in summary["node_decisions"]}
        _assert(
            decisions["middle"]["reason_code"] == "UPSTREAM_BLOCKED",
            "intermediate node must be synthesized as UPSTREAM_BLOCKED when its predecessor triages",
        )
        _assert(
            decisions["middle"]["executed"] is False,
            "synthesized blocked intermediate node must record executed=False in GraphSummary",
        )
        _assert(
            decisions["closeout"]["reason_code"] == "UPSTREAM_BLOCKED",
            "allow_terminal_predecessors must not execute when predecessor terminality is only synthesized by UPSTREAM_BLOCKED",
        )
        _assert(
            decisions["closeout"]["executed"] is False,
            "terminal-predecessor sink must record executed=False when blocked by synthesized upstream terminality",
        )
        _assert(
            summary["final_status"] == "TRIAGED",
            "blocked closeout chain must preserve the upstream terminal class",
        )


def _assert_executed_terminal_reason_code_does_not_block_terminal_predecessor() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_terminal_predecessor_executed_reason_code_") as td:
        repo = Path(td)
        summary = LoopGraphRuntime(repo_root=repo, run_key="8" * 64).execute(
            graph_spec=_terminal_closeout_chain(suffix="executed_reason_code"),
            node_executor=lambda node: {
                "root": {"state": "PASSED", "reason_code": "ROOT_OK"},
                "middle": {"state": "TRIAGED", "reason_code": "UPSTREAM_BLOCKED"},
                "closeout": {"state": "PASSED", "reason_code": "CLOSEOUT_EXECUTED"},
            }[str(node["node_id"])],
        )
        decisions = {str(item["node_id"]): dict(item) for item in summary["node_decisions"]}
        _assert(
            decisions["middle"]["executed"] is True,
            "terminal predecessor that actually ran must keep executed=True even if its reason_code text is UPSTREAM_BLOCKED",
        )
        _assert(
            decisions["closeout"]["reason_code"] == "CLOSEOUT_EXECUTED",
            "allow_terminal_predecessors must key off execution evidence, not free-form reason_code text",
        )
        _assert(
            decisions["closeout"]["executed"] is True,
            "closeout sink must record executed=True when it legitimately runs after an executed terminal predecessor",
        )
        _assert(
            summary["final_status"] == "TRIAGED",
            "executed terminal predecessor path must still preserve the upstream terminal class in the final summary",
        )


def _assert_mixed_executed_and_synthesized_terminal_predecessors_preserve_worst_class() -> None:
    graph = {
        "version": "1",
        "graph_id": "graph.loop.mixed_terminal_predecessor_classes",
        "graph_mode": "STATIC_USER_MODE",
        "nodes": [
            {"node_id": "root_ok", "loop_id": "loop.root_ok"},
            {"node_id": "root_triaged", "loop_id": "loop.root_triaged"},
            {"node_id": "failed_branch", "loop_id": "loop.failed_branch"},
            {"node_id": "blocked_branch", "loop_id": "loop.blocked_branch"},
            {"node_id": "closeout", "loop_id": "loop.closeout", "allow_terminal_predecessors": True},
        ],
        "edges": [
            {"from": "root_ok", "to": "failed_branch", "kind": "SERIAL"},
            {"from": "root_triaged", "to": "blocked_branch", "kind": "SERIAL"},
            {"from": "failed_branch", "to": "closeout", "kind": "BARRIER"},
            {"from": "blocked_branch", "to": "closeout", "kind": "BARRIER"},
        ],
    }
    with tempfile.TemporaryDirectory(prefix="loop_terminal_predecessor_mixed_classes_") as td:
        repo = Path(td)
        summary = LoopGraphRuntime(repo_root=repo, run_key="9" * 64).execute(
            graph_spec=graph,
            node_executor=lambda node: {
                "root_ok": {"state": "PASSED", "reason_code": "ROOT_OK"},
                "root_triaged": {"state": "TRIAGED", "reason_code": "ROOT_TRIAGED"},
                "failed_branch": {"state": "FAILED", "reason_code": "FAILED_BRANCH_EXECUTED"},
                "blocked_branch": {"state": "PASSED", "reason_code": "BLOCKED_BRANCH_SHOULD_NOT_RUN"},
                "closeout": {"state": "PASSED", "reason_code": "CLOSEOUT_SHOULD_NOT_RUN"},
            }[str(node["node_id"])],
        )
        decisions = {str(item["node_id"]): dict(item) for item in summary["node_decisions"]}
        _assert(
            decisions["blocked_branch"]["reason_code"] == "UPSTREAM_BLOCKED"
            and decisions["blocked_branch"]["executed"] is False,
            "blocked branch must be synthesized from upstream triage rather than execute",
        )
        _assert(
            decisions["failed_branch"]["state"] == "FAILED" and decisions["failed_branch"]["executed"] is True,
            "failed branch must preserve its executed terminal failure",
        )
        _assert(
            decisions["closeout"]["state"] == "FAILED",
            "closeout sink must preserve the worst admitted terminal class across mixed executed and synthesized predecessors",
        )
        _assert(
            decisions["closeout"]["executed"] is False,
            "closeout sink must stay blocked when any predecessor terminality is synthesized upstream",
        )
        _assert(
            summary["final_status"] == "FAILED",
            "graph summary must preserve FAILED over TRIAGED when blocked closeout predecessors mix executed and synthesized states",
        )


def _assert_all_pass_required_blocked_merge_preserves_worst_terminal_class() -> None:
    graph = {
        "version": "1",
        "graph_id": "graph.loop.all_pass_required_blocked_merge_worst_class",
        "graph_mode": "STATIC_USER_MODE",
        "nodes": [
            {"node_id": "a_triaged", "loop_id": "loop.a_triaged"},
            {"node_id": "z_failed", "loop_id": "loop.z_failed"},
            {"node_id": "join", "loop_id": "loop.join"},
        ],
        "edges": [
            {"from": "a_triaged", "to": "join", "kind": "BARRIER"},
            {"from": "z_failed", "to": "join", "kind": "BARRIER"},
        ],
    }
    with tempfile.TemporaryDirectory(prefix="loop_all_pass_required_blocked_merge_") as td:
        repo = Path(td)
        summary = LoopGraphRuntime(repo_root=repo, run_key="a" * 64).execute(
            graph_spec=graph,
            node_executor=lambda node: {
                "a_triaged": {"state": "TRIAGED", "reason_code": "UPSTREAM_TRIAGED"},
                "z_failed": {"state": "FAILED", "reason_code": "UPSTREAM_FAILED"},
                "join": {"state": "PASSED", "reason_code": "JOIN_SHOULD_NOT_RUN"},
            }[str(node["node_id"])],
        )
        decisions = {str(item["node_id"]): dict(item) for item in summary["node_decisions"]}
        _assert(
            decisions["join"]["executed"] is False and decisions["join"]["reason_code"] == "UPSTREAM_BLOCKED",
            "all-pass-required fan-in must synthesize a blocked join when any predecessor is non-pass",
        )
        _assert(
            decisions["join"]["state"] == "FAILED",
            "blocked all-pass fan-in must preserve the worst upstream terminal class instead of the first lexical non-pass predecessor",
        )
        _assert(
            summary["final_status"] == "FAILED",
            "graph summary must preserve FAILED over TRIAGED when a blocked all-pass fan-in mixes terminal classes",
        )


def main() -> int:
    _assert_real_parallelism()
    _assert_nested_lineage()
    _assert_blocked_batch_scheduler_zero_width()
    _assert_upstream_blocked_does_not_count_as_terminal_predecessor()
    _assert_executed_terminal_reason_code_does_not_block_terminal_predecessor()
    _assert_mixed_executed_and_synthesized_terminal_predecessors_preserve_worst_class()
    _assert_all_pass_required_blocked_merge_preserves_worst_terminal_class()
    print("[loop-graph-parallel-nested-runtime] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
