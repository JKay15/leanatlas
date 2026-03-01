#!/usr/bin/env python3
"""Contract: feedback ledger append script must be append-only and deduplicate by feedback_id."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APPEND = ROOT / "tools" / "feedback" / "append_feedback_ledger.py"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _run(digest: Path, ledger: Path, summary: Path) -> dict:
    p = subprocess.run(
        [
            sys.executable,
            str(APPEND),
            "--digest",
            str(digest),
            "--ledger",
            str(ledger),
            "--summary-out",
            str(summary),
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    _assert(p.returncode == 0, f"append failed: {p.stdout}")
    return json.loads(summary.read_text(encoding="utf-8"))


def _digest_with(ids: list[str]) -> dict:
    items = []
    for fid in ids:
        items.append(
            {
                "id": fid,
                "feedback_id": fid,
                "session_id": "s1",
                "agent_build_id": "b1",
                "source_file": "artifacts/feedback/inbox/x.md",
                "text": f"text for {fid}",
                "category": "docs",
                "triage_class": "how_to_gap",
                "severity": "S2",
                "sla_hours": 72,
                "frequency_hint": "unknown",
                "target_bucket": "docs/agents",
                "status": "open",
                "required_actions": ["update_how_to_docs"],
                "closure_criteria": ["how_to_doc_merged"],
                "links": {"prs": [], "tests": [], "docs": [], "release_notes": []},
            }
        )
    return {
        "schema": "leanatlas.chat_feedback_digest",
        "schema_version": "0.1.0",
        "generated_at_utc": "2026-02-28T00:00:00Z",
        "source_root": "artifacts/feedback/inbox",
        "item_count": len(items),
        "items": items,
        "summary": {"by_category": {"docs": len(items)}, "by_severity": {"S2": len(items)}, "by_target_bucket": {"docs/agents": len(items)}},
    }


def main() -> int:
    _assert(APPEND.exists(), "missing tools/feedback/append_feedback_ledger.py")
    with tempfile.TemporaryDirectory(prefix="leanatlas_feedback_ledger_") as td:
        base = Path(td)
        digest = base / "digest.json"
        ledger = base / "ledger.jsonl"
        summary = base / "summary.json"

        digest.write_text(json.dumps(_digest_with(["fb_a", "fb_b"]), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        s1 = _run(digest, ledger, summary)
        _assert(int(s1.get("new_items_count", -1)) == 2, f"first run should append 2, got {s1}")
        lines1 = ledger.read_text(encoding="utf-8").splitlines()
        _assert(len(lines1) == 2, f"ledger should contain 2 lines, got {len(lines1)}")

        s2 = _run(digest, ledger, summary)
        _assert(int(s2.get("new_items_count", -1)) == 0, f"second run should append 0, got {s2}")
        lines2 = ledger.read_text(encoding="utf-8").splitlines()
        _assert(lines2 == lines1, "ledger content changed on duplicate append run")

        digest.write_text(json.dumps(_digest_with(["fb_a", "fb_b", "fb_c"]), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        s3 = _run(digest, ledger, summary)
        _assert(int(s3.get("new_items_count", -1)) == 1, f"third run should append 1, got {s3}")
        lines3 = ledger.read_text(encoding="utf-8").splitlines()
        _assert(len(lines3) == 3, f"ledger should contain 3 lines, got {len(lines3)}")
        _assert(lines3[:2] == lines1, "append-only violated: old lines were changed")

    print("[feedback-ledger-append-only][PASS]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[feedback-ledger-append-only][FAIL] {ex}")
        raise SystemExit(1)
