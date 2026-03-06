#!/usr/bin/env python3
"""Helpers for deterministic maintainer LOOP execution artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .graph_runtime import LoopGraphRuntime
from .presets import build_maintainer_change_graph
from .run_key import RunKeyInput, compute_run_key
from .store import LoopStore

_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_TERMINAL_STATES = {"PASSED", "FAILED", "TRIAGED"}
_SOURCE_ROOT = Path(__file__).resolve().parents[2]


def _require_jsonschema() -> Any:
    try:
        import jsonschema
    except Exception as exc:  # pragma: no cover - exercised via subprocess contract check
        raise RuntimeError(
            "execute_recorded_graph requires jsonschema; run via `uv run --locked` or install jsonschema."
        ) from exc
    return jsonschema


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _resolve_repo_file(repo_root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    path = path.resolve()
    repo_resolved = repo_root.resolve()
    try:
        path.relative_to(repo_resolved)
    except ValueError as exc:
        raise ValueError(f"path must stay under repo_root: {raw}") from exc
    if not path.exists():
        raise ValueError(f"path does not exist: {raw}")
    if not path.is_file():
        raise ValueError(f"path must be a file: {raw}")
    return path


def _normalize_repo_file_refs(
    *,
    repo_root: Path,
    refs: Sequence[str | Path],
    field_name: str,
    require_non_empty: bool = False,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in refs:
        resolved = _resolve_repo_file(repo_root, raw)
        rel = resolved.relative_to(repo_root.resolve()).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        normalized.append(rel)
    normalized.sort()
    if require_non_empty and not normalized:
        raise ValueError(f"{field_name} must be a non-empty sequence of repo files")
    return normalized


def _expected_instruction_scope_chain(*, repo_root: Path, active_repo_files: Sequence[str]) -> list[str]:
    repo_root = repo_root.resolve()
    expected: set[str] = set()
    for rel in active_repo_files:
        current = (repo_root / rel).resolve().parent
        while True:
            candidate = current / "AGENTS.md"
            if candidate.exists() and candidate.is_file():
                expected.add(candidate.relative_to(repo_root).as_posix())
            if current == repo_root:
                break
            current = current.parent
    return sorted(expected)


def _normalize_instruction_scope_refs(
    *,
    repo_root: Path,
    instruction_scope_refs: Sequence[str | Path],
    active_repo_files: Sequence[str],
) -> list[str]:
    provided = _normalize_repo_file_refs(
        repo_root=repo_root,
        refs=instruction_scope_refs,
        field_name="instruction_scope_refs",
        require_non_empty=True,
    )
    expected_chain = _expected_instruction_scope_chain(
        repo_root=repo_root,
        active_repo_files=active_repo_files,
    )
    missing = [ref for ref in expected_chain if ref not in provided]
    if missing:
        raise ValueError(
            "instruction_scope_refs must include the active AGENTS.md chain; "
            f"missing: {', '.join(missing)}"
        )
    return expected_chain


def _normalize_required_context_refs(
    *,
    repo_root: Path,
    required_context_refs: Sequence[str | Path],
    scope_paths: Sequence[str],
) -> list[str]:
    normalized = _normalize_repo_file_refs(
        repo_root=repo_root,
        refs=required_context_refs,
        field_name="required_context_refs",
        require_non_empty=True,
    )
    overlapping = sorted(set(normalized) & set(scope_paths))
    if overlapping:
        raise ValueError(
            "required_context_refs must stay disjoint from scope_paths because maintainer run identity "
            "cannot depend on mutable scoped file bytes; overlapping refs: "
            + ", ".join(overlapping)
    )
    return normalized


def _validate_execplan_disjoint_from_scope(*, execplan_ref: str, scope_paths: Sequence[str]) -> None:
    if execplan_ref in set(scope_paths):
        raise ValueError(
            "execplan_ref must stay disjoint from scope_paths because the frozen ExecPlan cannot also be a mutable "
            "scoped file; overlapping ref: "
            + execplan_ref
        )


def _hash_repo_file_set(*, repo_root: Path, refs: Sequence[str]) -> str:
    payload = {rel: _sha256_file(repo_root / rel) for rel in refs}
    return _canonical_hash(payload)


def _canonical_node_results(
    *, graph_spec: dict[str, Any], node_results: dict[str, dict[str, object]]
) -> dict[str, dict[str, object]]:
    node_ids = [str(node["node_id"]) for node in graph_spec.get("nodes") or []]
    actual = set(node_results)
    unexpected = sorted(actual - set(node_ids))
    if unexpected:
        raise ValueError(f"unexpected node_results keys: {', '.join(unexpected)}")

    canonical: dict[str, dict[str, object]] = {}
    for node_id in node_ids:
        if node_id not in node_results:
            continue
        raw = dict(node_results[node_id])
        state = str(raw.get("state", "")).strip()
        if state not in _TERMINAL_STATES:
            raise ValueError(f"node_results[{node_id!r}].state must be one of {_TERMINAL_STATES}")
        result: dict[str, object] = {
            "state": state,
            "reason_code": str(raw.get("reason_code") or "NODE_EXEC_RESULT"),
        }
        run_key = raw.get("run_key")
        if run_key is not None:
            run_key_str = str(run_key)
            if not _HEX64.fullmatch(run_key_str):
                raise ValueError(f"node_results[{node_id!r}].run_key must be 64-char lowercase hex")
            result["run_key"] = run_key_str
        canonical[node_id] = result
    return canonical


def _validate_graph_spec(*, repo_root: Path, graph_spec: dict[str, object]) -> dict[str, object]:
    jsonschema = _require_jsonschema()
    schema_path = repo_root / "docs" / "schemas" / "LoopGraphSpec.schema.json"
    if not schema_path.exists():
        schema_path = _SOURCE_ROOT / "docs" / "schemas" / "LoopGraphSpec.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
    )
    errors = sorted(validator.iter_errors(graph_spec), key=lambda err: list(err.absolute_path))
    if errors:
        joined = "; ".join(
            f"/{'/'.join(str(token) for token in err.absolute_path)}: {err.message}" for err in errors
        )
        raise ValueError(f"graph_spec must validate against LoopGraphSpec.schema.json: {joined}")
    return dict(graph_spec)


def _actual_node_results(summary: dict[str, object]) -> dict[str, dict[str, object]]:
    actual: dict[str, dict[str, object]] = {}
    for decision in summary.get("node_decisions") or []:
        node_id = str(decision["node_id"])
        result: dict[str, object] = {
            "state": str(decision["state"]),
            "reason_code": str(decision["reason_code"]),
        }
        run_key = decision.get("run_key")
        if run_key is not None:
            result["run_key"] = str(run_key)
        actual[node_id] = result
    return actual


def _validate_maintainer_closeout(summary: dict[str, object]) -> None:
    decisions = {str(decision["node_id"]): dict(decision) for decision in summary.get("node_decisions") or []}
    ai_review = decisions.get("ai_review_node")
    closeout = decisions.get("loop_closeout")
    if ai_review is None or closeout is None:
        return
    ai_state = str(ai_review.get("state") or "")
    closeout_state = str(closeout.get("state") or "")
    if ai_state != closeout_state:
        raise ValueError(
            "maintainer closeout must preserve ai_review_node terminal state "
            f"(ai_review_node={ai_state}, loop_closeout={closeout_state})"
        )


def _write_json_if_absent_or_equal(
    *, store: LoopStore, rel: str, obj: Any, stream: str = "artifact"
) -> Path:
    path = store.artifact_path(rel) if stream == "artifact" else store.cache_path(rel)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != obj:
            raise FileExistsError(f"write-once path already exists with different content: {path}")
        return path
    return store.write_once_json(rel, obj, stream=stream)


def _append_jsonl_if_absent_or_equal_first(
    *, store: LoopStore, rel: str, first_obj: Any, stream: str = "artifact"
) -> Path:
    path = store.artifact_path(rel) if stream == "artifact" else store.cache_path(rel)
    if path.exists():
        first_line = next(
            (line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()),
            None,
        )
        if first_line is None:
            raise ValueError(f"append-only journal exists but is empty: {path}")
        existing = json.loads(first_line)
        if all(key in existing and key in first_obj for key in ("at_utc",)):
            existing = {k: v for k, v in existing.items() if k != "at_utc"}
            first_obj = {k: v for k, v in dict(first_obj).items() if k != "at_utc"}
        if existing != first_obj:
            raise FileExistsError(f"append-only journal already exists with different first entry: {path}")
        return path
    return store.append_jsonl(rel, first_obj, stream=stream)


def _last_jsonl_obj(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    return dict(json.loads(lines[-1]))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [dict(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json_overwrite(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _progress_snapshot(
    *,
    graph_spec: dict[str, Any],
    session: dict[str, Any],
    journal: Sequence[dict[str, Any]],
    final_status: str | None = None,
    summary_ref: str | None = None,
) -> dict[str, Any]:
    node_order = [str(node_id) for node_id in session.get("node_order") or []]
    terminal_by_node = {
        str(entry.get("node_id")): str(entry.get("state"))
        for entry in journal
        if entry.get("entry_kind") == "NODE_TERMINAL_RESULT"
    }
    resolved_terminal_by_node, _effective_terminal_by_node = _resolved_terminal_states(
        graph_spec=graph_spec,
        terminal_by_node=terminal_by_node,
    )
    blocked_node_ids = [
        node_id
        for node_id in node_order
        if node_id not in terminal_by_node and resolved_terminal_by_node.get(node_id) in {"FAILED", "TRIAGED"}
    ]
    completed = [node_id for node_id in node_order if node_id in terminal_by_node]
    pending = [node_id for node_id in node_order if node_id not in completed and node_id not in blocked_node_ids]
    last_progress_at = next(
        (
            str(entry.get("at_utc"))
            for entry in reversed(list(journal))
            if isinstance(entry.get("at_utc"), str) and entry.get("at_utc")
        ),
        str(session.get("created_at_utc") or _utc_now()),
    )
    snapshot: dict[str, Any] = {
        "version": "1",
        "updated_at_utc": last_progress_at,
        "run_key": str(session["run_key"]),
        "graph_spec_ref": str(session["graph_spec_ref"]),
        "session_ref": str(session.get("session_ref") or ""),
        "node_journal_ref": str(session["node_journal_ref"]),
        "node_order": node_order,
        "completed_node_ids": completed,
        "pending_node_ids": pending,
        "current_node_id": pending[0] if pending else None,
    }
    if blocked_node_ids:
        snapshot["blocked_node_ids"] = blocked_node_ids
    if final_status is not None:
        snapshot["final_status"] = final_status
    if summary_ref is not None:
        snapshot["summary_ref"] = summary_ref
    return snapshot


def _write_progress_snapshot(
    *,
    store: LoopStore,
    session: dict[str, Any],
    final_status: str | None = None,
    summary_ref: str | None = None,
) -> Path:
    journal = _read_jsonl(store.artifact_path("graph/NodeJournal.jsonl"))
    graph_spec = dict(store.read_json("graph/GraphSpec.json", stream="artifact"))
    graph_summary_path = store.artifact_path("graph/GraphSummary.jsonl")
    if (final_status is None or summary_ref is None) and graph_summary_path.exists():
        graph_summary = _last_jsonl_obj(graph_summary_path) or {}
        if final_status is None:
            value = graph_summary.get("final_status")
            if value is not None:
                final_status = str(value)
        if summary_ref is None:
            summary_ref = str(graph_summary_path)
    progress = _progress_snapshot(
        graph_spec=graph_spec,
        session=session,
        journal=journal,
        final_status=final_status,
        summary_ref=summary_ref,
    )
    progress_path = store.artifact_path("graph/MaintainerProgress.json")
    _write_json_overwrite(progress_path, progress)
    return progress_path


def materialize_maintainer_session(
    *,
    repo_root: Path,
    change_id: str,
    execplan_ref: str | Path,
    scope_paths: Sequence[str | Path],
    instruction_scope_refs: Sequence[str | Path],
    required_context_refs: Sequence[str | Path],
    dependency_pin_set_id: str = "maintainer.repo_local.v1",
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    normalized_execplan = _normalize_repo_file_refs(
        repo_root=repo_root,
        refs=[execplan_ref],
        field_name="execplan_ref",
        require_non_empty=True,
    )[0]
    normalized_scope = _normalize_repo_file_refs(
        repo_root=repo_root,
        refs=scope_paths,
        field_name="scope_paths",
        require_non_empty=True,
    )
    _validate_execplan_disjoint_from_scope(
        execplan_ref=normalized_execplan,
        scope_paths=normalized_scope,
    )
    normalized_required_context = _normalize_required_context_refs(
        repo_root=repo_root,
        required_context_refs=required_context_refs,
        scope_paths=normalized_scope,
    )
    normalized_instruction = _normalize_instruction_scope_refs(
        repo_root=repo_root,
        instruction_scope_refs=instruction_scope_refs,
        active_repo_files=[normalized_execplan, *normalized_scope, *normalized_required_context],
    )

    graph_spec = _validate_graph_spec(
        repo_root=repo_root,
        graph_spec=build_maintainer_change_graph(change_id=change_id),
    )
    graph_spec_hash = _canonical_hash(graph_spec)
    input_projection_hash = _canonical_hash(
        {
            "change_id": change_id,
            "graph_spec_hash": graph_spec_hash,
            "execplan_ref": normalized_execplan,
            "execplan_hash": _hash_repo_file_set(repo_root=repo_root, refs=[normalized_execplan]),
            "scope_paths": normalized_scope,
            "required_context_refs": normalized_required_context,
            "required_context_hash": _hash_repo_file_set(
                repo_root=repo_root,
                refs=normalized_required_context,
            ),
        }
    )
    instruction_chain_hash = _hash_repo_file_set(repo_root=repo_root, refs=normalized_instruction)
    run_key = compute_run_key(
        RunKeyInput(
            loop_id=str(graph_spec["graph_id"]),
            graph_mode=str(graph_spec["graph_mode"]),
            input_projection_hash=input_projection_hash,
            instruction_chain_hash=instruction_chain_hash,
            dependency_pin_set_id=dependency_pin_set_id,
        )
    )
    store = LoopStore(repo_root=repo_root, run_key=run_key)
    store.ensure_layout()
    graph_spec_path = _write_json_if_absent_or_equal(
        store=store,
        rel="graph/GraphSpec.json",
        obj=graph_spec,
        stream="artifact",
    )
    session_path = store.artifact_path("graph/MaintainerSession.json")
    if session_path.exists():
        session = json.loads(session_path.read_text(encoding="utf-8"))
    else:
        session = {
            "version": "1",
            "created_at_utc": _utc_now(),
            "run_key": run_key,
            "change_id": change_id,
            "graph_id": str(graph_spec["graph_id"]),
            "graph_mode": str(graph_spec["graph_mode"]),
            "graph_spec_ref": str(graph_spec_path),
            "graph_spec_hash": graph_spec_hash,
            "session_ref": str(session_path),
            "progress_ref": str(store.artifact_path("graph/MaintainerProgress.json")),
            "execplan_ref": normalized_execplan,
            "scope_paths": normalized_scope,
            "instruction_scope_refs": normalized_instruction,
            "required_context_refs": normalized_required_context,
            "input_projection_hash": input_projection_hash,
            "instruction_chain_hash": instruction_chain_hash,
            "dependency_pin_set_id": dependency_pin_set_id,
            "node_order": [str(node["node_id"]) for node in graph_spec.get("nodes") or []],
            "node_journal_ref": str(store.artifact_path("graph/NodeJournal.jsonl")),
        }
        session_path = _write_json_if_absent_or_equal(
            store=store,
            rel="graph/MaintainerSession.json",
            obj=session,
            stream="artifact",
        )
    _append_jsonl_if_absent_or_equal_first(
        store=store,
        rel="graph/NodeJournal.jsonl",
        first_obj={
            "entry_kind": "SESSION_STARTED",
            "at_utc": _utc_now(),
            "run_key": run_key,
            "graph_spec_ref": str(graph_spec_path),
            "execplan_ref": normalized_execplan,
            "pending_node_ids": session["node_order"],
        },
        stream="artifact",
    )
    session["session_ref"] = str(session_path)
    session["progress_ref"] = str(store.artifact_path("graph/MaintainerProgress.json"))
    progress_path = _write_progress_snapshot(store=store, session=session)
    return {
        **session,
        "graph_spec": graph_spec,
        "session_ref": str(session_path),
        "progress_ref": str(progress_path),
    }


def _load_maintainer_session(
    *, repo_root: Path, run_key: str
) -> tuple[LoopStore, dict[str, Any], dict[str, Any]]:
    store = LoopStore(repo_root=repo_root.resolve(), run_key=run_key)
    session = dict(store.read_json("graph/MaintainerSession.json", stream="artifact"))
    graph_spec = dict(store.read_json("graph/GraphSpec.json", stream="artifact"))
    return store, session, graph_spec


def _resolved_terminal_states(
    *,
    graph_spec: dict[str, Any],
    terminal_by_node: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve recorded terminal nodes plus deterministically blocked descendants."""

    nodes_by_id = {str(node["node_id"]): dict(node) for node in graph_spec.get("nodes") or []}
    batches = LoopGraphRuntime._topological_batches(graph_spec)
    incoming, _outgoing = LoopGraphRuntime._graph_index(graph_spec)
    merge_policy = dict(graph_spec.get("merge_policy") or {})

    resolved_states = dict(terminal_by_node)
    effective_states = dict(terminal_by_node)
    for batch in batches:
        for node_id in batch:
            if node_id in resolved_states:
                continue
            deps = incoming.get(node_id, [])
            if not deps:
                continue
            edge_kind = LoopGraphRuntime._edge_kind_for_target(deps) or "SERIAL"
            allow_terminal_predecessors = bool(nodes_by_id[node_id].get("allow_terminal_predecessors"))
            gate_node_states = resolved_states
            if allow_terminal_predecessors and edge_kind not in {"RACE", "QUORUM"}:
                gate_node_states = effective_states
            predecessor_ids = [str(dep["from"]) for dep in deps]
            if any(pred not in gate_node_states for pred in predecessor_ids):
                continue
            gate = LoopGraphRuntime._evaluate_gate(
                edge_kind=edge_kind,
                predecessors=predecessor_ids,
                node_states=gate_node_states,
                merge_policy=merge_policy,
                allow_terminal_predecessors=allow_terminal_predecessors,
            )
            if gate.get("execute"):
                continue
            blocked_state = str(gate.get("blocked_state", "FAILED"))
            resolved_states[node_id] = blocked_state
            effective_states[node_id] = blocked_state
    return resolved_states, effective_states


def record_maintainer_node_result(
    *,
    repo_root: Path,
    run_key: str,
    node_id: str,
    state: str,
    reason_code: str,
    evidence_refs: Sequence[str | Path] | None = None,
    node_run_key: str | None = None,
) -> dict[str, Any]:
    if state not in _TERMINAL_STATES:
        raise ValueError(f"state must be one of {_TERMINAL_STATES}")
    if node_run_key is not None and not _HEX64.fullmatch(str(node_run_key)):
        raise ValueError("node_run_key must be 64-char lowercase hex when present")

    store, session, graph_spec = _load_maintainer_session(repo_root=repo_root, run_key=run_key)
    nodes = [dict(node) for node in graph_spec.get("nodes") or []]
    node_ids = [str(node["node_id"]) for node in nodes]
    if node_id not in node_ids:
        raise ValueError(f"node_id is not part of this maintainer graph: {node_id}")
    journal = _read_jsonl(store.artifact_path("graph/NodeJournal.jsonl"))
    terminal_by_node = {
        str(entry.get("node_id")): str(entry.get("state"))
        for entry in journal
        if entry.get("entry_kind") == "NODE_TERMINAL_RESULT"
    }
    resolved_terminal_by_node, _effective_terminal_by_node = _resolved_terminal_states(
        graph_spec=graph_spec,
        terminal_by_node=terminal_by_node,
    )
    if any(
        entry.get("entry_kind") == "NODE_TERMINAL_RESULT" and entry.get("node_id") == node_id
        for entry in journal
    ):
        raise ValueError(f"node_id {node_id!r} already has a terminal journal entry")
    predecessors = sorted(
        str(edge["from"])
        for edge in graph_spec.get("edges") or []
        if str(edge.get("to")) == node_id
    )
    missing_predecessors = [candidate for candidate in predecessors if candidate not in resolved_terminal_by_node]
    if missing_predecessors:
        raise ValueError(
            "node results must follow maintainer graph order; missing predecessor nodes: "
            + ", ".join(missing_predecessors)
        )
    allow_terminal_predecessors = any(
        str(node.get("node_id")) == node_id and bool(node.get("allow_terminal_predecessors"))
        for node in nodes
    )
    if not allow_terminal_predecessors:
        blocked_predecessors = [
            candidate for candidate in predecessors if resolved_terminal_by_node.get(candidate) != "PASSED"
        ]
        if blocked_predecessors:
            raise ValueError(
                "node results require passed predecessors; blocked by: " + ", ".join(blocked_predecessors)
            )
    elif predecessors:
        expected_terminal_state = LoopGraphRuntime._status_worst(
            [str(_effective_terminal_by_node.get(candidate, resolved_terminal_by_node[candidate])) for candidate in predecessors]
        )
        if state != expected_terminal_state:
            raise ValueError(
                "terminal-predecessor closeout must preserve resolved upstream terminal state; "
                f"expected {expected_terminal_state}, got {state}"
            )

    normalized_evidence = _normalize_repo_file_refs(
        repo_root=repo_root.resolve(),
        refs=tuple(evidence_refs or ()),
        field_name="evidence_refs",
        require_non_empty=False,
    )
    entry: dict[str, Any] = {
        "entry_kind": "NODE_TERMINAL_RESULT",
        "at_utc": _utc_now(),
        "run_key": run_key,
        "session_ref": str(store.artifact_path("graph/MaintainerSession.json")),
        "node_id": node_id,
        "state": state,
        "reason_code": reason_code,
    }
    if normalized_evidence:
        entry["evidence_refs"] = normalized_evidence
    if node_run_key is not None:
        entry["node_run_key"] = str(node_run_key)
    store.append_jsonl("graph/NodeJournal.jsonl", entry, stream="artifact")
    session["session_ref"] = str(store.artifact_path("graph/MaintainerSession.json"))
    _write_progress_snapshot(store=store, session=session)
    return entry


def close_maintainer_session(*, repo_root: Path, run_key: str) -> dict[str, Any]:
    store, session, graph_spec = _load_maintainer_session(repo_root=repo_root, run_key=run_key)
    journal = _read_jsonl(store.artifact_path("graph/NodeJournal.jsonl"))
    node_results: dict[str, dict[str, object]] = {}
    for entry in journal:
        if entry.get("entry_kind") != "NODE_TERMINAL_RESULT":
            continue
        node_result: dict[str, object] = {
            "state": str(entry["state"]),
            "reason_code": str(entry["reason_code"]),
        }
        if entry.get("node_run_key") is not None:
            node_result["run_key"] = str(entry["node_run_key"])
        node_results[str(entry["node_id"])] = node_result

    if "loop_closeout" not in node_results:
        raise ValueError("cannot close maintainer session without a loop_closeout journal entry")

    summary = execute_recorded_graph(
        repo_root=repo_root.resolve(),
        run_key=run_key,
        graph_spec=graph_spec,
        node_results=node_results,
    )
    session["session_ref"] = str(store.artifact_path("graph/MaintainerSession.json"))
    _write_progress_snapshot(
        store=store,
        session=session,
        final_status=str(summary["final_status"]),
        summary_ref=str(summary["summary_ref"]),
    )
    return summary


def execute_recorded_graph(
    *,
    repo_root: Path,
    run_key: str,
    graph_spec: dict[str, object],
    node_results: dict[str, dict[str, object]],
    unresolved_exception: bool | None = None,
) -> dict[str, object]:
    """Execute a graph with pre-recorded terminal node results and persist artifacts."""

    if not _HEX64.fullmatch(run_key):
        raise ValueError("run_key must be 64-char lowercase hex")

    validated_graph_spec = _validate_graph_spec(repo_root=repo_root, graph_spec=graph_spec)
    store = LoopStore(repo_root=repo_root, run_key=run_key)
    store.ensure_layout()
    canonical_results = _canonical_node_results(graph_spec=validated_graph_spec, node_results=node_results)

    graph_spec_path = _write_json_if_absent_or_equal(
        store=store,
        rel="graph/GraphSpec.json",
        obj=validated_graph_spec,
        stream="artifact",
    )
    node_results_path = store.artifact_path("graph/NodeResults.json")

    runtime = LoopGraphRuntime(repo_root=repo_root, run_key=run_key)

    def _executor(node: dict[str, object]) -> dict[str, object]:
        node_id = str(node["node_id"])
        if node_id not in canonical_results:
            raise ValueError(f"missing node_results for executable node_id: {node_id}")
        return dict(canonical_results[node_id])

    summary, arbitration_records = runtime._evaluate_execution(
        graph_spec=validated_graph_spec,
        node_executor=_executor,
        unresolved_exception=unresolved_exception,
        summary_overlay={
            "graph_spec_ref": str(graph_spec_path),
            "node_results_ref": str(node_results_path),
        },
    )
    _validate_maintainer_closeout(summary)
    _write_json_if_absent_or_equal(
        store=store,
        rel="graph/NodeResults.json",
        obj=_actual_node_results(summary),
        stream="artifact",
    )
    summary_path = store.artifact_path("graph/GraphSummary.jsonl")
    existing_summary = _last_jsonl_obj(summary_path)
    if existing_summary is not None:
        if existing_summary != summary:
            raise FileExistsError(f"append-only summary already exists with different content: {summary_path}")
        return {**summary, "summary_ref": str(summary_path)}
    return runtime._persist_execution(summary=summary, arbitration_records=arbitration_records)


@dataclass(frozen=True)
class MaintainerLoopSession:
    """High-level facade for a materialized maintainer LOOP session."""

    repo_root: Path
    run_key: str
    session_ref: str
    graph_spec_ref: str
    node_journal_ref: str
    progress_ref: str

    @classmethod
    def materialize(
        cls,
        *,
        repo_root: Path,
        change_id: str,
        execplan_ref: str | Path,
        scope_paths: Sequence[str | Path],
        instruction_scope_refs: Sequence[str | Path],
        required_context_refs: Sequence[str | Path],
        dependency_pin_set_id: str = "maintainer.repo_local.v1",
    ) -> "MaintainerLoopSession":
        session = materialize_maintainer_session(
            repo_root=repo_root,
            change_id=change_id,
            execplan_ref=execplan_ref,
            scope_paths=scope_paths,
            instruction_scope_refs=instruction_scope_refs,
            required_context_refs=required_context_refs,
            dependency_pin_set_id=dependency_pin_set_id,
        )
        return cls(
            repo_root=repo_root.resolve(),
            run_key=str(session["run_key"]),
            session_ref=str(session["session_ref"]),
            graph_spec_ref=str(session["graph_spec_ref"]),
            node_journal_ref=str(session["node_journal_ref"]),
            progress_ref=str(session["progress_ref"]),
        )

    @classmethod
    def load(cls, *, repo_root: Path, run_key: str) -> "MaintainerLoopSession":
        store, session, _graph_spec = _load_maintainer_session(repo_root=repo_root.resolve(), run_key=run_key)
        session["session_ref"] = str(store.artifact_path("graph/MaintainerSession.json"))
        progress_path = _write_progress_snapshot(store=store, session=session)
        return cls(
            repo_root=repo_root.resolve(),
            run_key=str(run_key),
            session_ref=str(store.artifact_path("graph/MaintainerSession.json")),
            graph_spec_ref=str(session["graph_spec_ref"]),
            node_journal_ref=str(session["node_journal_ref"]),
            progress_ref=str(progress_path),
        )

    def record_node_result(
        self,
        *,
        node_id: str,
        state: str,
        reason_code: str,
        evidence_refs: Sequence[str | Path] | None = None,
        node_run_key: str | None = None,
    ) -> dict[str, Any]:
        return record_maintainer_node_result(
            repo_root=self.repo_root,
            run_key=self.run_key,
            node_id=node_id,
            state=state,
            reason_code=reason_code,
            evidence_refs=evidence_refs,
            node_run_key=node_run_key,
        )

    def close(self) -> dict[str, Any]:
        return close_maintainer_session(repo_root=self.repo_root, run_key=self.run_key)


__all__ = [
    "MaintainerLoopSession",
    "close_maintainer_session",
    "execute_recorded_graph",
    "materialize_maintainer_session",
    "record_maintainer_node_result",
]
