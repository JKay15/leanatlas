---
name: leanatlas-onboard
description: "First-run onboarding: print the LeanAtlas banner, ask for consent, initialize env + contracts + core tests, and generate Codex App automation prompts."
---

## What this skill is

This skill turns a fresh clone into a usable workspace **without asking the human to run commands**.

It is intentionally designed to feel like a product onboarding:

1) show a banner,
2) explain what will happen,
3) ask for consent,
4) run setup + verify,
5) record a local done-state.

## Use when

- The user just cloned the repo and this is the first Codex prompt.
- The user says “initialize”, “bootstrap”, “setup”, or “make it ready”.
- The onboarding state file is missing/outdated.

## Don't use when

- The user is in OPERATOR mode proving a single problem and explicitly wants *no framework actions*.
- The user says “skip setup”.

## Outputs

- Onboarding summary with selected option (A/B/C) and preflight result.
- Mandatory post-onboarding automation install checklist generated from `docs/agents/AUTOMATIONS.md` + `automations/registry.json`.
- On success: `.cache/leanatlas/onboarding/state.json`.
- After bootstrap+doctor success: compacted root `AGENTS.md` onboarding block.

## Must-run checks

- Preflight checks: `test -x ./.venv/bin/python`, deps import, and `lake --version`.
- Verification gate for setup path: `./.venv/bin/python tests/run.py --profile core`.

## Banner (print on first-run)

```text
       □   △   ○
┌──────────────────────┐
│  L E A N  A T L A S  │
└──────────────────────┘
```

Banner source of truth:

- `docs/agents/BRANDING.md`

## Consent gate (hard rule)

Before running *any* networked install or writing setup state, ask the user to choose:

**A) Python-only setup (safe + fast)**
- Ensure `uv` exists.
- Create/sync `.venv` via `uv sync --locked`.
- Run core contracts: `.venv/bin/python tests/run.py --profile core`.

**B) Full maintainer initialization (recommended)**
- Execute `INIT_FOR_CODEX.md` (Steps 0–7, plus optional Step 8).

**C) Skip (do nothing)**
- Continue with the user’s task.

If the user does not clearly choose A/B/C, do not proceed.

## First-run detection

Treat onboarding as required when this file is missing or outdated:

- `.cache/leanatlas/onboarding/state.json`

This path is gitignored.

## Preflight before any install/update (hard rule)

Before running A or B, perform local readiness checks:

1) `test -x ./.venv/bin/python`
2) `./.venv/bin/python -c "import yaml, jsonschema; print('deps-ok')"`
3) `lake --version`

If all pass:

- report that the local environment is already satisfied,
- skip redundant install/update steps (`uv sync --locked`, `lake update`),
- continue with verification gates and state write.

## Execution (A/B)

### A) Python-only

1) Verify `uv`:
   - `uv --version`
2) If preflight failed, sync venv:
   - `uv sync --locked`
3) Verify critical imports (always):
   - `./.venv/bin/python -c "import yaml, jsonschema; print('deps-ok')"`
4) Run core contracts:
   - `./.venv/bin/python tests/run.py --profile core`

### B) Full maintainer init

Follow `INIT_FOR_CODEX.md` as an executable checklist.

Hard requirements:

- Prefer `./.venv/bin/python` once it exists.
- If preflight passes, skip redundant install/update commands and continue with verification steps.
- Fix root causes (no retry/jitter hacks).
- Keep diffs minimal.
- Any produced artifacts must land under `artifacts/**`.

## Codex App automations (required post-onboarding step)

After A or B succeeds, Codex must provide a “ready-to-paste automation bundle” and a concrete install checklist:

- Read: `docs/agents/AUTOMATIONS.md` and `automations/registry.json`.
- Use install template: `docs/agents/templates/AUTOMATION_INSTALL_CHECKLIST.md`.
- Output: three automation prompts (smoke/core/nightly) plus a robustness checklist.
- List all active automation IDs and ask the user to create them in Codex App UI.
- Require one manual trigger per automation and confirmation that outputs land under `artifacts/**`.

Important:

- Automations are configured in the Codex App UI.
- Codex should not claim it can silently install them.

## Done state

If A or B completes successfully, write:

- `.cache/leanatlas/onboarding/state.json`

Use the minimal schema defined in `docs/agents/ONBOARDING.md`.

After `bootstrap` + `doctor` both pass, run:

- `./.venv/bin/python tools/onboarding/finalize_onboarding.py --step bootstrap`
- `./.venv/bin/python tools/onboarding/finalize_onboarding.py --step doctor`

Expected result:
- root `AGENTS.md` onboarding section is compacted
- verbose copy remains in `docs/agents/archive/AGENTS_ONBOARDING_VERBOSE.md`

## Deliverables (what to report back)

- Which option (A/B/C) was selected.
- Preflight result (ready/not-ready) and why.
- Which steps were skipped because requirements were already satisfied.
- The key verification outputs (short excerpts only).
- Where the onboarding state was written.
- Which active automations must be installed next, with install order.
- Any remaining TODOs (file paths).
