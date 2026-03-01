# Automations (Codex background task: "Task Specification Table" of this warehouse)

This directory is used to save **LeanAtlas's internal specification** for Codex Automations (machine-readable + human-readable).

- Goal: Write "backend unattended library maintenance/quality access control tasks" into auditable, reproducible, and TDD-able specifications.
- Note: Codex App's Automations are currently mainly created and managed through the UI; the `automations/registry.json` of this warehouse is used as a **single source of truth** for:
1) Let Codex/maintainers know what automations are available
2) Allow CI to verify that specifications do not drift (TDD)
3) Allow Codex CLI (`codex exec`) to reuse the same set of task definitions in CI/scripts

Please read along:
- `docs/agents/AUTOMATIONS.md`
- `docs/contracts/AUTOMATION_CONTRACT.md`
