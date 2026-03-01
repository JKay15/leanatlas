---
title: Manifest Completeness + Shared Cache Strategy + Warehouse Topology Contract Reconstruction
owner: LeanAtlas Maintainer
status: active
created: 2026-02-28
---

## Purpose / Big Picture
This plan solves three blocking problems:
1) The executable test assets are not fully registered in the manifest, and the wrapper may conceal the true coverage.
2) The `.lake/packages` sharing strategy of the five runners is implemented in a decentralized manner, resulting in behavioral drift and audit difficulties.
3) The warehouse topology and MCP boundary have not formed an executable contract, especially the rule that "neither MCP will enter the third warehouse, only clone and install" has not been solidified.

Upon completion, LeanAtlas will have:
- Auditable mapping of manifest to executable assets (including wrapper expansion consistency gate);
- Single shared cache strategy module + five-entry unified call;
- Consistent access control of resume/fresh on cache strategy;
- Three-warehouse topology and module visualization capabilities are restored and verifiable at the document/script layer.

## Glossary
- Executable assets: YAML units (e2e case/scenario, agent_eval pack/scenario) that can be directly consumed by the runner and drive the real execution path.
- wrapper expansion: Manifest entries calculated via `expands_spec` should cover the collection of assets and listed explicitly in `expands`.
- Shared cache strategy: unified rules defined by `ensure_workspace_lake_packages` in `tools/workflow/shared_cache.py`.
- Cache policy drift: The runner does not call the shared policy, or the local implementation allows per-run independent completion of `.lake/packages`.

## Scope
Must change:
- `tests/contract/check_manifest_completeness.py`
- `tests/contract/check_shared_cache_policy.py`
- `tools/workflow/shared_cache.py`
- `tools/agent_eval/run_pack.py`
- `tools/agent_eval/run_scenario.py`
- `tests/e2e/run_cases.py`
- `tests/e2e/run_scenarios.py`
- `tests/stress/soak.py`
- `tests/manifest.json`
- `docs/contracts/REPO_TOPOLOGY_CONTRACT.md`
- `docs/tools/MODULE_VISUALIZATION.md`
- `tools/module_graph/edges_to_dot.py`

Optional changes (not implemented in this round, only recorded in risk items):
- Three-warehouse splitting automation script (git subtree/submodule orchestrator).
- Automatically install MCP's bootstrap script when cloning (constrained by documentation first).

Don’t do:
- Changed Lean proof logic to `Problems/**`.
-Introducing new external dependencies.

## Interfaces and Files
- `tools/workflow/shared_cache.py`
  - `ensure_workspace_lake_packages(repo_root, workspace_root, purpose, required_packages=...) -> CacheResult`
- `tests/contract/check_manifest_completeness.py`
- Verify unregistered assets/manifest points to non-existent assets/`expands_spec` is inconsistent with `expands`.
- `tests/contract/check_shared_cache_policy.py`
- Verify that the five entries uniformly import and call the shared cache; prohibit local independent seed implementation; verify the key fields of scenario resume/fresh semantics.
- `tests/manifest.json`
- Add `expands_spec` and `expands` to relevant entries.
- Register new contract tests.

## Milestones
1) Gate and shared module recovery
- Deliverables: Added `shared_cache.py` and two contract checks.
- Command: `python tests/contract/check_manifest_completeness.py`, `python tests/contract/check_shared_cache_policy.py`
- Acceptance: The two scripts are executable in the current warehouse, and PASS/FAIL and specific reasons are output.

2) Five runners unified strategy
- Deliverables: Five entries are unified to call `ensure_workspace_lake_packages`; local seed replication logic is removed.
- Command: `python tests/contract/check_shared_cache_policy.py`
- Acceptance: contract PASS, and `tools/agent_eval/run_*` no longer triggers subprocess-wrapper violations.

3) Manifest completeness implemented
- Deliverables: `tests/manifest.json` added to `expands_spec/expands` + new gate registration.
- Command: `python tests/contract/check_manifest_completeness.py`
- Acceptance: All executable assets are registered, and each expands is consistent with the spec.

4) Document and tool recovery
- Deliverables: `REPO_TOPOLOGY_CONTRACT.md`, `MODULE_VISUALIZATION.md`, `edges_to_dot.py`.
- Command: `python tools/module_graph/edges_to_dot.py --help`
- Acceptance: The script can be run, and the document clearly states that "two MCPs do not enter the three warehouses, only clone installation".

5) Regression verification
- Order:
  - `uv run --locked python tests/run.py --profile core`
- `uv run --locked python tests/e2e/run_cases.py --profile smoke` (pending local Lean environment)
  - `uv run --locked python tests/agent_eval/check_runner_plan_mode.py`
  - `uv run --locked python tests/agent_eval/check_scenario_runner_plan_mode.py`
- Acceptance: core passed; if smoke cannot be executed locally, it is clearly marked for local verification.

## Testing Plan (TDD)
- First add contract tests (manifest completeness, shared cache policy).
- Modify runner/manifest again to make the contract pass.
- Finally run `tests/run.py --profile core` to verify that there are no regressions.

## Decision Log
- 2026-02-28: Use `expands_spec + expands` for asset registration instead of adding executable manifest entries for each asset to avoid `tests/run.py` from running the same wrapper repeatedly.
- 2026-02-28: The shared cache strategy is unified into a single module API, which is only called by the runner and no longer embeds `.lake/packages` seed details.
- 2026-02-28: The warehouse topology contract is updated according to "main/skills/domain-mcp three warehouse + lean-lsp-mcp external installation", and `services/` is no longer embedded in the repo.

## Rollback Plan
- Rollback by filegroup:
- Gate rollback: `tests/contract/check_manifest_completeness.py`, `tests/contract/check_shared_cache_policy.py`
- Runner rollback: five entry files
- Document/tool ​​rollback: `docs/contracts/REPO_TOPOLOGY_CONTRACT.md`, `docs/tools/MODULE_VISUALIZATION.md`, `tools/module_graph/edges_to_dot.py`
- Verify successful rollback: `python tests/contract/check_test_registry.py` + `python tests/run.py --profile core`.

## Outcomes & Retrospective
Will be added after implementation.
