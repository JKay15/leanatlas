# Phase3 PromotionGate — structural signals as auditable evidence (no fallback)

Owner: PHASE-3 / WS-PROMOTION

Status: active

Created: 2026-02-23

This ExecPlan is a living document. The sections **Progress**, **Surprises & Discoveries**, **Decision Log**, and **Outcomes & Retrospective** must be kept up to date as work proceeds.

## Purpose / Big Picture

PromotionGate is the “Seeds → Toolbox” safety check: it decides whether a candidate tool is ready to become a stable, reusable building block.

This plan hardens one missing piece: **structural signals** must be written into `PromotionReport.json` as **auditable evidence**.

In simple terms: when we say “this tool is light-weight / doesn’t leak imports / respects directory boundaries”, we must also attach proof showing exactly what we ran and what it output.

Non-negotiable rule: **no downgrade / no heuristic fallback**. If the required tooling can’t run, the gate fails and records evidence (stdout/stderr + artifact hashes).

## Progress

- [x] (2026-02-23) Updated PromotionGate contract to forbid skipping / heuristic fallback for structural gates.
- [x] (2026-02-23) Added Phase3 capability manifest entry for `promote.gate` with a runnable smoke command.
- [x] (2026-02-23) Added Phase3 skills (GC/Dedup/Promotion) with Codex-required frontmatter so Codex can route tasks.
- [x] (2026-02-23) Added/extended a smoke scenario to exercise GC + Dedup + Promotion entrypoints.
- [ ] Implement real structural signals (min imports / import graph / dir dependency / upstreamability) using pinned Lean tooling.
- [ ] Emit evidence bundles for each structural gate under `<out-root>/evidence/**` and include sha256 in `PromotionReport.json`.
- [ ] Add nightly gate cases that run the real tooling (requires Lean + mathlib).

## Surprises & Discoveries

- None yet (current code is scaffold + contracts). Add findings here once real tooling is wired.

## Decision Log

- Decision: Structural signals must not degrade into heuristic fallbacks. If tooling is missing or errors, the gate fails and records auditable evidence.
  Rationale: Structural signals are only valuable if they are reproducible and accountable.
  Date/Author: 2026-02-23 / PHASE-3

## Outcomes & Retrospective

- Pending (write after Milestone 2 lands and nightly is green).

## Context and Orientation

Key repo concepts (plain language):

- A **Seed** is a candidate tool under `LeanAtlas/Incubator/Seeds/**`.
- The **Toolbox** is the promoted, stable tool area under `LeanAtlas/Toolbox/**`.
- `PromotionPlan.json` is the input “what we want to promote”.
- `PromotionReport.json` is the output “what checks passed/failed and why”.

Relevant files (repo-relative paths):

- Tool entrypoint: `tools/promote/promote.py`
- Contracts:
  - `docs/contracts/PROMOTION_GATE_CONTRACT.md`
- Schemas:
  - `docs/schemas/PromotionPlan.schema.json`
  - `docs/schemas/PromotionReport.schema.json`
- Capability manifest (Phase3 interface table): `tools/capabilities/phase3.yaml`
- Skill used by Codex: `.agents/skills/leanatlas-promote/SKILL.md`

## Plan of Work

Milestone 1 (core, no Lean required): enforce the “shape” of reporting + routing.

- Make sure Codex can discover the Phase3 skills (frontmatter).
- Make sure automation can discover the Phase3 commands (capability manifest).
- Make sure there is at least one smoke scenario that runs PromotionGate entrypoint.

Milestone 2 (nightly, Lean required): implement real structural checks + evidence bundles.

- Run pinned Lean tooling to compute structural signals.
- Save raw outputs under `<out-root>/evidence/**`.
- Hash every artifact and record the hashes in `PromotionReport.json`.
- If the tooling fails, mark the gate failed and include stderr/stdout artifacts.

## Concrete Steps

Milestone 1 commands (should already work):

    cd <repo_root>
    python tests/contract/check_capability_manifests.py
    python tests/contract/check_phase3_e2e_scenarios.py

PromotionGate smoke run:

    cd <repo_root>
    uv run --locked python tools/promote/promote.py \
      --repo-root . \
      --plan tools/promote/fixtures/plan_minimal.json \
      --out-root .cache/leanatlas/promotion/gate \
      --mode MAINTAINER

Expected outputs:

- `.cache/leanatlas/promotion/gate/PromotionReport.json`
- `.cache/leanatlas/promotion/gate/PromotionReport.md`

Milestone 2 commands (requires Lean + mathlib + pinned tooling):

    cd <repo_root>
    uv run --locked python tools/promote/promote.py \
      --repo-root . \
      --plan <PromotionPlan.json> \
      --out-root .cache/leanatlas/promotion/gate \
      --mode MAINTAINER

Expected additional outputs:

- `.cache/leanatlas/promotion/gate/evidence/structural/<gate_id>/...`

## Validation and Acceptance

Milestone 1 acceptance (core):

- `python tests/contract/check_phase3_e2e_scenarios.py` prints `[phase3-scenarios] OK`.
- Phase3 smoke scenario includes a step that calls `tools/promote/promote.py`.
- `.agents/skills/leanatlas-promote/SKILL.md` contains YAML frontmatter with `name` and `description` (so Codex can route tasks).

Milestone 2 acceptance (nightly):

- `PromotionReport.json` contains structural gates, and for each structural gate:
  - If it passed: evidence shows the tool ran successfully and artifacts exist with matching sha256.
  - If it failed: evidence still exists (stdout/stderr artifacts + sha256) and explains the failure.
- No structural gate uses “skipped_reason” or a heuristic fallback path.

## Idempotence and Recovery

- PromotionGate must be safe to re-run: it writes outputs only under `<out-root>`.
- If a run fails halfway, you can delete `<out-root>` and re-run; no repo state should be corrupted.
- If a new dependency is introduced, it must be pinned and have a smoke command (per dependency contract).

## Artifacts and Notes

PromotionReport evidence bundle (minimum):

- `PromotionReport.json` must include, for each structural gate:
  - the exact command(s) run
  - return code
  - paths to saved artifacts
  - sha256 of each artifact

Decision reference:

- The “no heuristic fallback for structural signals” rule is logged in `docs/coordination/DECISIONS.md`.
