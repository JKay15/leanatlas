#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.workflow.judge import judge_decide

def assert_eq(a, b, msg):
  if a != b:
    raise AssertionError(f"{msg}: {a} != {b}")

def main():
  patch_ok = {"verdict":"ALLOW", "primary_reason_code":"OK", "violations":[], "ignored_paths":[]}
  patch_bad = {"verdict":"DISALLOW", "primary_reason_code":"SPEC_TOUCHED", "violations":[{"path":"Problems/x/Spec.lean","code":"SPEC_TOUCHED"}], "ignored_paths":[]}

  budgets_ok = {
    "limits": {"max_attempts": 10, "max_steps": 50, "max_external_queries": 5, "max_wall_time_ms": 0},
    "counters": {"attempts_used": 1, "steps_used": 1, "external_queries_used": 0, "wall_time_ms": 0},
  }

  # Case 1: patch scope violation => TRIAGED ESCALATE
  r = judge_decide(
    mode="OPERATOR",
    patch_scope=patch_bad,
    suspected_family="TYPE",
    stagnant_count=0,
    signals={"stagnant": False},
    budgets=budgets_ok,
  )
  assert_eq(r["decision"], "TRIAGED", "scope violation must triage")
  assert_eq(r["triage_level"], "ESCALATE", "scope violation escalates")
  assert_eq(r["reason_code"], "SCOPE_VIOLATION", "reason_code")

  # Case 2: ASSUMPTION family => immediate escalation
  r = judge_decide(
    mode="OPERATOR",
    patch_scope=patch_ok,
    suspected_family="ASSUMPTION",
    stagnant_count=0,
    signals={"stagnant": False},
    budgets=budgets_ok,
  )
  assert_eq(r["decision"], "TRIAGED", "assumption family must triage")
  assert_eq(r["triage_level"], "ESCALATE", "assumption escalates")
  assert_eq(r["reason_code"], "FAMILY_REQUIRES_ESCALATION", "reason_code")

  
  # Case 2.5: TOOLING failure signal => TRIAGED ESCALATE (tool failure has priority)
  r = judge_decide(
    mode="OPERATOR",
    patch_scope=patch_ok,
    suspected_family="TOOLING",
    stagnant_count=0,
    signals={"stagnant": False, "tooling_failed": True},
    budgets=budgets_ok,
  )
  assert_eq(r["decision"], "TRIAGED", "tooling_failed must triage")
  assert_eq(r["triage_level"], "ESCALATE", "tooling_failed escalates")
  assert_eq(r["reason_code"], "TOOLING_FAILURE", "tooling_failed reason")

  # Case 2.6: error outside problem scope => TRIAGED ESCALATE
  r = judge_decide(
    mode="OPERATOR",
    patch_scope=patch_ok,
    suspected_family="TYPE",
    stagnant_count=0,
    signals={"stagnant": False, "error_outside_problem": True},
    budgets=budgets_ok,
  )
  assert_eq(r["decision"], "TRIAGED", "error outside scope must triage")
  assert_eq(r["triage_level"], "ESCALATE", "error outside scope escalates")
  assert_eq(r["reason_code"], "ERROR_OUTSIDE_SCOPE", "error outside scope reason")


# Case 3: budget exhausted (max_steps) => TRIAGED FIXABLE
  budgets_exhaust = {
    "limits": {"max_attempts": 10, "max_steps": 2, "max_external_queries": 5, "max_wall_time_ms": 0},
    "counters": {"attempts_used": 1, "steps_used": 2, "external_queries_used": 0, "wall_time_ms": 0},
  }
  r = judge_decide(
    mode="OPERATOR",
    patch_scope=patch_ok,
    suspected_family="TYPE",
    stagnant_count=0,
    signals={"stagnant": False},
    budgets=budgets_exhaust,
  )
  assert_eq(r["decision"], "TRIAGED", "budget exhausted should triage")
  assert_eq(r["triage_level"], "FIXABLE", "budget exhausted is fixable by default")
  assert_eq(r["reason_code"], "BUDGET_EXHAUSTED", "reason_code")
  assert_eq("MAX_STEPS" in r.get("budget_exceeded", []), True, "budget_exceeded should include MAX_STEPS")

  # Case 4: stagnation exceeded => TRIAGED FIXABLE
  r = judge_decide(
    mode="OPERATOR",
    patch_scope=patch_ok,
    suspected_family="TYPE",
    stagnant_count=3,   # previous stagnant
    signals={"stagnant": True},
    budgets=budgets_ok,
  )
  assert_eq(r["decision"], "TRIAGED", "stagnation should triage")
  assert_eq(r["triage_level"], "FIXABLE", "stagnation is fixable by default")
  assert_eq(r["reason_code"], "STAGNATION_EXCEEDED", "reason_code")

  # Case 5: not stagnant => CONTINUE and count resets
  r = judge_decide(
    mode="OPERATOR",
    patch_scope=patch_ok,
    suspected_family="TYPE",
    stagnant_count=3,
    signals={"stagnant": False},
    budgets=budgets_ok,
  )
  assert_eq(r["decision"], "CONTINUE", "should continue")
  assert_eq(r["stagnant_count"], 0, "stagnant count resets")

  print("[judge][OK] all cases passed")
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
