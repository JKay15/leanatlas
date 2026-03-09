#!/usr/bin/env python3
"""Contract check: non-trivial maintainer work must materialize and close through LOOP."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def main() -> int:
    plans = _read("docs/agents/PLANS.md")
    wave = _read("docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md")
    sdk = _read("docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md")
    graph = _read("docs/contracts/LOOP_GRAPH_CONTRACT.md")
    required_sequence = "ExecPlan -> graph_spec -> test node -> implement node -> verify node -> AI review node -> LOOP closeout"
    for name, text in {
        "docs/agents/PLANS.md": plans,
        "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md": wave,
        "docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md": sdk,
    }.items():
        _assert(required_sequence in text, f"{name} must include the maintainer LOOP sequence")

    _assert(
        "manual closeout is exceptional only" in wave,
        "LOOP_WAVE_EXECUTION_CONTRACT.md must forbid routine manual closeout",
    )
    _assert(
        "TRIAGED_TOOLING" in wave,
        "LOOP_WAVE_EXECUTION_CONTRACT.md must define tooling-triage fallback for AI review",
    )
    _assert(
        "graph payload MUST remain schema-valid" in graph,
        "LOOP_GRAPH_CONTRACT.md must distinguish schema-valid graph payload from host metadata sidecars",
    )
    _assert(
        "allow_terminal_predecessors" in graph,
        "LOOP_GRAPH_CONTRACT.md must document terminal-predecessor closeout execution",
    )
    _assert(
        "must not mask upstream `FAILED` or `TRIAGED` outcomes as `PASSED`" in graph,
        "LOOP_GRAPH_CONTRACT.md must preserve upstream terminal class in GraphSummary final_status",
    )
    _assert(
        "only valid on sink nodes with at least one incoming edge" in graph
        and "must not be attached to non-sink, `RACE`, or `QUORUM` nodes" in graph,
        "LOOP_GRAPH_CONTRACT.md must restrict allow_terminal_predecessors to sink all-pass nodes",
    )
    _assert(
        "non-trivial maintainer work MUST materialize a maintainer LOOP graph" in plans,
        "PLANS.md must require maintainer LOOP materialization",
    )
    _assert(
        "before implementation begins" in graph and "NodeJournal.jsonl" in graph,
        "LOOP_GRAPH_CONTRACT.md must require upfront maintainer session materialization and node journal visibility",
    )
    _assert(
        "materialize_maintainer_session" in sdk and "post-hoc `GraphSummary` alone is insufficient" in sdk,
        "LOOP_PYTHON_SDK_CONTRACT.md must require Python maintainer session materialization rather than post-hoc-only closeout",
    )
    _assert(
        "MaintainerLoopSession" in sdk and "MaintainerProgress.json" in sdk,
        "LOOP_PYTHON_SDK_CONTRACT.md must define the higher-level maintainer facade and visible progress artifact",
    )
    _assert(
        "`execplan_ref` MUST stay disjoint from `scope_paths`" in sdk
        and "freeze an incomplete chain" in sdk
        and "required_context_refs` MUST stay disjoint from `scope_paths`" in sdk,
        "LOOP_PYTHON_SDK_CONTRACT.md must forbid mutable ExecPlan overlap and validate immutable context boundaries",
    )
    _assert(
        "canonicalize `instruction_scope_refs` to the active `AGENTS.md` chain" in sdk
        and "run identity MUST include the frozen `graph_spec` contents" in sdk
        and "`execplan_ref`" in sdk
        and "active `AGENTS.md` chain" in sdk,
        "LOOP_PYTHON_SDK_CONTRACT.md must make instruction-chain canonicalization, execplan-induced scope, and graph-spec identity explicit",
    )
    _assert(
        "must still execute after `AI review` reaches `FAILED` or `TRIAGED`" in wave,
        "LOOP_WAVE_EXECUTION_CONTRACT.md must require closeout execution after terminal AI review states",
    )
    _assert(
        "must not improve the terminal class decided by `AI review`" in wave,
        "LOOP_WAVE_EXECUTION_CONTRACT.md must forbid closeout from overriding the AI review outcome",
    )
    _assert(
        "subjective early termination is forbidden" in wave
        and "minimum observation window for `codex_cli` is 600 seconds" in wave
        and "two-minute impatience aborts are invalid for `codex_cli`" in wave,
        "LOOP_WAVE_EXECUTION_CONTRACT.md must pin maintainer review waiting policy and forbid impatience-driven aborts",
    )
    _assert(
        "MaintainerProgress.json" in graph and "preferred maintainer path" in plans,
        "PLANS/GRAPH contracts must explain the visible maintainer progress path",
    )
    print("[maintainer-loop-requirement] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
