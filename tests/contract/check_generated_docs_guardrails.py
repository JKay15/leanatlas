#!/usr/bin/env python3
"""Contract: generated-doc guardrails must exist for FILE_INDEX and TEST_MATRIX.

This check enforces three layers:
1) local pre-commit hooks auto-regenerate + verify generated docs
2) CI workflow verifies generated-doc contracts
3) root AGENTS hard rule explicitly mentions required regeneration triggers
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRE_COMMIT = ROOT / ".pre-commit-config.yaml"
WORKFLOW = ROOT / ".github" / "workflows" / "generated-doc-guardrails.yml"
AGENTS = ROOT / "AGENTS.md"


def _fail(msg: str) -> int:
    print(f"[generated-doc-guardrails][FAIL] {msg}", file=sys.stderr)
    return 2


def _require_snippets(text: str, snippets: list[str], label: str) -> list[str]:
    missing: list[str] = []
    for s in snippets:
        if s not in text:
            missing.append(f"{label}: missing snippet `{s}`")
    return missing


def main() -> int:
    for p in (PRE_COMMIT, WORKFLOW, AGENTS):
        if not p.exists():
            return _fail(f"missing required file: {p.relative_to(ROOT)}")

    pre = PRE_COMMIT.read_text(encoding="utf-8")
    wf = WORKFLOW.read_text(encoding="utf-8")
    agents = AGENTS.read_text(encoding="utf-8")

    pre_required = [
        "id: regenerate-file-index",
        "entry: python tools/docs/generate_file_index.py --write",
        "id: regenerate-test-matrix",
        "entry: python tools/tests/generate_test_matrix.py --write",
        "id: check-file-index-up-to-date",
        "entry: python tests/contract/check_file_index_reachability.py",
        "id: check-test-matrix-up-to-date",
        "entry: python tests/contract/check_test_matrix_up_to_date.py",
    ]
    wf_required = [
        "name: generated-doc-guardrails",
        "python tests/contract/check_file_index_reachability.py",
        "python tests/contract/check_test_matrix_up_to_date.py",
    ]
    agents_required = [
        "docs/navigation/FILE_INDEX.md",
        "docs/testing/TEST_MATRIX.md",
        "tests/manifest.json",
    ]

    missing = []
    missing.extend(_require_snippets(pre, pre_required, ".pre-commit-config.yaml"))
    missing.extend(_require_snippets(wf, wf_required, ".github/workflows/generated-doc-guardrails.yml"))
    missing.extend(_require_snippets(agents, agents_required, "AGENTS.md"))
    if missing:
        print("[generated-doc-guardrails] missing policy snippets:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 2

    print("[generated-doc-guardrails] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
