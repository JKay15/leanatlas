# Phase6 Real-Agent Eval: Usage Scenarios

This document explains how Phase6 ("real agent eval") is *intended* to be used.

Phase6 is designed around a single abstraction boundary:

- **Runner** (this repo): orchestrates the evaluation workflow.
- **Agent** (external): configured via provider/profile (`--agent-provider`, optional `--agent-profile`) or legacy `--agent-cmd`.

The runner does **not** assume a particular authentication method. If your chosen agent implementation needs API keys, you configure those for the agent itself.

## What Phase6 is testing

Phase6 evaluates whether an agent can:

1. Read a task context and repo-local contracts.
2. Take actions in a workspace (edit files, run commands) within the allowed patch scope.
3. Produce machine-readable artifacts (reports) that the grader can score.

The runner is *not* the agent. The runner is the harness.

## How Codex participates

There are two distinct ways "Codex" can be involved:

1. **Codex as the evaluated agent (inner loop)**
   - The runner spawns Codex via `--agent-provider codex_cli` (or legacy `--agent-cmd "codex ..."`).
   - Codex reads the rendered `PROMPT.md` and operates inside the workspace.
   - The runner collects the artifacts Codex writes and grades them.

   Practical note: the runner passes the rendered prompt path via environment variables.

   - `LEANATLAS_EVAL_PROMPT` = path to the rendered `PROMPT.md`
   - `LEANATLAS_EVAL_WORKSPACE` = workspace root (also the process CWD)

   Recommended provider path for Codex CLI:

   - `--agent-provider codex_cli`

   Legacy robust `--agent-cmd` for Codex CLI:

   - `--agent-cmd "codex exec - < \"$LEANATLAS_EVAL_PROMPT\""`

   This avoids quoting issues and guarantees Codex reads exactly what the runner rendered.

2. **Codex App as the operator/orchestrator (outer loop)**
   - You (human) ask Codex App to run the runner commands locally.
   - From your perspective: you only type prompts; Codex runs commands, inspects artifacts, and summarizes results.
   - Under the hood: the runner still provides determinism and repeatable grading.

Both are valid. They solve different problems:

- Inner loop = reproducible, machine-gradable evaluation.
- Outer loop = prompt-driven UX for humans.

## Layer 1: User scenario

This is the default for a user who just cloned the repo and wants to run Phase6.

### Preconditions

- Repo is cloned.
- Python env is ready (`uv sync --locked` recommended).
- A real agent is available via provider/profile or executable command.

### What the user does

- Run a pack or scenario evaluation with provider/profile (or `--agent-cmd`).

Key point: framework-level requirement is a valid agent configuration (provider/profile or command).

If the agent command requires credentials:

- API keys / tokens are configured for the *agent*, not the runner.
- If your agent config maps to **Codex CLI** (`codex_cli` or `codex exec ...`), authenticate the CLI (e.g. `codex login`) or provide an API key via `CODEX_API_KEY` (per Codex CLI docs).
- If your `--agent-cmd` is a **custom OpenAI-API-based agent**, that agent may require `OPENAI_API_KEY` (or whatever env var it documents).

### Expected outputs

A successful Phase6 run produces graded artifacts under the run directory (see `REPORTING_CONTRACT.md`).

Important:

- `pins_used.json` is **runner-owned** and is auto-generated if missing.

## Layer 2: Developer scenario

This is for maintainers developing the framework itself.

### Goal

- Change runner/contract code.
- Re-run Phase6 harness checks.
- Validate that graders + reporting contracts still align.

### Workflow

1. Run contract tests locally (fast).
2. Run `--mode plan` for packs/scenarios (validates structure without spawning a real agent).
3. Run a small `--mode run` with `--limit 1` against a real agent config.

### What to watch for

- Misleading error messages that suggest framework-level auth requirements.
- Hard-gates in graders that depend on artifacts whose ownership is unclear.

The project rule is:

- If an artifact is required for grading and can be derived deterministically, it should be **runner-owned**.

## Layer 3: Automation scenario

This is for running Phase6 on a schedule.

### Codex App automations

Codex App supports *Automations* that run locally on a schedule (they run on your machine while the app is running).

Automation design constraints:

- Automations must be robust to cold starts and caches.
- Automations must emit artifacts and a summary.
- Automations should use deterministic commands + fixed seeds when applicable.

### Recommended automation pattern

Create automations in the main profiles (smoke/core/nightly), plus optional soak:

1. **Smoke**: short, confirms the harness works.
2. **Core**: the minimum meaningful set of tasks.
3. **Nightly/Soak**: heavier runs that can take longer.

Each automation should:

- bootstrap env if missing
- run the evaluation
- archive artifacts
- update `feedback/todos.yaml` when failures are detected

See `docs/agents/CODEX_APP_PROMPTS.md` for copy/paste automation prompts.
