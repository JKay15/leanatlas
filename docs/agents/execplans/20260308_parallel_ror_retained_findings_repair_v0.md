---
title: Repair retained whole-project audit truth-source drift without widening scope
owner: Codex (local workspace)
status: done
created: 2026-03-08
parent_execplan: docs/agents/execplans/20260308_parallel_ror_whole_project_audit_v0.md
---

## Purpose / Big Picture
The whole-project audit and parallel reviewer-of-reviewer pass retained two substantive repository findings: OPERATOR mode truth-source drift and DedupGate productization drift. This plan is a bounded repair wave for those retained findings only. It is not a new audit, not a productization expansion, and not a new Phase3 feature push. The goal is to add or tighten deterministic guardrails first, then align the minimum set of docs/skills/tooling surfaces so the repository tells one accurate story about OPERATOR routing and DedupGate V0 behavior.

## Glossary
- retained finding: a repository-level defect that survived the primary audit plus reviewer-of-reviewer reconciliation.
- truth source drift: multiple repo surfaces claiming different canonical behavior for the same concept.
- OPERATOR mode selector: the single rule that determines whether Codex should treat the repo as OPERATOR or MAINTAINER.
- DedupGate V0: the currently implemented LeanAtlas DedupGate path, which today is the Python source-backed instance scan in `tools/dedup/dedup.py`.
- bounded repair wave: a repair pass that fixes the retained findings without widening into adjacent roadmap or productization work.

## Scope
In scope:
- F1 repair:
  - `AGENTS.md`
  - `docs/agents/OPERATOR_WORKFLOW.md`
  - `.agents/skills/leanatlas-operator-proof-loop/SKILL.md`
  - `docs/agents/templates/AGENTS.override.minimal.md`
- F2 repair:
  - `.agents/skills/leanatlas-dedup/SKILL.md`
  - `tools/dedup/README.md`
  - `tools/dedup/dedup.py`
  - `tools/capabilities/phase3.yaml`
  - `docs/agents/STATUS.md`
- direct deterministic guardrails for the above truth sources:
  - one or more contract tests under `tests/contract/`
  - `tests/manifest.json`
  - generated indexes affected by new/changed tests

Out of scope:
- adding new LOOP capabilities
- changing review orchestration/runtime semantics
- introducing a new audit workflow or a dedicated audit skill
- implementing compiled-environment DedupGate scanning
- autopilot, worktree orchestration, or reviewer-of-reviewer productization
- widening F3 beyond an explicitly tiny tail fix; default action is to defer it

## Interfaces and Files
- `artifacts/verify/20260308_parallel_ror_whole_project_primary_audit.md`
  - authoritative retained-finding source for this repair wave.
- `artifacts/verify/20260308_parallel_ror_whole_project_reconciliation_summary.md`
  - authoritative narrowing of F2 wording and F1 matrix contradiction.
- `AGENTS.md`
  - root OPERATOR/MAINTAINER mode source-of-truth statement.
- `docs/agents/OPERATOR_WORKFLOW.md`
  - OPERATOR entrypoint and default-mode explanation.
- `.agents/skills/leanatlas-operator-proof-loop/SKILL.md`
  - OPERATOR procedure must use the same mode selector as root docs.
- `docs/agents/templates/AGENTS.override.minimal.md`
  - local override template must not describe a conflicting selector.
- `.agents/skills/leanatlas-dedup/SKILL.md`
  - Dedup workflow guidance must describe the implemented V0 honestly.
- `tools/dedup/README.md`
  - must distinguish current V0 from future compiled-environment goal.
- `tools/dedup/dedup.py`
  - module docstring must stay aligned with V0 description.
- `tools/capabilities/phase3.yaml`
  - capability manifest must reflect the same DedupGate V0 implementation story.
- `docs/agents/STATUS.md`
  - current-stage summary must not overstate DedupGate productization or current implementation.
- `tests/contract/*`
  - add/update deterministic checks for OPERATOR truth-source alignment and DedupGate V0 wording alignment.
- `tests/manifest.json`
  - register any new contract test.
- `docs/testing/TEST_MATRIX.md`
  - regenerated if manifest changes.
- `docs/navigation/FILE_INDEX.md`
  - regenerated if files are added or renamed.

## Milestones
1) Freeze retained-finding acceptance in tests
- Deliverables:
  - add or update contract tests that fail while OPERATOR mode selector text disagrees
  - add or update contract tests that fail while DedupGate V0 wording disagrees across skill/README/capability/status
- Commands:
  - `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
  - targeted new/updated contract checks for OPERATOR truth source and DedupGate truth source
- Acceptance:
  - tests clearly encode one OPERATOR selector and one honest DedupGate V0 description

2) Repair F1 OPERATOR truth-source drift
- Deliverables:
  - align `AGENTS.md`, `docs/agents/OPERATOR_WORKFLOW.md`, `.agents/skills/leanatlas-operator-proof-loop/SKILL.md`, and `docs/agents/templates/AGENTS.override.minimal.md`
- Commands:
  - targeted OPERATOR truth-source contract check
- Acceptance:
  - repo presents one unambiguous OPERATOR/MAINTAINER selector
  - no remaining doc/skill text claims `.cache/leanatlas/mode.json` is the authoritative selector

3) Repair F2 DedupGate productization drift
- Deliverables:
  - align Dedup skill/README/tool docstring/capability/status around the implemented source-backed V0
  - either remove the missing contract reference or add the contract only if the repo already requires it for truthful current-state documentation
- Commands:
  - targeted Dedup truth-source contract check
- Acceptance:
  - no repaired surface overclaims compiled-environment scanning as already implemented
  - no repaired surface claims a missing DedupGate contract as current truth unless such a contract is added in-scope

4) Verify bounded repair and close out under the current default reviewer policy
- Deliverables:
  - updated decision log / outcomes
  - fresh AI review artifact using baseline `FAST + low`, escalating only to `medium` if needed
- Commands:
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py`
  - `uv run --locked python tests/contract/check_skills_standard_headers.py`
  - relevant targeted contract tests for OPERATOR / Phase3 wording
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
- Acceptance:
  - targeted and full verification pass on the repaired worktree
  - repair closeout uses only the committed default reviewer policy (`FAST + low`, with `medium` as bounded escalation if baseline is insufficient)

## Testing plan (TDD)
- Add a deterministic contract test for OPERATOR truth-source alignment that inspects:
  - `AGENTS.md`
  - `docs/agents/OPERATOR_WORKFLOW.md`
  - `.agents/skills/leanatlas-operator-proof-loop/SKILL.md`
  - `docs/agents/templates/AGENTS.override.minimal.md`
- Add a deterministic contract test for DedupGate V0 truth-source alignment that inspects:
  - `.agents/skills/leanatlas-dedup/SKILL.md`
  - `tools/dedup/README.md`
  - `tools/dedup/dedup.py`
  - `tools/capabilities/phase3.yaml`
  - `docs/agents/STATUS.md`
- Register the test(s) in `tests/manifest.json` and regenerate generated indexes only if required.
- Do not add tests for optional F3 unless the repair remains a tiny, direct tail-item after F1/F2 are closed.

## Decision log
- 2026-03-08: keep this wave bounded to retained repository truth-source drift; do not widen into new productization work.
- 2026-03-08: prefer truthful current-state wording for DedupGate V0 over adding a speculative contract document just to satisfy stale references.
- 2026-03-08: F3 audit-only discoverability is default-deferred unless it can be closed with a tiny direct change after F1/F2.
- 2026-03-08: repair closeout must use the committed default reviewer policy only; `xhigh` is out of scope for this wave.

## Rollback plan
- Revert the bounded repair changes in:
  - `AGENTS.md`
  - `docs/agents/OPERATOR_WORKFLOW.md`
  - `.agents/skills/leanatlas-operator-proof-loop/SKILL.md`
  - `docs/agents/templates/AGENTS.override.minimal.md`
  - `.agents/skills/leanatlas-dedup/SKILL.md`
  - `tools/dedup/README.md`
  - `tools/dedup/dedup.py`
  - `tools/capabilities/phase3.yaml`
  - `docs/agents/STATUS.md`
  - any new/updated tests and generated index files
- Re-run the targeted contract checks plus `core`, `nightly`, `lake build`, and `git diff --check` to verify rollback restores the prior state cleanly.

## Outcomes & retrospective (fill when done)
- Completed:
  - Repaired F1 by aligning OPERATOR/MAINTAINER mode-selection wording around local root `AGENTS.override.md` in:
    - `AGENTS.md`
    - `docs/agents/OPERATOR_WORKFLOW.md`
    - `docs/agents/templates/AGENTS.override.minimal.md`
  - Left `.agents/skills/leanatlas-operator-proof-loop/SKILL.md` unchanged because it was already consistent with the repaired truth source.
  - Repaired F2 by aligning DedupGate V0 wording with the implemented source-backed scanner in:
    - `.agents/skills/leanatlas-dedup/SKILL.md`
    - `tools/dedup/README.md`
    - `tools/dedup/dedup.py`
    - `docs/agents/STATUS.md`
  - Repaired the remaining Dedup skill output-path drift so the documented outputs now match the actual `--out-root .cache/leanatlas/dedup/scan` CLI behavior.
  - Removed the stale Dedup skill reference to missing `docs/contracts/DEDUP_GATE_CONTRACT.md` instead of inventing a new contract that current code/tests do not require.
  - Added `tests/contract/check_repo_truth_source_alignment.py` and registered it in `tests/manifest.json`, then regenerated `docs/testing/TEST_MATRIX.md`.
- Verification:
  - `uv run --locked python tests/contract/check_repo_truth_source_alignment.py` PASS
  - `uv run --locked python tests/contract/check_loop_mainline_docs_integration.py` PASS
  - `uv run --locked python tests/contract/check_skills_standard_headers.py` PASS
  - `uv run --locked python tests/contract/check_setup_docs.py` PASS
  - `uv run --locked python tests/contract/check_manifest_completeness.py` PASS
  - `uv run --locked python tests/contract/check_test_matrix_up_to_date.py` PASS
  - `uv run --locked python tests/contract/check_file_index_reachability.py` PASS
  - `uv run --locked python tests/contract/check_loop_contract_docs.py` PASS
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py` PASS
  - `uv run --locked python tests/contract/check_capability_manifests.py` PASS
  - `uv run --locked python tests/contract/check_phase3_e2e_scenarios.py` PASS
  - `uv run --locked python tests/run.py --profile core` PASS
  - `uv run --locked python tests/run.py --profile nightly` PASS
  - `lake build` PASS
  - `git diff --check` PASS
  - Tooling note:
    - direct CLI closeout attempt produced an empty `-o` file on this machine:
      - `artifacts/reviews/20260308_parallel_ror_retained_findings_repair_review_round2_fast_summary.json`
    - rerunning the same low-tier review through the reviewer runner in `--json` mode recovered the terminal `agent_message` and exposed one remaining in-scope Dedup skill output-path drift, which this wave then repaired before the final closeout rerun.
- Deferred:
  - F3 audit-only discoverability gap remains deferred by design because closing F1/F2 did not require widening this repair wave.
- Remaining risks:
  - DedupGate still does not implement compiled-environment scanning or stronger canonicalization; that is intentional follow-on work and must not be described as current behavior.
  - This repair wave closes only the retained F1/F2 truth-source issues under the default reviewer policy. It is not a new whole-project audit and does not claim adjacent repo surfaces are globally drift-free.
