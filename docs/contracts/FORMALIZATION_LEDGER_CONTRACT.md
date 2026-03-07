# FORMALIZATION_LEDGER_CONTRACT v0.1

This contract defines the canonical ledger for theorem/lemma extraction, proof linkage,
and Lean alignment artifacts used by formalization workflow gates.

## 1) Required top-level sections
A formalization ledger MUST contain these top-level sections:
- `ledger_meta`
- `review_workflow`
- `source_spans`
- `claims`
- `proofs`
- `external_results`
- `claim_proof_links`
- `formalization_bindings`
- `lean_reverse_links`
- `clause_atoms`
- `lean_anchors`
- `atom_mappings`
- `index`
- `audit`

Schema authority:
- `docs/schemas/FormalizationLedger.schema.json`

## 2) Identity and determinism rules
- Every entity id MUST be stable and deterministic for identical input text.
- `ledger_meta` MUST include source document identity and extraction provenance.
- Ledger JSON MUST be canonical (sorted keys, deterministic formatting).

## 3) Review-state model (entity-level)
The canonical review state enum is:
- `AUTO_EXTRACTED`
- `NEEDS_REVIEW`
- `HUMAN_CONFIRMED`
- `HUMAN_EDITED`
- `HUMAN_REJECTED`
- `LOCKED`

Required review fields for auditable entities:
- `state`
- `confidence`
- `uncertainty_score`
- `last_updated_utc`
- `reviewer`
- `note`

## 4) Claim/proof/link requirements
- Every claim must declare statement spans and in-paper proof status.
- Every proof must declare proof body spans and dependency references.
- Claim-proof links must carry confidence and evidence spans.
- Internal/external dependencies must be explicit; silent dependency omission is forbidden.

## 5) Lean mapping requirements
- `formalization_bindings` must track claim-level Lean target and dependency status.
- `clause_atoms` + `lean_anchors` + `atom_mappings` define clause/atom-to-Lean alignment.
- `lean_reverse_links` must support reverse lookup from Lean location back to clause/span ids.
- committed source enrichment may augment clause links with equation/citation evidence derived from LaTeX/PDF sources.
- committed reverse-link resync may rebuild `AUTO_FROM_ANNOTATION` reverse links from `LEAN_LINK` annotations after Lean source edits.
- committed review todo generation may prioritize clause/atom/anchor review work without mutating canonical ids.

## 5.1) Committed front-end helper surfaces
The canonical mainline formalization front-end helpers are:
- `tools/formalization/external_source_pack.py`
- `tools/formalization/source_enrichment.py`
- `tools/formalization/review_todo.py`
- `tools/formalization/resync_reverse_links.py`

These helpers are deterministic absorptions of validated experimental capabilities. They replace paper-local `.cache/**` entry scripts as the committed default path.

## 6) Compatibility bridge policy
During migration from experimental ledgers:
- adapters MAY read experimental v0.2/v0.3/v0.4 ledger formats,
- but all produced outputs MUST conform to `FormalizationLedger.schema.json`.

## 7) Mapping from experimental ledger v0.2 (field-level deltas)
v0.2 adapters MUST apply deterministic normalization before schema validation:

| Experimental v0.2 field/status | Product field/status | Rule |
|---|---|---|
| missing `clause_atoms` | `clause_atoms` | Materialize as `[]` (empty list) when unavailable. |
| missing `lean_anchors` | `lean_anchors` | Materialize as `[]` (empty list) when unavailable. |
| missing `atom_mappings` | `atom_mappings` | Materialize as `[]` (empty list) when unavailable. |
| `formalization_bindings[*].external_dependency_formalized` | `formalization_bindings[*].external_dependency_status` | Preserve status string as source of truth; treat legacy boolean as advisory compatibility metadata only. |

## 8) Mapping from experimental ledger v0.3 (field-level)
| Experimental v0.3 field | Product field | Rule |
|---|---|---|
| `ledger_meta` | `ledger_meta` | Preserve with compatibility metadata in `migration` section if needed. |
| `review_workflow` | `review_workflow` | Preserve workflow enum semantics unchanged. |
| `source_spans` | `source_spans` | Preserve span ids and provenance fields. |
| `claims` | `claims` | Preserve claim ids; enforce product review object shape. |
| `proofs` | `proofs` | Preserve proof ids and dependency refs. |
| `external_results` | `external_results` | Preserve unresolved/found status and retrieval evidence. |
| `claim_proof_links` | `claim_proof_links` | Preserve evidence spans + confidence. |
| `formalization_bindings` | `formalization_bindings` | Preserve dependency status and Lean target metadata. |
| `lean_reverse_links` | `lean_reverse_links` | Preserve reverse link ids and Lean refs. |
| `clause_atoms` | `clause_atoms` | Preserve atom ids/text and parent linkage. |
| `lean_anchors` | `lean_anchors` | Preserve anchor role/origin and Lean refs. |
| `atom_mappings` | `atom_mappings` | Preserve mapping confidence/relation/mismatch kinds. |
| `index` | `index` | Preserve by-kind/by-section lookup materialization. |
| `audit` | `audit` | Preserve coverage and ledger-level notes. |

## 9) Mapping from experimental ledger v0.4 (field-level deltas)
v0.4 adapters MUST preserve the same canonical sections as v0.3 and additionally:

| Experimental v0.4 field/status | Product field/status | Rule |
|---|---|---|
| additional experimental metadata fields | canonical sections above | Ignore unknown fields for schema conformance; record dropped keys in migration notes. |
| already materialized clause/anchor/atom mapping sections | `clause_atoms`/`lean_anchors`/`atom_mappings` | Preserve as-is; do not regenerate ids if present. |
| external dependency compatibility flags | `formalization_bindings[*].external_dependency_status` | Keep deterministic status mapping; do not infer completion from legacy booleans alone. |
