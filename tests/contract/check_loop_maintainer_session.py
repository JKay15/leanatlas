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
        if graph_spec_ref.name != "GraphSpec.json":
            return _fail("maintainer session graph_spec_ref must point at GraphSpec.json")
        if (graph_spec_ref.parent / "GraphSummary.jsonl").exists():
            return _fail("maintainer session must not create GraphSummary.jsonl before closeout")
        progress_obj = _read_json(progress_ref)
        if progress_obj.get("completed_node_ids") != []:
            return _fail("MaintainerProgress.json must start with no completed nodes")
        if progress_obj.get("pending_node_ids") != session_obj.get("node_order"):
            return _fail("MaintainerProgress.json must expose the pending maintainer sequence")
        if progress_obj.get("current_node_id") != "execplan":
            return _fail("MaintainerProgress.json must point at the next pending node")

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

        loaded_handle = MaintainerLoopSession.load(repo_root=repo, run_key=str(session["run_key"]))
        if loaded_handle.session_ref != str(session_ref):
            return _fail("MaintainerLoopSession.load must resolve the persisted session artifact")

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

        journal = _read_jsonl(node_journal_ref)
        if len(journal) != 1 or journal[0].get("entry_kind") != "SESSION_STARTED":
            return _fail("NodeJournal.jsonl must begin with a SESSION_STARTED entry")

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

        summary = handle.close()
        if summary.get("final_status") != "PASSED":
            return _fail("close_maintainer_session must synthesize a PASSED GraphSummary from journaled results")
        if summary.get("graph_spec_ref") != str(graph_spec_ref):
            return _fail("close_maintainer_session must preserve graph_spec_ref in GraphSummary")

        closed_progress = _read_json(progress_ref)
        if closed_progress.get("final_status") != "PASSED":
            return _fail("MaintainerProgress.json must preserve final_status after closeout")
        if not closed_progress.get("summary_ref"):
            return _fail("MaintainerProgress.json must expose summary_ref after closeout")
        closed_updated_at = closed_progress.get("updated_at_utc")

        reloaded = MaintainerLoopSession.load(repo_root=repo, run_key=str(session["run_key"]))
        if reloaded.progress_ref != str(progress_ref):
            return _fail("MaintainerLoopSession.load must preserve the same progress sidecar path")
        reloaded_progress = _read_json(progress_ref)
        if reloaded_progress.get("final_status") != "PASSED":
            return _fail("reloading a closed session must preserve MaintainerProgress final_status")
        if reloaded_progress.get("summary_ref") != closed_progress.get("summary_ref"):
            return _fail("reloading a closed session must preserve MaintainerProgress summary_ref")
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
        if rematerialized_progress.get("updated_at_utc") != closed_updated_at:
            return _fail("re-materializing a closed session without journal changes must not rewrite updated_at_utc")
        if rematerialized.get("progress_ref") != str(progress_ref):
            return _fail("re-materialized session must still expose the same progress sidecar")

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
        closed_blocked_progress = _read_json(Path(blocked_closeout.progress_ref))
        if closed_blocked_progress.get("final_status") != "FAILED":
            return _fail("closed failure-path progress should preserve final_status")
        if closed_blocked_progress.get("pending_node_ids") != []:
            return _fail("closed failure-path progress should not leave pending maintainer nodes")

        graph_summary_path = graph_spec_ref.parent / "GraphSummary.jsonl"
        if not graph_summary_path.exists():
            return _fail("close_maintainer_session must persist GraphSummary.jsonl")
        if len(_read_jsonl(graph_summary_path)) != 1:
            return _fail("GraphSummary.jsonl must contain exactly one appended summary for the session")

    print("[loop-maintainer-session] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
