# Version roadmap (V0 → V1 → V2)

>Purpose: We do need "future-forward design" for V1/V2, but we also need to avoid premature complication.
> The core of this roadmap: **Use "observable data + exit threshold" to drive version upgrades** instead of time.

## Unified definition

- **V0**: Minimal closed loop + field-level contract + TDD gate. It can run through the real workflow, but does not pursue optimal performance.
- **V1**: Stability and scale. Systematically solve the top three pain points exposed by V0 in real use.
- **V2**: Intelligence and reconstruction assistance. Allows for the introduction of stronger analysis/advice capabilities (including Codex Advisor), but must remain auditable.

## When to enter V1 from V0 (hard exit threshold)

V1 design/implementation is only allowed to start if the following conditions are met:

1) **real data is enough**:
- At least 20 real small-loop runs (including SUCCESS and TRIAGED), with complete AttemptLog/RunReport.
- Cover at least 3 domains (MSC/LOCAL).

2) **Loop closure has occurred**:
- Complete the process and pass the gate through Promotion (Incubator → Toolbox) at least 3 times.
- At least 2 times of GC propose+apply to complete the process (even if V0 only changes metadata status).

3) **Test stable**:
- The core test is all green.
- Pass nightly at least 7 times in a row (same environment).

4) **External dependency governance is mature**:
- Experienced at least 1 "external dependency upgrade" (pin + installation document + smoke) without causing a system crash.

> Reason: Without this data, the optimization of V1 will become a "slap on the head".

## Subsystem upgrade route

### DedupGate

- **V0 (current)**
- Goal: First solve the most classic and dangerous duplication: `instance` duplication (can cause confusion in typeclass search).
- Method: Prioritize the reuse of mature duplicate-declaration linter/canonicalization ideas in the community; output DedupReport; serve as a strong front-end for Promotion.

- **V1 (Stabilized)**
- Extension to: more kind (theorem/def) but still with "low false positives" as the primary goal.
- Introduced: allowlist/denylist, module level "legal duplication" (compat alias / re-export) determination.
- Introduced: subsumption-lite (very conservative subsumption checking, only performed when it can be automatically proven).

- **V2 (intelligent)**
- Stronger equivalence/implication determination (optional invocation of stronger proof search/LeanDojo style tool), but must:
- Output reproducible evidence (proof object / script / trace)
- Not enabled by default, needs to be explicitly switched on

### PromotionGate

- **V0 (current)**
- Target: Access control + rollback patch + PromotionReport.
- Emphasis: Structure signals for Rule-of-Three, deprecated alias/compat, min_imports/directoryDependency/upstreamableDecl.

- **V1 (Scaling)**
- Use import-graph as a hard dependency: use it for "placement suggestions" and "reachability/influence" evaluation.
- Introduce more systematic migration: deprecation migration table, batch rewrite suggestions (still subject to PR review).

- **V2 (Reconstruction Assist)**
- Advisor provides a "candidate set of refactoring solutions" (multiple solutions + risk assessment + expected diff range) and can automatically generate a PR draft.

### GCGate

- **V0 (current)**
- Goal: Recycle Seeds according to domain session logical clock (metadata isolation first: active/quarantined/archived).
- Output: GCPlan + GCReport; rollable.

- **V1 (closer to traditional GC)**
- Introduced reachability: Calculate reachable Seeds from Roots (Toolbox imports/Active Problems/External bundles).
- Introduce grace period: Separate "recycling decision" from "physical relocation/deletion".

- **V2 (Online/Incremental)**
- Incremental maintenance reachability (avoiding full scan).
- A more fine-grained "hotness/value" model (still mainly deterministic, LLM only explains).

## Version upgrade reflected in document package

- Each gate document (ExecPlan + Contract + Schema + Tests) is explicitly layered with `V0/V1/V2`.
- V1/V2 fields can be occupied in advance, but they must:
- Default values ​​are clear
- Does not affect the determinism of V0
- There are "not implemented/not enabled" mechanical criteria
