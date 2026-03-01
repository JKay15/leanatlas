# Testing system

Goal: turn TDD from a slogan into an **auditable, reproducible, extensible** engineering system.

LeanAtlas uses four profiles:

- **smoke**: ultra-fast gate (schemas/contracts; no Lean build required).
- **core**: PR gate (must run on every change). Fast and deterministic. Includes smoke.
- **nightly**: expanded CI (may require external tools, MCP, full local Lean env). Includes core.
- **soak**: extreme sequence/pressure tests (find state leaks, regression chains, long-run collapse). Includes nightly.

Profiles are inclusive: higher profiles include lower ones.


## Test intents

- See `docs/testing/TEST_INTENTS.md` for why each test category exists and what fixes are considered valid.

## Single source of truth: `tests/manifest.json`

- `tests/manifest.json` is the test registry and the machine-executable “test matrix”.
- **Every script that counts as a test must be registered**, otherwise CI cannot see it.
- `./.venv/bin/python tests/run.py --profile <profile>` reads the registry and executes tests.

## Human-friendly matrix

- `docs/testing/TEST_MATRIX.md` is a deterministic, human-readable view generated from the registry.
- Any PR that changes the registry must update the matrix (enforced by core profile).

## E2E catalog

E2E cases and scenarios are Lean-backed tests defined under `tests/e2e/`.

- Case/scenario intent and debugging rules: `docs/testing/E2E_CATALOG.md`

## How to add a test (standard flow)

1) Write the script:
   - preferred locations: `tests/contract/`, `tests/schema/`, `tests/e2e/`, `tests/stress/`, `tests/setup/`
   - naming: `check_*.py` / `validate_*.py` / `exec_*.py`

2) Register it in `tests/manifest.json`:
   - required fields: `id`, `profile`, `phase`, `area`, `goal`, `runtime_budget_sec`, `script`

3) Update the matrix:

```bash
./.venv/bin/python tools/tests/generate_test_matrix.py --write
```

4) Run the default gate:

```bash
./.venv/bin/python tests/run.py --profile core
```

## Artifacts and cleaning

- Test artifacts must land only in `artifacts/**` or `.cache/leanatlas/**` (both are gitignored).
- One-shot cleaning:
  - `scripts/clean.sh`
  - `scripts/clobber.sh`

## Observability (no silent waiting)

LeanAtlas test runners are required to be **self-diagnosing**:

- Any external command execution must go through `tools/workflow/run_cmd.py`.
- `run_cmd()` prints:
  - the full command + cwd
  - where stdout/stderr logs are written
  - exit code + duration
  - on failure, an automatic tail excerpt of stderr/stdout

This ensures humans and agents (Codex) are never forced to "hunt" for logs.

To suppress streaming output (e.g., in very noisy environments), set:

```bash
export LEANATLAS_QUIET=1
```
