#!/usr/bin/env python3
"""Scenario sequence checks for LOOP execution/audit policy semantics."""

from __future__ import annotations

import sys

EXEC_ALLOWED = {
    ("PENDING", "RUNNING"),
    ("RUNNING", "AI_REVIEW"),
    ("AI_REVIEW", "RUNNING"),
    ("AI_REVIEW", "PASSED"),
    ("AI_REVIEW", "FAILED"),
    ("AI_REVIEW", "TRIAGED"),
}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _validate_exec_sequence(states: list[str]) -> bool:
    if len(states) < 2:
        return False
    return all((states[i], states[i + 1]) in EXEC_ALLOWED for i in range(len(states) - 1))


def _simulate_review_repair(max_retry: int, attempts: int) -> str:
    used = 0
    for _ in range(attempts):
        # always returns to running while budget remains
        if used < max_retry:
            used += 1
            continue
        return "TRIAGED"
    return "PASSED"


def _promotion_blocked(severity: str, resolved: bool) -> bool:
    return severity == "S1_CRITICAL" or (severity == "S2_MAJOR" and not resolved)


def _dynamic_exception_flow(recovery_success: bool, retries_exhausted: bool) -> str:
    # static flow raises exception -> system mode recovery -> return static or triage
    if recovery_success:
        return "RETURN_TO_STATIC_FLOW"
    if retries_exhausted:
        return "TRIAGED"
    return "SYSTEM_MODE_RETRY"


def main() -> int:
    # Sequence 1: happy path with one repair loop.
    s1 = ["PENDING", "RUNNING", "AI_REVIEW", "RUNNING", "AI_REVIEW", "PASSED"]
    _assert(_validate_exec_sequence(s1), "happy-path repair loop sequence should be valid")

    # Sequence 2: repeated repair then TRIAGED.
    s2 = ["PENDING", "RUNNING", "AI_REVIEW", "RUNNING", "AI_REVIEW", "RUNNING", "AI_REVIEW", "TRIAGED"]
    _assert(_validate_exec_sequence(s2), "repeated repair then triage sequence should be valid")
    _assert(_simulate_review_repair(max_retry=2, attempts=3) == "TRIAGED", "max_retry=2 should triage on 3rd repair")

    # Sequence 3: severity routing.
    _assert(_promotion_blocked("S1_CRITICAL", resolved=True), "S1 must block promotion")
    _assert(_promotion_blocked("S2_MAJOR", resolved=False), "unresolved S2 must block promotion")
    _assert(not _promotion_blocked("S2_MAJOR", resolved=True), "resolved S2 should not block promotion")
    _assert(not _promotion_blocked("S3_MINOR", resolved=False), "S3 should not block promotion by default")

    # Sequence 4: dynamic exception entry/exit back to static flow.
    _assert(
        _dynamic_exception_flow(recovery_success=True, retries_exhausted=False) == "RETURN_TO_STATIC_FLOW",
        "successful system-mode recovery should return to static flow",
    )
    _assert(
        _dynamic_exception_flow(recovery_success=False, retries_exhausted=False) == "SYSTEM_MODE_RETRY",
        "failed recovery with budget should retry in system mode",
    )
    _assert(
        _dynamic_exception_flow(recovery_success=False, retries_exhausted=True) == "TRIAGED",
        "failed recovery with exhausted budget should triage",
    )

    print("[loop-state-sequences] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
