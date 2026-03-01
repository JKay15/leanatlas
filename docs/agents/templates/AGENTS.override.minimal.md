# LeanAtlas - AGENTS.override.md (minimal template)

This is a committed template for a compact local override.
It is optional and inert by default.

- It only takes effect after you copy it to repository root as `AGENTS.override.md`.
- The root `AGENTS.override.md` is local (gitignored). Do not commit the root file.
- The full guidance remains in `AGENTS.md` and `docs/agents/**`.

Activation (manual):

```bash
cp docs/agents/templates/AGENTS.override.minimal.md AGENTS.override.md
```

To restore full always-on guidance:

- delete `AGENTS.override.md`
- restart Codex

## Mode selection (explicit)

LeanAtlas mode is a local file (gitignored):

- `.cache/leanatlas/mode.json`

Rules:

- missing file → **OPERATOR**
- `{"mode": "MAINTAINER"}` → **MAINTAINER**

Do not infer mode from the existence of this file.

## Onboarding (only when needed)

If onboarding is incomplete or outdated (missing `.cache/leanatlas/onboarding/state.json`):

- use the skill: `$leanatlas-onboard`
- do not run networked installs without explicit consent

## OPERATOR boundaries (short)

In OPERATOR mode:

- you may edit only within `Problems/<problem_slug>/`
- do not edit `Spec.lean`
- do not edit platform code under `LeanAtlas/**`, `tools/**`, `docs/contracts/**`, `tests/**`

If you need to change platform code: TRIAGE and produce a maintainer plan.

## Required evidence (short)

For every run/attempt, write the reporting triple under `Problems/<slug>/Reports/<run_id>/`:

- `RunReport.json` + `RunReport.md`
- `RetrievalTrace.json`
- `AttemptLog.jsonl`

See:

- `docs/contracts/REPORTING_CONTRACT.md`
- `docs/contracts/HARD_REQUIREMENTS.md`
- `docs/agents/README.md` (task → docs map)
