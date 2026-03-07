#!/usr/bin/env python3
"""Python SDK facade for LOOP runtime (Wave-B M5 minimal)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .assurance import evaluate_wave_completion_gate, normalize_assurance_level
from .dirty_tree_gate import collect_dirty_tree_snapshot
from .errors import normalize_exception
from .review_history import summarize_review_history
from .run_key import RunKeyInput, compute_run_key
from .runtime import LoopRuntime
from .wave_gate import assert_wave_execution_report


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _call_id(operation: str, idempotency_key: str) -> str:
    digest = hashlib.sha256(f"{operation}|{idempotency_key}".encode("utf-8")).hexdigest()[:24]
    return f"sdk_{operation}_{digest}"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, obj: Any) -> None:
    _write_text(path, _canonical_json(obj))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows]
    path.write_text("".join(lines), encoding="utf-8")


def _round_time(round_idx: int, *, submit_phase: bool) -> str:
    base = datetime(1970, 1, 1, tzinfo=timezone.utc)
    minute = (round_idx - 1) * 2 + (1 if submit_phase else 2)
    ts = base + timedelta(minutes=minute)
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_finding_fingerprint(round_idx: int, verdict: str) -> str:
    return hashlib.sha256(f"round:{round_idx}|verdict:{verdict}".encode("utf-8")).hexdigest()


def _default_findings(round_idx: int, verdict: str) -> list[dict[str, Any]]:
    repairable = verdict == "REPAIRABLE"
    severity = "S2_MAJOR" if repairable else "S3_MINOR"
    return [
        {
            "finding_id": f"finding.wave.auto.round{round_idx}.001",
            "severity": severity,
            "repairable": repairable,
            "summary": f"Auto-generated review finding for verdict={verdict}.",
            "evidence_refs": [f"artifacts/wave_execution/review_finding_round{round_idx}.md"],
        }
    ]


def _invocation_source(agent_provider: str | None, agent_profile: str | None) -> str:
    if agent_provider:
        return "cli.agent_provider"
    if agent_profile:
        return "cli.agent_profile"
    return "loop.runtime.default"


def _resolved_invocation_list(agent_provider: str | None) -> list[str]:
    sig = _resolved_invocation_signature(agent_provider)
    if not sig:
        return ["loop", "runtime", "default"]
    if ":" in sig and " " not in sig:
        provider = sig.split(":", 1)[0]
        return [provider, "unspecified"]
    return [x for x in sig.split() if x]


def _history_context_refs(
    *,
    iteration_index: int,
    review_history_summary: dict[str, Any],
) -> list[str]:
    refs: list[str] = [f"artifacts/wave_execution/review_history_until_round{iteration_index - 1}.json"]
    refs.extend([str(x) for x in review_history_summary.get("contradiction_refs") or []])
    refs.extend([str(x) for x in review_history_summary.get("nitpick_refs") or []])
    deduped: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref and ref not in seen:
            deduped.append(ref)
            seen.add(ref)
    return deduped or [f"artifacts/wave_execution/review_history_until_round{iteration_index - 1}.json"]


def _max_consecutive_fingerprint(review_records: list[dict[str, Any]]) -> int:
    last_fp: str | None = None
    run = 0
    best = 0
    for rec in review_records:
        fp = str((rec.get("ai_review") or {}).get("finding_fingerprint") or "")
        if fp and fp == last_fp:
            run += 1
        else:
            run = 1 if fp else 0
            last_fp = fp if fp else None
        if run > best:
            best = run
    return max(0, best)


def _build_wave_execution_report(
    *,
    spec: dict[str, Any],
    rt: LoopRuntime,
    review_records: list[dict[str, Any]],
    review_history_summary: dict[str, Any],
    agent_provider: str | None,
    agent_profile: str | None,
    instruction_scope_refs: list[str] | None,
    ai_review_log_path: Path,
    iteration_trace_path: Path,
    final_decision_path: Path,
    strict_prompt_ref: str | None,
    strict_response_ref: str | None,
    strict_summary_ref: str | None,
    repo_root: Path,
) -> dict[str, Any]:
    transitions = rt.read_transitions()
    final_transition = transitions[-1] if transitions else {"to": rt.state["current_state"], "reason_code": "REVIEW_INVALID_VERDICT"}
    if review_records:
        last_review = review_records[-1]
        last_ai = (last_review.get("ai_review") or {})
        if not strict_prompt_ref:
            strict_prompt_ref = str(last_ai.get("prompt_ref") or "")
        if not strict_response_ref:
            strict_response_ref = str(last_ai.get("response_ref") or "")
        if not strict_summary_ref:
            idx = int(last_review.get("iteration_index") or 0)
            if idx > 0:
                candidate = rt.store.artifact_path(f"wave_execution/review_summary_round{idx}.json")
                if candidate.exists():
                    strict_summary_ref = str(candidate)
    resolved_invocation = _resolved_invocation_list(agent_provider)
    resolved_invocation_str = " ".join(resolved_invocation)
    scope_refs = instruction_scope_refs or [str(Path("AGENTS.md"))]
    replay_payload = {
        "transitions": transitions,
        "iterations": review_records,
        "review_history_consistency": review_history_summary,
        "state": rt.state,
    }
    replay_digest = hashlib.sha256(_canonical_json(replay_payload).encode("utf-8")).hexdigest()
    dirty_tree = collect_dirty_tree_snapshot(repo_root)
    report = {
        "version": "1",
        "wave_id": str(spec.get("wave_id") or spec["loop_id"]),
        "run_key": rt.store.run_key,
        "assurance_level": str(spec.get("assurance_level") or "FAST"),
        "agent_invocation": {
            "agent_provider_id": str(agent_provider or "loop.runtime.default"),
            "resolved_invocation": resolved_invocation,
            "instruction_scope_refs": scope_refs,
            "invocation_source": _invocation_source(agent_provider, agent_profile),
            "resolved_command_sha256": hashlib.sha256(resolved_invocation_str.encode("utf-8")).hexdigest(),
        },
        "budgets": {
            "max_ai_review_rounds": int(rt.state["max_ai_review_rounds"]),
            "max_same_fingerprint_rounds": int(rt.state["max_same_fingerprint_rounds"]),
            "max_wave_wall_clock_minutes": int(rt.state["max_wave_wall_clock_minutes"]),
            "used_ai_review_rounds": int(rt.state["used_ai_review_rounds"]),
            "used_wall_clock_minutes": int(rt.state["used_wall_clock_minutes"]),
        },
        "derived_metrics": {
            "max_consecutive_same_fingerprint": max(
                1,
                int(_max_consecutive_fingerprint(review_records)),
            ),
            "replay_digest": replay_digest,
        },
        "dirty_tree": dirty_tree,
        "review_history_consistency": {
            "consulted_iteration_count": int(review_history_summary.get("consulted_iteration_count") or 0),
            "contradiction_count": int(review_history_summary.get("contradiction_count") or 0),
            "potential_nitpick_count": int(review_history_summary.get("potential_nitpick_count") or 0),
            "contradiction_refs": [str(x) for x in review_history_summary.get("contradiction_refs") or []],
            "nitpick_refs": [str(x) for x in review_history_summary.get("nitpick_refs") or []],
        },
        "execution": {
            "current_state": str(rt.state["current_state"]),
            "transitions": transitions,
        },
        "iterations": review_records,
        "final_decision": {
            "state": str(final_transition.get("to") or rt.state["current_state"]),
            "reason_code": str(final_transition.get("reason_code") or "REVIEW_INVALID_VERDICT"),
            "at_utc": str(final_transition.get("at_utc") or _utc_now()),
        },
        "evidence": {
            "ai_review_log_path": str(ai_review_log_path),
            "iteration_trace_path": str(iteration_trace_path),
            "final_decision_path": str(final_decision_path),
        },
    }
    if agent_profile:
        report["agent_invocation"]["agent_profile"] = agent_profile
    if strict_prompt_ref:
        report["evidence"]["ai_review_prompt_ref"] = strict_prompt_ref
    if strict_response_ref:
        report["evidence"]["ai_review_response_ref"] = strict_response_ref
    if strict_summary_ref:
        report["evidence"]["ai_review_summary_ref"] = strict_summary_ref
    return report


def _attach_optional_routing_fields(
    *,
    out: dict[str, Any],
    agent_provider: str | None,
    agent_profile: str | None,
    instruction_scope_refs: list[str] | None,
    review_history_ref: str | None,
) -> None:
    if agent_provider:
        out["agent_provider"] = agent_provider
        sig = _resolved_invocation_signature(agent_provider)
        if sig:
            out["resolved_invocation_signature"] = sig
    if agent_profile:
        out["agent_profile"] = agent_profile
    if instruction_scope_refs:
        out["instruction_scope_refs"] = instruction_scope_refs
    if review_history_ref:
        out["review_history_ref"] = review_history_ref


def _resolved_invocation_signature(agent_provider: str | None) -> str | None:
    if agent_provider == "codex_cli":
        return "codex exec review"
    if agent_provider == "claude_code":
        return "claude exec review"
    if agent_provider:
        return f"{agent_provider}:unspecified"
    return None


def _error_call(
    *,
    operation: str,
    idempotency_key: str,
    actor_identity: str,
    request: dict[str, Any],
    agent_provider: str | None,
    agent_profile: str | None,
    instruction_scope_refs: list[str] | None,
    review_history_ref: str | None,
    exc: Exception,
    trace_refs: list[str],
) -> dict[str, Any]:
    normalized = normalize_exception(exc)
    refs = list(dict.fromkeys((normalized.trace_refs or []) + trace_refs))
    out = {
        "version": "1",
        "call_id": _call_id(operation, idempotency_key),
        "api_group": "loop/runs",
        "operation": operation,
        "idempotency_key": idempotency_key,
        "actor_identity": actor_identity,
        "request": request,
        "response": {
            "status": "ERROR",
            "at_utc": _utc_now(),
            "error": normalized.to_response_error(),
            "trace_refs": refs,
        },
    }
    _attach_optional_routing_fields(
        out=out,
        agent_provider=agent_provider,
        agent_profile=agent_profile,
        instruction_scope_refs=instruction_scope_refs,
        review_history_ref=review_history_ref,
    )
    return out


def loop(
    *,
    loop_id: str,
    graph_mode: str,
    input_projection_hash: str,
    instruction_chain_hash: str,
    dependency_pin_set_id: str,
    wave_id: str | None = None,
    assurance_level: str = "FAST",
) -> dict[str, Any]:
    lvl = normalize_assurance_level(assurance_level)
    return {
        "version": "1",
        "loop_id": loop_id,
        "graph_mode": graph_mode,
        "input_projection_hash": input_projection_hash,
        "instruction_chain_hash": instruction_chain_hash,
        "dependency_pin_set_id": dependency_pin_set_id,
        "wave_id": wave_id or loop_id,
        "assurance_level": lvl.value,
    }


def serial(*nodes: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "SERIAL", "nodes": list(nodes)}


def parallel(*nodes: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "PARALLEL", "nodes": list(nodes)}


def nested(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "NESTED", "parent": parent, "child": child}


def run(
    *,
    spec: dict[str, Any],
    repo_root: Path,
    actor_identity: str,
    idempotency_key: str,
    agent_provider: str | None = None,
    agent_profile: str | None = None,
    instruction_scope_refs: list[str] | None = None,
    review_history: list[dict[str, Any]] | None = None,
    review_plan: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {"spec": spec, "repo_root": str(repo_root)}
    if review_plan is not None:
        request["review_plan_rounds"] = len(review_plan)
    review_history_ref: str | None = None
    try:
        rk = compute_run_key(
            RunKeyInput(
                loop_id=spec["loop_id"],
                graph_mode=spec["graph_mode"],
                input_projection_hash=spec["input_projection_hash"],
                instruction_chain_hash=spec["instruction_chain_hash"],
                dependency_pin_set_id=spec["dependency_pin_set_id"],
            )
        )

        try:
            rt = LoopRuntime.start(
                repo_root=repo_root,
                run_key=rk,
                wave_id=str(spec.get("wave_id") or spec["loop_id"]),
            )
        except FileExistsError:
            rt = LoopRuntime.resume(repo_root=repo_root, run_key=rk)

        trace_refs: list[str] = [str(rt.store.cache_path("state/checkpoints.jsonl"))]
        review_history_summary = summarize_review_history(review_history or [])
        review_history_summary_path = rt.store.cache_path("wave_execution/review_history_consistency.json")
        if review_history is not None:
            review_history_path = rt.store.cache_path("wave_execution/review_history.json")
            _write_json(review_history_path, review_history)
            review_history_ref = str(review_history_path)
            trace_refs.append(review_history_ref)

            _write_json(review_history_summary_path, review_history_summary)
            trace_refs.append(str(review_history_summary_path))
        elif review_plan:
            _write_json(review_history_summary_path, review_history_summary)
            trace_refs.append(str(review_history_summary_path))

        if review_plan:
            strict_prompt_ref: str | None = None
            strict_response_ref: str | None = None
            strict_summary_ref: str | None = None

            ai_log_path = rt.store.artifact_path("wave_execution/ai_review.jsonl")
            existing_records: list[dict[str, Any]] = []
            if ai_log_path.exists():
                existing_records = [
                    json.loads(ln)
                    for ln in ai_log_path.read_text(encoding="utf-8").splitlines()
                    if ln.strip()
                ]

            wall_prev = int(rt.state.get("used_wall_clock_minutes") or 0)
            next_index = int(rt.state.get("used_ai_review_rounds") or 0) + 1
            new_records: list[dict[str, Any]] = []

            for offset, planned in enumerate(review_plan):
                cur_state = str(rt.state["current_state"])
                if cur_state in {"PASSED", "FAILED", "TRIAGED"}:
                    break
                if cur_state != "RUNNING":
                    raise ValueError(f"review_plan requires RUNNING state before submit_for_review; got {cur_state}")

                idx = next_index + offset
                submit_at = _round_time(idx, submit_phase=True)
                rt.submit_for_review(at_utc=submit_at)

                verdict = str(planned.get("verdict", "REPAIRABLE")).strip().upper()
                confidence = float(planned.get("confidence", 0.5))
                finding_fingerprint = str(planned.get("finding_fingerprint") or _default_finding_fingerprint(idx, verdict))
                findings = planned.get("findings")
                if not isinstance(findings, list) or not findings:
                    findings = _default_findings(idx, verdict)

                prompt_path = rt.store.artifact_path(f"wave_execution/review_prompt_round{idx}.md")
                response_path = rt.store.artifact_path(f"wave_execution/review_response_round{idx}.md")
                summary_path_round = rt.store.artifact_path(f"wave_execution/review_summary_round{idx}.json")

                _write_text(prompt_path, f"round={idx}\nprovider={agent_provider or 'loop.runtime.default'}\n")
                _write_text(response_path, f"verdict={verdict}\nconfidence={confidence}\n")
                _write_json(
                    summary_path_round,
                    {
                        "iteration_index": idx,
                        "verdict": verdict,
                        "finding_fingerprint": finding_fingerprint,
                        "finding_count": len(findings),
                    },
                )

                strict_prompt_ref = str(prompt_path)
                strict_response_ref = str(response_path)
                strict_summary_ref = str(summary_path_round)

                wall = int(planned.get("wall_clock_used_minutes", wall_prev + 6))
                if wall <= wall_prev:
                    wall = wall_prev + 1
                max_wall = int(rt.state["max_wave_wall_clock_minutes"])
                wall = min(wall, max_wall)
                apply_at = _round_time(idx, submit_phase=False)
                to_state, reason = rt.apply_review(
                    verdict=verdict,
                    finding_fingerprint=finding_fingerprint,
                    wall_clock_used_minutes=wall,
                    at_utc=apply_at,
                )
                wall_prev = wall

                history_refs = planned.get("history_context_refs")
                if not isinstance(history_refs, list) or not history_refs:
                    history_refs = _history_context_refs(
                        iteration_index=idx,
                        review_history_summary=review_history_summary,
                    )
                history_refs = [str(x) for x in history_refs if str(x).strip()]
                if not history_refs:
                    history_refs = [f"artifacts/wave_execution/review_history_until_round{idx - 1}.json"]

                new_records.append(
                    {
                        "iteration_index": idx,
                        "ai_review": {
                            "engine": _resolved_invocation_signature(agent_provider) or "loop runtime review",
                            "prompt_ref": str(prompt_path),
                            "response_ref": str(response_path),
                            "verdict": verdict,
                            "confidence": confidence,
                            "finding_fingerprint": finding_fingerprint,
                            "findings": findings,
                        },
                        "history_context_refs": history_refs,
                        "transition": {
                            "from": "AI_REVIEW",
                            "to": to_state,
                            "reason_code": reason,
                            "at_utc": apply_at,
                        },
                        "wall_clock_used_minutes": wall,
                    }
                )

            if str(rt.state["current_state"]) not in {"PASSED", "FAILED", "TRIAGED"}:
                raise ValueError("review_plan exhausted before reaching terminal wave state")

            all_records = existing_records + new_records
            _write_jsonl(ai_log_path, all_records)
            iteration_trace_path = rt.store.artifact_path("wave_execution/iteration_trace.json")
            _write_json(iteration_trace_path, all_records)
            final_decision_path = rt.store.artifact_path("wave_execution/final_decision.json")

            report = _build_wave_execution_report(
                spec=spec,
                rt=rt,
                review_records=all_records,
                review_history_summary=review_history_summary,
                agent_provider=agent_provider,
                agent_profile=agent_profile,
                instruction_scope_refs=instruction_scope_refs,
                ai_review_log_path=ai_log_path,
                iteration_trace_path=iteration_trace_path,
                final_decision_path=final_decision_path,
                strict_prompt_ref=strict_prompt_ref,
                strict_response_ref=strict_response_ref,
                strict_summary_ref=strict_summary_ref,
                repo_root=repo_root,
            )
            ok, reason = evaluate_wave_completion_gate(report)
            if not ok:
                raise ValueError(f"assurance completion gate failed: {reason}")

            assert_wave_execution_report(report)
            _write_json(final_decision_path, report["final_decision"])
            wave_report_path = rt.store.artifact_path("wave_execution/WaveExecutionLoopRun.json")
            _write_json(wave_report_path, report)
            trace_refs.extend(
                [
                    str(ai_log_path),
                    str(iteration_trace_path),
                    str(final_decision_path),
                    str(wave_report_path),
                ]
            )
            if strict_summary_ref:
                trace_refs.append(strict_summary_ref)
        trace_refs = list(dict.fromkeys(trace_refs))

        out = {
            "version": "1",
            "call_id": _call_id("start", idempotency_key),
            "api_group": "loop/runs",
            "operation": "start",
            "idempotency_key": idempotency_key,
            "actor_identity": actor_identity,
            "request": request,
            "response": {
                "status": "OK",
                "at_utc": _utc_now(),
                "result_ref": str(rt.store.artifact_path("wave_execution/transitions.jsonl")),
                "trace_refs": trace_refs,
            },
        }
        if "assurance_level" in spec:
            out["assurance_level"] = str(spec["assurance_level"])
        _attach_optional_routing_fields(
            out=out,
            agent_provider=agent_provider,
            agent_profile=agent_profile,
            instruction_scope_refs=instruction_scope_refs,
            review_history_ref=review_history_ref,
        )
        return out
    except Exception as exc:
        checkpoint_ref = str(
            Path(repo_root).resolve()
            / ".cache"
            / "leanatlas"
            / "loop_runtime"
            / "by_key"
            / ("?" * 64)
            / "state"
            / "checkpoints.jsonl"
        )
        return _error_call(
            operation="start",
            idempotency_key=idempotency_key,
            actor_identity=actor_identity,
            request=request,
            agent_provider=agent_provider,
            agent_profile=agent_profile,
            instruction_scope_refs=instruction_scope_refs,
            review_history_ref=review_history_ref,
            exc=exc,
            trace_refs=[checkpoint_ref],
        )


def resume(
    *,
    run_key: str,
    repo_root: Path,
    actor_identity: str,
    idempotency_key: str,
    agent_provider: str | None = None,
    agent_profile: str | None = None,
    instruction_scope_refs: list[str] | None = None,
) -> dict[str, Any]:
    request = {"run_key": run_key, "repo_root": str(repo_root)}
    checkpoint_ref = str(
        Path(repo_root).resolve()
        / ".cache"
        / "leanatlas"
        / "loop_runtime"
        / "by_key"
        / run_key
        / "state"
        / "checkpoints.jsonl"
    )
    try:
        rt = LoopRuntime.resume(repo_root=repo_root, run_key=run_key)
        out = {
            "version": "1",
            "call_id": _call_id("resume", idempotency_key),
            "api_group": "loop/runs",
            "operation": "resume",
            "idempotency_key": idempotency_key,
            "actor_identity": actor_identity,
            "request": request,
            "response": {
                "status": "OK",
                "at_utc": _utc_now(),
                "result_ref": str(rt.store.artifact_path("wave_execution/transitions.jsonl")),
                "trace_refs": [checkpoint_ref],
            },
        }
        _attach_optional_routing_fields(
            out=out,
            agent_provider=agent_provider,
            agent_profile=agent_profile,
            instruction_scope_refs=instruction_scope_refs,
            review_history_ref=None,
        )
        return out
    except Exception as exc:
        return _error_call(
            operation="resume",
            idempotency_key=idempotency_key,
            actor_identity=actor_identity,
            request=request,
            agent_provider=agent_provider,
            agent_profile=agent_profile,
            instruction_scope_refs=instruction_scope_refs,
            review_history_ref=None,
            exc=exc,
            trace_refs=[checkpoint_ref],
        )
