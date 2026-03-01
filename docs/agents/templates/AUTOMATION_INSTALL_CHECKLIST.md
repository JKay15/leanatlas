# Automation Install Checklist (Codex App)

Use this template immediately after onboarding `A` or `B` completes.

Goal:
- install all required active automations in Codex App UI,
- avoid missing any closed-loop automation,
- verify each automation writes artifacts to the expected location.

## Source of truth

- `automations/registry.json` (`status=active`)
- `docs/agents/AUTOMATIONS.md`

Do not install from memory; always re-check the active list above.

## Copy/Paste prompt for Codex (post-onboarding)

```text
Install the LeanAtlas Codex App automations using the canonical checklist in:
docs/agents/templates/AUTOMATION_INSTALL_CHECKLIST.md

Rules:
- Read automations/registry.json and docs/agents/AUTOMATIONS.md first.
- Generate one install block per active automation id (name, schedule, cwd, prompt body).
- Present blocks in the exact checklist order.
- After each automation is created in Codex App UI, ask for a short "done" confirmation.
- After all are created, ask me to manually trigger each once and verify artifact paths.
- Do not skip any active automation id.
```

## Install order (required)

1. `nightly_reporting_integrity`
2. `nightly_mcp_healthcheck`
3. `nightly_trace_mining`
4. `weekly_kb_suggestions`
5. `nightly_dedup_instances`
6. `weekly_docpack_memory_audit`
7. `nightly_phase3_governance_audit`
8. `nightly_chat_feedback_deposition`

## Post-install verification (required)

After creating all eight automations, manually trigger each once and confirm:

- `nightly_reporting_integrity` -> `artifacts/automation/nightly_reporting_integrity/**`
- `nightly_mcp_healthcheck` -> `artifacts/mcp_health/**`
- `nightly_trace_mining` -> `artifacts/telemetry/**`, `artifacts/bench/trace_mining/**`
- `weekly_kb_suggestions` -> `artifacts/skills_regen/**`
- `nightly_dedup_instances` -> `artifacts/dedup/**`
- `weekly_docpack_memory_audit` -> `artifacts/automation/weekly_docpack_memory_audit/**`
- `nightly_phase3_governance_audit` -> `artifacts/phase3_governance/**`
- `nightly_chat_feedback_deposition` -> `artifacts/feedback/chat_feedback/**`, `artifacts/feedback/ledger/**`, `artifacts/feedback/traceability/**`

If any path is missing, keep the thread open and debug that automation before closing onboarding.
