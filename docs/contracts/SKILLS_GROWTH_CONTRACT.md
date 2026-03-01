# SKILLS_GROWTH_CONTRACT v0 (Phase6-ready)

Purpose: define **when and how the skills/knowledge base is allowed to grow**, with explicit evidence, deterministic triggers, and regression methods.

Think of this as an engineering projection of:
- SRE “reduce toil” + postmortem action items (turn repeated friction into procedures/automation)
- AIOps log mining + clustering + KB retrieval (avoid re-triaging the same failure forever)

We do **not** optimize for “having many skills”.
We optimize for **less repeated failure, less wheel reinventing, and more net progress**.

---

## -1) Industry anchors (not vibes)

These are mature practices mapped into LeanAtlas’s evidence chain:

- **SRE: reduce toil** (repetitive, automatable human work).
  - In LeanAtlas: skill growth converts frequent friction into a reproducible procedure (KB/Skill) or an Automation.

- **Log template mining** (extract stable templates from noisy logs).
  - Mature method: Drain (He et al., 2017); common implementation: Drain3.
  - In LeanAtlas: normalize Lean diagnostics by removing variable noise (line/col, local names, tmp paths) to a stable template.

- **Log clustering + KB retrieval** (cluster similar failure sequences; reuse known fixes).
  - Mature method: LogCluster (Lin et al., 2016).
  - In LeanAtlas: cluster AttemptLog/RunReport event sequences to produce `kb_suggestions.json`, then land KB/Skill updates via Change Proposals.

Authoritative entry points (for maintainer audit):
- Google SRE book (toil/automation/postmortems)
- Drain (He et al., 2017) and Drain3
- LogCluster (Lin et al., 2016)

---

## 0) Terms

- **Skill**: an executable playbook for Codex (routing + procedure + checks + outputs).
- **KB entry**: stable fact/stable pattern (symptom → reproduction → fix → regression check). Typically shorter than a skill.
- **Skill growth**: add/update/merge/deprecate a Skill or KB entry.

Additional:
- **Pattern**: a reproducible failure/success template extracted from real artifacts.
- **Pattern signature**: a deterministic key that classifies a run into a Pattern.

---

## 1) Minimum quality bar (must be enforced by tests)

### 1.1 Every `SKILL.md` must include
- `## Use when` (≤3 bullets)
- `## Don't use when` (≤3 bullets)
- `## Outputs` (exact files/artifacts it writes)
- `## Must-run checks` (≥2 commands)

Goal: routing behaves like compiler branches, not like mystical prompt poetry.

### 1.2 Every KB entry must include
- **Trigger symptoms** (observable evidence from RunReport/AttemptLog)
- **Reproduction steps** (ideally 1–3 commands)
- **Fix steps** (ordered)
- **Regression check** (how to confirm it’s fixed)

---

## 2) When growth is allowed (deterministic triggers)

Growth proposals must have **input evidence**.
Any one trigger is sufficient to open a proposal.

### 2.1 Repeated friction (recommended: toil signal)

Any of:
- **Frequency threshold**: the same Pattern appears ≥ `F` times in the last `M` runs.
- **Cross-problem threshold**: the same Pattern appears in ≥ `P` distinct `problem_slug`s.

V0 defaults (configurable; must be pinned in repo config):
- `M = 20`
- `F = 3`
- `P = 2`

This maps SRE “repetitive and automatable” into deterministic thresholds.

### 2.2 High-leverage capability change (exception)

- A new external wheel/tool is integrated (MCP server, Lean package, external CLI) that changes workflow capability.
- Toolbox/Seeds structure changes (promotion/deprecation/migration) such that routing must be updated.

### 2.3 Systemic regression (nightly/pressure signal)

- A new version introduces a new failure Pattern observed in nightly/soak/scenario, and:
  - the failure has a clear Pattern signature
  - there is a deterministic reproduction

### 2.5 Human-forced deposition (explicit override)

- A maintainer may explicitly force selected pattern signatures via:
  - `tools/index/force_deposit.json` -> `skills[]`
- Forced deposition is allowed even below default frequency thresholds, but must still:
  - keep deterministic pattern signature matching
  - produce auditable `force_deposit` markers in suggestion output
  - pass the same downstream regen/eval checks

---

## 2.4 Pattern signature (V0 answer to: “skills grow based on what?”)

Skill/KB growth is only allowed based on **structured facts**, not on “feels”.

V0 Pattern signature (deterministic key) is composed of:

1) `triage_family`: `RunReport.triage.category.family`
2) `triage_code`: `RunReport.triage.category.code` (open codes allowed)
3) `failure_stage`: primary hotspot stage from `RunReport.hotspots[*].stage` (prefer build/verify)
4) `diag_templates[]`: a set of template-hash values derived from normalizing `RunReport.diagnostics[*].message`

`diag_templates[]` must be:
- deterministic (same input → same output)
- denoised (ignore line/col, tmp paths, random ids, local binder names when possible)

V0 recommended implementation:
- use a Drain-style template miner (e.g. Drain3) on diagnostic messages.
- do not use cluster ids as the truth source; use **template text hash** as the stable id.

This makes “what triggers growth” mechanically checkable.

---

## 3) Growth gate (must pass)

Any new/modified Skill or KB entry must satisfy:

1) **Evidence**: links to at least one real artifact (RunReport/AttemptLog/RetrievalTrace path or sha).
2) **Deterministic checks**: provide ≥2 commands that reproduce the key criterion in CI/local.
3) **No routing explosion**: Use when/Don’t use when must be crisp (reduces misrouting).
4) **No capability regression**: must run Phase6 agent eval (or a minimal subset) and prove:
   - at least one core metric improves (success_rate↑, attempts↓, triage_accuracy↑, net_progress↑, …)
   - key tasks do not exceed regression thresholds

---

## 4) Lifecycle (recommended)

- `draft/`: new patterns land as KB drafts first (lighter weight).
- `stable/`: only KB/skills that passed Phase6 eval become stable.
- `deprecated/`: replaced or harmful entries go here (must include migration guidance).

---

## 5) Automation pipeline (Phase6-aligned)

Automation is not “write prompts for humans”. It converts repeated work into a deterministic pipeline:

1) Aggregate AttemptLog / RunReport / RetrievalTrace (structured fields + diagnostics)
2) Template extraction: diagnostics → `diag_templates[]` (see §2.4)
3) Clustering:
   - same signature ⇒ same bucket
   - optional similarity clustering within a family/code to avoid over-fragmentation
4) Generate suggestions:
   - output `artifacts/skills_regen/kb_suggestions.json`
5) Open a Change Proposal:
   - minimal patch updating KB/skills (default: KB draft)
6) Phase6 eval:
   - prove the growth is real (≥1 metric improves and no threshold-exceeding regression)

Suggested entrypoint:
- `uv run --locked python tools/bench/mine_kb_suggestions.py --in <root> --out artifacts/skills_regen/kb_suggestions.json`
- Optional force-policy override:
  - `uv run --locked python tools/bench/mine_kb_suggestions.py --in <root> --out artifacts/skills_regen/kb_suggestions.json --force-file tools/index/force_deposit.json`

---

## 6) Coupling with tool growth

Tool growth (Promotion) and skill growth must be evaluated together:
- more tools increases routing complexity → skills must teach “reuse first”.
- more skills increases maintenance cost → eval must prove benefit.

---

## 7) TDD: skill growth must be testable

Every trigger must have regression tests.
V0 minimum test set (must be registered in `tests/manifest.json` and appear in `docs/testing/TEST_MATRIX.md`):

### 7.1 KB mining determinism
Given the same fixture run dirs (diagnostics with varying line/col/tmp paths), `mine_kb_suggestions.py` output must be identical (byte-identical canonical JSON).
Traversal order changes must not affect output (script must sort internally).

### 7.2 Template denoise effectiveness
Changes:
- line/col / tmp paths / random ids
Must not change:
- resulting `diag_template_hash`

### 7.3 Threshold correctness
- Pattern appears 2 times: no suggestion
- Pattern appears 3 times (or across 2 problems): suggestion must appear

### 7.4 Pressure/serialization scenarios
- interleaving/regression/pressure scenario AttemptLog fixtures must cluster correctly
- after `scripts/clean.sh`, there must be no contamination (git status clean)

Note: “Codex actually runs non-interactively” belongs to `AGENT_EVAL_CONTRACT`. Here we stabilize the deterministic growth core.

---

## 8) Local commands (trigger + test)

Mine KB suggestions (deterministic):

```bash
uv run --locked python tools/bench/collect_telemetry.py --repo-root . --out-root artifacts/telemetry --clean
uv run --locked python tools/bench/mine_kb_suggestions.py \
  --in artifacts/telemetry \
  --out artifacts/skills_regen/kb_suggestions.json
```

Run skills regen structural audit:

```bash
uv run --locked python tools/coordination/skills_regen.py --check
```

Run the registered weekly automation (deterministic + verify):

```bash
uv run --locked python tools/coordination/run_automation.py --id weekly_kb_suggestions --advisor-mode auto --verify
```

Run core test profile:

```bash
uv run --locked python tests/run.py --profile core
```
