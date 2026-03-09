#!/usr/bin/env python3
"""Contract: LeanAtlas worktree orchestration must exist as a LOOP host adapter."""

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
    print(f"[loop-worktree-adapter][FAIL] {msg}", file=sys.stderr)
    return 2


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    try:
        from tools.loop.worktree_adapter import materialize_worktree_child, remove_worktree_child
    except Exception as exc:  # noqa: BLE001
        return _fail(f"missing worktree adapter surface: {exc}")

    with tempfile.TemporaryDirectory(prefix="loop_worktree_adapter_") as td:
        repo = Path(td) / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        _git(repo, "init")
        _git(repo, "config", "user.email", "loop@example.com")
        _git(repo, "config", "user.name", "Loop Test")
        _write(repo / "README.md", "# repo\n")
        _write(repo / "tools" / "loop" / "target.py", "VALUE = 1\n")
        _git(repo, "add", "README.md", "tools/loop/target.py")
        _git(repo, "commit", "-m", "initial")

        child = materialize_worktree_child(
            repo_root=repo,
            batch_id="master-plan-completion",
            wave_id="review-wave",
            base_ref="HEAD",
        )
        metadata_ref = Path(str(child["metadata_ref"]))
        worktree_path = Path(str(child["worktree_path"]))
        if not metadata_ref.exists():
            return _fail("worktree adapter must persist metadata for the child worktree")
        if not worktree_path.exists():
            return _fail("worktree adapter must materialize the child worktree path")
        child_obj = _read_json(metadata_ref)
        if child_obj.get("batch_id") != "master-plan-completion":
            return _fail("worktree metadata must preserve batch_id")
        if child_obj.get("wave_id") != "review-wave":
            return _fail("worktree metadata must preserve wave_id")
        if child_obj.get("base_ref") != "HEAD":
            return _fail("worktree metadata must preserve base_ref")

        top_level = subprocess.run(
            ["git", "-C", str(worktree_path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if Path(top_level) != worktree_path.resolve():
            return _fail("materialized child workspace must be a real git worktree")
        if not (worktree_path / "tools" / "loop" / "target.py").exists():
            return _fail("child worktree must contain tracked repo files")

        child_again = materialize_worktree_child(
            repo_root=repo,
            batch_id="master-plan-completion",
            wave_id="review-wave",
            base_ref="HEAD",
        )
        if child_again["worktree_path"] != child["worktree_path"]:
            return _fail("identical worktree materialization should be idempotent")

        (worktree_path / "tools" / "loop" / "target.py").write_text("VALUE = 999\n", encoding="utf-8")
        (worktree_path / "scratch.txt").write_text("leftover\n", encoding="utf-8")
        child_cleaned = materialize_worktree_child(
            repo_root=repo,
            batch_id="master-plan-completion",
            wave_id="review-wave",
            base_ref="HEAD",
        )
        if child_cleaned["worktree_path"] != child["worktree_path"]:
            return _fail("dirty-worktree refresh should reuse the deterministic child worktree path")
        restored_value = (worktree_path / "tools" / "loop" / "target.py").read_text(encoding="utf-8")
        if restored_value != "VALUE = 1\n":
            return _fail("worktree rematerialization must discard tracked edits left in the cached child worktree")
        if (worktree_path / "scratch.txt").exists():
            return _fail("worktree rematerialization must discard untracked files left in the cached child worktree")
        clean_status = subprocess.run(
            ["git", "-C", str(worktree_path), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if clean_status:
            return _fail("reused child worktrees must be clean before they are handed back to a new execution")

        first_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        _write(repo / "tools" / "loop" / "target.py", "VALUE = 2\n")
        _git(repo, "add", "tools/loop/target.py")
        _git(repo, "commit", "-m", "second")
        second_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if second_commit == first_commit:
            return _fail("worktree adapter contract test requires distinct commits")

        child_updated = materialize_worktree_child(
            repo_root=repo,
            batch_id="master-plan-completion",
            wave_id="review-wave",
            base_ref=second_commit,
        )
        if child_updated["worktree_path"] != child["worktree_path"]:
            return _fail("base-ref refresh should reuse the deterministic child worktree path")
        updated_obj = _read_json(metadata_ref)
        if updated_obj.get("base_ref") != second_commit:
            return _fail("worktree metadata must refresh base_ref when the requested revision changes")
        if updated_obj.get("head_commit") != second_commit:
            return _fail("worktree metadata must refresh head_commit when the requested revision changes")
        worktree_head = subprocess.run(
            ["git", "-C", str(worktree_path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if worktree_head != second_commit:
            return _fail("rematerialized child worktree must track the newly requested base revision")

        removal = remove_worktree_child(
            repo_root=repo,
            batch_id="master-plan-completion",
            wave_id="review-wave",
        )
        if Path(str(removal["metadata_ref"])) != metadata_ref:
            return _fail("worktree removal must preserve the same metadata ref")
        removed_obj = _read_json(metadata_ref)
        if not removed_obj.get("removed_at_utc"):
            return _fail("worktree removal must record removed_at_utc in metadata")
        if worktree_path.exists():
            return _fail("worktree removal must remove the child worktree path")

        print("[loop-worktree-adapter] OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
