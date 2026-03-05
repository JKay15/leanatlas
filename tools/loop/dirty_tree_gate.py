#!/usr/bin/env python3
"""Deterministic DirtyTreeGate snapshot + validator for LOOP completion."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

from tools.workflow.run_cmd import run_cmd

PASS_ALLOWED_DISPOSITIONS = {"CLEAN", "COMMITTED", "IGNORED_ONLY"}


def _run_git(repo_root: Path, args: list[str], *, label: str) -> dict[str, Any]:
    try:
        with tempfile.TemporaryDirectory(prefix="leanatlas_dirty_tree_cmd_") as td:
            result = run_cmd(
                cmd=["git", *args],
                cwd=repo_root,
                log_dir=Path(td),
                label=label,
                timeout_s=20,
                capture_text=True,
            )
            exit_code = int(result.span.get("exit_code", 1))
            return {
                "ok": exit_code == 0,
                "exit_code": exit_code,
                "stdout": str(result.stdout_text or ""),
                "stderr": str(result.stderr_text or ""),
            }
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }


def _git_head_commit(repo_root: Path) -> str | None:
    cmd = _run_git(repo_root, ["rev-parse", "HEAD"], label="dirty_tree_head")
    if not cmd["ok"]:
        return None
    value = str(cmd.get("stdout") or "").strip()
    return value if value else None


def _is_not_git_repo_error(stderr: str) -> bool:
    s = str(stderr or "").lower()
    return "not a git repository" in s


def _git_toplevel_probe(repo_root: Path) -> dict[str, Any]:
    cmd = _run_git(repo_root, ["rev-parse", "--show-toplevel"], label="dirty_tree_toplevel")
    if not cmd["ok"]:
        if _is_not_git_repo_error(str(cmd.get("stderr") or "")):
            return {
                "probe_ok": True,
                "in_git_repo": False,
                "git_root": None,
                "exit_code": int(cmd.get("exit_code", 1)),
                "stderr": str(cmd.get("stderr") or ""),
            }
        return {
            "probe_ok": False,
            "in_git_repo": True,
            "git_root": None,
            "exit_code": int(cmd.get("exit_code", 1)),
            "stderr": str(cmd.get("stderr") or ""),
        }
    value = str(cmd.get("stdout") or "").strip()
    if not value:
        return {
            "probe_ok": False,
            "in_git_repo": True,
            "git_root": None,
            "exit_code": int(cmd.get("exit_code", 1)),
            "stderr": "empty output from git rev-parse --show-toplevel",
        }
    try:
        return {
            "probe_ok": True,
            "in_git_repo": True,
            "git_root": Path(value).resolve(),
            "exit_code": int(cmd.get("exit_code", 0)),
            "stderr": str(cmd.get("stderr") or ""),
        }
    except Exception as exc:
        return {
            "probe_ok": False,
            "in_git_repo": True,
            "git_root": None,
            "exit_code": int(cmd.get("exit_code", 1)),
            "stderr": f"invalid top-level path: {type(exc).__name__}: {exc}",
        }


def collect_dirty_tree_snapshot(repo_root: Path | str, *, sample_limit: int = 50) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    probe = _git_toplevel_probe(root)
    if probe["probe_ok"] and (probe["in_git_repo"] is False):
        return {
            "checked": True,
            "in_git_repo": False,
            "is_clean": True,
            "disposition": "NO_GIT_CONTEXT",
            "head_commit": None,
            "tracked_entry_count": 0,
            "untracked_entry_count": 0,
            "changed_entry_count": 0,
            "status_porcelain_sample": [],
        }
    if not probe["probe_ok"]:
        exit_code = int(probe.get("exit_code", 1))
        stderr = str(probe.get("stderr") or "")
        return {
            "checked": True,
            "in_git_repo": True,
            "is_clean": False,
            "disposition": "DIRTY_PENDING",
            "head_commit": None,
            "tracked_entry_count": 1,
            "untracked_entry_count": 0,
            "changed_entry_count": 1,
            "status_porcelain_sample": [f"! git top-level probe failed (exit={exit_code}): {stderr}".strip()],
        }
    git_root = probe.get("git_root")
    if not isinstance(git_root, Path):
        return {
            "checked": True,
            "in_git_repo": True,
            "is_clean": False,
            "disposition": "DIRTY_PENDING",
            "head_commit": None,
            "tracked_entry_count": 1,
            "untracked_entry_count": 0,
            "changed_entry_count": 1,
            "status_porcelain_sample": ["! git top-level probe returned non-path result"],
        }

    cmd = _run_git(git_root, ["status", "--porcelain=v1", "-uall"], label="dirty_tree_status")
    if not cmd["ok"]:
        return {
            "checked": True,
            "in_git_repo": True,
            "is_clean": False,
            "disposition": "DIRTY_PENDING",
            "head_commit": _git_head_commit(git_root),
            "tracked_entry_count": 1,
            "untracked_entry_count": 0,
            "changed_entry_count": 1,
            "status_porcelain_sample": [f"! git status failed (exit={int(cmd.get('exit_code', 1))})"],
        }
    lines = [ln for ln in str(cmd.get("stdout") or "").splitlines() if ln.strip()]
    tracked = 0
    untracked = 0
    for ln in lines:
        if ln.startswith("?? "):
            untracked += 1
        else:
            tracked += 1
    changed = tracked + untracked
    is_clean = bool(cmd.get("ok")) and changed == 0
    return {
        "checked": True,
        "in_git_repo": True,
        "is_clean": bool(is_clean),
        "disposition": "CLEAN" if is_clean else "DIRTY_PENDING",
        "head_commit": _git_head_commit(git_root),
        "tracked_entry_count": tracked,
        "untracked_entry_count": untracked,
        "changed_entry_count": changed,
        "status_porcelain_sample": lines[: max(0, int(sample_limit))],
    }


def validate_dirty_tree_snapshot(snapshot: dict[str, Any], *, final_state: str | None = None) -> list[str]:
    errs: list[str] = []
    dt = snapshot
    if not isinstance(dt, dict):
        return ["dirty tree gate: dirty_tree block must be an object"]

    if "head_commit" not in dt:
        errs.append("dirty tree gate: dirty_tree.head_commit must be present (sha or null)")

    if dt.get("checked") is not True:
        errs.append("dirty tree gate: dirty_tree.checked must be true")

    in_git = bool(dt.get("in_git_repo", False))
    is_clean = bool(dt.get("is_clean", False))
    disposition = str(dt.get("disposition") or "").strip()

    try:
        tracked = int(dt.get("tracked_entry_count", 0))
        untracked = int(dt.get("untracked_entry_count", 0))
        changed = int(dt.get("changed_entry_count", 0))
    except Exception:
        errs.append("dirty tree gate: tracked/untracked/changed counts must be integers")
        tracked = untracked = changed = -1

    sample = dt.get("status_porcelain_sample") or []
    if not isinstance(sample, list) or any(not isinstance(x, str) for x in sample):
        errs.append("dirty tree gate: status_porcelain_sample must be an array of strings")
        sample = []

    if tracked >= 0 and untracked >= 0 and changed >= 0 and changed != tracked + untracked:
        errs.append("dirty tree gate: changed_entry_count must equal tracked_entry_count + untracked_entry_count")
    if changed == 0 and sample:
        errs.append("dirty tree gate: clean worktree must not include non-empty status_porcelain_sample")
    if changed > 0 and not sample:
        errs.append("dirty tree gate: dirty worktree must include status_porcelain_sample evidence")

    if in_git:
        if disposition == "NO_GIT_CONTEXT":
            errs.append("dirty tree gate: in_git_repo=true cannot use NO_GIT_CONTEXT disposition")
        if is_clean and changed != 0:
            errs.append("dirty tree gate: in_git_repo clean snapshot must have changed_entry_count=0")
        if (not is_clean) and changed == 0:
            errs.append("dirty tree gate: in_git_repo dirty snapshot must have changed_entry_count>0")
    else:
        if disposition != "NO_GIT_CONTEXT":
            errs.append("dirty tree gate: in_git_repo=false requires disposition=NO_GIT_CONTEXT")
        if is_clean is not True:
            errs.append("dirty tree gate: in_git_repo=false requires is_clean=true")
        if (tracked, untracked, changed) != (0, 0, 0):
            errs.append("dirty tree gate: in_git_repo=false requires zero tracked/untracked/changed counts")
        if sample:
            errs.append("dirty tree gate: in_git_repo=false requires empty status_porcelain_sample")
        if dt.get("head_commit", None) is not None:
            errs.append("dirty tree gate: in_git_repo=false requires head_commit=null")

    if str(final_state or "").strip().upper() == "PASSED" and in_git and (not is_clean):
        errs.append("dirty tree gate: PASSED run in git repo requires clean worktree (commit or ignore before pass)")
    if str(final_state or "").strip().upper() == "PASSED" and in_git and disposition not in PASS_ALLOWED_DISPOSITIONS:
        errs.append("dirty tree gate: PASSED run in git repo must use CLEAN/COMMITTED/IGNORED_ONLY disposition")

    return errs


def run_dirty_tree_gate(
    repo_root: Path | str,
    *,
    final_state: str | None = None,
    sample_limit: int = 50,
) -> dict[str, Any]:
    snapshot = collect_dirty_tree_snapshot(repo_root, sample_limit=sample_limit)
    errors = validate_dirty_tree_snapshot(snapshot, final_state=final_state)
    return {
        "repo_root": str(Path(repo_root).resolve()),
        "final_state": str(final_state or ""),
        "pass": len(errors) == 0,
        "errors": errors,
        "dirty_tree": snapshot,
    }


def _dump_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run deterministic DirtyTreeGate.")
    ap.add_argument("--repo-root", type=Path, default=Path.cwd())
    ap.add_argument("--final-state", type=str, default="")
    ap.add_argument("--sample-limit", type=int, default=50)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    report = run_dirty_tree_gate(
        args.repo_root,
        final_state=(args.final_state or ""),
        sample_limit=max(0, int(args.sample_limit)),
    )
    if args.out is not None:
        _dump_json(args.out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if bool(report.get("pass")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
