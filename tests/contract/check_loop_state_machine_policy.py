#!/usr/bin/env python3
"""Contract check: LOOP execution/audit state-machine policy invariants."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_CONTRACT = ROOT / "docs" / "contracts" / "LOOP_RUNTIME_CONTRACT.md"

EXEC_ALLOWED = {
    ("PENDING", "RUNNING"),
    ("RUNNING", "AI_REVIEW"),
    ("AI_REVIEW", "RUNNING"),
    ("AI_REVIEW", "PASSED"),
    ("AI_REVIEW", "FAILED"),
    ("AI_REVIEW", "TRIAGED"),
}

AUDIT_ALLOWED = {
    ("AUDIT_PENDING", "AUDIT_CONFIRMED"),
    ("AUDIT_PENDING", "AUDIT_FLAGGED_OPEN"),
    ("AUDIT_FLAGGED_OPEN", "AUDIT_MITIGATED"),
    ("AUDIT_MITIGATED", "AUDIT_VERIFIED"),
    ("AUDIT_VERIFIED", "AUDIT_CLOSED"),
    ("AUDIT_FLAGGED_OPEN", "AUDIT_ACCEPTED_RISK"),
}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _is_exec_allowed(src: str, dst: str) -> bool:
    return (src, dst) in EXEC_ALLOWED


def _is_audit_allowed(src: str, dst: str) -> bool:
    return (src, dst) in AUDIT_ALLOWED


def _review_outcome(
    *,
    repairable: bool,
    unresolved_blocker: bool,
    non_retryable_fault: bool,
    retry_used: int,
    retry_max: int,
) -> str:
    if non_retryable_fault:
        return "FAILED"
    if unresolved_blocker:
        return "TRIAGED"
    if repairable and retry_used < retry_max:
        return "RUNNING"
    if repairable and retry_used >= retry_max:
        return "TRIAGED"
    return "PASSED"


def _promotion_blocked(severity: str, resolved: bool) -> bool:
    return severity == "S1_CRITICAL" or (severity == "S2_MAJOR" and not resolved)


def main() -> int:
    # Required execution transitions.
    for edge in [
        ("PENDING", "RUNNING"),
        ("RUNNING", "AI_REVIEW"),
        ("AI_REVIEW", "RUNNING"),
        ("AI_REVIEW", "PASSED"),
        ("AI_REVIEW", "FAILED"),
        ("AI_REVIEW", "TRIAGED"),
    ]:
        _assert(_is_exec_allowed(*edge), f"missing required execution edge: {edge}")

    # Some forbidden execution transitions.
    for edge in [
        ("PENDING", "PASSED"),
        ("RUNNING", "PASSED"),
        ("PASSED", "RUNNING"),
        ("TRIAGED", "RUNNING"),
        ("FAILED", "RUNNING"),
    ]:
        _assert(not _is_exec_allowed(*edge), f"forbidden execution edge must be blocked: {edge}")

    # Required audit transitions.
    for edge in [
        ("AUDIT_PENDING", "AUDIT_CONFIRMED"),
        ("AUDIT_PENDING", "AUDIT_FLAGGED_OPEN"),
        ("AUDIT_FLAGGED_OPEN", "AUDIT_MITIGATED"),
        ("AUDIT_MITIGATED", "AUDIT_VERIFIED"),
        ("AUDIT_VERIFIED", "AUDIT_CLOSED"),
        ("AUDIT_FLAGGED_OPEN", "AUDIT_ACCEPTED_RISK"),
    ]:
        _assert(_is_audit_allowed(*edge), f"missing required audit edge: {edge}")

    # Review outcomes.
    _assert(
        _review_outcome(
            repairable=True,
            unresolved_blocker=False,
            non_retryable_fault=False,
            retry_used=0,
            retry_max=2,
        )
        == "RUNNING",
        "repairable + budget remaining should loop to RUNNING",
    )
    _assert(
        _review_outcome(
            repairable=True,
            unresolved_blocker=False,
            non_retryable_fault=False,
            retry_used=2,
            retry_max=2,
        )
        == "TRIAGED",
        "repairable + budget exhausted should TRIAGE",
    )
    _assert(
        _review_outcome(
            repairable=False,
            unresolved_blocker=False,
            non_retryable_fault=False,
            retry_used=0,
            retry_max=2,
        )
        == "PASSED",
        "non-repairable and no blocker should PASS",
    )
    _assert(
        _review_outcome(
            repairable=False,
            unresolved_blocker=True,
            non_retryable_fault=False,
            retry_used=0,
            retry_max=2,
        )
        == "TRIAGED",
        "unresolved blocker should TRIAGE",
    )
    _assert(
        _review_outcome(
            repairable=False,
            unresolved_blocker=False,
            non_retryable_fault=True,
            retry_used=0,
            retry_max=2,
        )
        == "FAILED",
        "non-retryable fault should FAIL",
    )

    # Promotion block policy.
    _assert(_promotion_blocked("S1_CRITICAL", resolved=True), "S1 must block promotion")
    _assert(_promotion_blocked("S2_MAJOR", resolved=False), "unresolved S2 must block promotion")
    _assert(not _promotion_blocked("S2_MAJOR", resolved=True), "resolved S2 should not block promotion")
    _assert(not _promotion_blocked("S3_MINOR", resolved=False), "S3 should not block by default")

    # Contract text must include default dynamic bounds.
    txt = RUNTIME_CONTRACT.read_text(encoding="utf-8")
    required_snippets = [
        "max_dynamic_recovery_rounds_per_exception = 2",
        "max_dynamic_recovery_total_minutes = 45",
        "max_temp_graph_nodes = 6",
        "max_retry_per_node = 2",
        "rounds: `[1, 3]`",
        "total minutes: `[20, 90]`",
        "temp graph nodes: `[3, 10]`",
    ]
    for s in required_snippets:
        _assert(s in txt, f"runtime contract missing dynamic bound snippet: {s}")

    print("[loop-state-policy] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
