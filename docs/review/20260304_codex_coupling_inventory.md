# Codex Coupling Inventory (Task Ledger)

- generated_at: 2026-03-04
- query_scope: tracked + untracked repo files excluding `.git/**` and `.cache/**`
- query_pattern: `codex|Codex|codex_cli|codex-cli|codex exec|claude_code|claude exec|LEANATLAS_REAL_AGENT_CMD|agent_provider|agent_profile`
- purpose: provide a full migration ledger before replacing remaining Codex-specific execution paths

## A. Code / Config Files

Count:  49

- `DOC_PACK_ID.json`
- `automations/registry.json`
- `docs/schemas/AgentProfile.schema.json`
- `docs/schemas/AutomationRegistry.schema.json`
- `scripts/bootstrap.sh`
- `scripts/doctor.sh`
- `tests/agent_eval/check_runner_plan_mode.py`
- `tests/agent_eval/check_scenario_runner_plan_mode.py`
- `tests/agent_eval/exec_pack_real_agent_nightly.py`
- `tests/agent_eval/exec_scenario_real_agent_nightly.py`
- `tests/agent_eval/profiles/dummy_agent.profile.json`
- `tests/agent_eval/tasks/mk_convex_log_barrier/task.yaml`
- `tests/agent_eval/tasks/mk_convex_log_barrier/variants/v1_correct_hint_mathlib_lemma/fixture_overlay/Spec.lean`
- `tests/agent_eval/tasks/mk_convex_log_barrier_gap/task.yaml`
- `tests/agent_eval/tasks/mk_poly_factorization_square/task.yaml`
- `tests/agent_eval/tasks/mk_poly_factorization_square_dvd/task.yaml`
- `tests/agent_eval/tasks/mk_poly_solvability_by_radicals_reuse/task.yaml`
- `tests/agent_eval/tasks/mk_queue_littles_law_slot/task.yaml`
- `tests/agent_eval/tasks/mk_queue_littles_law_slot_reuse/task.yaml`
- `tests/agent_eval/tasks/mk_queue_mg1_lindley/task.yaml`
- `tests/agent_eval/tasks/mk_queue_mg1_lindley_reuse_nonneg/task.yaml`
- `tests/agent_eval/tasks/proof_loop_demo/task.yaml`
- `tests/automation/check_run_automation_local.py`
- `tests/automation/check_stuck_run_recovery.py`
- `tests/automation/dry_run_single.py`
- `tests/automation/validate_registry.py`
- `tests/contract/check_chat_feedback_filtering_policy.py`
- `tests/contract/check_dependency_pins.py`
- `tests/contract/check_doc_pack_completeness.py`
- `tests/contract/check_git_policy_contracts.py`
- `tests/contract/check_onboarding_automation_gate.py`
- `tests/contract/check_phase3_e2e_scenarios.py`
- `tests/contract/check_setup_docs.py`
- `tests/manifest.json`
- `tools/agent_eval/agent_provider.py`
- `tools/agent_eval/dummy_agent.py`
- `tools/agent_eval/run_pack.py`
- `tools/agent_eval/run_scenario.py`
- `tools/coordination/recover_stuck_automation_runs.py`
- `tools/coordination/run_automation.py`
- `tools/coordination/run_automation_local.py`
- `tools/coordination/skills_regen.py`
- `tools/coordination/skills_stubgen.py`
- `tools/module_graph/edges_to_dot.py`
- `tools/onboarding/check_branch_name.py`
- `tools/onboarding/verify_automation_install.py`
- `tools/tests/generate_test_env_inventory.py`
- `tools/workflow/patch_scope.py`
- `tools/workflow/run_cmd.py`

## B. Text / Doc Files

Count:  71

- `.agents/skills/README.md`
- `.agents/skills/leanatlas-automations/SKILL.md`
- `.agents/skills/leanatlas-domain-mcp/SKILL.md`
- `.agents/skills/leanatlas-onboard/SKILL.md`
- `.agents/skills/leanatlas-operator-proof-loop/SKILL.md`
- `AGENTS.md`
- `INIT_FOR_CODEX.md`
- `README.md`
- `automations/README.md`
- `docs/agents/AUTOMATIONS.md`
- `docs/agents/BRANDING.md`
- `docs/agents/CODEX_APP_PROMPTS.md`
- `docs/agents/EVAL_PROBLEM_PACK_GUIDE.md`
- `docs/agents/FEEDBACK_LOOP.md`
- `docs/agents/GLOSSARY.md`
- `docs/agents/MAINTAINER_INIT_TASKS.md`
- `docs/agents/MAINTAINER_WORKFLOW.md`
- `docs/agents/MEMORY_COVERAGE.md`
- `docs/agents/ONBOARDING.md`
- `docs/agents/OPERATOR_WORKFLOW.md`
- `docs/agents/README.md`
- `docs/agents/STATUS.md`
- `docs/agents/VERSION_ROADMAP.md`
- `docs/agents/archive/AGENTS_ONBOARDING_VERBOSE.md`
- `docs/agents/execplans/20260228_domain_mcp_rename_and_topology_alignment.md`
- `docs/agents/execplans/20260228_feedback_governance_closure.md`
- `docs/agents/execplans/20260228_hard_convergence_pack.md`
- `docs/agents/execplans/20260228_strong_guarantee_force_deposit_pack.md`
- `docs/agents/execplans/20260303_agent_eval_materialize_out_root_isolation.md`
- `docs/agents/execplans/20260303_automation_local_execution_guard.md`
- `docs/agents/execplans/20260304_agent_provider_abstraction_v0.md`
- `docs/agents/execplans/20260304_agent_provider_v0_2_runtime_bridge.md`
- `docs/agents/execplans/20260304_file_index_tracked_only.md`
- `docs/agents/execplans/20260304_generated_docs_guardrails.md`
- `docs/agents/execplans/20260304_onboarding_banner_locale_upgrade.md`
- `docs/agents/execplans/20260304_repo_wide_agent_provider_rollout.md`
- `docs/agents/execplans/phase3_dedup_gate_v0.md`
- `docs/agents/execplans/phase3_promotion_structural_signals_v1.md`
- `docs/agents/phase6/PHASE6_USAGE.md`
- `docs/agents/templates/AGENTS.override.md`
- `docs/agents/templates/AGENTS.override.minimal.md`
- `docs/agents/templates/AUTOMATION_INSTALL_CHECKLIST.md`
- `docs/contracts/AGENT_EVAL_CONTRACT.md`
- `docs/contracts/AGENT_EVAL_SCENARIO_CONTRACT.md`
- `docs/contracts/AI_NATIVE_ENGINEERING_CONTRACT.md`
- `docs/contracts/AUTOMATION_CONTRACT.md`
- `docs/contracts/PROBLEM_STATE_CONTRACT.md`
- `docs/contracts/PROMOTION_GATE_CONTRACT.md`
- `docs/contracts/REPO_TOPOLOGY_CONTRACT.md`
- `docs/contracts/RUNREPORT_CONTRACT.md`
- `docs/contracts/SKILLS_GROWTH_CONTRACT.md`
- `docs/contracts/SKILLS_REGEN_CONTRACT.md`
- `docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md`
- `docs/contracts/WORKFLOW_CONTRACT.md`
- `docs/coordination/PHASE_PLAN.md`
- `docs/coordination/USER_REQUIREMENTS.md`
- `docs/reuse/README.md`
- `docs/review/gptpro_full_rebuild_prompt.md`
- `docs/review/gptpro_skill_discovery_prompt.md`
- `docs/setup/DEPENDENCIES.md`
- `docs/setup/QUICKSTART.md`
- `docs/setup/README.md`
- `docs/setup/SUBMODULES.md`
- `docs/setup/TEST_ENV_INVENTORY.md`
- `docs/setup/external/pre-commit.md`
- `docs/testing/E2E_CATALOG.md`
- `docs/testing/README.md`
- `docs/testing/TEST_MATRIX.md`
- `docs/tools/MODULE_VISUALIZATION.md`
- `tests/README.md`
- `tests/agent_eval/README.md`

## Notes

- This inventory is intentionally broad: it includes both executable couplings and narrative/product wording.
- Runtime migration priority should focus on executable coupling points (scripts, runners, automation bridge, nightly tests, setup docs/contracts).
