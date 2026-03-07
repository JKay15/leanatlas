# ExecPlans

This directory stores **execution plan** documents (ExecPlans).

Rules:
- New plans: `<YYYYMMDD>_<short_name>.md` or a fixed name when it is a phase master plan.
- One plan solves one thing.
- Plans must be self-contained (someone can execute it without chat history).
- Plans must include a TDD plan (at least core/nightly layering) and artifact conventions.

See: `docs/agents/PLANS.md`

## Index only
This README is a non-authoritative index.

If you need the real current plan state:
- inspect each plan's `status:` front matter directly
- then, for the latest maintainer work, follow the corresponding maintainer LOOP / session evidence under `artifacts/loop_runtime/by_key/**`

This means a hand-maintained list here must not be treated as the source of truth for active work.

## Useful entry points
- Phase3 master plans:
  - `phase3_dedup_gate_v0.md`
  - `phase3_promotion_gate_v0.md`
  - `phase3_gc_gate_v0.md`
- Recent LOOP hardening cluster:
  - `20260305_loop_waveA_foundation_v0.md`
  - `20260305_loop_waveB_runtime_sdk_v0.md`
  - `20260305_loop_waveC_hardening_backlog_v0.md`
  - `20260306_maintainer_loop_facade_visibility_v0.md`
  - `20260306_review_canonical_payload_v0.md`
  - `20260306_execplan_closeout_hygiene_v0.md`
