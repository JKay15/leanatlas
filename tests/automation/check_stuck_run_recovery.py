#!/usr/bin/env python3
"""Contract: stuck automation run recovery tool must detect and repair stale IN_PROGRESS rows."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "coordination" / "recover_stuck_automation_runs.py"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _prepare_db(db_path: Path, now_ms: int) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE automations (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              prompt TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'ACTIVE',
              next_run_at INTEGER,
              last_run_at INTEGER,
              cwds TEXT NOT NULL DEFAULT '[]',
              rrule TEXT NOT NULL DEFAULT 'FREQ=HOURLY;INTERVAL=24;BYMINUTE=0',
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );
            CREATE TABLE automation_runs (
              thread_id TEXT PRIMARY KEY,
              automation_id TEXT NOT NULL,
              status TEXT NOT NULL,
              read_at INTEGER,
              thread_title TEXT,
              source_cwd TEXT,
              inbox_title TEXT,
              inbox_summary TEXT,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL,
              archived_user_message TEXT,
              archived_assistant_message TEXT,
              archived_reason TEXT
            );
            """
        )
        con.execute(
            """
            INSERT INTO automations(id,name,prompt,status,cwds,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                "nightly-reporting-integrity",
                "Nightly Reporting Integrity",
                "prompt",
                "ACTIVE",
                json.dumps([str(ROOT)]),
                now_ms - 100_000,
                now_ms - 100_000,
            ),
        )
        con.execute(
            """
            INSERT INTO automation_runs(thread_id,automation_id,status,source_cwd,created_at,updated_at)
            VALUES(?,?,?,?,?,?)
            """,
            (
                "stuck-thread-1",
                "nightly-reporting-integrity",
                "IN_PROGRESS",
                str(ROOT),
                now_ms - 2_000_000,
                now_ms - 2_000_000,
            ),
        )
        con.execute(
            """
            INSERT INTO automation_runs(thread_id,automation_id,status,source_cwd,created_at,updated_at)
            VALUES(?,?,?,?,?,?)
            """,
            (
                "fresh-thread-1",
                "nightly-reporting-integrity",
                "IN_PROGRESS",
                str(ROOT),
                now_ms - 30_000,
                now_ms - 30_000,
            ),
        )
        con.commit()
    finally:
        con.close()


def _status(db_path: Path, thread_id: str) -> str:
    con = sqlite3.connect(db_path)
    try:
        row = con.execute("SELECT status FROM automation_runs WHERE thread_id = ?", (thread_id,)).fetchone()
        _require(row is not None, f"missing row for {thread_id}")
        return str(row[0])
    finally:
        con.close()


def main() -> int:
    _require(SCRIPT.exists(), "missing tools/coordination/recover_stuck_automation_runs.py")

    with tempfile.TemporaryDirectory(prefix="leanatlas_stuck_recovery_") as td:
        tmp = Path(td)
        db_path = tmp / "codex-dev.db"
        now_ms = 1_772_000_000_000
        _prepare_db(db_path, now_ms=now_ms)

        dry = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--db-path",
                str(db_path),
                "--max-in-progress-minutes",
                "10",
                "--dry-run",
                "--now-ms",
                str(now_ms),
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        _require(dry.returncode == 0, f"dry-run failed: {dry.stderr.strip()}")
        _require(_status(db_path, "stuck-thread-1") == "IN_PROGRESS", "dry-run must not mutate db state")
        _require("stuck-thread-1" in dry.stdout, "dry-run must report stale stuck thread")
        _require("fresh-thread-1" not in dry.stdout, "fresh in-progress run must not be selected")

        apply = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--db-path",
                str(db_path),
                "--max-in-progress-minutes",
                "10",
                "--apply",
                "--skip-rerun",
                "--now-ms",
                str(now_ms),
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        _require(apply.returncode == 0, f"apply failed: {apply.stderr.strip()}")
        _require(_status(db_path, "stuck-thread-1") == "PENDING_REVIEW", "apply must repair stale stuck row")
        _require(_status(db_path, "fresh-thread-1") == "IN_PROGRESS", "fresh row must stay IN_PROGRESS")

    print("[automation.stuck-recovery][PASS]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[automation.stuck-recovery][FAIL] {ex}", file=sys.stderr)
        raise SystemExit(1)
