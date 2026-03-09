#!/usr/bin/env python3
"""Deterministic parent supervisor/autopilot for child-wave batches."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .publication import (
    publish_capability_event,
    publish_supervisor_guidance_event,
    record_human_external_input,
    rematerialize_context_pack,
)
from .run_key import RunKeyInput, compute_run_key
from .store import LoopStore

_TOKEN_SANITIZER = re.compile(r"[^A-Za-z0-9._-]+")
_SUPPORTED_WAVE_KINDS = frozenset(
    {
        "HUMAN_INGRESS",
        "CAPABILITY_PUBLISH",
        "SUPERVISOR_GUIDANCE",
        "CONTEXT_REMATERIALIZE",
        "WORKTREE_PREP",
        "CALLABLE",
        "EXTERNAL_CLOSEOUT",
    }
)
_TERMINAL_STATUSES = frozenset({"PASSED", "FAILED", "TRIAGED"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _canonical_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _slug_token(raw: str, *, fallback: str) -> str:
    token = _TOKEN_SANITIZER.sub("-", str(raw).strip()).strip(".-_")
    return token or fallback


def _resolve_repo_file(repo_root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    path = path.resolve()
    repo_root = repo_root.resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"path must stay under repo_root: {raw}") from exc
    if not path.exists() or not path.is_file():
        raise ValueError(f"path must exist and be a file: {raw}")
    return path


def _normalize_repo_refs(*, repo_root: Path, refs: Sequence[str | Path], require_non_empty: bool) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in refs:
        resolved = _resolve_repo_file(repo_root, raw)
        rel = resolved.relative_to(repo_root.resolve()).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        normalized.append(rel)
    if require_non_empty and not normalized:
        raise ValueError("normalized repo refs must be non-empty")
    return normalized


def _hash_repo_file_set(*, repo_root: Path, refs: Sequence[str]) -> str:
    payload = {}
    for rel in refs:
        path = repo_root / rel
        payload[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return _canonical_hash(payload)


def _validate_completed_artifact_refs(*, repo_root: Path, result: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    normalized: dict[str, Any] = {}
    invalid_refs: list[str] = []

    normalized_result_refs: list[str] = []
    for raw_ref in result.get("result_refs") or []:
        text = str(raw_ref or "").strip()
        if not text:
            continue
        try:
            resolved = _resolve_repo_file(repo_root, text)
        except ValueError:
            invalid_refs.append(text)
            continue
        normalized_result_refs.append(resolved.relative_to(repo_root.resolve()).as_posix())
    normalized["result_refs"] = normalized_result_refs

    closeout_ref = str(result.get("closeout_ref") or "").strip()
    if closeout_ref:
        try:
            resolved_closeout = _resolve_repo_file(repo_root, closeout_ref)
        except ValueError:
            invalid_refs.append(closeout_ref)
        else:
            normalized["closeout_ref"] = resolved_closeout.relative_to(repo_root.resolve()).as_posix()

    return normalized, invalid_refs


def _coerce_nonnegative_int(raw_value: Any, *, default: int) -> int:
    if raw_value is None:
        return default
    return max(0, int(raw_value))


def _normalize_reasoning_effort(raw_value: Any) -> str:
    return str(raw_value or "").strip().lower()


def _plan_ref(store: LoopStore) -> Path:
    return store.artifact_path("batch/BatchSupervisorPlan.json")


def _state_ref(store: LoopStore) -> Path:
    return store.artifact_path("batch/BatchSupervisorState.json")


def _journal_ref(store: LoopStore) -> Path:
    return store.artifact_path("batch/BatchSupervisorJournal.jsonl")


def _progress_ref(store: LoopStore) -> Path:
    return store.artifact_path("batch/BatchSupervisorProgress.json")


def _closeout_ref(store: LoopStore) -> Path:
    return store.artifact_path("batch/BatchIntegratedCloseout.json")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(obj), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def _normalize_child_waves(child_waves: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in child_waves:
        wave = dict(raw)
        wave_id = str(wave.get("wave_id") or "").strip()
        wave_kind = str(wave.get("wave_kind") or "").strip().upper()
        if not wave_id:
            raise ValueError("child_waves[*].wave_id must be non-empty")
        if wave_id in seen_ids:
            raise ValueError(f"child_waves must not repeat wave_id `{wave_id}`")
        if wave_kind not in _SUPPORTED_WAVE_KINDS:
            raise ValueError(f"unsupported child wave kind: {wave_kind}")
        seen_ids.add(wave_id)
        normalized_wave = {
            **wave,
            "wave_id": wave_id,
            "wave_kind": wave_kind,
            "depends_on": [str(item) for item in wave.get("depends_on") or []],
            "execution_mode": str(wave.get("execution_mode") or ("WORKTREE" if wave_kind == "WORKTREE_PREP" else "INLINE")).upper(),
            "reroute_modes": [str(item).upper() for item in wave.get("reroute_modes") or []],
        }
        normalized.append(normalized_wave)
    known_ids = {wave["wave_id"] for wave in normalized}
    for wave in normalized:
        missing = sorted(set(wave["depends_on"]) - known_ids)
        if missing:
            raise ValueError(
                f"child_waves[{wave['wave_id']}] depends_on unknown wave ids: {', '.join(missing)}"
            )
    return normalized


def _write_progress(*, store: LoopStore, state: dict[str, Any]) -> Path:
    child_order = [wave["wave_id"] for wave in state["child_waves"]]
    child_by_id = {wave["wave_id"]: wave for wave in state["child_waves"]}
    completed = [wave_id for wave_id in child_order if child_by_id[wave_id]["status"] == "PASSED"]
    pending = [wave_id for wave_id in child_order if child_by_id[wave_id]["status"] == "PENDING"]
    failed = [wave_id for wave_id in child_order if child_by_id[wave_id]["status"] in {"FAILED", "TRIAGED"}]
    current_wave_id = next((wave_id for wave_id in child_order if child_by_id[wave_id]["status"] == "RUNNING"), None)
    progress = {
        "version": "1",
        "run_key": state["run_key"],
        "batch_id": state["batch_id"],
        "current_wave_id": current_wave_id,
        "completed_wave_ids": completed,
        "pending_wave_ids": pending,
        "failed_wave_ids": failed,
        "updated_at_utc": _utc_now(),
    }
    progress_path = _progress_ref(store)
    _write_json(progress_path, progress)
    return progress_path


def _load_state(*, repo_root: Path, run_key: str) -> tuple[LoopStore, dict[str, Any], dict[str, Any]]:
    store = LoopStore(repo_root=repo_root.resolve(), run_key=run_key)
    plan = _read_json(_plan_ref(store))
    state = _read_json(_state_ref(store))
    return store, plan, state


def _write_state(*, store: LoopStore, state: dict[str, Any]) -> None:
    _write_json(_state_ref(store), state)
    _write_progress(store=store, state=state)


def _state_wave(state: dict[str, Any], wave_id: str) -> dict[str, Any]:
    for wave in state["child_waves"]:
        if wave["wave_id"] == wave_id:
            return wave
    raise KeyError(wave_id)


def _wave_ancestors(plan: dict[str, Any], wave_id: str) -> list[str]:
    child_by_id = {wave["wave_id"]: wave for wave in plan["child_waves"]}
    ordered: list[str] = []
    seen: set[str] = set()

    def _visit(current: str) -> None:
        for parent in child_by_id[current].get("depends_on") or []:
            if parent in seen:
                continue
            seen.add(parent)
            _visit(parent)
            ordered.append(parent)

    _visit(wave_id)
    return ordered


def _lineage_refs(
    *,
    plan: dict[str, Any],
    state: dict[str, Any],
    wave_id: str,
    field_name: str,
    include_self: bool = False,
) -> list[str]:
    refs: list[str] = []
    lineage = _wave_ancestors(plan, wave_id)
    if include_self:
        lineage.append(wave_id)
    for ancestor in lineage:
        value = _state_wave(state, ancestor).get(field_name)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for item in value:
                text = str(item or "").strip()
                if text and text not in refs:
                    refs.append(text)
            continue
        text = str(value or "").strip()
        if text and text not in refs:
            refs.append(text)
    return refs


def _upstream_result_summary(
    *, plan: dict[str, Any], state: dict[str, Any], wave_id: str, include_self: bool = False
) -> dict[str, Any]:
    return {
        "publication_event_refs": _lineage_refs(
            plan=plan,
            state=state,
            wave_id=wave_id,
            field_name="publication_ref",
            include_self=include_self,
        ),
        "human_ingress_event_refs": _lineage_refs(
            plan=plan,
            state=state,
            wave_id=wave_id,
            field_name="ingress_ref",
            include_self=include_self,
        ),
        "supervisor_guidance_event_refs": _lineage_refs(
            plan=plan,
            state=state,
            wave_id=wave_id,
            field_name="supervisor_guidance_refs",
            include_self=include_self,
        ),
        "context_pack_refs": _lineage_refs(
            plan=plan,
            state=state,
            wave_id=wave_id,
            field_name="context_pack_ref",
            include_self=include_self,
        ),
        "worktree_refs": _lineage_refs(
            plan=plan,
            state=state,
            wave_id=wave_id,
            field_name="worktree_ref",
            include_self=include_self,
        ),
    }


@dataclass
class BatchWaveRetryableError(RuntimeError):
    message: str
    reroute_to: str | None = None
    reason_code: str = "RETRYABLE_WAVE_FAILURE"
    retry_same_mode: bool = False
    progress_class: str | None = None
    reminder_summary: str | None = None
    reminder_message: str | None = None
    known_conclusion_refs: Sequence[str] = ()
    non_goal_refs: Sequence[str] = ()

    def __str__(self) -> str:
        return self.message


WaveExecutor = Callable[[dict[str, Any]], Mapping[str, Any]]


def materialize_batch_supervisor(
    *,
    repo_root: Path,
    batch_id: str,
    execplan_ref: str | Path,
    child_waves: Sequence[Mapping[str, Any]],
    instruction_scope_refs: Sequence[str | Path],
    required_context_refs: Sequence[str | Path],
    dependency_pin_set_id: str = "maintainer.repo_local.v1",
) -> dict[str, str]:
    repo_root = Path(repo_root).resolve()
    normalized_execplan = _normalize_repo_refs(repo_root=repo_root, refs=[execplan_ref], require_non_empty=True)[0]
    normalized_instruction = _normalize_repo_refs(
        repo_root=repo_root,
        refs=instruction_scope_refs,
        require_non_empty=True,
    )
    normalized_required_context = _normalize_repo_refs(
        repo_root=repo_root,
        refs=required_context_refs,
        require_non_empty=True,
    )
    normalized_child_waves = _normalize_child_waves(child_waves)
    execplan_hash = _hash_repo_file_set(repo_root=repo_root, refs=[normalized_execplan])
    required_context_hash = _hash_repo_file_set(repo_root=repo_root, refs=normalized_required_context)
    instruction_chain_hash = _hash_repo_file_set(repo_root=repo_root, refs=normalized_instruction)
    input_projection_hash = _canonical_hash(
        {
            "batch_id": str(batch_id),
            "execplan_ref": normalized_execplan,
            "execplan_hash": execplan_hash,
            "required_context_refs": normalized_required_context,
            "required_context_hash": required_context_hash,
            "child_waves": normalized_child_waves,
        }
    )
    run_key = compute_run_key(
        RunKeyInput(
            loop_id=f"loop.batch_supervisor.{_slug_token(str(batch_id), fallback='batch')}",
            graph_mode="STATIC_USER_MODE",
            input_projection_hash=input_projection_hash,
            instruction_chain_hash=instruction_chain_hash,
            dependency_pin_set_id=dependency_pin_set_id,
        )
    )
    store = LoopStore(repo_root=repo_root, run_key=run_key)
    store.ensure_layout()
    plan_path = _plan_ref(store)
    state_path = _state_ref(store)
    journal_path = _journal_ref(store)
    progress_path = _progress_ref(store)
    plan = {
        "version": "1",
        "run_key": run_key,
        "batch_id": str(batch_id),
        "execplan_ref": normalized_execplan,
        "instruction_scope_refs": normalized_instruction,
        "required_context_refs": normalized_required_context,
        "dependency_pin_set_id": dependency_pin_set_id,
        "child_waves": normalized_child_waves,
    }
    state = {
        "version": "1",
        "run_key": run_key,
        "batch_id": str(batch_id),
        "child_waves": [
            {
                **wave,
                "status": "PENDING",
                "attempt_count": 0,
                "result_refs": [],
            }
            for wave in normalized_child_waves
        ],
    }
    if plan_path.exists() or state_path.exists():
        if not (plan_path.exists() and state_path.exists() and journal_path.exists()):
            raise ValueError(
                "existing batch supervisor run is incomplete; missing one of plan/state/journal artifacts"
            )
        existing_plan = _read_json(plan_path)
        if existing_plan != plan:
            raise ValueError("existing batch supervisor plan does not match rematerialized frozen inputs")
        existing_state = _read_json(state_path)
        if (
            str(existing_state.get("run_key") or "") != run_key
            or str(existing_state.get("batch_id") or "") != str(batch_id)
        ):
            raise ValueError("existing batch supervisor state does not match the rematerialized run identity")
        if not progress_path.exists():
            _write_progress(store=store, state=existing_state)
        return {
            "run_key": run_key,
            "plan_ref": str(plan_path),
            "state_ref": str(state_path),
            "journal_ref": str(journal_path),
            "progress_ref": str(progress_path),
        }

    _write_json(plan_path, plan)
    _write_state(store=store, state=state)
    _append_jsonl(
        journal_path,
        {
            "entry_kind": "BATCH_SUPERVISOR_STARTED",
            "at_utc": _utc_now(),
            "run_key": run_key,
            "batch_id": str(batch_id),
            "execplan_ref": normalized_execplan,
            "pending_wave_ids": [wave["wave_id"] for wave in normalized_child_waves],
        },
    )
    return {
        "run_key": run_key,
        "plan_ref": str(plan_path),
        "state_ref": str(state_path),
        "journal_ref": str(journal_path),
        "progress_ref": str(progress_path),
    }


def _execute_builtin_wave(*, repo_root: Path, plan: dict[str, Any], state: dict[str, Any], wave: dict[str, Any]) -> dict[str, Any]:
    wave_id = str(wave["wave_id"])
    wave_kind = str(wave["wave_kind"])
    if wave_kind == "HUMAN_INGRESS":
        ingress = record_human_external_input(
            repo_root=repo_root,
            ingress_id=wave_id,
            producer_id=str(wave.get("producer_id") or "user"),
            source_label=str(wave.get("source_label") or wave_id),
            summary=str(wave.get("summary") or wave_id),
            evidence_refs=[str(item) for item in wave.get("evidence_refs") or []],
            related_context_refs=plan["required_context_refs"],
        )
        return {
            "ingress_ref": ingress["event_ref"],
            "result_refs": [ingress["event_ref"]],
        }
    if wave_kind == "CAPABILITY_PUBLISH":
        publication = publish_capability_event(
            repo_root=repo_root,
            publication_id=wave_id,
            producer_id=str(wave.get("producer_id") or "batch_supervisor"),
            summary=str(wave.get("summary") or wave_id),
            resource_refs=[str(item) for item in wave.get("resource_refs") or []],
            capability_kind=str(wave.get("capability_kind") or "CAPABILITY"),
        )
        return {
            "publication_ref": publication["event_ref"],
            "result_refs": [publication["event_ref"]],
        }
    if wave_kind == "SUPERVISOR_GUIDANCE":
        guidance = publish_supervisor_guidance_event(
            repo_root=repo_root,
            guidance_id=wave_id,
            producer_id=str(wave.get("producer_id") or "batch_supervisor"),
            summary=str(wave.get("summary") or wave_id),
            reminder_message=str(wave.get("reminder_message") or ""),
            known_conclusion_refs=[str(item) for item in wave.get("known_conclusion_refs") or []],
            non_goal_refs=[str(item) for item in wave.get("non_goal_refs") or []],
        )
        return {
            "supervisor_guidance_refs": [guidance["event_ref"]],
            "result_refs": [guidance["event_ref"]],
        }
    if wave_kind == "CONTEXT_REMATERIALIZE":
        upstream = _upstream_result_summary(plan=plan, state=state, wave_id=wave_id)
        context_pack = rematerialize_context_pack(
            repo_root=repo_root,
            context_id=wave_id,
            consumer_id=str(wave.get("consumer_id") or wave_id),
            base_context_refs=[str(item) for item in wave.get("base_context_refs") or plan["required_context_refs"]],
            publication_event_refs=upstream["publication_event_refs"],
            human_ingress_event_refs=upstream["human_ingress_event_refs"],
            supervisor_guidance_event_refs=upstream["supervisor_guidance_event_refs"],
        )
        return {
            "context_pack_ref": context_pack["context_pack_ref"],
            "result_refs": [context_pack["context_pack_ref"]],
        }
    if wave_kind == "WORKTREE_PREP":
        from .worktree_adapter import materialize_worktree_child

        worktree = materialize_worktree_child(
            repo_root=repo_root,
            batch_id=str(plan["batch_id"]),
            wave_id=wave_id,
            base_ref=str(wave.get("base_ref") or "HEAD"),
        )
        return {
            "worktree_ref": worktree["metadata_ref"],
            "worktree_path": worktree["worktree_path"],
            "result_refs": [worktree["metadata_ref"]],
        }
    raise KeyError(wave_kind)


def _integrated_closeout(*, store: LoopStore, state: dict[str, Any]) -> dict[str, Any]:
    child_waves = [dict(wave) for wave in state["child_waves"]]
    authoritative = next(
        (wave for wave in reversed(child_waves) if str(wave.get("closeout_ref") or "").strip()),
        child_waves[-1] if child_waves else None,
    )
    child_statuses = {str(wave.get("status") or "") for wave in child_waves}
    if "TRIAGED" in child_statuses:
        final_status = "TRIAGED"
    elif "FAILED" in child_statuses:
        final_status = "FAILED"
    else:
        final_status = "PASSED"
    closeout = {
        "version": "1",
        "run_key": state["run_key"],
        "batch_id": state["batch_id"],
        "generated_at_utc": _utc_now(),
        "final_status": final_status,
        "publication_wave_ids": [wave["wave_id"] for wave in child_waves if str(wave.get("publication_ref") or "").strip()],
        "supervisor_guidance_wave_ids": [
            wave["wave_id"] for wave in child_waves if list(wave.get("supervisor_guidance_refs") or [])
        ],
        "context_wave_ids": [wave["wave_id"] for wave in child_waves if str(wave.get("context_pack_ref") or "").strip()],
        "worktree_wave_ids": [wave["wave_id"] for wave in child_waves if str(wave.get("worktree_ref") or "").strip()],
        "authoritative_child_wave_id": authoritative.get("wave_id") if authoritative else None,
        "authoritative_closeout_ref": authoritative.get("closeout_ref") if authoritative else None,
        "child_results": {
            wave["wave_id"]: {
                "status": wave["status"],
                "execution_mode": wave["execution_mode"],
                "attempt_count": wave["attempt_count"],
                "result_refs": list(wave.get("result_refs") or []),
                "closeout_ref": wave.get("closeout_ref"),
                "publication_ref": wave.get("publication_ref"),
                "ingress_ref": wave.get("ingress_ref"),
                "supervisor_guidance_refs": list(wave.get("supervisor_guidance_refs") or []),
                "context_pack_ref": wave.get("context_pack_ref"),
                "followup_context_pack_refs": list(wave.get("followup_context_pack_refs") or []),
                "worktree_ref": wave.get("worktree_ref"),
            }
            for wave in child_waves
        },
    }
    _write_json(_closeout_ref(store), closeout)
    return closeout


def execute_batch_supervisor(
    *,
    repo_root: Path,
    run_key: str,
    wave_executors: Mapping[str, WaveExecutor] | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    store, plan, state = _load_state(repo_root=repo_root, run_key=run_key)
    journal_path = _journal_ref(store)
    child_order = [wave["wave_id"] for wave in state["child_waves"]]
    child_by_id = {wave["wave_id"]: wave for wave in state["child_waves"]}

    def _wave_supervision_policy(current_wave: dict[str, Any]) -> dict[str, Any]:
        raw = dict(current_wave.get("supervision_policy") or {})
        executor_reasoning_effort = _normalize_reasoning_effort(
            raw.get("executor_reasoning_effort") or current_wave.get("agent_profile")
        )
        default_context_rebuild_retries = 1 if executor_reasoning_effort == "xhigh" else 0
        allow_context_rebuild_retries = _coerce_nonnegative_int(
            raw.get("allow_context_rebuild_retries"),
            default=default_context_rebuild_retries,
        )
        max_no_milestone_retries = _coerce_nonnegative_int(
            raw.get("max_no_milestone_retries"),
            default=0,
        )
        followup_base_context_refs = [str(item) for item in raw.get("followup_base_context_refs") or plan["required_context_refs"]]
        return {
            "executor_reasoning_effort": executor_reasoning_effort,
            "allow_context_rebuild_retries": allow_context_rebuild_retries,
            "max_no_milestone_retries": max_no_milestone_retries,
            "followup_base_context_refs": followup_base_context_refs,
        }

    def _append_unique(existing: list[str], new_items: Sequence[str]) -> list[str]:
        out = list(existing)
        for item in new_items:
            text = str(item or "").strip()
            if text and text not in out:
                out.append(text)
        return out

    resumed_running_waves = False
    for wave_id in child_order:
        wave = child_by_id[wave_id]
        if wave["status"] != "RUNNING":
            continue
        wave["status"] = "PENDING"
        _append_jsonl(
            journal_path,
            {
                "entry_kind": "CHILD_WAVE_REQUEUED",
                "at_utc": _utc_now(),
                "wave_id": wave_id,
                "reason_code": "INTERRUPTED_RUNNING_STATE",
                "attempt_count": int(wave.get("attempt_count") or 0),
            },
        )
        resumed_running_waves = True
    if resumed_running_waves:
        _write_state(store=store, state=state)

    while True:
        pending_ids = [wave_id for wave_id in child_order if child_by_id[wave_id]["status"] == "PENDING"]
        if not pending_ids:
            break
        progressed = False
        for wave_id in pending_ids:
            wave = child_by_id[wave_id]
            dependencies = [child_by_id[parent_id] for parent_id in wave.get("depends_on") or []]
            if any(parent["status"] in {"FAILED", "TRIAGED"} for parent in dependencies):
                wave["status"] = "TRIAGED"
                _append_jsonl(
                    journal_path,
                    {
                        "entry_kind": "CHILD_WAVE_TRIAGED",
                        "at_utc": _utc_now(),
                        "wave_id": wave_id,
                        "reason_code": "UPSTREAM_BLOCKED",
                    },
                )
                _write_state(store=store, state=state)
                progressed = True
                break
            if not all(parent["status"] == "PASSED" for parent in dependencies):
                continue
            wave["status"] = "RUNNING"
            wave["attempt_count"] = int(wave.get("attempt_count") or 0) + 1
            _append_jsonl(
                journal_path,
                {
                    "entry_kind": "CHILD_WAVE_STARTED",
                    "at_utc": _utc_now(),
                    "wave_id": wave_id,
                    "execution_mode": wave["execution_mode"],
                    "attempt_count": wave["attempt_count"],
                },
            )
            _write_state(store=store, state=state)
            try:
                if wave["wave_kind"] in {
                    "HUMAN_INGRESS",
                    "CAPABILITY_PUBLISH",
                    "SUPERVISOR_GUIDANCE",
                    "CONTEXT_REMATERIALIZE",
                    "WORKTREE_PREP",
                }:
                    result = _execute_builtin_wave(repo_root=repo_root, plan=plan, state=state, wave=wave)
                elif wave["wave_kind"] == "CALLABLE":
                    executor = (wave_executors or {}).get(wave_id)
                    if executor is None:
                        raise RuntimeError(f"no executor supplied for callable child wave `{wave_id}`")
                    result = dict(
                        executor(
                            {
                                **wave,
                                "batch_id": plan["batch_id"],
                                "run_key": run_key,
                                "upstream_results": _upstream_result_summary(
                                    plan=plan,
                                    state=state,
                                    wave_id=wave_id,
                                    include_self=True,
                                ),
                            }
                        )
                    )
                elif wave["wave_kind"] == "EXTERNAL_CLOSEOUT":
                    closeout_ref = str(wave.get("closeout_ref") or "").strip()
                    if not closeout_ref:
                        raise RuntimeError("EXTERNAL_CLOSEOUT wave requires closeout_ref")
                    result = {"closeout_ref": closeout_ref, "result_refs": [closeout_ref]}
                else:
                    raise RuntimeError(f"unsupported child wave kind at runtime: {wave['wave_kind']}")
            except BatchWaveRetryableError as exc:
                retry_same_mode = bool(exc.retry_same_mode)
                progress_class = str(exc.progress_class or "").strip().upper()
                supervision_policy = _wave_supervision_policy(wave)
                if retry_same_mode:
                    if progress_class == "CONTEXT_REBUILD":
                        used = int(wave.get("context_rebuild_retry_count") or 0)
                        if used < supervision_policy["allow_context_rebuild_retries"]:
                            wave["context_rebuild_retry_count"] = used + 1
                            wave["status"] = "PENDING"
                            _append_jsonl(
                                journal_path,
                                {
                                    "entry_kind": "CHILD_WAVE_CONTEXT_REBUILD_CONTINUED",
                                    "at_utc": _utc_now(),
                                    "wave_id": wave_id,
                                    "reason_code": str(exc.reason_code or "CONTEXT_REBUILD"),
                                    "attempt_count": wave["attempt_count"],
                                },
                            )
                            _write_state(store=store, state=state)
                            progressed = True
                            break
                        wave["status"] = "TRIAGED"
                        wave["last_error"] = str(exc)
                        _append_jsonl(
                            journal_path,
                            {
                                "entry_kind": "CHILD_WAVE_TRIAGED",
                                "at_utc": _utc_now(),
                                "wave_id": wave_id,
                                "reason_code": "CONTEXT_REBUILD_BUDGET_EXHAUSTED",
                                "attempt_count": wave["attempt_count"],
                            },
                        )
                        _write_state(store=store, state=state)
                        progressed = True
                        break
                    if progress_class == "NO_MILESTONE_PROGRESS":
                        used = int(wave.get("no_milestone_retry_count") or 0)
                        if used < supervision_policy["max_no_milestone_retries"]:
                            reminder_summary = str(exc.reminder_summary or "").strip() or f"Reminder for {wave_id}"
                            reminder_message = str(exc.reminder_message or "").strip() or (
                                "Known conclusions and non-goals are now explicit; move from analysis into bounded work."
                            )
                            guidance = publish_supervisor_guidance_event(
                                repo_root=repo_root,
                                guidance_id=f"{wave_id}.followup.{used + 1}",
                                producer_id="batch_supervisor",
                                summary=reminder_summary,
                                reminder_message=reminder_message,
                                known_conclusion_refs=[str(item) for item in exc.known_conclusion_refs],
                                non_goal_refs=[str(item) for item in exc.non_goal_refs],
                            )
                            wave["supervisor_guidance_refs"] = _append_unique(
                                list(wave.get("supervisor_guidance_refs") or []),
                                [guidance["event_ref"]],
                            )
                            followup_upstream = _upstream_result_summary(
                                plan=plan,
                                state=state,
                                wave_id=wave_id,
                                include_self=True,
                            )
                            context_pack = rematerialize_context_pack(
                                repo_root=repo_root,
                                context_id=f"{wave_id}.followup.{used + 1}",
                                consumer_id=wave_id,
                                base_context_refs=supervision_policy["followup_base_context_refs"],
                                publication_event_refs=followup_upstream["publication_event_refs"],
                                human_ingress_event_refs=followup_upstream["human_ingress_event_refs"],
                                supervisor_guidance_event_refs=followup_upstream["supervisor_guidance_event_refs"],
                            )
                            wave["context_pack_ref"] = context_pack["context_pack_ref"]
                            wave["followup_context_pack_refs"] = _append_unique(
                                list(wave.get("followup_context_pack_refs") or []),
                                [context_pack["context_pack_ref"]],
                            )
                            wave["no_milestone_retry_count"] = used + 1
                            wave["status"] = "PENDING"
                            _append_jsonl(
                                journal_path,
                                {
                                    "entry_kind": "CHILD_WAVE_REMINDER_REQUESTED",
                                    "at_utc": _utc_now(),
                                    "wave_id": wave_id,
                                    "reason_code": str(exc.reason_code or "NO_MILESTONE_PROGRESS"),
                                    "attempt_count": wave["attempt_count"],
                                    "supervisor_guidance_ref": guidance["event_ref"],
                                    "context_pack_ref": context_pack["context_pack_ref"],
                                },
                            )
                            _write_state(store=store, state=state)
                            progressed = True
                            break
                        wave["status"] = "TRIAGED"
                        wave["last_error"] = str(exc)
                        _append_jsonl(
                            journal_path,
                            {
                                "entry_kind": "CHILD_WAVE_TRIAGED",
                                "at_utc": _utc_now(),
                                "wave_id": wave_id,
                                "reason_code": "NO_MILESTONE_DRIFT_BUDGET_EXHAUSTED",
                                "attempt_count": wave["attempt_count"],
                            },
                        )
                        _write_state(store=store, state=state)
                        progressed = True
                        break
                reroute_to = str(exc.reroute_to or "").upper()
                if reroute_to and reroute_to in set(wave.get("reroute_modes") or []):
                    wave["execution_mode"] = reroute_to
                    wave["status"] = "PENDING"
                    _append_jsonl(
                        journal_path,
                        {
                            "entry_kind": "CHILD_WAVE_REROUTED",
                            "at_utc": _utc_now(),
                            "wave_id": wave_id,
                            "reason_code": str(exc.reason_code or "RETRYABLE_WAVE_FAILURE"),
                            "selected_execution_mode": reroute_to,
                            "attempt_count": wave["attempt_count"],
                        },
                    )
                    _write_state(store=store, state=state)
                    progressed = True
                    break
                wave["status"] = "FAILED"
                wave["last_error"] = str(exc)
                _append_jsonl(
                    journal_path,
                    {
                        "entry_kind": "CHILD_WAVE_FAILED",
                        "at_utc": _utc_now(),
                        "wave_id": wave_id,
                        "reason_code": str(exc.reason_code or "RETRYABLE_WAVE_FAILURE"),
                    },
                )
                _write_state(store=store, state=state)
                progressed = True
                break
            except Exception as exc:  # noqa: BLE001
                wave["status"] = "FAILED"
                wave["last_error"] = str(exc)
                _append_jsonl(
                    journal_path,
                    {
                        "entry_kind": "CHILD_WAVE_FAILED",
                        "at_utc": _utc_now(),
                        "wave_id": wave_id,
                        "reason_code": "UNHANDLED_EXCEPTION",
                        "message": str(exc),
                    },
                )
                _write_state(store=store, state=state)
                progressed = True
                break

            validated_result, invalid_artifact_refs = _validate_completed_artifact_refs(
                repo_root=repo_root,
                result=result,
            )
            if invalid_artifact_refs:
                wave["status"] = "TRIAGED"
                wave["last_error"] = "missing or invalid artifact refs: " + ", ".join(invalid_artifact_refs)
                _append_jsonl(
                    journal_path,
                    {
                        "entry_kind": "CHILD_WAVE_TRIAGED",
                        "at_utc": _utc_now(),
                        "wave_id": wave_id,
                        "reason_code": "INVALID_ARTIFACT_REFS",
                        "attempt_count": wave["attempt_count"],
                        "artifact_refs": invalid_artifact_refs,
                    },
                )
                _write_state(store=store, state=state)
                progressed = True
                break

            wave["status"] = "PASSED"
            wave["result_refs"] = list(validated_result.get("result_refs") or [])
            for key in (
                "closeout_ref",
                "publication_ref",
                "ingress_ref",
                "context_pack_ref",
                "worktree_ref",
                "worktree_path",
            ):
                if key == "closeout_ref":
                    if key in validated_result and validated_result[key] is not None:
                        wave[key] = str(validated_result[key])
                    continue
                if key in result and result[key] is not None:
                    wave[key] = str(result[key])
            if "supervisor_guidance_refs" in result:
                wave["supervisor_guidance_refs"] = _append_unique(
                    list(wave.get("supervisor_guidance_refs") or []),
                    [str(item) for item in result.get("supervisor_guidance_refs") or []],
                )
            _append_jsonl(
                journal_path,
                {
                    "entry_kind": "CHILD_WAVE_COMPLETED",
                    "at_utc": _utc_now(),
                    "wave_id": wave_id,
                    "execution_mode": wave["execution_mode"],
                    "attempt_count": wave["attempt_count"],
                    "result_refs": wave["result_refs"],
                    "closeout_ref": wave.get("closeout_ref"),
                },
            )
            _write_state(store=store, state=state)
            progressed = True
            break
        if not progressed:
            raise RuntimeError("batch supervisor made no progress; unresolved dependency cycle or missing executor")
    closeout = _integrated_closeout(store=store, state=state)
    return {
        "run_key": run_key,
        "final_status": closeout["final_status"],
        "closeout_ref": str(_closeout_ref(store)),
        "journal_ref": str(journal_path),
        "progress_ref": str(_progress_ref(store)),
    }


def load_batch_supervisor(*, repo_root: Path, run_key: str) -> dict[str, Any]:
    store, plan, state = _load_state(repo_root=Path(repo_root).resolve(), run_key=run_key)
    progress = _read_json(_progress_ref(store))
    return {
        "run_key": run_key,
        "plan": plan,
        "state": state,
        "child_waves": {wave["wave_id"]: dict(wave) for wave in state["child_waves"]},
        "progress": progress,
        "journal_ref": str(_journal_ref(store)),
        "closeout_ref": str(_closeout_ref(store)) if _closeout_ref(store).exists() else None,
    }


__all__ = [
    "BatchWaveRetryableError",
    "execute_batch_supervisor",
    "load_batch_supervisor",
    "materialize_batch_supervisor",
]
