#!/usr/bin/env python3
"""Contract check: Python SDK surface is pinned and aligned with LOOP MCP semantics."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

try:
    import jsonschema
except Exception:
    print("[loop-sdk-surface] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
SDK_CONTRACT = ROOT / "docs" / "contracts" / "LOOP_PYTHON_SDK_CONTRACT.md"
MCP_CONTRACT = ROOT / "docs" / "contracts" / "LOOP_MCP_CONTRACT.md"
SDK_SCHEMA = ROOT / "docs" / "schemas" / "LoopSDKCallContract.schema.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop import (
    build_default_tiered_review_policy,
    build_pyramid_review_plan,
    build_review_orchestration_bundle,
    build_review_orchestration_graph,
    merge_partition_scope_paths,
    partition_review_scope_paths,
)
from tools.loop.sdk import loop, nested, parallel, resume, run, serial


def _fail(msg: str) -> int:
    print(f"[loop-sdk-surface][FAIL] {msg}", file=sys.stderr)
    return 2


def main() -> int:
    for p in (SDK_CONTRACT, MCP_CONTRACT, SDK_SCHEMA):
        if not p.exists():
            return _fail(f"missing required file: {p.relative_to(ROOT)}")

    sdk_doc = SDK_CONTRACT.read_text(encoding="utf-8")
    mcp_doc = MCP_CONTRACT.read_text(encoding="utf-8")
    schema = json.loads(SDK_SCHEMA.read_text(encoding="utf-8"))

    # SDK surface snippets
    for s in (
        "loop(...)",
        "serial(...)",
        "parallel(...)",
        "nested(...)",
        "run(...)",
        "resume(...)",
        "assurance_level",
        "agent_provider",
        "agent_profile",
        "review_history",
        "instruction_scope_refs",
        "resolved_invocation_signature",
        "build_default_review_policy(...)",
        "build_default_tiered_review_policy(...)",
        "`Budget Saver` is the committed default preset",
        "`FAST + low` is the default reviewer path",
        "`LOW_PLUS_MEDIUM` is the committed default reviewer tier policy",
        "`medium` is the standard bounded escalation tier",
        "`medium` is a bounded escalation for small-scope high-risk core logic",
        "`STRICT / xhigh` is exceptional",
        "partition_review_scope_paths(...)",
        "merge_partition_scope_paths(...)",
        "build_pyramid_review_plan(...)",
        "build_review_orchestration_graph(...)",
        "build_review_orchestration_bundle(...)",
        "follow-up partition set",
        "effective_scope_paths",
        "build_review_orchestration_graph(...)` compiles the schema-valid executable LOOP review graph payload only",
        "build_review_orchestration_bundle(...)` compiles the executable LOOP review graph plus deterministic sidecar routing metadata",
        "authoritative artifact for per-node reviewer-routing/audit metadata",
        "`graph_spec` may still persist coarse orchestration metadata",
        "authoritative source for per-node reviewer routing",
        "machine-readable `stage_manifest`",
        "containing one entry per executable orchestration node",
        "including non-review orchestration nodes such as `review_intake` and `finding_dedupe`",
        "join each entry back to `graph_spec.nodes` via its stable `node_id`",
        "`node_id`",
        "alias forms such as `foo.py` and `./foo.py` MUST be rejected as duplicates",
        "Reviewer-launching nodes MUST include `agent_profile`",
        "Non-review orchestration nodes that do not launch a reviewer MUST omit `agent_profile`",
        "Authoritative orchestration bundles MUST reject blank routing or scope metadata",
        "top-level `agent_provider_id`",
        "top-level `full_scope_fingerprint`",
        "top-level `effective_scope_fingerprint`",
        "any reviewer-launching stage `agent_profile`",
        "any partition `scope_fingerprint`",
        "`final_integrated_closeout.scope_fingerprint`",
        "MUST validate authoritative scope fingerprints against the live repository bytes under the supplied `repo_root`",
        "`strategy_plan.strategy_fingerprint` MUST match the canonical hash of the authoritative strategy-plan content that executable orchestration artifacts actually consume",
        "MUST cover the complete top-level provenance surface",
        "MUST NOT fork only because replayed plans mutate ignored metadata",
        "`strategy_plan.strategy_id` MUST remain `review.pyramid_partition.v1`",
        "machine-readable reconciliation contract for the `finding_dedupe` stage",
        "stable `resource_id` locator for the reconciliation state",
        "`artifact_schema_ref = docs/schemas/ReviewSupersessionReconciliation.schema.json`",
        "`authoritative_closeout_stage_id = final_integrated_closeout`",
        "`late_output_disposition_enum = APPLIED | NOOP_ALREADY_COVERED | REJECTED_WITH_RATIONALE`",
        "`reconcile_review_rounds(...)`",
        "`assert_review_reconciliation_ready(...)`",
        "`persist_review_reconciliation(...)`",
        "`ReviewSupersessionReconciliation.schema.json`",
        "authoritative finding ledger",
        "`final_integrated_closeout.review_tier` defaults to `MEDIUM`",
        "`final_integrated_closeout.agent_profile` MUST reuse the bounded medium escalation profile",
        "`LOW_ONLY` staged-review policies MAY set `final_integrated_closeout.review_tier = LOW`",
        "`strategy_plan.closeout_policy.review_tier_policy = LOW_ONLY`",
        "`final_integrated_closeout.agent_profile` MUST reuse `fast_partition_scan.agent_profile` exactly",
        "`strategy_plan.bounded_medium_profile` MUST be non-empty",
        "`final_integrated_closeout.agent_profile` MUST match `strategy_plan.bounded_medium_profile` exactly",
        "`strategy_plan.strict_exception_profile` MUST be non-empty in helper-authored/current strategies",
        "missing `strategy_plan.closeout_policy.review_tier_policy` is rejected on the default authoritative replay path",
        "`allow_historical_strategy_replay=True`",
        "Explicit historical replay mode MAY deterministically backfill `strategy_plan.strict_exception_profile` for supported legacy MEDIUM/STRICT-closeout plans that match one of the supported historical omit sets",
        "Explicit exception plans MAY set `final_integrated_closeout.review_tier = STRICT`",
        "`final_integrated_closeout.agent_profile` MUST reuse the explicit strict/xhigh exception profile",
        "`final_integrated_closeout.agent_profile` MUST match `strategy_plan.strict_exception_profile` exactly",
        "run-key-independent artifact path",
        "final integrated closeout sink MUST remain executable after post-dedupe advisory stages",
        "In explicit no-followup runs, `finding_dedupe` is still a hard gate",
        "When `deep_partition_followup.partition_ids=[]`, `effective_scope_paths` and `final_integrated_closeout.scope_paths` MUST match the frozen `fast_partition_scan.partition_ids` lineage exactly",
        "Fast partition scan nodes still gate `finding_dedupe`",
        "`fast_partition_scan.partition_ids` MUST preserve the canonical `strategy_plan.partitions` order exactly",
        "`strategy_plan.full_scope_paths` MUST preserve canonical repo-relative file order",
        "`strategy_plan.partitions` itself MUST preserve the canonical helper-derived partition order",
        "`strategy_plan.partitioning_policy` MUST preserve the helper-authored partitioning policy shape exactly",
        "`max_files_per_partition` MUST remain a positive integer policy field; string/bool lookalikes such as `\"2\"` or `true` are not authoritative replays",
        "`strategy_plan.partitions.*.scope_paths` MUST preserve canonical repo-relative file order within each partition",
        "`strategy_plan.stages` MUST preserve the canonical helper-authored stage order exactly",
        "helper-authored stage descriptor shape exactly",
        "`review_tier`, `finding_policy`, `selection_policy`, or `closeout_eligible`",
        "deep_partition_followup.partition_ids` MUST stay within the frozen `fast_partition_scan.partition_ids` subset",
        "unique `partition_id` values and non-empty `scope_paths`",
        "duplicate or unknown `stage_id` entries",
        "exact disjoint cover of `full_scope_paths`",
        "overlapping partition files",
        "repeated files inside a partition",
        "`strategy_plan.selected_partition_ids` MUST match `deep_partition_followup.partition_ids` exactly",
        "explicit `followup_partition_ids` are supplied to `build_pyramid_review_plan(...)`",
        "must not lexicographically reorder `part_100+` partition ids",
        "`strategy_plan.partitions[*].partition_id` numeric prefix MUST remain zero-padded",
        "`strategy_plan.partitions[*].partition_id` values MUST preserve the canonical helper-derived routing ids exactly",
        "`strategy_plan.partitions` MUST also match the helper-generated partition boundaries exactly for the declared `partitioning_policy`",
        "boundary-equivalent `max_files_per_partition` values are accepted when the frozen helper-generated partition boundaries remain identical",
        "MUST preserve the frozen `fast_partition_scan.partition_ids` order exactly",
        "deep_partition_followup.scope_paths` MUST stay within the selected partition lineage",
        "canonical selected partition lineage exactly",
        "deep_partition_followup.scope_paths`, `effective_scope_paths`, and `final_integrated_closeout.scope_paths` MUST match exactly",
        "exactness is sequence-sensitive, not set-sensitive",
        "`strategy_plan.effective_scope_source` MUST match `final_integrated_closeout.scope_source`",
        "MUST use a canonical helper-authored provenance label",
        "`FULL_SCOPE_AFTER_EMPTY_FOLLOWUP` is only valid when `deep_partition_followup.partition_ids=[]`",
        "the empty `effective_scope_paths=[]` input is shorthand for \"keep the canonical full fast-scan scope\"",
        "final_integrated_closeout.scope_paths` MUST also stay within that same selected partition lineage",
        "final_integrated_closeout.scope_paths` MUST match `effective_scope_paths` exactly",
        "final_integrated_closeout.scope_fingerprint` MUST match `effective_scope_fingerprint`",
        "`strategy_plan.closeout_policy` MUST preserve the helper-authored closeout policy shape exactly",
        "`strategy_plan.closeout_policy.intermediate_rounds_are_advisory` and `strategy_plan.closeout_policy.requires_integrated_scope_closeout` MUST remain `true`",
        "MUST NOT repeat the same repo file path more than once",
        "must also reject stale fingerprint metadata",
        "must reject stale `strategy_fingerprint` values",
        "narrows inside a selected multi-file partition",
        "partition_scope_paths",
        "partition_scope_fingerprint",
        "scope_fingerprint_basis",
        "REPO_FILE_BYTES",
        "PATH_SET",
        "PATH_SET` fingerprints MUST be order-insensitive",
        "composition_notes.fast_partition_node_ids",
        "`finding_dedupe` stage-manifest `scope_paths` / `scope_fingerprint` MUST freeze the actual `fast_partition_scan.partition_ids` lineage",
        "bookkeeping_pending_node_ids",
        "current_node_mode",
        "MaintainerCloseoutRef.json",
        "closeout_ref_ref",
        "`MaintainerSession.json`, `MaintainerProgress.json`, and `close_maintainer_session(...)` return summaries MUST expose `closeout_ref_ref`",
        "session_created_at_utc",
        "session_created_at_epoch_ns",
        "stale frozen inputs",
        "must reject stale execplan bytes before settled-state closeout",
        "refuse to let an older same-plan session overwrite a newer stable closeout ref",
        "legacy sessions missing `required_context_hash` or `instruction_chain_hash` must be rematerialized before closeout",
        "scope_observed_stamp",
        "mutate-and-restore scope drift after `ai_review_node`",
        "Maintainer `loop_closeout` remains a bookkeeping sink",
        "`reason_code=\"REVIEW_PASS\"` (or any other success-implying AI review reason) MUST be rejected as misleading evidence",
        "Recorded-graph replay that accepts legacy `GraphSummary.jsonl` rows missing `node_decisions[].executed` MUST rewrite the persisted summary",
        "preserve a journaled blocked `loop_closeout` as executed bookkeeping evidence",
        "Legacy blocked-closeout replay compatibility is not limited to the summary row",
        "`GraphSummary.jsonl`, `NodeResults.json`, and `graph/arbitration.jsonl`",
        "ordinary runnable work",
        "`serial(...)`, `parallel(...)`, and `nested(...)` are LOOP core composition helpers",
        "`OPERATOR`, `MAINTAINER`, and `worktree` policies are host/workflow adapters",
    ):
        if s not in sdk_doc:
            return _fail(f"LOOP_PYTHON_SDK_CONTRACT missing `{s}`")

    for helper_name, helper in (
        ("build_default_tiered_review_policy", build_default_tiered_review_policy),
        ("partition_review_scope_paths", partition_review_scope_paths),
        ("merge_partition_scope_paths", merge_partition_scope_paths),
        ("build_pyramid_review_plan", build_pyramid_review_plan),
        ("build_review_orchestration_graph", build_review_orchestration_graph),
        ("build_review_orchestration_bundle", build_review_orchestration_bundle),
    ):
        if not callable(helper):
            return _fail(f"tools.loop must export callable helper `{helper_name}`")

    node_a = {"node_id": "a"}
    node_b = {"node_id": "b"}
    if serial(node_a, node_b) != {"kind": "SERIAL", "nodes": [node_a, node_b]}:
        return _fail("serial(...) must stay pinned to the committed SDK composition shape")
    if parallel(node_a, node_b) != {"kind": "PARALLEL", "nodes": [node_a, node_b]}:
        return _fail("parallel(...) must stay pinned to the committed SDK composition shape")
    if nested(node_a, node_b) != {"kind": "NESTED", "parent": node_a, "child": node_b}:
        return _fail("nested(...) must stay pinned to the committed SDK composition shape")

    # MCP/SDK group alignment
    groups = [
        "loop/definitions",
        "loop/runs",
        "loop/graphs",
        "loop/components",
        "loop/resources",
        "loop/audit",
        "loop/providers",
        "loop/review-history",
    ]
    for g in groups:
        if g + "/*" not in mcp_doc:
            return _fail(f"LOOP_MCP_CONTRACT missing API group `{g}/*`")
        if g not in schema["properties"]["api_group"]["enum"]:
            return _fail(f"LoopSDKCallContract schema missing api_group `{g}`")

    required = set(schema.get("required") or [])
    for req in ("idempotency_key", "actor_identity", "request", "response"):
        if req not in required:
            return _fail(f"LoopSDKCallContract missing required field `{req}`")

    assurance_prop = (schema.get("properties") or {}).get("assurance_level") or {}
    assurance_enum = assurance_prop.get("enum") or []
    if sorted(assurance_enum) != ["FAST", "LIGHT", "STRICT"]:
        return _fail("LoopSDKCallContract assurance_level enum must be FAST/LIGHT/STRICT")

    # Validate error envelope behavior using schema itself.
    validator = jsonschema.Draft202012Validator(schema)

    ok_call = {
        "version": "1",
        "call_id": "sdk_call_001",
        "api_group": "loop/runs",
        "operation": "start",
        "idempotency_key": "idem-001",
        "actor_identity": "agent.codex",
        "request": {"run_key_hint": "abc"},
        "response": {"status": "OK", "at_utc": "2026-03-05T00:00:00Z", "result_ref": "artifacts/x.json"}
    }
    errs = list(validator.iter_errors(ok_call))
    if errs:
        return _fail(f"valid OK sdk call should pass schema; got {errs[0].message}")

    bad_error_call = {
        "version": "1",
        "call_id": "sdk_call_002",
        "api_group": "loop/runs",
        "operation": "start",
        "idempotency_key": "idem-002",
        "actor_identity": "agent.codex",
        "request": {},
        "response": {"status": "ERROR", "at_utc": "2026-03-05T00:00:00Z"}
    }
    errs = list(validator.iter_errors(bad_error_call))
    if not errs:
        return _fail("ERROR sdk call without `response.error` must fail schema")

    with tempfile.TemporaryDirectory(prefix="loop_sdk_surface_") as td:
        repo = Path(td)
        spec = loop(
            loop_id="loop.sdk.surface.v1",
            graph_mode="STATIC_USER_MODE",
            input_projection_hash="1" * 64,
            instruction_chain_hash="2" * 64,
            dependency_pin_set_id="pins.20260305",
            wave_id="loop.wave.sdk.surface.v1",
        )

        run_default = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-surface-run-default",
        )
        errs = list(validator.iter_errors(run_default))
        if errs:
            return _fail(f"default run() output must satisfy LoopSDKCallContract; got {errs[0].message}")
        default_spec = run_default.get("request", {}).get("spec", {})
        if default_spec.get("assurance_level") != "FAST":
            return _fail("default loop()/run() path must materialize FAST assurance_level")

        run_with_empty_history = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-surface-run-history-empty",
            agent_provider="codex_cli",
            agent_profile="profiles/codex_review.json",
            instruction_scope_refs=[str(ROOT / "AGENTS.md")],
            review_history=[],
        )
        errs = list(validator.iter_errors(run_with_empty_history))
        if errs:
            return _fail(f"run() with empty review_history must satisfy schema; got {errs[0].message}")
        if run_with_empty_history.get("resolved_invocation_signature") != "codex exec review":
            return _fail("run() with agent_provider=codex_cli must expose resolved_invocation_signature")
        review_history_ref = run_with_empty_history.get("review_history_ref")
        if not isinstance(review_history_ref, str) or not review_history_ref:
            return _fail("run() with review_history=[] must return non-empty review_history_ref")

        run_key_root = repo / ".cache" / "leanatlas" / "loop_runtime" / "by_key"
        run_key_candidates = sorted(p.name for p in run_key_root.iterdir() if p.is_dir())
        if not run_key_candidates:
            return _fail("run() should materialize at least one run_key directory")

        resume_default = resume(
            run_key=run_key_candidates[0],
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-surface-resume-default",
        )
        errs = list(validator.iter_errors(resume_default))
        if errs:
            return _fail(f"default resume() output must satisfy LoopSDKCallContract; got {errs[0].message}")

        run_with_history_a = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-surface-run-history-a",
            review_history=[{"iteration_index": 1, "findings": [{"finding_id": "finding.a", "flags": ["CONTRADICTION"]}]}],
        )
        run_with_history_b = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-surface-run-history-b",
            review_history=[{"iteration_index": 1, "findings": [{"finding_id": "finding.b", "flags": ["NITPICK"]}]}],
        )
        ref_b = run_with_history_b.get("review_history_ref")
        if not isinstance(ref_b, str) or not ref_b:
            return _fail("run() with review history must provide review_history_ref")
        history_txt = Path(ref_b).read_text(encoding="utf-8")
        if "finding.b" not in history_txt:
            return _fail("latest run() call must refresh persisted review_history content for same run_key")
        summary_ref_b = [
            p for p in run_with_history_b.get("response", {}).get("trace_refs", []) if p.endswith("review_history_consistency.json")
        ]
        if len(summary_ref_b) != 1:
            return _fail("run() with review history must include one review_history_consistency ref")
        summary_txt = Path(summary_ref_b[0]).read_text(encoding="utf-8")
        if "finding.a" in summary_txt:
            return _fail("review_history_consistency must reflect latest call input, not stale prior data")

    print("[loop-sdk-surface] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
