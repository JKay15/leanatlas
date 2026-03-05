#!/usr/bin/env python3
"""Deterministic LOOP execution state model (Wave-B M1).

This module intentionally covers only execution-track semantics needed by M1.
Audit-track semantics stay in existing contract checks for now.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


class ExecutionState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AI_REVIEW = "AI_REVIEW"
    PASSED = "PASSED"
    FAILED = "FAILED"
    TRIAGED = "TRIAGED"


@dataclass(frozen=True)
class ExecutionTransition:
    from_state: ExecutionState
    to_state: ExecutionState


EXEC_ALLOWED: set[tuple[ExecutionState, ExecutionState]] = {
    (ExecutionState.PENDING, ExecutionState.RUNNING),
    (ExecutionState.RUNNING, ExecutionState.AI_REVIEW),
    (ExecutionState.AI_REVIEW, ExecutionState.RUNNING),
    (ExecutionState.AI_REVIEW, ExecutionState.PASSED),
    (ExecutionState.AI_REVIEW, ExecutionState.FAILED),
    (ExecutionState.AI_REVIEW, ExecutionState.TRIAGED),
}


def validate_execution_transition(from_state: ExecutionState, to_state: ExecutionState) -> bool:
    return (from_state, to_state) in EXEC_ALLOWED


def require_execution_transition(from_state: ExecutionState, to_state: ExecutionState) -> None:
    if not validate_execution_transition(from_state, to_state):
        raise ValueError(f"forbidden execution transition: {from_state.value} -> {to_state.value}")


def validate_execution_trace(trace: Sequence[ExecutionState]) -> bool:
    """Validate a state trace using pairwise transition legality.

    A trace is interpreted as contiguous states [s0, s1, s2, ...].
    """

    if len(trace) < 2:
        return False
    if trace[0] != ExecutionState.PENDING:
        return False

    for i in range(len(trace) - 1):
        if not validate_execution_transition(trace[i], trace[i + 1]):
            return False
    return True


def transitions_from_states(trace: Iterable[ExecutionState]) -> list[ExecutionTransition]:
    states = list(trace)
    out: list[ExecutionTransition] = []
    for i in range(len(states) - 1):
        out.append(ExecutionTransition(from_state=states[i], to_state=states[i + 1]))
    return out
