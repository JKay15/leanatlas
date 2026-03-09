#!/usr/bin/env python3
"""Contract check: LOOP composition presets stay schema-valid and executable."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import jsonschema
except Exception:
    print("[loop-composition-presets] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.graph_runtime import LoopGraphRuntime
from tools.loop.maintainer import execute_recorded_graph
from tools.loop.presets import (
    build_dynamic_recovery_bundle,
    build_dynamic_recovery_graph,
    build_formalization_bundle,
    build_formalization_graph,
    build_maintainer_change_bundle,
    build_maintainer_change_graph,
    build_task_bootstrap_bundle,
    build_task_bootstrap_graph,
)


SCHEMA = json.loads((ROOT / "docs" / "schemas" / "LoopGraphSpec.schema.json").read_text(encoding="utf-8"))
GRAPH_VALIDATOR = jsonschema.Draft202012Validator(
    SCHEMA,
    format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _all_pass(_node: dict) -> dict:
    return {"state": "PASSED", "reason_code": "REVIEW_PASS"}


def _node_ids(graph: dict) -> list[str]:
    return [str(node["node_id"]) for node in graph["nodes"]]


def _edges(graph: dict) -> set[tuple[str, str, str]]:
    return {(str(edge["from"]), str(edge["to"]), str(edge["kind"])) for edge in graph["edges"]}


def _resource_class_map(bundle: dict) -> dict[str, str]:
    return {str(item["resource_id"]): str(item["resource_class"]) for item in bundle.get("resource_manifest") or []}


def _validate_graph(graph: dict) -> None:
    errs = sorted(GRAPH_VALIDATOR.iter_errors(graph), key=lambda e: list(e.absolute_path))
    if errs:
        joined = "; ".join(f"/{'/'.join(str(x) for x in e.absolute_path)}: {e.message}" for e in errs)
        raise AssertionError(f"graph_spec must validate against LoopGraphSpec.schema.json: {joined}")


def _assert_bundle_shape(bundle: dict, *, expected_preset_id: str) -> dict:
    _assert(bundle["preset_id"] == expected_preset_id, f"unexpected preset id: {bundle['preset_id']}")
    _assert("graph_spec" in bundle, "bundle must contain graph_spec")
    _assert("resource_manifest" in bundle, "bundle must contain resource_manifest")
    _assert("composition_notes" in bundle, "bundle must contain composition_notes")
    graph = dict(bundle["graph_spec"])
    _validate_graph(graph)
    for forbidden in ("preset_id", "resource_manifest", "shared_resources", "composition_notes"):
        _assert(forbidden not in graph, f"graph_spec must not contain sidecar field `{forbidden}`")
    return graph


def _assert_task_bootstrap_shape() -> None:
    bundle = build_task_bootstrap_bundle(task_id="formalization_bootstrap")
    graph = _assert_bundle_shape(bundle, expected_preset_id="task_bootstrap_v1")
    _assert(graph["graph_mode"] == "STATIC_USER_MODE", "task graph must be static")
    _assert(
        _node_ids(graph)
        == [
            "scope_freeze",
            "mainline_audit",
            "experiment_audit",
            "contract_gap_extract",
            "implementation_cycle",
            "governor_decide",
            "final_closeout",
        ],
        "unexpected task preset node order",
    )
    _assert(
        _edges(graph)
        == {
            ("scope_freeze", "mainline_audit", "SERIAL"),
            ("scope_freeze", "experiment_audit", "SERIAL"),
            ("scope_freeze", "contract_gap_extract", "SERIAL"),
            ("mainline_audit", "implementation_cycle", "BARRIER"),
            ("experiment_audit", "implementation_cycle", "BARRIER"),
            ("contract_gap_extract", "implementation_cycle", "BARRIER"),
            ("implementation_cycle", "governor_decide", "SERIAL"),
            ("governor_decide", "final_closeout", "SERIAL"),
        },
        "unexpected task preset topology",
    )
    resources = _resource_class_map(bundle)
    _assert(resources["contracts.active"] == "IMMUTABLE", "contracts should be immutable")
    _assert(resources["loop.review_history"] == "APPEND_ONLY", "review history should be append-only")
    _assert(resources["task.checkpoint_state"] == "MUTABLE_CONTROLLED", "task checkpoint must be controlled")
    _assert(bundle["composition_notes"]["dynamic_recovery_enabled"] is True, "task bundle should expose recovery note")


def _assert_formalization_shape() -> None:
    bundle = build_formalization_bundle(paper_id="A2112_13254v3")
    graph = _assert_bundle_shape(bundle, expected_preset_id="formalization_v1")
    _assert(graph["graph_mode"] == "STATIC_USER_MODE", "formalization graph must be static")
    _assert(
        _node_ids(graph)
        == [
            "source_evidence_pack",
            "formalization_cycle",
            "anti_cheat_gate",
            "strong_validation_gate",
            "fidelity_review_gate",
            "formalization_gate_1",
            "mapping_alignment",
            "mapping_gate_2",
            "governor_cycle",
            "promotion_decision",
            "final_report",
        ],
        "unexpected formalization preset node order",
    )
    edges = _edges(graph)
    for expected in {
        ("source_evidence_pack", "formalization_cycle", "SERIAL"),
        ("formalization_cycle", "anti_cheat_gate", "SERIAL"),
        ("formalization_cycle", "strong_validation_gate", "SERIAL"),
        ("formalization_cycle", "fidelity_review_gate", "SERIAL"),
        ("anti_cheat_gate", "formalization_gate_1", "BARRIER"),
        ("strong_validation_gate", "formalization_gate_1", "BARRIER"),
        ("fidelity_review_gate", "formalization_gate_1", "BARRIER"),
        ("formalization_gate_1", "mapping_alignment", "SERIAL"),
        ("mapping_alignment", "mapping_gate_2", "SERIAL"),
        ("mapping_gate_2", "governor_cycle", "SERIAL"),
        ("governor_cycle", "promotion_decision", "SERIAL"),
        ("promotion_decision", "final_report", "SERIAL"),
    }:
        _assert(expected in edges, f"missing formalization edge: {expected}")
    resources = _resource_class_map(bundle)
    _assert(resources["paper.source_material"] == "IMMUTABLE", "paper sources should be immutable")
    _assert(resources["formalization.gate_reports"] == "APPEND_ONLY", "gate reports should be append-only")
    _assert(resources["formalization.ledger"] == "MUTABLE_CONTROLLED", "ledger must be controlled")
    _assert(resources["formalization.worklist"] == "MUTABLE_CONTROLLED", "worklist must be controlled")


def _assert_dynamic_recovery_shape() -> None:
    bundle = build_dynamic_recovery_bundle(
        source_run_key="a" * 64,
        root_cause_signature="formalization-mapping-desync",
    )
    graph = _assert_bundle_shape(bundle, expected_preset_id="dynamic_recovery_v1")
    _assert(graph["graph_mode"] == "SYSTEM_EXCEPTION_MODE", "dynamic preset must be system exception mode")
    _assert(
        _node_ids(graph) == ["exception_intake", "attempt_recovery", "reconcile_static_return"],
        "unexpected dynamic preset node order",
    )
    _assert(
        _edges(graph)
        == {
            ("exception_intake", "attempt_recovery", "SERIAL"),
            ("attempt_recovery", "reconcile_static_return", "SERIAL"),
        },
        "unexpected dynamic preset topology",
    )
    exception_context = graph.get("exception_context") or {}
    _assert(exception_context.get("source_run_key") == "a" * 64, "dynamic preset should capture source run key")
    _assert(
        exception_context.get("root_cause_signature") == "formalization-mapping-desync",
        "dynamic preset should capture root cause signature",
    )
    same_cause_other_run = build_dynamic_recovery_graph(
        source_run_key="b" * 64,
        root_cause_signature="formalization-mapping-desync",
    )
    _assert(
        graph["graph_id"] != same_cause_other_run["graph_id"],
        "dynamic graph_id must differ when source_run_key differs under the same root cause",
    )
    same_prefix_other_tail = build_dynamic_recovery_graph(
        source_run_key="1234567890ab" + ("c" * 52),
        root_cause_signature="formalization-mapping-desync",
    )
    same_prefix_other_tail_2 = build_dynamic_recovery_graph(
        source_run_key="1234567890ab" + ("d" * 52),
        root_cause_signature="formalization-mapping-desync",
    )
    _assert(
        same_prefix_other_tail["graph_id"] != same_prefix_other_tail_2["graph_id"],
        "dynamic graph_id must remain collision-resistant when run keys share the same prefix",
    )


def _assert_maintainer_shape() -> None:
    bundle = build_maintainer_change_bundle(change_id="loop_requirement_rollout")
    graph = _assert_bundle_shape(bundle, expected_preset_id="maintainer_change_v1")
    _assert(graph["graph_mode"] == "STATIC_USER_MODE", "maintainer graph must be static")
    expected_nodes = [
        "execplan",
        "graph_spec",
        "test_node",
        "implement_node",
        "verify_node",
        "ai_review_node",
        "loop_closeout",
    ]
    _assert(_node_ids(graph) == expected_nodes, "maintainer graph must follow the required node chain")
    edges = _edges(graph)
    _assert(
        {
            ("execplan", "graph_spec", "SERIAL"),
            ("graph_spec", "test_node", "SERIAL"),
            ("test_node", "implement_node", "SERIAL"),
            ("implement_node", "verify_node", "SERIAL"),
            ("verify_node", "ai_review_node", "SERIAL"),
        }.issubset(edges),
        "maintainer graph must preserve the required serial work path",
    )
    _assert(
        {
            ("execplan", "loop_closeout", "SERIAL"),
            ("graph_spec", "loop_closeout", "SERIAL"),
            ("test_node", "loop_closeout", "SERIAL"),
            ("implement_node", "loop_closeout", "SERIAL"),
            ("verify_node", "loop_closeout", "SERIAL"),
            ("ai_review_node", "loop_closeout", "SERIAL"),
        }.issubset(edges),
        "maintainer graph must route all terminal states into loop_closeout",
    )
    roles = {str(node["node_id"]): str(node.get("role") or "") for node in graph["nodes"]}
    _assert(roles["execplan"] == "PROPOSER", "execplan node should be PROPOSER")
    _assert(roles["ai_review_node"] == "REVIEWER", "ai_review node should be REVIEWER")
    _assert(roles["loop_closeout"] == "JUDGE", "loop_closeout node should be JUDGE")
    closeout = next(node for node in graph["nodes"] if node["node_id"] == "loop_closeout")
    _assert(
        closeout.get("allow_terminal_predecessors") is True,
        "loop_closeout must opt into terminal-predecessor execution",
    )
    resources = _resource_class_map(bundle)
    _assert(resources["maintainer.execplan"] == "IMMUTABLE", "execplan should be immutable once frozen")
    _assert(resources["maintainer.review_history"] == "APPEND_ONLY", "review history should be append-only")
    _assert(resources["maintainer.closeout_state"] == "MUTABLE_CONTROLLED", "closeout state should be controlled")


def _assert_allow_terminal_contract() -> None:
    invalid_root_sink = {
        "version": "1",
        "graph_id": "graph.allow_terminal.invalid_root_sink",
        "graph_mode": "STATIC_USER_MODE",
        "nodes": [
            {"node_id": "closeout", "loop_id": "loop.closeout", "allow_terminal_predecessors": True},
        ],
        "edges": [],
    }
    try:
        LoopGraphRuntime(repo_root=ROOT, run_key="c" * 64).execute(
            graph_spec=invalid_root_sink,
            node_executor=_all_pass,
        )
    except ValueError as exc:
        _assert(
            "requires at least one incoming edge" in str(exc),
            "root sink allow_terminal_predecessors should be rejected explicitly",
        )
    else:
        raise AssertionError("allow_terminal_predecessors must require at least one incoming edge")

    invalid_non_sink = {
        "version": "1",
        "graph_id": "graph.allow_terminal.invalid_non_sink",
        "graph_mode": "STATIC_USER_MODE",
        "nodes": [
            {"node_id": "root", "loop_id": "loop.root"},
            {"node_id": "closeout", "loop_id": "loop.closeout", "allow_terminal_predecessors": True},
            {"node_id": "tail", "loop_id": "loop.tail"},
        ],
        "edges": [
            {"from": "root", "to": "closeout", "kind": "SERIAL"},
            {"from": "closeout", "to": "tail", "kind": "SERIAL"},
        ],
    }
    try:
        LoopGraphRuntime(repo_root=ROOT, run_key="d" * 64).execute(
            graph_spec=invalid_non_sink,
            node_executor=_all_pass,
        )
    except ValueError as exc:
        _assert("sink nodes" in str(exc), "non-sink allow_terminal_predecessors should be rejected explicitly")
    else:
        raise AssertionError("allow_terminal_predecessors must be rejected on non-sink nodes")

    invalid_quorum = {
        "version": "1",
        "graph_id": "graph.allow_terminal.invalid_quorum",
        "graph_mode": "STATIC_USER_MODE",
        "nodes": [
            {"node_id": "left", "loop_id": "loop.left"},
            {"node_id": "right", "loop_id": "loop.right"},
            {"node_id": "closeout", "loop_id": "loop.closeout", "allow_terminal_predecessors": True},
        ],
        "edges": [
            {"from": "left", "to": "closeout", "kind": "QUORUM"},
            {"from": "right", "to": "closeout", "kind": "QUORUM"},
        ],
    }
    try:
        LoopGraphRuntime(repo_root=ROOT, run_key="e" * 64).execute(
            graph_spec=invalid_quorum,
            node_executor=_all_pass,
        )
    except ValueError as exc:
        _assert(
            "SERIAL/PARALLEL/NESTED/BARRIER" in str(exc),
            "allow_terminal_predecessors should reject QUORUM/RACE incoming edges",
        )
    else:
        raise AssertionError("allow_terminal_predecessors must reject QUORUM/RACE incoming edges")


def _assert_runtime_execution() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_preset_exec_") as td:
        repo = Path(td)

        task_rt = LoopGraphRuntime(repo_root=repo, run_key="1" * 64)
        task_summary = task_rt.execute(
            graph_spec=build_task_bootstrap_graph(task_id="formalization_bootstrap"),
            node_executor=_all_pass,
        )
        _assert(task_summary["final_status"] == "PASSED", "task preset should pass with all-pass executor")

        formalization_rt = LoopGraphRuntime(repo_root=repo, run_key="2" * 64)
        formalization_summary = formalization_rt.execute(
            graph_spec=build_formalization_graph(paper_id="A2112_13254v3"),
            node_executor=_all_pass,
        )
        _assert(
            formalization_summary["final_status"] == "PASSED",
            "formalization preset should pass with all-pass executor",
        )

        dynamic_rt = LoopGraphRuntime(repo_root=repo, run_key="3" * 64)
        dynamic_summary = dynamic_rt.execute(
            graph_spec=build_dynamic_recovery_graph(
                source_run_key="a" * 64,
                root_cause_signature="formalization-mapping-desync",
            ),
            node_executor=_all_pass,
            unresolved_exception=True,
        )
        _assert(dynamic_summary["final_status"] == "PASSED", "dynamic preset should pass with all-pass executor")
        _assert(dynamic_summary["return_to_static_flow"] is True, "dynamic preset should return to static flow")

        maintainer_summary = execute_recorded_graph(
            repo_root=repo,
            run_key="4" * 64,
            graph_spec=build_maintainer_change_graph(change_id="loop_requirement_rollout"),
            node_results={
                "execplan": {"state": "PASSED", "reason_code": "EXECPLAN_FROZEN"},
                "graph_spec": {"state": "PASSED", "reason_code": "GRAPH_SPEC_MATERIALIZED"},
                "test_node": {"state": "PASSED", "reason_code": "TESTS_LOCKED"},
                "implement_node": {"state": "PASSED", "reason_code": "IMPLEMENTATION_APPLIED"},
                "verify_node": {"state": "PASSED", "reason_code": "VERIFICATION_PASS"},
                "ai_review_node": {"state": "PASSED", "reason_code": "REVIEW_PASS"},
                "loop_closeout": {"state": "PASSED", "reason_code": "REVIEW_PASS"},
            },
        )
        _assert(maintainer_summary["final_status"] == "PASSED", "maintainer recorded graph should pass")
        summary_ref = str(maintainer_summary.get("summary_ref") or "")
        _assert(summary_ref.endswith("graph/GraphSummary.jsonl"), "maintainer execution should emit GraphSummary")
        graph_spec_path = (repo / "artifacts" / "loop_runtime" / "by_key" / ("4" * 64) / "graph" / "GraphSpec.json").resolve()
        node_results_path = (
            repo / "artifacts" / "loop_runtime" / "by_key" / ("4" * 64) / "graph" / "NodeResults.json"
        ).resolve()
        _assert(graph_spec_path.exists(), "recorded graph execution should persist GraphSpec.json")
        _assert(node_results_path.exists(), "recorded graph execution should persist NodeResults.json")
        persisted_summary = json.loads(Path(summary_ref).read_text(encoding="utf-8").strip().splitlines()[-1])
        _assert(
            persisted_summary["graph_spec_ref"] == str(graph_spec_path),
            "persisted GraphSummary must carry graph_spec_ref",
        )
        _assert(
            persisted_summary["node_results_ref"] == str(node_results_path),
            "persisted GraphSummary must carry node_results_ref",
        )

        inconsistent_summary = execute_recorded_graph(
            repo_root=repo,
            run_key="5" * 64,
            graph_spec=build_maintainer_change_graph(change_id="blocked_branch_consistency"),
            node_results={
                "execplan": {"state": "FAILED", "reason_code": "EXECPLAN_REJECTED"},
                "graph_spec": {"state": "PASSED", "reason_code": "IGNORED_IF_BLOCKED"},
                "test_node": {"state": "PASSED", "reason_code": "IGNORED_IF_BLOCKED"},
                "implement_node": {"state": "PASSED", "reason_code": "IGNORED_IF_BLOCKED"},
                "verify_node": {"state": "PASSED", "reason_code": "IGNORED_IF_BLOCKED"},
                "ai_review_node": {"state": "FAILED", "reason_code": "IGNORED_IF_BLOCKED"},
                "loop_closeout": {"state": "FAILED", "reason_code": "IGNORED_IF_BLOCKED"},
            },
        )
        inconsistent_node_results = json.loads(
            (
                repo
                / "artifacts"
                / "loop_runtime"
                / "by_key"
                / ("5" * 64)
                / "graph"
                / "NodeResults.json"
            ).read_text(encoding="utf-8")
        )
        graph_spec_decision = next(
            decision for decision in inconsistent_summary["node_decisions"] if decision["node_id"] == "graph_spec"
        )
        _assert(
            inconsistent_node_results["graph_spec"]["state"] == graph_spec_decision["state"],
            "NodeResults.json must reflect the actual executed/blocked node state",
        )

        triaged_summary = execute_recorded_graph(
            repo_root=repo,
            run_key="8" * 64,
            graph_spec=build_maintainer_change_graph(change_id="triaged_closeout"),
            node_results={
                "execplan": {"state": "PASSED", "reason_code": "EXECPLAN_FROZEN"},
                "graph_spec": {"state": "PASSED", "reason_code": "GRAPH_SPEC_MATERIALIZED"},
                "test_node": {"state": "PASSED", "reason_code": "TESTS_LOCKED"},
                "implement_node": {"state": "PASSED", "reason_code": "IMPLEMENTATION_APPLIED"},
                "verify_node": {"state": "PASSED", "reason_code": "VERIFICATION_PASS"},
                "ai_review_node": {"state": "TRIAGED", "reason_code": "TRIAGED_TOOLING"},
                "loop_closeout": {"state": "TRIAGED", "reason_code": "TRIAGED_TOOLING"},
            },
        )
        triaged_closeout = next(
            decision for decision in triaged_summary["node_decisions"] if decision["node_id"] == "loop_closeout"
        )
        _assert(triaged_closeout["state"] == "TRIAGED", "closeout should execute after triaged AI review")
        _assert(
            triaged_closeout["reason_code"] == "TRIAGED_TOOLING",
            "closeout should preserve explicit triage reason instead of UPSTREAM_BLOCKED",
        )

        raw_runtime = LoopGraphRuntime(repo_root=repo, run_key="b" * 64)
        raw_runtime_summary = raw_runtime.execute(
            graph_spec=build_maintainer_change_graph(change_id="raw_runtime_terminal_masking"),
            node_executor=lambda node: {
                "execplan": {"state": "PASSED", "reason_code": "EXECPLAN_FROZEN"},
                "graph_spec": {"state": "PASSED", "reason_code": "GRAPH_SPEC_MATERIALIZED"},
                "test_node": {"state": "PASSED", "reason_code": "TESTS_LOCKED"},
                "implement_node": {"state": "PASSED", "reason_code": "IMPLEMENTATION_APPLIED"},
                "verify_node": {"state": "PASSED", "reason_code": "VERIFICATION_PASS"},
                "ai_review_node": {"state": "FAILED", "reason_code": "REVIEW_REJECTED"},
                "loop_closeout": {"state": "PASSED", "reason_code": "CLOSEOUT_RECORDED"},
            }[str(node["node_id"])],
        )
        raw_closeout = next(
            decision for decision in raw_runtime_summary["node_decisions"] if decision["node_id"] == "loop_closeout"
        )
        _assert(raw_closeout["state"] == "PASSED", "regression check requires a passing closeout sink")
        _assert(
            raw_runtime_summary["final_status"] == "FAILED",
            "terminal-predecessor closeout must not mask an upstream failed AI review in GraphSummary",
        )
        try:
            raw_runtime.execute(
                graph_spec=build_maintainer_change_graph(change_id="summary_overlay_core_fields"),
                node_executor=_all_pass,
                summary_overlay={"final_status": "PASSED", "run_key": "f" * 64},
            )
        except ValueError as exc:
            _assert(
                "summary_overlay cannot override core summary fields" in str(exc),
                "summary_overlay should reject attempts to overwrite core GraphSummary fields",
            )
        else:
            raise AssertionError("summary_overlay must not override final_status or run_key")

        retry_same_key_graph = build_maintainer_change_graph(change_id="summary_consistency")
        first_retry = execute_recorded_graph(
            repo_root=repo,
            run_key="9" * 64,
            graph_spec=retry_same_key_graph,
            node_results={
                "execplan": {"state": "PASSED", "reason_code": "EXECPLAN_FROZEN"},
                "graph_spec": {"state": "PASSED", "reason_code": "GRAPH_SPEC_MATERIALIZED"},
                "test_node": {"state": "PASSED", "reason_code": "TESTS_LOCKED"},
                "implement_node": {"state": "PASSED", "reason_code": "IMPLEMENTATION_APPLIED"},
                "verify_node": {"state": "PASSED", "reason_code": "VERIFICATION_PASS"},
                "ai_review_node": {"state": "PASSED", "reason_code": "REVIEW_PASS"},
                "loop_closeout": {"state": "PASSED", "reason_code": "REVIEW_PASS"},
            },
        )
        retry_summary_path = Path(str(first_retry["summary_ref"]))
        _assert(len(retry_summary_path.read_text(encoding="utf-8").splitlines()) == 1, "expected one summary line")
        second_retry = execute_recorded_graph(
            repo_root=repo,
            run_key="9" * 64,
            graph_spec=retry_same_key_graph,
            node_results={
                "execplan": {"state": "PASSED", "reason_code": "EXECPLAN_FROZEN"},
                "graph_spec": {"state": "PASSED", "reason_code": "GRAPH_SPEC_MATERIALIZED"},
                "test_node": {"state": "PASSED", "reason_code": "TESTS_LOCKED"},
                "implement_node": {"state": "PASSED", "reason_code": "IMPLEMENTATION_APPLIED"},
                "verify_node": {"state": "PASSED", "reason_code": "VERIFICATION_PASS"},
                "ai_review_node": {"state": "PASSED", "reason_code": "REVIEW_PASS"},
                "loop_closeout": {"state": "PASSED", "reason_code": "REVIEW_PASS"},
            },
        )
        _assert(second_retry["summary_ref"] == first_retry["summary_ref"], "idempotent replay should reuse summary_ref")
        _assert(
            len(retry_summary_path.read_text(encoding="utf-8").splitlines()) == 1,
            "idempotent replay must not append duplicate GraphSummary lines",
        )
        try:
            execute_recorded_graph(
                repo_root=repo,
                run_key="9" * 64,
                graph_spec=retry_same_key_graph,
                node_results={
                    "execplan": {"state": "FAILED", "reason_code": "EXECPLAN_REJECTED"},
                    "graph_spec": {"state": "PASSED", "reason_code": "IGNORED_IF_BLOCKED"},
                    "test_node": {"state": "PASSED", "reason_code": "IGNORED_IF_BLOCKED"},
                    "implement_node": {"state": "PASSED", "reason_code": "IGNORED_IF_BLOCKED"},
                    "verify_node": {"state": "PASSED", "reason_code": "IGNORED_IF_BLOCKED"},
                    "ai_review_node": {"state": "FAILED", "reason_code": "IGNORED_IF_BLOCKED"},
                    "loop_closeout": {"state": "FAILED", "reason_code": "IGNORED_IF_BLOCKED"},
                },
            )
        except FileExistsError:
            pass
        else:
            raise AssertionError("conflicting rerun on same run_key must fail before appending a new summary")
        _assert(
            len(retry_summary_path.read_text(encoding="utf-8").splitlines()) == 1,
            "conflicting rerun must not append an inconsistent GraphSummary line",
        )

        try:
            execute_recorded_graph(
                repo_root=repo,
                run_key="a" * 64,
                graph_spec=build_maintainer_change_graph(change_id="closeout_must_not_improve_review"),
                node_results={
                    "execplan": {"state": "PASSED", "reason_code": "EXECPLAN_FROZEN"},
                    "graph_spec": {"state": "PASSED", "reason_code": "GRAPH_SPEC_MATERIALIZED"},
                    "test_node": {"state": "PASSED", "reason_code": "TESTS_LOCKED"},
                    "implement_node": {"state": "PASSED", "reason_code": "IMPLEMENTATION_APPLIED"},
                    "verify_node": {"state": "PASSED", "reason_code": "VERIFICATION_PASS"},
                    "ai_review_node": {"state": "FAILED", "reason_code": "REVIEW_NON_RETRYABLE_FAULT"},
                    "loop_closeout": {"state": "PASSED", "reason_code": "REVIEW_PASS"},
                },
            )
        except ValueError as exc:
            _assert(
                "must preserve ai_review_node terminal state" in str(exc),
                "closeout override rejection should explain the terminal-state mismatch",
            )
        else:
            raise AssertionError("maintainer closeout must not improve the AI review terminal state")

        try:
            execute_recorded_graph(
                repo_root=repo,
                run_key="6" * 64,
                graph_spec=build_maintainer_change_bundle(change_id="bundle_is_not_graph_spec"),
                node_results={
                    "execplan": {"state": "PASSED", "reason_code": "EXECPLAN_FROZEN"},
                    "graph_spec": {"state": "PASSED", "reason_code": "GRAPH_SPEC_MATERIALIZED"},
                    "test_node": {"state": "PASSED", "reason_code": "TESTS_LOCKED"},
                    "implement_node": {"state": "PASSED", "reason_code": "IMPLEMENTATION_APPLIED"},
                    "verify_node": {"state": "PASSED", "reason_code": "VERIFICATION_PASS"},
                    "ai_review_node": {"state": "PASSED", "reason_code": "REVIEW_PASS"},
                    "loop_closeout": {"state": "PASSED", "reason_code": "REVIEW_PASS"},
                },
            )
        except ValueError as exc:
            _assert("LoopGraphSpec.schema.json" in str(exc), "bundle rejection should cite graph schema validation")
        else:
            raise AssertionError("execute_recorded_graph must reject bundle payloads in place of graph_spec")

        retry_graph = build_dynamic_recovery_graph(
            source_run_key="7" * 64,
            root_cause_signature="retry-after-dynamic-entry-violation",
        )
        retry_results = {
            "exception_intake": {"state": "PASSED", "reason_code": "RECOVERY_INTAKE_READY"},
            "attempt_recovery": {"state": "PASSED", "reason_code": "RECOVERY_APPLIED"},
            "reconcile_static_return": {"state": "PASSED", "reason_code": "STATIC_FLOW_RESTORED"},
        }
        try:
            execute_recorded_graph(
                repo_root=repo,
                run_key="7" * 64,
                graph_spec=retry_graph,
                node_results=retry_results,
            )
        except Exception as exc:
            _assert(
                "unresolved_exception=True" in str(exc),
                "dynamic retry setup should fail first for the expected entry-policy reason",
            )
        else:
            raise AssertionError("dynamic recorded execution should fail without unresolved_exception=True")

        retry_summary = execute_recorded_graph(
            repo_root=repo,
            run_key="7" * 64,
            graph_spec=retry_graph,
            node_results=retry_results,
            unresolved_exception=True,
        )
        _assert(retry_summary["final_status"] == "PASSED", "dynamic recorded execution should retry cleanly")


def _assert_maintainer_module_import_stays_jsonschema_optional() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_top_level_import_") as td:
        blocker = Path(td) / "jsonschema.py"
        blocker.write_text("raise ImportError('blocked jsonschema for regression test')\n", encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{td}{os.pathsep}{ROOT}"
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import importlib.util\n"
                    "import pathlib\n"
                    "import sys\n"
                    "import types\n"
                    f"root = pathlib.Path({str(ROOT)!r})\n"
                    "tools_pkg = types.ModuleType('tools')\n"
                    "tools_pkg.__path__ = [str(root / 'tools')]\n"
                    "sys.modules['tools'] = tools_pkg\n"
                    "loop_pkg = types.ModuleType('tools.loop')\n"
                    "loop_pkg.__path__ = [str(root / 'tools' / 'loop')]\n"
                    "sys.modules['tools.loop'] = loop_pkg\n"
                    "spec = importlib.util.spec_from_file_location("
                    "'tools.loop.maintainer', root / 'tools' / 'loop' / 'maintainer.py')\n"
                    "module = importlib.util.module_from_spec(spec)\n"
                    "sys.modules['tools.loop.maintainer'] = module\n"
                    "assert spec.loader is not None\n"
                    "spec.loader.exec_module(module)\n"
                    "assert callable(module.execute_recorded_graph)\n"
                    "print('ok')\n"
                ),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(
                "importing tools.loop.maintainer should not require jsonschema until execution time: "
                f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
            )


def _assert_package_presets_import_stays_jsonschema_optional() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_package_import_") as td:
        blocker = Path(td) / "jsonschema.py"
        blocker.write_text("raise ImportError('blocked jsonschema for regression test')\n", encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{td}{os.pathsep}{ROOT}"
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import tools.loop.presets as presets\n"
                    "import tools.loop\n"
                    "graph = presets.build_task_bootstrap_graph(task_id='package_optional_dep')\n"
                    "assert graph['graph_id'] == 'graph.loop.task_bootstrap.package_optional_dep'\n"
                    "assert hasattr(tools.loop, 'run')\n"
                    "assert hasattr(tools.loop, 'run_review_closure')\n"
                    "from tools.loop import build_task_bootstrap_graph\n"
                    "graph2 = build_task_bootstrap_graph(task_id='top_level_optional_dep')\n"
                    "assert graph2['graph_id'] == 'graph.loop.task_bootstrap.top_level_optional_dep'\n"
                    "from tools.loop import run, run_review_closure\n"
                    "assert callable(run)\n"
                    "assert callable(run_review_closure)\n"
                    "print('ok')\n"
                ),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(
                "importing tools.loop.presets should not require jsonschema via package __init__: "
                f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
            )


def main() -> int:
    _assert_task_bootstrap_shape()
    _assert_formalization_shape()
    _assert_dynamic_recovery_shape()
    _assert_maintainer_shape()
    _assert_allow_terminal_contract()
    _assert_runtime_execution()
    _assert_maintainer_module_import_stays_jsonschema_optional()
    _assert_package_presets_import_stays_jsonschema_optional()
    print("[loop-composition-presets] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
