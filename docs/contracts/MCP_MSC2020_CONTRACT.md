# MCP_MSC2020_CONTRACT

This contract defines the minimum required capabilities for the **Domain Ontology MCP** in LeanAtlas.

MSC2020 is the first supported provider (`source_id=msc2020`), but the server interface must be **provider-agnostic**.

Important:
- The stable tool namespace is `domain/*`.
- MSC2020 is only one provider behind that namespace.
- For backward compatibility, `msc_*` aliases may exist (optional), but **new clients must prefer `domain/*`.**

---

## 0) Positioning

Domain Ontology MCP provides an auditable, extensible, versioned **domain coordinate system** used for:
- domain-driven retrieval pruning/expansion
- Seeds GC bucketing / bench bucketing
- directory boundary audits (Phase3 structural signals)
- validating human hints (domain labels in prompts)

Hard constraint: **read-only MCP**.
- Any update (MSC ingest, LOCAL overlay changes) must go through deterministic generation artifacts + PR audit.

---

## 1) Data layer: provider + overlay (required)

### 1.1 Providers
- `msc2020`: MSC2020 classification (recommended truth source: CSV ingest; see `docs/setup/external/msc2020.md`).
- `local`: LeanAtlas overlay (aliases/directory mappings/synonyms; rare new domains allowed only via maintainer gate).

All query results must include `source_id` (`msc2020` / `local`).

### 1.2 Bundle schema (required)
After ingesting a provider, generate a bundle JSON:

Required fields:
- `schema_version: string` (e.g. `leanatlas.domain_ontology.bundle.v1`)
- `data_version: string` (e.g. `msc2020@2020` or `msc2020@2020+rev1`)
- `source: { source_id, license, input_sha256, generated_at_utc }`
- `nodes: Node[]`

Node minimal fields:
- `id: string` (recommended `${source_id}:${code}`, e.g. `msc2020:03E20`)
- `code: string` (e.g. `03E20`, `14Qxx`, `03-01`)
- `text: string` (short title)
- `description: string` (may be empty)
- `level: number` (MSC levels, typically 2/3/5)
- `parent_id: string|null`

### 1.3 Overlay schema (required)
LOCAL overlay is also versioned JSON:

Required fields:
- `schema_version: string` (e.g. `leanatlas.domain_ontology.overlay.v1`)
- `data_version: string` (e.g. `local@2026-02-23`)
- `source_id: "local"`
- `generated_at_utc: string`
- `overrides: { [id: string]: OverlayPatch }`
- `new_nodes: Node[]` (optional; rare path)

OverlayPatch may only override/extend the following **extension fields** (it must not rewrite definitional MSC fields):
- `aliases: string[]`
- `keywords: string[]`
- `directory_roots: string[]` (domain → directory prune roots)
- `notes: string[]`

If overlay attempts to rewrite definitional fields (`code/text/description/parent_id/level`), the server must reject the overlay (load failure).

---

## 2) MCP tools (stable interface)

Naming constraint: tool names should follow MCP community conventions (e.g. SEP‑986 style); use `/` namespaces.

Required tools under `domain/*`:

### 2.1 `domain/info()`
Returns:
- `server_name`, `server_version`
- `schema_version`
- `data_bundle_version` (e.g. `msc2020:<sha2568>+local:<sha2568>`)
- `sources[]` (for each provider: `source_id/data_version/license/content_hash_sha256`)
- `counts` (node counts overall + by level)
- `warnings[]` (e.g. only mini bundle loaded)

### 2.2 `domain/validate_hint(hint)`
Input:
- `hint: string` (code-like or natural language)

Output:
- `normalized_hint`
- `is_code_like: bool`
- `candidates[]` (top‑k with `id/code/text/score`)
- `warnings[]`

Purpose: turn human hints into auditable candidates.

### 2.3 `domain/lookup(query, k=10, source_filter?, level_filter?, mode="hybrid")`
- Returns deterministic top‑k candidates (same input → same output order).

### 2.4 `domain/get(ids | codes)`
- Fetch nodes by `ids[]` (preferred) or `codes[]`.

### 2.5 `domain/path(id|code, include_self=true)`
- Returns ancestor chain from root to node (explainable routing).

### 2.6 `domain/children(id|code, depth=1)`
- Returns subtree (UI/debug/expansion).

### 2.7 `domain/expand(ids|codes, up_depth=1, down_depth=0, include_siblings=false)`
- Returns expansion set (DOMAIN_EXPAND layer).

### 2.8 `domain/roots(ids|codes)` (recommended)
- Returns suggested directory roots in the repo from overlay `directory_roots`.
- If no mapping exists, must return `missing=true` explicitly (never guess).

---

## 3) Downgrade strategy (required)

When Domain MCP is unavailable, times out, or data is missing:
- OPERATOR workflow must continue using deterministic fallback:
  - domain choice: downgrade to `UNKNOWN` or structural-only routing
  - retrieval prune: downgrade to no pruning (full local scan)

Any downgrade must be auditable:
- RetrievalTrace must record a `DOMAIN_ROUTE` step and set `fallback_used=true`.

---

## 4) TDD (required)
Must cover at least:

1) **Protocol black-box tests (core)**
- `initialize → tools/list → tools/call`
- stable error shapes for unknown method / invalid params / unknown tool

2) **Functional determinism tests (core)**
- fixed query returns stable top‑k set and order
- `domain/path` returns a valid ancestor chain
- `domain/expand` output set is stable under tie-break rules

3) **Overlay merge tests (core or nightly)**
- overlay adds aliases/roots that are queryable
- overlay attempting to rewrite definitional fields must be rejected

---

## 5) Backward compatibility (optional)

To support older clients, the server may provide `msc_*` aliases:
- `msc_info` ≈ `domain/info`
- `msc_lookup` ≈ `domain/lookup` with default `source_filter=["msc2020"]`
- others similarly

All new capability and docs must treat `domain/*` as the primary interface.
