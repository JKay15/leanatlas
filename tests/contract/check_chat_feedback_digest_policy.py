#!/usr/bin/env python3
"""Contract: chat feedback digest must include triage/severity/SLA governance fields."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MINER = ROOT / "tools" / "feedback" / "mine_chat_feedback.py"

EXPECTED_SLA = {
    "S0": 4,
    "S1": 24,
    "S2": 72,
    "S3": 168,
}
TRIAGE_CLASSES = {"contract_drift", "how_to_gap", "bug_missing_test", "one_off_preference"}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    _assert(MINER.exists(), "missing tools/feedback/mine_chat_feedback.py")
    with tempfile.TemporaryDirectory(prefix="leanatlas_feedback_digest_") as td:
        base = Path(td)
        inbox = base / "inbox"
        out_path = base / "out.json"
        inbox.mkdir(parents=True, exist_ok=True)

        (inbox / "a.md").write_text(
            "\n".join(
                [
                    "feedback: contract schema is wrong and blocking",
                    "issue: docs unclear for setup",
                    "request: I prefer shorter output wording",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        p = subprocess.run(
            [sys.executable, str(MINER), "--in-root", str(inbox), "--out", str(out_path)],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        _assert(p.returncode == 0, f"miner failed: {p.stdout}")
        obj = json.loads(out_path.read_text(encoding="utf-8"))
        items = list(obj.get("items") or [])
        _assert(len(items) == 3, f"expected 3 items, got {len(items)}")

        for item in items:
            _assert(isinstance(item.get("feedback_id"), str) and item.get("feedback_id"), "missing feedback_id")
            triage = str(item.get("triage_class") or "")
            _assert(triage in TRIAGE_CLASSES, f"invalid triage_class: {triage}")
            sev = str(item.get("severity") or "")
            _assert(sev in EXPECTED_SLA, f"invalid severity: {sev}")
            sla = int(item.get("sla_hours") or 0)
            _assert(sla == EXPECTED_SLA[sev], f"sla_hours mismatch for {sev}: got {sla}, expected {EXPECTED_SLA[sev]}")
            actions = list(item.get("required_actions") or [])
            criteria = list(item.get("closure_criteria") or [])
            _assert(actions, "required_actions must be non-empty")
            _assert(criteria, "closure_criteria must be non-empty")
            links = item.get("links") or {}
            _assert(isinstance(links, dict), "links must be object")
            for key in ("prs", "tests", "docs", "release_notes"):
                _assert(isinstance(links.get(key), list), f"links.{key} must be list")

    print("[chat-feedback-digest-policy][PASS]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[chat-feedback-digest-policy][FAIL] {ex}")
        raise SystemExit(1)
