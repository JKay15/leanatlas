---
title: Maintainer LOOP facade and visible progress trail
owner: codex
status: completed
created: 2026-03-06
---

## Purpose / Big Picture
The maintainer LOOP contracts now require upfront session materialization, but the current Python surface is still too low-level. It is easy to know the rules, yet still operate through ad-hoc helper calls that make the chat history and the artifact trail hard to read. This plan fixes that ergonomics gap. Maintainer work should have a single obvious Python entry path that materializes the graph/session, advances node results, and closes the run. The same change also makes in-progress execution easier to audit by publishing a deterministic progress sidecar rather than forcing observers to parse `NodeJournal.jsonl`. Finally, the review waiting policy should speak more directly: impatience-driven two-minute aborts are not valid for `codex_cli`, whose high-thinking modes are intentionally slow.

## Glossary
- Maintainer LOOP facade: a higher-level Python API that wraps the existing maintainer helpers into a single session object.
- Progress sidecar: a deterministic derived artifact showing completed/pending/current maintainer nodes without reading the append-only journal directly.
- Observation policy: the frozen provider waiting rules used by `run_review_closure`, including hard timeout, transport idle, semantic idle, and minimum observation window.

## Scope
In scope:
- `tools/loop/maintainer.py` high-level maintainer session facade and progress sidecar support.
- `tools/loop/__init__.py` export surface for the new maintainer API.
- LOOP contracts/docs/tests that must explain and enforce the visible maintainer execution path.
- Explicit wording that impatience-driven short waits are invalid for `codex_cli`.

Out of scope:
- Reworking the general graph scheduler.
- Changing provider CLI behavior.
- Adding a full interactive UI for maintainer sessions.

## Interfaces and Files
- `tools/loop/maintainer.py`
  - add a higher-level maintainer session API
  - derive and persist a `MaintainerProgress.json` sidecar
- `tools/loop/__init__.py`
  - export the new facade
- `docs/agents/PLANS.md`
  - explain that the maintainer LOOP should normally be driven through the Python facade, not a post-hoc summary
- `docs/contracts/LOOP_GRAPH_CONTRACT.md`
  - require visible progress evidence alongside the append-only journal
- `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - pin the preferred maintainer Python entrypoint and visible progress artifact
- `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - make the codex wait policy wording more explicit about slow high-thinking modes and invalid short aborts
- `tests/contract/check_loop_maintainer_session.py`
  - TDD for the facade and progress sidecar
- `tests/contract/check_maintainer_loop_requirement.py`
  - require the stronger wording
- `tests/contract/check_loop_contract_docs.py`
  - require the new snippets

## Milestones
1) Red tests for facade and visibility
- Deliverables:
  - update `tests/contract/check_loop_maintainer_session.py`
  - update `tests/contract/check_maintainer_loop_requirement.py`
  - update `tests/contract/check_loop_contract_docs.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_maintainer_session.py`
  - `uv run --locked python tests/contract/check_maintainer_loop_requirement.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
- Acceptance:
  - tests fail before implementation because the repo lacks the higher-level facade and explicit progress/wait wording.

2) Maintainer facade + progress sidecar
- Deliverables:
  - update `tools/loop/maintainer.py`
  - update `tools/loop/__init__.py`
- Commands:
  - `uv run --locked python tests/contract/check_loop_maintainer_session.py`
- Acceptance:
  - a single session object can materialize, record node results, and close the run
  - `MaintainerProgress.json` exists from the start and updates deterministically as the session advances

3) Contract/doc alignment
- Deliverables:
  - update `docs/agents/PLANS.md`
  - update `docs/contracts/LOOP_GRAPH_CONTRACT.md`
  - update `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - update `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
- Commands:
  - `uv run --locked python tests/contract/check_maintainer_loop_requirement.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
- Acceptance:
  - docs explain the preferred maintainer facade path
  - docs explain the visible progress artifact
  - docs explicitly reject impatience-driven short waits for `codex_cli`

4) Verification and real-session evidence
- Deliverables:
  - fill outcomes in this plan
  - materialize and advance a maintainer session for this task using the new facade
- Commands:
  - `uv run --locked python tests/contract/check_loop_maintainer_session.py`
  - `uv run --locked python tests/contract/check_maintainer_loop_requirement.py`
  - `uv run --locked python tests/contract/check_loop_contract_docs.py`
  - `uv run --locked python tests/contract/check_loop_schema_validity.py`
  - `uv run --locked python tests/contract/check_loop_wave_execution_policy.py`
  - `uv run --locked python tests/contract/check_loop_python_sdk_contract_surface.py`
  - `uv run --locked python tests/run.py --profile core`
  - `uv run --locked python tests/run.py --profile nightly`
  - `lake build`
  - `git diff --check`
- Acceptance:
  - targeted and full verification pass
  - this task has a visible maintainer session/progress trail that clearly precedes closeout

## Testing plan (TDD)
- Extend `tests/contract/check_loop_maintainer_session.py` to require the facade and `MaintainerProgress.json`.
- Extend `tests/contract/check_maintainer_loop_requirement.py` to require explicit mention of the facade path and anti-impatience wording.
- Extend `tests/contract/check_loop_contract_docs.py` to require the new contract snippets.
- Keep tests repo-local and deterministic.

## Decision log
- 2026-03-06: treat “the agent knew the LOOP rules but did not naturally use the maintainer Python surface” as an API ergonomics problem, not just an operator mistake.
- 2026-03-06: add a progress sidecar because append-only journals are correct but too opaque for fast human inspection.
- 2026-03-06: make `codex_cli` impatience limits explicit in docs; slow high-thinking modes are normal, not tooling failure.

## Rollback plan
- Revert:
  - `tools/loop/maintainer.py`
  - `tools/loop/__init__.py`
  - `docs/agents/PLANS.md`
  - `docs/contracts/LOOP_GRAPH_CONTRACT.md`
  - `docs/contracts/LOOP_PYTHON_SDK_CONTRACT.md`
  - `docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md`
  - `tests/contract/check_loop_maintainer_session.py`
  - `tests/contract/check_maintainer_loop_requirement.py`
  - `tests/contract/check_loop_contract_docs.py`
- Re-run the targeted checks above to confirm rollback.

## Outcomes & retrospective (fill when done)
- Outcome: `PASSED`
- Final maintainer session:
  - run key: `1f187fcff663529b00c62c70e2774db668167108476dcc6c36b8d024bcfb9686`
  - summary: `artifacts/loop_runtime/by_key/1f187fcff663529b00c62c70e2774db668167108476dcc6c36b8d024bcfb9686/graph/GraphSummary.jsonl`
  - progress: `artifacts/loop_runtime/by_key/1f187fcff663529b00c62c70e2774db668167108476dcc6c36b8d024bcfb9686/graph/MaintainerProgress.json`
- Intermediate rounds:
  - round4: tooling-triage closeout preserved separately under `artifacts/reviews/20260306_maintainer_loop_facade_visibility_review_round4_triage.md`
  - round5: real review findings on `execplan_ref` overlap and failure-path progress accounting
  - round6: real review findings on canonical instruction-chain identity and frozen `graph_spec` identity
  - round7: real review finding on `execplan_ref`-induced instruction-chain derivation
  - round8: `REVIEW_RUN` with `No findings.`
- What changed:
  - maintainer work now has a visible Python facade path via `MaintainerLoopSession`
  - `MaintainerProgress.json` exposes live completed/pending/current nodes
  - `instruction_scope_refs` are canonicalized to the active chain instead of trusting caller extras
  - session identity now includes frozen `graph_spec` contents and the `execplan_ref`-induced instruction chain
  - `codex_cli` wait policy explicitly forbids impatience-driven two-minute aborts
