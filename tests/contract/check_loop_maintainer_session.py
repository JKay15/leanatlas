#!/usr/bin/env python3
"""Contract check: maintainer LOOP must materialize an upfront session and node journal."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.loop.maintainer as maintainer_module
from tools.loop import (
    MaintainerLoopSession,
    close_maintainer_session,
    execute_recorded_graph,
    issue_root_supervisor_exception,
    materialize_maintainer_session,
    record_maintainer_node_result,
)


def _fail(msg: str) -> int:
    print(f"[loop-maintainer-session][FAIL] {msg}", file=sys.stderr)
    return 2


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _nested_replay_graph() -> dict[str, object]:
    return {
        "version": "1",
        "graph_id": "graph.loop.maintainer_replay_nested",
        "graph_mode": "STATIC_USER_MODE",
        "nodes": [
            {"node_id": "parent_a", "loop_id": "loop.parent_a"},
            {"node_id": "parent_b", "loop_id": "loop.parent_b"},
            {"node_id": "child", "loop_id": "loop.child"},
        ],
        "edges": [
            {"from": "parent_a", "to": "child", "kind": "NESTED"},
            {"from": "parent_b", "to": "child", "kind": "NESTED"},
        ],
    }


def _record_happy_path(*, repo: Path, run_key: str) -> None:
    for node_id, evidence_refs in (
        ("execplan", ["docs/agents/execplans/active_plan.md"]),
        ("graph_spec", ["docs/agents/execplans/active_plan.md"]),
        ("test_node", ["tools/loop/target.py"]),
        ("implement_node", ["tools/loop/target.py"]),
        ("verify_node", ["metadata/context.txt"]),
        ("ai_review_node", ["metadata/context.txt"]),
        ("loop_closeout", ["docs/agents/execplans/active_plan.md"]),
    ):
        record_maintainer_node_result(
            repo_root=repo,
            run_key=run_key,
            node_id=node_id,
            state="PASSED",
            reason_code="REVIEW_PASS" if node_id == "ai_review_node" else "NODE_EXEC_RESULT",
            evidence_refs=evidence_refs,
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loop_maintainer_session_") as td:
        repo = Path(td)
        _write(repo / "AGENTS.md", "# repo instructions\n")
        _write(repo / "docs" / "AGENTS.md", "# docs instructions\n")
        _write(repo / "tests" / "AGENTS.md", "# tests instructions\n")
        _write(repo / "tools" / "AGENTS.md", "# tools instructions\n")
        _write(repo / "docs" / "agents" / "execplans" / "active_plan.md", "---\nstatus: active\n---\n")
        _write(repo / "docs" / "contracts" / "LOOP_WAVE_EXECUTION_CONTRACT.md", "# contract\n")
        _write(repo / "metadata" / "context.txt", "frozen context\n")
        _write(repo / "tools" / "loop" / "target.py", "VALUE = 1\n")
        active_instruction_scope = ["AGENTS.md", "docs/AGENTS.md", "tools/AGENTS.md"]

        try:
            materialize_maintainer_session(
                repo_root=repo,
                change_id="review_wait_policy_missing_chain",
                execplan_ref="docs/agents/execplans/active_plan.md",
                scope_paths=["tools/loop/target.py"],
                instruction_scope_refs=["AGENTS.md"],
                required_context_refs=[
                    "docs/agents/execplans/active_plan.md",
                    "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
                ],
            )
        except ValueError as exc:
            if "active AGENTS.md chain" not in str(exc):
                return _fail("missing-chain rejection should mention the active AGENTS.md chain")
        else:
            return _fail("materialize_maintainer_session must reject incomplete instruction_scope_refs")

        try:
            materialize_maintainer_session(
                repo_root=repo,
                change_id="review_wait_policy_scope_overlap",
                execplan_ref="docs/agents/execplans/active_plan.md",
                scope_paths=["tools/loop/target.py"],
                instruction_scope_refs=active_instruction_scope,
                required_context_refs=[
                    "docs/agents/execplans/active_plan.md",
                    "tools/loop/target.py",
                ],
            )
        except ValueError as exc:
            if "required_context_refs" not in str(exc) or "scope_paths" not in str(exc):
                return _fail("scope-overlap rejection should mention required_context_refs and scope_paths")
        else:
            return _fail("materialize_maintainer_session must reject required_context_refs that overlap scope_paths")

        try:
            materialize_maintainer_session(
                repo_root=repo,
                change_id="review_wait_policy_execplan_overlap",
                execplan_ref="docs/agents/execplans/active_plan.md",
                scope_paths=[
                    "docs/agents/execplans/active_plan.md",
                    "tools/loop/target.py",
                ],
                instruction_scope_refs=active_instruction_scope,
                required_context_refs=[
                    "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
                ],
            )
        except ValueError as exc:
            if "execplan_ref" not in str(exc) or "scope_paths" not in str(exc):
                return _fail("execplan-overlap rejection should mention execplan_ref and scope_paths")
        else:
            return _fail("materialize_maintainer_session must reject execplan_ref that overlaps scope_paths")

        session = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )

        if len(str(session.get("run_key") or "")) != 64:
            return _fail("materialize_maintainer_session must return a 64-char run_key")
        graph_spec_ref = Path(str(session.get("graph_spec_ref") or ""))
        session_ref = Path(str(session.get("session_ref") or ""))
        node_journal_ref = Path(str(session.get("node_journal_ref") or ""))
        progress_ref = Path(str(session.get("progress_ref") or ""))
        if not graph_spec_ref.exists():
            return _fail("maintainer session must materialize graph_spec before implementation begins")
        if not session_ref.exists():
            return _fail("maintainer session must persist MaintainerSession.json")
        if not node_journal_ref.exists():
            return _fail("maintainer session must persist NodeJournal.jsonl")
        if not progress_ref.exists():
            return _fail("maintainer session must persist MaintainerProgress.json")
        root_skeleton_ref = Path(str(session.get("root_supervisor_skeleton_ref") or ""))
        root_delegation_ref = Path(str(session.get("root_supervisor_delegation_ref") or ""))
        if not root_skeleton_ref.exists():
            return _fail("maintainer session must persist root_supervisor_skeleton.json before implementation begins")
        if not root_delegation_ref.exists():
            return _fail("maintainer session must persist root_supervisor_delegation.json before implementation begins")

        session_obj = _read_json(session_ref)
        if session_obj.get("execplan_ref") != "docs/agents/execplans/active_plan.md":
            return _fail("MaintainerSession.json must preserve execplan_ref")
        if session_obj.get("scope_paths") != ["tools/loop/target.py"]:
            return _fail("MaintainerSession.json must preserve normalized scope_paths")
        if session_obj.get("instruction_scope_refs") != active_instruction_scope:
            return _fail("MaintainerSession.json must preserve normalized instruction_scope_refs")
        if session_obj.get("required_context_refs") != [
            "docs/agents/execplans/active_plan.md",
            "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
        ]:
            return _fail("MaintainerSession.json must preserve normalized required_context_refs")
        if not session_obj.get("graph_spec_hash"):
            return _fail("MaintainerSession.json must persist graph_spec_hash for run-identity auditing")
        if str(session_obj.get("root_supervisor_skeleton_ref") or "") != str(root_skeleton_ref):
            return _fail("MaintainerSession.json must preserve root_supervisor_skeleton_ref")
        if str(session_obj.get("root_supervisor_delegation_ref") or "") != str(root_delegation_ref):
            return _fail("MaintainerSession.json must preserve root_supervisor_delegation_ref")
        if graph_spec_ref.name != "GraphSpec.json":
            return _fail("maintainer session graph_spec_ref must point at GraphSpec.json")
        if (graph_spec_ref.parent / "GraphSummary.jsonl").exists():
            return _fail("maintainer session must not create GraphSummary.jsonl before closeout")
        root_skeleton = _read_json(root_skeleton_ref)
        if root_skeleton.get("authoritative_owner_surface") != "generic_loop_library":
            return _fail("root_supervisor_skeleton.json must declare generic_loop_library as the authoritative owner")
        if root_skeleton.get("integrated_closeout_path", {}).get("authoritative_sink_node_id") != "loop_closeout":
            return _fail("root_supervisor_skeleton.json must preserve the authoritative sink node mapping")
        if [str(item.get("node_id") or "") for item in root_skeleton.get("root_nodes") or []] != [
            "execplan",
            "graph_spec",
            "loop_closeout",
        ]:
            return _fail("root_supervisor_skeleton.json root_nodes must list only the root-owned maintainer nodes")
        root_delegation = _read_json(root_delegation_ref)
        if root_delegation.get("delegated_node_ids") != ["test_node", "implement_node", "verify_node", "ai_review_node"]:
            return _fail("root_supervisor_delegation.json must preserve the delegated node set for the maintainer graph")
        if set(root_delegation.get("delegated_node_ids") or []).intersection(
            {str(item.get("node_id") or "") for item in root_skeleton.get("root_nodes") or []}
        ):
            return _fail("root_supervisor_skeleton.json must not classify delegated maintainer nodes as root_nodes")
        progress_obj = _read_json(progress_ref)
        if progress_obj.get("completed_node_ids") != []:
            return _fail("MaintainerProgress.json must start with no completed nodes")
        if progress_obj.get("pending_node_ids") != session_obj.get("node_order"):
            return _fail("MaintainerProgress.json must expose the pending maintainer sequence")
        if progress_obj.get("current_node_id") != "execplan":
            return _fail("MaintainerProgress.json must point at the next pending node")
        if str(progress_obj.get("root_supervisor_skeleton_ref") or "") != str(root_skeleton_ref):
            return _fail("MaintainerProgress.json must surface root_supervisor_skeleton_ref")
        if str(progress_obj.get("root_supervisor_delegation_ref") or "") != str(root_delegation_ref):
            return _fail("MaintainerProgress.json must surface root_supervisor_delegation_ref")

        handle = MaintainerLoopSession.materialize(
            repo_root=repo,
            change_id="review_wait_policy",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        if handle.run_key != str(session["run_key"]):
            return _fail("MaintainerLoopSession.materialize must reuse the deterministic run_key")
        if Path(handle.progress_ref) != progress_ref:
            return _fail("MaintainerLoopSession.materialize must expose the persisted progress sidecar")
        if Path(handle.root_supervisor_skeleton_ref) != root_skeleton_ref:
            return _fail("MaintainerLoopSession.materialize must expose root_supervisor_skeleton_ref")
        if Path(handle.root_supervisor_delegation_ref) != root_delegation_ref:
            return _fail("MaintainerLoopSession.materialize must expose root_supervisor_delegation_ref")

        loaded_handle = MaintainerLoopSession.load(repo_root=repo, run_key=str(session["run_key"]))
        if loaded_handle.session_ref != str(session_ref):
            return _fail("MaintainerLoopSession.load must resolve the persisted session artifact")
        if loaded_handle.root_supervisor_skeleton_ref != str(root_skeleton_ref):
            return _fail("MaintainerLoopSession.load must expose the persisted root_supervisor_skeleton_ref")
        if loaded_handle.root_supervisor_delegation_ref != str(root_delegation_ref):
            return _fail("MaintainerLoopSession.load must expose the persisted root_supervisor_delegation_ref")

        resumed = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        if resumed.get("run_key") != session.get("run_key"):
            return _fail("same-input maintainer session materialization must be reusable with the same run_key")
        if resumed.get("session_ref") != session.get("session_ref"):
            return _fail("same-input maintainer session materialization must reuse the existing session artifact")

        resumed_with_extra_instruction = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=["AGENTS.md", "docs/AGENTS.md", "tests/AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        if resumed_with_extra_instruction.get("run_key") != session.get("run_key"):
            return _fail("extra unrelated AGENTS refs must not fork the maintainer session run_key")
        resumed_extra_session = _read_json(Path(str(resumed_with_extra_instruction.get("session_ref"))))
        if resumed_extra_session.get("instruction_scope_refs") != active_instruction_scope:
            return _fail("maintainer session must canonicalize instruction_scope_refs to the active AGENTS.md chain")
        if str(resumed_with_extra_instruction.get("root_supervisor_skeleton_ref") or "") != str(root_skeleton_ref):
            return _fail("maintainer session reuse must preserve root_supervisor_skeleton_ref")
        if str(resumed_with_extra_instruction.get("root_supervisor_delegation_ref") or "") != str(root_delegation_ref):
            return _fail("maintainer session reuse must preserve root_supervisor_delegation_ref")

        try:
            materialize_maintainer_session(
                repo_root=repo,
                change_id="review_wait_policy_execplan_chain_missing",
                execplan_ref="docs/agents/execplans/active_plan.md",
                scope_paths=["tools/loop/target.py"],
                instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
                required_context_refs=["metadata/context.txt"],
            )
        except ValueError as exc:
            if "docs/AGENTS.md" not in str(exc):
                return _fail("missing execplan-induced AGENTS chain rejection should mention docs/AGENTS.md")
        else:
            return _fail("maintainer session must derive instruction_scope_refs from execplan_ref as well as scope/context refs")

        original_builder = maintainer_module.build_maintainer_change_graph
        try:
            def _revised_builder(*, change_id: str) -> dict[str, object]:
                graph = original_builder(change_id=change_id)
                nodes = []
                for node in graph.get("nodes", []):
                    revised = dict(node)
                    if revised.get("node_id") == "test_node":
                        revised["role"] = "PROPOSER"
                    nodes.append(revised)
                graph = dict(graph)
                graph["nodes"] = nodes
                return graph

            maintainer_module.build_maintainer_change_graph = _revised_builder
            try:
                revised_graph = materialize_maintainer_session(
                    repo_root=repo,
                    change_id="review_wait_policy",
                    execplan_ref="docs/agents/execplans/active_plan.md",
                    scope_paths=["tools/loop/target.py"],
                    instruction_scope_refs=active_instruction_scope,
                    required_context_refs=[
                        "docs/agents/execplans/active_plan.md",
                        "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
                    ],
                )
            except FileExistsError:
                return _fail("graph_spec revisions must produce a new maintainer session run_key instead of colliding with existing GraphSpec.json")
        finally:
            maintainer_module.build_maintainer_change_graph = original_builder

        root_exception = issue_root_supervisor_exception(
            repo_root=repo,
            run_key=str(session["run_key"]),
            reason_code="TOOLING_BLOCKED",
            blocked_capability="loop.worker.execute",
            evidence_refs=["metadata/context.txt"],
            bounded_scope_paths=["tools/loop/target.py"],
            fallback_allowed_actions=["DIRECT_MANUAL_EXECUTION"],
            reentry_condition="resume delegated loop after bounded manual patch",
            affected_node_ids=["implement_node"],
        )
        root_exception_ref = Path(str(root_exception.get("root_supervisor_exception_ref") or ""))
        if not root_exception_ref.exists():
            return _fail("issue_root_supervisor_exception must persist a stable root_supervisor_exception.json artifact")
        root_exception_obj = _read_json(root_exception_ref)
        if root_exception_obj.get("approved_by") != "root_supervisor":
            return _fail("root_supervisor_exception.json must record approved_by = root_supervisor")
        if root_exception_obj.get("affected_node_ids") != ["implement_node"]:
            return _fail("root_supervisor_exception.json must preserve the bounded affected_node_ids")
        if root_exception_obj.get("fallback_allowed_actions") != ["DIRECT_MANUAL_EXECUTION"]:
            return _fail("root_supervisor_exception.json must preserve fallback_allowed_actions")
        second_root_exception = issue_root_supervisor_exception(
            repo_root=repo,
            run_key=str(session["run_key"]),
            reason_code="SECONDARY_TOOLING_BLOCKED",
            blocked_capability="loop.worker.verify",
            evidence_refs=["metadata/context.txt"],
            bounded_scope_paths=["tools/loop/target.py"],
            fallback_allowed_actions=["DIRECT_MANUAL_EXECUTION"],
            reentry_condition="resume delegated verification after bounded manual repair",
            affected_node_ids=["verify_node"],
        )
        if str(second_root_exception.get("root_supervisor_exception_ref") or "") != str(root_exception_ref):
            return _fail("issue_root_supervisor_exception must append to the stable root_supervisor_exception.json artifact")
        root_exception_obj = _read_json(root_exception_ref)
        if int(root_exception_obj.get("issued_exception_count") or 0) != 2:
            return _fail("root_supervisor_exception.json must preserve the number of bounded exception entries")
        if [entry.get("affected_node_ids") for entry in root_exception_obj.get("exceptions") or []] != [
            ["implement_node"],
            ["verify_node"],
        ]:
            return _fail("root_supervisor_exception.json must preserve multiple bounded exception entries in order")

        try:
            issue_root_supervisor_exception(
                repo_root=repo,
                run_key=str(session["run_key"]),
                reason_code="TOOLING_BLOCKED",
                blocked_capability="loop.worker.execute",
                evidence_refs=["metadata/context.txt"],
                bounded_scope_paths=["tools/loop/target.py"],
                fallback_allowed_actions=["DIRECT_MANUAL_EXECUTION"],
                reentry_condition="resume delegated loop after bounded manual patch",
                affected_node_ids=["test_node", "implement_node", "verify_node", "ai_review_node"],
            )
        except ValueError as exc:
            if "proper subset" not in str(exc):
                return _fail("root supervisor exception rejection should mention proper subset when the whole delegated subtree is waived")
        else:
            return _fail("issue_root_supervisor_exception must reject exceptions that waive the whole delegated subtree")

        session_manual = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_manual",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        try:
            record_maintainer_node_result(
                repo_root=repo,
                run_key=str(session_manual["run_key"]),
                node_id="execplan",
                state="PASSED",
                reason_code="NODE_EXEC_RESULT",
            )
            record_maintainer_node_result(
                repo_root=repo,
                run_key=str(session_manual["run_key"]),
                node_id="graph_spec",
                state="PASSED",
                reason_code="NODE_EXEC_RESULT",
            )
            record_maintainer_node_result(
                repo_root=repo,
                run_key=str(session_manual["run_key"]),
                node_id="test_node",
                state="PASSED",
                reason_code="NODE_EXEC_RESULT",
            )
            record_maintainer_node_result(
                repo_root=repo,
                run_key=str(session_manual["run_key"]),
                node_id="implement_node",
                state="PASSED",
                reason_code="NODE_EXEC_RESULT",
                execution_path="DIRECT_MANUAL_EXCEPTION",
            )
        except ValueError as exc:
            if "root-issued exception artifact" not in str(exc):
                return _fail("manual/direct maintainer node rejection should mention the missing root-issued exception artifact")
        else:
            return _fail("direct/manual maintainer node results must require a root-issued exception artifact")

        session_manual_multi = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_manual_multi",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        for node_id in ("execplan", "graph_spec", "test_node"):
            record_maintainer_node_result(
                repo_root=repo,
                run_key=str(session_manual_multi["run_key"]),
                node_id=node_id,
                state="PASSED",
                reason_code="NODE_EXEC_RESULT",
            )
        first_multi_exception = issue_root_supervisor_exception(
            repo_root=repo,
            run_key=str(session_manual_multi["run_key"]),
            reason_code="TOOLING_BLOCKED",
            blocked_capability="loop.worker.execute",
            evidence_refs=["metadata/context.txt"],
            bounded_scope_paths=["tools/loop/target.py"],
            fallback_allowed_actions=["DIRECT_MANUAL_EXECUTION"],
            reentry_condition="resume delegated loop after bounded manual patch",
            affected_node_ids=["implement_node"],
        )
        record_maintainer_node_result(
            repo_root=repo,
            run_key=str(session_manual_multi["run_key"]),
            node_id="implement_node",
            state="PASSED",
            reason_code="NODE_EXEC_RESULT",
            execution_path="DIRECT_MANUAL_EXCEPTION",
            root_exception_ref=str(first_multi_exception["root_supervisor_exception_ref"]),
        )
        second_multi_exception = issue_root_supervisor_exception(
            repo_root=repo,
            run_key=str(session_manual_multi["run_key"]),
            reason_code="VERIFY_TOOLING_BLOCKED",
            blocked_capability="loop.worker.verify",
            evidence_refs=["metadata/context.txt"],
            bounded_scope_paths=["tools/loop/target.py"],
            fallback_allowed_actions=["DIRECT_MANUAL_EXECUTION"],
            reentry_condition="resume delegated verification after bounded manual patch",
            affected_node_ids=["verify_node"],
        )
        if str(second_multi_exception.get("root_supervisor_exception_ref") or "") != str(
            first_multi_exception.get("root_supervisor_exception_ref") or ""
        ):
            return _fail("multiple bounded manual exceptions in one run must reuse the stable root exception artifact path")
        record_maintainer_node_result(
            repo_root=repo,
            run_key=str(session_manual_multi["run_key"]),
            node_id="verify_node",
            state="PASSED",
            reason_code="NODE_EXEC_RESULT",
            execution_path="DIRECT_MANUAL_EXCEPTION",
            root_exception_ref=str(second_multi_exception["root_supervisor_exception_ref"]),
        )

        session_manual_overlap_guard = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_manual_multi_overlap_guard",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        for node_id in ("execplan", "graph_spec", "test_node"):
            record_maintainer_node_result(
                repo_root=repo,
                run_key=str(session_manual_overlap_guard["run_key"]),
                node_id=node_id,
                state="PASSED",
                reason_code="NODE_EXEC_RESULT",
            )
        overlap_first_exception = issue_root_supervisor_exception(
            repo_root=repo,
            run_key=str(session_manual_overlap_guard["run_key"]),
            reason_code="TOOLING_BLOCKED",
            blocked_capability="loop.worker.execute",
            evidence_refs=["metadata/context.txt"],
            bounded_scope_paths=["tools/loop/target.py"],
            fallback_allowed_actions=["DIRECT_MANUAL_EXECUTION"],
            reentry_condition="resume delegated loop after bounded manual patch",
            affected_node_ids=["implement_node"],
        )
        record_maintainer_node_result(
            repo_root=repo,
            run_key=str(session_manual_overlap_guard["run_key"]),
            node_id="implement_node",
            state="PASSED",
            reason_code="NODE_EXEC_RESULT",
            execution_path="DIRECT_MANUAL_EXCEPTION",
            root_exception_ref=str(overlap_first_exception["root_supervisor_exception_ref"]),
        )
        overlap_second_exception = issue_root_supervisor_exception(
            repo_root=repo,
            run_key=str(session_manual_overlap_guard["run_key"]),
            reason_code="VERIFY_TOOLING_BLOCKED",
            blocked_capability="loop.worker.verify",
            evidence_refs=["metadata/context.txt"],
            bounded_scope_paths=["tools/loop/target.py"],
            fallback_allowed_actions=["DIRECT_MANUAL_EXECUTION"],
            reentry_condition="resume delegated verification after bounded manual patch",
            affected_node_ids=["verify_node"],
        )
        overlap_exception_ref = Path(str(overlap_second_exception["root_supervisor_exception_ref"]))
        record_maintainer_node_result(
            repo_root=repo,
            run_key=str(session_manual_overlap_guard["run_key"]),
            node_id="verify_node",
            state="PASSED",
            reason_code="NODE_EXEC_RESULT",
            execution_path="DIRECT_MANUAL_EXCEPTION",
            root_exception_ref=str(overlap_exception_ref),
        )
        record_maintainer_node_result(
            repo_root=repo,
            run_key=str(session_manual_overlap_guard["run_key"]),
            node_id="ai_review_node",
            state="PASSED",
            reason_code="REVIEW_PASS",
            evidence_refs=["metadata/context.txt"],
        )
        record_maintainer_node_result(
            repo_root=repo,
            run_key=str(session_manual_overlap_guard["run_key"]),
            node_id="loop_closeout",
            state="PASSED",
            reason_code="NODE_EXEC_RESULT",
            evidence_refs=["docs/agents/execplans/active_plan.md"],
        )
        overlap_exception_obj = _read_json(overlap_exception_ref)
        overlap_exception_obj["exceptions"].extend(
            [
                {
                    "version": "1",
                    "issued_at_utc": "2026-03-09T00:00:00Z",
                    "run_key": str(session_manual_overlap_guard["run_key"]),
                    "execplan_ref": "docs/agents/execplans/active_plan.md",
                    "reason_code": "AUXILIARY_TOOLING_BLOCKED",
                    "blocked_capability": "loop.worker.test",
                    "evidence_refs": ["metadata/context.txt"],
                    "approved_by": "root_supervisor",
                    "bounded_scope_paths": ["tools/loop/target.py"],
                    "fallback_allowed_actions": ["DIRECT_MANUAL_EXECUTION"],
                    "reentry_condition": "resume delegated execution after bounded manual patch",
                    "affected_node_ids": ["test_node"],
                },
                {
                    "version": "1",
                    "issued_at_utc": "2026-03-09T00:00:01Z",
                    "run_key": str(session_manual_overlap_guard["run_key"]),
                    "execplan_ref": "docs/agents/execplans/active_plan.md",
                    "reason_code": "AUXILIARY_REVIEW_BLOCKED",
                    "blocked_capability": "loop.worker.review",
                    "evidence_refs": ["metadata/context.txt"],
                    "approved_by": "root_supervisor",
                    "bounded_scope_paths": ["tools/loop/target.py"],
                    "fallback_allowed_actions": ["DIRECT_MANUAL_EXECUTION"],
                    "reentry_condition": "resume delegated review after bounded manual patch",
                    "affected_node_ids": ["test_node", "ai_review_node"],
                },
            ]
        )
        overlap_exception_ref.write_text(
            json.dumps(overlap_exception_obj, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            close_maintainer_session(repo_root=repo, run_key=str(session_manual_overlap_guard["run_key"]))
        except ValueError as exc:
            if "overlapping affected_node_ids" not in str(exc):
                return _fail(
                    "closeout rejection should mention overlapping affected_node_ids when the root exception artifact overlaps away from the active direct/manual nodes"
                )
        else:
            return _fail(
                "maintainer closeout must reject globally overlapping root-issued exception entries even when the overlap is outside the active direct/manual node"
            )

        foreign_session = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_manual_foreign_exception",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        foreign_exception = issue_root_supervisor_exception(
            repo_root=repo,
            run_key=str(foreign_session["run_key"]),
            reason_code="TOOLING_BLOCKED",
            blocked_capability="loop.worker.execute",
            evidence_refs=["metadata/context.txt"],
            bounded_scope_paths=["tools/loop/target.py"],
            fallback_allowed_actions=["DIRECT_MANUAL_EXECUTION"],
            reentry_condition="resume delegated loop after bounded manual patch",
            affected_node_ids=["implement_node"],
        )
        try:
            record_maintainer_node_result(
                repo_root=repo,
                run_key=str(session_manual["run_key"]),
                node_id="implement_node",
                state="PASSED",
                reason_code="NODE_EXEC_RESULT",
                execution_path="DIRECT_MANUAL_EXCEPTION",
                root_exception_ref=str(foreign_exception["root_supervisor_exception_ref"]),
            )
        except ValueError as exc:
            if "session's root-issued exception artifact" not in str(exc):
                return _fail(
                    "manual/direct maintainer node rejection should require the session's root-issued exception artifact"
                )
        else:
            return _fail(
                "direct/manual maintainer node results must reject a foreign root-issued exception artifact when the session has not recorded its own exception ref"
            )

        session_closeout_guard = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_closeout_guard",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        _record_happy_path(repo=repo, run_key=str(session_closeout_guard["run_key"]))
        skeleton_guard_path = Path(str(session_closeout_guard["root_supervisor_skeleton_ref"]))
        skeleton_guard_path.unlink()
        try:
            close_maintainer_session(repo_root=repo, run_key=str(session_closeout_guard["run_key"]))
        except ValueError as exc:
            if "root_supervisor_skeleton_ref" not in str(exc):
                return _fail("closeout rejection should mention root_supervisor_skeleton_ref when the root skeleton artifact is missing")
        else:
            return _fail("maintainer closeout must fail closed when root_supervisor_skeleton_ref is missing")

        session_closeout_guard_stale = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_closeout_guard_stale",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        _record_happy_path(repo=repo, run_key=str(session_closeout_guard_stale["run_key"]))
        stale_skeleton_path = Path(str(session_closeout_guard_stale["root_supervisor_skeleton_ref"]))
        stale_skeleton_obj = _read_json(stale_skeleton_path)
        stale_skeleton_obj["integrated_closeout_path"]["authoritative_sink_node_id"] = "verify_node"
        stale_skeleton_path.write_text(
            json.dumps(stale_skeleton_obj, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            close_maintainer_session(repo_root=repo, run_key=str(session_closeout_guard_stale["run_key"]))
        except ValueError as exc:
            if "root_supervisor_skeleton_ref" not in str(exc):
                return _fail(
                    "closeout rejection should mention root_supervisor_skeleton_ref when the root skeleton artifact is stale"
                )
        else:
            return _fail(
                "maintainer closeout must fail closed when root_supervisor_skeleton_ref content drifts from the canonical root skeleton"
            )

        session_closeout_guard2 = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_closeout_guard2",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        _record_happy_path(repo=repo, run_key=str(session_closeout_guard2["run_key"]))
        delegation_guard_path = Path(str(session_closeout_guard2["root_supervisor_delegation_ref"]))
        delegation_guard_path.unlink()
        try:
            close_maintainer_session(repo_root=repo, run_key=str(session_closeout_guard2["run_key"]))
        except ValueError as exc:
            if "root_supervisor_delegation_ref" not in str(exc):
                return _fail("closeout rejection should mention root_supervisor_delegation_ref when the delegation artifact is missing")
        else:
            return _fail("maintainer closeout must fail closed when root_supervisor_delegation_ref is missing")
        if revised_graph.get("run_key") == session.get("run_key"):
            return _fail("frozen graph_spec revisions must participate in maintainer session run identity")

        _write(repo / "docs" / "agents" / "execplans" / "active_plan.md", "---\nstatus: active\nnote: changed\n---\n")
        changed_plan = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        if changed_plan.get("run_key") == session.get("run_key"):
            return _fail("changing execplan contents must produce a different maintainer session run_key")

        _write(repo / "tools" / "loop" / "target.py", "VALUE = 2\n")
        changed_scope = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        if changed_scope.get("run_key") != changed_plan.get("run_key"):
            return _fail("changing scoped file bytes alone must not change the maintainer session run_key")
        _write(repo / "docs" / "agents" / "execplans" / "active_plan.md", "---\nstatus: active\n---\n")

        journal = _read_jsonl(node_journal_ref)
        if len(journal) != 1 or journal[0].get("entry_kind") != "SESSION_STARTED":
            return _fail("NodeJournal.jsonl must begin with a SESSION_STARTED entry")

        legacy_session = _read_json(session_ref)
        legacy_session.pop("closeout_ref_ref", None)
        legacy_session.pop("execplan_hash", None)
        legacy_session.pop("required_context_hash", None)
        legacy_session.pop("instruction_chain_hash", None)
        Path(session_ref).write_text(json.dumps(legacy_session, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        legacy_progress = _read_json(progress_ref)
        legacy_progress.pop("closeout_ref_ref", None)
        Path(progress_ref).write_text(json.dumps(legacy_progress, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        repaired = MaintainerLoopSession.load(repo_root=repo, run_key=str(session["run_key"]))
        repaired_session = _read_json(session_ref)
        repaired_closeout_ref = str(repaired_session.get("closeout_ref_ref") or "")
        if repaired_closeout_ref != str(session.get("closeout_ref_ref") or ""):
            return _fail("loading an existing session must backfill missing closeout_ref_ref into MaintainerSession.json")
        if repaired_session.get("execplan_hash") != session_obj.get("execplan_hash"):
            return _fail("loading an existing session must backfill missing execplan_hash into MaintainerSession.json")
        if repaired_session.get("required_context_hash") != session_obj.get("required_context_hash"):
            return _fail("loading an existing session must backfill missing required_context_hash into MaintainerSession.json")
        if repaired_session.get("instruction_chain_hash") != session_obj.get("instruction_chain_hash"):
            return _fail("loading an existing session must backfill missing instruction_chain_hash into MaintainerSession.json")
        repaired_progress = _read_json(progress_ref)
        if repaired_progress.get("closeout_ref_ref") != repaired_closeout_ref:
            return _fail("loading an existing session must backfill closeout_ref_ref into MaintainerProgress.json")
        handle = repaired

        terminal_results = {
            "execplan": ("PASSED", "EXECPLAN_FROZEN"),
            "graph_spec": ("PASSED", "GRAPH_SPEC_MATERIALIZED"),
            "test_node": ("PASSED", "RED_TESTS_ADDED"),
            "implement_node": ("PASSED", "IMPLEMENTATION_COMPLETE"),
            "verify_node": ("PASSED", "VERIFICATION_PASSED"),
            "ai_review_node": ("PASSED", "REVIEW_PASS"),
            "loop_closeout": ("PASSED", "REVIEW_PASS"),
        }
        for node_id, (state, reason_code) in terminal_results.items():
            handle.record_node_result(node_id=node_id, state=state, reason_code=reason_code)

        try:
            handle.record_node_result(node_id="execplan", state="PASSED", reason_code="DUPLICATE")
        except ValueError as exc:
            if "already has a terminal journal entry" not in str(exc):
                return _fail("duplicate node result rejection should mention terminal journal entry")
        else:
            return _fail("record_maintainer_node_result must reject duplicate terminal entries")

        progress_after = _read_json(progress_ref)
        if progress_after.get("completed_node_ids") != list(terminal_results):
            return _fail("MaintainerProgress.json must advance as node results are recorded")
        if progress_after.get("pending_node_ids") != []:
            return _fail("MaintainerProgress.json must show no pending nodes after all nodes complete")
        if progress_after.get("current_node_id") is not None:
            return _fail("MaintainerProgress.json must clear current_node_id when no nodes remain pending")
        journal_after = _read_jsonl(node_journal_ref)
        ai_review_entries = [
            entry
            for entry in journal_after
            if entry.get("entry_kind") == "NODE_TERMINAL_RESULT" and entry.get("node_id") == "ai_review_node"
        ]
        if len(ai_review_entries) != 1:
            return _fail("recording ai_review_node must journal exactly one ai_review terminal entry")
        ai_review_entry = ai_review_entries[0]
        if not ai_review_entry.get("scope_fingerprint"):
            return _fail("ai_review_node journal entry must capture scope_fingerprint")
        if not ai_review_entry.get("scope_observed_stamp"):
            return _fail("ai_review_node journal entry must capture scope_observed_stamp")

        summary = handle.close()
        if summary.get("final_status") != "PASSED":
            return _fail("close_maintainer_session must synthesize a PASSED GraphSummary from journaled results")
        if summary.get("graph_spec_ref") != str(graph_spec_ref):
            return _fail("close_maintainer_session must preserve graph_spec_ref in GraphSummary")
        closeout_ref_ref = summary.get("closeout_ref_ref")
        if not isinstance(closeout_ref_ref, str) or not closeout_ref_ref:
            return _fail("close_maintainer_session must expose a stable closeout_ref_ref")
        closeout_ref_path = Path(closeout_ref_ref)
        if not closeout_ref_path.exists():
            return _fail("close_maintainer_session must persist the stable closeout ref artifact")
        closeout_ref = _read_json(closeout_ref_path)
        if closeout_ref.get("execplan_ref") != "docs/agents/execplans/active_plan.md":
            return _fail("stable closeout ref must preserve execplan_ref")
        if closeout_ref.get("run_key") != str(session["run_key"]):
            return _fail("stable closeout ref must preserve the settled maintainer run_key")
        if closeout_ref.get("summary_ref") != summary.get("summary_ref"):
            return _fail("stable closeout ref must point at the settled GraphSummary")
        if closeout_ref.get("final_status") != "PASSED":
            return _fail("stable closeout ref must preserve the settled final_status")

        closed_progress = _read_json(progress_ref)
        if closed_progress.get("final_status") != "PASSED":
            return _fail("MaintainerProgress.json must preserve final_status after closeout")
        if not closed_progress.get("summary_ref"):
            return _fail("MaintainerProgress.json must expose summary_ref after closeout")
        if closed_progress.get("closeout_ref_ref") != closeout_ref_ref:
            return _fail("MaintainerProgress.json must expose closeout_ref_ref after closeout")
        closed_updated_at = closed_progress.get("updated_at_utc")

        reloaded = MaintainerLoopSession.load(repo_root=repo, run_key=str(session["run_key"]))
        if reloaded.progress_ref != str(progress_ref):
            return _fail("MaintainerLoopSession.load must preserve the same progress sidecar path")
        reloaded_progress = _read_json(progress_ref)
        if reloaded_progress.get("final_status") != "PASSED":
            return _fail("reloading a closed session must preserve MaintainerProgress final_status")
        if reloaded_progress.get("summary_ref") != closed_progress.get("summary_ref"):
            return _fail("reloading a closed session must preserve MaintainerProgress summary_ref")
        if reloaded_progress.get("closeout_ref_ref") != closeout_ref_ref:
            return _fail("reloading a closed session must preserve MaintainerProgress closeout_ref_ref")
        if reloaded_progress.get("updated_at_utc") != closed_updated_at:
            return _fail("reloading a closed session without journal changes must not rewrite updated_at_utc")

        _write(repo / "docs" / "agents" / "execplans" / "active_plan.md", "---\nstatus: active\n---\n")
        rematerialized = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        rematerialized_progress = _read_json(progress_ref)
        if rematerialized_progress.get("final_status") != "PASSED":
            return _fail("re-materializing a closed session must preserve MaintainerProgress final_status")
        if rematerialized_progress.get("summary_ref") != closed_progress.get("summary_ref"):
            return _fail("re-materializing a closed session must preserve MaintainerProgress summary_ref")
        if rematerialized_progress.get("closeout_ref_ref") != closeout_ref_ref:
            return _fail("re-materializing a closed session must preserve MaintainerProgress closeout_ref_ref")
        if rematerialized_progress.get("updated_at_utc") != closed_updated_at:
            return _fail("re-materializing a closed session without journal changes must not rewrite updated_at_utc")
        if rematerialized.get("progress_ref") != str(progress_ref):
            return _fail("re-materialized session must still expose the same progress sidecar")

        _write(repo / "docs" / "agents" / "execplans" / "stale_plan.md", "---\nstatus: active\n---\n")
        _write(repo / "tools" / "loop" / "stale_target.py", "STALE = 1\n")
        stale_session = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_stale_closeout",
            execplan_ref="docs/agents/execplans/stale_plan.md",
            scope_paths=["tools/loop/stale_target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/stale_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        stale_handle = MaintainerLoopSession.load(repo_root=repo, run_key=str(stale_session["run_key"]))
        for node_id, (state, reason_code) in terminal_results.items():
            stale_handle.record_node_result(node_id=node_id, state=state, reason_code=reason_code)
        _write(repo / "docs" / "agents" / "execplans" / "stale_plan.md", "---\nstatus: active\nnote: updated\n---\n")
        refreshed_stale_session = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_stale_closeout",
            execplan_ref="docs/agents/execplans/stale_plan.md",
            scope_paths=["tools/loop/stale_target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/stale_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        if refreshed_stale_session.get("run_key") == stale_session.get("run_key"):
            return _fail("changing execplan contents must fork stale-closeout sessions to a new run_key")
        refreshed_handle = MaintainerLoopSession.load(repo_root=repo, run_key=str(refreshed_stale_session["run_key"]))
        for node_id, (state, reason_code) in terminal_results.items():
            refreshed_handle.record_node_result(node_id=node_id, state=state, reason_code=reason_code)
        refreshed_summary = refreshed_handle.close()
        refreshed_closeout_ref = _read_json(Path(str(refreshed_summary["closeout_ref_ref"])))
        try:
            stale_handle.close()
        except ValueError as exc:
            if "stale execplan_ref bytes" not in str(exc):
                return _fail("stale maintainer closeout rejection should mention stale execplan_ref bytes")
        else:
            return _fail("close_maintainer_session must reject stale execplan bytes before overwriting the stable closeout ref")
        stale_closeout_ref = _read_json(Path(str(refreshed_summary["closeout_ref_ref"])))
        if stale_closeout_ref.get("run_key") != refreshed_closeout_ref.get("run_key"):
            return _fail("stale maintainer closeout attempts must not overwrite the latest stable closeout ref")

        _write(repo / "docs" / "agents" / "execplans" / "legacy_hash_plan.md", "---\nstatus: active\n---\n")
        _write(repo / "tools" / "loop" / "legacy_hash_target.py", "LEGACY = 1\n")
        legacy_hash_session = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_legacy_hash",
            execplan_ref="docs/agents/execplans/legacy_hash_plan.md",
            scope_paths=["tools/loop/legacy_hash_target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/legacy_hash_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        legacy_hash_handle = MaintainerLoopSession.load(repo_root=repo, run_key=str(legacy_hash_session["run_key"]))
        for node_id, (state, reason_code) in terminal_results.items():
            legacy_hash_handle.record_node_result(node_id=node_id, state=state, reason_code=reason_code)
        legacy_hash_session_obj = _read_json(Path(str(legacy_hash_session["session_ref"])))
        legacy_hash_session_obj.pop("required_context_hash", None)
        legacy_hash_session_obj.pop("instruction_chain_hash", None)
        Path(str(legacy_hash_session["session_ref"])).write_text(
            json.dumps(legacy_hash_session_obj, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write(repo / "docs" / "contracts" / "LOOP_WAVE_EXECUTION_CONTRACT.md", "# contract updated\n")
        try:
            close_maintainer_session(repo_root=repo, run_key=str(legacy_hash_session["run_key"]))
        except ValueError as exc:
            if "required_context_hash" not in str(exc) and "instruction_chain_hash" not in str(exc):
                return _fail("legacy frozen-input rejection should mention missing required_context_hash/instruction_chain_hash")
        else:
            return _fail("close_maintainer_session must reject legacy sessions that lack frozen context hashes after context drift")

        _write(repo / "docs" / "agents" / "execplans" / "same_plan_alias.md", "---\nstatus: active\n---\n")
        _write(repo / "tools" / "loop" / "same_plan_alias_target.py", "ALIAS = 1\n")
        older_same_plan = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_same_plan_alias_old",
            execplan_ref="docs/agents/execplans/same_plan_alias.md",
            scope_paths=["tools/loop/same_plan_alias_target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/same_plan_alias.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        newer_same_plan = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_same_plan_alias_new",
            execplan_ref="docs/agents/execplans/same_plan_alias.md",
            scope_paths=["tools/loop/same_plan_alias_target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/same_plan_alias.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        if older_same_plan.get("run_key") == newer_same_plan.get("run_key"):
            return _fail("distinct same-plan maintainer sessions must not collapse to one run_key")
        older_same_plan_obj = _read_json(Path(str(older_same_plan["session_ref"])))
        older_same_plan_obj["created_at_utc"] = "2026-03-07T00:00:00Z"
        older_same_plan_obj["created_at_epoch_ns"] = 100
        Path(str(older_same_plan["session_ref"])).write_text(
            json.dumps(older_same_plan_obj, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        newer_same_plan_obj = _read_json(Path(str(newer_same_plan["session_ref"])))
        newer_same_plan_obj["created_at_utc"] = "2026-03-07T00:00:00Z"
        newer_same_plan_obj["created_at_epoch_ns"] = 200
        Path(str(newer_same_plan["session_ref"])).write_text(
            json.dumps(newer_same_plan_obj, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        older_same_plan_handle = MaintainerLoopSession.load(
            repo_root=repo, run_key=str(older_same_plan["run_key"])
        )
        newer_same_plan_handle = MaintainerLoopSession.load(
            repo_root=repo, run_key=str(newer_same_plan["run_key"])
        )
        for node_id, (state, reason_code) in terminal_results.items():
            older_same_plan_handle.record_node_result(node_id=node_id, state=state, reason_code=reason_code)
            newer_same_plan_handle.record_node_result(node_id=node_id, state=state, reason_code=reason_code)
        newer_same_plan_summary = newer_same_plan_handle.close()
        newer_same_plan_closeout_ref = _read_json(Path(str(newer_same_plan_summary["closeout_ref_ref"])))
        if newer_same_plan_closeout_ref.get("session_created_at_utc") != "2026-03-07T00:00:00Z":
            return _fail("stable closeout ref must preserve the authoritative session_created_at_utc")
        if newer_same_plan_closeout_ref.get("session_created_at_epoch_ns") != 200:
            return _fail("stable closeout ref must preserve the authoritative session_created_at_epoch_ns")
        legacy_same_plan_closeout_ref = dict(newer_same_plan_closeout_ref)
        legacy_same_plan_closeout_ref.pop("session_created_at_epoch_ns", None)
        Path(str(newer_same_plan_summary["closeout_ref_ref"])).write_text(
            json.dumps(legacy_same_plan_closeout_ref, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            older_same_plan_handle.close()
        except ValueError as exc:
            if "newer stable closeout ref" not in str(exc):
                return _fail("same-plan alias overwrite rejection should mention the newer stable closeout ref")
        else:
            return _fail("older same-plan maintainer sessions must not overwrite a newer stable closeout ref")
        preserved_same_plan_closeout_ref = _read_json(Path(str(newer_same_plan_summary["closeout_ref_ref"])))
        if preserved_same_plan_closeout_ref.get("run_key") != newer_same_plan_closeout_ref.get("run_key"):
            return _fail("older same-plan closeout attempts must not overwrite the newer stable closeout ref")

        _write(repo / "docs" / "agents" / "execplans" / "reviewed_scope_plan.md", "---\nstatus: active\n---\n")
        _write(repo / "tools" / "loop" / "reviewed_scope_target.py", "REVIEWED = 1\n")
        reviewed_session = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_reviewed_scope",
            execplan_ref="docs/agents/execplans/reviewed_scope_plan.md",
            scope_paths=["tools/loop/reviewed_scope_target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/reviewed_scope_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        reviewed_handle = MaintainerLoopSession.load(repo_root=repo, run_key=str(reviewed_session["run_key"]))
        reviewed_prefix = {
            "execplan": ("PASSED", "EXECPLAN_FROZEN"),
            "graph_spec": ("PASSED", "GRAPH_SPEC_MATERIALIZED"),
            "test_node": ("PASSED", "RED_TESTS_ADDED"),
            "implement_node": ("PASSED", "IMPLEMENTATION_COMPLETE"),
            "verify_node": ("PASSED", "VERIFICATION_PASSED"),
            "ai_review_node": ("PASSED", "REVIEW_PASS"),
        }
        for node_id, (state, reason_code) in reviewed_prefix.items():
            reviewed_handle.record_node_result(node_id=node_id, state=state, reason_code=reason_code)
        _write(repo / "tools" / "loop" / "reviewed_scope_target.py", "REVIEWED = 2\n")
        _write(repo / "tools" / "loop" / "reviewed_scope_target.py", "REVIEWED = 1\n")
        reviewed_handle.record_node_result(node_id="loop_closeout", state="PASSED", reason_code="REVIEW_PASS")
        try:
            reviewed_handle.close()
        except ValueError as exc:
            if "scope_observed_stamp" not in str(exc):
                return _fail("reviewed-scope mutate-and-restore rejection should mention scope_observed_stamp")
        else:
            return _fail("close_maintainer_session must reject mutate-and-restore scope drift after ai_review_node")

        _write(repo / "docs" / "agents" / "execplans" / "reviewed_scope_triaged_plan.md", "---\nstatus: active\n---\n")
        _write(repo / "tools" / "loop" / "reviewed_scope_triaged_target.py", "TRIAGED = 1\n")
        reviewed_triaged_session = materialize_maintainer_session(
            repo_root=repo,
            change_id="review_wait_policy_reviewed_scope_triaged",
            execplan_ref="docs/agents/execplans/reviewed_scope_triaged_plan.md",
            scope_paths=["tools/loop/reviewed_scope_triaged_target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/reviewed_scope_triaged_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        reviewed_triaged_handle = MaintainerLoopSession.load(
            repo_root=repo, run_key=str(reviewed_triaged_session["run_key"])
        )
        reviewed_triaged_prefix = {
            "execplan": ("PASSED", "EXECPLAN_FROZEN"),
            "graph_spec": ("PASSED", "GRAPH_SPEC_MATERIALIZED"),
            "test_node": ("PASSED", "RED_TESTS_ADDED"),
            "implement_node": ("PASSED", "IMPLEMENTATION_COMPLETE"),
            "verify_node": ("PASSED", "VERIFICATION_PASSED"),
            "ai_review_node": ("TRIAGED", "REVIEW_BUDGET_EXHAUSTED"),
        }
        for node_id, (state, reason_code) in reviewed_triaged_prefix.items():
            reviewed_triaged_handle.record_node_result(node_id=node_id, state=state, reason_code=reason_code)
        _write(repo / "tools" / "loop" / "reviewed_scope_triaged_target.py", "TRIAGED = 2\n")
        _write(repo / "tools" / "loop" / "reviewed_scope_triaged_target.py", "TRIAGED = 1\n")
        reviewed_triaged_handle.record_node_result(
            node_id="loop_closeout",
            state="TRIAGED",
            reason_code="REVIEW_BUDGET_EXHAUSTED",
        )
        try:
            reviewed_triaged_handle.close()
        except ValueError as exc:
            if "scope_observed_stamp" not in str(exc):
                return _fail("triaged reviewed-scope rejection should mention scope_observed_stamp")
        else:
            return _fail("close_maintainer_session must reject mutate-and-restore scope drift after triaged ai_review_node")

        replay_run_key = "a" * 64
        replay_graph = _nested_replay_graph()
        replay_node_results = {
            "parent_a": {"state": "PASSED", "reason_code": "PARENT_A_OK"},
            "parent_b": {"state": "PASSED", "reason_code": "PARENT_B_OK"},
            "child": {"state": "PASSED", "reason_code": "CHILD_OK"},
        }
        replay_summary = execute_recorded_graph(
            repo_root=repo,
            run_key=replay_run_key,
            graph_spec=replay_graph,
            node_results=replay_node_results,
        )
        replay_root = (
            repo
            / "artifacts"
            / "loop_runtime"
            / "by_key"
            / replay_run_key
            / "graph"
        )
        scheduler_path = replay_root / "scheduler.jsonl"
        nested_lineage_path = replay_root / "nested_lineage.jsonl"
        if not scheduler_path.exists() or not nested_lineage_path.exists():
            return _fail("initial recorded-graph execution must materialize scheduler and nested-lineage sidecars")
        scheduler_path.unlink()
        nested_lineage_path.unlink()
        replay_summary_again = execute_recorded_graph(
            repo_root=repo,
            run_key=replay_run_key,
            graph_spec=replay_graph,
            node_results=replay_node_results,
        )
        if replay_summary_again.get("summary_ref") != replay_summary.get("summary_ref"):
            return _fail("recorded-graph replay should reuse the existing GraphSummary ref")
        if not scheduler_path.exists():
            return _fail("recorded-graph replay must backfill missing scheduler.jsonl when GraphSummary already exists")
        if not nested_lineage_path.exists():
            return _fail("recorded-graph replay must backfill missing nested_lineage.jsonl when GraphSummary already exists")

        legacy_summary_path = replay_root / "GraphSummary.jsonl"
        legacy_summary = _read_jsonl(legacy_summary_path)
        if len(legacy_summary) != 1:
            return _fail("recorded-graph replay fixture should have exactly one GraphSummary row")
        legacy_row = dict(legacy_summary[0])
        legacy_row["node_decisions"] = [
            {key: value for key, value in dict(decision).items() if key != "executed"}
            for decision in legacy_row.get("node_decisions") or []
        ]
        legacy_summary_path.write_text(json.dumps(legacy_row, sort_keys=True) + "\n", encoding="utf-8")
        arbitration_path = replay_root / "arbitration.jsonl"
        arbitration_path.unlink()
        scheduler_path.unlink()
        nested_lineage_path.unlink()
        replay_summary_legacy = execute_recorded_graph(
            repo_root=repo,
            run_key=replay_run_key,
            graph_spec=replay_graph,
            node_results=replay_node_results,
        )
        if replay_summary_legacy.get("summary_ref") != replay_summary.get("summary_ref"):
            return _fail("legacy GraphSummary replay should still reuse the existing GraphSummary ref")
        if not arbitration_path.exists():
            return _fail("legacy GraphSummary replay must backfill missing arbitration.jsonl sidecar")
        if not scheduler_path.exists():
            return _fail("legacy GraphSummary replay must backfill missing scheduler.jsonl sidecar")
        if not nested_lineage_path.exists():
            return _fail("legacy GraphSummary replay must backfill missing nested_lineage.jsonl sidecar")
        replayed_legacy_summary = _read_jsonl(legacy_summary_path)
        if len(replayed_legacy_summary) != 1:
            return _fail("legacy GraphSummary replay should still leave exactly one summary row")
        replayed_legacy_decisions = replayed_legacy_summary[0].get("node_decisions") or []
        if not replayed_legacy_decisions or not all("executed" in decision for decision in replayed_legacy_decisions):
            return _fail("legacy GraphSummary replay must backfill node_decisions[].executed for old summaries")

        legacy_arbitration_rows = _read_jsonl(arbitration_path)
        arbitration_path.write_text(
            "".join(
                json.dumps(
                    {
                        key: value
                        for key, value in row.items()
                        if key != "predecessor_executed"
                    },
                    sort_keys=True,
                )
                + "\n"
                for row in legacy_arbitration_rows
            ),
            encoding="utf-8",
        )
        replay_summary_legacy_arbitration = execute_recorded_graph(
            repo_root=repo,
            run_key=replay_run_key,
            graph_spec=replay_graph,
            node_results=replay_node_results,
        )
        if replay_summary_legacy_arbitration.get("summary_ref") != replay_summary.get("summary_ref"):
            return _fail("legacy arbitration replay should still reuse the existing GraphSummary ref")
        if not arbitration_path.exists():
            return _fail("legacy arbitration replay must preserve arbitration.jsonl")
        gate_rows = [
            row
            for row in _read_jsonl(arbitration_path)
            if "predecessor_states" in row
        ]
        if not gate_rows:
            return _fail("legacy arbitration replay fixture must include gate rows with predecessor_states")
        if _read_jsonl(arbitration_path) != legacy_arbitration_rows:
            return _fail("legacy arbitration replay must restore the exact current arbitration row shape after backfill")
        if not all("predecessor_executed" in row for row in gate_rows):
            return _fail("legacy arbitration replay must backfill predecessor_executed for old arbitration rows")

        legacy_sidecar_run_key = "b" * 64
        legacy_sidecar_graph = {
            "version": "1",
            "graph_id": "graph.loop.maintainer_replay_legacy_sidecars",
            "graph_mode": "STATIC_USER_MODE",
            "nodes": [
                {"node_id": "parent_fail", "loop_id": "loop.parent_fail"},
                {"node_id": "child_closeout", "loop_id": "loop.child_closeout", "allow_terminal_predecessors": True},
                {"node_id": "blocked_child", "loop_id": "loop.blocked_child"},
            ],
            "edges": [
                {"from": "parent_fail", "to": "child_closeout", "kind": "NESTED"},
                {"from": "parent_fail", "to": "blocked_child", "kind": "SERIAL"},
            ],
        }
        legacy_sidecar_node_results = {
            "parent_fail": {"state": "FAILED", "reason_code": "PARENT_FAIL"},
            "child_closeout": {"state": "PASSED", "reason_code": "BOOKKEEPING_PASS"},
        }
        initial_legacy_sidecar_summary = execute_recorded_graph(
            repo_root=repo,
            run_key=legacy_sidecar_run_key,
            graph_spec=legacy_sidecar_graph,
            node_results=legacy_sidecar_node_results,
        )
        legacy_sidecar_root = (
            repo
            / "artifacts"
            / "loop_runtime"
            / "by_key"
            / legacy_sidecar_run_key
            / "graph"
        )
        legacy_scheduler_path = legacy_sidecar_root / "scheduler.jsonl"
        legacy_nested_path = legacy_sidecar_root / "nested_lineage.jsonl"
        current_scheduler_rows = _read_jsonl(legacy_scheduler_path)
        current_nested_rows = _read_jsonl(legacy_nested_path)
        legacy_scheduler_rows = []
        for row in current_scheduler_rows:
            mutated = dict(row)
            if mutated.get("parallel_width") == 0 and mutated.get("execution_mode") == "SERIAL":
                mutated["parallel_width"] = 1
            legacy_scheduler_rows.append(mutated)
        legacy_nested_rows = []
        for row in current_nested_rows:
            mutated = dict(row)
            if mutated.get("executed") is True and mutated.get("blocked_state") is None:
                mutated["child_state"] = "FAILED"
            legacy_nested_rows.append(mutated)
        legacy_scheduler_path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in legacy_scheduler_rows),
            encoding="utf-8",
        )
        legacy_nested_path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in legacy_nested_rows),
            encoding="utf-8",
        )
        replay_legacy_sidecars = execute_recorded_graph(
            repo_root=repo,
            run_key=legacy_sidecar_run_key,
            graph_spec=legacy_sidecar_graph,
            node_results=legacy_sidecar_node_results,
        )
        if replay_legacy_sidecars.get("summary_ref") != initial_legacy_sidecar_summary.get("summary_ref"):
            return _fail("legacy sidecar replay should still reuse the existing GraphSummary ref")
        if _read_jsonl(legacy_scheduler_path) != current_scheduler_rows:
            return _fail("legacy sidecar replay must rewrite scheduler.jsonl from the pre-fix blocked-batch shape")
        if _read_jsonl(legacy_nested_path) != current_nested_rows:
            return _fail("legacy sidecar replay must rewrite nested_lineage.jsonl from the pre-fix child_state shape")

        ordering = MaintainerLoopSession.materialize(
            repo_root=repo,
            change_id="review_wait_policy_ordering",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        try:
            ordering.record_node_result(
                node_id="implement_node",
                state="PASSED",
                reason_code="OUT_OF_ORDER",
            )
        except ValueError as exc:
            if "predecessor" not in str(exc) and "order" not in str(exc):
                return _fail("out-of-order node rejection should mention predecessor/order constraints")
        else:
            return _fail("record_maintainer_node_result must reject out-of-order node journaling")

        failed_path = MaintainerLoopSession.materialize(
            repo_root=repo,
            change_id="review_wait_policy_failed_path",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        failed_path.record_node_result(
            node_id="execplan",
            state="FAILED",
            reason_code="EXECPLAN_REJECTED",
        )
        failed_progress = _read_json(Path(failed_path.progress_ref))
        if failed_progress.get("completed_node_ids") != ["execplan"]:
            return _fail("failed-path progress should only mark journaled maintainer nodes as completed")
        if failed_progress.get("current_node_id") != "loop_closeout":
            return _fail("failed-path progress should advance directly to loop_closeout")
        if failed_progress.get("pending_node_ids") != ["loop_closeout"]:
            return _fail("failed-path progress should leave only loop_closeout pending")
        if failed_progress.get("bookkeeping_pending_node_ids") != ["loop_closeout"]:
            return _fail("failed-path progress should classify loop_closeout as bookkeeping pending work")
        if failed_progress.get("current_node_mode") != "BOOKKEEPING_CLOSEOUT":
            return _fail("failed-path progress should expose loop_closeout as bookkeeping closeout mode")
        if failed_progress.get("blocked_node_ids") != [
            "graph_spec",
            "test_node",
            "implement_node",
            "verify_node",
            "ai_review_node",
        ]:
            return _fail("failed-path progress should expose deterministically blocked maintainer nodes")
        try:
            failed_path.record_node_result(
                node_id="graph_spec",
                state="PASSED",
                reason_code="SHOULD_NOT_ADVANCE",
            )
        except ValueError as exc:
            if "passed predecessors" not in str(exc) and "blocked" not in str(exc):
                return _fail("failed-predecessor rejection should mention passed/blocking predecessors")
        else:
            return _fail("non-closeout nodes must not advance after a failed predecessor")

        blocked_closeout = MaintainerLoopSession.materialize(
            repo_root=repo,
            change_id="review_wait_policy_blocked_closeout",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        blocked_closeout.record_node_result(node_id="execplan", state="PASSED", reason_code="EXECPLAN_FROZEN")
        blocked_closeout.record_node_result(node_id="graph_spec", state="PASSED", reason_code="GRAPH_SPEC_MATERIALIZED")
        blocked_closeout.record_node_result(node_id="test_node", state="PASSED", reason_code="RED_TESTS_ADDED")
        blocked_closeout.record_node_result(node_id="implement_node", state="PASSED", reason_code="IMPLEMENTATION_COMPLETE")
        blocked_closeout.record_node_result(node_id="verify_node", state="FAILED", reason_code="VERIFICATION_FAILED")
        blocked_progress = _read_json(Path(blocked_closeout.progress_ref))
        if blocked_progress.get("completed_node_ids") != [
            "execplan",
            "graph_spec",
            "test_node",
            "implement_node",
            "verify_node",
        ]:
            return _fail("verify-failure progress should not mark blocked descendants as completed")
        if blocked_progress.get("current_node_id") != "loop_closeout":
            return _fail("verify failure should leave loop_closeout as the only current maintainer node")
        if blocked_progress.get("pending_node_ids") != ["loop_closeout"]:
            return _fail("verify failure should leave only loop_closeout pending")
        if blocked_progress.get("bookkeeping_pending_node_ids") != ["loop_closeout"]:
            return _fail("verify failure should classify loop_closeout as bookkeeping pending work")
        if blocked_progress.get("current_node_mode") != "BOOKKEEPING_CLOSEOUT":
            return _fail("verify failure should expose loop_closeout as bookkeeping closeout mode")
        if blocked_progress.get("blocked_node_ids") != ["ai_review_node"]:
            return _fail("verify failure should expose ai_review_node as a blocked progress node")
        mismatch_closeout = MaintainerLoopSession.materialize(
            repo_root=repo,
            change_id="review_wait_policy_mismatched_closeout",
            execplan_ref="docs/agents/execplans/active_plan.md",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=active_instruction_scope,
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        mismatch_closeout.record_node_result(node_id="execplan", state="PASSED", reason_code="EXECPLAN_FROZEN")
        mismatch_closeout.record_node_result(node_id="graph_spec", state="PASSED", reason_code="GRAPH_SPEC_MATERIALIZED")
        mismatch_closeout.record_node_result(node_id="test_node", state="PASSED", reason_code="RED_TESTS_ADDED")
        mismatch_closeout.record_node_result(node_id="implement_node", state="PASSED", reason_code="IMPLEMENTATION_COMPLETE")
        mismatch_closeout.record_node_result(node_id="verify_node", state="FAILED", reason_code="VERIFICATION_FAILED")
        try:
            mismatch_closeout.record_node_result(
                node_id="loop_closeout",
                state="PASSED",
                reason_code="SHOULD_BE_REJECTED",
            )
        except ValueError as exc:
            if "preserve resolved upstream terminal state" not in str(exc):
                return _fail("mismatched closeout rejection should explain the required upstream terminal state")
        else:
            return _fail("loop_closeout journaling must reject terminal states that contradict upstream failures")
        try:
            mismatch_closeout.record_node_result(
                node_id="loop_closeout",
                state="FAILED",
                reason_code="REVIEW_PASS",
            )
        except ValueError as exc:
            if "reason_code" not in str(exc) and "blocked closeout" not in str(exc):
                return _fail("blocked closeout reason rejection should explain misleading successful reason codes")
        else:
            return _fail("loop_closeout journaling must reject successful review reason codes on blocked runs")
        blocked_closeout.record_node_result(
            node_id="loop_closeout",
            state="FAILED",
            reason_code="VERIFICATION_FAILED",
        )
        blocked_progress_after_closeout = _read_json(Path(blocked_closeout.progress_ref))
        if blocked_progress_after_closeout.get("completed_node_ids") != [
            "execplan",
            "graph_spec",
            "test_node",
            "implement_node",
            "verify_node",
            "loop_closeout",
        ]:
            return _fail("closeout progress should only list journaled maintainer nodes as completed")
        if blocked_progress_after_closeout.get("pending_node_ids") != []:
            return _fail("recording loop_closeout should clear pending maintainer progress")
        if blocked_progress_after_closeout.get("current_node_id") is not None:
            return _fail("recording loop_closeout should clear the current maintainer node")
        blocked_summary = blocked_closeout.close()
        if blocked_summary.get("final_status") != "FAILED":
            return _fail("blocked maintainer closeout must preserve FAILED final_status")
        blocked_ai_review = next(
            (decision for decision in blocked_summary.get("node_decisions", []) if decision.get("node_id") == "ai_review_node"),
            None,
        )
        if blocked_ai_review is None:
            return _fail("blocked maintainer closeout must still emit an ai_review_node decision")
        if blocked_ai_review.get("reason_code") != "UPSTREAM_BLOCKED":
            return _fail("blocked maintainer closeout must synthesize ai_review_node as UPSTREAM_BLOCKED")
        blocked_loop_closeout = next(
            (decision for decision in blocked_summary.get("node_decisions", []) if decision.get("node_id") == "loop_closeout"),
            None,
        )
        if blocked_loop_closeout is None:
            return _fail("blocked maintainer closeout must still emit a loop_closeout decision")
        if blocked_loop_closeout.get("executed") is not True:
            return _fail("blocked maintainer closeout must preserve the journaled loop_closeout as executed")
        if blocked_loop_closeout.get("reason_code") != "VERIFICATION_FAILED":
            return _fail("blocked maintainer closeout must preserve the journaled loop_closeout reason_code")
        closed_blocked_progress = _read_json(Path(blocked_closeout.progress_ref))
        if closed_blocked_progress.get("final_status") != "FAILED":
            return _fail("closed failure-path progress should preserve final_status")
        if closed_blocked_progress.get("pending_node_ids") != []:
            return _fail("closed failure-path progress should not leave pending maintainer nodes")

        blocked_graph_root = Path(blocked_closeout.graph_spec_ref).parent
        blocked_graph_spec = _read_json(Path(blocked_closeout.graph_spec_ref))
        blocked_graph_summary_path = blocked_graph_root / "GraphSummary.jsonl"
        blocked_node_results_path = blocked_graph_root / "NodeResults.json"
        blocked_arbitration_path = blocked_graph_root / "arbitration.jsonl"
        blocked_current_summary_rows = _read_jsonl(blocked_graph_summary_path)
        if len(blocked_current_summary_rows) != 1:
            return _fail("blocked maintainer fixture must persist exactly one GraphSummary row")
        blocked_legacy_summary_row = dict(blocked_current_summary_rows[0])
        blocked_legacy_summary_row["node_decisions"] = [
            (
                {
                    key: value
                    for key, value in dict(decision).items()
                    if key != "run_key"
                }
                | {"executed": False, "reason_code": "UPSTREAM_BLOCKED"}
                if decision.get("node_id") == "loop_closeout"
                else dict(decision)
            )
            for decision in blocked_legacy_summary_row.get("node_decisions") or []
        ]
        blocked_graph_summary_path.write_text(
            json.dumps(blocked_legacy_summary_row, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        blocked_legacy_node_results = _read_json(blocked_node_results_path)
        blocked_legacy_node_results["loop_closeout"] = {
            "state": "FAILED",
            "reason_code": "UPSTREAM_BLOCKED",
        }
        blocked_node_results_path.write_text(
            json.dumps(blocked_legacy_node_results, sort_keys=True),
            encoding="utf-8",
        )

        blocked_legacy_arbitration_rows = []
        for row in _read_jsonl(blocked_arbitration_path):
            mutated = dict(row)
            if mutated.get("target_node_id") == "loop_closeout":
                mutated["winner_rule"] = "ALL_PASS_REQUIRED"
                mutated.pop("bookkeeping_closeout_recorded", None)
                mutated.pop("bookkeeping_reason_code", None)
            blocked_legacy_arbitration_rows.append(mutated)
        blocked_arbitration_path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in blocked_legacy_arbitration_rows),
            encoding="utf-8",
        )

        replay_blocked_legacy = execute_recorded_graph(
            repo_root=repo,
            run_key=blocked_closeout.run_key,
            graph_spec=blocked_graph_spec,
            node_results={
                "execplan": {"state": "PASSED", "reason_code": "EXECPLAN_FROZEN"},
                "graph_spec": {"state": "PASSED", "reason_code": "GRAPH_SPEC_MATERIALIZED"},
                "test_node": {"state": "PASSED", "reason_code": "RED_TESTS_ADDED"},
                "implement_node": {"state": "PASSED", "reason_code": "IMPLEMENTATION_COMPLETE"},
                "verify_node": {"state": "FAILED", "reason_code": "VERIFICATION_FAILED"},
                "loop_closeout": {"state": "FAILED", "reason_code": "VERIFICATION_FAILED"},
            },
        )
        if replay_blocked_legacy.get("summary_ref") != str(blocked_graph_summary_path):
            return _fail("legacy blocked maintainer replay should still reuse the existing GraphSummary ref")
        replayed_blocked_summary_rows = _read_jsonl(blocked_graph_summary_path)
        if len(replayed_blocked_summary_rows) != 1:
            return _fail("legacy blocked maintainer replay should still leave exactly one GraphSummary row")
        replayed_blocked_closeout = next(
            (
                decision
                for decision in replayed_blocked_summary_rows[0].get("node_decisions", [])
                if decision.get("node_id") == "loop_closeout"
            ),
            None,
        )
        if replayed_blocked_closeout is None:
            return _fail("legacy blocked maintainer replay must restore the loop_closeout summary row")
        if replayed_blocked_closeout.get("executed") is not True:
            return _fail("legacy blocked maintainer replay must backfill loop_closeout.executed to true")
        if replayed_blocked_closeout.get("reason_code") != "VERIFICATION_FAILED":
            return _fail("legacy blocked maintainer replay must restore the journaled loop_closeout reason_code")
        replayed_blocked_node_results = _read_json(blocked_node_results_path)
        if replayed_blocked_node_results.get("loop_closeout") != {
            "reason_code": "VERIFICATION_FAILED",
            "state": "FAILED",
        }:
            return _fail("legacy blocked maintainer replay must rewrite NodeResults.json to the journaled loop_closeout result")
        replayed_blocked_arbitration_rows = _read_jsonl(blocked_arbitration_path)
        replayed_blocked_closeout_row = next(
            (row for row in replayed_blocked_arbitration_rows if row.get("target_node_id") == "loop_closeout"),
            None,
        )
        if replayed_blocked_closeout_row is None:
            return _fail("legacy blocked maintainer replay must preserve the loop_closeout arbitration row")
        if replayed_blocked_closeout_row.get("winner_rule") != "BOOKKEEPING_CLOSEOUT_RECORDED":
            return _fail("legacy blocked maintainer replay must restore bookkeeping closeout arbitration winner_rule")
        if replayed_blocked_closeout_row.get("bookkeeping_closeout_recorded") is not True:
            return _fail("legacy blocked maintainer replay must restore bookkeeping closeout arbitration evidence")
        if replayed_blocked_closeout_row.get("bookkeeping_reason_code") != "VERIFICATION_FAILED":
            return _fail("legacy blocked maintainer replay must restore bookkeeping closeout arbitration reason_code")

        graph_summary_path = graph_spec_ref.parent / "GraphSummary.jsonl"
        if not graph_summary_path.exists():
            return _fail("close_maintainer_session must persist GraphSummary.jsonl")
        if len(_read_jsonl(graph_summary_path)) != 1:
            return _fail("GraphSummary.jsonl must contain exactly one appended summary for the session")

    print("[loop-maintainer-session] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
