#!/usr/bin/env python3
"""Budget limits + counters helpers (deterministic).

This module is intentionally small and dependency-free.
It provides:
- normalization of limits/counters from dicts
- exhaustion checks with stable reason codes
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, List


@dataclass(frozen=True)
class BudgetLimits:
    """Deterministic caps for a run.

    A value of 0 means "no limit" for that dimension.
    """
    max_attempts: int = 0
    max_steps: int = 0
    max_external_queries: int = 0
    max_wall_time_ms: int = 0

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "BudgetLimits":
        return BudgetLimits(
            max_attempts=int(d.get("max_attempts", 0)),
            max_steps=int(d.get("max_steps", 0)),
            max_external_queries=int(d.get("max_external_queries", 0)),
            max_wall_time_ms=int(d.get("max_wall_time_ms", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BudgetCounters:
    """Deterministic usage counters measured by tools/runner."""
    attempts_used: int = 0
    steps_used: int = 0
    external_queries_used: int = 0
    wall_time_ms: int = 0

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "BudgetCounters":
        return BudgetCounters(
            attempts_used=int(d.get("attempts_used", 0)),
            steps_used=int(d.get("steps_used", 0)),
            external_queries_used=int(d.get("external_queries_used", 0)),
            wall_time_ms=int(d.get("wall_time_ms", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def check_exhausted(limits: BudgetLimits, counters: BudgetCounters) -> List[str]:
    """Return a stable list of exceeded limit codes (empty means OK).

    Note:
    - We use ">=" as the exhaustion threshold so the last allowed attempt/step
      is the one with counter == max_* - 1 (0-indexed internally). In practice,
      callers can decide whether to increment counters before or after checks,
      but MUST be consistent and log counters per attempt.
    """
    exceeded: List[str] = []
    if limits.max_attempts and counters.attempts_used >= limits.max_attempts:
        exceeded.append("MAX_ATTEMPTS")
    if limits.max_steps and counters.steps_used >= limits.max_steps:
        exceeded.append("MAX_STEPS")
    if limits.max_external_queries and counters.external_queries_used >= limits.max_external_queries:
        exceeded.append("MAX_EXTERNAL_QUERIES")
    if limits.max_wall_time_ms and counters.wall_time_ms >= limits.max_wall_time_ms:
        exceeded.append("MAX_WALL_TIME_MS")
    return exceeded
