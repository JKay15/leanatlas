# Setup (local environment and external dependencies)

> Goal: Let Codex (and humans) **definitely** find external tools locally, and verify successful installation with canned commands.
>
> Additional goals: External dependencies must be reproducible, auditable, and rollable (version pin / no drift). See:
> - `tools/deps/pins.json`
> - `docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md`

## 0) Four things you need to know first

1) **LeanAtlas's "source of truth for correctness" is the local Lean build environment** (`lake build`).
2) MCP/retrieval/visualization are all accelerators: they can be absent, but there must be a degradation path.
3) External dependencies must not be "drift installed" (e.g. `@main` / `latest`): they must be pinned to the version or commit.
4) Any external dependencies must be met:
- Clearly describe the installation and verification commands in the documentation (`docs/setup/**`)
- Write clear pin information in pins (`tools/deps/pins.json`)
- Have runnable smoke verification (at least nightly tier)

## 1) Dependency overview

- Dependency summary: see `DEPENDENCIES.md`
- Test-derived environment inventory (commands/env vars/modules): see `TEST_ENV_INVENTORY.md`
- First run for new users: see `QUICKSTART.md`
- One-click scripts: `scripts/bootstrap.sh`, `scripts/doctor.sh`
- External tool installation details: see `external/`
- Depends on pin truth source: see `tools/deps/pins.json`

## 2) Verification entry (recommended)

- Document-level inspection (does not require installation of external tools such as MCP):
- Preferred (already-initialized repo): `./.venv/bin/python tests/run.py --profile core`
- Reproducible bootstrap path (when `.venv` is missing): `uv run --locked python tests/run.py --profile core`
- Compatible fallback (last resort): `python tests/run.py --profile core`

- Depends on smoke (requires you to actually install external tools):
  - `./.venv/bin/python tests/run.py --profile nightly`
- Or run alone: `./.venv/bin/python tests/setup/deps_smoke.py`

> Note: nightly tier is allowed to be heavier (Lean+mathlib/MCP), core tier must be fast and deterministic.
