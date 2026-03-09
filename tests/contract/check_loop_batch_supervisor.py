#!/usr/bin/env python3
"""Contract: parent supervisor/autopilot must materialize, reroute, and close child waves."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> int:
    print(f"[loop-batch-supervisor][FAIL] {msg}", file=sys.stderr)
    return 2


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def main() -> int:
    try:
        from tools.loop.batch_supervisor import (
            BatchWaveRetryableError,
            execute_batch_supervisor,
            load_batch_supervisor,
            materialize_batch_supervisor,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"missing batch supervisor runtime: {exc}")

    with tempfile.TemporaryDirectory(prefix="loop_batch_supervisor_") as td:
        repo = Path(td) / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        _git(repo, "init")
        _git(repo, "config", "user.email", "loop@example.com")
        _git(repo, "config", "user.name", "Loop Test")
        _write(repo / "AGENTS.md", "# root instructions\n")
        _write(repo / "docs" / "contracts" / "LOOP_WAVE_EXECUTION_CONTRACT.md", "# contract\n")
        _write(repo / "docs" / "agents" / "execplans" / "active_plan.md", "# active plan\n")
        _write(repo / "tools" / "loop" / "target.py", "VALUE = 1\n")
        _write(repo / ".cache" / "leanatlas" / "tmp" / "external" / "note.txt", "note\n")
        _git(repo, "add", "AGENTS.md", "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md", "docs/agents/execplans/active_plan.md", "tools/loop/target.py")
        _git(repo, "commit", "-m", "seed")

        child_waves = [
            {
                "wave_id": "human_ingress",
                "wave_kind": "HUMAN_INGRESS",
                "evidence_refs": [".cache/leanatlas/tmp/external/note.txt"],
                "summary": "user clarification",
            },
            {
                "wave_id": "supervisor_guidance",
                "wave_kind": "SUPERVISOR_GUIDANCE",
                "depends_on": ["human_ingress"],
                "summary": "Known conclusions for the bounded child wave.",
                "reminder_message": "Use the bounded scope only; do not restart broad discovery.",
                "known_conclusion_refs": ["docs/agents/execplans/active_plan.md"],
                "non_goal_refs": ["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
            },
            {
                "wave_id": "capability_publish",
                "wave_kind": "CAPABILITY_PUBLISH",
                "depends_on": ["human_ingress"],
                "resource_refs": ["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
                "summary": "publish review execution capability",
            },
            {
                "wave_id": "context_refresh",
                "wave_kind": "CONTEXT_REMATERIALIZE",
                "depends_on": ["capability_publish", "supervisor_guidance"],
                "base_context_refs": ["docs/agents/execplans/active_plan.md"],
            },
            {
                "wave_id": "worktree_prepare",
                "wave_kind": "WORKTREE_PREP",
                "depends_on": ["context_refresh"],
                "base_ref": "HEAD",
            },
            {
                "wave_id": "review_closeout",
                "wave_kind": "CALLABLE",
                "depends_on": ["context_refresh", "worktree_prepare"],
                "execution_mode": "INLINE",
                "reroute_modes": ["WORKTREE"],
            },
        ]

        session = materialize_batch_supervisor(
            repo_root=repo,
            batch_id="master-plan-completion",
            execplan_ref="docs/agents/execplans/active_plan.md",
            child_waves=child_waves,
            instruction_scope_refs=["AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        progress_ref = Path(str(session["progress_ref"]))
        if not progress_ref.exists():
            return _fail("batch supervisor must persist a progress sidecar before execution begins")
        progress = _read_json(progress_ref)
        if progress.get("pending_wave_ids") != [wave["wave_id"] for wave in child_waves]:
            return _fail("progress sidecar must preserve the pending child-wave order")

        closeout_ref = repo / "artifacts" / "reviews" / "review_closeout.json"
        result_ref = repo / "artifacts" / "reviews" / "review_response.md"
        attempts: list[str] = []

        def _review_executor(wave: dict[str, object]) -> dict[str, object]:
            attempts.append(str(wave["execution_mode"]))
            if str(wave["execution_mode"]) == "INLINE":
                raise BatchWaveRetryableError(
                    "needs isolated workspace",
                    reroute_to="WORKTREE",
                    reason_code="REROUTE_WORKTREE",
                )
            _write(result_ref, "No findings.\n")
            _write(closeout_ref, "{\"final_status\": \"PASSED\"}\n")
            return {
                "result_refs": [result_ref.relative_to(repo).as_posix()],
                "closeout_ref": closeout_ref.relative_to(repo).as_posix(),
            }

        result = execute_batch_supervisor(
            repo_root=repo,
            run_key=str(session["run_key"]),
            wave_executors={"review_closeout": _review_executor},
        )
        if result["final_status"] != "PASSED":
            return _fail("batch supervisor integrated closeout must report PASSED for successful child waves")
        if attempts != ["INLINE", "WORKTREE"]:
            return _fail("supervisor must reroute retryable child waves when policy allows")

        loaded = load_batch_supervisor(repo_root=repo, run_key=str(session["run_key"]))
        if loaded["progress"]["completed_wave_ids"] != [
            "human_ingress",
            "supervisor_guidance",
            "capability_publish",
            "context_refresh",
            "worktree_prepare",
            "review_closeout",
        ]:
            return _fail("supervisor progress must preserve completed child-wave order")
        child_state = loaded["child_waves"]["review_closeout"]
        if child_state.get("execution_mode") != "WORKTREE":
            return _fail("rerouted child wave must preserve the selected WORKTREE execution mode")
        if int(child_state.get("attempt_count") or 0) != 2:
            return _fail("rerouted child wave must record both attempts")

        journal = _read_jsonl(Path(str(loaded["journal_ref"])))
        if not any(entry.get("entry_kind") == "CHILD_WAVE_REROUTED" for entry in journal):
            return _fail("supervisor journal must record reroute decisions")

        integrated_closeout = _read_json(Path(str(result["closeout_ref"])))
        if integrated_closeout.get("publication_wave_ids") != ["capability_publish"]:
            return _fail("integrated closeout must preserve publication-wave lineage")
        if integrated_closeout.get("supervisor_guidance_wave_ids") != ["supervisor_guidance"]:
            return _fail("integrated closeout must preserve supervisor-guidance lineage")
        if integrated_closeout.get("context_wave_ids") != ["context_refresh"]:
            return _fail("integrated closeout must preserve rematerialized context lineage")
        if integrated_closeout.get("worktree_wave_ids") != ["worktree_prepare"]:
            return _fail("integrated closeout must preserve worktree lineage")
        if integrated_closeout.get("authoritative_child_wave_id") != "review_closeout":
            return _fail("integrated closeout must point at the authoritative terminal child wave")
        if integrated_closeout.get("authoritative_closeout_ref") != closeout_ref.relative_to(repo).as_posix():
            return _fail("integrated closeout must preserve the child-wave closeout ref")
        rematerialized = materialize_batch_supervisor(
            repo_root=repo,
            batch_id="master-plan-completion",
            execplan_ref="docs/agents/execplans/active_plan.md",
            child_waves=child_waves,
            instruction_scope_refs=["AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        if str(rematerialized["run_key"]) != str(session["run_key"]):
            return _fail("identical batch-supervisor inputs must rematerialize to the same run_key")
        rematerialized_loaded = load_batch_supervisor(repo_root=repo, run_key=str(rematerialized["run_key"]))
        if rematerialized_loaded["progress"]["completed_wave_ids"] != [
            "human_ingress",
            "supervisor_guidance",
            "capability_publish",
            "context_refresh",
            "worktree_prepare",
            "review_closeout",
        ]:
            return _fail("rematerializing an existing batch must preserve completed-wave progress")
        if int(rematerialized_loaded["child_waves"]["review_closeout"].get("attempt_count") or 0) != 2:
            return _fail("rematerializing an existing batch must preserve child attempt counts")
        rematerialized_journal = _read_jsonl(Path(str(rematerialized_loaded["journal_ref"])))
        if sum(1 for entry in rematerialized_journal if entry.get("entry_kind") == "BATCH_SUPERVISOR_STARTED") != 1:
            return _fail("rematerializing an existing batch must not append a duplicate started journal entry")

        blocked_session = materialize_batch_supervisor(
            repo_root=repo,
            batch_id="master-plan-blocked",
            execplan_ref="docs/agents/execplans/active_plan.md",
            child_waves=[
                {
                    "wave_id": "failing_wave",
                    "wave_kind": "CALLABLE",
                    "execution_mode": "INLINE",
                },
                {
                    "wave_id": "blocked_wave",
                    "wave_kind": "CALLABLE",
                    "depends_on": ["failing_wave"],
                    "execution_mode": "INLINE",
                },
            ],
            instruction_scope_refs=["AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )

        def _failing_executor(_wave: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("boom")

        blocked_result = execute_batch_supervisor(
            repo_root=repo,
            run_key=str(blocked_session["run_key"]),
            wave_executors={"failing_wave": _failing_executor},
        )
        if blocked_result["final_status"] != "TRIAGED":
            return _fail("batch supervisor integrated closeout must preserve TRIAGED when downstream waves are blocked")
        blocked_closeout = _read_json(Path(str(blocked_result["closeout_ref"])))
        if blocked_closeout.get("final_status") != "TRIAGED":
            return _fail("integrated closeout artifact must preserve TRIAGED batch status")
        if blocked_closeout.get("child_results", {}).get("blocked_wave", {}).get("status") != "TRIAGED":
            return _fail("blocked child waves must remain TRIAGED in the integrated closeout artifact")

        xhigh_session = materialize_batch_supervisor(
            repo_root=repo,
            batch_id="xhigh-executor-supervision",
            execplan_ref="docs/agents/execplans/active_plan.md",
            child_waves=[
                {
                    "wave_id": "initial_guidance",
                    "wave_kind": "SUPERVISOR_GUIDANCE",
                    "summary": "Known conclusions for the xhigh execution lane.",
                    "reminder_message": "Bounded repair only.",
                    "known_conclusion_refs": ["docs/agents/execplans/active_plan.md"],
                    "non_goal_refs": ["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
                },
                {
                    "wave_id": "xhigh_context_refresh",
                    "wave_kind": "CONTEXT_REMATERIALIZE",
                    "depends_on": ["initial_guidance"],
                    "base_context_refs": ["docs/agents/execplans/active_plan.md"],
                },
                {
                    "wave_id": "implementation_xhigh",
                    "wave_kind": "CALLABLE",
                    "depends_on": ["xhigh_context_refresh"],
                    "execution_mode": "INLINE",
                    "supervision_policy": {
                        "executor_reasoning_effort": "xhigh",
                        "max_no_milestone_retries": 1,
                        "followup_base_context_refs": ["docs/agents/execplans/active_plan.md"],
                    },
                },
            ],
            instruction_scope_refs=["AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )

        xhigh_attempts: list[tuple[int, dict[str, object]]] = []
        xhigh_closeout_ref = repo / "artifacts" / "reviews" / "implementation_xhigh_closeout.json"
        xhigh_result_ref = repo / "artifacts" / "reviews" / "implementation_xhigh_response.md"

        def _implementation_xhigh_executor(wave: dict[str, object]) -> dict[str, object]:
            attempt_index = len(xhigh_attempts) + 1
            xhigh_attempts.append((attempt_index, dict(wave)))
            if attempt_index == 1:
                raise BatchWaveRetryableError(
                    "initial xhigh context rebuild is still in progress",
                    reason_code="CONTEXT_REBUILD",
                    retry_same_mode=True,
                    progress_class="CONTEXT_REBUILD",
                )
            if attempt_index == 2:
                raise BatchWaveRetryableError(
                    "no milestone progress yet",
                    reason_code="NO_MILESTONE_PROGRESS",
                    retry_same_mode=True,
                    progress_class="NO_MILESTONE_PROGRESS",
                    reminder_summary="Bounded reminder for xhigh executor",
                    reminder_message="Known conclusions/non-goals are now explicit; stop broad discovery and move into tests or patch work.",
                    known_conclusion_refs=["docs/agents/execplans/active_plan.md"],
                    non_goal_refs=["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
                )
            if attempt_index == 3:
                upstream = dict(wave.get("upstream_results") or {})
                if len(list(upstream.get("supervisor_guidance_event_refs") or [])) < 2:
                    raise AssertionError("follow-up retry must expose both initial and reminder supervisor guidance refs")
                if len(list(upstream.get("context_pack_refs") or [])) < 2:
                    raise AssertionError("follow-up retry must expose a rematerialized context pack after reminder publication")
                _write(xhigh_result_ref, "Bounded implementation completed.\n")
                _write(xhigh_closeout_ref, "{\"final_status\": \"PASSED\"}\n")
                return {
                    "result_refs": [xhigh_result_ref.relative_to(repo).as_posix()],
                    "closeout_ref": xhigh_closeout_ref.relative_to(repo).as_posix(),
                }
            raise AssertionError("implementation_xhigh should not need more than three attempts")

        xhigh_result = execute_batch_supervisor(
            repo_root=repo,
            run_key=str(xhigh_session["run_key"]),
            wave_executors={"implementation_xhigh": _implementation_xhigh_executor},
        )
        if xhigh_result["final_status"] != "PASSED":
            return _fail("xhigh executor supervision must remain retryable through reminder-first follow-up")
        xhigh_loaded = load_batch_supervisor(repo_root=repo, run_key=str(xhigh_session["run_key"]))
        xhigh_child = xhigh_loaded["child_waves"]["implementation_xhigh"]
        if int(xhigh_child.get("attempt_count") or 0) != 3:
            return _fail("xhigh executor supervision must preserve all bounded retry attempts")
        if list(xhigh_child.get("supervisor_guidance_refs") or []) == []:
            return _fail("xhigh executor child state must preserve published supervisor guidance refs")
        xhigh_journal = _read_jsonl(Path(str(xhigh_loaded["journal_ref"])))
        if not any(entry.get("entry_kind") == "CHILD_WAVE_CONTEXT_REBUILD_CONTINUED" for entry in xhigh_journal):
            return _fail("xhigh executor supervision must record allowed early context rebuild retries")
        if not any(entry.get("entry_kind") == "CHILD_WAVE_REMINDER_REQUESTED" for entry in xhigh_journal):
            return _fail("xhigh executor supervision must publish a reminder before triageing repeated no-milestone drift")

        exhausted_session = materialize_batch_supervisor(
            repo_root=repo,
            batch_id="xhigh-executor-supervision-exhausted",
            execplan_ref="docs/agents/execplans/active_plan.md",
            child_waves=[
                {
                    "wave_id": "seed_guidance",
                    "wave_kind": "SUPERVISOR_GUIDANCE",
                    "summary": "Known conclusions for the exhausted xhigh child.",
                    "reminder_message": "Bounded repair only.",
                    "known_conclusion_refs": ["docs/agents/execplans/active_plan.md"],
                    "non_goal_refs": ["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
                },
                {
                    "wave_id": "seed_context_refresh",
                    "wave_kind": "CONTEXT_REMATERIALIZE",
                    "depends_on": ["seed_guidance"],
                    "base_context_refs": ["docs/agents/execplans/active_plan.md"],
                },
                {
                    "wave_id": "implementation_xhigh_stalled",
                    "wave_kind": "CALLABLE",
                    "depends_on": ["seed_context_refresh"],
                    "execution_mode": "INLINE",
                    "supervision_policy": {
                        "executor_reasoning_effort": "xhigh",
                        "allow_context_rebuild_retries": 0,
                        "max_no_milestone_retries": 1,
                        "followup_base_context_refs": ["docs/agents/execplans/active_plan.md"],
                    },
                },
            ],
            instruction_scope_refs=["AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )

        stalled_calls = 0

        def _stalled_executor(_wave: dict[str, object]) -> dict[str, object]:
            nonlocal stalled_calls
            stalled_calls += 1
            raise BatchWaveRetryableError(
                "still no milestone progress",
                reason_code="NO_MILESTONE_PROGRESS",
                retry_same_mode=True,
                progress_class="NO_MILESTONE_PROGRESS",
                reminder_summary="Reminder for still-stalled child",
                reminder_message="This is the final bounded reminder before triage.",
                known_conclusion_refs=["docs/agents/execplans/active_plan.md"],
                non_goal_refs=["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
            )

        exhausted_result = execute_batch_supervisor(
            repo_root=repo,
            run_key=str(exhausted_session["run_key"]),
            wave_executors={"implementation_xhigh_stalled": _stalled_executor},
        )
        if exhausted_result["final_status"] != "TRIAGED":
            return _fail("repeated no-milestone drift must eventually triage after bounded reminder-first retries")
        exhausted_closeout = _read_json(Path(str(exhausted_result["closeout_ref"])))
        if exhausted_closeout.get("child_results", {}).get("implementation_xhigh_stalled", {}).get("status") != "TRIAGED":
            return _fail("bounded no-milestone exhaustion must leave the child wave TRIAGED")
        if stalled_calls != 2:
            return _fail("bounded reminder-first retries must attempt the stalled child exactly once after reminder publication")

        default_context_budget_session = materialize_batch_supervisor(
            repo_root=repo,
            batch_id="non-xhigh-context-rebuild-default",
            execplan_ref="docs/agents/execplans/active_plan.md",
            child_waves=[
                {
                    "wave_id": "implementation_default_context_rebuild",
                    "wave_kind": "CALLABLE",
                    "execution_mode": "INLINE",
                }
            ],
            instruction_scope_refs=["AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )

        default_context_calls = 0

        def _default_context_executor(_wave: dict[str, object]) -> dict[str, object]:
            nonlocal default_context_calls
            default_context_calls += 1
            raise BatchWaveRetryableError(
                "non-xhigh child is still rebuilding context",
                reason_code="CONTEXT_REBUILD",
                retry_same_mode=True,
                progress_class="CONTEXT_REBUILD",
            )

        default_context_result = execute_batch_supervisor(
            repo_root=repo,
            run_key=str(default_context_budget_session["run_key"]),
            wave_executors={"implementation_default_context_rebuild": _default_context_executor},
        )
        if default_context_result["final_status"] != "TRIAGED":
            return _fail("non-xhigh child waves must not receive an implicit CONTEXT_REBUILD retry budget")
        if default_context_calls != 1:
            return _fail("non-xhigh child waves must triage on the first retryable CONTEXT_REBUILD attempt by default")
        default_context_loaded = load_batch_supervisor(
            repo_root=repo,
            run_key=str(default_context_budget_session["run_key"]),
        )
        default_context_journal = _read_jsonl(Path(str(default_context_loaded["journal_ref"])))
        if any(entry.get("entry_kind") == "CHILD_WAVE_CONTEXT_REBUILD_CONTINUED" for entry in default_context_journal):
            return _fail("non-xhigh child waves must not journal implicit CONTEXT_REBUILD retries")

        zero_context_budget_session = materialize_batch_supervisor(
            repo_root=repo,
            batch_id="xhigh-context-rebuild-budget-zero",
            execplan_ref="docs/agents/execplans/active_plan.md",
            child_waves=[
                {
                    "wave_id": "implementation_xhigh_context_rebuild",
                    "wave_kind": "CALLABLE",
                    "execution_mode": "INLINE",
                    "supervision_policy": {
                        "executor_reasoning_effort": "xhigh",
                        "allow_context_rebuild_retries": 0,
                    },
                }
            ],
            instruction_scope_refs=["AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )

        context_rebuild_calls = 0

        def _context_rebuild_executor(_wave: dict[str, object]) -> dict[str, object]:
            nonlocal context_rebuild_calls
            context_rebuild_calls += 1
            raise BatchWaveRetryableError(
                "still rebuilding context",
                reason_code="CONTEXT_REBUILD",
                retry_same_mode=True,
                progress_class="CONTEXT_REBUILD",
            )

        zero_context_budget_result = execute_batch_supervisor(
            repo_root=repo,
            run_key=str(zero_context_budget_session["run_key"]),
            wave_executors={"implementation_xhigh_context_rebuild": _context_rebuild_executor},
        )
        if zero_context_budget_result["final_status"] != "TRIAGED":
            return _fail("explicit allow_context_rebuild_retries=0 must triage on the first retryable context-rebuild attempt")
        if context_rebuild_calls != 1:
            return _fail("explicit allow_context_rebuild_retries=0 must not silently grant an extra context-rebuild retry")
        zero_context_budget_loaded = load_batch_supervisor(
            repo_root=repo,
            run_key=str(zero_context_budget_session["run_key"]),
        )
        zero_context_journal = _read_jsonl(Path(str(zero_context_budget_loaded["journal_ref"])))
        if any(entry.get("entry_kind") == "CHILD_WAVE_CONTEXT_REBUILD_CONTINUED" for entry in zero_context_journal):
            return _fail("explicit allow_context_rebuild_retries=0 must not journal a continued context-rebuild retry")
        if not any(
            entry.get("entry_kind") == "CHILD_WAVE_TRIAGED"
            and entry.get("reason_code") == "CONTEXT_REBUILD_BUDGET_EXHAUSTED"
            for entry in zero_context_journal
        ):
            return _fail("explicit allow_context_rebuild_retries=0 must triage with CONTEXT_REBUILD_BUDGET_EXHAUSTED")

        interrupted_resume_session = materialize_batch_supervisor(
            repo_root=repo,
            batch_id="batch-supervisor-resume-after-running",
            execplan_ref="docs/agents/execplans/active_plan.md",
            child_waves=[
                {
                    "wave_id": "resume_target",
                    "wave_kind": "CALLABLE",
                    "execution_mode": "INLINE",
                }
            ],
            instruction_scope_refs=["AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        interrupted_state_path = Path(str(interrupted_resume_session["state_ref"]))
        interrupted_state = _read_json(interrupted_state_path)
        interrupted_state["child_waves"][0]["status"] = "RUNNING"
        interrupted_state["child_waves"][0]["attempt_count"] = 1
        interrupted_state["child_waves"][0]["result_refs"] = []
        _write(interrupted_state_path, json.dumps(interrupted_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        interrupted_journal_path = Path(str(interrupted_resume_session["journal_ref"]))
        with interrupted_journal_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "entry_kind": "CHILD_WAVE_STARTED",
                        "at_utc": "2026-03-09T00:00:00Z",
                        "wave_id": "resume_target",
                        "execution_mode": "INLINE",
                        "attempt_count": 1,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )

        resumed_closeout_ref = repo / "artifacts" / "reviews" / "resume_target_closeout.json"
        resumed_result_ref = repo / "artifacts" / "reviews" / "resume_target_response.md"
        resumed_calls = 0

        def _resume_target_executor(wave: dict[str, object]) -> dict[str, object]:
            nonlocal resumed_calls
            resumed_calls += 1
            if int(wave.get("attempt_count") or 0) != 2:
                raise AssertionError("resumed child wave must restart with the next attempt_count")
            _write(resumed_result_ref, "Resumed child completed.\n")
            _write(resumed_closeout_ref, "{\"final_status\": \"PASSED\"}\n")
            return {
                "result_refs": [resumed_result_ref.relative_to(repo).as_posix()],
                "closeout_ref": resumed_closeout_ref.relative_to(repo).as_posix(),
            }

        resumed_result = execute_batch_supervisor(
            repo_root=repo,
            run_key=str(interrupted_resume_session["run_key"]),
            wave_executors={"resume_target": _resume_target_executor},
        )
        if resumed_result["final_status"] != "PASSED":
            return _fail("interrupted RUNNING child waves must be resumable on the same batch run_key")
        if resumed_calls != 1:
            return _fail("resumed RUNNING child waves must be requeued once and retried exactly once")
        resumed_loaded = load_batch_supervisor(
            repo_root=repo,
            run_key=str(interrupted_resume_session["run_key"]),
        )
        resumed_child = resumed_loaded["child_waves"]["resume_target"]
        if resumed_child.get("status") != "PASSED":
            return _fail("resumed RUNNING child wave must reach PASSED after the retried executor succeeds")
        if int(resumed_child.get("attempt_count") or 0) != 2:
            return _fail("resumed RUNNING child wave must preserve the interrupted attempt and the retried attempt")
        resumed_journal = _read_jsonl(Path(str(resumed_loaded["journal_ref"])))
        if not any(
            entry.get("entry_kind") == "CHILD_WAVE_REQUEUED"
            and entry.get("reason_code") == "INTERRUPTED_RUNNING_STATE"
            for entry in resumed_journal
        ):
            return _fail("resuming an interrupted RUNNING child wave must record an explicit requeue journal event")

        missing_callable_session = materialize_batch_supervisor(
            repo_root=repo,
            batch_id="missing-callable-artifacts",
            execplan_ref="docs/agents/execplans/active_plan.md",
            child_waves=[
                {
                    "wave_id": "missing_callable",
                    "wave_kind": "CALLABLE",
                    "execution_mode": "INLINE",
                }
            ],
            instruction_scope_refs=["AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )

        def _missing_callable_executor(_wave: dict[str, object]) -> dict[str, object]:
            return {
                "result_refs": ["artifacts/reviews/missing_response.md"],
                "closeout_ref": "artifacts/reviews/missing_closeout.json",
            }

        missing_callable_result = execute_batch_supervisor(
            repo_root=repo,
            run_key=str(missing_callable_session["run_key"]),
            wave_executors={"missing_callable": _missing_callable_executor},
        )
        if missing_callable_result["final_status"] != "TRIAGED":
            return _fail("callable child waves with missing artifact refs must not close out as PASSED")
        missing_callable_closeout = _read_json(Path(str(missing_callable_result["closeout_ref"])))
        callable_child = missing_callable_closeout.get("child_results", {}).get("missing_callable", {})
        if callable_child.get("status") != "TRIAGED":
            return _fail("callable child waves with missing artifact refs must remain TRIAGED in integrated closeout")

        missing_external_session = materialize_batch_supervisor(
            repo_root=repo,
            batch_id="missing-external-closeout-artifact",
            execplan_ref="docs/agents/execplans/active_plan.md",
            child_waves=[
                {
                    "wave_id": "external_closeout",
                    "wave_kind": "EXTERNAL_CLOSEOUT",
                    "closeout_ref": "artifacts/reviews/missing_external_closeout.json",
                }
            ],
            instruction_scope_refs=["AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        missing_external_result = execute_batch_supervisor(
            repo_root=repo,
            run_key=str(missing_external_session["run_key"]),
        )
        if missing_external_result["final_status"] != "TRIAGED":
            return _fail("external closeout waves with missing authoritative artifacts must not close out as PASSED")
        missing_external_closeout = _read_json(Path(str(missing_external_result["closeout_ref"])))
        external_child = missing_external_closeout.get("child_results", {}).get("external_closeout", {})
        if external_child.get("status") != "TRIAGED":
            return _fail("external closeout waves with missing authoritative artifacts must remain TRIAGED in integrated closeout")

        print("[loop-batch-supervisor] OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
