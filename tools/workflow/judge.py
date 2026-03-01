#!/usr/bin/env python3
"""Deterministic Judge for continue/stop decisions.

The Judge never reads LLM outputs. It uses only:
- patch scope verdict
- deterministic progress signals
- deterministic budgets/counters
- policy tables from the workflow contract

This file is a **reference implementation** used by tests and as an executable spec.
"""

from __future__ import annotations

from typing import Dict, Any, Optional

from tools.workflow.budgets import BudgetLimits, BudgetCounters, check_exhausted

DEFAULT_K_BY_FAMILY = {
    "ASSUMPTION": 0,
    "DEFINITION": 0,
    "STATEMENT": 0,
    "TOOLING": 1,
    "IMPORT": 2,
    "NAME": 2,
    "TYPE": 4,
    "TACTIC": 6,
    "BUDGET": 2,
    "UNKNOWN": 2,
}


def k_for_family(family: str, overrides: Optional[Dict[str, int]] = None) -> int:
    """Return K (max consecutive stagnant attempts) for a category family."""
    if overrides and family in overrides:
        return int(overrides[family])
    return int(DEFAULT_K_BY_FAMILY.get(family, 2))


def _normalize_budgets(budgets: Dict[str, Any]) -> tuple[BudgetLimits, BudgetCounters]:
    """Accept either nested or flat budgets dicts.

    Preferred shape (Phase 2.2+):
      budgets = { "limits": {...}, "counters": {...} }

    Back-compat shape:
      budgets = { "max_attempts": 10, "attempts_used": 3, ... }
    """
    if "limits" in budgets or "counters" in budgets:
        limits = BudgetLimits.from_dict(dict(budgets.get("limits", {})))
        counters = BudgetCounters.from_dict(dict(budgets.get("counters", {})))
        return limits, counters

    # flat
    limits = BudgetLimits.from_dict(budgets)
    counters = BudgetCounters.from_dict(budgets)
    return limits, counters


def judge_decide(
    *,
    mode: str,
    patch_scope: Dict[str, Any],
    suspected_family: str,
    stagnant_count: int,
    signals: Dict[str, Any],
    budgets: Dict[str, Any],
    k_overrides: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Decide whether to continue or stop.

    The Judge is deterministic: it MUST produce identical output for identical inputs.
    """
    if mode not in ("OPERATOR", "MAINTAINER"):
        raise ValueError("bad mode")

    K = k_for_family(suspected_family, k_overrides)

    # Patch scope violations are always a hard stop in OPERATOR mode.
    if mode == "OPERATOR" and patch_scope.get("verdict") == "DISALLOW":
        return {
            "decision": "TRIAGED",
            "triage_level": "ESCALATE",
            "reason_code": "SCOPE_VIOLATION",
            "detail": str(patch_scope.get("primary_reason_code", "UNKNOWN")),
            "stagnant_count": int(stagnant_count),
            "K": int(K),
            "budget_exceeded": [],
        }


    # Tooling failures are a hard stop: we cannot trust further attempts until tools are fixed.
    if bool(signals.get("tooling_failed")):
        return {
            "decision": "TRIAGED",
            "triage_level": "ESCALATE",
            "reason_code": "TOOLING_FAILURE",
            "detail": "tooling_failed",
            "stagnant_count": int(stagnant_count),
            "K": int(K),
            "budget_exceeded": [],
        }

    # If the primary error is outside the current problem in OPERATOR mode,
    # we cannot fix it within the allowed patch scope. Escalate immediately.
    if mode == "OPERATOR" and bool(signals.get("error_outside_problem")):
        return {
            "decision": "TRIAGED",
            "triage_level": "ESCALATE",
            "reason_code": "ERROR_OUTSIDE_SCOPE",
            "detail": "error_outside_problem",
            "stagnant_count": int(stagnant_count),
            "K": int(K),
            "budget_exceeded": [],
        }


    # Immediate escalation families (K=0)
    if K == 0:
        return {
            "decision": "TRIAGED",
            "triage_level": "ESCALATE",
            "reason_code": "FAMILY_REQUIRES_ESCALATION",
            "detail": str(suspected_family),
            "stagnant_count": int(stagnant_count),
            "K": 0,
            "budget_exceeded": [],
        }

    limits, counters = _normalize_budgets(budgets)
    exceeded = check_exhausted(limits, counters)
    if exceeded:
        return {
            "decision": "TRIAGED",
            "triage_level": "FIXABLE",
            "reason_code": "BUDGET_EXHAUSTED",
            "detail": ",".join(exceeded),
            "stagnant_count": int(stagnant_count),
            "K": int(K),
            "budget_exceeded": exceeded,
        }

    # Stagnation update
    if bool(signals.get("stagnant")):
        new_count = int(stagnant_count) + 1
    else:
        new_count = 0

    if new_count >= K:
        return {
            "decision": "TRIAGED",
            "triage_level": "FIXABLE",
            "reason_code": "STAGNATION_EXCEEDED",
            "detail": f"stagnant_count={new_count} K={K}",
            "stagnant_count": int(new_count),
            "K": int(K),
            "budget_exceeded": [],
        }

    return {
        "decision": "CONTINUE",
        "triage_level": None,
        "reason_code": "OK",
        "detail": "",
        "stagnant_count": int(new_count),
        "K": int(K),
        "budget_exceeded": [],
    }
