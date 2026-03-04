# LeanAtlas onboarding (Codex-first, prompt-driven)

This repo is meant to feel **product-like** when opened in the Codex App.

Goal:

* A user clones the repo.
* Their **first prompt** triggers a short “welcome + setup” flow.
* Codex asks for consent and then performs the setup itself.
* After that, the user can stay in **Operator** mode and focus on proofs.

The onboarding flow is implemented as an **agent behavior contract** (AGENTS.md + skill).
It is not a separate CLI installer.

## What “first prompt onboarding” can and cannot do

What we can do reliably (repo-owned):

* Print a terminal hero banner + info panel.
* Detect whether onboarding is environment-complete and operational-ready via a local state file.
* Explain required environment pieces and why they matter.
* Ask for explicit consent (a clear “YES/NO” interaction in chat).
* Run initialization commands and produce artifacts.
* Generate and drive Codex App automation installation from the repo checklist.

What we cannot guarantee (app-owned UI features):

* A pre-chat modal or “popup” before the user sends the first prompt.
  The first interaction still starts from a user prompt.
* Automatic creation of Codex App automations without user interaction.
  Codex can generate the exact automation prompts and guide you through configuration.

## State file (first-run detection)

Onboarding state is recorded here (gitignored):

* `.cache/leanatlas/onboarding/state.json`

Minimal expected fields:

```json
{
  "schema": "leanatlas.onboarding_state",
  "schema_version": "0.1.0",
  "completed": true,
  "completed_at": "2026-02-27T00:00:00Z",
  "operational_ready": true,
  "operational_ready_at": "2026-02-27T00:15:00Z",
  "steps": {
    "bootstrap": "ok",
    "doctor": "ok",
    "real_agent_cmd": "ok",
    "automations": "ok"
  }
}
```

Notes:

* `completed=true` means environment setup is done.
* `operational_ready=true` means active automations are installed/verified and normal task work may proceed.
* If a new version of the repo changes onboarding requirements, bump `schema_version`.

## The onboarding skill

The onboarding flow is routed through:

* `.agents/skills/leanatlas-onboard/SKILL.md`

The skill defines:

* the onboarding visual text,
* the consent gates,
* the exact checklist Codex must execute (`INIT_FOR_CODEX.md`),
* and the expected “done” artifacts.

Banner source of truth:

* `docs/agents/BRANDING.md`
* `docs/agents/locales/zh-CN/ONBOARDING_BANNER.md` (zh-CN locale asset)

## Recommended onboarding behavior (exact)

On first prompt (any content, including a simple `hi`), Codex should:

1) Read `.cache/leanatlas/onboarding/state.json`.
2) If missing/outdated, or if `operational_ready != true`:
   - print a locale-aware onboarding visual (hero banner + info panel)
     - Chinese/CJK user prompt => use `docs/agents/locales/zh-CN/ONBOARDING_BANNER.md`
     - otherwise => use `docs/agents/BRANDING.md`
   - show a 3-option consent menu:
     - **A)** “Python-only” (uv + .venv + core contracts)
     - **B)** “Full maintainer init” (execute `INIT_FOR_CODEX.md`)
     - **C)** “Skip” (continue without setup)
3) Before executing A/B, run a local preflight (no installs):
   - check `./.venv/bin/python` exists
   - check `./.venv/bin/python -c "import yaml, jsonschema"` succeeds
   - check `lake --version` succeeds
   - if all checks pass, report that setup prerequisites are already satisfied and skip redundant install/update steps.
4) If the user chooses A or B:
   - execute only missing steps using repo Python policy
   - ensure Repo-B skills are mounted (`.agents/skills/**`)
   - install repo-local git discipline hooks (`bash scripts/install_repo_git_hooks.sh`)
   - run Lean warmup verification (`importGraph` check + `lake build LeanAtlas` + `lake lint`)
   - keep diffs minimal
   - write the state file
   - once `bootstrap` + `doctor` + `real_agent_cmd` all pass, compact root `AGENTS.md` onboarding block
     (verbose archive remains in `docs/agents/archive/AGENTS_ONBOARDING_VERBOSE.md`)
5) End with:
   - a short summary
   - where artifacts were written
   - mandatory operational gate: install/verify all `status=active` automations in Codex App
   - what remains optional (for example: Phase6 real-agent eval)

### Required operational gate: install active automations in Codex App

Codex must explicitly tell the user:

1) Read automation specs:
   - `docs/agents/AUTOMATIONS.md`
   - `automations/registry.json`
   - `docs/agents/templates/AUTOMATION_INSTALL_CHECKLIST.md`
2) Generate one install block per active automation and present them in checklist order.
   - Each block must use local-execution wrapper command with absolute repo path:
     - `python <REPO_ROOT>/tools/coordination/run_automation_local.py --id <automation_id> --advisor-mode <mode> --verify`
   - Do not use `uv run --locked ... run_automation.py` in automation prompts.
3) Ask for per-item confirmation after each automation is created in Codex App UI.
4) Manually trigger each once and verify artifacts under `artifacts/**`.
5) Mark readiness only after verification succeeds:
   - `./.venv/bin/python tools/onboarding/verify_automation_install.py --mark-done`

`verify_automation_install.py` enforces:
- artifacts exist for every active automation
- installed automation prompt/cwds use source-workspace local wrapper policy (worktree-safe)

Hard behavior rule:
- If the automation gate is not complete, do not proceed with normal proof/maintainer tasks.
- Reply with automation install/verification guidance until the gate passes.

Current required set:
- `nightly_reporting_integrity`
- `nightly_mcp_healthcheck`
- `nightly_trace_mining`
- `weekly_kb_suggestions`
- `nightly_dedup_instances`
- `weekly_docpack_memory_audit`
- `nightly_phase3_governance_audit`
- `nightly_chat_feedback_deposition`

## Idempotency requirement (hard rule)

Onboarding must be safe to re-run on a prepared machine.

Required behavior:

* Never reinstall dependencies blindly when preflight says the environment is already ready.
* Always report what was skipped vs executed.
* Run verification gates even when install steps are skipped.

## Override activation rule (hard rule)

Templates are distributable and user-editable, but must not auto-trigger:

* Keep `docs/agents/templates/AGENTS.override.md` and
  `docs/agents/templates/AGENTS.override.minimal.md` in the repository.
* Do not auto-create root `AGENTS.override.md` during onboarding.
* Root override is manual opt-in only: a human must explicitly copy a template to root.

## Why consent matters

Setup can involve:

* network access (uv syncing, Lean deps, mathlib fetch)
* writing files (`.venv/`, `.lake/`, `.cache/leanatlas/**`)

Codex should never do those actions silently in a new checkout.
