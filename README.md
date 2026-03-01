# LeanAtlas (scaffold)

This is a LeanAtlas scaffold focused on **Codex-first workflows**:
- Deterministic reporting contracts (RunReport / RetrievalTrace / AttemptLog)
- TDD gates + executable e2e (cases + scenarios) + stress/soak
- A Codex documentation system (AGENTS.md + `.agents/skills/` + ExecPlans)
- External tooling is documented + smoke-verified (docs/setup)

## Clone
Use submodule-aware clone so Repo-B skills are present on first run:

```bash
git clone --recurse-submodules https://github.com/JKay15/leanatlas.git
cd leanatlas
```

If you already cloned without submodules:

```bash
git submodule update --init --recursive
```

## Start here (Codex users)
- Read `AGENTS.md` (repo root).
- See `docs/agents/README.md` for how instructions and ExecPlans are organized.
- First-time onboarding: `docs/setup/QUICKSTART.md`
- Setup details and external deps: `docs/setup/README.md`

## Tests
- Deterministic core: `python tests/run.py --profile core` or `lake test`
- Nightly (deps + heavier checks): `python tests/run.py --profile nightly`
- Lint discipline: `lake lint`
- Executable e2e: `python tests/e2e/run_cases.py --profile core`
- Sequence scenarios: `python tests/e2e/run_scenarios.py --profile core`

## Cleaning
- `./scripts/clean.sh`
- `./scripts/clobber.sh`
