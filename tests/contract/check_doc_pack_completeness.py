#!/usr/bin/env python3
"""Doc-pack completeness checks (core).

Goal: ensure we do not forget to wire key cross-cutting parts into the Codex doc system.

This test intentionally checks for the presence of a small set of *critical* documents/files.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED = [
  ROOT / "docs" / "contracts" / "PROBLEM_STATE_CONTRACT.md",

  # Automations
  ROOT / "docs" / "agents" / "AUTOMATIONS.md",
  ROOT / "docs" / "agents" / "MEMORY_COVERAGE.md",
  ROOT / "docs" / "contracts" / "AUTOMATION_CONTRACT.md",
  ROOT / "automations" / "registry.json",

  # MCP
  ROOT / "docs" / "contracts" / "MCP_ADAPTER_CONTRACT.md",
  ROOT / "docs" / "contracts" / "MCP_LEAN_LSP_MCP_ADAPTER.md",
  ROOT / "docs" / "contracts" / "MCP_MSC2020_CONTRACT.md",
  ROOT / "tools" / "mcp" / "healthcheck.py",

  # Dependency governance (supply chain)
  ROOT / "docs" / "contracts" / "THIRD_PARTY_DEPENDENCY_CONTRACT.md",
  ROOT / "docs" / "contracts" / "AI_NATIVE_ENGINEERING_CONTRACT.md",
  ROOT / "docs" / "contracts" / "HARD_REQUIREMENTS.md",
  ROOT / "docs" / "contracts" / "FEEDBACK_GOVERNANCE_CONTRACT.md",
  ROOT / "docs" / "setup" / "SUBMODULES.md",
  ROOT / "tools" / "deps" / "pins.json",
  ROOT / "docs" / "setup" / "DEPENDENCIES.md",
  ROOT / "docs" / "setup" / "external" / "lean-lsp-mcp.md",
  ROOT / "docs" / "setup" / "external" / "ripgrep.md",
  ROOT / "docs" / "navigation" / "FILE_INDEX.md",
  ROOT / "tools" / "docs" / "generate_file_index.py",
  ROOT / "tools" / "onboarding" / "finalize_onboarding.py",
  ROOT / "docs" / "agents" / "archive" / "AGENTS_ONBOARDING_VERBOSE.md",
  ROOT / "docs" / "agents" / "archive" / "AGENTS_ONBOARDING_COMPACT.md",
  ROOT / "pyproject.toml",
  ROOT / "uv.lock",

  # Phase plans
  ROOT / "docs" / "agents" / "execplans" / "phase3_dedup_gate_v0.md",
  ROOT / "docs" / "agents" / "execplans" / "phase3_promotion_gate_v0.md",
  ROOT / "docs" / "agents" / "execplans" / "phase3_gc_gate_v0.md",

  # Test registry + matrix
  ROOT / "docs" / "testing" / "README.md",
  ROOT / "docs" / "testing" / "TEST_MATRIX.md",
  ROOT / "tools" / "tests" / "generate_test_matrix.py",

  # Version roadmap (V0/V1/V2)
  ROOT / "docs" / "agents" / "VERSION_ROADMAP.md",

  # Growth contracts (tools + skills)
  ROOT / "docs" / "contracts" / "PROMOTION_GATE_CONTRACT.md",
  ROOT / "docs" / "contracts" / "GC_GATE_CONTRACT.md",
  ROOT / "docs" / "contracts" / "GC_STATE_CONTRACT.md",
  ROOT / "docs" / "contracts" / "SKILLS_GROWTH_CONTRACT.md",

  # Phase6 Agent eval
  ROOT / "docs" / "contracts" / "AGENT_EVAL_CONTRACT.md",
  ROOT / "docs" / "schemas" / "AgentEvalTask.schema.json",
  ROOT / "docs" / "schemas" / "AgentEvalReport.schema.json",
  ROOT / "docs" / "schemas" / "FeedbackDigest.schema.json",
  ROOT / "docs" / "schemas" / "FeedbackLedgerLine.schema.json",
  ROOT / "docs" / "agents" / "kb" / "README.md",

  # Growth truth sources
  ROOT / "docs" / "schemas" / "GCState.schema.json",
  ROOT / "docs" / "schemas" / "ProblemState.schema.json",
  ROOT / "tools" / "index" / "gc_state.json",
  ROOT / "tools" / "feedback" / "mine_chat_feedback.py",
  ROOT / "tools" / "feedback" / "append_feedback_ledger.py",
  ROOT / "tools" / "feedback" / "build_traceability_matrix.py",
]


def main() -> int:
  missing = [str(p.relative_to(ROOT)) for p in REQUIRED if not p.exists()]
  if missing:
    print("[docpack] Missing required files:", file=sys.stderr)
    for m in missing:
      print(f"  - {m}", file=sys.stderr)
    return 2

  # Soft content checks: ensure operator workflow mentions MCP + automations + setup.
  op = (ROOT / "docs" / "agents" / "OPERATOR_WORKFLOW.md").read_text(encoding="utf-8")
  if "MCP" not in op or "Automations" not in op or "docs/setup" not in op or "lean-lsp-mcp" not in op:
    print("[docpack] OPERATOR_WORKFLOW missing setup/MCP/Automations guidance", file=sys.stderr)
    return 2

  print("[docpack] OK")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
