# AGENTS Onboarding (Verbose Archive)

This file stores the full onboarding block that can be removed from root `AGENTS.md`
after successful environment initialization.

It is intentionally low-frequency and should not be preloaded during normal proof work.

## Verbatim Block

On the first user prompt in a fresh clone (missing `.cache/leanatlas/onboarding/state.json`),
Codex must run a short onboarding flow before any normal reply (including when the user only says `hi`):
If the state exists but `operational_ready != true` (or `steps.automations != "ok"`), route to the automation install gate before normal task work.

1) Print the LeanAtlas locale-aware onboarding visual:
   - Chinese/CJK prompt: use `docs/agents/locales/zh-CN/ONBOARDING_BANNER.md`
   - otherwise: use `docs/agents/BRANDING.md`
```text
+------------------------------------------------------------------------------+
| LEANATLAS :: Powered by LeanAtlas                                            |
+------------------------------------------------------------------------------+
| [i] Welcome to LeanAtlas                                                     |
| Choose: A) Python-only  B) Full init  C) Skip                                |
| Operational gate: install/verify active automations before normal tasks.     |
+------------------------------------------------------------------------------+
```

2) Ask the user to choose one option before running setup commands:
- `A)` Python-only setup (`uv sync --locked` + core checks)
- `B)` Full maintainer initialization (`INIT_FOR_CODEX.md`)
- `C)` Skip setup

3) Preflight before setup commands (mandatory):
- check whether the local environment already satisfies setup requirements:
  - `./.venv/bin/python` exists
  - `./.venv/bin/python -c "import yaml, jsonschema"` succeeds
  - `lake --version` succeeds
- if requirements are already satisfied, report that to the user and skip redundant install/update steps.

4) If user selects `A` or `B`, run only missing setup steps and write onboarding state:
- `.cache/leanatlas/onboarding/state.json`

5) End onboarding with next commands:
- `bash scripts/bootstrap.sh`
- `bash scripts/doctor.sh`
- `python tests/run.py --profile core`
- `python tools/onboarding/verify_automation_install.py --mark-done`

Operational gate:
- Environment setup completion alone is not enough.
- Do not proceed with normal proof/maintainer tasks until automation readiness is recorded.

Routing rule:
- Use `.agents/skills/leanatlas-onboard/SKILL.md` as the first-run execution guide.
- Never run networked installs or write onboarding state without explicit user consent.

Domain MCP note:
- If external Domain MCP source is not configured, ask for `LEANATLAS_DOMAIN_MCP_UVX_FROM`.
- If network/bootstrap is constrained, suggest:
  `bash scripts/bootstrap.sh --skip-uv-sync --skip-lake-update`
