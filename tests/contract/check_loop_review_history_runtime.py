#!/usr/bin/env python3
"""Contract check: SDK runtime emits deterministic review-history summary evidence."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.sdk import loop, run


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loop_review_history_rt_") as td:
        repo = Path(td)
        spec = loop(
            loop_id="loop.review_history.runtime.v1",
            graph_mode="STATIC_USER_MODE",
            input_projection_hash="3" * 64,
            instruction_chain_hash="4" * 64,
            dependency_pin_set_id="pins.20260305",
            wave_id="loop.wave.review_history.v1",
        )
        review_history = [
            {
                "iteration_index": 1,
                "findings": [
                    {"finding_id": "finding.r1.a", "flags": ["CONTRADICTION"]},
                    {"finding_id": "finding.r1.b", "potential_nitpick": True},
                ],
            },
            {
                "iteration_index": 2,
                "contradiction_refs": ["finding.r1.a"],
                "nitpick_refs": ["finding.r2.c"],
            },
        ]

        out = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-review-history-001",
            agent_provider="codex_cli",
            instruction_scope_refs=[str(ROOT / "AGENTS.md")],
            review_history=review_history,
        )
        _assert(out["response"]["status"] == "OK", "run() should succeed")

        refs = out["response"].get("trace_refs", [])
        summary_refs = [r for r in refs if r.endswith("review_history_consistency.json")]
        _assert(len(summary_refs) == 1, "expected one review_history_consistency summary ref in trace_refs")
        sp = Path(summary_refs[0])
        _assert(sp.exists(), "review_history_consistency summary file should exist")
        data = json.loads(sp.read_text(encoding="utf-8"))

        _assert(data["consulted_iteration_count"] == 2, "consulted_iteration_count mismatch")
        _assert(data["contradiction_count"] == 1, "contradiction_count mismatch")
        _assert(data["potential_nitpick_count"] == 2, "potential_nitpick_count mismatch")
        _assert(data["contradiction_refs"] == ["finding.r1.a"], "contradiction_refs mismatch")
        _assert(
            data["nitpick_refs"] == ["finding.r1.b", "finding.r2.c"],
            "nitpick_refs should be sorted and deduplicated",
        )

        spec_empty = loop(
            loop_id="loop.review_history.runtime.empty.v1",
            graph_mode="STATIC_USER_MODE",
            input_projection_hash="5" * 64,
            instruction_chain_hash="6" * 64,
            dependency_pin_set_id="pins.20260305",
            wave_id="loop.wave.review_history.empty.v1",
        )
        out_empty = run(
            spec=spec_empty,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-review-history-002",
            agent_provider="codex_cli",
            instruction_scope_refs=[str(ROOT / "AGENTS.md")],
            review_history=[],
        )
        _assert(out_empty["response"]["status"] == "OK", "run() should succeed for empty review_history")
        _assert(
            isinstance(out_empty.get("review_history_ref"), str) and bool(out_empty["review_history_ref"]),
            "empty review_history should still persist review_history_ref",
        )

        refs_empty = out_empty["response"].get("trace_refs", [])
        summary_refs_empty = [r for r in refs_empty if r.endswith("review_history_consistency.json")]
        _assert(
            len(summary_refs_empty) == 1,
            "empty review_history should still persist review_history_consistency summary",
        )
        sp_empty = Path(summary_refs_empty[0])
        _assert(sp_empty.exists(), "empty-history summary file should exist")
        data_empty = json.loads(sp_empty.read_text(encoding="utf-8"))
        _assert(data_empty["consulted_iteration_count"] == 0, "empty-history consulted_iteration_count must be 0")
        _assert(data_empty["contradiction_count"] == 0, "empty-history contradiction_count must be 0")
        _assert(data_empty["potential_nitpick_count"] == 0, "empty-history potential_nitpick_count must be 0")
        _assert(data_empty["contradiction_refs"] == [], "empty-history contradiction_refs must be []")
        _assert(data_empty["nitpick_refs"] == [], "empty-history nitpick_refs must be []")

    print("[loop-review-history-runtime] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
