#!/usr/bin/env python3
"""Contract: feedback traceability matrix must report closed-item link violations."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRACE = ROOT / "tools" / "feedback" / "build_traceability_matrix.py"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _run(ledger: Path, out_csv: Path, out_json: Path, strict: bool) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(TRACE),
        "--ledger",
        str(ledger),
        "--out-csv",
        str(out_csv),
        "--out-json",
        str(out_json),
    ]
    if strict:
        cmd.append("--strict-closed")
    return subprocess.run(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)


def _line(fid: str, status: str, with_links: bool) -> dict:
    links = {"prs": [], "tests": [], "docs": [], "release_notes": []}
    if with_links:
        links = {
            "prs": [f"pr/{fid}"],
            "tests": [f"tests/{fid}"],
            "docs": [f"docs/{fid}"],
            "release_notes": [],
        }
    return {
        "schema": "leanatlas.feedback_ledger_line",
        "schema_version": "0.1.0",
        "feedback_id": fid,
        "captured_at_utc": "2026-02-28T00:00:00Z",
        "first_seen_at_utc": "2026-02-28T00:00:00Z",
        "status": status,
        "session_id": "s1",
        "agent_build_id": "b1",
        "triage_class": "how_to_gap",
        "severity": "S2",
        "sla_hours": 72,
        "source_file": "artifacts/feedback/inbox/a.md",
        "target_bucket": "docs/agents",
        "observed_behavior": "x",
        "required_actions": ["update_how_to_docs"],
        "closure_criteria": ["how_to_doc_merged"],
        "links": links,
    }


def main() -> int:
    _assert(TRACE.exists(), "missing tools/feedback/build_traceability_matrix.py")
    with tempfile.TemporaryDirectory(prefix="leanatlas_feedback_trace_") as td:
        base = Path(td)
        ledger = base / "ledger.jsonl"
        out_csv = base / "matrix.csv"
        out_json = base / "summary.json"

        # One closed item without links should fail strict mode.
        lines = [_line("fb_open", "open", False), _line("fb_closed_bad", "closed", False)]
        ledger.write_text("\n".join(json.dumps(x, sort_keys=True) for x in lines) + "\n", encoding="utf-8")
        p1 = _run(ledger, out_csv, out_json, strict=True)
        _assert(p1.returncode != 0, "strict mode must fail when closed items have no links")

        # Closed item with links should pass strict mode.
        lines = [_line("fb_open", "open", False), _line("fb_closed_ok", "closed", True)]
        ledger.write_text("\n".join(json.dumps(x, sort_keys=True) for x in lines) + "\n", encoding="utf-8")
        p2 = _run(ledger, out_csv, out_json, strict=True)
        _assert(p2.returncode == 0, f"strict mode should pass: {p2.stdout}")
        _assert(out_csv.exists(), "missing output csv")
        _assert(out_json.exists(), "missing output summary json")
        summary = json.loads(out_json.read_text(encoding="utf-8"))
        _assert(int(summary.get("item_count", -1)) == 2, f"summary item_count mismatch: {summary}")
        _assert(summary.get("closed_without_links") == [], f"unexpected closed_without_links: {summary}")

    print("[feedback-traceability-policy][PASS]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[feedback-traceability-policy][FAIL] {ex}")
        raise SystemExit(1)
