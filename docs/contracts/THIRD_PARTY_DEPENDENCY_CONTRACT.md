# THIRD_PARTY_DEPENDENCY_CONTRACT v0

Goal: keep external dependencies (“third-party wheels”) inside a cage: **reproducible, auditable, rollbackable**.
This prevents a silent upstream upgrade from breaking the entire system.

This contract primarily constrains **MAINTAINER** mode (build/evolve).
In **OPERATOR** mode, dependency config must not be modified.

---

## 0) Terms (precise)

- **External dependency / wheel**: anything not defined by this repo’s source code that can affect build/retrieval/proof/testing/automation results.
  Examples: Lean toolchain, mathlib revision, Lake packages, Python toolchain, MCP servers, CLI tools (`rg`, `uv`).

- **Pin**: lock a dependency to an identifier that must not drift.
  - Git: prefer immutable **commit SHA** (or immutable tag).
  - Package managers: exact version (`==x.y.z`) or a lockfile that locks transitive deps (e.g. `uv.lock`).
  - OS tools: at least a **min_version** and a verification command.

- **Provenance**: record where the dependency comes from and how to verify it (hashes, versions, upstream URL, commit).

- **Allowlist**: the set of approved dependencies. Anything not on the allowlist is “unapproved”.

---

## 1) Single source of truth

Pin info must exist in two synchronized forms:

1) **Machine-readable (authoritative)**: `tools/deps/pins.json`
2) **Human-readable (install/verify)**: `docs/setup/DEPENDENCIES.md` + `docs/setup/external/*.md`

Rule: any dependency change must update both (1) and (2), and must run the relevant tests.

---

## 2) Hard rules (MUST / MUST NOT)

### 2.1 MUST: every external dependency must be covered by pins.json
If it is used by CI/tests/automations/MCP/proof loop, it must have a pin entry.

### 2.2 MUST: every dependency must state three things
- **Why**: what it is used for (why we need it).
- **Install**: exact local install commands.
- **Verify**: exact commands to confirm it works.

### 2.3 MUST NOT: forbidden drifting sources
The following are invalid and must be rejected by contract tests:
- `@main` / `@master` / `@latest`
- `git+https://...` without `@<commit>`
- docs that say “install the latest” with no pin/min_version/verify

### 2.4 MUST: upgrades go through a rollbackable PR
Any version bump must be a single PR containing:
- `tools/deps/pins.json` diff (old → new)
- synced install/verify docs (`docs/setup/**`)
- passing `./.venv/bin/python tests/run.py --profile core` (or `uv run --locked python tests/run.py --profile core` when `.venv` is absent)
- if the dependency affects execution (MCP/Lake/uv/toolchain): run `--profile nightly` or explicitly document why it cannot be run and what the risks are

No silent local upgrades.

---

## 3) Mature industry practice (we copy the homework)

LeanAtlas’s dependency governance follows established ideas from supply-chain security and reproducible builds:

- Maintain an approved component/version list + provenance (similar to NIST SSDF guidance).
- Prefer tamper-resistant, traceable builds (aligned with SLSA-style thinking).
- Lock transitive deps via lockfiles (standard practice across ecosystems).

LeanAtlas mapping:
- allowlist pins (`pins.json`)
- install/verify docs (`docs/setup/**`)
- smoke checks (nightly)
- rollbackable PRs

---

## 4) TDD requirements

### 4.1 Contract-level (core profile)
`tests/contract/check_dependency_pins.py` must validate:
- `tools/deps/pins.json` exists and required fields are present
- forbidden drift sources are absent (`main/latest`, unpinned git)
- `pyproject.toml` and `uv.lock` exist (uv standard)
- `docs/setup/**` matches pins (at least key pin strings)

### 4.2 Environment-level (nightly profile)
`tests/setup/deps_smoke.py` (STRICT mode) should actually run:
- `uv lock --check`
- `uv sync --locked`
- `uvx --from <pinned> lean-lsp-mcp --help`
- (future) call the MCP healthcheck for lean-lsp-mcp

---

## 5) Codex execution rules (avoid accidental upgrades)

- Python execution policy:
  - Prefer repo-local `.venv` execution once initialized: `./.venv/bin/python <...>`.
  - Use `uv run --locked python <...>` only when `.venv` is missing or when lockfile-based re-resolution is intentional.
  - Do not use `python3`; use `python` only where a portable fallback is needed.


- OPERATOR: must not modify:
  - `tools/deps/pins.json`
  - `pyproject.toml` / `uv.lock`
  - `lean-toolchain` / `lakefile.lean`
  - `docs/setup/**`

- MAINTAINER: if you need to add/upgrade a dependency:
  - write an ExecPlan first
  - follow the PR upgrade flow described above
