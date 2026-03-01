#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.workflow.patch_scope import evaluate_patch_scope

def assert_eq(a, b, msg):
  if a != b:
    raise AssertionError(f"{msg}: {a} != {b}")

def main():
  slug = "demo_problem"

  # 1) allow Proof.lean
  r = evaluate_patch_scope(slug, "OPERATOR", ["Problems/demo_problem/Proof.lean"])
  assert_eq(r["verdict"], "ALLOW", "Proof.lean should be allowed")
  assert_eq(r["primary_reason_code"], "OK", "primary reason")
  assert_eq(len(r["violations"]), 0, "no violations")

  # 2) allow Cache submodule
  r = evaluate_patch_scope(slug, "OPERATOR", ["Problems/demo_problem/Cache/Aux.lean"])
  assert_eq(r["verdict"], "ALLOW", "Cache/**.lean should be allowed")

  # 3) disallow Spec.lean
  r = evaluate_patch_scope(slug, "OPERATOR", ["Problems/demo_problem/Spec.lean"])
  assert_eq(r["verdict"], "DISALLOW", "Spec.lean must be disallowed")
  assert_eq(r["primary_reason_code"], "SPEC_TOUCHED", "primary reason SPEC_TOUCHED")

  # 4) disallow system edits
  r = evaluate_patch_scope(slug, "OPERATOR", ["LeanAtlas/Toolbox/Imports/Foo.lean"])
  assert_eq(r["verdict"], "DISALLOW", "LeanAtlas/** must be disallowed")
  assert_eq(r["primary_reason_code"], "SYSTEM_TOUCHED", "primary reason SYSTEM_TOUCHED")

  # 5) disallow other problem edits
  r = evaluate_patch_scope(slug, "OPERATOR", ["Problems/other_problem/Proof.lean"])
  assert_eq(r["verdict"], "DISALLOW", "Other problem must be disallowed")
  assert_eq(r["primary_reason_code"], "OUTSIDE_PROBLEM_TOUCHED", "primary reason OUTSIDE_PROBLEM_TOUCHED")

  # 6) ignore reports
  r = evaluate_patch_scope(slug, "OPERATOR", ["Problems/demo_problem/Reports/run_1/RunReport.json"])
  assert_eq(r["verdict"], "ALLOW", "Reports outputs should be ignored")
  assert_eq(len(r["ignored_paths"]), 1, "ignored paths should include report")

  # 7) disallow metadata (non-lean)
  r = evaluate_patch_scope(slug, "OPERATOR", ["Problems/demo_problem/README.md"])
  assert_eq(r["verdict"], "DISALLOW", "metadata edits disallowed")
  assert_eq(r["primary_reason_code"], "PROBLEM_METADATA_TOUCHED", "primary reason PROBLEM_METADATA_TOUCHED")

  print("[patch-scope][OK] all cases passed")
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
