#!/usr/bin/env python3
"""Deterministic LOOP graph runtime (Wave-B M4 minimal)."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable

from .errors import LoopException
from .store import LoopStore

EDGE_KINDS = {"SERIAL", "PARALLEL", "NESTED", "RACE", "QUORUM", "BARRIER"}
TERMINAL_STATES = {"PASSED", "FAILED", "TRIAGED"}
STATUS_PRIORITY = {"PASSED": 0, "TRIAGED": 1, "FAILED": 2}
_RESERVED_SUMMARY_KEYS = {
    "version",
    "graph_id",
    "graph_mode",
    "run_key",
    "final_status",
    "return_to_static_flow",
    "node_decisions",
    "exception_context",
}


class DynamicEntryViolation(LoopException):
    def __init__(self, message: str) -> None:
        super().__init__(
            error_code="DYNAMIC_ENTRY_FORBIDDEN",
            error_class="NON_RETRYABLE_CONTRACT",
            retryable=False,
            message=message,
        )


class LoopGraphRuntime:
    """Graph orchestrator that records deterministic node/arbitration evidence."""

    def __init__(self, *, repo_root: Path, run_key: str) -> None:
        self.store = LoopStore(repo_root=repo_root, run_key=run_key)
        self.store.ensure_layout()

    @staticmethod
    def _validate_graph(graph_spec: dict[str, Any]) -> None:
        nodes = graph_spec.get("nodes") or []
        edges = graph_spec.get("edges") or []
        node_ids = {n.get("node_id") for n in nodes}
        outgoing: dict[str, set[str]] = defaultdict(set)
        incoming_kinds: dict[str, set[str]] = defaultdict(set)
        if not node_ids:
            raise ValueError("graph_spec.nodes must be non-empty")
        for e in edges:
            kind = e.get("kind")
            if kind not in EDGE_KINDS:
                raise ValueError(f"unsupported edge kind: {kind}")
            src = str(e.get("from"))
            dst = str(e.get("to"))
            if src not in node_ids or dst not in node_ids:
                raise ValueError("edge references unknown node_id")
            outgoing[src].add(dst)
            incoming_kinds[dst].add(str(kind))
        for node in nodes:
            node_id = str(node.get("node_id"))
            if not node.get("allow_terminal_predecessors"):
                continue
            if outgoing.get(node_id):
                raise ValueError("allow_terminal_predecessors is only valid on sink nodes")
            if not incoming_kinds.get(node_id):
                raise ValueError("allow_terminal_predecessors requires at least one incoming edge")
            unsupported_incoming = sorted(incoming_kinds.get(node_id, set()) - {"SERIAL", "PARALLEL", "NESTED", "BARRIER"})
            if unsupported_incoming:
                raise ValueError(
                    "allow_terminal_predecessors only supports SERIAL/PARALLEL/NESTED/BARRIER incoming edges; "
                    f"got {', '.join(unsupported_incoming)}"
                )

    @staticmethod
    def _topological_batches(graph_spec: dict[str, Any]) -> list[list[str]]:
        nodes = [str(n["node_id"]) for n in graph_spec["nodes"]]
        edges = graph_spec["edges"]

        preds: dict[str, set[str]] = {n: set() for n in nodes}
        succ: dict[str, set[str]] = defaultdict(set)
        indeg: dict[str, int] = {n: 0 for n in nodes}
        for e in edges:
            src = str(e["from"])
            dst = str(e["to"])
            if src not in preds[dst]:
                preds[dst].add(src)
                succ[src].add(dst)
                indeg[dst] += 1

        q = deque(sorted([n for n, d in indeg.items() if d == 0]))
        done = 0
        batches: list[list[str]] = []
        while q:
            level: list[str] = []
            for _ in range(len(q)):
                cur = q.popleft()
                level.append(cur)
            level.sort()
            batches.append(level)
            for cur in level:
                done += 1
                for nxt in sorted(succ[cur]):
                    indeg[nxt] -= 1
                    if indeg[nxt] == 0:
                        q.append(nxt)

        if done != len(nodes):
            raise ValueError("graph has cycle or invalid dependencies")
        return batches

    @staticmethod
    def _graph_index(graph_spec: dict[str, Any]) -> tuple[dict[str, list[dict[str, str]]], dict[str, set[str]]]:
        incoming: dict[str, list[dict[str, str]]] = defaultdict(list)
        outgoing: dict[str, set[str]] = defaultdict(set)
        for e in graph_spec.get("edges") or []:
            src = str(e["from"])
            dst = str(e["to"])
            kind = str(e["kind"])
            incoming[dst].append({"from": src, "to": dst, "kind": kind})
            outgoing[src].add(dst)
        return incoming, outgoing

    @staticmethod
    def _status_worst(states: list[str]) -> str:
        if not states:
            return "PASSED"
        return max(states, key=lambda s: STATUS_PRIORITY.get(s, 2))

    @staticmethod
    def _quorum_min_passes(merge_policy: dict[str, Any], predecessor_count: int) -> int:
        quorum_obj = merge_policy.get("quorum")
        raw = None
        if isinstance(quorum_obj, dict):
            raw = quorum_obj.get("min_passes")
        if raw is None:
            raw = merge_policy.get("quorum_min_passes")
        if raw is None:
            raw = predecessor_count
        try:
            val = int(raw)
        except Exception:
            val = predecessor_count
        return max(1, min(val, predecessor_count))

    @classmethod
    def _evaluate_gate(
        cls,
        *,
        edge_kind: str,
        predecessors: list[str],
        node_states: dict[str, str],
        merge_policy: dict[str, Any],
        allow_terminal_predecessors: bool = False,
    ) -> dict[str, Any]:
        pred_ids = sorted(dict.fromkeys(predecessors))
        pred_states = {p: node_states.get(p, "FAILED") for p in pred_ids}
        passed = [p for p in pred_ids if pred_states[p] == "PASSED"]
        non_pass = [p for p in pred_ids if pred_states[p] != "PASSED"]

        if edge_kind == "RACE":
            if passed:
                winner = sorted(passed)[0]
                return {
                    "execute": True,
                    "winner_rule": "FIRST_PASS_LEXICOGRAPHIC",
                    "winner_nodes": [winner],
                    "winner_state": "PASSED",
                    "reason_code": "RACE_PASS_SELECTED",
                    "predecessor_states": pred_states,
                }
            blocked_state = pred_states[non_pass[0]] if non_pass else "FAILED"
            return {
                "execute": False,
                "winner_rule": "FIRST_PASS_LEXICOGRAPHIC",
                "winner_nodes": [],
                "winner_state": blocked_state,
                "reason_code": "RACE_NO_PASS",
                "blocked_state": blocked_state,
                "predecessor_states": pred_states,
            }

        if edge_kind == "QUORUM":
            min_passes = cls._quorum_min_passes(merge_policy, len(pred_ids))
            if len(passed) >= min_passes:
                return {
                    "execute": True,
                    "winner_rule": f"QUORUM_AT_LEAST_{min_passes}",
                    "winner_nodes": sorted(passed),
                    "winner_state": "PASSED",
                    "reason_code": "QUORUM_MET",
                    "predecessor_states": pred_states,
                }
            return {
                "execute": False,
                "winner_rule": f"QUORUM_AT_LEAST_{min_passes}",
                "winner_nodes": sorted(passed),
                "winner_state": "TRIAGED",
                "reason_code": "QUORUM_NOT_MET",
                "blocked_state": "TRIAGED",
                "predecessor_states": pred_states,
            }

        # SERIAL / PARALLEL / NESTED / BARRIER use all-pass gate by default.
        if not non_pass:
            return {
                "execute": True,
                "winner_rule": "ALL_PASS_REQUIRED",
                "winner_nodes": pred_ids,
                "winner_state": "PASSED",
                "reason_code": "UPSTREAM_ALL_PASS",
                "predecessor_states": pred_states,
            }
        if allow_terminal_predecessors and pred_ids and all(pred_states[p] in TERMINAL_STATES for p in pred_ids):
            return {
                "execute": True,
                "winner_rule": "ALL_TERMINAL_REQUIRED",
                "winner_nodes": pred_ids,
                "winner_state": cls._status_worst(list(pred_states.values())),
                "reason_code": "UPSTREAM_ALL_TERMINAL",
                "predecessor_states": pred_states,
            }
        blocked_state = pred_states[non_pass[0]]
        return {
            "execute": False,
            "winner_rule": "ALL_PASS_REQUIRED",
            "winner_nodes": sorted(passed),
            "winner_state": blocked_state,
            "reason_code": "UPSTREAM_BLOCKED",
            "blocked_state": blocked_state,
            "predecessor_states": pred_states,
        }

    @staticmethod
    def _edge_kind_for_target(incoming_edges: list[dict[str, str]]) -> str | None:
        if not incoming_edges:
            return None
        kinds = {e["kind"] for e in incoming_edges}
        if len(kinds) != 1:
            raise ValueError("incoming edges for one target must share the same kind")
        return next(iter(kinds))

    def _evaluate_execution(
        self,
        *,
        graph_spec: dict[str, Any],
        node_executor: Callable[[dict[str, Any]], dict[str, Any]],
        unresolved_exception: bool | None = None,
        summary_overlay: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        self._validate_graph(graph_spec)
        graph_mode = str(graph_spec.get("graph_mode"))
        if graph_mode not in {"STATIC_USER_MODE", "SYSTEM_EXCEPTION_MODE"}:
            raise ValueError("graph_mode must be STATIC_USER_MODE or SYSTEM_EXCEPTION_MODE")
        if graph_mode == "SYSTEM_EXCEPTION_MODE":
            if not unresolved_exception:
                raise DynamicEntryViolation("SYSTEM_EXCEPTION_MODE requires unresolved_exception=True")
            if not graph_spec.get("exception_context"):
                raise DynamicEntryViolation("SYSTEM_EXCEPTION_MODE requires exception_context")

        nodes_by_id = {str(n["node_id"]): dict(n) for n in graph_spec["nodes"]}
        batches = self._topological_batches(graph_spec)
        incoming, outgoing = self._graph_index(graph_spec)
        merge_policy = dict(graph_spec.get("merge_policy") or {})
        node_decisions: list[dict[str, Any]] = []
        arbitration_records: list[dict[str, Any]] = []
        node_states: dict[str, str] = {}
        effective_states: dict[str, str] = {}

        for level_idx, batch in enumerate(batches, start=1):
            batch_states: list[str] = []
            batch_effective_states: list[str] = []
            for node_id in batch:
                deps = incoming.get(node_id, [])
                edge_kind = self._edge_kind_for_target(deps)
                allow_terminal_predecessors = bool(nodes_by_id[node_id].get("allow_terminal_predecessors"))
                propagated_terminal_state: str | None = None
                if deps:
                    gate_node_states = node_states
                    if allow_terminal_predecessors and (edge_kind or "SERIAL") not in {"RACE", "QUORUM"}:
                        gate_node_states = effective_states
                    gate = self._evaluate_gate(
                        edge_kind=edge_kind or "SERIAL",
                        predecessors=[d["from"] for d in deps],
                        node_states=gate_node_states,
                        merge_policy=merge_policy,
                        allow_terminal_predecessors=allow_terminal_predecessors,
                    )
                    arbitration_records.append(
                        {
                            "graph_id": graph_spec["graph_id"],
                            "level_index": level_idx,
                            "target_node_id": node_id,
                            "edge_kind": edge_kind,
                            "winner_rule": gate["winner_rule"],
                            "winner_nodes": gate["winner_nodes"],
                            "winner_state": gate["winner_state"],
                            "predecessor_states": gate["predecessor_states"],
                        }
                    )
                    if gate.get("reason_code") == "UPSTREAM_ALL_TERMINAL":
                        propagated_terminal_state = self._status_worst(
                            [gate_node_states.get(d["from"], node_states.get(d["from"], "FAILED")) for d in deps]
                        )
                    if not gate["execute"]:
                        blocked_state = str(gate.get("blocked_state", "FAILED"))
                        decision = {
                            "level_index": level_idx,
                            "node_id": node_id,
                            "loop_id": nodes_by_id[node_id].get("loop_id"),
                            "state": blocked_state,
                            "reason_code": gate.get("reason_code", "UPSTREAM_BLOCKED"),
                            "run_key": None,
                        }
                        node_decisions.append(decision)
                        node_states[node_id] = blocked_state
                        effective_states[node_id] = blocked_state
                        batch_states.append(blocked_state)
                        batch_effective_states.append(blocked_state)
                        continue

                res = node_executor(nodes_by_id[node_id])
                state = str(res.get("state", "FAILED"))
                if state not in TERMINAL_STATES:
                    state = "FAILED"
                effective_state = state
                if propagated_terminal_state is not None:
                    # Terminal-predecessor sinks are bookkeeping nodes: they may execute after
                    # upstream failure/triage, but must not erase the admitted terminal class
                    # from the graph summary.
                    effective_state = self._status_worst([state, propagated_terminal_state])
                decision = {
                    "level_index": level_idx,
                    "node_id": node_id,
                    "loop_id": nodes_by_id[node_id].get("loop_id"),
                    "state": state,
                    "reason_code": res.get("reason_code", "NODE_EXEC_RESULT"),
                    "run_key": res.get("run_key"),
                }
                node_decisions.append(decision)
                node_states[node_id] = state
                effective_states[node_id] = effective_state
                batch_states.append(state)
                batch_effective_states.append(effective_state)
            arbitration_records.append(
                {
                    "graph_id": graph_spec["graph_id"],
                    "level_index": level_idx,
                    "batch_node_ids": batch,
                    "winner_rule": "ALL_PASS_REQUIRED",
                    "winner_state": self._status_worst(batch_effective_states or batch_states),
                }
            )

        sink_nodes = sorted([n for n in nodes_by_id if not outgoing.get(n)])
        sink_states = [effective_states.get(n, node_states.get(n, "FAILED")) for n in sink_nodes]
        final_status = self._status_worst(sink_states)

        summary = {
            "version": "1",
            "graph_id": graph_spec["graph_id"],
            "graph_mode": graph_mode,
            "run_key": self.store.run_key,
            "final_status": final_status,
            "return_to_static_flow": graph_mode == "SYSTEM_EXCEPTION_MODE" and final_status == "PASSED",
            "node_decisions": node_decisions,
            "exception_context": graph_spec.get("exception_context"),
        }
        if summary_overlay:
            overlap = sorted(_RESERVED_SUMMARY_KEYS & set(summary_overlay))
            if overlap:
                raise ValueError(
                    "summary_overlay cannot override core summary fields: "
                    + ", ".join(overlap)
                )
            summary.update(dict(summary_overlay))
        return summary, arbitration_records

    def _persist_execution(
        self,
        *,
        summary: dict[str, Any],
        arbitration_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        for rec in arbitration_records:
            self.store.append_jsonl("graph/arbitration.jsonl", rec, stream="artifact")
        summary_path = self.store.append_jsonl("graph/GraphSummary.jsonl", summary, stream="artifact")
        persisted = dict(summary)
        persisted["summary_ref"] = str(summary_path)
        return persisted

    def execute(
        self,
        *,
        graph_spec: dict[str, Any],
        node_executor: Callable[[dict[str, Any]], dict[str, Any]],
        unresolved_exception: bool | None = None,
        summary_overlay: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        summary, arbitration_records = self._evaluate_execution(
            graph_spec=graph_spec,
            node_executor=node_executor,
            unresolved_exception=unresolved_exception,
            summary_overlay=summary_overlay,
        )
        return self._persist_execution(summary=summary, arbitration_records=arbitration_records)
