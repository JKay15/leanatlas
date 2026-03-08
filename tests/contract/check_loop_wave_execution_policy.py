#!/usr/bin/env python3
"""Contract check: Wave execution meta-loop strict review/exit policy."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

try:
    import jsonschema
except Exception:
    print("[loop-wave-exec-policy] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "contracts" / "LOOP_WAVE_EXECUTION_CONTRACT.md"
SCHEMA = ROOT / "docs" / "schemas" / "WaveExecutionLoopRun.schema.json"

EXEC_ALLOWED = {
    ("PENDING", "RUNNING"),
    ("RUNNING", "AI_REVIEW"),
    ("AI_REVIEW", "RUNNING"),
    ("AI_REVIEW", "PASSED"),
    ("AI_REVIEW", "FAILED"),
    ("AI_REVIEW", "TRIAGED"),
}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _transition_from_review(
    *,
    verdict: str,
    retry_used: int,
    retry_max: int,
    repeated_fingerprint_count: int,
    max_same_fingerprint_rounds: int,
    wall_clock_used_minutes: int,
    wall_clock_max_minutes: int,
) -> tuple[str, str]:
    if repeated_fingerprint_count >= max_same_fingerprint_rounds:
        return ("TRIAGED", "REVIEW_STAGNATION")
    if verdict == "NON_RETRYABLE":
        return ("FAILED", "REVIEW_NON_RETRYABLE_FAULT")
    if verdict == "UNRESOLVED_BLOCKER":
        return ("TRIAGED", "REVIEW_UNRESOLVED_BLOCKER")
    if wall_clock_used_minutes >= wall_clock_max_minutes:
        return ("TRIAGED", "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED")
    if verdict == "REPAIRABLE":
        if retry_used < retry_max:
            return ("RUNNING", "REVIEW_REPAIR_LOOP")
        return ("TRIAGED", "REVIEW_BUDGET_EXHAUSTED")
    if verdict == "PASS":
        return ("PASSED", "REVIEW_PASS")
    return ("FAILED", "REVIEW_INVALID_VERDICT")


def _base_instance() -> dict:
    return {
        "version": "1",
        "wave_id": "loop.wave_a.execution.v0",
        "run_key": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "assurance_level": "STRICT",
        "budgets": {
            "max_ai_review_rounds": 8,
            "max_same_fingerprint_rounds": 2,
            "max_wave_wall_clock_minutes": 120,
            "used_ai_review_rounds": 1,
            "used_wall_clock_minutes": 8,
        },
        "agent_invocation": {
            "agent_provider_id": "codex_cli",
            "agent_profile": "profiles/codex_review.json",
            "resolved_invocation": ["codex", "exec", "review"],
            "instruction_scope_refs": [
                "/Users/xiongjiangkai/xjk_papers/leanatlas/AGENTS.md",
                "/Users/xiongjiangkai/xjk_papers/leanatlas/tools/AGENTS.md",
            ],
        },
        "derived_metrics": {
            "max_consecutive_same_fingerprint": 1,
            "replay_digest": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        },
        "dirty_tree": {
            "checked": True,
            "in_git_repo": True,
            "is_clean": True,
            "disposition": "CLEAN",
            "head_commit": "1111111111111111111111111111111111111111",
            "tracked_entry_count": 0,
            "untracked_entry_count": 0,
            "changed_entry_count": 0,
            "status_porcelain_sample": [],
        },
        "review_history_consistency": {
            "contradiction_count": 0,
            "potential_nitpick_count": 0,
            "contradiction_refs": [],
            "nitpick_refs": [],
        },
        "execution": {
            "current_state": "PASSED",
            "transitions": [
                {
                    "from": "PENDING",
                    "to": "RUNNING",
                    "reason_code": "WAVE_START",
                    "at_utc": "2026-03-05T00:00:00Z",
                },
                {
                    "from": "RUNNING",
                    "to": "AI_REVIEW",
                    "reason_code": "IMPLEMENTATION_SUBMITTED_FOR_REVIEW",
                    "at_utc": "2026-03-05T00:01:00Z",
                },
                {
                    "from": "AI_REVIEW",
                    "to": "PASSED",
                    "reason_code": "REVIEW_PASS",
                    "at_utc": "2026-03-05T00:02:00Z",
                },
            ],
        },
        "iterations": [
            {
                "iteration_index": 1,
                "ai_review": {
                    "engine": "codex exec review",
                    "prompt_ref": "artifacts/waveA/review_prompt_round1.md",
                    "response_ref": "artifacts/waveA/review_response_round1.md",
                    "verdict": "PASS",
                    "confidence": 0.94,
                    "finding_fingerprint": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "findings": [
                        {
                            "finding_id": "finding.waveA.round1.001",
                            "severity": "S3_MINOR",
                            "repairable": False,
                            "summary": "No blocking issue remains.",
                            "evidence_refs": [
                                "artifacts/waveA/diff_round1.patch",
                            ],
                        }
                    ],
                },
                "transition": {
                    "from": "AI_REVIEW",
                    "to": "PASSED",
                    "reason_code": "REVIEW_PASS",
                    "at_utc": "2026-03-05T00:02:00Z",
                },
                "history_context_refs": [
                    "artifacts/waveA/review_history_until_round0.json",
                ],
                "wall_clock_used_minutes": 8,
            }
        ],
        "final_decision": {
            "state": "PASSED",
            "reason_code": "REVIEW_PASS",
            "at_utc": "2026-03-05T00:02:00Z",
        },
        "evidence": {
            "ai_review_log_path": "artifacts/loop_runtime/by_key/aaa/wave_execution/ai_review.jsonl",
            "ai_review_prompt_ref": "artifacts/waveA/review_prompt_round1.md",
            "ai_review_response_ref": "artifacts/waveA/review_response_round1.md",
            "ai_review_summary_ref": "artifacts/waveA/review_summary_round1.json",
            "iteration_trace_path": "artifacts/loop_runtime/by_key/aaa/wave_execution/iteration_trace.json",
            "final_decision_path": "artifacts/loop_runtime/by_key/aaa/wave_execution/final_decision.json",
        },
    }


def _schema_errors(schema: dict, inst: dict) -> list:
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
    )
    return sorted(validator.iter_errors(inst), key=lambda e: list(e.absolute_path))


def _max_consecutive_fingerprint(iterations: list[dict]) -> int:
    last = None
    run = 0
    best = 0
    for rec in iterations:
        fp = rec["ai_review"]["finding_fingerprint"]
        if fp == last:
            run += 1
        else:
            run = 1
            last = fp
        best = max(best, run)
    return best


def _replay_iteration_transitions(inst: dict) -> list[tuple[str, str]]:
    budgets = inst["budgets"]
    out: list[tuple[str, str]] = []
    last = None
    run = 0
    for idx, rec in enumerate(inst["iterations"]):
        fp = rec["ai_review"]["finding_fingerprint"]
        if fp == last:
            run += 1
        else:
            run = 1
            last = fp
        out.append(
            _transition_from_review(
                verdict=rec["ai_review"]["verdict"],
                retry_used=idx + 1,
                retry_max=budgets["max_ai_review_rounds"],
                repeated_fingerprint_count=run,
                max_same_fingerprint_rounds=budgets["max_same_fingerprint_rounds"],
                wall_clock_used_minutes=rec["wall_clock_used_minutes"],
                wall_clock_max_minutes=budgets["max_wave_wall_clock_minutes"],
            )
        )
    return out


def _validate_trace_consistency(inst: dict) -> bool:
    transitions = inst["execution"]["transitions"]
    if not transitions:
        return False
    first = transitions[0]
    if (first["from"], first["to"], first["reason_code"]) != ("PENDING", "RUNNING", "WAVE_START"):
        return False
    for i in range(len(transitions) - 1):
        if transitions[i]["to"] != transitions[i + 1]["from"]:
            return False

    ai_review_edges = [t for t in transitions if t["from"] == "AI_REVIEW"]
    if len(ai_review_edges) != len(inst["iterations"]):
        return False
    for edge, rec in zip(ai_review_edges, inst["iterations"]):
        if (
            edge["to"] != rec["transition"]["to"]
            or edge["reason_code"] != rec["transition"]["reason_code"]
        ):
            return False

    last = transitions[-1]
    if (
        last["to"] != inst["final_decision"]["state"]
        or last["reason_code"] != inst["final_decision"]["reason_code"]
    ):
        return False
    if inst["execution"]["current_state"] != inst["final_decision"]["state"]:
        return False
    return True


def _validate_iteration_indexing(inst: dict) -> bool:
    expected = 1
    for rec in inst["iterations"]:
        if rec["iteration_index"] != expected:
            return False
        expected += 1
    return True


def _validate_budget_consistency(inst: dict) -> bool:
    budgets = inst["budgets"]
    iterations = inst["iterations"]

    used_rounds = budgets["used_ai_review_rounds"]
    max_rounds = budgets["max_ai_review_rounds"]
    if used_rounds != len(iterations) or used_rounds > max_rounds:
        return False

    max_wall = budgets["max_wave_wall_clock_minutes"]
    used_wall = budgets["used_wall_clock_minutes"]
    if used_wall > max_wall:
        return False

    wall_values = [rec["wall_clock_used_minutes"] for rec in iterations]
    if any(v > max_wall for v in wall_values):
        return False
    if wall_values != sorted(wall_values):
        return False
    if wall_values and wall_values[-1] != used_wall:
        return False
    return True


def _validate_agent_invocation(inst: dict) -> bool:
    inv = inst["agent_invocation"]
    resolved = inv["resolved_invocation"]
    if not resolved or not all(isinstance(x, str) and x.strip() for x in resolved):
        return False
    if len(inv["instruction_scope_refs"]) < 1:
        return False
    if not any(ref.endswith("AGENTS.md") for ref in inv["instruction_scope_refs"]):
        return False
    expected_prefix = {
        "codex_cli": ["codex", "exec"],
        "claude_code": ["claude", "exec"],
    }
    provider = inv["agent_provider_id"]
    if provider in expected_prefix and resolved[:2] != expected_prefix[provider]:
        return False
    return True


def _validate_review_history_consistency(inst: dict) -> bool:
    summary = inst["review_history_consistency"]
    if summary["contradiction_count"] < len(summary["contradiction_refs"]):
        return False
    if summary["potential_nitpick_count"] < len(summary["nitpick_refs"]):
        return False
    refs = summary["contradiction_refs"] + summary["nitpick_refs"]
    if any((not isinstance(ref, str)) or (not ref.strip()) for ref in refs):
        return False
    return True


def _validate_history_ref_propagation(inst: dict) -> bool:
    summary = inst["review_history_consistency"]
    refs = set(summary["contradiction_refs"]) | set(summary["nitpick_refs"])
    if not refs:
        return True
    iterations = inst["iterations"]
    if len(iterations) <= 1:
        return False
    propagated: set[str] = set()
    for rec in iterations[1:]:
        propagated.update(rec["history_context_refs"])
    return refs.issubset(propagated)


def _validate_review_closure(inst: dict) -> bool:
    iterations = inst["iterations"]
    expected = list(range(1, len(iterations) + 1))
    actual = [int(rec["iteration_index"]) for rec in iterations]
    if actual != expected:
        return False

    seen_prompts: set[str] = set()
    seen_responses: set[str] = set()
    for rec in iterations:
        prompt_ref = str(rec["ai_review"]["prompt_ref"])
        response_ref = str(rec["ai_review"]["response_ref"])
        if prompt_ref in seen_prompts or response_ref in seen_responses:
            return False
        seen_prompts.add(prompt_ref)
        seen_responses.add(response_ref)

    for i, rec in enumerate(iterations):
        tr = rec["transition"]
        if tr["to"] == "RUNNING" and tr["reason_code"] == "REVIEW_REPAIR_LOOP":
            if i + 1 >= len(iterations):
                return False
            next_ai = iterations[i + 1]["ai_review"]
            cur_ai = rec["ai_review"]
            if (
                cur_ai["prompt_ref"] == next_ai["prompt_ref"]
                or cur_ai["response_ref"] == next_ai["response_ref"]
            ):
                return False
    return True


def _validate_dirty_tree(inst: dict) -> bool:
    dt = inst.get("dirty_tree")
    if not isinstance(dt, dict):
        return False
    for key in (
        "checked",
        "in_git_repo",
        "is_clean",
        "disposition",
        "head_commit",
        "tracked_entry_count",
        "untracked_entry_count",
        "changed_entry_count",
        "status_porcelain_sample",
    ):
        if key not in dt:
            return False
    if dt["checked"] is not True:
        return False
    if dt["in_git_repo"] is True:
        if dt["is_clean"] is not True:
            return False
        if dt["disposition"] not in {"CLEAN", "COMMITTED", "IGNORED_ONLY"}:
            return False
    else:
        if dt["disposition"] != "NO_GIT_CONTEXT":
            return False
        if dt["is_clean"] is not True:
            return False
        if dt["head_commit"] is not None:
            return False
        if (dt["tracked_entry_count"], dt["untracked_entry_count"], dt["changed_entry_count"]) != (0, 0, 0):
            return False
        if dt["status_porcelain_sample"] != []:
            return False
    return True


def main() -> int:
    _assert(CONTRACT.exists(), f"missing contract: {CONTRACT.relative_to(ROOT)}")
    _assert(SCHEMA.exists(), f"missing schema: {SCHEMA.relative_to(ROOT)}")

    txt = CONTRACT.read_text(encoding="utf-8")
    required_patterns = [
        r"Assurance level policy \(FAST/LIGHT/STRICT\)",
        r"STRICT completion gate",
        r"ai_review_prompt_ref",
        r"ai_review_response_ref",
        r"ai_review_summary_ref",
        r"AI_REVIEW verdict enum:\s*`PASS \| REPAIRABLE \| UNRESOLVED_BLOCKER \| NON_RETRYABLE`",
        r"REPAIRABLE and retry budget remains -> RUNNING",
        r"REPAIRABLE and retry budget exhausted -> TRIAGED .*REVIEW_BUDGET_EXHAUSTED",
        r"same finding_fingerprint repeats >= 2 -> TRIAGED .*REVIEW_STAGNATION",
        r"while state is non-terminal, the loop must continue",
        r"HUMAN_REVIEW.*MUST NOT block the execution track",
        r"DirtyTreeGate",
        r"dirty_tree",
        r"PASSED.*worktree.*clean",
        r"agent_provider_id",
        r"resolved_invocation",
        r"instruction_scope_refs",
        r"history_context_refs",
        r"review_history_consistency",
        r"contradiction_count",
        r"timed_out=true",
        r"exit_code=124",
        r"timeout_command_span",
        r"if `REVIEW_REPAIR_LOOP` occurs, terminal closure MUST come from a later AI review round",
        r"reusing the same `prompt_ref` or `response_ref` across distinct AI review rounds is forbidden",
    ]
    for p in required_patterns:
        _assert(bool(re.search(p, txt, flags=re.MULTILINE)), f"contract missing required pattern: {p}")

    _assert(("RUNNING", "AI_REVIEW") in EXEC_ALLOWED, "RUNNING->AI_REVIEW must be allowed")
    _assert(("AI_REVIEW", "RUNNING") in EXEC_ALLOWED, "repair loop edge missing")
    _assert(("RUNNING", "PASSED") not in EXEC_ALLOWED, "RUNNING->PASSED must be forbidden")

    _assert(
        _transition_from_review(
            verdict="PASS",
            retry_used=0,
            retry_max=8,
            repeated_fingerprint_count=0,
            max_same_fingerprint_rounds=2,
            wall_clock_used_minutes=10,
            wall_clock_max_minutes=120,
        )
        == ("PASSED", "REVIEW_PASS"),
        "PASS verdict must terminate as PASSED",
    )

    _assert(
        _transition_from_review(
            verdict="REPAIRABLE",
            retry_used=2,
            retry_max=3,
            repeated_fingerprint_count=0,
            max_same_fingerprint_rounds=2,
            wall_clock_used_minutes=10,
            wall_clock_max_minutes=120,
        )
        == ("RUNNING", "REVIEW_REPAIR_LOOP"),
        "REPAIRABLE with budget must loop back to RUNNING",
    )

    _assert(
        _transition_from_review(
            verdict="REPAIRABLE",
            retry_used=3,
            retry_max=3,
            repeated_fingerprint_count=0,
            max_same_fingerprint_rounds=2,
            wall_clock_used_minutes=10,
            wall_clock_max_minutes=120,
        )
        == ("TRIAGED", "REVIEW_BUDGET_EXHAUSTED"),
        "REPAIRABLE with exhausted budget must TRIAGE",
    )
    _assert(
        _transition_from_review(
            verdict="REPAIRABLE",
            retry_used=8,
            retry_max=8,
            repeated_fingerprint_count=1,
            max_same_fingerprint_rounds=2,
            wall_clock_used_minutes=10,
            wall_clock_max_minutes=120,
        )
        == ("TRIAGED", "REVIEW_BUDGET_EXHAUSTED"),
        "max_ai_review_rounds boundary must TRIAGE (no off-by-one)",
    )

    _assert(
        _transition_from_review(
            verdict="REPAIRABLE",
            retry_used=2,
            retry_max=8,
            repeated_fingerprint_count=2,
            max_same_fingerprint_rounds=2,
            wall_clock_used_minutes=10,
            wall_clock_max_minutes=120,
        )
        == ("TRIAGED", "REVIEW_STAGNATION"),
        "repeated finding fingerprint must TRIAGE as stagnation",
    )

    _assert(
        _transition_from_review(
            verdict="UNRESOLVED_BLOCKER",
            retry_used=0,
            retry_max=8,
            repeated_fingerprint_count=0,
            max_same_fingerprint_rounds=2,
            wall_clock_used_minutes=10,
            wall_clock_max_minutes=120,
        )
        == ("TRIAGED", "REVIEW_UNRESOLVED_BLOCKER"),
        "UNRESOLVED_BLOCKER must TRIAGE",
    )
    _assert(
        _transition_from_review(
            verdict="UNRESOLVED_BLOCKER",
            retry_used=0,
            retry_max=8,
            repeated_fingerprint_count=2,
            max_same_fingerprint_rounds=2,
            wall_clock_used_minutes=10,
            wall_clock_max_minutes=120,
        )
        == ("TRIAGED", "REVIEW_STAGNATION"),
        "stagnation precedence must dominate unresolved blocker",
    )

    _assert(
        _transition_from_review(
            verdict="NON_RETRYABLE",
            retry_used=0,
            retry_max=8,
            repeated_fingerprint_count=0,
            max_same_fingerprint_rounds=2,
            wall_clock_used_minutes=10,
            wall_clock_max_minutes=120,
        )
        == ("FAILED", "REVIEW_NON_RETRYABLE_FAULT"),
        "NON_RETRYABLE must FAIL",
    )
    _assert(
        _transition_from_review(
            verdict="NON_RETRYABLE",
            retry_used=0,
            retry_max=8,
            repeated_fingerprint_count=2,
            max_same_fingerprint_rounds=2,
            wall_clock_used_minutes=10,
            wall_clock_max_minutes=120,
        )
        == ("TRIAGED", "REVIEW_STAGNATION"),
        "stagnation precedence must dominate NON_RETRYABLE when threshold is reached",
    )
    _assert(
        _transition_from_review(
            verdict="REPAIRABLE",
            retry_used=8,
            retry_max=8,
            repeated_fingerprint_count=1,
            max_same_fingerprint_rounds=2,
            wall_clock_used_minutes=120,
            wall_clock_max_minutes=120,
        )
        == ("TRIAGED", "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED"),
        "wall clock budget exhaustion must TRIAGE",
    )

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    verdict_enum = schema["$defs"]["reviewVerdict"]["enum"]
    _assert(
        verdict_enum == ["PASS", "REPAIRABLE", "UNRESOLVED_BLOCKER", "NON_RETRYABLE"],
        "review verdict enum must be strict and ordered",
    )
    _assert(
        schema["properties"]["budgets"]["properties"]["max_ai_review_rounds"].get("default") == 8,
        "max_ai_review_rounds default must be 8",
    )
    _assert(
        schema["properties"]["budgets"]["properties"]["max_same_fingerprint_rounds"].get("default") == 2,
        "max_same_fingerprint_rounds default must be 2",
    )
    _assert(
        schema["properties"]["budgets"]["properties"]["max_wave_wall_clock_minutes"].get("default") == 120,
        "max_wave_wall_clock_minutes default must be 120",
    )
    _assert(
        "agent_invocation" in schema["required"],
        "agent_invocation must be required in WaveExecutionLoopRun schema",
    )
    _assert(
        "review_history_consistency" in schema["required"],
        "review_history_consistency must be required in WaveExecutionLoopRun schema",
    )
    _assert(
        "dirty_tree" in schema["required"],
        "dirty_tree must be required in WaveExecutionLoopRun schema",
    )
    _assert(
        "assurance_level" in schema["required"],
        "assurance_level must be required in WaveExecutionLoopRun schema",
    )
    assurance_enum = schema["$defs"]["assuranceLevel"]["enum"]
    _assert(
        all(v in assurance_enum for v in ("FAST", "LIGHT", "STRICT")),
        "assuranceLevel enum must include FAST/LIGHT/STRICT",
    )
    _assert(
        "history_context_refs" in schema["$defs"]["reviewRecord"]["properties"],
        "reviewRecord must include history_context_refs for reviewer-memory handoff",
    )
    _assert(
        "dirtyTree" in schema["$defs"],
        "WaveExecutionLoopRun schema must define dirtyTree",
    )
    _assert(
        "timeoutCommandSpan" in schema["$defs"],
        "WaveExecutionLoopRun schema must define timeoutCommandSpan",
    )
    _assert(
        "timeout_command_span" in schema["properties"]["evidence"]["properties"],
        "WaveExecutionLoopRun evidence must expose timeout_command_span",
    )

    base = _base_instance()
    _assert(not _schema_errors(schema, base), "base wave execution instance must validate")
    _assert(
        _max_consecutive_fingerprint(base["iterations"]) == base["derived_metrics"]["max_consecutive_same_fingerprint"],
        "derived max_consecutive_same_fingerprint must match iteration replay",
    )
    replay = _replay_iteration_transitions(base)
    _assert(
        replay[-1] == (base["final_decision"]["state"], base["final_decision"]["reason_code"]),
        "replay from persisted iteration inputs must match final_decision",
    )
    _assert(
        replay[0] == (
            base["iterations"][0]["transition"]["to"],
            base["iterations"][0]["transition"]["reason_code"],
        ),
        "replay from persisted iteration inputs must match recorded transition",
    )
    _assert(_validate_trace_consistency(base), "execution trace must satisfy chain/start/end invariants")
    _assert(
        _validate_iteration_indexing(base),
        "iteration_index values must be contiguous 1..N",
    )
    _assert(
        _validate_budget_consistency(base),
        "budget counters must match iteration replay and wall-clock progression",
    )
    _assert(
        _validate_agent_invocation(base),
        "agent invocation evidence must be non-empty and deterministic",
    )
    _assert(
        _validate_review_history_consistency(base),
        "review history consistency summary must be self-consistent",
    )
    _assert(
        _validate_history_ref_propagation(base),
        "history refs propagation check must pass when no contradiction/nitpick refs exist",
    )
    _assert(
        _validate_review_closure(base),
        "review closure policy should accept base instance",
    )
    _assert(
        _validate_dirty_tree(base),
        "dirty_tree policy should accept base instance",
    )

    bad_edge = copy.deepcopy(base)
    bad_edge["execution"]["transitions"][1]["to"] = "PASSED"
    bad_edge["execution"]["transitions"][1]["reason_code"] = "REVIEW_PASS"
    _assert(
        bool(_schema_errors(schema, bad_edge)),
        "schema must reject forbidden execution edge RUNNING->PASSED",
    )

    bad_verdict_mapping = copy.deepcopy(base)
    bad_verdict_mapping["iterations"][0]["ai_review"]["verdict"] = "PASS"
    bad_verdict_mapping["iterations"][0]["transition"]["to"] = "FAILED"
    bad_verdict_mapping["iterations"][0]["transition"]["reason_code"] = "REVIEW_NON_RETRYABLE_FAULT"
    _assert(
        bool(_schema_errors(schema, bad_verdict_mapping)),
        "schema must reject PASS verdict mapped to FAILED transition",
    )

    bad_terminal_mismatch = copy.deepcopy(base)
    bad_terminal_mismatch["execution"]["current_state"] = "TRIAGED"
    _assert(
        bool(_schema_errors(schema, bad_terminal_mismatch)),
        "schema must reject final_decision/execution.current_state mismatch",
    )

    bad_stagnation_rule = copy.deepcopy(base)
    bad_stagnation_rule["derived_metrics"]["max_consecutive_same_fingerprint"] = 2
    bad_stagnation_rule["final_decision"]["state"] = "PASSED"
    bad_stagnation_rule["final_decision"]["reason_code"] = "REVIEW_PASS"
    bad_stagnation_rule["execution"]["current_state"] = "PASSED"
    _assert(
        bool(_schema_errors(schema, bad_stagnation_rule)),
        "schema must force TRIAGED/REVIEW_STAGNATION when max_consecutive_same_fingerprint >= 2",
    )

    ok_stagnation_over_non_retryable = copy.deepcopy(base)
    ok_stagnation_over_non_retryable["budgets"]["used_ai_review_rounds"] = 2
    ok_stagnation_over_non_retryable["budgets"]["used_wall_clock_minutes"] = 20
    ok_stagnation_over_non_retryable["derived_metrics"]["max_consecutive_same_fingerprint"] = 2
    first_iter = copy.deepcopy(base["iterations"][0])
    first_iter["ai_review"]["verdict"] = "REPAIRABLE"
    first_iter["transition"]["to"] = "RUNNING"
    first_iter["transition"]["reason_code"] = "REVIEW_REPAIR_LOOP"
    first_iter["wall_clock_used_minutes"] = 10
    second_iter = copy.deepcopy(base["iterations"][0])
    second_iter["iteration_index"] = 2
    second_iter["ai_review"]["verdict"] = "NON_RETRYABLE"
    second_iter["transition"]["to"] = "TRIAGED"
    second_iter["transition"]["reason_code"] = "REVIEW_STAGNATION"
    second_iter["wall_clock_used_minutes"] = 20
    ok_stagnation_over_non_retryable["iterations"] = [first_iter, second_iter]
    ok_stagnation_over_non_retryable["execution"]["current_state"] = "TRIAGED"
    ok_stagnation_over_non_retryable["execution"]["transitions"] = [
        {
            "from": "PENDING",
            "to": "RUNNING",
            "reason_code": "WAVE_START",
            "at_utc": "2026-03-05T00:00:00Z",
        },
        {
            "from": "RUNNING",
            "to": "AI_REVIEW",
            "reason_code": "IMPLEMENTATION_SUBMITTED_FOR_REVIEW",
            "at_utc": "2026-03-05T00:01:00Z",
        },
        {
            "from": "AI_REVIEW",
            "to": "RUNNING",
            "reason_code": "REVIEW_REPAIR_LOOP",
            "at_utc": "2026-03-05T00:02:00Z",
        },
        {
            "from": "RUNNING",
            "to": "AI_REVIEW",
            "reason_code": "IMPLEMENTATION_SUBMITTED_FOR_REVIEW",
            "at_utc": "2026-03-05T00:03:00Z",
        },
        {
            "from": "AI_REVIEW",
            "to": "TRIAGED",
            "reason_code": "REVIEW_STAGNATION",
            "at_utc": "2026-03-05T00:04:00Z",
        },
    ]
    ok_stagnation_over_non_retryable["final_decision"]["state"] = "TRIAGED"
    ok_stagnation_over_non_retryable["final_decision"]["reason_code"] = "REVIEW_STAGNATION"
    ok_stagnation_over_non_retryable["final_decision"]["at_utc"] = "2026-03-05T00:04:00Z"
    _assert(
        not _schema_errors(schema, ok_stagnation_over_non_retryable),
        "schema must allow stagnation precedence over NON_RETRYABLE",
    )

    bad_pass_with_wall_clock_exhausted = copy.deepcopy(base)
    bad_pass_with_wall_clock_exhausted["budgets"]["used_wall_clock_minutes"] = 120
    bad_pass_with_wall_clock_exhausted["iterations"][0]["wall_clock_used_minutes"] = 120
    _assert(
        bool(_schema_errors(schema, bad_pass_with_wall_clock_exhausted)),
        "schema must reject final PASSED when wall-clock budget is exhausted",
    )

    bad_wallclock_reason_without_exhaustion = copy.deepcopy(base)
    bad_wallclock_reason_without_exhaustion["iterations"][0]["ai_review"]["verdict"] = "REPAIRABLE"
    bad_wallclock_reason_without_exhaustion["iterations"][0]["transition"]["to"] = "TRIAGED"
    bad_wallclock_reason_without_exhaustion["iterations"][0]["transition"]["reason_code"] = "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED"
    bad_wallclock_reason_without_exhaustion["final_decision"]["state"] = "TRIAGED"
    bad_wallclock_reason_without_exhaustion["final_decision"]["reason_code"] = "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED"
    bad_wallclock_reason_without_exhaustion["execution"]["current_state"] = "TRIAGED"
    bad_wallclock_reason_without_exhaustion["execution"]["transitions"][-1]["to"] = "TRIAGED"
    bad_wallclock_reason_without_exhaustion["execution"]["transitions"][-1]["reason_code"] = "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED"
    _assert(
        bool(_schema_errors(schema, bad_wallclock_reason_without_exhaustion)),
        "schema must reject wall-clock exhaustion reason when wall-clock budget is not exhausted",
    )

    bad_budget_reason_when_wallclock_exhausted = copy.deepcopy(base)
    bad_budget_reason_when_wallclock_exhausted["budgets"]["used_wall_clock_minutes"] = 120
    bad_budget_reason_when_wallclock_exhausted["iterations"][0]["wall_clock_used_minutes"] = 120
    bad_budget_reason_when_wallclock_exhausted["iterations"][0]["ai_review"]["verdict"] = "REPAIRABLE"
    bad_budget_reason_when_wallclock_exhausted["iterations"][0]["transition"]["to"] = "TRIAGED"
    bad_budget_reason_when_wallclock_exhausted["iterations"][0]["transition"]["reason_code"] = "REVIEW_BUDGET_EXHAUSTED"
    bad_budget_reason_when_wallclock_exhausted["final_decision"]["state"] = "TRIAGED"
    bad_budget_reason_when_wallclock_exhausted["final_decision"]["reason_code"] = "REVIEW_BUDGET_EXHAUSTED"
    bad_budget_reason_when_wallclock_exhausted["execution"]["current_state"] = "TRIAGED"
    bad_budget_reason_when_wallclock_exhausted["execution"]["transitions"][-1]["to"] = "TRIAGED"
    bad_budget_reason_when_wallclock_exhausted["execution"]["transitions"][-1]["reason_code"] = "REVIEW_BUDGET_EXHAUSTED"
    _assert(
        bool(_schema_errors(schema, bad_budget_reason_when_wallclock_exhausted)),
        "schema must reject REVIEW_BUDGET_EXHAUSTED when wall-clock budget is exhausted",
    )

    bad_timeout_evidence = copy.deepcopy(base)
    bad_timeout_evidence["budgets"]["used_wall_clock_minutes"] = 120
    bad_timeout_evidence["iterations"][0]["wall_clock_used_minutes"] = 120
    bad_timeout_evidence["iterations"][0]["ai_review"]["verdict"] = "PASS"
    bad_timeout_evidence["iterations"][0]["transition"]["to"] = "TRIAGED"
    bad_timeout_evidence["iterations"][0]["transition"]["reason_code"] = "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED"
    bad_timeout_evidence["final_decision"]["state"] = "TRIAGED"
    bad_timeout_evidence["final_decision"]["reason_code"] = "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED"
    bad_timeout_evidence["execution"]["current_state"] = "TRIAGED"
    bad_timeout_evidence["execution"]["transitions"][-1]["to"] = "TRIAGED"
    bad_timeout_evidence["execution"]["transitions"][-1]["reason_code"] = "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED"
    bad_timeout_evidence["evidence"].pop("timeout_command_span", None)
    _assert(
        bool(_schema_errors(schema, bad_timeout_evidence)),
        "schema must require timeout_command_span for REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED terminal reports",
    )

    good_timeout_evidence = copy.deepcopy(bad_timeout_evidence)
    good_timeout_evidence["evidence"]["timeout_command_span"] = {
        "timed_out": True,
        "exit_code": 124,
        "stdout_path": "artifacts/loop_runtime/by_key/aaa/wave_execution/reviewer_timeout.stdout.txt",
        "stderr_path": "artifacts/loop_runtime/by_key/aaa/wave_execution/reviewer_timeout.stderr.txt",
    }
    _assert(
        not _schema_errors(schema, good_timeout_evidence),
        "schema should accept wall-clock timeout reports with structured timeout_command_span evidence",
    )

    bad_trace_chain = copy.deepcopy(base)
    bad_trace_chain["execution"]["transitions"][1]["from"] = "PENDING"
    _assert(
        not _validate_trace_consistency(bad_trace_chain),
        "policy checker must reject non-contiguous transition chains",
    )

    bad_replay_mismatch = copy.deepcopy(base)
    bad_replay_mismatch["iterations"][0]["transition"]["to"] = "RUNNING"
    bad_replay_mismatch["iterations"][0]["transition"]["reason_code"] = "REVIEW_REPAIR_LOOP"
    bad_replay = _replay_iteration_transitions(bad_replay_mismatch)
    _assert(
        bad_replay[0] != (
            bad_replay_mismatch["iterations"][0]["transition"]["to"],
            bad_replay_mismatch["iterations"][0]["transition"]["reason_code"],
        ),
        "policy checker must detect replay/recorded transition mismatch",
    )

    bad_ai_iteration_mismatch = copy.deepcopy(base)
    bad_ai_iteration_mismatch["iterations"].append(copy.deepcopy(base["iterations"][0]))
    bad_ai_iteration_mismatch["iterations"][1]["iteration_index"] = 2
    _assert(
        not _validate_trace_consistency(bad_ai_iteration_mismatch),
        "policy checker must reject AI_REVIEW-edge count != len(iterations)",
    )

    bad_iteration_index = copy.deepcopy(base)
    bad_iteration_index["iterations"][0]["iteration_index"] = 2
    _assert(
        not _validate_iteration_indexing(bad_iteration_index),
        "policy checker must reject non-contiguous iteration_index values",
    )
    _assert(
        not _validate_review_closure(bad_iteration_index),
        "review closure policy must reject non-contiguous iteration_index values",
    )

    bad_round_budget = copy.deepcopy(base)
    bad_round_budget["budgets"]["used_ai_review_rounds"] = 0
    _assert(
        not _validate_budget_consistency(bad_round_budget),
        "policy checker must reject used_ai_review_rounds != len(iterations)",
    )

    bad_wall_budget = copy.deepcopy(base)
    bad_wall_budget["budgets"]["used_wall_clock_minutes"] = 13
    _assert(
        not _validate_budget_consistency(bad_wall_budget),
        "policy checker must reject used_wall_clock_minutes != last iteration wall_clock_used_minutes",
    )

    bad_wall_order = copy.deepcopy(base)
    bad_wall_order["iterations"][0]["wall_clock_used_minutes"] = 15
    _assert(
        not _validate_budget_consistency(bad_wall_order),
        "policy checker must reject non-monotonic wall_clock_used_minutes",
    )

    bad_invocation = copy.deepcopy(base)
    bad_invocation["agent_invocation"]["resolved_invocation"] = []
    _assert(
        not _validate_agent_invocation(bad_invocation),
        "policy checker must reject empty agent invocation command",
    )

    bad_provider_invocation = copy.deepcopy(base)
    bad_provider_invocation["agent_invocation"]["agent_provider_id"] = "codex_cli"
    bad_provider_invocation["agent_invocation"]["resolved_invocation"] = ["claude", "exec", "review"]
    _assert(
        not _validate_agent_invocation(bad_provider_invocation),
        "policy checker must reject invocation that mismatches selected agent_provider_id",
    )

    bad_instruction_scope = copy.deepcopy(base)
    bad_instruction_scope["agent_invocation"]["instruction_scope_refs"] = [
        "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
    ]
    _assert(
        not _validate_agent_invocation(bad_instruction_scope),
        "policy checker must reject instruction_scope_refs that do not include AGENTS.md chain",
    )

    bad_history_summary = copy.deepcopy(base)
    bad_history_summary["review_history_consistency"]["contradiction_count"] = 0
    bad_history_summary["review_history_consistency"]["contradiction_refs"] = [
        "finding.waveA.round1.001",
    ]
    _assert(
        not _validate_review_history_consistency(bad_history_summary),
        "policy checker must reject contradiction refs exceeding contradiction_count",
    )

    bad_history_ref = copy.deepcopy(base)
    bad_history_ref["review_history_consistency"]["contradiction_count"] = 1
    bad_history_ref["review_history_consistency"]["contradiction_refs"] = [""]
    _assert(
        not _validate_review_history_consistency(bad_history_ref),
        "policy checker must reject history consistency refs that are empty/non-string",
    )

    ok_history_propagation = copy.deepcopy(base)
    ok_history_propagation["budgets"]["used_ai_review_rounds"] = 2
    ok_history_propagation["budgets"]["used_wall_clock_minutes"] = 16
    first_iter = copy.deepcopy(base["iterations"][0])
    first_iter["ai_review"]["verdict"] = "REPAIRABLE"
    first_iter["transition"]["to"] = "RUNNING"
    first_iter["transition"]["reason_code"] = "REVIEW_REPAIR_LOOP"
    first_iter["history_context_refs"] = [
        "artifacts/waveA/review_history_until_round0.json",
    ]
    first_iter["wall_clock_used_minutes"] = 8
    second_iter = copy.deepcopy(base["iterations"][0])
    second_iter["iteration_index"] = 2
    second_iter["ai_review"]["verdict"] = "PASS"
    second_iter["ai_review"]["finding_fingerprint"] = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    second_iter["transition"]["to"] = "PASSED"
    second_iter["transition"]["reason_code"] = "REVIEW_PASS"
    second_iter["transition"]["at_utc"] = "2026-03-05T00:04:00Z"
    second_iter["history_context_refs"] = [
        "finding.waveA.round1.001",
    ]
    second_iter["wall_clock_used_minutes"] = 16
    ok_history_propagation["iterations"] = [first_iter, second_iter]
    ok_history_propagation["execution"]["transitions"] = [
        {
            "from": "PENDING",
            "to": "RUNNING",
            "reason_code": "WAVE_START",
            "at_utc": "2026-03-05T00:00:00Z",
        },
        {
            "from": "RUNNING",
            "to": "AI_REVIEW",
            "reason_code": "IMPLEMENTATION_SUBMITTED_FOR_REVIEW",
            "at_utc": "2026-03-05T00:01:00Z",
        },
        {
            "from": "AI_REVIEW",
            "to": "RUNNING",
            "reason_code": "REVIEW_REPAIR_LOOP",
            "at_utc": "2026-03-05T00:02:00Z",
        },
        {
            "from": "RUNNING",
            "to": "AI_REVIEW",
            "reason_code": "IMPLEMENTATION_SUBMITTED_FOR_REVIEW",
            "at_utc": "2026-03-05T00:03:00Z",
        },
        {
            "from": "AI_REVIEW",
            "to": "PASSED",
            "reason_code": "REVIEW_PASS",
            "at_utc": "2026-03-05T00:04:00Z",
        },
    ]
    ok_history_propagation["execution"]["current_state"] = "PASSED"
    ok_history_propagation["final_decision"]["state"] = "PASSED"
    ok_history_propagation["final_decision"]["reason_code"] = "REVIEW_PASS"
    ok_history_propagation["final_decision"]["at_utc"] = "2026-03-05T00:04:00Z"
    ok_history_propagation["review_history_consistency"]["contradiction_count"] = 1
    ok_history_propagation["review_history_consistency"]["contradiction_refs"] = ["finding.waveA.round1.001"]
    _assert(
        _validate_history_ref_propagation(ok_history_propagation),
        "policy checker must accept valid propagation of contradiction refs into later history_context_refs",
    )

    bad_history_propagation = copy.deepcopy(ok_history_propagation)
    bad_history_propagation["iterations"][1]["history_context_refs"] = ["artifacts/waveA/review_history_until_round0.json"]
    _assert(
        not _validate_history_ref_propagation(bad_history_propagation),
        "policy checker must reject missing propagation of contradiction/nitpick refs to later rounds",
    )

    bad_closure_reuse = copy.deepcopy(ok_history_propagation)
    bad_closure_reuse["iterations"][1]["ai_review"]["prompt_ref"] = bad_closure_reuse["iterations"][0]["ai_review"][
        "prompt_ref"
    ]
    bad_closure_reuse["iterations"][1]["ai_review"]["response_ref"] = bad_closure_reuse["iterations"][0]["ai_review"][
        "response_ref"
    ]
    _assert(
        not _validate_review_closure(bad_closure_reuse),
        "review closure policy must reject reused prompt/response refs across rounds",
    )

    bad_missing_followup = copy.deepcopy(ok_history_propagation)
    bad_missing_followup["iterations"] = [copy.deepcopy(ok_history_propagation["iterations"][0])]
    _assert(
        not _validate_review_closure(bad_missing_followup),
        "review closure policy must reject repair-loop without a later AI review round",
    )

    bad_strict_evidence = copy.deepcopy(base)
    del bad_strict_evidence["evidence"]["ai_review_summary_ref"]
    _assert(
        bool(_schema_errors(schema, bad_strict_evidence)),
        "schema must reject STRICT PASSED instance missing ai_review_summary_ref",
    )

    print("[loop-wave-exec-policy] OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[loop-wave-exec-policy][FAIL] {ex}", file=sys.stderr)
        raise SystemExit(2)
