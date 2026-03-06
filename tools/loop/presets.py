#!/usr/bin/env python3
"""Reusable LOOP graph presets and host-local bundle sidecars."""

from __future__ import annotations

import re
from typing import Any

_GRAPH_MODE_VALUES = {"STATIC_USER_MODE", "SYSTEM_EXCEPTION_MODE"}
_RESOURCE_CLASS_VALUES = {"IMMUTABLE", "APPEND_ONLY", "MUTABLE_CONTROLLED"}
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_TOKEN_SANITIZER = re.compile(r"[^A-Za-z0-9._-]+")


def _slug_token(raw: str, *, fallback: str) -> str:
    token = _TOKEN_SANITIZER.sub("-", str(raw).strip()).strip(".-_")
    return token or fallback


def _validate_graph_shape(graph_spec: dict[str, Any]) -> dict[str, Any]:
    graph = dict(graph_spec)
    if graph.get("version") != "1":
        raise ValueError("graph_spec.version must be '1'")
    if graph.get("graph_mode") not in _GRAPH_MODE_VALUES:
        raise ValueError("graph_spec.graph_mode must be STATIC_USER_MODE or SYSTEM_EXCEPTION_MODE")

    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    if not nodes:
        raise ValueError("graph_spec.nodes must be non-empty")

    node_ids: set[str] = set()
    for node in nodes:
        node_id = str(node.get("node_id") or "").strip()
        loop_id = str(node.get("loop_id") or "").strip()
        if not node_id or not loop_id:
            raise ValueError("each node requires node_id and loop_id")
        if node_id in node_ids:
            raise ValueError(f"duplicate node_id: {node_id}")
        node_ids.add(node_id)

    for edge in edges:
        src = str(edge.get("from") or "").strip()
        dst = str(edge.get("to") or "").strip()
        kind = str(edge.get("kind") or "").strip()
        if not src or not dst or not kind:
            raise ValueError("each edge requires from/to/kind")
        if src not in node_ids or dst not in node_ids:
            raise ValueError(f"edge references unknown node: {src}->{dst}")

    if graph["graph_mode"] == "SYSTEM_EXCEPTION_MODE":
        exception_context = dict(graph.get("exception_context") or {})
        if not str(exception_context.get("trigger_reason") or "").strip():
            raise ValueError("SYSTEM_EXCEPTION_MODE requires exception_context.trigger_reason")
        if not str(exception_context.get("root_cause_signature") or "").strip():
            raise ValueError("SYSTEM_EXCEPTION_MODE requires exception_context.root_cause_signature")
        source_run_key = exception_context.get("source_run_key")
        if source_run_key is not None and not _HEX64.fullmatch(str(source_run_key)):
            raise ValueError("exception_context.source_run_key must be 64-char lowercase hex when present")

    return graph


def _node(
    node_id: str,
    loop_id: str,
    *,
    role: str | None = None,
    run_key: str | None = None,
    allow_terminal_predecessors: bool = False,
) -> dict[str, Any]:
    node: dict[str, Any] = {"node_id": node_id, "loop_id": loop_id}
    if role is not None:
        node["role"] = role
    if run_key is not None:
        node["run_key"] = run_key
    if allow_terminal_predecessors:
        node["allow_terminal_predecessors"] = True
    return node


def _edge(src: str, dst: str, kind: str) -> dict[str, str]:
    return {"from": src, "to": dst, "kind": kind}


def _resource(resource_id: str, resource_class: str) -> dict[str, str]:
    if resource_class not in _RESOURCE_CLASS_VALUES:
        raise ValueError(f"unsupported resource class: {resource_class}")
    return {"resource_id": resource_id, "resource_class": resource_class}


def _bundle(
    *,
    preset_id: str,
    graph_spec: dict[str, Any],
    resource_manifest: list[dict[str, str]],
    composition_notes: dict[str, Any],
) -> dict[str, Any]:
    return {
        "preset_id": preset_id,
        "graph_spec": _validate_graph_shape(graph_spec),
        "resource_manifest": list(resource_manifest),
        "composition_notes": dict(composition_notes),
    }


def build_task_bootstrap_graph(*, task_id: str) -> dict[str, Any]:
    task_token = _slug_token(task_id, fallback="task")
    return _validate_graph_shape(
        {
            "version": "1",
            "graph_id": f"graph.loop.task_bootstrap.{task_token}",
            "graph_mode": "STATIC_USER_MODE",
            "nodes": [
                _node("scope_freeze", "loop.task.scope_freeze", role="PROPOSER"),
                _node("mainline_audit", "loop.task.mainline_audit", role="REVIEWER"),
                _node("experiment_audit", "loop.task.experiment_audit", role="REVIEWER"),
                _node("contract_gap_extract", "loop.task.contract_gap_extract", role="REVIEWER"),
                _node("implementation_cycle", "loop.task.implementation_cycle", role="WORKER"),
                _node("governor_decide", "loop.task.governor_decide", role="JUDGE"),
                _node("final_closeout", "loop.task.final_closeout", role="JUDGE"),
            ],
            "edges": [
                _edge("scope_freeze", "mainline_audit", "SERIAL"),
                _edge("scope_freeze", "experiment_audit", "SERIAL"),
                _edge("scope_freeze", "contract_gap_extract", "SERIAL"),
                _edge("mainline_audit", "implementation_cycle", "BARRIER"),
                _edge("experiment_audit", "implementation_cycle", "BARRIER"),
                _edge("contract_gap_extract", "implementation_cycle", "BARRIER"),
                _edge("implementation_cycle", "governor_decide", "SERIAL"),
                _edge("governor_decide", "final_closeout", "SERIAL"),
            ],
        }
    )


def build_task_bootstrap_bundle(*, task_id: str) -> dict[str, Any]:
    return _bundle(
        preset_id="task_bootstrap_v1",
        graph_spec=build_task_bootstrap_graph(task_id=task_id),
        resource_manifest=[
            _resource("contracts.active", "IMMUTABLE"),
            _resource("loop.review_history", "APPEND_ONLY"),
            _resource("task.checkpoint_state", "MUTABLE_CONTROLLED"),
        ],
        composition_notes={
            "task_id": task_id,
            "dynamic_recovery_enabled": True,
            "closeout_mode": "AI_REVIEW_REQUIRED",
        },
    )


def build_formalization_graph(*, paper_id: str) -> dict[str, Any]:
    paper_token = _slug_token(paper_id, fallback="paper")
    return _validate_graph_shape(
        {
            "version": "1",
            "graph_id": f"graph.loop.formalization.{paper_token}",
            "graph_mode": "STATIC_USER_MODE",
            "nodes": [
                _node("source_evidence_pack", "loop.formalization.source_evidence", role="PROPOSER"),
                _node("formalization_cycle", "loop.formalization.cycle", role="WORKER"),
                _node("anti_cheat_gate", "loop.formalization.anti_cheat_gate", role="REVIEWER"),
                _node("strong_validation_gate", "loop.formalization.strong_validation_gate", role="REVIEWER"),
                _node("fidelity_review_gate", "loop.formalization.fidelity_review_gate", role="REVIEWER"),
                _node("formalization_gate_1", "loop.formalization.gate_1", role="JUDGE"),
                _node("mapping_alignment", "loop.formalization.mapping_alignment", role="WORKER"),
                _node("mapping_gate_2", "loop.formalization.mapping_gate_2", role="JUDGE"),
                _node("governor_cycle", "loop.formalization.governor_cycle", role="JUDGE"),
                _node("promotion_decision", "loop.formalization.promotion_decision", role="JUDGE"),
                _node("final_report", "loop.formalization.final_report", role="JUDGE"),
            ],
            "edges": [
                _edge("source_evidence_pack", "formalization_cycle", "SERIAL"),
                _edge("formalization_cycle", "anti_cheat_gate", "SERIAL"),
                _edge("formalization_cycle", "strong_validation_gate", "SERIAL"),
                _edge("formalization_cycle", "fidelity_review_gate", "SERIAL"),
                _edge("anti_cheat_gate", "formalization_gate_1", "BARRIER"),
                _edge("strong_validation_gate", "formalization_gate_1", "BARRIER"),
                _edge("fidelity_review_gate", "formalization_gate_1", "BARRIER"),
                _edge("formalization_gate_1", "mapping_alignment", "SERIAL"),
                _edge("mapping_alignment", "mapping_gate_2", "SERIAL"),
                _edge("mapping_gate_2", "governor_cycle", "SERIAL"),
                _edge("governor_cycle", "promotion_decision", "SERIAL"),
                _edge("promotion_decision", "final_report", "SERIAL"),
            ],
        }
    )


def build_formalization_bundle(*, paper_id: str) -> dict[str, Any]:
    return _bundle(
        preset_id="formalization_v1",
        graph_spec=build_formalization_graph(paper_id=paper_id),
        resource_manifest=[
            _resource("paper.source_material", "IMMUTABLE"),
            _resource("formalization.gate_reports", "APPEND_ONLY"),
            _resource("formalization.ledger", "MUTABLE_CONTROLLED"),
            _resource("formalization.worklist", "MUTABLE_CONTROLLED"),
        ],
        composition_notes={
            "paper_id": paper_id,
            "gate_split": ["formalization_gate_1", "mapping_gate_2"],
            "promotion_requires_governor": True,
        },
    )


def build_dynamic_recovery_graph(*, source_run_key: str, root_cause_signature: str) -> dict[str, Any]:
    if not _HEX64.fullmatch(source_run_key):
        raise ValueError("source_run_key must be 64-char lowercase hex")
    cause_token = _slug_token(root_cause_signature, fallback="exception")
    return _validate_graph_shape(
        {
            "version": "1",
            "graph_id": f"graph.loop.dynamic_recovery.{cause_token}.{source_run_key}",
            "graph_mode": "SYSTEM_EXCEPTION_MODE",
            "exception_context": {
                "trigger_reason": "UNRESOLVED_SYSTEM_EXCEPTION",
                "root_cause_signature": root_cause_signature,
                "source_run_key": source_run_key,
            },
            "nodes": [
                _node("exception_intake", "loop.dynamic.exception_intake", role="RECOVERY"),
                _node("attempt_recovery", "loop.dynamic.attempt_recovery", role="RECOVERY"),
                _node("reconcile_static_return", "loop.dynamic.reconcile_static_return", role="JUDGE"),
            ],
            "edges": [
                _edge("exception_intake", "attempt_recovery", "SERIAL"),
                _edge("attempt_recovery", "reconcile_static_return", "SERIAL"),
            ],
        }
    )


def build_dynamic_recovery_bundle(*, source_run_key: str, root_cause_signature: str) -> dict[str, Any]:
    return _bundle(
        preset_id="dynamic_recovery_v1",
        graph_spec=build_dynamic_recovery_graph(
            source_run_key=source_run_key,
            root_cause_signature=root_cause_signature,
        ),
        resource_manifest=[
            _resource("dynamic.exception_snapshot", "IMMUTABLE"),
            _resource("dynamic.recovery_journal", "APPEND_ONLY"),
            _resource("dynamic.recovery_state", "MUTABLE_CONTROLLED"),
        ],
        composition_notes={
            "return_to_static_flow": True,
            "root_cause_signature": root_cause_signature,
        },
    )


def build_maintainer_change_graph(*, change_id: str) -> dict[str, Any]:
    change_token = _slug_token(change_id, fallback="change")
    return _validate_graph_shape(
        {
            "version": "1",
            "graph_id": f"graph.loop.maintainer_change.{change_token}",
            "graph_mode": "STATIC_USER_MODE",
            "nodes": [
                _node("execplan", "loop.maintainer.execplan", role="PROPOSER"),
                _node("graph_spec", "loop.maintainer.graph_spec", role="PROPOSER"),
                _node("test_node", "loop.maintainer.test_node", role="WORKER"),
                _node("implement_node", "loop.maintainer.implement_node", role="WORKER"),
                _node("verify_node", "loop.maintainer.verify_node", role="WORKER"),
                _node("ai_review_node", "loop.maintainer.ai_review_node", role="REVIEWER"),
                _node(
                    "loop_closeout",
                    "loop.maintainer.loop_closeout",
                    role="JUDGE",
                    allow_terminal_predecessors=True,
                ),
            ],
            "edges": [
                _edge("execplan", "graph_spec", "SERIAL"),
                _edge("graph_spec", "test_node", "SERIAL"),
                _edge("test_node", "implement_node", "SERIAL"),
                _edge("implement_node", "verify_node", "SERIAL"),
                _edge("verify_node", "ai_review_node", "SERIAL"),
                _edge("execplan", "loop_closeout", "SERIAL"),
                _edge("graph_spec", "loop_closeout", "SERIAL"),
                _edge("test_node", "loop_closeout", "SERIAL"),
                _edge("implement_node", "loop_closeout", "SERIAL"),
                _edge("verify_node", "loop_closeout", "SERIAL"),
                _edge("ai_review_node", "loop_closeout", "SERIAL"),
            ],
        }
    )


def build_maintainer_change_bundle(*, change_id: str) -> dict[str, Any]:
    return _bundle(
        preset_id="maintainer_change_v1",
        graph_spec=build_maintainer_change_graph(change_id=change_id),
        resource_manifest=[
            _resource("maintainer.execplan", "IMMUTABLE"),
            _resource("maintainer.review_history", "APPEND_ONLY"),
            _resource("maintainer.closeout_state", "MUTABLE_CONTROLLED"),
        ],
        composition_notes={
            "change_id": change_id,
            "required_sequence": (
                "ExecPlan -> graph_spec -> test node -> implement node -> verify node -> "
                "AI review node -> LOOP closeout"
            ),
            "manual_closeout_policy": "exceptional_only",
        },
    )


__all__ = [
    "build_dynamic_recovery_bundle",
    "build_dynamic_recovery_graph",
    "build_formalization_bundle",
    "build_formalization_graph",
    "build_maintainer_change_bundle",
    "build_maintainer_change_graph",
    "build_task_bootstrap_bundle",
    "build_task_bootstrap_graph",
]
