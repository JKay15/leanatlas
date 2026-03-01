# Parallel Workstreams Protocol

> Purpose: allow multiple GPT Pro threads to advance LeanAtlas in parallel without context drift, identity loss, or non-mergeable outputs.

## 0) Base DocPack freeze

- Before parallel execution, freeze a **Base DocPack** (zip or git commit).
- Every thread must declare the base it uses (if needed, verify hash via `python tools/coordination/compute_docpack_hash.py`):
  - `DOC_PACK_VERSION`
  - `DOC_PACK_CONTENT_HASH` (from repo root `DOC_PACK_ID.json`)
- Any output without base declaration is non-mergeable.

## 1) Thread identity (workstream charter)

Each thread must bind to a workstream ID, for example:
- `WS-DEDUP`
- `WS-PROMOTION`
- `WS-GC`
- `WS-MCP`
- `WS-AUTOMATION`

The first message of a thread must include:
- Workstream ID
- Base DocPack ID (version + content hash)
- Scope (allowed directories)
- Deliverables
- Non-goals

Anti-forget rule: every later reply starts with a one-line header:
`[WS-xxx | Base vX.Y | one-line current goal]`

## 2) Ownership boundaries

During parallel work, each workstream may only edit owned scope.

For cross-scope changes (shared schema/contract/etc.), do not edit directly.
Create an RFC under `docs/coordination/rfcs/` and let integration decide.

## 3) Output shape (change proposal)

Each workstream output must be merge-ready and follow:
1. Summary
2. Rationale
3. Files changed
4. Tests
5. Risks / Rollback

Template: `docs/coordination/CHANGE_PROPOSAL_TEMPLATE.md`

## 4) Sync / rebase model

Recommended model: one integration thread.
- Each workstream submits change proposal/patch.
- Integration thread merges, resolves conflicts, updates `DECISIONS.md`, and bumps DocPack version.
- Publish new base (zip or commit).
- Other workstreams rebase to new base before continuing.

## 5) Hard no rules

- Editing system directories under OPERATOR context (`Toolbox`/`Incubator`/`tools`/`docs/contracts`, etc.)
- Silent external dependency upgrades (pin + PR + tests required)
- Editing shared schema/contract without version bump
- Changing gate criteria without test/benchmark evidence

## 6) Cross-cutting rule for skills/automation

- Skills/automation are cross-cutting and cannot be owned by one phase alone.
- Rule: the phase defining an interface owns its business semantics; Phase5 owns platform framework and deterministic regeneration.
- Mechanism: each top-level phase maintains `tools/capabilities/phase<N>.yaml` (see `docs/contracts/CAPABILITY_MANIFEST_CONTRACT.md`).
- If one skill/automation depends on multiple phases, use RFC to prevent overwrite races.
