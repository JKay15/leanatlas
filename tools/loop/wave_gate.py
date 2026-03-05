#!/usr/bin/env python3
"""Blocking gate for WaveExecutionLoopRun artifacts."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .dirty_tree_gate import validate_dirty_tree_snapshot

try:
    import jsonschema
except Exception as exc:  # pragma: no cover - dependency guard in runtime env
    raise RuntimeError("jsonschema is required for wave gate checks") from exc


def _root_from_repo(repo_root: Path | str | None) -> Path:
    if repo_root is None:
        return Path(__file__).resolve().parents[2]
    return Path(repo_root).resolve()


@lru_cache(maxsize=8)
def _load_wave_schema(repo_root_str: str) -> dict[str, Any]:
    root = Path(repo_root_str)
    p = root / "docs" / "schemas" / "WaveExecutionLoopRun.schema.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _schema_errors(report: dict[str, Any], *, repo_root: Path) -> list[str]:
    schema = _load_wave_schema(str(repo_root))
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
    )
    errs = sorted(validator.iter_errors(report), key=lambda e: list(e.absolute_path))
    out: list[str] = []
    for e in errs:
        path = "/" + "/".join(str(x) for x in e.absolute_path)
        out.append(f"schema violation at {path}: {e.message}")
    return out


def _validate_trace_consistency(report: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    transitions = ((report.get("execution") or {}).get("transitions")) or []
    iterations = report.get("iterations") or []
    final = report.get("final_decision") or {}
    execution = report.get("execution") or {}
    if not transitions:
        return ["trace consistency: execution.transitions must be non-empty"]

    first = transitions[0]
    if (first.get("from"), first.get("to"), first.get("reason_code")) != ("PENDING", "RUNNING", "WAVE_START"):
        errs.append("trace consistency: first transition must be PENDING->RUNNING with WAVE_START")

    for i in range(len(transitions) - 1):
        if transitions[i].get("to") != transitions[i + 1].get("from"):
            errs.append("trace consistency: transitions must be contiguous")
            break

    ai_edges = [t for t in transitions if t.get("from") == "AI_REVIEW"]
    if len(ai_edges) != len(iterations):
        errs.append("trace consistency: number of AI_REVIEW->* edges must equal len(iterations)")
    else:
        for edge, rec in zip(ai_edges, iterations):
            tr = rec.get("transition") or {}
            if edge.get("to") != tr.get("to") or edge.get("reason_code") != tr.get("reason_code"):
                errs.append("trace consistency: iteration.transition must match corresponding AI_REVIEW edge")
                break

    last = transitions[-1]
    if last.get("to") != final.get("state") or last.get("reason_code") != final.get("reason_code"):
        errs.append("trace consistency: final_decision must match last transition")
    if execution.get("current_state") != final.get("state"):
        errs.append("trace consistency: execution.current_state must equal final_decision.state")
    return errs


def _validate_budget_consistency(report: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    budgets = report.get("budgets") or {}
    iterations = report.get("iterations") or []

    used_rounds = int(budgets.get("used_ai_review_rounds", -1))
    max_rounds = int(budgets.get("max_ai_review_rounds", -1))
    if used_rounds != len(iterations):
        errs.append("budget consistency: budgets.used_ai_review_rounds must equal len(iterations)")
    if used_rounds > max_rounds:
        errs.append("budget consistency: used_ai_review_rounds cannot exceed max_ai_review_rounds")

    used_wall = int(budgets.get("used_wall_clock_minutes", -1))
    max_wall = int(budgets.get("max_wave_wall_clock_minutes", -1))
    if used_wall > max_wall:
        errs.append("budget consistency: used_wall_clock_minutes cannot exceed max_wave_wall_clock_minutes")

    wall_values = [int((rec or {}).get("wall_clock_used_minutes", 0)) for rec in iterations]
    if wall_values:
        if any(v > max_wall for v in wall_values):
            errs.append("budget consistency: iteration wall_clock_used_minutes cannot exceed max_wave_wall_clock_minutes")
        if wall_values != sorted(wall_values):
            errs.append("budget consistency: iteration wall_clock_used_minutes must be non-decreasing")
        if wall_values[-1] != used_wall:
            errs.append("budget consistency: last iteration wall_clock_used_minutes must equal budgets.used_wall_clock_minutes")
    return errs


def _validate_review_history(report: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    summary = report.get("review_history_consistency") or {}
    contradiction_refs = list(summary.get("contradiction_refs") or [])
    nitpick_refs = list(summary.get("nitpick_refs") or [])
    contradiction_count = int(summary.get("contradiction_count", 0))
    nitpick_count = int(summary.get("potential_nitpick_count", 0))
    if contradiction_count < len(contradiction_refs):
        errs.append("review_history_consistency: contradiction_count must be >= len(contradiction_refs)")
    if nitpick_count < len(nitpick_refs):
        errs.append("review_history_consistency: potential_nitpick_count must be >= len(nitpick_refs)")

    refs = set(contradiction_refs) | set(nitpick_refs)
    if refs:
        iterations = report.get("iterations") or []
        if not iterations:
            errs.append("review_history_consistency: contradiction/nitpick refs require non-empty iterations")
            return errs
        if len(iterations) <= 1:
            errs.append("review_history_consistency: contradiction/nitpick refs must be propagated to later review rounds")
            return errs
        propagated: set[str] = set()
        for rec in iterations[1:]:
            for href in rec.get("history_context_refs") or []:
                propagated.add(str(href))
        if not refs.issubset(propagated):
            errs.append(
                "review_history_consistency: contradiction/nitpick refs must be included in later-round history_context_refs"
            )
    return errs


def _validate_review_closure(report: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    iterations = report.get("iterations") or []
    if not iterations:
        return errs

    expected = list(range(1, len(iterations) + 1))
    actual: list[int] = []
    for rec in iterations:
        try:
            actual.append(int(rec.get("iteration_index")))
        except Exception:
            actual.append(-1)
    if actual != expected:
        errs.append("review closure: iteration_index must be contiguous 1..N")

    seen_prompts: set[str] = set()
    seen_responses: set[str] = set()
    for rec in iterations:
        ai = rec.get("ai_review") or {}
        prompt_ref = str(ai.get("prompt_ref") or "")
        response_ref = str(ai.get("response_ref") or "")
        if prompt_ref in seen_prompts:
            errs.append("review closure: reusing the same prompt_ref across distinct AI review rounds is forbidden")
            break
        if response_ref in seen_responses:
            errs.append("review closure: reusing the same response_ref across distinct AI review rounds is forbidden")
            break
        seen_prompts.add(prompt_ref)
        seen_responses.add(response_ref)

    for i, rec in enumerate(iterations):
        tr = rec.get("transition") or {}
        if tr.get("to") == "RUNNING" and tr.get("reason_code") == "REVIEW_REPAIR_LOOP":
            if i + 1 >= len(iterations):
                errs.append(
                    "review closure: if REVIEW_REPAIR_LOOP occurs, terminal closure MUST come from a later AI review round"
                )
                break
            cur_ai = rec.get("ai_review") or {}
            next_ai = (iterations[i + 1] or {}).get("ai_review") or {}
            if str(cur_ai.get("prompt_ref") or "") == str(next_ai.get("prompt_ref") or "") or str(
                cur_ai.get("response_ref") or ""
            ) == str(next_ai.get("response_ref") or ""):
                errs.append("review closure: post-repair review must carry fresh prompt_ref/response_ref evidence")
                break

    return errs


def _validate_dirty_tree(report: dict[str, Any]) -> list[str]:
    final_state = str((report.get("final_decision") or {}).get("state") or "")
    dt = report.get("dirty_tree") or {}
    return validate_dirty_tree_snapshot(dt, final_state=final_state)


def _validate_reason_coherence(report: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    budgets = report.get("budgets") or {}
    final = report.get("final_decision") or {}
    derived = report.get("derived_metrics") or {}
    reason = str(final.get("reason_code") or "")
    state = str(final.get("state") or "")

    used_rounds = int(budgets.get("used_ai_review_rounds", 0))
    max_rounds = int(budgets.get("max_ai_review_rounds", 0))
    max_same = int(budgets.get("max_same_fingerprint_rounds", 0))
    max_consecutive = int(derived.get("max_consecutive_same_fingerprint", 0))

    if reason == "REVIEW_BUDGET_EXHAUSTED":
        if state != "TRIAGED":
            errs.append("reason coherence: REVIEW_BUDGET_EXHAUSTED requires final_decision.state=TRIAGED")
        if used_rounds != max_rounds:
            errs.append("reason coherence: REVIEW_BUDGET_EXHAUSTED requires used_ai_review_rounds=max_ai_review_rounds")
    if reason == "REVIEW_STAGNATION":
        if state != "TRIAGED":
            errs.append("reason coherence: REVIEW_STAGNATION requires final_decision.state=TRIAGED")
        if max_same > 0 and max_consecutive < max_same:
            errs.append(
                "reason coherence: REVIEW_STAGNATION requires max_consecutive_same_fingerprint >= max_same_fingerprint_rounds"
            )
    return errs


def _validate_timeout_evidence(report: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    final = report.get("final_decision") or {}
    reason = str(final.get("reason_code") or "")
    if reason != "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED":
        return errs

    evidence = report.get("evidence") or {}
    span = evidence.get("timeout_command_span")
    if not isinstance(span, dict):
        return ["timeout evidence: REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED requires evidence.timeout_command_span"]
    if span.get("timed_out") is not True:
        errs.append("timeout evidence: timeout_command_span.timed_out must be true")
    try:
        exit_code = int(span.get("exit_code", -1))
    except Exception:
        exit_code = -1
    if exit_code != 124:
        errs.append("timeout evidence: timeout_command_span.exit_code must be 124")
    for field in ("stdout_path", "stderr_path"):
        if not str(span.get(field) or "").strip():
            errs.append(f"timeout evidence: timeout_command_span.{field} must be a non-empty path")
    return errs


def _max_consecutive_fingerprint(iterations: list[dict[str, Any]]) -> int:
    last_fp: str | None = None
    run = 0
    best = 0
    for rec in iterations:
        fp = str(((rec.get("ai_review") or {}).get("finding_fingerprint")) or "")
        if fp and fp == last_fp:
            run += 1
        else:
            run = 1 if fp else 0
            last_fp = fp if fp else None
        if run > best:
            best = run
    return max(0, best)


def _tail_consecutive_fingerprint(iterations: list[dict[str, Any]]) -> int:
    last_fp: str | None = None
    run = 0
    for rec in iterations:
        fp = str(((rec.get("ai_review") or {}).get("finding_fingerprint")) or "")
        if fp and fp == last_fp:
            run += 1
        else:
            run = 1 if fp else 0
            last_fp = fp if fp else None
    return max(0, run)


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _validate_replay_consistency(report: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    iterations = report.get("iterations") or []
    derived = report.get("derived_metrics") or {}
    budgets = report.get("budgets") or {}
    execution = report.get("execution") or {}
    review_hist = report.get("review_history_consistency") or {}
    transitions = execution.get("transitions") or []

    expected_max_consecutive = max(1, _max_consecutive_fingerprint(iterations))
    got_max_consecutive = int(derived.get("max_consecutive_same_fingerprint", -1))
    if got_max_consecutive != expected_max_consecutive:
        errs.append("replay consistency: derived max_consecutive_same_fingerprint must match iteration replay")

    last_fp = None
    if iterations:
        last_fp = str(((iterations[-1].get("ai_review") or {}).get("finding_fingerprint")) or "") or None
    expected_state = {
        "version": "1",
        "run_key": str(report.get("run_key") or ""),
        "wave_id": str(report.get("wave_id") or ""),
        "current_state": str(execution.get("current_state") or ""),
        "used_ai_review_rounds": int(budgets.get("used_ai_review_rounds", 0)),
        "used_wall_clock_minutes": int(budgets.get("used_wall_clock_minutes", 0)),
        "max_ai_review_rounds": int(budgets.get("max_ai_review_rounds", 0)),
        "max_same_fingerprint_rounds": int(budgets.get("max_same_fingerprint_rounds", 0)),
        "max_wave_wall_clock_minutes": int(budgets.get("max_wave_wall_clock_minutes", 0)),
        "last_finding_fingerprint": last_fp,
        "consecutive_same_fingerprint": _tail_consecutive_fingerprint(iterations),
    }
    expected_digest = hashlib.sha256(
        _canonical_json(
            {
                "transitions": transitions,
                "iterations": iterations,
                "review_history_consistency": review_hist,
                "state": expected_state,
            }
        ).encode("utf-8")
    ).hexdigest()
    got_digest = str(derived.get("replay_digest") or "")
    if got_digest != expected_digest:
        errs.append("replay consistency: derived replay_digest must match canonical replay payload")
    return errs


def _validate_agent_invocation(report: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    inv = report.get("agent_invocation") or {}
    provider = str(inv.get("agent_provider_id") or "").strip()
    resolved = [str(x) for x in (inv.get("resolved_invocation") or [])]
    if not resolved or any(not x.strip() for x in resolved):
        errs.append("agent invocation: resolved_invocation must be a non-empty command list")
        return errs
    expected_prefix = {
        "codex_cli": ["codex", "exec"],
        "claude_code": ["claude", "exec"],
    }
    if provider in expected_prefix and resolved[:2] != expected_prefix[provider]:
        errs.append("agent invocation: resolved_invocation must match agent_provider_id routing prefix")
    refs = [str(x) for x in (inv.get("instruction_scope_refs") or [])]
    if not refs or not any(r.endswith("AGENTS.md") for r in refs):
        errs.append("agent invocation: instruction_scope_refs must include AGENTS.md chain")
    return errs


def validate_wave_execution_report(report: dict[str, Any], *, repo_root: Path | str | None = None) -> list[str]:
    """Return deterministic list of blocking errors for a Wave execution report."""

    root = _root_from_repo(repo_root)
    errors: list[str] = []
    errors.extend(_schema_errors(report, repo_root=root))
    if errors:
        return errors
    errors.extend(_validate_trace_consistency(report))
    errors.extend(_validate_budget_consistency(report))
    errors.extend(_validate_review_history(report))
    errors.extend(_validate_review_closure(report))
    errors.extend(_validate_dirty_tree(report))
    errors.extend(_validate_reason_coherence(report))
    errors.extend(_validate_timeout_evidence(report))
    errors.extend(_validate_replay_consistency(report))
    errors.extend(_validate_agent_invocation(report))
    return errors


def assert_wave_execution_report(report: dict[str, Any], *, repo_root: Path | str | None = None) -> None:
    errs = validate_wave_execution_report(report, repo_root=repo_root)
    if errs:
        msg = "\n".join(errs)
        raise ValueError(f"wave execution blocking gate failed:\n{msg}")
