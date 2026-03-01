# GPT Pro Full Rebuild Prompt (Copy/Paste Ready)

You are GPT Pro. Provide an implementable system refactor design + executable migration plan for LeanAtlas with these goals:

1. Testing is auditable, reproducible, and extensible.
2. Documentation lets Codex hit when needed and stay out of context when not needed.
3. Real research tasks are verifiable and can deposit tools and skills.

---

## Inputs (must read first)

0. `/Users/xiongjiangkai/Downloads/leanatlas_codex_scaffold_v0_50_1/leanatlas_clean_en_only_v0_50_13.zip`
1. `/Users/xiongjiangkai/Desktop/leanatlas_feedback_journal_v3.md`
2. `/Users/xiongjiangkai/Downloads/leanatlas_codex_scaffold_v0_50_1/tests/manifest.json`
3. `/Users/xiongjiangkai/Downloads/leanatlas_codex_scaffold_v0_50_1/AGENTS.md`
4. `/Users/xiongjiangkai/Downloads/leanatlas_codex_scaffold_v0_50_1/docs/review/file_mapping_template.md`
5. `/Users/xiongjiangkai/Downloads/leanatlas_codex_scaffold_v0_50_1/docs/review/content_review_template.md`
6. `/Users/xiongjiangkai/Downloads/leanatlas_codex_scaffold_v0_50_1/docs/review/test_coverage_matrix_template.md`

---

## Hard constraints (must satisfy)

1. **All executable tests must be registered in `tests/manifest.json`**, not only wrappers.
2. **Lean dependencies and problem workspaces must share across entrypoints**:
   - `tools/agent_eval/run_pack.py`
   - `tools/agent_eval/run_scenario.py`
   - `tests/e2e/run_cases.py`
   - `tests/e2e/run_scenarios.py`
   - `tests/stress/soak.py`
   Shared strategy is mandatory. Per-run isolated full `.lake/packages` is forbidden.
3. `resume` and `fresh` semantics must be consistent. Historical workspace contamination must not cause false failures.
4. Documentation must be trigger-minimized: discoverable when needed, low context footprint otherwise.
5. Refactor must preserve validated success paths; no regression on proven green routes.

---

## Required output as "0 + 4 layers"

### Layer 0: Evidence layer (first)

1. Extract index from v3: `ISSUE_ID -> evidence path -> root cause -> fix status`.
2. Mark status as `fixed+verified / fixed+unverified / not fixed`.

### Layer 1: File layer

1. Output complete file mapping table (using template columns).
2. For each `delete/add/move/split/merge`, provide necessity and risk.
3. List high-risk changes and rollback points.

### Layer 2: Content layer

1. Review diffs item-by-item on overlapping files.
2. Bind each diff to ISSUE_ID and state whether it covers v1/v2/v3.
3. Provide verifiable evidence for "better or not".

### Layer 3: Testing layer

1. Output diff between "manifest registered universe" and "executable asset universe".
2. Provide backfill rules and automatic gate design.
3. Provide test execution order and pass criteria.

### Layer 4: Real-usage layer

1. Map instructor task list to executable use cases.
2. For each use case, define validation criteria:
   - validation success
   - tool deposition success
   - skills deposition success
   - written to correct docs with on-demand triggerability

---

## Mandatory new gates (implementable design)

1. `tests/contract/check_manifest_completeness.py`
   - unregistered executable assets -> FAIL
   - manifest points to missing asset -> FAIL
   - wrapper expansion set mismatch -> FAIL

2. `tests/contract/check_shared_cache_policy.py`
   - inconsistent shared policy across runners -> FAIL
   - per-run isolated full `.lake/packages` found -> FAIL
   - resume/fresh cache policy drift found -> FAIL

---

## Output format (strict)

1. `Executive Summary` (conclusions only)
2. `Layered Results (0+4)`
3. `Minimal Change Set (by file)`
4. `Migration Plan (phased + rollback)`
5. `New Gate Rules`
6. `Acceptance Criteria (quantified)`
7. `Open Risks and Follow-ups`

---

## Additional requirements

1. Separate `must change` and `optional change` explicitly; do not mix.
2. No vague advice; every item must land on file/rule/script.
3. If any suggestion cannot be locally verified, mark it as `pending local verification`.
