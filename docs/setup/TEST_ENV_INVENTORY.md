# Test Environment Inventory

> Deterministic inventory generated from `tests/`, `tools/`, and `scripts/` by `./.venv/bin/python tools/tests/generate_test_env_inventory.py --write`.
> Scope: environment requirements that appear in test and test-runner codepaths.

## External Commands Referenced by Tests

| Command | Role | Evidence (files) |
|---|---|---|
| `bash` | Runner shell for scripted scenario and agent commands. | `scripts/bootstrap.sh`, `scripts/doctor.sh`, `tests/agent_eval/check_scenario_tool_reuse_scoring.py`, `tools/agent_eval/dummy_agent.py`, `tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py` |
| `codex` | Real-agent command for Phase6 nightly eval execution. | `scripts/bootstrap.sh`, `scripts/doctor.sh`, `tests/automation/dry_run_single.py` |
| `git` | Repository metadata checks in tests/contracts. | `scripts/bootstrap.sh`, `scripts/clean.sh`, `tests/contract/check_problem_template_state.py`, `tools/docs/generate_file_index.py`, `tools/promote/promote.py` |
| `lake` | Lean build/lint/test execution and cache warmup. | `scripts/bootstrap.sh`, `tests/e2e/run_cases.py`, `tests/e2e/run_scenarios.py`, `tests/stress/soak.py`, `tools/agent_eval/run_pack.py`, `tools/gc/gc.py` |
| `pre-commit` | Repo-local git hooks and commit/branch policy enforcement. | `scripts/install_repo_git_hooks.sh` |
| `python` | Primary runtime for all registered tests and tooling. | `scripts/doctor.sh` |
| `rg` | Fast fallback search backend (recommended). | `scripts/bootstrap.sh`, `scripts/doctor.sh` |
| `uv` | Locked Python environment sync/check path. | `scripts/bootstrap.sh`, `tests/run.py`, `tests/setup/deps_smoke.py`, `tools/coordination/run_automation_local.py` |
| `uvx` | Pinned external tool execution (MCP checks). | `scripts/bootstrap.sh`, `scripts/doctor.sh`, `tests/setup/deps_smoke.py` |

## Third-Party Python Modules Referenced

| Module | Role | Evidence (files) |
|---|---|---|
| `drain3` | Telemetry/log pattern mining checks. | `tools/bench/mine_kb_suggestions.py` |
| `jsonschema` | Schema validation for contracts and fixtures. | `tests/agent_eval/validate_scenarios.py`, `tests/agent_eval/validate_tasks.py`, `tests/contract/check_attemptlog_jsonl.py`, `tests/contract/check_capability_manifests.py`, `tests/contract/check_problem_state_reconcile.py`, `tests/contract/check_test_registry.py`, `tests/e2e/run_scenarios.py`, `tests/e2e/validate_cases.py`, ... |
| `yaml` | YAML parsing for test manifests/scenarios/tasks. | `tests/agent_eval/check_fixtures_exist.py`, `tests/agent_eval/check_pack_keyword_coverage.py`, `tests/agent_eval/check_scenario_class_coverage.py`, `tests/agent_eval/check_task_references_integrity.py`, `tests/agent_eval/validate_scenarios.py`, `tests/agent_eval/validate_tasks.py`, `tests/contract/check_capability_manifests.py`, `tests/contract/check_manifest_completeness.py`, ... |

## LEANATLAS Environment Variables Observed

| Variable | Purpose Category | Evidence (files) |
|---|---|---|
| `LEANATLAS_AGENT_BUILD_ID` | Traceability/telemetry | `tools/feedback/mine_chat_feedback.py` |
| `LEANATLAS_AGENT_SHELL` | Real-agent execution | `tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py` |
| `LEANATLAS_AGENT_TIMEOUT_S` | Real-agent execution | `tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py` |
| `LEANATLAS_ALLOW_HEAVY_PACKAGE_COPY` | Shared Lake cache policy | `tests/contract/check_shared_cache_policy.py`, `tools/workflow/shared_cache.py` |
| `LEANATLAS_CONTEXT_PATH` | Prompt/context handoff | `tools/agent_eval/dummy_agent.py`, `tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py` |
| `LEANATLAS_DOMAIN_MCP_COMMAND` | Domain MCP installation/command | `scripts/bootstrap.sh`, `scripts/doctor.sh`, `tests/setup/deps_smoke.py` |
| `LEANATLAS_DOMAIN_MCP_UVX_FROM` | Domain MCP installation/command | `scripts/bootstrap.sh`, `scripts/doctor.sh`, `tests/setup/deps_smoke.py` |
| `LEANATLAS_E2E_WORKDIR` | Workspace routing | `tests/e2e/run_scenarios.py` |
| `LEANATLAS_EVAL_CONTEXT` | Prompt/context handoff | `tools/agent_eval/dummy_agent.py` |
| `LEANATLAS_EVAL_PROMPT` | Prompt/context handoff | `scripts/bootstrap.sh`, `scripts/doctor.sh`, `tools/agent_eval/dummy_agent.py`, `tools/agent_eval/run_pack.py` |
| `LEANATLAS_EVAL_RUN_ID` | Traceability/telemetry | `tools/agent_eval/dummy_agent.py`, `tools/agent_eval/run_pack.py` |
| `LEANATLAS_EVAL_WORKSPACE` | Workspace routing | `tools/agent_eval/dummy_agent.py`, `tools/agent_eval/run_pack.py` |
| `LEANATLAS_KEEP_WORKSPACE_LAKE` | Shared Lake cache policy | `tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py` |
| `LEANATLAS_LAKE_PACKAGES_SEED_FROM` | Shared Lake cache policy | `tools/workflow/shared_cache.py` |
| `LEANATLAS_PROMPT_PATH` | Prompt/context handoff | `tools/agent_eval/dummy_agent.py`, `tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py` |
| `LEANATLAS_REAL_AGENT_CMD` | Real-agent execution | `scripts/bootstrap.sh`, `scripts/doctor.sh`, `tests/agent_eval/exec_pack_real_agent_nightly.py`, `tests/agent_eval/exec_scenario_real_agent_nightly.py`, `tests/contract/check_setup_docs.py` |
| `LEANATLAS_RUN_DIR` | Traceability/telemetry | `tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py` |
| `LEANATLAS_RUN_ID` | Traceability/telemetry | `tools/agent_eval/dummy_agent.py`, `tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py` |
| `LEANATLAS_SCENARIO_CLASS` | Scenario runtime context | `tools/agent_eval/run_scenario.py` |
| `LEANATLAS_SCENARIO_ID` | Scenario runtime context | `tools/agent_eval/run_scenario.py` |
| `LEANATLAS_SCENARIO_STEP` | Scenario runtime context | `tools/agent_eval/run_scenario.py` |
| `LEANATLAS_SESSION_ID` | Traceability/telemetry | `tools/feedback/mine_chat_feedback.py` |
| `LEANATLAS_SHARED_LAKE_PACKAGES` | Shared Lake cache policy | `tests/contract/check_shared_cache_policy.py`, `tools/workflow/shared_cache.py` |
| `LEANATLAS_STRICT_DEPS` | Strict dependency smoke | `scripts/doctor.sh`, `tests/setup/deps_smoke.py` |
| `LEANATLAS_WORKSPACE` | Workspace routing | `tools/agent_eval/dummy_agent.py`, `tools/agent_eval/run_pack.py`, `tools/agent_eval/run_scenario.py` |

## Operational Notes

- Core profile can run without real-agent command, but nightly real-agent tests require `LEANATLAS_REAL_AGENT_CMD` to be non-dummy.
- Shared Lake policy is enforced by `tests/contract/check_shared_cache_policy.py`; runners must hydrate workspace `.lake/packages` via shared cache.
- MCP tools are external installs: `lean-lsp-mcp` (third-party) and `lean-domain-mcp` (Repo C command endpoint).
- On network-restricted machines, use healthy `.venv` fallback when `uv run --locked` handshake fails, then repair proxy/network before forced resync.
