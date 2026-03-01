#!/usr/bin/env python3
"""Contract: chat feedback miner must only ingest tagged/structured feedback.

Policy:
- Full chat transcripts or arbitrary prompt text must not be ingested by default.
- Text input requires explicit tags (feedback:/issue:/request:/... or [feedback] style).
- Structured JSON must not ingest generic `prompt` fields.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MINER = ROOT / "tools" / "feedback" / "mine_chat_feedback.py"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    _assert(MINER.exists(), "missing tools/feedback/mine_chat_feedback.py")

    with tempfile.TemporaryDirectory(prefix="leanatlas_feedback_filter_") as td:
        base = Path(td)
        inbox = base / "inbox"
        out_path = base / "out.json"
        inbox.mkdir(parents=True, exist_ok=True)

        (inbox / "tagged.md").write_text(
            "\n".join(
                [
                    "feedback: onboarding misses automation reminder",
                    "- issue: promotion gate explanation is unclear",
                    "- random bullet should be ignored",
                    "plain sentence should be ignored",
                    "[request] add explicit cache-policy section",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        (inbox / "transcript.md").write_text(
            "Hi Codex, please solve this theorem and optimize imports.\n",
            encoding="utf-8",
        )

        (inbox / "structured.json").write_text(
            json.dumps(
                {
                    "feedback": "need better setup docs",
                    "prompt": "this is full user prompt text and must be ignored",
                    "items": [
                        {"issue": "domain mcp install step unclear"},
                        {"note": "should be ignored because note is not a feedback field"},
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        proc = subprocess.run(
            [
                sys.executable,
                str(MINER),
                "--in-root",
                str(inbox),
                "--out",
                str(out_path),
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        _assert(proc.returncode == 0, f"miner failed: {proc.stdout}")
        _assert(out_path.exists(), "missing output json")

        report = json.loads(out_path.read_text(encoding="utf-8"))
        items = list(report.get("items") or [])
        texts = [str(x.get("text", "")) for x in items if isinstance(x, dict)]

        # Expected accepted items:
        # 1) feedback:
        # 2) issue:
        # 3) [request]
        # 4) structured feedback
        # 5) structured items.issue
        _assert(len(items) == 5, f"expected 5 filtered items, got {len(items)}")

        blob = "\n".join(texts).lower()
        _assert("random bullet should be ignored" not in blob, "untagged bullet was incorrectly ingested")
        _assert("plain sentence should be ignored" not in blob, "untagged line was incorrectly ingested")
        _assert("this is full user prompt text" not in blob, "generic prompt field was incorrectly ingested")
        _assert("please solve this theorem" not in blob, "full transcript text was incorrectly ingested")

    print("[chat-feedback-filter][PASS]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[chat-feedback-filter][FAIL] {ex}")
        raise SystemExit(1)
