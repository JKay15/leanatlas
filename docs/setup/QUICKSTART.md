# Quickstart (First-Time Setup)

This page gives the shortest runnable path after your first clone.

## 0) Prerequisites

- OS: macOS / Linux (for Windows, use PowerShell equivalents)
- Installed commands: `uv`, `uvx`, `lake`, `python`

References:
- `docs/setup/README.md`
- `docs/setup/DEPENDENCIES.md`

## 1) One-shot bootstrap

Run at repo root:

```bash
bash scripts/bootstrap.sh
```

Domain MCP pin is loaded from `tools/deps/pins.json` automatically.
If you need to override it temporarily:

```bash
export LEANATLAS_DOMAIN_MCP_UVX_FROM='git+https://github.com/JKay15/lean-domain-mcp@291b0f453cfa2db6708671205fab792e465c574f'
bash scripts/bootstrap.sh
```

Notes:
- The script syncs Python from `uv.lock`, validates dependency pins, warms Lean dependencies, and verifies `lean-lsp-mcp`.
- Bootstrap also verifies Repo-B skills are mounted (`.agents/skills/**`) and runs Lean warmup gates:
  - if skills are missing, bootstrap auto-runs `git submodule update --init --recursive .agents/skills`
  - `importGraph` package presence check
  - `lake build LeanAtlas`
  - `lake lint`
- Bootstrap installs repo-local git hooks via `scripts/install_repo_git_hooks.sh`:
  - `pre-commit` hook (basic hygiene checks)
  - `commit-msg` hook (Conventional Commit policy)
  - `pre-push` hook (branch naming policy)
- If external Domain MCP is not configured, the script prints a warning and shows the fallback path.

## 2) One-shot health check

```bash
bash scripts/doctor.sh
```

Strict mode (runs heavier dependency smoke checks):

```bash
bash scripts/doctor.sh --strict
```

Notes:
- `bootstrap`/`doctor` require a real-agent command for Phase6 nightly checks.
- Recommended value when using Codex CLI:
  `codex exec - < "$LEANATLAS_EVAL_PROMPT"`.
- The configured command is persisted at
  `.cache/leanatlas/onboarding/real_agent_cmd.env`.
- After `bootstrap` + `doctor` + `real_agent_cmd` all pass, onboarding state is written to
  `.cache/leanatlas/onboarding/state.json`.
- Root `AGENTS.md` onboarding block is compacted automatically to reduce routine context usage.
- The archived verbose onboarding text remains available at
  `docs/agents/archive/AGENTS_ONBOARDING_VERBOSE.md`.
- Git hook policy can be repaired manually at any time:
  - `bash scripts/install_repo_git_hooks.sh`
  - `bash scripts/install_repo_git_hooks.sh --check`

## 3) Run core tests

```bash
./.venv/bin/python tests/run.py --profile core
```

Fallback (only when `.venv` is not created yet):

```bash
uv run --locked python tests/run.py --profile core
```

## 4) Install Codex App automations (hard operational gate)

Environment setup alone is not enough. Active automations are mandatory for normal LeanAtlas operation.
Until automation readiness is recorded, onboarding is environment-complete but operationally blocked.

Source of truth:
- `docs/agents/AUTOMATIONS.md`
- `automations/registry.json` (`status=active`)

Current required automations:
- `nightly_reporting_integrity`
- `nightly_mcp_healthcheck`
- `nightly_trace_mining`
- `weekly_kb_suggestions`
- `nightly_dedup_instances`
- `weekly_docpack_memory_audit`
- `nightly_phase3_governance_audit`
- `nightly_chat_feedback_deposition`

After creating them in Codex App:
- trigger each once manually,
- verify outputs are written under `artifacts/**`.
- mark readiness in onboarding state:
  - `./.venv/bin/python tools/onboarding/verify_automation_install.py --mark-done`

## 5) Common issues

- Missing `uv`/`uvx`: install via `docs/setup/external/lean-lsp-mcp.md`.
- Missing `lake`: install Lean toolchain first (`lean-toolchain` is the source of truth).
- Git hooks missing/stale: run `bash scripts/install_repo_git_hooks.sh`.
- Domain MCP not installed: verify `tools/deps/pins.json` has `lean_domain_mcp.run.uvx_from`, or set `LEANATLAS_DOMAIN_MCP_UVX_FROM` and rerun bootstrap.
- `LEANATLAS_REAL_AGENT_CMD` missing: rerun `bootstrap` or set it manually, for example:
  `export LEANATLAS_REAL_AGENT_CMD='codex exec - < "$LEANATLAS_EVAL_PROMPT"'`.
- `uv run --locked` fails with TLS/network handshake: if `./.venv/bin/python` already works, use local `.venv` commands and skip redundant sync; then fix proxy/network before forced resync.
- Network-restricted environment: configure terminal proxy first, then retry `uv sync --locked`.
