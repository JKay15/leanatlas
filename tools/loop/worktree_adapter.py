#!/usr/bin/env python3
"""LeanAtlas worktree orchestration as a host adapter on top of LOOP core."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TOKEN_SANITIZER = re.compile(r"[^A-Za-z0-9._-]+")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _slug_token(raw: str, *, fallback: str) -> str:
    token = _TOKEN_SANITIZER.sub("-", str(raw).strip()).strip(".-_")
    return token or fallback


def _metadata_path(*, repo_root: Path, batch_id: str, wave_id: str) -> Path:
    return (
        repo_root.resolve()
        / "artifacts"
        / "loop_runtime"
        / "worktrees"
        / "by_batch"
        / _slug_token(batch_id, fallback="batch")
        / f"{_slug_token(wave_id, fallback='wave')}.json"
    )


def _worktree_path(*, repo_root: Path, batch_id: str, wave_id: str) -> Path:
    return (
        repo_root.resolve()
        / ".cache"
        / "leanatlas"
        / "worktrees"
        / "by_batch"
        / _slug_token(batch_id, fallback="batch")
        / _slug_token(wave_id, fallback="wave")
    )


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(obj), encoding="utf-8")


def _run_cmd(*args: Any, **kwargs: Any) -> Any:
    from tools.workflow.run_cmd import run_cmd

    return run_cmd(*args, **kwargs)


def _git_capture(*, repo_root: Path, label: str, cmd: list[str]) -> str:
    log_dir = repo_root.resolve() / "artifacts" / "loop_runtime" / "worktrees" / "cmd"
    result = _run_cmd(
        cmd=cmd,
        cwd=repo_root,
        log_dir=log_dir,
        label=label,
        timeout_s=120,
        idle_timeout_s=60,
        capture_text=True,
    )
    if int(result.span.get("exit_code", -1)) != 0:
        raise RuntimeError(f"git command failed for `{label}`: {cmd}")
    return str(result.stdout_text or "").strip()


def _resolve_revision(*, repo_root: Path, label: str, rev: str) -> str:
    return _git_capture(
        repo_root=repo_root,
        label=label,
        cmd=["git", "rev-parse", str(rev)],
    )


def _worktree_head_commit(*, repo_root: Path, worktree_path: Path, wave_id: str) -> str:
    return _git_capture(
        repo_root=repo_root,
        label=f"{wave_id}.worktree_head",
        cmd=["git", "-C", str(worktree_path), "rev-parse", "HEAD"],
    )


def _worktree_is_clean(*, repo_root: Path, worktree_path: Path, wave_id: str) -> bool:
    status = _git_capture(
        repo_root=repo_root,
        label=f"{wave_id}.worktree_status",
        cmd=["git", "-C", str(worktree_path), "status", "--porcelain"],
    )
    return not status


def materialize_worktree_child(
    *,
    repo_root: Path,
    batch_id: str,
    wave_id: str,
    base_ref: str = "HEAD",
) -> dict[str, str]:
    repo_root = Path(repo_root).resolve()
    metadata_ref = _metadata_path(repo_root=repo_root, batch_id=batch_id, wave_id=wave_id)
    worktree_path = _worktree_path(repo_root=repo_root, batch_id=batch_id, wave_id=wave_id)
    requested_base_ref = str(base_ref)
    requested_head_commit = _resolve_revision(
        repo_root=repo_root,
        label=f"{wave_id}.requested_head",
        rev=requested_base_ref,
    )
    if metadata_ref.exists() and worktree_path.exists():
        metadata = json.loads(metadata_ref.read_text(encoding="utf-8"))
        cached_base_ref = str(metadata.get("base_ref") or "")
        cached_head_commit = str(metadata.get("head_commit") or "")
        try:
            current_worktree_head = _worktree_head_commit(
                repo_root=repo_root,
                worktree_path=worktree_path,
                wave_id=wave_id,
            )
        except Exception:  # noqa: BLE001
            current_worktree_head = ""
        if (
            cached_base_ref == requested_base_ref
            and cached_head_commit == requested_head_commit
            and current_worktree_head == requested_head_commit
            and _worktree_is_clean(
                repo_root=repo_root,
                worktree_path=worktree_path,
                wave_id=wave_id,
            )
        ):
            return metadata
        remove_worktree_child(
            repo_root=repo_root,
            batch_id=batch_id,
            wave_id=wave_id,
        )

    _git_capture(repo_root=repo_root, label=f"{wave_id}.root", cmd=["git", "rev-parse", "--show-toplevel"])
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    if not worktree_path.exists():
        _git_capture(
            repo_root=repo_root,
            label=f"{wave_id}.add",
            cmd=["git", "worktree", "add", "--detach", str(worktree_path), requested_base_ref],
        )
    head_commit = _worktree_head_commit(
        repo_root=repo_root,
        worktree_path=worktree_path,
        wave_id=wave_id,
    )
    metadata = {
        "version": "1",
        "batch_id": str(batch_id),
        "wave_id": str(wave_id),
        "base_ref": requested_base_ref,
        "worktree_path": str(worktree_path),
        "metadata_ref": str(metadata_ref),
        "head_commit": head_commit,
        "created_at_utc": _utc_now(),
        "removed_at_utc": None,
    }
    _write_json(metadata_ref, metadata)
    return metadata


def remove_worktree_child(
    *,
    repo_root: Path,
    batch_id: str,
    wave_id: str,
) -> dict[str, str]:
    repo_root = Path(repo_root).resolve()
    metadata_ref = _metadata_path(repo_root=repo_root, batch_id=batch_id, wave_id=wave_id)
    worktree_path = _worktree_path(repo_root=repo_root, batch_id=batch_id, wave_id=wave_id)
    metadata: dict[str, Any] = {}
    if metadata_ref.exists():
        metadata = json.loads(metadata_ref.read_text(encoding="utf-8"))
    if worktree_path.exists():
        _git_capture(
            repo_root=repo_root,
            label=f"{wave_id}.remove",
            cmd=["git", "worktree", "remove", "--force", str(worktree_path)],
        )
        _git_capture(
            repo_root=repo_root,
            label=f"{wave_id}.prune",
            cmd=["git", "worktree", "prune"],
        )
    metadata.update(
        {
            "version": "1",
            "batch_id": str(batch_id),
            "wave_id": str(wave_id),
            "base_ref": str(metadata.get("base_ref") or "HEAD"),
            "worktree_path": str(worktree_path),
            "metadata_ref": str(metadata_ref),
            "head_commit": str(metadata.get("head_commit") or ""),
            "created_at_utc": str(metadata.get("created_at_utc") or _utc_now()),
            "removed_at_utc": _utc_now(),
        }
    )
    _write_json(metadata_ref, metadata)
    return metadata


__all__ = [
    "materialize_worktree_child",
    "remove_worktree_child",
]
