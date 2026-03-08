# Codex App Prompt Templates

This file is intentionally copy/paste friendly.

- **Maintainer mode** prompts assume you allow Codex to run commands and edit files.
- **Operator mode** prompts assume you want Codex to focus on proving/working in `Problems/` and avoid framework changes.

Conventions used in these templates:

- "Repo root" = the folder containing `AGENTS.md`.
- Commands are examples; Codex should run them itself.

## Maintainer: one-shot repo initialization

Use this immediately after cloning.

```text
You are in Maintainer mode.

Goal: make this repo ready for use.

Rules:
- Follow AGENTS.md and all contracts under docs/contracts/.
- Prefer repo-local Python: .venv/bin/python if present; otherwise use `uv run --locked python`.
- Do NOT ask me to run commands. Run them yourself and paste the relevant outputs.
- If you change files, keep changes minimal and explain why.

Tasks (in order):
1) Read INIT_FOR_CODEX.md and execute the checklist.
2) Run the core test profile: `.venv/bin/python tests/run.py --profile core`.
3) If anything fails: fix the root cause (no retry hacks), then re-run core.
4) Summarize what you changed and why.

Deliverables:
- A short summary.
- Paths to any generated artifacts.
- A list of remaining TODO markers (if any) with file paths.

## First prompt: onboarding (banner + consented setup)

Use this if the automatic first-run onboarding did not trigger.

```text
Run the LeanAtlas first-run onboarding flow.

Rules:
- Follow AGENTS.md + docs/agents/ONBOARDING.md.
- Print the LeanAtlas locale-aware onboarding visual (hero banner + info panel).
- Ask me to choose A/B/C before running installs or writing setup state.
- Run a local preflight first (`.venv` + deps import + `lake --version`).
- If preflight passes, report "environment already satisfied" and skip redundant install/update commands.

After I choose:
- If A: execute INIT_FOR_CODEX.md with preflight-aware skip behavior (recommended).
- If B: run only missing setup steps, then core contracts.
- If C: do nothing and continue.

Write onboarding state to .cache/leanatlas/onboarding/state.json.
Then install/verify active automations and mark readiness:
`.venv/bin/python tools/onboarding/verify_automation_install.py --mark-done`.
```

## Maintainer: "find missing requirements and implement"

Use this when you want Codex to hunt for incomplete scaffolding.

```text
You are in Maintainer mode.

Scan the repo for incomplete scaffolding and missing contracts.

Procedure:
1) Search for TODO markers, stubbed files, and failing contract tests.
2) For each finding: classify as (a) must-fix now, (b) acceptable placeholder, (c) out of scope.
3) Implement all (a) items.
4) Run `.venv/bin/python tests/run.py --profile core`.

Constraints:
- Keep compatibility simple: prefer one canonical flag/name (`--profile`) and avoid the legacy tier flag.
- Do not add flake retries. If a test is flaky, fix the determinism/caching/budget.

Output:
- A bullet list of fixes with file paths.
- The final core test status.
```

## Operator: start a new proof task

```text
You are in Operator mode.

Goal: help me formalize the proof for the problem in Problems/<PROBLEM_SLUG>/.

Rules:
- Do NOT modify tools/, tests/, docs/contracts/ unless I explicitly ask.
- If you need a helper tactic or lemma, propose it first, then implement it locally under Problems/.
- Keep Lean edits small and compile frequently.

Steps:
1) Open the problem statement.
2) Identify the minimal set of Lean imports and lemmas needed.
3) Implement the proof incrementally, running `lake build` only for the target file.
4) Summarize the final proof structure.
```

## Run E2E golden cases (prompt-driven)

```text
Run the E2E golden cases in tier=core.

- Use `.venv/bin/python` if available.
- Command: `.venv/bin/python tests/e2e/run_cases.py --profile core --keep-workdir`.

After it finishes:
- Summarize pass/fail.
- If there is a failure, open the corresponding RunReport.json and explain the diagnostic.
- Propose a minimal fix and apply it.
```

## Run E2E scenarios (prompt-driven)

```text
Run E2E scenarios in tier=core.

Command: `.venv/bin/python tests/e2e/run_scenarios.py --profile core --keep-workdir`.

After the run:
- Summarize scenario results.
- For any failure: open the scenario report JSON and explain the failing step.
```

## Phase6: run a pack with Codex as the agent

This is the "inner loop" evaluation (runner spawns a real agent).

```text
Run a Phase6 pack evaluation where the agent is Codex.

Steps:
1) Pick a small pack (limit=1).
2) Run:
   `.venv/bin/python tools/agent_eval/run_pack.py --mode run --limit 1 --agent-provider codex_cli --pack <PACK_ID>`

Compatibility fallback (legacy command path):
- `.venv/bin/python tools/agent_eval/run_pack.py --mode run --limit 1 --agent-cmd 'codex exec - < "$LEANATLAS_EVAL_PROMPT"' --pack <PACK_ID>`

After it finishes:
- Open the produced RunReport.json.
- Confirm `pins_used.json` exists.
- Summarize pass/fail and the top 3 failure causes (if any).
```

## Phase6: plan-mode validation (no real agent)

```text
Validate that Phase6 scenario/pack structures are well-formed without running a real agent.

Run:
- `.venv/bin/python tools/agent_eval/run_pack.py --mode plan --pack <PACK_ID>`
- `.venv/bin/python tools/agent_eval/run_scenario.py --mode plan --scenario <SCENARIO_ID>`

Report:
- Any contract violations.
- Any missing required files.
```

## Codex App Automations: install required active automations

Automations are configured in the Codex App UI. Use this prompt to drive installation of all active automations (no manual authoring by the user).

```text
Install all active Codex App automations for this repo.

Inputs:
- Read docs/agents/AUTOMATIONS.md and automations/registry.json.

Outputs:
- One install block per active automation id, in checklist order.
- Each block must include name, schedule, cwd(s), and prompt body.
- Prompt body must run the local wrapper by absolute repo path:
  `python <REPO_ROOT>/tools/coordination/run_automation_local.py --id <automation_id> --advisor-mode <mode> --verify`
- Do not use `uv run --locked python tools/coordination/run_automation.py ...` in automation prompts.
- Ask for a short "done" confirmation after each item.
- After all are created, ask for one manual trigger per automation.
- Verify artifacts using:
  `.venv/bin/python tools/onboarding/verify_automation_install.py --mark-done`

Do not ask me to run commands.
```

## Codex App Automations: robustness test prompt

```text
Test the robustness of the automation prompts you generated.

For each automation prompt:
1) Run it manually once in a normal Codex session.
2) Simulate a cold start by deleting artifacts only (do not delete .lake unless needed).
3) Confirm that failures produce a clear summary plus links/paths to artifacts.

Output:
- A table of automation -> status -> notes.
- Concrete fixes to prompts or scripts (if needed).
```


## Module graph: generate import visualization artifacts

```text
Generate a module import graph for this repo.

Goals:
- Produce artifacts under `artifacts/module_graph/`.
- Prefer a `.dot` graph (does not require Graphviz).
- If Graphviz is available, also produce an `.html` graph.

Rules:
- Do NOT ask me to run commands. Run them yourself.
- Do not commit generated artifacts (keep git status clean).

Steps:
1) Create the output directory: `artifacts/module_graph/`.
2) Build what is needed to run import-graph:
   - Run `lake build` (or build the specific `--to` modules you plan to graph).
3) Generate a focused import graph for `LeanAtlas`:
   - `lake exe graph --to LeanAtlas artifacts/module_graph/LeanAtlas.dot`
   - If Graphviz is installed: `lake exe graph --to LeanAtlas artifacts/module_graph/LeanAtlas.html`
4) Generate a source-only graph (works even if a full build is not available):
   - Extract JSON edges with `scripts/import_edges_from_source.lean`.
   - Convert to DOT with `tools/module_graph/edges_to_dot.py`.

Deliverables:
- The paths to produced artifacts.
- A short summary: node/edge counts (if available) and any missing-tool warnings.
```
