# ExecPlans

This directory stores **execution plan** documents (ExecPlans).

Rules:
- New plans: `<YYYYMMDD>_<short_name>.md` or a fixed name when it is a phase master plan.
- One plan solves one thing.
- Plans must be self-contained (someone can execute it without chat history).
- Plans must include a TDD plan (at least core/nightly layering) and artifact conventions.

See: `docs/agents/PLANS.md`

## Current plans
- Phase3: DedupGate V0 (Instances): `phase3_dedup_gate_v0.md`
- Phase3: PromotionGate V0 (minimal promotion loop): `phase3_promotion_gate_v0.md`
- Phase3: GCGate V0 (Seeds GC loop): `phase3_gc_gate_v0.md`
- 2026-03-03: Automation local-execution guard: `20260303_automation_local_execution_guard.md`
- 2026-03-03: Agent-eval materialize out_root isolation: `20260303_agent_eval_materialize_out_root_isolation.md`
- 2026-03-04: Generated-doc guardrails: `20260304_generated_docs_guardrails.md`

- 2026-03-04: FILE_INDEX tracked-only generation: `20260304_file_index_tracked_only.md`
- 2026-03-03: Generator newline canonicalization: `20260303_generator_newline_canonicalization.md`
- 2026-03-05: Wave review-closure hardening: `20260305_wave_review_closure_hardening_v0.md`
- 2026-03-05: Dynamic timeout reconnect policy: `20260305_dynamic_timeout_reconnect_policy_v0.md`
- 2026-03-05: Wave isolated-review hang recovery hardening: `20260305_wave_review_workspace_hang_fix_v0.md`
- 2026-03-05: LOOP Wave-C hardening backlog: `20260305_loop_waveC_hardening_backlog_v0.md`
- 2026-03-05: Master closeout before LangChain/LangGraph adaptation: `20260305_loop_full_closeout_before_langgraph_v0.md`
