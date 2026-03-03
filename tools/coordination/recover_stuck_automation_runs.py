#!/usr/bin/env python3
"""Recover stale Codex App automation runs stuck in IN_PROGRESS.

Scope:
- Operates on Codex local state DB (`automation_runs` + `automations` tables).
- Marks stale IN_PROGRESS rows as PENDING_REVIEW.
- Optionally reruns affected automations via local wrapper in source workspace.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.workflow.run_cmd import run_cmd


@dataclass
class StuckRun:
    thread_id: str
    automation_id: str
    source_cwd: str
    created_at: int
    updated_at: int
    prompt: str


def _default_db_path() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    return codex_home / "sqlite" / "codex-dev.db"


def _now_ms(cli_now_ms: Optional[int]) -> int:
    if cli_now_ms is not None:
        return int(cli_now_ms)
    return int(time.time() * 1000)


def _load_stuck_runs(
    *,
    conn: sqlite3.Connection,
    cutoff_ms: int,
    automation_ids: List[str],
) -> List[StuckRun]:
    sql = """
    SELECT r.thread_id, r.automation_id, COALESCE(r.source_cwd, ''), r.created_at, r.updated_at, COALESCE(a.prompt, '')
    FROM automation_runs r
    LEFT JOIN automations a ON a.id = r.automation_id
    WHERE r.status = 'IN_PROGRESS'
      AND r.updated_at <= ?
    ORDER BY r.updated_at ASC
    """
    rows = conn.execute(sql, (cutoff_ms,)).fetchall()
    out: List[StuckRun] = []
    allow = set(automation_ids)
    for row in rows:
        item = StuckRun(
            thread_id=str(row[0]),
            automation_id=str(row[1]),
            source_cwd=str(row[2]),
            created_at=int(row[3]),
            updated_at=int(row[4]),
            prompt=str(row[5]),
        )
        if allow and item.automation_id not in allow:
            continue
        out.append(item)
    return out


def _extract_runner_id(x: StuckRun) -> str:
    m = re.search(r"--id\s+([A-Za-z0-9_-]+)", x.prompt)
    if m:
        return m.group(1)
    # Codex DB stores ids with hyphens; repo runner ids use underscores.
    return x.automation_id.replace("-", "_")


def _extract_advisor_mode(x: StuckRun) -> str:
    m = re.search(r"--advisor-mode\s+([A-Za-z0-9_-]+)", x.prompt)
    if m:
        mode = m.group(1)
        if mode in {"off", "auto", "force"}:
            return mode
    return "auto"


def _extract_verify_flag(x: StuckRun) -> bool:
    return "--verify" in x.prompt


def _repair_rows(
    *,
    conn: sqlite3.Connection,
    rows: List[StuckRun],
    now_ms: int,
) -> int:
    repaired = 0
    for x in rows:
        title = "Recovered stuck automation run"
        summary = (
            "Auto-recovery marked stale IN_PROGRESS as PENDING_REVIEW. "
            f"thread_id={x.thread_id} automation_id={x.automation_id}"
        )
        cur = conn.execute(
            """
            UPDATE automation_runs
            SET status = 'PENDING_REVIEW',
                updated_at = ?,
                inbox_title = ?,
                inbox_summary = ?
            WHERE thread_id = ?
              AND status = 'IN_PROGRESS'
            """,
            (now_ms, title, summary, x.thread_id),
        )
        if cur.rowcount:
            repaired += 1
    conn.commit()
    return repaired


def _rerun_once(
    *,
    x: StuckRun,
    logs_dir: Path,
) -> Dict[str, object]:
    source_root = Path(x.source_cwd).resolve()
    wrapper = source_root / "tools" / "coordination" / "run_automation_local.py"
    if not wrapper.exists():
        return {
            "thread_id": x.thread_id,
            "automation_id": x.automation_id,
            "ok": False,
            "reason": f"missing wrapper: {wrapper}",
        }

    cmd = [
        sys.executable,
        str(wrapper),
        "--id",
        _extract_runner_id(x),
        "--advisor-mode",
        _extract_advisor_mode(x),
    ]
    if _extract_verify_flag(x):
        cmd.append("--verify")

    res = run_cmd(
        cmd=cmd,
        cwd=source_root,
        log_dir=logs_dir,
        label=f"rerun_{x.automation_id}_{x.thread_id}",
        timeout_s=1800,
        capture_text=False,
    )
    rc = int(res.span.get("exit_code", 1))
    return {
        "thread_id": x.thread_id,
        "automation_id": x.automation_id,
        "runner_id": _extract_runner_id(x),
        "advisor_mode": _extract_advisor_mode(x),
        "verify": _extract_verify_flag(x),
        "ok": (rc == 0),
        "exit_code": rc,
        "evidence": res.span,
    }


def _dedupe_for_rerun(rows: List[StuckRun]) -> List[StuckRun]:
    out: List[StuckRun] = []
    seen: set[Tuple[str, str]] = set()
    for x in rows:
        key = (x.automation_id, x.source_cwd)
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-path", default=None, help="Override Codex sqlite DB path")
    ap.add_argument("--max-in-progress-minutes", type=int, default=8, help="Stale threshold in minutes")
    ap.add_argument("--automation-id", action="append", default=[], help="Only recover these automation ids")
    ap.add_argument("--dry-run", action="store_true", help="Do not mutate DB; print candidates only")
    ap.add_argument("--apply", action="store_true", help="Apply recovery updates")
    ap.add_argument("--skip-rerun", action="store_true", help="Do not rerun wrapper commands after repair")
    ap.add_argument("--now-ms", type=int, default=None, help="Inject deterministic current time (tests)")
    args = ap.parse_args()

    db_path = Path(args.db_path).resolve() if args.db_path else _default_db_path()
    if not db_path.exists():
        raise SystemExit(f"db not found: {db_path}")
    if not args.dry_run and not args.apply:
        ap.error("choose one mode: --dry-run or --apply")

    now_ms = _now_ms(args.now_ms)
    cutoff_ms = now_ms - int(args.max_in_progress_minutes) * 60 * 1000

    conn = sqlite3.connect(db_path)
    try:
        rows = _load_stuck_runs(
            conn=conn,
            cutoff_ms=cutoff_ms,
            automation_ids=list(args.automation_id or []),
        )

        stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now_ms / 1000.0))
        run_dir = ROOT / "artifacts" / "automation" / "recovery" / stamp
        logs_dir = run_dir / "Cmd"
        run_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        print(
            "[automation.recovery] "
            f"mode={'dry-run' if args.dry_run else 'apply'} "
            f"cutoff_ms={cutoff_ms} candidates={len(rows)} db={db_path}"
        )
        for x in rows:
            age_min = max(0.0, (now_ms - x.updated_at) / 60000.0)
            print(
                f" - thread_id={x.thread_id} automation_id={x.automation_id} "
                f"source_cwd={x.source_cwd} age_min={age_min:.1f}"
            )

        repaired = 0
        reruns: List[Dict[str, object]] = []
        if args.apply and rows:
            repaired = _repair_rows(conn=conn, rows=rows, now_ms=now_ms)
            if not args.skip_rerun:
                for x in _dedupe_for_rerun(rows):
                    reruns.append(_rerun_once(x=x, logs_dir=logs_dir))

        manifest = {
            "schema": "leanatlas.automation_recovery_manifest",
            "schema_version": "0.1.0",
            "mode": "dry-run" if args.dry_run else "apply",
            "db_path": str(db_path),
            "now_ms": now_ms,
            "max_in_progress_minutes": int(args.max_in_progress_minutes),
            "candidate_count": len(rows),
            "repaired_count": int(repaired),
            "candidates": [
                {
                    "thread_id": x.thread_id,
                    "automation_id": x.automation_id,
                    "source_cwd": x.source_cwd,
                    "created_at": x.created_at,
                    "updated_at": x.updated_at,
                }
                for x in rows
            ],
            "reruns": reruns,
        }
        (run_dir / "recovery_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        latest = ROOT / "artifacts" / "automation" / "recovery" / "latest_recovery_manifest.json"
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"[automation.recovery] wrote {run_dir / 'recovery_manifest.json'}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
