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
