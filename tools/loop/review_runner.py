#!/usr/bin/env python3
"""Deterministic reviewer-runner helpers for maintainer LOOP closeout."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools.loop.review_canonical import (
    build_canonical_review_result,
    extract_canonical_response,
    provider_adapter,
)
from tools.loop.review_prompting import inspect_review_prompt_protocol
from tools.workflow.run_cmd import run_cmd


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _slug(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    safe = safe.strip("._")
    return safe or "review"


def _resolve_repo_path(repo_root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    path = path.resolve()
    repo_resolved = repo_root.resolve()
    try:
        path.relative_to(repo_resolved)
    except ValueError as exc:
        raise ValueError(f"path must stay under repo_root: {raw}") from exc
    return path


def _normalize_repo_file_refs(
    *,
    repo_root: Path,
    raw_refs: Sequence[str | Path],
    field_name: str,
    require_non_empty: bool = False,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_refs:
        p = _resolve_repo_path(repo_root, raw)
        if not p.exists():
            raise ValueError(f"{field_name} path does not exist: {raw}")
        if not p.is_file():
            raise ValueError(f"{field_name} MUST be file-scoped; got non-file path: {raw}")
        rel = p.relative_to(repo_root.resolve()).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        normalized.append(rel)
    normalized.sort()
    if require_non_empty and not normalized:
        raise ValueError(f"{field_name} must be a non-empty sequence of repo files")
    return normalized


def _normalize_scope_paths(*, repo_root: Path, scope_paths: Sequence[str | Path]) -> list[str]:
    return _normalize_repo_file_refs(
        repo_root=repo_root,
        raw_refs=scope_paths,
        field_name="scope_paths",
        require_non_empty=True,
    )


def _normalize_instruction_scope_refs(
    *,
    repo_root: Path,
    instruction_scope_refs: Sequence[str | Path],
    active_repo_files: Sequence[str],
) -> list[str]:
    normalized = _normalize_repo_file_refs(
        repo_root=repo_root,
        raw_refs=instruction_scope_refs,
        field_name="instruction_scope_refs",
        require_non_empty=True,
    )
    expected_chain = _expected_instruction_scope_chain(repo_root=repo_root, active_repo_files=active_repo_files)
    missing = [ref for ref in expected_chain if ref not in normalized]
    if missing:
        raise ValueError(
            "instruction_scope_refs must include the active AGENTS.md chain; "
            f"missing: {', '.join(missing)}"
        )
    return normalized


def _normalize_required_context_refs(
    *, repo_root: Path, required_context_refs: Sequence[str | Path]
) -> list[str]:
    return _normalize_repo_file_refs(
        repo_root=repo_root,
        raw_refs=required_context_refs,
        field_name="required_context_refs",
        require_non_empty=True,
    )


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


def compute_review_scope_fingerprint(*, repo_root: Path, scope_paths: Sequence[str | Path]) -> str:
    repo_root = repo_root.resolve()
    normalized = _normalize_scope_paths(repo_root=repo_root, scope_paths=scope_paths)
    payload = {rel: _sha256_file(repo_root / rel) for rel in normalized}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _scope_observed_stamp(*, repo_root: Path, scope_paths: Sequence[str | Path]) -> str:
    repo_root = repo_root.resolve()
    normalized = _normalize_scope_paths(repo_root=repo_root, scope_paths=scope_paths)
    payload: dict[str, dict[str, int | str | None]] = {}
    for rel in normalized:
        path = repo_root / rel
        stat = path.stat()
        payload[rel] = {
            "sha256": _sha256_file(path),
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "ctime_ns": int(getattr(stat, "st_ctime_ns", stat.st_ctime_ns)),
        }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, sort_keys=True) + "\n")


def _write_attempts_md(path: Path, attempts: Sequence[Mapping[str, Any]]) -> None:
    lines = ["# Review Attempts", ""]
    for attempt in attempts:
        lines.append(f"## Attempt {attempt['attempt_index']}")
        lines.append(f"- status: `{attempt['status']}`")
        lines.append(f"- reason_code: `{attempt['reason_code']}`")
        lines.append(f"- started_at_utc: `{attempt['started_at_utc']}`")
        lines.append(f"- finished_at_utc: `{attempt['finished_at_utc']}`")
        span = attempt.get("command_span")
        if isinstance(span, dict):
            exit_code = span.get("exit_code")
            lines.append(f"- exit_code: `{exit_code}`")
            if span.get("timed_out") is True:
                lines.append("- timed_out: `true`")
            stdout_path = span.get("stdout_path")
            stderr_path = span.get("stderr_path")
            if stdout_path:
                lines.append(f"- stdout_path: `{stdout_path}`")
            if stderr_path:
                lines.append(f"- stderr_path: `{stderr_path}`")
        semantic_response_source = attempt.get("semantic_response_source")
        if semantic_response_source:
            lines.append(f"- semantic_response_source: `{semantic_response_source}`")
        provider_event_ref = attempt.get("provider_event_ref")
        if provider_event_ref:
            lines.append(f"- provider_event_ref: `{provider_event_ref}`")
        canonical_result_ref = attempt.get("canonical_result_ref")
        if canonical_result_ref:
            lines.append(f"- canonical_result_ref: `{canonical_result_ref}`")
        lines.append(
            f"- scope_fingerprint_before: `{attempt.get('scope_fingerprint_before') or ''}`"
        )
        lines.append(
            f"- scope_fingerprint_after: `{attempt.get('scope_fingerprint_after') or ''}`"
        )
        lines.append(
            f"- scope_observed_stamp_before: `{attempt.get('scope_observed_stamp_before') or ''}`"
        )
        lines.append(
            f"- scope_observed_stamp_after: `{attempt.get('scope_observed_stamp_after') or ''}`"
        )
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_review_closure(
    *,
    repo_root: Path,
    review_id: str,
    prompt_path: str | Path,
    response_path: str | Path,
    scope_paths: Sequence[str | Path],
    command: Sequence[str],
    expected_scope_fingerprint: str | None = None,
    timeout_s: int | None = None,
    idle_timeout_s: int | None = None,
    semantic_idle_timeout_s: int | None = None,
    max_attempts: int = 1,
    env: Mapping[str, str] | None = None,
    agent_provider_id: str = "codex_cli",
    agent_profile: str | None = None,
    resolved_invocation_signature: str = "codex exec review",
    instruction_scope_refs: Sequence[str] | None = None,
    required_context_refs: Sequence[str] | None = None,
    required_prompt_protocol_id: str | None = None,
    allow_timebox_override: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    if not command or not all(isinstance(part, str) and part for part in command):
        raise ValueError("command must be a non-empty argv sequence")
    if int(max_attempts) <= 0:
        raise ValueError("max_attempts must be >= 1")

    prompt = _resolve_repo_path(repo_root, prompt_path)
    if not prompt.exists() or not prompt.is_file():
        raise ValueError("prompt_path must exist and be a file")
    prompt_text = prompt.read_text(encoding="utf-8")
    if not prompt_text.strip():
        raise ValueError("prompt_path must be non-empty")
    prompt_protocol = inspect_review_prompt_protocol(prompt_text)
    if required_prompt_protocol_id is not None:
        required_prompt_protocol_id = str(required_prompt_protocol_id).strip()
        if (
            prompt_protocol.get("protocol_id") != required_prompt_protocol_id
            or prompt_protocol.get("is_canonical") is not True
        ):
            raise ValueError(
                "required_prompt_protocol_id was not satisfied by prompt_path; "
                f"required_prompt_protocol_id={required_prompt_protocol_id}, "
                f"actual_protocol_id={prompt_protocol.get('protocol_id')}, "
                f"missing_sections={prompt_protocol.get('missing_sections')}"
            )

    response = _resolve_repo_path(repo_root, response_path)
    response.parent.mkdir(parents=True, exist_ok=True)

    normalized_scope = _normalize_scope_paths(repo_root=repo_root, scope_paths=scope_paths)
    normalized_required_context = _normalize_required_context_refs(
        repo_root=repo_root,
        required_context_refs=tuple(required_context_refs or ()),
    )
    normalized_instruction_scope = _normalize_instruction_scope_refs(
        repo_root=repo_root,
        instruction_scope_refs=tuple(instruction_scope_refs or ()),
        active_repo_files=[*normalized_scope, *normalized_required_context],
    )
    current_scope_fingerprint = compute_review_scope_fingerprint(repo_root=repo_root, scope_paths=normalized_scope)
    frozen_scope_fingerprint = expected_scope_fingerprint or current_scope_fingerprint
    if prompt_protocol.get("is_canonical") is True:
        mismatches: list[str] = []
        if str(prompt_protocol.get("review_id") or "") != str(review_id):
            mismatches.append("review_id")
        if str(prompt_protocol.get("agent_provider_id") or "") != str(agent_provider_id):
            mismatches.append("agent_provider_id")
        if agent_profile is not None and str(prompt_protocol.get("agent_profile") or "") != str(agent_profile):
            mismatches.append("agent_profile")
        if [str(path) for path in prompt_protocol.get("scope_paths") or []] != normalized_scope:
            mismatches.append("scope_paths")
        if [str(ref) for ref in prompt_protocol.get("instruction_scope_refs") or []] != normalized_instruction_scope:
            mismatches.append("instruction_scope_refs")
        if [str(ref) for ref in prompt_protocol.get("required_context_refs") or []] != normalized_required_context:
            mismatches.append("required_context_refs")
        if mismatches:
            raise ValueError(
                "canonical prompt frozen inputs must match run_review_closure arguments exactly; mismatched fields: "
                + ", ".join(mismatches)
            )
    adapter = provider_adapter(agent_provider_id)
    effective_timeout_s = int(adapter["default_timeout_s"] if timeout_s is None else timeout_s)
    effective_idle_timeout_s = int(adapter["default_idle_timeout_s"] if idle_timeout_s is None else idle_timeout_s)
    effective_semantic_idle_timeout_s = int(
        adapter["default_semantic_idle_timeout_s"]
        if semantic_idle_timeout_s is None
        else semantic_idle_timeout_s
    )
    minimum_observation_window_s = int(adapter["minimum_observation_window_s"])
    if not allow_timebox_override:
        too_short = [
            name
            for name, value in (
                ("timeout_s", effective_timeout_s),
                ("idle_timeout_s", effective_idle_timeout_s),
                ("semantic_idle_timeout_s", effective_semantic_idle_timeout_s),
            )
            if value < minimum_observation_window_s
        ]
        if too_short:
            raise ValueError(
                "minimum observation policy forbids provider timeboxes shorter than "
                f"{minimum_observation_window_s}s for {agent_provider_id}; got {', '.join(too_short)}"
            )

    safe_id = _slug(review_id)
    evidence_root = repo_root / "artifacts" / "reviews"
    attempts_jsonl = evidence_root / f"{safe_id}_attempts.jsonl"
    attempts_md = evidence_root / f"{safe_id}_attempts.md"
    scope_json = evidence_root / f"{safe_id}_scope.json"
    context_json = evidence_root / f"{safe_id}_context.json"
    summary_json = evidence_root / f"{safe_id}_summary.json"
    cmd_log_dir = evidence_root / f"{safe_id}_cmd"

    for path in (attempts_jsonl, attempts_md, scope_json, context_json, summary_json):
        if path.exists():
            raise FileExistsError(f"review evidence path already exists: {path}")

    scope_payload = {
        "review_id": review_id,
        "prompt_ref": str(prompt),
        "response_ref": str(response),
        "scope_paths": normalized_scope,
        "scope_fingerprint": frozen_scope_fingerprint,
        "generated_at_utc": _utc_now(),
    }
    _write_json(scope_json, scope_payload)
    context_payload = {
        "review_id": review_id,
        "generated_at_utc": _utc_now(),
        "agent_provider_id": agent_provider_id,
        "provider_adapter_id": adapter["adapter_id"],
        "resolved_invocation_signature": resolved_invocation_signature,
        "prompt_ref": str(prompt),
        "response_ref": str(response),
        "scope_ref": str(scope_json),
        "scope_paths": normalized_scope,
        "scope_fingerprint": frozen_scope_fingerprint,
        "instruction_scope_refs": normalized_instruction_scope,
        "required_context_refs": normalized_required_context,
        "prompt_protocol_id": (
            prompt_protocol.get("protocol_id") if prompt_protocol.get("is_canonical") is True else None
        ),
        "declared_prompt_protocol_id": prompt_protocol.get("protocol_id"),
        "required_prompt_protocol_id": required_prompt_protocol_id,
        "expected_semantic_sources": list(adapter["semantic_sources"]),
        "observation_policy": {
            "minimum_observation_window_s": minimum_observation_window_s,
            "timeout_s": effective_timeout_s,
            "idle_timeout_s": effective_idle_timeout_s,
            "semantic_idle_timeout_s": effective_semantic_idle_timeout_s,
            "subjective_early_termination_policy": "forbidden_without_explicit_exception",
        },
    }
    _write_json(context_json, context_payload)

    attempts: list[dict[str, Any]] = []
    last_reason_code = "UNKNOWN"
    result_state = "TOOLING_FAILURE"
    semantic_response_source: str | None = None
    provider_event_ref: str | None = None
    canonical_result_ref: str | None = None
    extraction_kind: str | None = None

    for attempt_index in range(1, int(max_attempts) + 1):
        started_at = _utc_now()
        before_fingerprint = compute_review_scope_fingerprint(repo_root=repo_root, scope_paths=normalized_scope)
        before_observed_stamp = _scope_observed_stamp(repo_root=repo_root, scope_paths=normalized_scope)
        canonical_json = evidence_root / f"{safe_id}_canonical_attempt{attempt_index}.json"
        if before_fingerprint != frozen_scope_fingerprint:
            canonical_result = build_canonical_review_result(
                review_id=review_id,
                attempt_index=attempt_index,
                agent_provider_id=agent_provider_id,
                provider_adapter_id=adapter["adapter_id"],
                status="STALE_INPUT",
                reason_code="STALE_INPUT",
                response_ref=str(response),
                response_exists=response.exists(),
                response_bytes=(response.stat().st_size if response.exists() else 0),
                semantic_response_source=None,
                extraction_kind=None,
                provider_event_ref=None,
                stdout_ref=None,
                stderr_ref=None,
            )
            _write_json(canonical_json, canonical_result)
            record = {
                "attempt_index": attempt_index,
                "status": "STALE_INPUT",
                "reason_code": "STALE_INPUT",
                "started_at_utc": started_at,
                "finished_at_utc": _utc_now(),
                "scope_fingerprint_before": before_fingerprint,
                "scope_fingerprint_after": before_fingerprint,
                "scope_observed_stamp_before": before_observed_stamp,
                "scope_observed_stamp_after": before_observed_stamp,
                "expected_scope_fingerprint": frozen_scope_fingerprint,
                "command_span": None,
                "response_ref": str(response),
                "response_exists": response.exists(),
                "response_bytes": response.stat().st_size if response.exists() else 0,
                "semantic_response_source": None,
                "provider_event_ref": None,
                "canonical_result_ref": str(canonical_json),
            }
            attempts.append(record)
            _append_jsonl(attempts_jsonl, record)
            _write_attempts_md(attempts_md, attempts)
            last_reason_code = "STALE_INPUT"
            result_state = "STALE_INPUT"
            canonical_result_ref = str(canonical_json)
            break

        if response.exists():
            response.unlink()

        merged_env = dict(env or {})
        merged_env.update(
            {
                "LEANATLAS_REVIEW_ATTEMPT_INDEX": str(attempt_index),
                "LEANATLAS_REVIEW_PROMPT_PATH": str(prompt),
                "LEANATLAS_REVIEW_RESPONSE_PATH": str(response),
                "LEANATLAS_REVIEW_SCOPE_FINGERPRINT": frozen_scope_fingerprint,
                "LEANATLAS_REVIEW_SCOPE_PATHS_JSON": json.dumps(normalized_scope, separators=(",", ":")),
                "LEANATLAS_REVIEW_CONTEXT_PACK_PATH": str(context_json),
                "LEANATLAS_REVIEW_INSTRUCTION_SCOPE_REFS_JSON": json.dumps(
                    normalized_instruction_scope, separators=(",", ":")
                ),
                "LEANATLAS_REVIEW_REQUIRED_CONTEXT_REFS_JSON": json.dumps(
                    normalized_required_context, separators=(",", ":")
                ),
            }
        )

        semantic_activity_streams: list[str] = []
        provider_event_stream = str(adapter.get("provider_event_jsonl_stream") or "").strip()
        if provider_event_stream in {"stdout", "stderr"}:
            semantic_activity_streams.append(provider_event_stream)

        cmd_result = run_cmd(
            cmd=list(command),
            cwd=repo_root,
            log_dir=cmd_log_dir,
            label=f"{safe_id}.attempt{attempt_index}",
            timeout_s=effective_timeout_s,
            idle_timeout_s=effective_idle_timeout_s,
            semantic_idle_timeout_s=effective_semantic_idle_timeout_s,
            semantic_activity_streams=semantic_activity_streams,
            semantic_activity_paths=[response],
            env=merged_env,
            capture_text=False,
        )
        span = dict(cmd_result.span)
        scope_state_error = False
        try:
            after_fingerprint = compute_review_scope_fingerprint(repo_root=repo_root, scope_paths=normalized_scope)
            after_observed_stamp = _scope_observed_stamp(repo_root=repo_root, scope_paths=normalized_scope)
        except (ValueError, FileNotFoundError):
            after_fingerprint = None
            after_observed_stamp = None
            scope_state_error = True
        response_exists = response.exists()
        response_bytes = response.stat().st_size if response_exists else 0
        response_text = response.read_text(encoding="utf-8").strip() if response_exists else ""
        attempt_semantic_source: str | None = None
        attempt_provider_event_ref: str | None = None
        attempt_extraction_kind: str | None = None

        status = "COMMAND_FAILED"
        reason_code = "COMMAND_FAILED"
        if (
            scope_state_error
            or after_fingerprint != frozen_scope_fingerprint
            or after_fingerprint != before_fingerprint
            or after_observed_stamp != before_observed_stamp
        ):
            status = "STALE_INPUT"
            reason_code = "STALE_INPUT"
            result_state = "STALE_INPUT"
        elif span.get("timeout_kind") == "semantic":
            status = "SEMANTIC_IDLE_TIMEOUT"
            reason_code = "SEMANTIC_IDLE_TIMEOUT"
        elif span.get("timed_out") is True or int(span.get("exit_code", -1)) == 124:
            status = "REVIEW_TIMEOUT"
            reason_code = "REVIEW_TIMEOUT"
        elif int(span.get("exit_code", -1)) != 0:
            status = "COMMAND_FAILED"
            reason_code = "COMMAND_FAILED"
        elif response_text:
            status = "SUCCEEDED"
            reason_code = "OK"
            if attempt_semantic_source is None:
                attempt_semantic_source = "response_file"
            result_state = "SUCCEEDED"
        else:
            extraction = extract_canonical_response(
                agent_provider_id=agent_provider_id,
                span=span,
                evidence_root=evidence_root,
            )
            terminal_message = str(extraction.get("response_text") or "").strip() or None
            attempt_provider_event_ref = extraction.get("provider_event_ref")
            attempt_semantic_source = extraction.get("semantic_response_source")
            attempt_extraction_kind = extraction.get("extraction_kind")
            if terminal_message:
                response.write_text(terminal_message.rstrip() + "\n", encoding="utf-8")
                response_exists = True
                response_bytes = response.stat().st_size
                status = "SUCCEEDED"
                reason_code = "OK"
                result_state = "SUCCEEDED"
            elif response_exists:
                status = "RESPONSE_INVALID"
                reason_code = "RESPONSE_EMPTY"
            else:
                status = "NO_TERMINAL_EVENT"
                reason_code = "NO_TERMINAL_EVENT"

        if status != "SUCCEEDED":
            attempt_semantic_source = None
            attempt_extraction_kind = None

        canonical_result = build_canonical_review_result(
            review_id=review_id,
            attempt_index=attempt_index,
            agent_provider_id=agent_provider_id,
            provider_adapter_id=adapter["adapter_id"],
            status=status,
            reason_code=reason_code,
            response_ref=str(response),
            response_exists=response_exists,
            response_bytes=response_bytes,
            semantic_response_source=attempt_semantic_source,
            extraction_kind=attempt_extraction_kind,
            provider_event_ref=attempt_provider_event_ref,
            stdout_ref=str(span.get("stdout_path") or "") or None,
            stderr_ref=str(span.get("stderr_path") or "") or None,
        )
        _write_json(canonical_json, canonical_result)

        record = {
            "attempt_index": attempt_index,
            "status": status,
            "reason_code": reason_code,
            "started_at_utc": started_at,
            "finished_at_utc": _utc_now(),
            "scope_fingerprint_before": before_fingerprint,
            "scope_fingerprint_after": after_fingerprint,
            "scope_observed_stamp_before": before_observed_stamp,
            "scope_observed_stamp_after": after_observed_stamp,
            "expected_scope_fingerprint": frozen_scope_fingerprint,
            "command_span": span,
            "response_ref": str(response),
            "response_exists": response_exists,
            "response_bytes": response_bytes,
            "semantic_response_source": attempt_semantic_source,
            "provider_event_ref": attempt_provider_event_ref,
            "canonical_result_ref": str(canonical_json),
        }
        attempts.append(record)
        _append_jsonl(attempts_jsonl, record)
        _write_attempts_md(attempts_md, attempts)

        last_reason_code = reason_code
        canonical_result_ref = str(canonical_json)
        if status == "SUCCEEDED":
            semantic_response_source = attempt_semantic_source
            provider_event_ref = attempt_provider_event_ref
            extraction_kind = attempt_extraction_kind
            break
        if status == "STALE_INPUT":
            break

    evidence_refs = [str(scope_json), str(context_json), str(attempts_md), str(attempts_jsonl)]
    if canonical_result_ref:
        evidence_refs.append(canonical_result_ref)
    if result_state == "SUCCEEDED":
        review_closeout: dict[str, Any] = {
            "mode": "REVIEW_RUN",
            "prompt_ref": str(prompt),
            "response_ref": str(response),
            "summary_ref": str(summary_json),
            "evidence_refs": evidence_refs,
        }
    else:
        skip_reason = "OTHER" if result_state == "STALE_INPUT" else "TRIAGED_TOOLING"
        review_closeout = {
            "mode": "REVIEW_SKIPPED",
            "skip_reason_code": skip_reason,
            "note": last_reason_code,
            "evidence_refs": evidence_refs,
        }

    summary = {
        "version": "0.1",
        "review_id": review_id,
        "generated_at_utc": _utc_now(),
        "agent_provider_id": agent_provider_id,
        "provider_adapter_id": adapter["adapter_id"],
        "agent_profile": agent_profile,
        "resolved_invocation_signature": resolved_invocation_signature,
        "instruction_scope_refs": normalized_instruction_scope,
        "required_context_refs": normalized_required_context,
        "scope_ref": str(scope_json),
        "context_pack_ref": str(context_json),
        "scope_fingerprint": frozen_scope_fingerprint,
        "attempts_ref": str(attempts_jsonl),
        "attempts_md_ref": str(attempts_md),
        "prompt_ref": str(prompt),
        "response_ref": str(response),
        "semantic_response_source": semantic_response_source,
        "provider_event_ref": provider_event_ref,
        "canonical_result_ref": canonical_result_ref,
        "extraction_kind": extraction_kind,
        "result_state": result_state,
        "reason_code": last_reason_code,
        "review_closeout": review_closeout,
    }
    _write_json(summary_json, summary)
    return {**summary, "summary_ref": str(summary_json)}


__all__ = ["compute_review_scope_fingerprint", "run_review_closure"]
