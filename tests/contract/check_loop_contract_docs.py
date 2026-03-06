#!/usr/bin/env python3
"""Contract check: LOOP Wave-A contract docs completeness and key semantics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DOCS = [
    ROOT / "docs" / "contracts" / "LOOP_RUNTIME_CONTRACT.md",
    ROOT / "docs" / "contracts" / "LOOP_GRAPH_CONTRACT.md",
    ROOT / "docs" / "contracts" / "LOOP_RESOURCE_ARBITER_CONTRACT.md",
    ROOT / "docs" / "contracts" / "LOOP_AUDIT_CONTRACT.md",
    ROOT / "docs" / "contracts" / "LOOP_MCP_CONTRACT.md",
    ROOT / "docs" / "contracts" / "LOOP_PYTHON_SDK_CONTRACT.md",
    ROOT / "docs" / "contracts" / "LOOP_WAVE_EXECUTION_CONTRACT.md",
]

REQUIRED_SNIPPETS = {
    "docs/contracts/LOOP_RUNTIME_CONTRACT.md": [
        "AI_REVIEW -> RUNNING",
        "`HUMAN_REVIEW` MUST NOT appear in execution track as a blocking state",
        "Assurance levels",
        "FAST",
        "LIGHT",
        "STRICT",
        "ai_review_prompt_ref",
        "ai_review_response_ref",
        "ai_review_summary_ref",
        "agent_provider_id",
        "instruction_scope_refs",
        "max_dynamic_recovery_rounds_per_exception = 2",
        "max_dynamic_recovery_total_minutes = 45",
        "PROMOTION_BLOCKED_BY_AUDIT",
    ],
    "docs/contracts/LOOP_GRAPH_CONTRACT.md": [
        "STATIC_USER_MODE",
        "SYSTEM_EXCEPTION_MODE",
        "Dynamic graph entry is allowed only when",
        "GraphSummary.jsonl",
        "graph payload MUST remain schema-valid",
        "host metadata sidecar",
        "allow_terminal_predecessors",
        "all-pass",
        "before implementation begins",
        "MaintainerSession.json",
        "NodeJournal.jsonl",
        "MaintainerProgress.json",
        "must not mask upstream `FAILED` or `TRIAGED` outcomes as `PASSED`",
        "only valid on sink nodes with at least one incoming edge",
        "must not be attached to non-sink, `RACE`, or `QUORUM` nodes",
    ],
    "docs/contracts/LOOP_RESOURCE_ARBITER_CONTRACT.md": [
        "IMMUTABLE",
        "APPEND_ONLY",
        "MUTABLE_CONTROLLED",
        "lease + CAS protocol is mandatory",
    ],
    "docs/contracts/LOOP_AUDIT_CONTRACT.md": [
        "AUDIT_FLAGGED",
        "S1_CRITICAL",
        "S2_MAJOR",
        "S3_MINOR",
        "non-blocking for already-finished execution path",
    ],
    "docs/contracts/LOOP_MCP_CONTRACT.md": [
        "loop/definitions/*",
        "loop/runs/*",
        "loop/graphs/*",
        "loop/components/*",
        "loop/resources/*",
        "loop/audit/*",
        "loop/providers/*",
        "loop/review-history/*",
        "idempotency_key",
        "instruction_scope_refs",
    ],
    "docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md": [
        "loop(...)",
        "serial(...)",
        "parallel(...)",
        "run(...)",
        "resume(...)",
        "assurance_level",
        "FAST | LIGHT | STRICT",
        "agent_provider",
        "agent_profile",
        "review_history",
        "instruction_scope_refs",
        "resolved_invocation_signature",
        "error_code",
        "error_class",
        "retryable",
        "ExecPlan -> graph_spec -> test node -> implement node -> verify node -> AI review node -> LOOP closeout",
        "deterministic reviewer runner",
        "non-empty review scope file list",
        "visibility/context pack",
        "required_context_refs",
        "semantic-idle gate",
        "canonical review payload",
        "CanonicalReviewResult.schema.json",
        "raw provider stdout/stderr are audit evidence only",
        "mutate-and-restore scope rewrites",
        "materialize_maintainer_session",
        "MaintainerLoopSession",
        "MaintainerProgress.json",
        "post-hoc `GraphSummary` alone is insufficient",
        "observation_policy",
        "`execplan_ref` MUST stay disjoint from `scope_paths`",
        "freeze an incomplete chain",
        "required_context_refs` MUST stay disjoint from `scope_paths`",
        "canonicalize `instruction_scope_refs` to the active `AGENTS.md` chain",
        "run identity MUST include the frozen `graph_spec` contents",
        "`execplan_ref` as well as `scope_paths` and `required_context_refs`",
    ],
    "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md": [
        "Assurance level policy (FAST/LIGHT/STRICT)",
        "STRICT completion gate",
        "ai_review_prompt_ref",
        "ai_review_response_ref",
        "ai_review_summary_ref",
        "AI_REVIEW verdict enum: `PASS | REPAIRABLE | UNRESOLVED_BLOCKER | NON_RETRYABLE`",
        "REPAIRABLE and retry budget remains -> RUNNING",
        "REPAIRABLE and retry budget exhausted -> TRIAGED (`REVIEW_BUDGET_EXHAUSTED`)",
        "same finding_fingerprint repeats >= 2 -> TRIAGED (`REVIEW_STAGNATION`)",
        "`HUMAN_REVIEW` is asynchronous evidence and MUST NOT block the execution track",
        "agent_provider_id",
        "resolved_invocation",
        "instruction_scope_refs",
        "history_context_refs",
        "review_history_consistency",
        "contradiction_count",
        "DirtyTreeGate",
        "`dirty_tree` evidence must be present",
        "worktree must be clean before pass",
        "bounded execution (hard timeout + idle timeout)",
        "transport idle from semantic idle",
        "SEMANTIC_IDLE_TIMEOUT",
        "bounded extension (default cap: max 5 reconnect events)",
        "timed_out=true",
        "exit_code=124",
        "timeout_command_span",
        "REVIEW_UNRESOLVED_BLOCKER",
        "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED",
        "if `REVIEW_REPAIR_LOOP` occurs, terminal closure MUST come from a later AI review round",
        "reusing the same `prompt_ref` or `response_ref` across distinct AI review rounds is forbidden",
        "`codex exec review`",
        "ExecPlan -> graph_spec -> test node -> implement node -> verify node -> AI review node -> LOOP closeout",
        "manual closeout is exceptional only",
        "TRIAGED_TOOLING",
        "must still execute after `AI review` reaches `FAILED` or `TRIAGED`",
        "must not improve the terminal class decided by `AI review`",
        "review scope MUST be a non-empty file list",
        "CanonicalReviewResult",
        "raw provider capture and LOOP closeout MUST be separate stages",
        "response artifact MUST exist and be non-empty before `REVIEW_RUN`",
        "event.item.agent_message",
        "non-assistant `final_message` / `last_message` fallbacks are forbidden",
        "scope fingerprint mismatch makes the attempt stale",
        "scope observed stamp mismatch",
        "`artifacts/reviews/`",
        "visibility/context pack",
        "required_context_refs",
        "NO_TERMINAL_EVENT",
        "provider JSON event stream",
        "subjective early termination is forbidden",
        "minimum observation window for `codex_cli` is 600 seconds",
        "two-minute impatience aborts are invalid for `codex_cli`",
        "10-minute transport-idle default",
        "20-minute semantic-idle default",
    ],
}


def _fail(msg: str) -> int:
    print(f"[loop-contract-docs][FAIL] {msg}", file=sys.stderr)
    return 2


def main() -> int:
    missing = [str(p.relative_to(ROOT)) for p in REQUIRED_DOCS if not p.exists()]
    if missing:
        print("[loop-contract-docs][FAIL] missing required docs:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 2

    for rel, snippets in REQUIRED_SNIPPETS.items():
        p = ROOT / rel
        text = p.read_text(encoding="utf-8")
        for s in snippets:
            if s not in text:
                return _fail(f"{rel} missing snippet `{s}`")

    print("[loop-contract-docs] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
