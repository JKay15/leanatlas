# LeanAtlas AGENTS.override.md (MAINTAINER mode) - TEMPLATE

This is a committed template for advanced users.

- It is inert by default.
- It only takes effect after you copy it to repository root as `AGENTS.override.md`.
- The root `AGENTS.override.md` must remain local (gitignored); do not commit the root file.
- Onboarding must not auto-create this file.

Activation (manual, explicit opt-in):

```bash
cp docs/agents/templates/AGENTS.override.md AGENTS.override.md
```

After this copy, Codex enters MAINTAINER mode via the local root override file.

## Maintainer rules (summary)
- You may modify system code under `LeanAtlas/**`, `tools/**`, `docs/contracts/**`, `tests/**`.
- Any non-trivial change MUST start with an ExecPlan:
  - Read `docs/agents/PLANS.md`
  - Create a new plan under `docs/agents/execplans/`
- TDD is mandatory: add/adjust tests first, then implement, then document.
- Preserve determinism: schema/contracts/reporting must remain reproducible.
- Never let tests pollute the real Toolbox/Incubator in the repository:
  - test-only Toolbox content must be injected into a temporary workspace under `.cache/leanatlas/**`
  - after tests, `git status --porcelain` must be clean

## Required verification before proposing changes
- `python tests/run.py --profile core`
- If you changed workflow/tests: `python tests/run.py --profile nightly`
- If you changed e2e runners: run at least one scenario:
  - `python tests/e2e/run_scenarios.py --profile core`
