#!/usr/bin/env python3
"""Helpers for deterministic maintainer LOOP execution artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import time
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
_SUCCESS_IMPLYING_REVIEW_REASON_CODES = {"REVIEW_PASS"}
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


def _utc_now_epoch_ns() -> int:
    return time.time_ns()


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


def _slug_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    token = token.strip("._")
    return token or "ref"


def _stable_execplan_id(execplan_ref: str) -> str:
    rel = str(execplan_ref).strip().replace("\\", "/")
    slug = _slug_token(rel.replace("/", "__"))
    digest = hashlib.sha256(rel.encode("utf-8")).hexdigest()[:12]
    return f"{slug}__{digest}"


def _closeout_ref_path(*, repo_root: Path, execplan_ref: str) -> Path:
    return (
        repo_root.resolve()
        / "artifacts"
        / "loop_runtime"
        / "by_execplan"
        / _stable_execplan_id(execplan_ref)
        / "MaintainerCloseoutRef.json"
    )


def _closeout_authority_token(
    *,
    created_at_epoch_ns: int | str | None,
    created_at_utc: str,
    run_key: str,
) -> tuple[int, str, str]:
    try:
        epoch_ns = int(created_at_epoch_ns) if created_at_epoch_ns not in (None, "") else -1
    except (TypeError, ValueError):
        epoch_ns = -1
    return (epoch_ns, str(created_at_utc or ""), str(run_key or ""))


def _existing_closeout_authority_token(*, closeout_ref: dict[str, Any]) -> tuple[int, str, str]:
    created_at_utc = str(closeout_ref.get("session_created_at_utc") or "")
    created_at_epoch_ns = closeout_ref.get("session_created_at_epoch_ns")
    needs_session_backfill = not created_at_utc or created_at_epoch_ns in (None, "")
    if needs_session_backfill:
        session_ref = str(closeout_ref.get("session_ref") or "").strip()
        if session_ref:
            session_path = Path(session_ref)
            if session_path.exists() and session_path.is_file():
                try:
                    session_obj = json.loads(session_path.read_text(encoding="utf-8"))
                except Exception:
                    session_obj = {}
                if not created_at_utc:
                    created_at_utc = str(session_obj.get("created_at_utc") or "")
                if created_at_epoch_ns in (None, ""):
                    created_at_epoch_ns = session_obj.get("created_at_epoch_ns")
    return _closeout_authority_token(
        created_at_epoch_ns=created_at_epoch_ns,
        created_at_utc=created_at_utc,
        run_key=str(closeout_ref.get("run_key") or ""),
    )


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


def _scope_observed_stamp(*, repo_root: Path, scope_paths: Sequence[str]) -> str:
    payload: dict[str, dict[str, int | str]] = {}
    repo_root = repo_root.resolve()
    for rel in scope_paths:
        path = repo_root / rel
        stat = path.stat()
        payload[rel] = {
            "sha256": _sha256_file(path),
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "ctime_ns": int(getattr(stat, "st_ctime_ns", stat.st_ctime_ns)),
        }
    return _canonical_hash(payload)


def _compute_input_projection_hash(
    *,
    change_id: str,
    graph_spec_hash: str,
    execplan_ref: str,
    execplan_hash: str,
    scope_paths: Sequence[str],
    required_context_refs: Sequence[str],
    required_context_hash: str,
) -> str:
    return _canonical_hash(
        {
            "change_id": change_id,
            "graph_spec_hash": graph_spec_hash,
            "execplan_ref": execplan_ref,
            "execplan_hash": execplan_hash,
            "scope_paths": list(scope_paths),
            "required_context_refs": list(required_context_refs),
            "required_context_hash": required_context_hash,
        }
    )


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


def _legacy_blocked_closeout_summary_variant(expected: dict[str, Any]) -> dict[str, Any] | None:
    decisions = [dict(item) for item in expected.get("node_decisions") or []]
    if not decisions:
        return None
    ai_review = next((item for item in decisions if str(item.get("node_id") or "") == "ai_review_node"), None)
    closeout = next((item for item in decisions if str(item.get("node_id") or "") == "loop_closeout"), None)
    if ai_review is None or closeout is None:
        return None
    if ai_review.get("executed") is not False or str(ai_review.get("reason_code") or "") != "UPSTREAM_BLOCKED":
        return None
    if closeout.get("executed") is not True or str(closeout.get("reason_code") or "") == "UPSTREAM_BLOCKED":
        return None
    if str(closeout.get("state") or "") != str(ai_review.get("state") or ""):
        return None

    variant = dict(expected)
    variant["node_decisions"] = []
    for item in decisions:
        if str(item.get("node_id") or "") != "loop_closeout":
            variant["node_decisions"].append(item)
            continue
        patched = dict(item)
        patched["executed"] = False
        patched["reason_code"] = "UPSTREAM_BLOCKED"
        patched.pop("run_key", None)
        variant["node_decisions"].append(patched)
    return variant


def _summary_matches_without_executed(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    existing_decisions = [dict(item) for item in existing.get("node_decisions") or []]
    if not existing_decisions or all("executed" in item for item in existing_decisions):
        return False
    normalized_existing = dict(existing)
    normalized_candidate = dict(candidate)
    normalized_existing["node_decisions"] = [
        {k: v for k, v in item.items() if k != "executed"} for item in existing_decisions
    ]
    normalized_candidate["node_decisions"] = [
        {k: v for k, v in dict(item).items() if k != "executed"}
        for item in candidate.get("node_decisions") or []
    ]
    return normalized_existing == normalized_candidate


def _summary_matches_existing_graph_summary(existing: dict[str, Any], expected: dict[str, Any]) -> bool:
    if existing == expected:
        return True
    if _summary_matches_without_executed(existing, expected):
        return True
    legacy_blocked_variant = _legacy_blocked_closeout_summary_variant(expected)
    if legacy_blocked_variant is None:
        return False
    if existing == legacy_blocked_variant:
        return True
    return _summary_matches_without_executed(existing, legacy_blocked_variant)


def _summary_requires_executed_backfill(existing: dict[str, Any], expected: dict[str, Any]) -> bool:
    return existing != expected and _summary_matches_existing_graph_summary(existing, expected)


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


def _write_json_overwrite(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _preserve_maintainer_bookkeeping_closeout(
    *,
    graph_spec: dict[str, Any],
    node_results: dict[str, dict[str, object]],
    summary: dict[str, Any],
    arbitration_records: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    node_ids = {str(node.get("node_id") or "") for node in graph_spec.get("nodes") or []}
    if not {"ai_review_node", "loop_closeout"}.issubset(node_ids):
        return summary, [dict(record) for record in arbitration_records]
    if "loop_closeout" not in node_results or "ai_review_node" in node_results:
        return summary, [dict(record) for record in arbitration_records]

    decisions = [dict(item) for item in summary.get("node_decisions") or []]
    ai_review_decision = next((item for item in decisions if str(item.get("node_id") or "") == "ai_review_node"), None)
    closeout_decision = next((item for item in decisions if str(item.get("node_id") or "") == "loop_closeout"), None)
    if ai_review_decision is None or closeout_decision is None:
        return summary, [dict(record) for record in arbitration_records]
    if closeout_decision.get("executed") is not False or str(closeout_decision.get("reason_code") or "") != "UPSTREAM_BLOCKED":
        return summary, [dict(record) for record in arbitration_records]
    if ai_review_decision.get("executed") is not False or str(ai_review_decision.get("reason_code") or "") != "UPSTREAM_BLOCKED":
        return summary, [dict(record) for record in arbitration_records]

    journaled_closeout = dict(node_results["loop_closeout"])
    if str(journaled_closeout.get("state") or "") != str(closeout_decision.get("state") or ""):
        raise ValueError(
            "maintainer bookkeeping closeout replay requires loop_closeout journal state to match the resolved "
            "terminal class of the blocked graph summary"
        )

    patched_summary = dict(summary)
    patched_decisions: list[dict[str, Any]] = []
    for item in decisions:
        if str(item.get("node_id") or "") != "loop_closeout":
            patched_decisions.append(item)
            continue
        patched = dict(item)
        patched["executed"] = True
        patched["reason_code"] = str(journaled_closeout.get("reason_code") or item.get("reason_code") or "")
        run_key = journaled_closeout.get("run_key")
        if run_key is None:
            patched.pop("run_key", None)
        else:
            patched["run_key"] = str(run_key)
        patched_decisions.append(patched)
    patched_summary["node_decisions"] = patched_decisions

    patched_arbitration_records: list[dict[str, Any]] = []
    for record in arbitration_records:
        patched_record = dict(record)
        if str(record.get("target_node_id") or "") == "loop_closeout":
            patched_record["winner_rule"] = "BOOKKEEPING_CLOSEOUT_RECORDED"
            patched_record["winner_state"] = str(journaled_closeout.get("state") or patched_record.get("winner_state") or "")
            patched_record["bookkeeping_closeout_recorded"] = True
            patched_record["bookkeeping_reason_code"] = str(journaled_closeout.get("reason_code") or "")
        patched_arbitration_records.append(patched_record)
    return patched_summary, patched_arbitration_records


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


def _write_node_results_json_with_legacy_backfill(
    *,
    store: LoopStore,
    rel: str,
    obj: dict[str, Any],
    summary: dict[str, Any],
    stream: str = "artifact",
) -> Path:
    path = store.artifact_path(rel) if stream == "artifact" else store.cache_path(rel)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing == obj:
            return path
        legacy_summary = _legacy_blocked_closeout_summary_variant(summary)
        legacy_node_results = _actual_node_results(legacy_summary) if legacy_summary is not None else None
        if legacy_node_results is not None and existing == legacy_node_results:
            _write_json_overwrite(path, obj)
            return path
        raise FileExistsError(f"write-once path already exists with different content: {path}")
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


def _write_jsonl_sequence_if_absent_or_equal(
    *, store: LoopStore, rel: str, objs: Sequence[dict[str, Any]], stream: str = "artifact"
) -> Path:
    path = store.artifact_path(rel) if stream == "artifact" else store.cache_path(rel)
    expected = [dict(obj) for obj in objs]
    if path.exists():
        actual = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if actual != expected:
            raise FileExistsError(f"append-only journal already exists with different content: {path}")
        return path
    if not expected:
        return path
    for obj in expected:
        store.append_jsonl(rel, obj, stream=stream)
    return path


def _legacy_compatible_nested_lineage_rows(
    *, actual: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]]
) -> bool:
    if len(actual) != len(expected):
        return False
    normalized_actual: list[dict[str, Any]] = []
    for actual_row, expected_row in zip(actual, expected, strict=True):
        normalized = dict(actual_row)
        if normalized != expected_row:
            comparable_actual = {key: value for key, value in normalized.items() if key != "child_state"}
            comparable_expected = {key: value for key, value in expected_row.items() if key != "child_state"}
            if (
                comparable_actual == comparable_expected
                and normalized.get("executed") is True
                and expected_row.get("executed") is True
                and normalized.get("blocked_state") is None
                and expected_row.get("blocked_state") is None
            ):
                normalized["child_state"] = expected_row.get("child_state")
            else:
                return False
        normalized_actual.append(normalized)
    return normalized_actual == [dict(row) for row in expected]


def _write_nested_lineage_jsonl_with_legacy_backfill(
    *, store: LoopStore, rel: str, objs: Sequence[dict[str, Any]], stream: str = "artifact"
) -> Path:
    path = store.artifact_path(rel) if stream == "artifact" else store.cache_path(rel)
    expected = [dict(obj) for obj in objs]
    if path.exists():
        actual = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if actual == expected:
            return path
        if _legacy_compatible_nested_lineage_rows(actual=actual, expected=expected):
            _write_jsonl_overwrite(path, expected)
            return path
        raise FileExistsError(f"append-only journal already exists with different content: {path}")
    if not expected:
        return path
    for obj in expected:
        store.append_jsonl(rel, obj, stream=stream)
    return path


def _legacy_compatible_scheduler_rows(
    *, actual: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]]
) -> bool:
    if len(actual) != len(expected):
        return False
    normalized_actual: list[dict[str, Any]] = []
    for actual_row, expected_row in zip(actual, expected, strict=True):
        normalized = dict(actual_row)
        if normalized != expected_row:
            comparable_actual = {key: value for key, value in normalized.items() if key != "parallel_width"}
            comparable_expected = {key: value for key, value in expected_row.items() if key != "parallel_width"}
            if (
                comparable_actual == comparable_expected
                and normalized.get("execution_mode") == "SERIAL"
                and expected_row.get("execution_mode") == "SERIAL"
                and normalized.get("parallel_width") == 1
                and expected_row.get("parallel_width") == 0
            ):
                normalized["parallel_width"] = 0
            else:
                return False
        normalized_actual.append(normalized)
    return normalized_actual == [dict(row) for row in expected]


def _write_scheduler_jsonl_with_legacy_backfill(
    *, store: LoopStore, rel: str, objs: Sequence[dict[str, Any]], stream: str = "artifact"
) -> Path:
    path = store.artifact_path(rel) if stream == "artifact" else store.cache_path(rel)
    expected = [dict(obj) for obj in objs]
    if path.exists():
        actual = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if actual == expected:
            return path
        if _legacy_compatible_scheduler_rows(actual=actual, expected=expected):
            _write_jsonl_overwrite(path, expected)
            return path
        raise FileExistsError(f"append-only journal already exists with different content: {path}")
    if not expected:
        return path
    for obj in expected:
        store.append_jsonl(rel, obj, stream=stream)
    return path


def _legacy_compatible_arbitration_rows(
    *, actual: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]]
) -> bool:
    if len(actual) != len(expected):
        return False
    normalized_actual: list[dict[str, Any]] = []
    for actual_row, expected_row in zip(actual, expected, strict=True):
        normalized = dict(actual_row)
        if "predecessor_executed" not in normalized and "predecessor_states" in normalized:
            if "predecessor_executed" not in expected_row:
                return False
            normalized["predecessor_executed"] = expected_row["predecessor_executed"]
        if (
            str(normalized.get("target_node_id") or "") == "loop_closeout"
            and expected_row.get("bookkeeping_closeout_recorded") is True
            and "bookkeeping_closeout_recorded" not in normalized
        ):
            normalized["winner_rule"] = expected_row["winner_rule"]
            normalized["winner_state"] = expected_row["winner_state"]
            normalized["bookkeeping_closeout_recorded"] = expected_row["bookkeeping_closeout_recorded"]
            normalized["bookkeeping_reason_code"] = expected_row["bookkeeping_reason_code"]
        normalized_actual.append(normalized)
    return normalized_actual == [dict(row) for row in expected]


def _write_jsonl_overwrite(path: Path, objs: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(obj), sort_keys=True) + "\n" for obj in objs),
        encoding="utf-8",
    )


def _write_arbitration_jsonl_with_legacy_backfill(
    *, store: LoopStore, rel: str, objs: Sequence[dict[str, Any]], stream: str = "artifact"
) -> Path:
    path = store.artifact_path(rel) if stream == "artifact" else store.cache_path(rel)
    expected = [dict(obj) for obj in objs]
    if path.exists():
        actual = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if actual == expected:
            return path
        if _legacy_compatible_arbitration_rows(actual=actual, expected=expected):
            _write_jsonl_overwrite(path, expected)
            return path
        raise FileExistsError(f"append-only journal already exists with different content: {path}")
    if not expected:
        return path
    for obj in expected:
        store.append_jsonl(rel, obj, stream=stream)
    return path


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
    nodes_by_id = {str(node["node_id"]): dict(node) for node in graph_spec.get("nodes") or []}
    terminal_by_node = {
        str(entry.get("node_id")): str(entry.get("state"))
        for entry in journal
        if entry.get("entry_kind") == "NODE_TERMINAL_RESULT"
    }
    reason_by_node = {
        str(entry.get("node_id")): str(entry.get("reason_code") or "NODE_EXEC_RESULT")
        for entry in journal
        if entry.get("entry_kind") == "NODE_TERMINAL_RESULT"
    }
    incoming, _outgoing = LoopGraphRuntime._graph_index(graph_spec)
    resolved_terminal_by_node, _effective_terminal_by_node, resolved_executed_by_node = _resolved_terminal_states(
        graph_spec=graph_spec,
        terminal_by_node=terminal_by_node,
        reason_by_node=reason_by_node,
    )
    bookkeeping_pending_node_ids = [
        node_id
        for node_id in node_order
        if node_id not in terminal_by_node
        if bool(nodes_by_id.get(node_id, {}).get("allow_terminal_predecessors"))
        and all(
            str(dep["from"]) in resolved_terminal_by_node
            for dep in incoming.get(node_id, [])
        )
        and not bool(resolved_executed_by_node.get(node_id, False))
    ]
    bookkeeping_pending_node_id_set = set(bookkeeping_pending_node_ids)
    blocked_node_ids = [
        node_id
        for node_id in node_order
        if node_id not in terminal_by_node
        and node_id not in bookkeeping_pending_node_id_set
        and resolved_terminal_by_node.get(node_id) in {"FAILED", "TRIAGED"}
    ]
    completed = [node_id for node_id in node_order if node_id in terminal_by_node]
    pending = [node_id for node_id in node_order if node_id not in completed and node_id not in blocked_node_ids]
    current_node_id = pending[0] if pending else None
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
        "current_node_id": current_node_id,
    }
    if blocked_node_ids:
        snapshot["blocked_node_ids"] = blocked_node_ids
    if bookkeeping_pending_node_ids:
        snapshot["bookkeeping_pending_node_ids"] = bookkeeping_pending_node_ids
    if current_node_id is not None:
        snapshot["current_node_mode"] = (
            "BOOKKEEPING_CLOSEOUT" if current_node_id in bookkeeping_pending_node_ids else "RUNNABLE"
        )
    if final_status is not None:
        snapshot["final_status"] = final_status
    if summary_ref is not None:
        snapshot["summary_ref"] = summary_ref
    closeout_ref_ref = str(session.get("closeout_ref_ref") or "").strip()
    if closeout_ref_ref:
        snapshot["closeout_ref_ref"] = closeout_ref_ref
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


def _canonicalize_session_sidecars(
    *,
    store: LoopStore,
    session: dict[str, Any],
    closeout_ref_ref: str | None = None,
) -> tuple[dict[str, Any], bool]:
    session_path = store.artifact_path("graph/MaintainerSession.json")
    canonical_fields = {
        "session_ref": str(session_path),
        "progress_ref": str(store.artifact_path("graph/MaintainerProgress.json")),
    }
    normalized_closeout_ref = str(closeout_ref_ref or session.get("closeout_ref_ref") or "").strip()
    if normalized_closeout_ref:
        canonical_fields["closeout_ref_ref"] = normalized_closeout_ref

    changed = False
    for key, value in canonical_fields.items():
        if str(session.get(key) or "") != value:
            session[key] = value
            changed = True
    if changed:
        _write_json_overwrite(session_path, session)
    return session, changed


def _reconcile_session_frozen_inputs(
    *,
    repo_root: Path,
    store: LoopStore,
    session: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    execplan_ref = str(session.get("execplan_ref") or "").strip()
    change_id = str(session.get("change_id") or "").strip()
    graph_spec_hash = str(session.get("graph_spec_hash") or "").strip()
    input_projection_hash = str(session.get("input_projection_hash") or "").strip()
    required_context_refs = [str(ref) for ref in session.get("required_context_refs") or []]
    instruction_scope_refs = [str(ref) for ref in session.get("instruction_scope_refs") or []]
    scope_paths = [str(ref) for ref in session.get("scope_paths") or []]
    if not execplan_ref:
        return session, False

    current_execplan_hash = _hash_repo_file_set(repo_root=repo_root, refs=[execplan_ref])
    current_required_context_hash = _hash_repo_file_set(
        repo_root=repo_root,
        refs=required_context_refs,
    )
    expected_input_projection_hash = _compute_input_projection_hash(
        change_id=change_id,
        graph_spec_hash=graph_spec_hash,
        execplan_ref=execplan_ref,
        execplan_hash=current_execplan_hash,
        scope_paths=scope_paths,
        required_context_refs=required_context_refs,
        required_context_hash=current_required_context_hash,
    )

    changed = False
    session_path = store.artifact_path("graph/MaintainerSession.json")
    if not str(session.get("execplan_hash") or "").strip():
        if input_projection_hash == expected_input_projection_hash:
            session["execplan_hash"] = current_execplan_hash
            changed = True
    if not str(session.get("required_context_hash") or "").strip():
        if input_projection_hash == expected_input_projection_hash:
            session["required_context_hash"] = current_required_context_hash
            changed = True
    if instruction_scope_refs and not str(session.get("instruction_chain_hash") or "").strip():
        current_instruction_chain_hash = _hash_repo_file_set(
            repo_root=repo_root,
            refs=instruction_scope_refs,
        )
        expected_run_key = compute_run_key(
            RunKeyInput(
                loop_id=str(session.get("graph_id") or ""),
                graph_mode=str(session.get("graph_mode") or ""),
                input_projection_hash=input_projection_hash,
                instruction_chain_hash=current_instruction_chain_hash,
                dependency_pin_set_id=str(session.get("dependency_pin_set_id") or ""),
            )
        )
        if expected_run_key == str(session.get("run_key") or ""):
            session["instruction_chain_hash"] = current_instruction_chain_hash
            changed = True
    if changed:
        _write_json_overwrite(session_path, session)
    return session, changed


def _assert_frozen_session_inputs_current(*, repo_root: Path, session: dict[str, Any]) -> None:
    execplan_ref = str(session.get("execplan_ref") or "").strip()
    if execplan_ref:
        expected_execplan_hash = str(session.get("execplan_hash") or "").strip()
        if not expected_execplan_hash:
            raise ValueError(
                "cannot close maintainer session without frozen execplan_hash; rematerialize the session first"
            )
        current_execplan_hash = _hash_repo_file_set(repo_root=repo_root, refs=[execplan_ref])
        if current_execplan_hash != expected_execplan_hash:
            raise ValueError(
                "cannot close maintainer session with stale execplan_ref bytes; rematerialize the session first"
            )

    required_context_refs = [str(ref) for ref in session.get("required_context_refs") or []]
    expected_required_context_hash = str(session.get("required_context_hash") or "").strip()
    if required_context_refs:
        if not expected_required_context_hash:
            raise ValueError(
                "cannot close maintainer session without frozen required_context_hash; rematerialize the session first"
            )
        current_required_context_hash = _hash_repo_file_set(
            repo_root=repo_root,
            refs=required_context_refs,
        )
        if current_required_context_hash != expected_required_context_hash:
            raise ValueError(
                "cannot close maintainer session with stale required_context_refs bytes; rematerialize the session first"
            )

    instruction_scope_refs = [str(ref) for ref in session.get("instruction_scope_refs") or []]
    expected_instruction_chain_hash = str(session.get("instruction_chain_hash") or "").strip()
    if instruction_scope_refs:
        if not expected_instruction_chain_hash:
            raise ValueError(
                "cannot close maintainer session without frozen instruction_chain_hash; rematerialize the session first"
            )
        current_instruction_chain_hash = _hash_repo_file_set(
            repo_root=repo_root,
            refs=instruction_scope_refs,
        )
        if current_instruction_chain_hash != expected_instruction_chain_hash:
            raise ValueError(
                "cannot close maintainer session with stale instruction_scope_refs bytes; rematerialize the session first"
            )


def _assert_reviewed_scope_current(
    *,
    repo_root: Path,
    session: dict[str, Any],
    journal: Sequence[Mapping[str, Any]],
) -> None:
    scope_paths = [str(ref) for ref in session.get("scope_paths") or []]
    if not scope_paths:
        return
    ai_review_entries = [
        entry
        for entry in journal
        if entry.get("entry_kind") == "NODE_TERMINAL_RESULT" and entry.get("node_id") == "ai_review_node"
    ]
    if not ai_review_entries:
        return
    ai_review_entry = dict(ai_review_entries[-1])
    expected_scope_fingerprint = str(ai_review_entry.get("scope_fingerprint") or "").strip()
    expected_scope_observed_stamp = str(ai_review_entry.get("scope_observed_stamp") or "").strip()
    if not expected_scope_fingerprint or not expected_scope_observed_stamp:
        raise ValueError(
            "cannot close maintainer session without ai_review_node reviewed-scope evidence; re-record ai_review_node"
        )
    current_scope_fingerprint = _hash_repo_file_set(repo_root=repo_root, refs=scope_paths)
    current_scope_observed_stamp = _scope_observed_stamp(repo_root=repo_root, scope_paths=scope_paths)
    if current_scope_fingerprint != expected_scope_fingerprint:
        raise ValueError(
            "cannot close maintainer session with stale reviewed scope bytes; current scope_fingerprint no longer "
            "matches ai_review_node evidence"
        )
    if current_scope_observed_stamp != expected_scope_observed_stamp:
        raise ValueError(
            "cannot close maintainer session after reviewed scope mutate-and-restore; current "
            "scope_observed_stamp no longer matches ai_review_node evidence"
        )


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
    execplan_hash = _hash_repo_file_set(repo_root=repo_root, refs=[normalized_execplan])
    required_context_hash = _hash_repo_file_set(
        repo_root=repo_root,
        refs=normalized_required_context,
    )
    input_projection_hash = _compute_input_projection_hash(
        change_id=change_id,
        graph_spec_hash=graph_spec_hash,
        execplan_ref=normalized_execplan,
        execplan_hash=execplan_hash,
        scope_paths=normalized_scope,
        required_context_refs=normalized_required_context,
        required_context_hash=required_context_hash,
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
    closeout_ref_ref = str(_closeout_ref_path(repo_root=repo_root, execplan_ref=normalized_execplan))
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
            "created_at_epoch_ns": _utc_now_epoch_ns(),
            "run_key": run_key,
            "change_id": change_id,
            "graph_id": str(graph_spec["graph_id"]),
            "graph_mode": str(graph_spec["graph_mode"]),
            "graph_spec_ref": str(graph_spec_path),
            "graph_spec_hash": graph_spec_hash,
            "session_ref": str(session_path),
            "progress_ref": str(store.artifact_path("graph/MaintainerProgress.json")),
            "closeout_ref_ref": closeout_ref_ref,
            "execplan_ref": normalized_execplan,
            "scope_paths": normalized_scope,
            "instruction_scope_refs": normalized_instruction,
            "required_context_refs": normalized_required_context,
            "execplan_hash": execplan_hash,
            "required_context_hash": required_context_hash,
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
    session, _session_updated = _canonicalize_session_sidecars(
        store=store,
        session=session,
        closeout_ref_ref=closeout_ref_ref,
    )
    session, _session_frozen_input_updated = _reconcile_session_frozen_inputs(
        repo_root=repo_root,
        store=store,
        session=session,
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
    expected_closeout_ref_ref: str | None = None
    execplan_ref = str(session.get("execplan_ref") or "").strip()
    if execplan_ref:
        expected_closeout_ref_ref = str(
            _closeout_ref_path(repo_root=repo_root.resolve(), execplan_ref=execplan_ref)
        )
    session, _session_updated = _canonicalize_session_sidecars(
        store=store,
        session=session,
        closeout_ref_ref=expected_closeout_ref_ref,
    )
    session, _session_frozen_input_updated = _reconcile_session_frozen_inputs(
        repo_root=repo_root.resolve(),
        store=store,
        session=session,
    )
    graph_spec = dict(store.read_json("graph/GraphSpec.json", stream="artifact"))
    return store, session, graph_spec


def _resolved_terminal_states(
    *,
    graph_spec: dict[str, Any],
    terminal_by_node: dict[str, str],
    reason_by_node: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str], dict[str, bool]]:
    """Resolve recorded terminal nodes plus deterministically blocked descendants."""

    nodes_by_id = {str(node["node_id"]): dict(node) for node in graph_spec.get("nodes") or []}
    batches = LoopGraphRuntime._topological_batches(graph_spec)
    incoming, _outgoing = LoopGraphRuntime._graph_index(graph_spec)
    merge_policy = dict(graph_spec.get("merge_policy") or {})

    resolved_states = dict(terminal_by_node)
    resolved_reason_codes = dict(reason_by_node or {})
    resolved_executed = {str(node_id): True for node_id in terminal_by_node}
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
            gate_node_reason_codes = resolved_reason_codes
            gate_node_executed = resolved_executed
            if allow_terminal_predecessors and edge_kind not in {"RACE", "QUORUM"}:
                gate_node_states = effective_states
                gate_node_reason_codes = resolved_reason_codes
                gate_node_executed = resolved_executed
            predecessor_ids = [str(dep["from"]) for dep in deps]
            if any(pred not in gate_node_states for pred in predecessor_ids):
                continue
            gate = LoopGraphRuntime._evaluate_gate(
                edge_kind=edge_kind,
                predecessors=predecessor_ids,
                node_states=gate_node_states,
                node_reason_codes=gate_node_reason_codes,
                node_executed=gate_node_executed,
                merge_policy=merge_policy,
                allow_terminal_predecessors=allow_terminal_predecessors,
            )
            if gate.get("execute"):
                continue
            blocked_state = str(gate.get("blocked_state", "FAILED"))
            resolved_states[node_id] = blocked_state
            resolved_reason_codes[node_id] = str(gate.get("reason_code", "UPSTREAM_BLOCKED"))
            resolved_executed[node_id] = False
            effective_states[node_id] = blocked_state
    return resolved_states, effective_states, resolved_executed


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
    reason_by_node = {
        str(entry.get("node_id")): str(entry.get("reason_code") or "NODE_EXEC_RESULT")
        for entry in journal
        if entry.get("entry_kind") == "NODE_TERMINAL_RESULT"
    }
    resolved_terminal_by_node, _effective_terminal_by_node, _resolved_executed_by_node = _resolved_terminal_states(
        graph_spec=graph_spec,
        terminal_by_node=terminal_by_node,
        reason_by_node=reason_by_node,
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
        # Maintainer loop_closeout is a bookkeeping sink: it may be journaled after upstream
        # failure/triage so the session can close deterministically, but it must preserve the
        # resolved upstream terminal class rather than inventing a review pass.
        expected_terminal_state = LoopGraphRuntime._status_worst(
            [str(_effective_terminal_by_node.get(candidate, resolved_terminal_by_node[candidate])) for candidate in predecessors]
        )
        if state != expected_terminal_state:
            raise ValueError(
                "terminal-predecessor closeout must preserve resolved upstream terminal state; "
                f"expected {expected_terminal_state}, got {state}"
            )
        if expected_terminal_state != "PASSED" and reason_code in _SUCCESS_IMPLYING_REVIEW_REASON_CODES:
            raise ValueError(
                "blocked closeout reason_code must not imply successful AI review execution; "
                f"got {reason_code}"
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
    if node_id == "ai_review_node":
        entry["scope_fingerprint"] = _hash_repo_file_set(
            repo_root=repo_root.resolve(),
            refs=[str(rel) for rel in session.get("scope_paths") or []],
        )
        entry["scope_observed_stamp"] = _scope_observed_stamp(
            repo_root=repo_root.resolve(),
            scope_paths=[str(rel) for rel in session.get("scope_paths") or []],
        )
    store.append_jsonl("graph/NodeJournal.jsonl", entry, stream="artifact")
    session["session_ref"] = str(store.artifact_path("graph/MaintainerSession.json"))
    _write_progress_snapshot(store=store, session=session)
    return entry


def close_maintainer_session(*, repo_root: Path, run_key: str) -> dict[str, Any]:
    store, session, graph_spec = _load_maintainer_session(repo_root=repo_root, run_key=run_key)
    journal = _read_jsonl(store.artifact_path("graph/NodeJournal.jsonl"))
    _assert_frozen_session_inputs_current(repo_root=repo_root.resolve(), session=session)
    _assert_reviewed_scope_current(repo_root=repo_root.resolve(), session=session, journal=journal)
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
    closeout_ref_path = Path(str(session["closeout_ref_ref"]))
    session_created_at_utc = str(session.get("created_at_utc") or "")
    session_created_at_epoch_ns = session.get("created_at_epoch_ns")
    current_authority = _closeout_authority_token(
        created_at_epoch_ns=session_created_at_epoch_ns,
        created_at_utc=session_created_at_utc,
        run_key=run_key,
    )
    if closeout_ref_path.exists():
        existing_closeout_ref = json.loads(closeout_ref_path.read_text(encoding="utf-8"))
        existing_run_key = str(existing_closeout_ref.get("run_key") or "")
        if existing_run_key and existing_run_key != run_key:
            existing_authority = _existing_closeout_authority_token(closeout_ref=existing_closeout_ref)
            if existing_authority > current_authority:
                raise ValueError(
                    "cannot overwrite newer stable closeout ref for the same execplan_ref"
                )
    closeout_ref = {
        "version": "1",
        "updated_at_utc": _utc_now(),
        "session_created_at_utc": session_created_at_utc,
        "session_created_at_epoch_ns": session_created_at_epoch_ns,
        "execplan_ref": str(session["execplan_ref"]),
        "run_key": run_key,
        "summary_ref": str(summary["summary_ref"]),
        "final_status": str(summary["final_status"]),
        "session_ref": str(store.artifact_path("graph/MaintainerSession.json")),
        "progress_ref": str(store.artifact_path("graph/MaintainerProgress.json")),
    }
    _write_json_overwrite(closeout_ref_path, closeout_ref)
    session["session_ref"] = str(store.artifact_path("graph/MaintainerSession.json"))
    _write_progress_snapshot(
        store=store,
        session=session,
        final_status=str(summary["final_status"]),
        summary_ref=str(summary["summary_ref"]),
    )
    return {**summary, "closeout_ref_ref": str(closeout_ref_path)}


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

    summary, arbitration_records, nested_lineage_records, scheduler_records = runtime._evaluate_execution(
        graph_spec=validated_graph_spec,
        node_executor=_executor,
        unresolved_exception=unresolved_exception,
        summary_overlay={
            "graph_spec_ref": str(graph_spec_path),
            "node_results_ref": str(node_results_path),
        },
    )
    summary, arbitration_records = _preserve_maintainer_bookkeeping_closeout(
        graph_spec=validated_graph_spec,
        node_results=canonical_results,
        summary=summary,
        arbitration_records=arbitration_records,
    )
    _validate_maintainer_closeout(summary)
    _write_node_results_json_with_legacy_backfill(
        store=store,
        rel="graph/NodeResults.json",
        obj=_actual_node_results(summary),
        summary=summary,
        stream="artifact",
    )
    summary_path = store.artifact_path("graph/GraphSummary.jsonl")
    existing_summary = _last_jsonl_obj(summary_path)
    if existing_summary is not None:
        legacy_summary_backfill = _summary_requires_executed_backfill(existing_summary, summary)
        if not legacy_summary_backfill and not _summary_matches_existing_graph_summary(existing_summary, summary):
            raise FileExistsError(f"append-only summary already exists with different content: {summary_path}")
        if legacy_summary_backfill:
            _write_jsonl_overwrite(summary_path, [summary])
        _write_arbitration_jsonl_with_legacy_backfill(
            store=store,
            rel="graph/arbitration.jsonl",
            objs=arbitration_records,
            stream="artifact",
        )
        _write_nested_lineage_jsonl_with_legacy_backfill(
            store=store,
            rel="graph/nested_lineage.jsonl",
            objs=nested_lineage_records,
            stream="artifact",
        )
        _write_scheduler_jsonl_with_legacy_backfill(
            store=store,
            rel="graph/scheduler.jsonl",
            objs=scheduler_records,
            stream="artifact",
        )
        return {**summary, "summary_ref": str(summary_path)}
    return runtime._persist_execution(
        summary=summary,
        arbitration_records=arbitration_records,
        nested_lineage_records=nested_lineage_records,
        scheduler_records=scheduler_records,
    )


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
