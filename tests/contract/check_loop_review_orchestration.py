#!/usr/bin/env python3
"""Contract: staged review strategies compile into executable LOOP review-orchestration graphs."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

try:
    import jsonschema
except Exception:
    print("[loop-review-orchestration] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.loop.review_orchestration as review_orchestration  # noqa: E402

from tools.loop import (  # noqa: E402
    EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
    LoopGraphRuntime,
    build_pyramid_review_plan,
    build_review_orchestration_bundle,
    build_review_orchestration_graph,
    compute_review_scope_fingerprint,
    partition_review_scope_paths,
)

SCHEMA = json.loads((ROOT / "docs" / "schemas" / "LoopGraphSpec.schema.json").read_text(encoding="utf-8"))
GRAPH_VALIDATOR = jsonschema.Draft202012Validator(
    SCHEMA,
    format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _canonical_hash(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _canonical_partitioning_policy_for_fingerprint(plan: dict) -> dict:
    policy = dict(plan.get("partitioning_policy") or {})
    if not policy or str(policy.get("group_by") or "") != "TOP_LEVEL_SCOPE_PREFIX":
        return policy
    full_scope_paths = [str(path) for path in plan.get("full_scope_paths") or []]
    partitions = [dict(part) for part in plan.get("partitions") or []]
    if not full_scope_paths or not partitions:
        return policy
    expected_chunks = [[str(path) for path in part.get("scope_paths") or []] for part in partitions]
    grouped_scope_paths: dict[str, list[str]] = {}
    for rel in full_scope_paths:
        grouped_scope_paths.setdefault(str(rel).split("/", 1)[0], []).append(str(rel))
    for max_files_per_partition in range(1, len(full_scope_paths) + 1):
        candidate_chunks: list[list[str]] = []
        for group in sorted(grouped_scope_paths):
            files = grouped_scope_paths[group]
            for start in range(0, len(files), max_files_per_partition):
                candidate_chunks.append(files[start : start + max_files_per_partition])
        if candidate_chunks == expected_chunks:
            return {
                "group_by": "TOP_LEVEL_SCOPE_PREFIX",
                "max_files_per_partition": max_files_per_partition,
            }
    return policy


def _strategy_fingerprint_payload(plan: dict) -> dict:
    partition_keys = ("partition_id", "scope_paths", "scope_fingerprint")
    stage_keys = {
        "fast_partition_scan": ("stage_id", "agent_profile", "prompt_protocol_id", "partition_ids"),
        "deep_partition_followup": (
            "stage_id",
            "agent_profile",
            "partition_ids",
            "scope_paths",
            "scope_fingerprint",
            "prompt_protocol_id",
        ),
        "final_integrated_closeout": (
            "stage_id",
            "review_tier",
            "agent_profile",
            "scope_paths",
            "scope_fingerprint",
            "scope_source",
            "prompt_protocol_id",
        ),
    }
    authoritative_stages: list[dict] = []
    for stage in plan.get("stages") or []:
        stage_id = str(stage.get("stage_id") or "")
        keys = stage_keys.get(stage_id)
        if keys is None:
            authoritative_stages.append(dict(stage))
            continue
        if stage_id == "deep_partition_followup" and not [str(pid) for pid in stage.get("partition_ids") or []]:
            keys = (
                "stage_id",
                "partition_ids",
                "scope_paths",
                "prompt_protocol_id",
            )
        authoritative_stages.append({key: stage.get(key) for key in keys})
    return {
        "version": str(plan.get("version") or ""),
        "strategy_id": str(plan.get("strategy_id") or ""),
        "agent_provider_id": str(plan.get("agent_provider_id") or ""),
        "bounded_medium_profile": str(plan.get("bounded_medium_profile") or ""),
        "strict_exception_profile": str(plan.get("strict_exception_profile") or ""),
        "partitioning_policy": _canonical_partitioning_policy_for_fingerprint(plan),
        "full_scope_paths": [str(path) for path in plan.get("full_scope_paths") or []],
        "full_scope_fingerprint": str(plan.get("full_scope_fingerprint") or ""),
        "partitions": [
            {key: part.get(key) for key in partition_keys}
            for part in plan.get("partitions") or []
        ],
        "selected_partition_ids": [str(pid) for pid in plan.get("selected_partition_ids") or []],
        "effective_scope_paths": [str(path) for path in plan.get("effective_scope_paths") or []],
        "effective_scope_fingerprint": str(plan.get("effective_scope_fingerprint") or ""),
        "effective_scope_source": str(plan.get("effective_scope_source") or ""),
        "stages": authoritative_stages,
        "closeout_policy": dict(plan.get("closeout_policy") or {}),
    }


def _legacy_strategy_fingerprint_payload(plan: dict, *, omitted_stage_ids: set[str]) -> dict:
    payload = _strategy_fingerprint_payload(plan)
    for stage in payload.get("stages") or []:
        stage_id = str(stage.get("stage_id") or "")
        if stage_id in omitted_stage_ids:
            stage.pop("prompt_protocol_id", None)
    return payload


def _legacy_uncanonicalized_strategy_fingerprint_payload(plan: dict) -> dict:
    payload = _strategy_fingerprint_payload(plan)
    payload["partitioning_policy"] = dict(plan.get("partitioning_policy") or {})
    return payload


def _legacy_pre_tier_provenance_strategy_fingerprint_payload(plan: dict) -> dict:
    payload = _strategy_fingerprint_payload(plan)
    payload["stages"] = [
        {
            key: value
            for key, value in stage.items()
            if not (
                str(stage.get("stage_id") or "") == "final_integrated_closeout"
                and key == "review_tier"
            )
        }
        for stage in payload.get("stages") or []
    ]
    return payload


def _write(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {path.name}\n", encoding="utf-8")


def _validate_graph(graph: dict) -> None:
    errs = sorted(GRAPH_VALIDATOR.iter_errors(graph), key=lambda e: list(e.absolute_path))
    if errs:
        joined = "; ".join(f"/{'/'.join(str(x) for x in e.absolute_path)}: {e.message}" for e in errs)
        raise AssertionError(f"graph_spec must validate against LoopGraphSpec.schema.json: {joined}")


def _node_ids(graph: dict) -> list[str]:
    return [str(node["node_id"]) for node in graph["nodes"]]


def _edges(graph: dict) -> set[tuple[str, str, str]]:
    return {(str(edge["from"]), str(edge["to"]), str(edge["kind"])) for edge in graph["edges"]}


def _resource_class_map(bundle: dict) -> dict[str, str]:
    return {str(item["resource_id"]): str(item["resource_class"]) for item in bundle.get("resource_manifest") or []}


def _stage_manifest_map(bundle: dict) -> dict[str, dict]:
    return {str(item["node_id"]): dict(item) for item in bundle.get("stage_manifest") or []}


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _pass_executor(node: dict) -> dict:
    return {"state": "PASSED", "reason_code": f"NODE_{node['node_id']}_PASS"}


def _strategy(
    repo: Path,
    *,
    followup_partition_ids: list[str],
    effective_scope_paths: list[str] | None = None,
    **overrides: object,
) -> dict:
    kwargs: dict[str, object] = {
        "repo_root": repo,
        "scope_paths": [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ],
        "fast_profile": "gpt-5.4-low",
        "deep_profile": "gpt-5.4-medium",
        "strict_profile": "gpt-5.4-xhigh",
        "max_files_per_partition": 2,
        "followup_partition_ids": followup_partition_ids,
    }
    if effective_scope_paths is not None:
        kwargs["effective_scope_paths"] = effective_scope_paths
    kwargs.update(overrides)
    return build_pyramid_review_plan(**kwargs)


def _assert_compiled_graph_shape() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_shape_") as td:
        repo = Path(td)
        for rel in (
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ):
            _write(repo / rel)

        strategy = _strategy(
            repo,
            followup_partition_ids=["part_02_tests", "part_03_tools_01"],
        )
        bundle = build_review_orchestration_bundle(
                repo_root=repo,
            review_id="review_orchestration_demo",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )
        graph = bundle["graph_spec"]
        _validate_graph(graph)
        for forbidden in ("preset_id", "resource_manifest", "composition_notes", "stage_manifest", "reconciliation_contract"):
            _assert(forbidden not in graph, f"graph_spec must not contain sidecar field `{forbidden}`")

        node_ids = _node_ids(graph)
        _assert(node_ids[0] == "review_intake", "review_intake must be the first orchestration node")
        _assert("finding_dedupe" in node_ids, "graph must contain finding_dedupe")
        _assert("final_integrated_closeout" in node_ids, "graph must contain final_integrated_closeout")
        _assert("review_finalize" not in node_ids, "final integrated closeout should now be the sink stage")

        fast_nodes = sorted(node for node in node_ids if node.startswith("fast_partition_scan__"))
        deep_nodes = sorted(node for node in node_ids if node.startswith("deep_partition_followup__"))
        _assert(len(fast_nodes) == 4, "expected one fast partition node per deterministic partition")
        _assert(
            deep_nodes == [
                "deep_partition_followup__part_02_tests",
                "deep_partition_followup__part_03_tools_01",
            ],
            "deep follow-up nodes must reflect the selected followup partitions",
        )

        edges = _edges(graph)
        for fast_node in fast_nodes:
            _assert(("review_intake", fast_node, "SERIAL") in edges, f"missing intake edge for {fast_node}")
            _assert((fast_node, "finding_dedupe", "BARRIER") in edges, f"missing dedupe edge for {fast_node}")
        for deep_node in deep_nodes:
            _assert(("finding_dedupe", deep_node, "NESTED") in edges, f"missing nested edge for {deep_node}")
            _assert(
                (deep_node, "final_integrated_closeout", "BARRIER") in edges,
                f"missing closeout barrier edge for {deep_node}",
            )
        _assert(
            not [edge for edge in edges if edge[0] == "final_integrated_closeout"],
            "final integrated closeout must be the sink node for authoritative closeout",
        )
        final_node = next(node for node in graph["nodes"] if node["node_id"] == "final_integrated_closeout")
        _assert(
            final_node.get("allow_terminal_predecessors") is True,
            "final integrated closeout must tolerate terminal advisory predecessors",
        )

        resources = _resource_class_map(bundle)
        _assert(resources["review.strategy_plan"] == "IMMUTABLE", "strategy plan should be immutable once frozen")
        _assert(resources["review.partition_findings"] == "APPEND_ONLY", "partition findings should be append-only")
        _assert(
            resources["review.reconciliation_state"] == "MUTABLE_CONTROLLED",
            "reconciliation state must be controlled",
        )

        notes = bundle["composition_notes"]
        _assert(notes["strategy_id"] == "review.pyramid_partition.v1", "bundle must carry strategy identity")
        _assert(
            notes["authoritative_closeout_stage_id"] == "final_integrated_closeout",
            "bundle must mark the final integrated stage as authoritative closeout",
        )
        _assert(
            notes["selected_partition_ids"] == ["part_02_tests", "part_03_tools_01"],
            "bundle must expose the selected followup partitions",
        )
        stage_manifest = _stage_manifest_map(bundle)
        _assert(
            set(stage_manifest) == {
                "review_intake",
                *fast_nodes,
                "finding_dedupe",
                *deep_nodes,
                "final_integrated_closeout",
            },
            "stage manifest must cover every executable review-orchestration node",
        )
        _assert(
            stage_manifest["fast_partition_scan__part_01_docs"]["node_id"] == "fast_partition_scan__part_01_docs",
            "stage manifest entries must preserve stable node_id routing keys",
        )
        _assert(
            stage_manifest["fast_partition_scan__part_01_docs"]["agent_profile"] == "gpt-5.4-low",
            "reviewer-launching stage manifest entries must preserve their concrete agent_profile",
        )
        _assert(
            stage_manifest["fast_partition_scan__part_01_docs"]["prompt_protocol_id"]
            == EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
            "fast reviewer-launching stage manifest entries must preserve prompt_protocol_id",
        )
        _assert(
            "agent_profile" not in stage_manifest["review_intake"],
            "non-review orchestration nodes must omit null agent_profile placeholders",
        )
        _assert(
            "prompt_protocol_id" not in stage_manifest["review_intake"],
            "non-review orchestration nodes must omit prompt_protocol_id placeholders",
        )
        _assert(
            stage_manifest["finding_dedupe"]["node_id"] == "finding_dedupe",
            "stage manifest must preserve node_id for non-review reconciliation nodes too",
        )
        _assert(
            "agent_profile" not in stage_manifest["finding_dedupe"],
            "finding_dedupe must omit agent_profile because it does not launch a reviewer",
        )
        _assert(
            "prompt_protocol_id" not in stage_manifest["finding_dedupe"],
            "finding_dedupe must omit prompt_protocol_id because it does not launch a reviewer",
        )
        _assert(
            stage_manifest["fast_partition_scan__part_01_docs"]["scope_paths"]
            == ["docs/contracts/alpha.md", "docs/contracts/beta.md"],
            "fast stage manifest must preserve deterministic partition scope",
        )
        _assert(
            stage_manifest["deep_partition_followup__part_02_tests"]["agent_profile"] == "gpt-5.4-medium",
            "deep stage manifest must preserve the narrowed follow-up profile",
        )
        _assert(
            stage_manifest["deep_partition_followup__part_02_tests"]["partition_id"] == "part_02_tests",
            "deep stage manifest must preserve per-partition routing identity",
        )
        _assert(
            stage_manifest["deep_partition_followup__part_02_tests"]["prompt_protocol_id"]
            == EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
            "deep stage manifest must preserve prompt_protocol_id",
        )
        _assert(
            stage_manifest["deep_partition_followup__part_02_tests"]["scope_fingerprint_basis"] == "REPO_FILE_BYTES",
            "deep stage manifest must record repository-byte fingerprint semantics when a full partition is replayed unchanged",
        )
        _assert(
            stage_manifest["final_integrated_closeout"]["allow_terminal_predecessors"] is True,
            "final closeout manifest must record sink execution after terminal advisory stages",
        )
        _assert(
            stage_manifest["final_integrated_closeout"]["review_tier"] == "MEDIUM",
            "final integrated closeout manifest must align with the default medium closeout tier",
        )
        _assert(
            stage_manifest["final_integrated_closeout"]["prompt_protocol_id"]
            == EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
            "final integrated closeout manifest must preserve prompt_protocol_id",
        )
        legacy_strategy = json.loads(json.dumps(strategy))
        omitted_stage_ids = {
            str(stage.get("stage_id") or "")
            for stage in legacy_strategy.get("stages") or []
        }
        for stage in legacy_strategy.get("stages") or []:
            stage.pop("prompt_protocol_id", None)
        legacy_strategy["strategy_fingerprint"] = _canonical_hash(
            _legacy_strategy_fingerprint_payload(legacy_strategy, omitted_stage_ids=omitted_stage_ids)
        )
        legacy_bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_legacy_prompt_protocol_replay",
            strategy_plan=legacy_strategy,
            max_parallel_branches=3,
            allow_legacy_prompt_protocol_backfill=True,
        )
        legacy_stage_manifest = _stage_manifest_map(legacy_bundle)
        _assert(
            legacy_stage_manifest["fast_partition_scan__part_01_docs"]["prompt_protocol_id"]
            == EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
            "legacy replay plans that predate prompt_protocol_id must backfill the canonical exhaustive protocol",
        )
        _assert(
            legacy_bundle["composition_notes"]["strategy_fingerprint"] == _canonical_hash(_strategy_fingerprint_payload(strategy)),
            "legacy replay plans should be upgraded to the canonical prompt-aware strategy fingerprint after validation",
        )
        downgraded_strategy = json.loads(json.dumps(strategy))
        for stage in downgraded_strategy.get("stages") or []:
            if str(stage.get("stage_id") or "") in {
                "fast_partition_scan",
                "deep_partition_followup",
                "final_integrated_closeout",
            }:
                stage["prompt_protocol_id"] = "review.prompt.baseline.v1"
        downgraded_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(downgraded_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_baseline_prompt_downgrade",
                strategy_plan=downgraded_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "review.prompt.exhaustive.v1" in str(exc),
                "authoritative replay plans should reject downgraded baseline prompt protocols",
            )
        else:
            raise AssertionError(
                "authoritative replay plans must reject reviewer-launching stages downgraded to the baseline prompt protocol"
            )
        missing_protocol_strategy = json.loads(json.dumps(strategy))
        for stage in missing_protocol_strategy.get("stages") or []:
            if str(stage.get("stage_id") or "") in {
                "fast_partition_scan",
                "deep_partition_followup",
                "final_integrated_closeout",
            }:
                stage.pop("prompt_protocol_id", None)
        missing_protocol_strategy["strategy_fingerprint"] = _canonical_hash(
            _legacy_strategy_fingerprint_payload(
                missing_protocol_strategy,
                omitted_stage_ids={"fast_partition_scan", "deep_partition_followup", "final_integrated_closeout"},
            )
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_missing_prompt_protocol_current",
                strategy_plan=missing_protocol_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "allow_legacy_prompt_protocol_backfill=True" in str(exc),
                "current replay plans missing prompt_protocol_id should require explicit legacy backfill opt-in",
            )
        else:
            raise AssertionError(
                "authoritative replay plans must reject missing prompt_protocol_id by default"
            )
        reconciliation = dict(bundle.get("reconciliation_contract") or {})
        _assert(
            reconciliation.get("resource_id") == "review.reconciliation_state",
            "bundle must expose a stable reconciliation resource locator",
        )
        _assert(
            reconciliation.get("producer_node_id") == "finding_dedupe",
            "bundle must expose finding_dedupe as the reconciliation producer",
        )
        _assert(
            reconciliation.get("artifact_schema_ref") == "docs/schemas/ReviewSupersessionReconciliation.schema.json",
            "bundle must pin the authoritative reconciliation artifact schema",
        )
        _assert(
            reconciliation.get("authoritative_closeout_stage_id") == "final_integrated_closeout",
            "bundle must pin the authoritative closeout stage for later reconciliation runtime consumers",
        )
        _assert(
            reconciliation.get("finding_disposition_enum") == ["CONFIRMED", "DISMISSED", "SUPERSEDED"],
            "bundle must expose deterministic reconciliation dispositions",
        )
        _assert(
            reconciliation.get("late_output_disposition_enum")
            == ["APPLIED", "NOOP_ALREADY_COVERED", "REJECTED_WITH_RATIONALE"],
            "bundle must expose deterministic late-output ingestion dispositions",
        )
        _assert(
            reconciliation.get("required_fields")
            == [
                "finding_key",
                "finding_group_key",
                "scope_lineage_key",
                "source_stage_id",
                "source_partition_id",
                "disposition",
                "selected_partition_ids",
                "effective_scope_paths",
                "effective_scope_fingerprint",
            ],
            "bundle must require machine-readable finding-dedupe lineage",
        )

        strict_strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=[
                "docs/contracts/alpha.md",
                "docs/contracts/beta.md",
                "tests/contract/test_alpha.py",
                "tools/loop/review_a.py",
                "tools/loop/review_b.py",
                "tools/loop/review_c.py",
            ],
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            final_closeout_tier="STRICT",
            max_files_per_partition=2,
            followup_partition_ids=["part_02_tests", "part_03_tools_01"],
        )
        strict_bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_strict_exception",
            strategy_plan=strict_strategy,
            max_parallel_branches=3,
        )
        _assert(
            strict_strategy["strict_exception_profile"] == "gpt-5.4-xhigh",
            "strict exception plans must persist the dedicated strict exception profile in the strategy payload",
        )
        strict_manifest = _stage_manifest_map(strict_bundle)
        _assert(
            strict_manifest["final_integrated_closeout"]["review_tier"] == "STRICT",
            "explicit strict exception bundles must preserve a STRICT integrated closeout tier",
        )
        _assert(
            strict_manifest["final_integrated_closeout"]["agent_profile"] == "gpt-5.4-xhigh",
            "explicit strict exception bundles must preserve the strict/xhigh closeout profile",
        )

        low_strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=[
                "docs/contracts/alpha.md",
                "docs/contracts/beta.md",
                "tests/contract/test_alpha.py",
                "tools/loop/review_a.py",
                "tools/loop/review_b.py",
                "tools/loop/review_c.py",
            ],
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            final_closeout_tier="LOW",
            review_tier_policy="LOW_ONLY",
            max_files_per_partition=2,
            followup_partition_ids=[],
        )
        low_bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_low_closeout",
            strategy_plan=low_strategy,
            max_parallel_branches=3,
        )
        low_manifest = _stage_manifest_map(low_bundle)
        _assert(
            low_manifest["final_integrated_closeout"]["review_tier"] == "LOW",
            "explicit LOW closeout bundles must preserve a LOW integrated closeout tier",
        )
        _assert(
            low_manifest["final_integrated_closeout"]["agent_profile"] == "gpt-5.4-low",
            "explicit LOW closeout bundles must preserve the baseline fast reviewer profile",
        )
        invalid_low_policy_strategy = json.loads(json.dumps(low_strategy))
        invalid_low_policy_strategy["closeout_policy"]["review_tier_policy"] = "LOW_PLUS_MEDIUM"
        invalid_low_policy_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_low_policy_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_low_policy_provenance",
                strategy_plan=invalid_low_policy_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "LOW closeout strategies require closeout_policy.review_tier_policy=`LOW_ONLY`" in str(exc),
                "LOW closeout bundles must reject strategies that downgrade closeout tier without LOW_ONLY provenance",
            )
        else:
            raise AssertionError("LOW closeout bundles must reject non-LOW_ONLY provenance")
        invalid_low_only_medium_strategy = json.loads(json.dumps(strategy))
        invalid_low_only_medium_strategy["closeout_policy"]["review_tier_policy"] = "LOW_ONLY"
        invalid_low_only_medium_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_low_only_medium_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_low_only_medium_closeout",
                strategy_plan=invalid_low_only_medium_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "LOW_ONLY closeout policy requires strategy_plan.final_integrated_closeout.review_tier=`LOW`" in str(exc),
                "authoritative bundles must reject LOW_ONLY policy plans that still compile a MEDIUM closeout",
            )
        else:
            raise AssertionError("LOW_ONLY policy plans must reject non-LOW final closeout tiers")
        invalid_low_escalated_strategy = json.loads(json.dumps(strategy))
        invalid_low_escalated_strategy["stages"][2]["review_tier"] = "LOW"
        invalid_low_escalated_strategy["stages"][2]["agent_profile"] = "gpt-5.4-low"
        invalid_low_escalated_strategy["closeout_policy"]["review_tier_policy"] = "LOW_ONLY"
        invalid_low_escalated_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_low_escalated_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_low_escalated_closeout",
                strategy_plan=invalid_low_escalated_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "LOW authoritative closeout requires deep_partition_followup.partition_ids to be empty" in str(exc),
                "authoritative bundle compilation must reject LOW closeout plans that still keep escalated deep follow-up partitions",
            )
        else:
            raise AssertionError("review orchestration bundle must reject LOW closeout plans with escalated deep follow-up partitions")

        manually_narrowed_strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=[
                "docs/contracts/alpha.md",
                "docs/contracts/beta.md",
                "tests/contract/test_alpha.py",
                "tools/loop/review_a.py",
                "tools/loop/review_b.py",
                "tools/loop/review_c.py",
            ],
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            max_files_per_partition=2,
            followup_partition_ids=["part_03_tools_01"],
            effective_scope_paths=["tools/loop/review_a.py"],
        )
        narrowed_bundle = build_review_orchestration_bundle(
                repo_root=repo,
            review_id="review_orchestration_manual_narrowing",
            strategy_plan=manually_narrowed_strategy,
            max_parallel_branches=3,
        )
        narrowed_stage_manifest = _stage_manifest_map(narrowed_bundle)
        narrowed_entry = narrowed_stage_manifest["deep_partition_followup__part_03_tools_01"]
        _assert(
            narrowed_entry["scope_paths"] == ["tools/loop/review_a.py"],
            "deep stage manifest must preserve manual file-level narrowing inside a selected partition",
        )
        _assert(
            narrowed_entry["partition_scope_paths"] == ["tools/loop/review_a.py", "tools/loop/review_b.py"],
            "deep stage manifest must also preserve the original partition scope for auditability",
        )
        _assert(
            narrowed_entry["scope_fingerprint_basis"] == "PATH_SET",
            "manual file-level narrowing must record that the manifest fingerprint came from the narrowed path set",
        )
        replayed_manual_narrowing = json.loads(json.dumps(manually_narrowed_strategy))
        replayed_manual_narrowing["stages"][1]["candidate_partition_ids"] = [
            "part_04_tools_02",
            "part_03_tools_01",
            "part_02_tests",
            "part_01_docs",
        ]
        replayed_manual_narrowing["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(replayed_manual_narrowing)
        )
        replayed_narrowed_bundle = build_review_orchestration_bundle(
                repo_root=repo,
            review_id="review_orchestration_manual_narrowing_replay",
            strategy_plan=replayed_manual_narrowing,
            max_parallel_branches=3,
        )
        replayed_narrowed_entry = _stage_manifest_map(replayed_narrowed_bundle)["deep_partition_followup__part_03_tools_01"]
        _assert(
            replayed_narrowed_entry["scope_paths"] == narrowed_entry["scope_paths"],
            "PATH_SET narrowed stage-manifest scope_paths must stay canonical under replayed non-authoritative candidate ordering",
        )
        _assert(
            replayed_narrowed_entry["scope_fingerprint"] == narrowed_entry["scope_fingerprint"],
            "PATH_SET narrowed stage-manifest scope_fingerprint must stay stable under replayed non-authoritative candidate ordering",
        )

        path_set_strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=[
                "docs/contracts/alpha.md",
                "docs/contracts/beta.md",
                "tests/contract/test_alpha.py",
                "tools/loop/review_a.py",
                "tools/loop/review_b.py",
                "tools/loop/review_c.py",
            ],
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            max_files_per_partition=3,
            followup_partition_ids=["part_03_tools"],
            effective_scope_paths=["tools/loop/review_a.py", "tools/loop/review_c.py"],
        )
        path_set_bundle = build_review_orchestration_bundle(
                repo_root=repo,
            review_id="review_orchestration_path_set_order_a",
            strategy_plan=path_set_strategy,
            max_parallel_branches=3,
        )
        path_set_entry = _stage_manifest_map(path_set_bundle)["deep_partition_followup__part_03_tools"]
        replayed_path_set_strategy = json.loads(json.dumps(path_set_strategy))
        replayed_path_set_strategy["stages"][1]["candidate_partition_ids"] = [
            "part_03_tools",
            "part_02_tests",
            "part_01_docs",
        ]
        replayed_path_set_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(replayed_path_set_strategy)
        )
        replayed_path_set_bundle = build_review_orchestration_bundle(
                repo_root=repo,
            review_id="review_orchestration_path_set_order_b",
            strategy_plan=replayed_path_set_strategy,
            max_parallel_branches=3,
        )
        replayed_path_set_entry = _stage_manifest_map(replayed_path_set_bundle)["deep_partition_followup__part_03_tools"]
        _assert(
            path_set_entry["scope_paths"] == ["tools/loop/review_a.py", "tools/loop/review_c.py"],
            "PATH_SET narrowed stage-manifest scope_paths must stay canonically ordered",
        )
        _assert(
            replayed_path_set_entry["scope_paths"] == path_set_entry["scope_paths"],
            "replayed non-authoritative candidate ordering must not reorder PATH_SET narrowed stage-manifest scope_paths",
        )
        _assert(
            replayed_path_set_entry["scope_fingerprint"] == path_set_entry["scope_fingerprint"],
            "PATH_SET narrowed stage-manifest scope_fingerprint must stay stable under replayed non-authoritative candidate ordering",
        )

        replay_strategy = json.loads(json.dumps(strategy))
        replay_strategy["stages"][0]["partition_ids"] = ["part_01_docs", "part_03_tools_01"]
        replay_strategy["stages"][1]["partition_ids"] = ["part_03_tools_01"]
        replay_strategy["stages"][1]["candidate_partition_ids"] = ["part_01_docs", "part_03_tools_01"]
        replay_strategy["stages"][1]["scope_paths"] = ["tools/loop/review_a.py", "tools/loop/review_b.py"]
        replay_strategy["stages"][1]["scope_fingerprint"] = strategy["partitions"][2]["scope_fingerprint"]
        replay_strategy["stages"][2]["scope_paths"] = ["tools/loop/review_a.py", "tools/loop/review_b.py"]
        replay_strategy["stages"][2]["scope_fingerprint"] = strategy["partitions"][2]["scope_fingerprint"]
        replay_strategy["selected_partition_ids"] = ["part_03_tools_01"]
        replay_strategy["effective_scope_paths"] = ["tools/loop/review_a.py", "tools/loop/review_b.py"]
        replay_strategy["effective_scope_fingerprint"] = strategy["partitions"][2]["scope_fingerprint"]
        replay_strategy["strategy_fingerprint"] = _canonical_hash(_strategy_fingerprint_payload(replay_strategy))
        replay_bundle = build_review_orchestration_bundle(
                repo_root=repo,
            review_id="review_orchestration_replay_fast_subset",
            strategy_plan=replay_strategy,
            max_parallel_branches=3,
        )
        replay_graph = replay_bundle["graph_spec"]
        replay_fast_nodes = sorted(node for node in _node_ids(replay_graph) if node.startswith("fast_partition_scan__"))
        _assert(
            replay_fast_nodes == [
                "fast_partition_scan__part_01_docs",
                "fast_partition_scan__part_03_tools_01",
            ],
            "graph compilation must honor the fast stage partition_ids frozen in the strategy plan",
        )
        _assert(
            replay_bundle["composition_notes"]["fast_partition_node_ids"]
            == [
                "fast_partition_scan__part_01_docs",
                "fast_partition_scan__part_03_tools_01",
            ],
            "bundle composition notes must stay aligned with the frozen fast-stage subset during replay/subset execution",
        )
        replay_edges = _edges(replay_graph)
        _assert(
            ("review_intake", "fast_partition_scan__part_02_tests", "SERIAL") not in replay_edges,
            "graph compilation must not silently resurrect fast partitions outside the frozen fast stage",
        )
        replay_stage_manifest = _stage_manifest_map(replay_bundle)
        replay_fast_lineage_scope = [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
        ]
        _assert(
            replay_stage_manifest["finding_dedupe"]["scope_paths"] == replay_fast_lineage_scope,
            "finding_dedupe stage manifest must freeze the replayed fast-stage lineage instead of the original full scope",
        )
        _assert(
            replay_stage_manifest["finding_dedupe"]["scope_fingerprint"]
            == compute_review_scope_fingerprint(repo_root=repo, scope_paths=replay_fast_lineage_scope),
            "finding_dedupe stage manifest fingerprint must track the replayed fast-stage lineage",
        )

        invalid_replay_strategy = json.loads(json.dumps(strategy))
        invalid_replay_strategy["stages"][0]["partition_ids"] = ["part_01_docs", "part_03_tools_01"]
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_replay_subset",
                strategy_plan=invalid_replay_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "must stay within the frozen fast_partition_scan.partition_ids subset" in str(exc),
                "invalid replay/subset execution should explain that deep follow-up nodes cannot outgrow the frozen fast stage",
            )
        else:
            raise AssertionError(
                "replay/subset execution must reject deep follow-up partitions that were omitted from the frozen fast stage"
            )
        invalid_replay_candidate_strategy = json.loads(json.dumps(replay_strategy))
        invalid_replay_candidate_strategy["stages"][1]["candidate_partition_ids"] = [
            "part_01_docs",
            "part_02_tests",
            "part_03_tools_01",
        ]
        invalid_replay_candidate_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_replay_candidate_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_replay_candidate_subset",
                strategy_plan=invalid_replay_candidate_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "candidate_partition_ids must stay within the frozen fast_partition_scan.partition_ids subset" in str(exc),
                "replay/subset execution must reject deep candidate partitions that were never scanned in the frozen fast stage",
            )
        else:
            raise AssertionError(
                "replay/subset execution must reject deep candidate partitions outside the frozen fast-stage subset"
            )
        invalid_replay_missing_selected_candidate_strategy = json.loads(json.dumps(replay_strategy))
        invalid_replay_missing_selected_candidate_strategy["stages"][1]["candidate_partition_ids"] = ["part_01_docs"]
        invalid_replay_missing_selected_candidate_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_replay_missing_selected_candidate_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_replay_missing_selected_candidate",
                strategy_plan=invalid_replay_missing_selected_candidate_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "candidate_partition_ids must cover every selected deep partition id" in str(exc),
                "replay/subset execution must reject candidate metadata that omits the actually selected deep partition",
            )
        else:
            raise AssertionError(
                "replay/subset execution must reject candidate metadata that omits the selected deep partition"
            )

        invalid_final_scope_strategy = json.loads(json.dumps(strategy))
        invalid_final_scope_strategy["stages"][2]["scope_paths"] = [
            "docs/contracts/alpha.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
        ]
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_final_scope",
                strategy_plan=invalid_final_scope_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "final_integrated_closeout.scope_paths must match the effective main scope exactly" in str(exc),
                "invalid final closeout scope should explain that integrated closeout cannot widen or shrink beyond the effective main scope",
            )
        else:
            raise AssertionError(
                "replay/subset execution must reject final closeout scopes that widen beyond the selected partition lineage"
            )

        invalid_deep_scope_strategy = json.loads(json.dumps(strategy))
        invalid_deep_scope_strategy["stages"][1]["partition_ids"] = ["part_02_tests", "part_03_tools_01"]
        invalid_deep_scope_strategy["stages"][1]["scope_paths"] = ["tools/loop/review_a.py"]
        invalid_deep_scope_strategy["stages"][1]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_deep_scope_strategy["stages"][1]["scope_paths"],
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_deep_scope_coverage",
                strategy_plan=invalid_deep_scope_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "must include at least one file from every selected" in str(exc),
                "invalid deep follow-up narrowing should explain that each selected partition needs explicit scope coverage",
            )
        else:
            raise AssertionError(
                "replay/subset execution must reject deep follow-up narrowing that silently drops a selected partition"
            )

        invalid_blank_provider_strategy = json.loads(json.dumps(strategy))
        invalid_blank_provider_strategy["agent_provider_id"] = ""
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_blank_provider",
                strategy_plan=invalid_blank_provider_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "agent_provider_id must be non-empty" in str(exc),
                "authoritative bundle compilation should reject blank top-level agent_provider_id metadata",
            )
        else:
            raise AssertionError("review orchestration bundle must reject blank agent_provider_id")

        invalid_blank_stage_profile_strategy = json.loads(json.dumps(strategy))
        invalid_blank_stage_profile_strategy["stages"][2]["agent_profile"] = ""
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_blank_strict_profile",
                strategy_plan=invalid_blank_stage_profile_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "final_integrated_closeout.agent_profile must be non-empty" in str(exc),
                "authoritative bundle compilation should reject blank reviewer agent_profile metadata",
            )
        else:
            raise AssertionError("review orchestration bundle must reject blank final stage agent_profile")

        invalid_final_tier_strategy = json.loads(json.dumps(strategy))
        invalid_final_tier_strategy["stages"][2]["review_tier"] = "FAST"
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_final_tier",
                strategy_plan=invalid_final_tier_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "final_integrated_closeout.review_tier must be `LOW`, `MEDIUM`, or `STRICT`" in str(exc),
                "authoritative bundle compilation must reject unsupported final closeout tiers",
            )
        else:
            raise AssertionError("review orchestration bundle must reject unsupported final closeout tiers")

        invalid_medium_low_profile_strategy = json.loads(json.dumps(strategy))
        invalid_medium_low_profile_strategy["stages"][2]["agent_profile"] = invalid_medium_low_profile_strategy["stages"][0]["agent_profile"]
        invalid_medium_low_profile_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_medium_low_profile_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_medium_low_profile",
                strategy_plan=invalid_medium_low_profile_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "final_integrated_closeout.agent_profile must match the bounded medium escalation profile exactly" in str(exc),
                "authoritative bundle compilation must reject medium closeout plans that swap in a non-medium profile",
            )
        else:
            raise AssertionError("review orchestration bundle must reject medium closeout plans that bypass the bounded medium profile")

        invalid_low_medium_profile_strategy = json.loads(json.dumps(low_strategy))
        invalid_low_medium_profile_strategy["stages"][2]["review_tier"] = "LOW"
        invalid_low_medium_profile_strategy["stages"][2]["agent_profile"] = invalid_low_medium_profile_strategy["stages"][1]["agent_profile"]
        invalid_low_medium_profile_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_low_medium_profile_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_low_medium_profile",
                strategy_plan=invalid_low_medium_profile_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "final_integrated_closeout.agent_profile must match strategy_plan.fast_partition_scan.agent_profile exactly" in str(exc),
                "authoritative bundle compilation must reject LOW closeout plans that swap in a non-baseline profile",
            )
        else:
            raise AssertionError("review orchestration bundle must reject LOW closeout plans that bypass the baseline fast profile")
        invalid_strict_medium_profile_strategy = json.loads(json.dumps(strategy))
        invalid_strict_medium_profile_strategy["stages"][2]["review_tier"] = "STRICT"
        invalid_strict_medium_profile_strategy["stages"][2]["agent_profile"] = invalid_strict_medium_profile_strategy["stages"][1]["agent_profile"]
        invalid_strict_medium_profile_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_strict_medium_profile_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_strict_medium_profile",
                strategy_plan=invalid_strict_medium_profile_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "final_integrated_closeout.agent_profile must match strategy_plan.strict_exception_profile exactly" in str(exc),
                "authoritative bundle compilation must reject strict closeout plans that silently reuse the medium profile",
            )
        else:
            raise AssertionError("review orchestration bundle must reject strict closeout plans that reuse the medium profile")

        invalid_strict_low_profile_strategy = json.loads(json.dumps(strategy))
        invalid_strict_low_profile_strategy["stages"][2]["review_tier"] = "STRICT"
        invalid_strict_low_profile_strategy["stages"][2]["agent_profile"] = invalid_strict_low_profile_strategy["stages"][0]["agent_profile"]
        invalid_strict_low_profile_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_strict_low_profile_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_strict_low_profile",
                strategy_plan=invalid_strict_low_profile_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "final_integrated_closeout.agent_profile must match strategy_plan.strict_exception_profile exactly" in str(exc),
                "authoritative bundle compilation must reject strict closeout plans that silently reuse the baseline fast profile",
            )
        else:
            raise AssertionError("review orchestration bundle must reject strict closeout plans that reuse the baseline fast profile")

        invalid_strict_arbitrary_profile_strategy = json.loads(json.dumps(strategy))
        invalid_strict_arbitrary_profile_strategy["stages"][2]["review_tier"] = "STRICT"
        invalid_strict_arbitrary_profile_strategy["stages"][2]["agent_profile"] = "gpt-5.4-high"
        invalid_strict_arbitrary_profile_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_strict_arbitrary_profile_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_strict_arbitrary_profile",
                strategy_plan=invalid_strict_arbitrary_profile_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "final_integrated_closeout.agent_profile must match strategy_plan.strict_exception_profile exactly" in str(exc),
                "authoritative bundle compilation must reject arbitrary non-exception strict closeout profiles",
            )
        else:
            raise AssertionError("review orchestration bundle must reject strict closeout plans that bypass the dedicated strict exception profile")

        invalid_blank_partition_fingerprint_strategy = json.loads(json.dumps(strategy))
        invalid_blank_partition_fingerprint_strategy["partitions"][0]["scope_fingerprint"] = ""
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_blank_partition_fingerprint",
                strategy_plan=invalid_blank_partition_fingerprint_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "partitions.*.scope_fingerprint must be non-empty" in str(exc),
                "authoritative bundle compilation should reject blank partition scope fingerprint metadata",
            )
        else:
            raise AssertionError("review orchestration bundle must reject blank partition scope fingerprint metadata")

        invalid_blank_final_fingerprint_strategy = json.loads(json.dumps(strategy))
        invalid_blank_final_fingerprint_strategy["stages"][2]["scope_fingerprint"] = ""
        invalid_blank_final_fingerprint_strategy["effective_scope_fingerprint"] = ""
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_blank_final_fingerprint",
                strategy_plan=invalid_blank_final_fingerprint_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "effective_scope_fingerprint must be non-empty" in str(exc)
                or "final_integrated_closeout.scope_fingerprint must be non-empty" in str(exc),
                "authoritative bundle compilation should reject blank effective/final scope fingerprint metadata",
            )
        else:
            raise AssertionError("review orchestration bundle must reject blank effective/final scope fingerprint metadata")

        invalid_stale_full_fingerprint_strategy = json.loads(json.dumps(strategy))
        invalid_stale_full_fingerprint_strategy["full_scope_fingerprint"] = "deadbeef"
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_stale_full_fingerprint",
                strategy_plan=invalid_stale_full_fingerprint_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "full_scope_fingerprint must match the repository-byte fingerprint of its scope_paths" in str(exc),
                "authoritative bundle compilation should reject stale full-scope fingerprint metadata",
            )
        else:
            raise AssertionError("review orchestration bundle must reject stale full-scope fingerprint metadata")

        invalid_stale_partition_fingerprint_strategy = json.loads(json.dumps(strategy))
        invalid_stale_partition_fingerprint_strategy["partitions"][0]["scope_fingerprint"] = "deadbeef"
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_stale_partition_fingerprint",
                strategy_plan=invalid_stale_partition_fingerprint_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "partitions.*.scope_fingerprint must match the repository-byte fingerprint of its scope_paths" in str(exc),
                "authoritative bundle compilation should reject stale partition fingerprint metadata",
            )
        else:
            raise AssertionError("review orchestration bundle must reject stale partition fingerprint metadata")

        invalid_stale_effective_fingerprint_strategy = json.loads(json.dumps(strategy))
        invalid_stale_effective_fingerprint_strategy["effective_scope_fingerprint"] = "deadbeef"
        invalid_stale_effective_fingerprint_strategy["stages"][2]["scope_fingerprint"] = "deadbeef"
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_stale_effective_fingerprint",
                strategy_plan=invalid_stale_effective_fingerprint_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "effective_scope_fingerprint must match the repository-byte fingerprint of its scope_paths" in str(exc),
                "authoritative bundle compilation should reject stale effective/final fingerprint metadata",
            )
        else:
            raise AssertionError("review orchestration bundle must reject stale effective/final fingerprint metadata")

        invalid_stale_deep_fingerprint_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_stale_deep_fingerprint_strategy["stages"][1]["scope_fingerprint"] = "deadbeef"
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_stale_deep_fingerprint",
                strategy_plan=invalid_stale_deep_fingerprint_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "deep_partition_followup.scope_fingerprint must match the repository-byte fingerprint of its scope_paths" in str(exc),
                "authoritative bundle compilation should reject stale deep-stage fingerprint metadata",
            )
        else:
            raise AssertionError("review orchestration bundle must reject stale deep-stage fingerprint metadata")

        invalid_stale_strategy_fingerprint_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
            effective_scope_paths=["tools/loop/review_a.py"],
        )
        invalid_stale_strategy_fingerprint_strategy["strategy_fingerprint"] = "deadbeef"
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_stale_strategy_fingerprint",
                strategy_plan=invalid_stale_strategy_fingerprint_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "strategy_fingerprint must match the canonical hash of the authoritative strategy-plan content that executable orchestration artifacts actually consume"
                in str(exc),
                "authoritative bundle compilation should reject stale strategy fingerprints after replayed narrowing",
            )
        else:
            raise AssertionError("review orchestration bundle must reject stale strategy fingerprints")

        invalid_no_followup_lineage_strategy = _strategy(
            repo,
            followup_partition_ids=[],
        )
        invalid_no_followup_lineage_strategy["stages"][0]["partition_ids"] = [
            "part_01_docs",
            "part_03_tools_01",
        ]
        invalid_no_followup_lineage_strategy["stages"][1]["candidate_partition_ids"] = [
            "part_01_docs",
            "part_03_tools_01",
        ]
        invalid_no_followup_lineage_strategy["effective_scope_paths"] = [
            "docs/contracts/alpha.md",
            "tests/contract/test_alpha.py",
        ]
        invalid_no_followup_lineage_strategy["effective_scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_no_followup_lineage_strategy["effective_scope_paths"],
        )
        invalid_no_followup_lineage_strategy["stages"][2]["scope_paths"] = list(
            invalid_no_followup_lineage_strategy["effective_scope_paths"]
        )
        invalid_no_followup_lineage_strategy["stages"][2]["scope_fingerprint"] = str(
            invalid_no_followup_lineage_strategy["effective_scope_fingerprint"]
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_no_followup_lineage",
                strategy_plan=invalid_no_followup_lineage_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "must match the frozen fast_partition_scan lineage exactly when deep_partition_followup.partition_ids is empty"
                in str(exc),
                "authoritative bundle compilation should reject no-followup closeout scopes without frozen fast-stage lineage",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject no-followup effective scopes that no longer match the frozen fast-stage lineage"
            )

        invalid_reordered_final_scope_strategy = _strategy(
            repo,
            followup_partition_ids=[],
        )
        reversed_final_scope = list(
            reversed(
                invalid_reordered_final_scope_strategy["stages"][2]["scope_paths"]
            )
        )
        invalid_reordered_final_scope_strategy["stages"][2]["scope_paths"] = reversed_final_scope
        invalid_reordered_final_scope_strategy["stages"][2]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reversed_final_scope,
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_reordered_final_scope",
                strategy_plan=invalid_reordered_final_scope_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "final_integrated_closeout.scope_paths must match the effective main scope exactly" in str(exc)
                and "path order differs" in str(exc),
                "authoritative bundle compilation should reject reordered final closeout scopes even when the path set matches",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject reordered final closeout scope paths"
            )

        invalid_reordered_no_followup_lineage_strategy = _strategy(
            repo,
            followup_partition_ids=[],
        )
        reordered_effective_scope = list(
            reversed(invalid_reordered_no_followup_lineage_strategy["effective_scope_paths"])
        )
        invalid_reordered_no_followup_lineage_strategy["effective_scope_paths"] = reordered_effective_scope
        invalid_reordered_no_followup_lineage_strategy["effective_scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_effective_scope,
        )
        invalid_reordered_no_followup_lineage_strategy["stages"][2]["scope_paths"] = list(reordered_effective_scope)
        invalid_reordered_no_followup_lineage_strategy["stages"][2]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_effective_scope,
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_reordered_no_followup_lineage",
                strategy_plan=invalid_reordered_no_followup_lineage_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "must match the frozen fast_partition_scan lineage exactly when deep_partition_followup.partition_ids is empty"
                in str(exc)
                and "path order differs" in str(exc),
                "authoritative bundle compilation should reject reordered no-followup effective scopes even when the file set matches",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject reordered no-followup effective scope paths"
            )

        invalid_deep_exact_lineage_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_deep_exact_lineage_strategy["stages"][1]["scope_paths"] = ["tools/loop/review_a.py"]
        invalid_deep_exact_lineage_strategy["stages"][1]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_deep_exact_lineage_strategy["stages"][1]["scope_paths"],
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_deep_exact_lineage",
                strategy_plan=invalid_deep_exact_lineage_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "strategy_plan.effective_scope_paths and strategy_plan.deep_partition_followup.scope_paths must match exactly when deep_partition_followup.partition_ids is non-empty"
                in str(exc),
                "authoritative bundle compilation should reject closeout scopes that widen beyond the narrowed deep follow-up lineage",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject closeout scopes that do not exactly match the narrowed deep follow-up scope"
            )

        invalid_reordered_deep_exact_lineage_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        reordered_deep_scope = list(
            reversed(invalid_reordered_deep_exact_lineage_strategy["stages"][1]["scope_paths"])
        )
        invalid_reordered_deep_exact_lineage_strategy["stages"][1]["scope_paths"] = reordered_deep_scope
        invalid_reordered_deep_exact_lineage_strategy["stages"][1]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_deep_scope,
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_reordered_deep_exact_lineage",
                strategy_plan=invalid_reordered_deep_exact_lineage_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "strategy_plan.deep_partition_followup.scope_paths must match the canonical selected partition lineage exactly when deep_partition_followup.partition_ids is non-empty"
                in str(exc)
                and "path order differs" in str(exc),
                "authoritative bundle compilation should reject reordered deep follow-up scopes even when the file set matches",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject reordered deep follow-up scope paths"
            )

        invalid_reordered_selected_partition_lineage_strategy = _strategy(
            repo,
            followup_partition_ids=["part_02_tests", "part_03_tools_01"],
        )
        reordered_narrowed_scope = list(
            reversed(invalid_reordered_selected_partition_lineage_strategy["stages"][1]["scope_paths"])
        )
        invalid_reordered_selected_partition_lineage_strategy["stages"][1]["scope_paths"] = reordered_narrowed_scope
        invalid_reordered_selected_partition_lineage_strategy["stages"][1]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_narrowed_scope,
        )
        invalid_reordered_selected_partition_lineage_strategy["effective_scope_paths"] = list(reordered_narrowed_scope)
        invalid_reordered_selected_partition_lineage_strategy["effective_scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_narrowed_scope,
        )
        invalid_reordered_selected_partition_lineage_strategy["stages"][2]["scope_paths"] = list(reordered_narrowed_scope)
        invalid_reordered_selected_partition_lineage_strategy["stages"][2]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_narrowed_scope,
        )
        invalid_reordered_selected_partition_lineage_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_reordered_selected_partition_lineage_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_reordered_selected_partition_lineage",
                strategy_plan=invalid_reordered_selected_partition_lineage_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "canonical selected partition lineage exactly" in str(exc)
                and "path order differs" in str(exc),
                "authoritative bundle compilation should reject deep/effective/final scopes that are reordered together away from the canonical selected-partition lineage",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject reordered narrowed scopes even when deep/effective/final stay internally consistent"
            )

        invalid_reordered_selected_partition_ids_strategy = _strategy(
            repo,
            followup_partition_ids=["part_02_tests", "part_03_tools_01"],
        )
        reordered_selected_partition_ids = ["part_03_tools_01", "part_02_tests"]
        reordered_selected_partition_scope = [
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tests/contract/test_alpha.py",
        ]
        invalid_reordered_selected_partition_ids_strategy["selected_partition_ids"] = list(
            reordered_selected_partition_ids
        )
        invalid_reordered_selected_partition_ids_strategy["stages"][1]["partition_ids"] = list(
            reordered_selected_partition_ids
        )
        invalid_reordered_selected_partition_ids_strategy["stages"][1]["scope_paths"] = list(
            reordered_selected_partition_scope
        )
        invalid_reordered_selected_partition_ids_strategy["stages"][1]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_selected_partition_scope,
        )
        invalid_reordered_selected_partition_ids_strategy["effective_scope_paths"] = list(
            reordered_selected_partition_scope
        )
        invalid_reordered_selected_partition_ids_strategy["effective_scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_selected_partition_scope,
        )
        invalid_reordered_selected_partition_ids_strategy["stages"][2]["scope_paths"] = list(
            reordered_selected_partition_scope
        )
        invalid_reordered_selected_partition_ids_strategy["stages"][2]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_selected_partition_scope,
        )
        invalid_reordered_selected_partition_ids_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_reordered_selected_partition_ids_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_reordered_selected_partition_ids",
                strategy_plan=invalid_reordered_selected_partition_ids_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "deep_partition_followup.partition_ids must preserve the frozen fast_partition_scan.partition_ids order exactly"
                in str(exc),
                "authoritative bundle compilation should reject reordered selected/deep partition ids even when the narrowed scope is reordered consistently",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject reordered selected/deep partition ids against the frozen fast-stage partition order"
            )

        invalid_reordered_fast_partition_ids_strategy = _strategy(
            repo,
            followup_partition_ids=["part_02_tests", "part_03_tools_01"],
        )
        reordered_fast_partition_ids = [
            "part_03_tools_01",
            "part_02_tests",
            "part_01_docs",
            "part_04_tools_02",
        ]
        reordered_followup_partition_ids = ["part_03_tools_01", "part_02_tests"]
        reordered_followup_scope = [
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tests/contract/test_alpha.py",
        ]
        invalid_reordered_fast_partition_ids_strategy["stages"][0]["partition_ids"] = list(
            reordered_fast_partition_ids
        )
        invalid_reordered_fast_partition_ids_strategy["selected_partition_ids"] = list(
            reordered_followup_partition_ids
        )
        invalid_reordered_fast_partition_ids_strategy["stages"][1]["partition_ids"] = list(
            reordered_followup_partition_ids
        )
        invalid_reordered_fast_partition_ids_strategy["stages"][1]["scope_paths"] = list(
            reordered_followup_scope
        )
        invalid_reordered_fast_partition_ids_strategy["stages"][1]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_followup_scope,
        )
        invalid_reordered_fast_partition_ids_strategy["effective_scope_paths"] = list(
            reordered_followup_scope
        )
        invalid_reordered_fast_partition_ids_strategy["effective_scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_followup_scope,
        )
        invalid_reordered_fast_partition_ids_strategy["stages"][2]["scope_paths"] = list(
            reordered_followup_scope
        )
        invalid_reordered_fast_partition_ids_strategy["stages"][2]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_followup_scope,
        )
        invalid_reordered_fast_partition_ids_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_reordered_fast_partition_ids_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_reordered_fast_partition_ids",
                strategy_plan=invalid_reordered_fast_partition_ids_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "fast_partition_scan.partition_ids must preserve the canonical strategy_plan.partitions order exactly"
                in str(exc),
                "authoritative bundle compilation should reject replayed strategies that redefine the frozen fast-stage order, even when deep/effective/final metadata is reordered consistently to match",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject reordered fast-stage partition ids against the canonical partition list"
            )

        invalid_reordered_partition_list_strategy = _strategy(
            repo,
            followup_partition_ids=["part_02_tests", "part_03_tools_01"],
        )
        reordered_partitions = [
            invalid_reordered_partition_list_strategy["partitions"][0],
            invalid_reordered_partition_list_strategy["partitions"][2],
            invalid_reordered_partition_list_strategy["partitions"][1],
            invalid_reordered_partition_list_strategy["partitions"][3],
        ]
        invalid_reordered_partition_list_strategy["partitions"] = list(reordered_partitions)
        reordered_partition_ids = [str(part["partition_id"]) for part in reordered_partitions]
        reordered_partition_index = {
            str(part["partition_id"]): list(part.get("scope_paths") or [])
            for part in reordered_partitions
        }
        reordered_effective_scope = [
            path
            for partition_id in reordered_partition_ids
            if partition_id in {"part_03_tools_01", "part_02_tests"}
            for path in reordered_partition_index[partition_id]
        ]
        invalid_reordered_partition_list_strategy["stages"][0]["partition_ids"] = list(reordered_partition_ids)
        invalid_reordered_partition_list_strategy["selected_partition_ids"] = [
            "part_03_tools_01",
            "part_02_tests",
        ]
        invalid_reordered_partition_list_strategy["stages"][1]["candidate_partition_ids"] = list(
            reordered_partition_ids
        )
        invalid_reordered_partition_list_strategy["stages"][1]["partition_ids"] = [
            "part_03_tools_01",
            "part_02_tests",
        ]
        invalid_reordered_partition_list_strategy["stages"][1]["scope_paths"] = list(
            reordered_effective_scope
        )
        invalid_reordered_partition_list_strategy["stages"][1]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_effective_scope,
        )
        invalid_reordered_partition_list_strategy["effective_scope_paths"] = list(
            reordered_effective_scope
        )
        invalid_reordered_partition_list_strategy["effective_scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_effective_scope,
        )
        invalid_reordered_partition_list_strategy["stages"][2]["scope_paths"] = list(
            reordered_effective_scope
        )
        invalid_reordered_partition_list_strategy["stages"][2]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=reordered_effective_scope,
        )
        invalid_reordered_partition_list_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_reordered_partition_list_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_reordered_partition_list",
                strategy_plan=invalid_reordered_partition_list_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                (
                    "strategy_plan.partitions must preserve canonical helper-derived partition order from partition scope chunking"
                    in str(exc)
                    or "strategy_plan.partitions must match the helper-generated partition boundaries exactly for the declared partitioning_policy"
                    in str(exc)
                ),
                "authoritative bundle compilation should reject replayed partition-list reordering even when fast/deep/effective/final metadata is rewritten consistently",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject replayed reordering of strategy_plan.partitions"
            )

        invalid_reordered_no_followup_partition_scope_strategy = _strategy(
            repo,
            followup_partition_ids=[],
            effective_scope_paths=[],
        )
        invalid_reordered_no_followup_partition_scope_strategy["partitions"][1]["scope_paths"] = [
            "tests/contract/test_alpha.py",
        ]
        invalid_reordered_no_followup_partition_scope_strategy["partitions"][2]["scope_paths"] = [
            "tools/loop/review_b.py",
            "tools/loop/review_a.py",
        ]
        invalid_reordered_no_followup_partition_scope_strategy["partitions"][2]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_reordered_no_followup_partition_scope_strategy["partitions"][2]["scope_paths"],
        )
        invalid_reordered_no_followup_partition_scope_strategy["effective_scope_paths"] = [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_b.py",
            "tools/loop/review_a.py",
            "tools/loop/review_c.py",
        ]
        invalid_reordered_no_followup_partition_scope_strategy["effective_scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_reordered_no_followup_partition_scope_strategy["effective_scope_paths"],
        )
        invalid_reordered_no_followup_partition_scope_strategy["stages"][2]["scope_paths"] = list(
            invalid_reordered_no_followup_partition_scope_strategy["effective_scope_paths"]
        )
        invalid_reordered_no_followup_partition_scope_strategy["stages"][2]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_reordered_no_followup_partition_scope_strategy["stages"][2]["scope_paths"],
        )
        invalid_reordered_no_followup_partition_scope_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_reordered_no_followup_partition_scope_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_reordered_no_followup_partition_scope",
                strategy_plan=invalid_reordered_no_followup_partition_scope_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "strategy_plan.partitions.*.scope_paths must preserve canonical repo-relative file order within each partition"
                in str(exc),
                "authoritative bundle compilation should reject no-followup replay plans that fork partition-local file order",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject no-followup partition-local scope reordering"
            )

        invalid_duplicate_partition_strategy = json.loads(json.dumps(strategy))
        invalid_duplicate_partition_strategy["partitions"][1]["partition_id"] = invalid_duplicate_partition_strategy["partitions"][0]["partition_id"]
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_duplicate_partition_ids",
                strategy_plan=invalid_duplicate_partition_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "must carry unique partition_id values" in str(exc),
                "authoritative bundle compilation should reject duplicate partition ids before routing metadata is compiled",
            )
        else:
            raise AssertionError("review orchestration bundle must reject duplicate partition ids")

        invalid_empty_partition_scope_strategy = json.loads(json.dumps(strategy))
        invalid_empty_partition_scope_strategy["partitions"][0]["scope_paths"] = []
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_empty_partition_scope",
                strategy_plan=invalid_empty_partition_scope_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "partitions.*.scope_paths must be non-empty" in str(exc),
                "authoritative bundle compilation should reject fast-stage partitions that do not carry a real file scope",
            )
        else:
            raise AssertionError("review orchestration bundle must reject empty partition scopes")

        invalid_overlapping_partition_scope_strategy = json.loads(json.dumps(strategy))
        invalid_overlapping_partition_scope_strategy["partitions"][1]["scope_paths"] = [
            "docs/contracts/alpha.md",
            "tests/contract/test_alpha.py",
        ]
        invalid_overlapping_partition_scope_strategy["partitions"][1]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_overlapping_partition_scope_strategy["partitions"][1]["scope_paths"],
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_overlapping_partition_scope",
                strategy_plan=invalid_overlapping_partition_scope_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "partitions must be disjoint across partition_id values" in str(exc),
                "authoritative bundle compilation should reject overlapping fast-stage partition scopes",
            )
        else:
            raise AssertionError("review orchestration bundle must reject overlapping partition scopes")

        invalid_missing_partition_cover_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_missing_partition_cover_strategy["partitions"][0]["scope_paths"] = [
            "docs/contracts/alpha.md",
        ]
        invalid_missing_partition_cover_strategy["partitions"][0]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_missing_partition_cover_strategy["partitions"][0]["scope_paths"],
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_missing_partition_cover",
                strategy_plan=invalid_missing_partition_cover_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "must form an exact cover of full_scope_paths" in str(exc),
                "authoritative bundle compilation should reject partition sets that do not cover the full frozen scope",
            )
        else:
            raise AssertionError("review orchestration bundle must reject incomplete partition coverage")

        invalid_reordered_full_scope_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_reordered_full_scope_strategy["full_scope_paths"] = list(
            reversed(invalid_reordered_full_scope_strategy["full_scope_paths"])
        )
        invalid_reordered_full_scope_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_reordered_full_scope_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_reordered_full_scope",
                strategy_plan=invalid_reordered_full_scope_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "strategy_plan.full_scope_paths must preserve canonical repo-relative file order" in str(exc),
                "authoritative bundle compilation should reject replayed full-scope reordering that only forks provenance",
            )
        else:
            raise AssertionError("review orchestration bundle must reject reordered full_scope_paths")

        invalid_duplicate_authoritative_scope_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        duplicate_scope = [
            "tools/loop/review_a.py",
            "tools/loop/review_a.py",
        ]
        duplicate_fingerprint = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=duplicate_scope,
        )
        invalid_duplicate_authoritative_scope_strategy["effective_scope_paths"] = list(duplicate_scope)
        invalid_duplicate_authoritative_scope_strategy["effective_scope_fingerprint"] = duplicate_fingerprint
        invalid_duplicate_authoritative_scope_strategy["stages"][1]["scope_paths"] = list(duplicate_scope)
        invalid_duplicate_authoritative_scope_strategy["stages"][1]["scope_fingerprint"] = duplicate_fingerprint
        invalid_duplicate_authoritative_scope_strategy["stages"][2]["scope_paths"] = list(duplicate_scope)
        invalid_duplicate_authoritative_scope_strategy["stages"][2]["scope_fingerprint"] = duplicate_fingerprint
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_duplicate_authoritative_scope",
                strategy_plan=invalid_duplicate_authoritative_scope_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "must not repeat paths" in str(exc),
                "authoritative bundle compilation should reject duplicate scope paths in deep/effective/final lineage",
            )
        else:
            raise AssertionError("review orchestration bundle must reject duplicate authoritative scope paths")

        invalid_duplicate_alias_scope_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        duplicate_alias_scope = [
            "tools/loop/review_a.py",
            "./tools/loop/review_a.py",
        ]
        duplicate_alias_fingerprint = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=duplicate_alias_scope,
        )
        invalid_duplicate_alias_scope_strategy["effective_scope_paths"] = list(duplicate_alias_scope)
        invalid_duplicate_alias_scope_strategy["effective_scope_fingerprint"] = duplicate_alias_fingerprint
        invalid_duplicate_alias_scope_strategy["stages"][1]["scope_paths"] = list(duplicate_alias_scope)
        invalid_duplicate_alias_scope_strategy["stages"][1]["scope_fingerprint"] = duplicate_alias_fingerprint
        invalid_duplicate_alias_scope_strategy["stages"][2]["scope_paths"] = list(duplicate_alias_scope)
        invalid_duplicate_alias_scope_strategy["stages"][2]["scope_fingerprint"] = duplicate_alias_fingerprint
        invalid_duplicate_alias_scope_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_duplicate_alias_scope_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_duplicate_alias_scope",
                strategy_plan=invalid_duplicate_alias_scope_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "must not repeat paths" in str(exc),
                "authoritative bundle compilation should canonicalize repo paths before rejecting duplicated scope entries",
            )
        else:
            raise AssertionError("review orchestration bundle must reject duplicate authoritative scope aliases")

        invalid_stale_top_level_provenance_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_stale_top_level_provenance_strategy["effective_scope_source"] = "FORGED_SOURCE"
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_stale_top_level_provenance",
                strategy_plan=invalid_stale_top_level_provenance_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "strategy_fingerprint must match the canonical hash of the authoritative strategy-plan content that executable orchestration artifacts actually consume"
                in str(exc)
                or "effective_scope_source must match final_integrated_closeout.scope_source" in str(exc),
                "authoritative bundle compilation should reject top-level provenance drift before integrated closeout metadata is compiled",
            )
        else:
            raise AssertionError("review orchestration bundle must reject stale top-level provenance metadata")

        invalid_selected_partition_ids_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_selected_partition_ids_strategy["selected_partition_ids"] = ["part_02_tests"]
        invalid_selected_partition_ids_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_selected_partition_ids_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_selected_partition_ids",
                strategy_plan=invalid_selected_partition_ids_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "selected_partition_ids must match deep_partition_followup.partition_ids exactly" in str(exc),
                "authoritative bundle compilation should reject forged top-level selected_partition_ids metadata",
            )
        else:
            raise AssertionError("review orchestration bundle must reject forged selected_partition_ids metadata")

        invalid_effective_scope_source_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_effective_scope_source_strategy["effective_scope_source"] = "FORGED_SOURCE"
        invalid_effective_scope_source_strategy["stages"][2]["scope_source"] = "FORGED_SOURCE"
        invalid_effective_scope_source_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_effective_scope_source_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_effective_scope_source",
                strategy_plan=invalid_effective_scope_source_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "effective_scope_source/final_integrated_closeout.scope_source must use a canonical helper-authored provenance label"
                in str(exc),
                "authoritative bundle compilation should reject forged top-level/final authoritative scope-source provenance",
            )
        else:
            raise AssertionError("review orchestration bundle must reject forged effective_scope_source metadata")

        invalid_partition_id_format_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_partition_id_format_strategy["partitions"][0]["partition_id"] = "part_1_docs!bad"
        invalid_partition_id_format_strategy["stages"][0]["partition_ids"][0] = "part_1_docs!bad"
        invalid_partition_id_format_strategy["stages"][1]["candidate_partition_ids"][0] = "part_1_docs!bad"
        invalid_partition_id_format_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_partition_id_format_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_partition_id_format",
                strategy_plan=invalid_partition_id_format_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "partitions[*].partition_id must preserve the canonical helper-derived routing ids exactly"
                in str(exc),
                "authoritative bundle compilation should reject replayed partition ids that drop zero-padding or safe helper slug formatting",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject malformed replayed partition ids even when the fingerprint is recomputed"
            )

        invalid_repartitioned_boundary_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_repartitioned_boundary_strategy["partitions"][2]["scope_paths"] = ["tools/loop/review_a.py"]
        invalid_repartitioned_boundary_strategy["partitions"][2]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_repartitioned_boundary_strategy["partitions"][2]["scope_paths"],
        )
        invalid_repartitioned_boundary_strategy["partitions"][3]["scope_paths"] = [
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ]
        invalid_repartitioned_boundary_strategy["partitions"][3]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_repartitioned_boundary_strategy["partitions"][3]["scope_paths"],
        )
        invalid_repartitioned_boundary_strategy["stages"][1]["scope_paths"] = ["tools/loop/review_a.py"]
        invalid_repartitioned_boundary_strategy["stages"][1]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_repartitioned_boundary_strategy["stages"][1]["scope_paths"],
        )
        invalid_repartitioned_boundary_strategy["effective_scope_paths"] = ["tools/loop/review_a.py"]
        invalid_repartitioned_boundary_strategy["effective_scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_repartitioned_boundary_strategy["effective_scope_paths"],
        )
        invalid_repartitioned_boundary_strategy["stages"][2]["scope_paths"] = ["tools/loop/review_a.py"]
        invalid_repartitioned_boundary_strategy["stages"][2]["scope_fingerprint"] = compute_review_scope_fingerprint(
            repo_root=repo,
            scope_paths=invalid_repartitioned_boundary_strategy["stages"][2]["scope_paths"],
        )
        invalid_repartitioned_boundary_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_repartitioned_boundary_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_repartitioned_boundary",
                strategy_plan=invalid_repartitioned_boundary_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "strategy_plan.partitions must match the helper-generated partition boundaries exactly for the declared partitioning_policy"
                in str(exc),
                "authoritative bundle compilation should reject replayed plans that keep canonical-looking ids but reshape helper partition boundaries",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject replayed repartitioning under canonical-looking partition ids"
            )

        invalid_string_partitioning_policy_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_string_partitioning_policy_strategy["partitioning_policy"]["max_files_per_partition"] = "2"
        invalid_string_partitioning_policy_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_string_partitioning_policy_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_string_partitioning_policy",
                strategy_plan=invalid_string_partitioning_policy_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "strategy_plan.partitioning_policy.max_files_per_partition must remain a positive integer policy field"
                in str(exc),
                "authoritative bundle compilation should reject replayed partitioning policies that coerce a non-integer chunk size into a no-op fingerprint fork",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject replayed partitioning policies that encode chunk size as a string"
            )

        boundary_equivalent_root = repo / "boundary_equivalent"
        for rel in (
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
        ):
            _write(boundary_equivalent_root / rel)
        boundary_equivalent_strategy = build_pyramid_review_plan(
            repo_root=boundary_equivalent_root,
            scope_paths=[
                "docs/contracts/alpha.md",
                "docs/contracts/beta.md",
                "tests/contract/test_alpha.py",
                "tools/loop/review_a.py",
                "tools/loop/review_b.py",
            ],
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            max_files_per_partition=2,
            followup_partition_ids=["part_03_tools"],
        )
        boundary_equivalent_replay = json.loads(json.dumps(boundary_equivalent_strategy))
        boundary_equivalent_replay["partitioning_policy"]["max_files_per_partition"] = 3
        boundary_equivalent_replay["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(boundary_equivalent_replay)
        )
        _assert(
            boundary_equivalent_replay["strategy_fingerprint"] == boundary_equivalent_strategy["strategy_fingerprint"],
            "boundary-equivalent max_files_per_partition replays must preserve the canonical strategy_fingerprint",
        )
        boundary_equivalent_bundle = build_review_orchestration_bundle(
            repo_root=boundary_equivalent_root,
            review_id="review_orchestration_boundary_equivalent_partitioning_policy",
            strategy_plan=boundary_equivalent_replay,
            max_parallel_branches=3,
        )
        boundary_equivalent_manifest = _stage_manifest_map(boundary_equivalent_bundle)
        _assert(
            boundary_equivalent_manifest["deep_partition_followup__part_03_tools"]["scope_paths"]
            == ["tools/loop/review_a.py", "tools/loop/review_b.py"],
            "authoritative replay should accept boundary-equivalent max_files_per_partition drift when the frozen helper-derived partition boundaries remain identical",
        )
        _assert(
            boundary_equivalent_bundle["composition_notes"]["strategy_fingerprint"]
            == boundary_equivalent_strategy["strategy_fingerprint"],
            "accepted boundary-equivalent authoritative replays must preserve the original strategy_fingerprint lineage",
        )

        legacy_boundary_equivalent_replay = json.loads(json.dumps(boundary_equivalent_replay))
        legacy_boundary_equivalent_replay["strategy_fingerprint"] = _canonical_hash(
            _legacy_uncanonicalized_strategy_fingerprint_payload(legacy_boundary_equivalent_replay)
        )
        _assert(
            legacy_boundary_equivalent_replay["strategy_fingerprint"] != boundary_equivalent_strategy["strategy_fingerprint"],
            "pre-canonical boundary-equivalent strategy fingerprints must differ from the current canonical hash in this replay regression fixture",
        )
        legacy_boundary_equivalent_bundle = build_review_orchestration_bundle(
            repo_root=boundary_equivalent_root,
            review_id="review_orchestration_boundary_equivalent_partitioning_policy_legacy_fingerprint",
            strategy_plan=legacy_boundary_equivalent_replay,
            max_parallel_branches=3,
        )
        _assert(
            legacy_boundary_equivalent_bundle["composition_notes"]["strategy_fingerprint"]
            == legacy_boundary_equivalent_replay["strategy_fingerprint"],
            "authoritative replay must continue accepting pre-canonical boundary-equivalent strategy fingerprints for historical plans",
        )

        invalid_narrowed_empty_followup_label_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_narrowed_empty_followup_label_strategy["effective_scope_source"] = "FULL_SCOPE_AFTER_EMPTY_FOLLOWUP"
        invalid_narrowed_empty_followup_label_strategy["stages"][2]["scope_source"] = "FULL_SCOPE_AFTER_EMPTY_FOLLOWUP"
        invalid_narrowed_empty_followup_label_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_narrowed_empty_followup_label_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_narrowed_empty_followup_label",
                strategy_plan=invalid_narrowed_empty_followup_label_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "must not be `FULL_SCOPE_AFTER_EMPTY_FOLLOWUP` when deep_partition_followup.partition_ids is non-empty"
                in str(exc),
                "authoritative bundle compilation should reject empty-followup full-scope provenance labels on narrowed plans",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject narrowed plans that forge the empty-followup full-scope provenance label"
            )

        invalid_duplicate_stage_id_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_duplicate_stage_id_strategy["stages"].append(
            json.loads(json.dumps(invalid_duplicate_stage_id_strategy["stages"][1]))
        )
        invalid_duplicate_stage_id_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_duplicate_stage_id_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_duplicate_stage_id",
                strategy_plan=invalid_duplicate_stage_id_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "stages must contain unique stage_id values" in str(exc),
                "authoritative bundle compilation should reject duplicate stage_id entries",
            )
        else:
            raise AssertionError("review orchestration bundle must reject duplicate stage_id entries")

        invalid_unknown_stage_id_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_unknown_stage_id_strategy["stages"].append(
            {
                "stage_id": "post_closeout_shadow",
                "review_tier": "STRICT",
                "agent_profile": "gpt-5.4-xhigh",
                "scope_paths": ["tools/loop/review_a.py"],
                "scope_fingerprint": compute_review_scope_fingerprint(
                    repo_root=repo,
                    scope_paths=["tools/loop/review_a.py"],
                ),
                "closeout_eligible": False,
                "finding_policy": "ADVISORY_CONFIRM_REQUIRED",
                "selection_policy": "SHADOW_STAGE",
                "scope_source": "MANUAL_EFFECTIVE_SCOPE_OVERRIDE",
            }
        )
        invalid_unknown_stage_id_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_unknown_stage_id_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_unknown_stage_id",
                strategy_plan=invalid_unknown_stage_id_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "stages must only contain supported stage_id values" in str(exc),
                "authoritative bundle compilation should reject unknown stage_id entries that the graph compiler would otherwise ignore",
            )
        else:
            raise AssertionError("review orchestration bundle must reject unknown stage_id entries")

        invalid_reordered_stage_order_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_reordered_stage_order_strategy["stages"] = [
            dict(invalid_reordered_stage_order_strategy["stages"][2]),
            dict(invalid_reordered_stage_order_strategy["stages"][0]),
            dict(invalid_reordered_stage_order_strategy["stages"][1]),
        ]
        invalid_reordered_stage_order_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_reordered_stage_order_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_reordered_stage_order",
                strategy_plan=invalid_reordered_stage_order_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "stages must preserve the canonical helper-authored stage order exactly" in str(exc),
                "authoritative bundle compilation should reject replayed stage lists that only permute non-executable stage descriptor order",
            )
        else:
            raise AssertionError("review orchestration bundle must reject replayed stage-order permutations")

        invalid_forged_stage_descriptor_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_forged_stage_descriptor_strategy["stages"][1]["finding_policy"] = "ADVISORY_CONFIRM_REQUIRED"
        invalid_forged_stage_descriptor_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_forged_stage_descriptor_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_forged_stage_descriptor",
                strategy_plan=invalid_forged_stage_descriptor_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "strategy_plan.deep_partition_followup.finding_policy must remain `CONFIRM_OR_DISMISS_BEFORE_CLOSEOUT`"
                in str(exc),
                "authoritative bundle compilation should reject replayed stage descriptors that forge ignored static policy metadata",
            )
        else:
            raise AssertionError("review orchestration bundle must reject forged stage static-policy metadata")

        invalid_closeout_policy_flags_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        invalid_closeout_policy_flags_strategy["closeout_policy"]["intermediate_rounds_are_advisory"] = False
        invalid_closeout_policy_flags_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(invalid_closeout_policy_flags_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_invalid_closeout_policy_flags",
                strategy_plan=invalid_closeout_policy_flags_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "strategy_plan.closeout_policy.intermediate_rounds_are_advisory must remain `true`" in str(exc),
                "authoritative bundle compilation should reject replayed closeout_policy flag changes that would fork strategy provenance without changing executable semantics",
            )
        else:
            raise AssertionError("review orchestration bundle must reject forged closeout_policy flags")

        ignored_partition_metadata_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        original_partition_fingerprint = ignored_partition_metadata_strategy["strategy_fingerprint"]
        ignored_partition_metadata_strategy["partitions"][0]["partition_group"] = "FORGED_GROUP"
        ignored_partition_metadata_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(ignored_partition_metadata_strategy)
        )
        _assert(
            ignored_partition_metadata_strategy["strategy_fingerprint"] == original_partition_fingerprint,
            "ignored partition replay metadata must not perturb authoritative strategy_fingerprint",
        )
        ignored_partition_bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_ignored_partition_metadata",
            strategy_plan=ignored_partition_metadata_strategy,
            max_parallel_branches=3,
        )
        _assert(
            ignored_partition_bundle["composition_notes"]["strategy_fingerprint"] == original_partition_fingerprint,
            "authoritative bundle provenance must stay stable when ignored partition metadata changes",
        )

        ignored_deep_scope_source_strategy = _strategy(
            repo,
            followup_partition_ids=["part_03_tools_01"],
        )
        original_deep_scope_source_fingerprint = ignored_deep_scope_source_strategy["strategy_fingerprint"]
        ignored_deep_scope_source_strategy["stages"][1]["scope_source"] = "FORGED_IGNORED_SCOPE_SOURCE"
        ignored_deep_scope_source_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(ignored_deep_scope_source_strategy)
        )
        _assert(
            ignored_deep_scope_source_strategy["strategy_fingerprint"] == original_deep_scope_source_fingerprint,
            "ignored deep-stage replay metadata must not perturb authoritative strategy_fingerprint",
        )
        ignored_deep_scope_source_bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_ignored_deep_scope_source",
            strategy_plan=ignored_deep_scope_source_strategy,
            max_parallel_branches=3,
        )
        _assert(
            ignored_deep_scope_source_bundle["composition_notes"]["strategy_fingerprint"]
            == original_deep_scope_source_fingerprint,
            "authoritative bundle provenance must stay stable when ignored deep-stage metadata changes",
        )


def _assert_runtime_evidence() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_runtime_") as td:
        repo = Path(td)
        for rel in (
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ):
            _write(repo / rel)

        strategy = _strategy(
            repo,
            followup_partition_ids=["part_02_tests", "part_03_tools_01"],
        )
        graph = build_review_orchestration_graph(
                repo_root=repo,
            review_id="review_orchestration_runtime",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )
        rt = LoopGraphRuntime(repo_root=repo, run_key="c" * 64)
        summary = rt.execute(graph_spec=graph, node_executor=_pass_executor)
        _assert(summary["final_status"] == "PASSED", "compiled review orchestration graph should be executable")

        base = repo / "artifacts" / "loop_runtime" / "by_key" / ("c" * 64) / "graph"
        scheduler = _read_jsonl(base / "scheduler.jsonl")
        nested_lineage = _read_jsonl(base / "nested_lineage.jsonl")

        fast_node_ids = {
            str(node["node_id"])
            for node in graph["nodes"]
            if str(node["node_id"]).startswith("fast_partition_scan__")
        }
        parallel_scheduler_records = [rec for rec in scheduler if rec.get("execution_mode") == "PARALLEL"]
        _assert(parallel_scheduler_records, "fast partition scan batch must record parallel scheduler evidence")
        parallel_covered_node_ids = {
            str(node_id)
            for rec in parallel_scheduler_records
            for node_id in rec.get("batch_node_ids") or []
        }
        _assert(
            fast_node_ids.issubset(parallel_covered_node_ids),
            "scheduler evidence must cover every fast partition scan node that ran in parallel",
        )
        _assert(
            any(int(rec.get("parallel_width") or 0) >= 2 for rec in parallel_scheduler_records),
            "parallel scheduler evidence must admit a width greater than one",
        )
        _assert(
            all(int(rec.get("parallel_width") or 0) <= 3 for rec in parallel_scheduler_records),
            "parallel scheduler evidence must respect the configured max_parallel_branches limit",
        )
        _assert(
            sorted(rec["child_node_id"] for rec in nested_lineage)
            == [
                "deep_partition_followup__part_02_tests",
                "deep_partition_followup__part_03_tools_01",
            ],
            "deep follow-up nodes must emit nested-lineage evidence",
        )
        _assert(
            all(rec.get("child_state") == "PASSED" for rec in nested_lineage),
            "nested-lineage evidence must preserve child node terminal state",
        )


def _assert_advisory_failures_do_not_block_authoritative_closeout() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_negative_") as td:
        repo = Path(td)
        for rel in (
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ):
            _write(repo / rel)

        strategy = _strategy(
            repo,
            followup_partition_ids=["part_02_tests", "part_03_tools_01"],
        )
        graph = build_review_orchestration_graph(
                repo_root=repo,
            review_id="review_orchestration_negative",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )

        def _executor(node: dict) -> dict:
            node_id = str(node["node_id"])
            if node_id.startswith("deep_partition_followup__"):
                return {"state": "TRIAGED", "reason_code": "DEEP_STAGE_FAILED"}
            if node_id == "final_integrated_closeout":
                return {"state": "PASSED", "reason_code": "INTEGRATED_CLOSEOUT_EXECUTED"}
            return {"state": "PASSED", "reason_code": f"NODE_{node_id}_PASS"}

        rt = LoopGraphRuntime(repo_root=repo, run_key="d" * 64)
        summary = rt.execute(graph_spec=graph, node_executor=_executor)
        decisions = {str(item["node_id"]): dict(item) for item in summary["node_decisions"]}
        _assert(
            decisions["final_integrated_closeout"]["state"] == "PASSED",
            "final integrated closeout must still execute when advisory deep follow-up nodes are terminal failures",
        )
        _assert(
            decisions["final_integrated_closeout"]["reason_code"] == "INTEGRATED_CLOSEOUT_EXECUTED",
            "final integrated closeout must preserve its own executed reason_code in the negative path",
        )
        _assert(
            summary["final_status"] == "TRIAGED",
            "graph summary must preserve the worst upstream admitted terminal class even after the final closeout runs",
        )


def _assert_fast_stage_failures_block_authoritative_closeout() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_fast_fail_") as td:
        repo = Path(td)
        for rel in (
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ):
            _write(repo / rel)

        strategy = _strategy(
            repo,
            followup_partition_ids=["part_02_tests", "part_03_tools_01"],
        )
        graph = build_review_orchestration_graph(
                repo_root=repo,
            review_id="review_orchestration_fast_fail",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )

        def _executor(node: dict) -> dict:
            node_id = str(node["node_id"])
            if node_id == "fast_partition_scan__part_01_docs":
                return {"state": "TRIAGED", "reason_code": "FAST_STAGE_FAILED"}
            if node_id == "final_integrated_closeout":
                return {"state": "PASSED", "reason_code": "INTEGRATED_CLOSEOUT_SHOULD_NOT_RUN"}
            return {"state": "PASSED", "reason_code": f"NODE_{node_id}_PASS"}

        rt = LoopGraphRuntime(repo_root=repo, run_key="e" * 64)
        summary = rt.execute(graph_spec=graph, node_executor=_executor)
        decisions = {str(item["node_id"]): dict(item) for item in summary["node_decisions"]}
        _assert(
            decisions["finding_dedupe"]["reason_code"] == "UPSTREAM_BLOCKED",
            "finding_dedupe must remain blocked when a fast partition scan fails",
        )
        _assert(
            decisions["final_integrated_closeout"]["reason_code"] == "UPSTREAM_BLOCKED",
            "authoritative closeout must not execute when reconciliation never ran",
        )
        _assert(
            summary["final_status"] == "TRIAGED",
            "fast-stage failure path must preserve upstream triage without emitting executed closeout",
        )


def _assert_empty_followup_shape() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_empty_") as td:
        repo = Path(td)
        for rel in (
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ):
            _write(repo / rel)

        strategy = _strategy(
            repo,
            followup_partition_ids=[],
            effective_scope_paths=[],
        )
        graph = build_review_orchestration_graph(
                repo_root=repo,
            review_id="review_orchestration_empty_followup",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )
        node_ids = _node_ids(graph)
        _assert(
            not [node for node in node_ids if node.startswith("deep_partition_followup__")],
            "explicit no-escalation should not materialize deep follow-up nodes",
        )
        edges = _edges(graph)
        _assert(
            ("finding_dedupe", "final_integrated_closeout", "SERIAL") in edges,
            "explicit no-escalation must still preserve final integrated closeout",
        )
        final_node = next(node for node in graph["nodes"] if node["node_id"] == "final_integrated_closeout")
        _assert(
            "allow_terminal_predecessors" not in final_node,
            "explicit no-escalation should not enable terminal-predecessor closeout on the reconciliation edge",
        )
        bundle = build_review_orchestration_bundle(
                repo_root=repo,
            review_id="review_orchestration_empty_followup_bundle",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )
        final_manifest = _stage_manifest_map(bundle)["final_integrated_closeout"]
        _assert(
            "allow_terminal_predecessors" not in final_manifest,
            "explicit no-escalation manifest should omit allow_terminal_predecessors on authoritative closeout",
        )
        original_no_followup_fingerprint = strategy["strategy_fingerprint"]
        ignored_no_followup_deep_strategy = json.loads(json.dumps(strategy))
        ignored_no_followup_deep_strategy["stages"][1]["agent_profile"] = "gpt-5.4-xhigh"
        ignored_no_followup_deep_strategy["stages"][1]["scope_fingerprint"] = "FORGED_IGNORED_DEEP_SCOPE"
        ignored_no_followup_deep_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(ignored_no_followup_deep_strategy)
        )
        _assert(
            ignored_no_followup_deep_strategy["strategy_fingerprint"] == original_no_followup_fingerprint,
            "explicit no-followup replay plans must ignore inert deep-stage metadata when computing authoritative strategy_fingerprint",
        )
        ignored_no_followup_bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_empty_followup_ignored_deep_metadata",
            strategy_plan=ignored_no_followup_deep_strategy,
            max_parallel_branches=3,
        )
        _assert(
            ignored_no_followup_bundle["composition_notes"]["strategy_fingerprint"] == original_no_followup_fingerprint,
            "explicit no-followup bundle provenance must stay stable when inert deep-stage metadata changes",
        )
        try:
            _strategy(
                repo,
                followup_partition_ids=[],
                effective_scope_paths=strategy["effective_scope_paths"],
            )
        except ValueError as exc:
            _assert(
                "effective_scope_paths must stay within the merged selected partitions" in str(exc),
                "literal full-scope replay for empty followup should remain unsupported until the helper contract widens explicitly",
            )
        else:
            raise AssertionError("explicit no-followup helper replay must not claim literal full-scope effective_scope_paths support")
        blank_no_followup_deep_profile = json.loads(json.dumps(strategy))
        blank_no_followup_deep_profile["stages"][1]["agent_profile"] = ""
        blank_no_followup_deep_profile["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(blank_no_followup_deep_profile)
        )
        _assert(
            blank_no_followup_deep_profile["strategy_fingerprint"] == original_no_followup_fingerprint,
            "explicit no-followup replay plans must ignore a blank deep-stage agent profile when the deep stage is inert",
        )
        blank_no_followup_bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_empty_followup_blank_deep_profile",
            strategy_plan=blank_no_followup_deep_profile,
            max_parallel_branches=3,
        )
        _assert(
            blank_no_followup_bundle["composition_notes"]["strategy_fingerprint"] == original_no_followup_fingerprint,
            "explicit no-followup bundle provenance must stay stable when inert deep-stage agent_profile is blank",
        )

        invalid_empty_closeout_strategy = json.loads(json.dumps(strategy))
        invalid_empty_closeout_strategy["stages"][2]["scope_paths"] = []
        invalid_empty_closeout_strategy["stages"][2]["scope_fingerprint"] = _canonical_hash({"scope_paths": []})
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_empty_followup_invalid_closeout_empty",
                strategy_plan=invalid_empty_closeout_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "final_integrated_closeout.scope_paths must match the effective main scope exactly" in str(exc),
                "no-followup plans should reject empty authoritative closeout scope",
            )
        else:
            raise AssertionError(
                "explicit no-followup execution must reject empty final closeout scope"
            )

        invalid_widened_closeout_strategy = json.loads(json.dumps(strategy))
        invalid_widened_closeout_strategy["stages"][2]["scope_paths"] = [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
            "docs/contracts/unexpected.md",
        ]
        invalid_widened_closeout_strategy["stages"][2]["scope_fingerprint"] = _canonical_hash(
            {"scope_paths": invalid_widened_closeout_strategy["stages"][2]["scope_paths"]}
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_empty_followup_invalid_closeout_widened",
                strategy_plan=invalid_widened_closeout_strategy,
                max_parallel_branches=3,
            )
        except ValueError as exc:
            _assert(
                "final_integrated_closeout.scope_paths must match the effective main scope exactly" in str(exc)
                or "path does not exist: docs/contracts/unexpected.md" in str(exc),
                "no-followup plans should reject authoritative closeout scope that widens beyond the effective main scope, including nonexistent files",
            )
        else:
            raise AssertionError(
                "explicit no-followup execution must reject widened final closeout scope"
            )


def _assert_no_followup_reconciliation_failures_block_authoritative_closeout() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_no_followup_fail_") as td:
        repo = Path(td)
        for rel in (
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ):
            _write(repo / rel)

        strategy = _strategy(
            repo,
            followup_partition_ids=[],
            effective_scope_paths=[],
        )
        graph = build_review_orchestration_graph(
                repo_root=repo,
            review_id="review_orchestration_no_followup_fail",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )

        def _executor(node: dict) -> dict:
            node_id = str(node["node_id"])
            if node_id == "finding_dedupe":
                return {"state": "TRIAGED", "reason_code": "RECONCILIATION_FAILED"}
            if node_id == "final_integrated_closeout":
                return {"state": "PASSED", "reason_code": "INTEGRATED_CLOSEOUT_SHOULD_NOT_RUN"}
            return {"state": "PASSED", "reason_code": f"NODE_{node_id}_PASS"}

        rt = LoopGraphRuntime(repo_root=repo, run_key="f" * 64)
        summary = rt.execute(graph_spec=graph, node_executor=_executor)
        decisions = {str(item["node_id"]): dict(item) for item in summary["node_decisions"]}
        _assert(
            decisions["finding_dedupe"]["reason_code"] == "RECONCILIATION_FAILED",
            "no-followup path should surface the real reconciliation failure on finding_dedupe",
        )
        _assert(
            decisions["final_integrated_closeout"]["reason_code"] == "UPSTREAM_BLOCKED",
            "authoritative closeout must stay blocked when no-followup reconciliation fails",
        )
        _assert(
            summary["final_status"] == "TRIAGED",
            "no-followup reconciliation failure must preserve the upstream triage state",
        )


def _assert_no_followup_success_executes_authoritative_closeout() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_no_followup_success_") as td:
        repo = Path(td)
        for rel in (
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ):
            _write(repo / rel)

        strategy = _strategy(
            repo,
            followup_partition_ids=[],
            effective_scope_paths=[],
        )
        graph = build_review_orchestration_graph(
                repo_root=repo,
            review_id="review_orchestration_no_followup_success",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )

        def _executor(node: dict) -> dict:
            node_id = str(node["node_id"])
            if node_id == "final_integrated_closeout":
                return {"state": "PASSED", "reason_code": "INTEGRATED_CLOSEOUT_EXECUTED"}
            return {"state": "PASSED", "reason_code": f"NODE_{node_id}_PASS"}

        rt = LoopGraphRuntime(repo_root=repo, run_key="1" * 64)
        summary = rt.execute(graph_spec=graph, node_executor=_executor)
        decisions = {str(item["node_id"]): dict(item) for item in summary["node_decisions"]}
        _assert(
            decisions["finding_dedupe"]["state"] == "PASSED",
            "no-followup success path must still execute reconciliation before authoritative closeout",
        )
        _assert(
            decisions["final_integrated_closeout"]["reason_code"] == "INTEGRATED_CLOSEOUT_EXECUTED",
            "no-followup success path must execute the final integrated closeout stage",
        )
        _assert(
            summary["final_status"] == "PASSED",
            "no-followup success path must preserve a passing final graph summary",
        )


def _assert_large_partition_runtime_order_stays_lexically_stable() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_large_partition_order_") as td:
        repo = Path(td)
        large_scope: list[str] = []
        for idx in range(1, 106):
            rel = f"reviewscope/file_{idx:03d}.txt"
            _write(repo / rel)
            large_scope.append(rel)

        strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=large_scope,
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            max_files_per_partition=1,
            followup_partition_ids=[],
        )
        bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_large_partition_order",
            strategy_plan=strategy,
            max_parallel_branches=8,
        )
        fast_node_ids = list(bundle["composition_notes"]["fast_partition_node_ids"])
        _assert(
            fast_node_ids == sorted(fast_node_ids),
            "fast partition node ids must stay lexically order-stable past part_100+ so scheduler evidence does not fork frozen partition order",
        )
        graph = bundle["graph_spec"]
        graph_fast_node_ids = [
            str(node["node_id"])
            for node in graph["nodes"]
            if str(node["node_id"]).startswith("fast_partition_scan__")
        ]
        _assert(
            graph_fast_node_ids == fast_node_ids,
            "compiled graph must preserve lexically stable fast partition node order for large partition counts",
        )

        rt = LoopGraphRuntime(repo_root=repo, run_key="2" * 64)
        summary = rt.execute(graph_spec=graph, node_executor=_pass_executor)
        executed_fast_node_ids = [
            str(item["node_id"])
            for item in summary["node_decisions"]
            if str(item["node_id"]).startswith("fast_partition_scan__")
        ]
        _assert(
            executed_fast_node_ids == fast_node_ids,
            "runtime evidence must preserve the lexically stable fast partition node order for large partition counts",
        )


def _assert_historical_strategy_plan_replay_stays_compatible() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_legacy_strategy_") as td:
        repo = Path(td)
        scope_paths = [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ]
        for rel in (
            *scope_paths,
        ):
            _write(repo / rel)
        partitions = partition_review_scope_paths(
            repo_root=repo,
            scope_paths=scope_paths,
            max_files_per_partition=3,
        )

        current_strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope_paths,
            fast_profile="FAST_DEFAULT_PROVIDER",
            deep_profile="DEEP_DEFAULT_PROVIDER",
            strict_profile="STRICT_DEFAULT_PROVIDER",
            final_closeout_tier="STRICT",
            max_files_per_partition=3,
            followup_partition_ids=[str(part["partition_id"]) for part in partitions],
        )
        legacy_strategy = json.loads(json.dumps(current_strategy))
        legacy_strategy.pop("bounded_medium_profile", None)
        legacy_strategy.pop("strict_exception_profile", None)
        legacy_strategy.pop("partitioning_policy", None)
        legacy_strategy["closeout_policy"].pop("review_tier_policy", None)
        legacy_payload = _strategy_fingerprint_payload(legacy_strategy)
        legacy_payload.pop("bounded_medium_profile", None)
        legacy_payload.pop("strict_exception_profile", None)
        legacy_payload.pop("partitioning_policy", None)
        legacy_strategy["strategy_fingerprint"] = _canonical_hash(legacy_payload)

        bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_historical_replay",
            strategy_plan=legacy_strategy,
            max_parallel_branches=4,
            allow_historical_strategy_replay=True,
        )
        stage_manifest = _stage_manifest_map(bundle)
        final_stage = stage_manifest["final_integrated_closeout"]
        _assert(
            final_stage["review_tier"] == "STRICT",
            "historical strict strategy plans must still replay with their preserved strict closeout tier",
        )
        _assert(
            final_stage["agent_profile"] == "STRICT_DEFAULT_PROVIDER",
            "historical strategy replay must recover the preserved strict closeout profile from the staged plan",
        )
        _assert(
            bundle["composition_notes"]["strategy_fingerprint"] == legacy_strategy["strategy_fingerprint"],
            "historical strategy replay must preserve the accepted legacy strategy fingerprint",
        )
        validated_legacy = review_orchestration._validate_strategy_plan(
            repo_root=repo,
            strategy_plan=legacy_strategy,
            allow_historical_strategy_replay=True,
        )
        replay_bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_historical_replay_second_pass",
            strategy_plan=validated_legacy,
            max_parallel_branches=4,
            allow_historical_strategy_replay=True,
        )
        _assert(
            replay_bundle["composition_notes"]["strategy_fingerprint"] == legacy_strategy["strategy_fingerprint"],
            "validated legacy strategy plans must stay replayable without trusting caller-supplied omit keys",
        )


def _assert_pre_tier_provenance_strict_strategy_replay_stays_compatible() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_legacy_strict_tierless_replay_") as td:
        repo = Path(td)
        scope_paths = [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ]
        for rel in scope_paths:
            _write(repo / rel)
        partitions = partition_review_scope_paths(
            repo_root=repo,
            scope_paths=scope_paths,
            max_files_per_partition=3,
        )

        current_strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope_paths,
            fast_profile="FAST_DEFAULT_PROVIDER",
            deep_profile="DEEP_DEFAULT_PROVIDER",
            strict_profile="STRICT_DEFAULT_PROVIDER",
            final_closeout_tier="STRICT",
            max_files_per_partition=3,
            followup_partition_ids=[str(part["partition_id"]) for part in partitions],
        )
        legacy_strategy = json.loads(json.dumps(current_strategy))
        legacy_strategy.pop("bounded_medium_profile", None)
        legacy_strategy.pop("strict_exception_profile", None)
        legacy_strategy.pop("partitioning_policy", None)
        legacy_strategy["closeout_policy"].pop("review_tier_policy", None)
        legacy_payload = _legacy_pre_tier_provenance_strategy_fingerprint_payload(legacy_strategy)
        legacy_payload.pop("bounded_medium_profile", None)
        legacy_payload.pop("strict_exception_profile", None)
        legacy_payload.pop("partitioning_policy", None)
        legacy_strategy["strategy_fingerprint"] = _canonical_hash(legacy_payload)

        bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_historical_strict_tierless_replay",
            strategy_plan=legacy_strategy,
            max_parallel_branches=4,
            allow_historical_strategy_replay=True,
        )
        final_stage = _stage_manifest_map(bundle)["final_integrated_closeout"]
        _assert(
            final_stage["review_tier"] == "STRICT",
            "pre-tier-provenance historical strict strategy plans must still replay with their preserved strict closeout tier",
        )
        _assert(
            final_stage["agent_profile"] == "STRICT_DEFAULT_PROVIDER",
            "pre-tier-provenance historical strict strategy plans must still replay with their preserved strict closeout profile",
        )
        _assert(
            bundle["composition_notes"]["strategy_fingerprint"] == legacy_strategy["strategy_fingerprint"],
            "pre-tier-provenance historical strict strategy plans must preserve the accepted legacy strategy fingerprint",
        )


def _assert_legacy_non_strict_strategy_replay_recovers_strict_profile() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_legacy_medium_replay_") as td:
        repo = Path(td)
        scope_paths = [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ]
        for rel in scope_paths:
            _write(repo / rel)
        partitions = partition_review_scope_paths(
            repo_root=repo,
            scope_paths=scope_paths,
            max_files_per_partition=3,
        )

        current_strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope_paths,
            fast_profile="FAST_DEFAULT_PROVIDER",
            deep_profile="DEEP_DEFAULT_PROVIDER",
            strict_profile="STRICT_DEFAULT_PROVIDER",
            final_closeout_tier="MEDIUM",
            max_files_per_partition=3,
            followup_partition_ids=[str(part["partition_id"]) for part in partitions],
        )
        legacy_strategy = json.loads(json.dumps(current_strategy))
        legacy_strategy.pop("strict_exception_profile", None)
        legacy_strategy.pop("partitioning_policy", None)
        legacy_strategy["closeout_policy"].pop("review_tier_policy", None)
        legacy_payload = _strategy_fingerprint_payload(legacy_strategy)
        legacy_payload.pop("strict_exception_profile", None)
        legacy_payload.pop("partitioning_policy", None)
        legacy_strategy["strategy_fingerprint"] = _canonical_hash(legacy_payload)

        bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_historical_medium_replay",
            strategy_plan=legacy_strategy,
            max_parallel_branches=4,
            allow_historical_strategy_replay=True,
        )
        final_stage = _stage_manifest_map(bundle)["final_integrated_closeout"]
        _assert(
            final_stage["review_tier"] == "MEDIUM",
            "historical non-STRICT strategy plans must preserve their original medium closeout tier",
        )
        _assert(
            final_stage["agent_profile"] == "DEEP_DEFAULT_PROVIDER",
            "historical non-STRICT strategy plans must still replay with their preserved medium closeout profile",
        )
        validated_legacy = review_orchestration._validate_strategy_plan(
            repo_root=repo,
            strategy_plan=legacy_strategy,
            allow_historical_strategy_replay=True,
        )
        _assert(
            "strict_exception_profile" not in validated_legacy,
            "validated legacy non-STRICT strategy plans must preserve omitted strict_exception_profile in the replay payload",
        )
        _assert(
            "partitioning_policy" not in validated_legacy,
            "validated legacy non-STRICT strategy plans must preserve omitted partitioning_policy in the replay payload",
        )
        replay_bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_historical_medium_replay_second_pass",
            strategy_plan=validated_legacy,
            max_parallel_branches=4,
            allow_historical_strategy_replay=True,
        )
        _assert(
            replay_bundle["composition_notes"]["strategy_fingerprint"] == legacy_strategy["strategy_fingerprint"],
            "validated legacy non-STRICT strategy plans must stay replayable without rewriting their accepted strategy fingerprint",
        )


def _assert_tierless_strategy_replay_requires_explicit_historical_mode() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_tierless_requires_historical_mode_") as td:
        repo = Path(td)
        scope_paths = [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ]
        for rel in scope_paths:
            _write(repo / rel)
        partitions = partition_review_scope_paths(
            repo_root=repo,
            scope_paths=scope_paths,
            max_files_per_partition=3,
        )

        current_strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope_paths,
            fast_profile="FAST_DEFAULT_PROVIDER",
            deep_profile="DEEP_DEFAULT_PROVIDER",
            strict_profile="STRICT_DEFAULT_PROVIDER",
            final_closeout_tier="STRICT",
            max_files_per_partition=3,
            followup_partition_ids=[str(part["partition_id"]) for part in partitions],
        )
        tierless_strategy = json.loads(json.dumps(current_strategy))
        tierless_strategy.pop("bounded_medium_profile", None)
        tierless_strategy.pop("strict_exception_profile", None)
        tierless_strategy.pop("partitioning_policy", None)
        tierless_strategy["closeout_policy"].pop("review_tier_policy", None)
        legacy_payload = _strategy_fingerprint_payload(tierless_strategy)
        legacy_payload.pop("bounded_medium_profile", None)
        legacy_payload.pop("strict_exception_profile", None)
        legacy_payload.pop("partitioning_policy", None)
        tierless_strategy["strategy_fingerprint"] = _canonical_hash(legacy_payload)

        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_tierless_default_reject",
                strategy_plan=tierless_strategy,
                max_parallel_branches=4,
            )
        except ValueError as exc:
            _assert(
                "allow_historical_strategy_replay=True" in str(exc),
                "default bundle compilation must reject tierless MEDIUM/STRICT strategies unless the caller explicitly opts into historical replay mode",
            )
        else:
            raise AssertionError("tierless MEDIUM/STRICT strategies must require explicit historical replay mode")

        explicit_historical_bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_orchestration_tierless_historical_mode",
            strategy_plan=tierless_strategy,
            max_parallel_branches=4,
            allow_historical_strategy_replay=True,
        )
        explicit_historical_final_stage = _stage_manifest_map(explicit_historical_bundle)["final_integrated_closeout"]
        _assert(
            explicit_historical_final_stage["review_tier"] == "STRICT",
            "explicit historical replay mode must preserve the accepted strict closeout tier for supported legacy strategies",
        )
        review_tierless_only_strategy = json.loads(json.dumps(current_strategy))
        review_tierless_only_strategy["closeout_policy"].pop("review_tier_policy", None)
        review_tierless_only_strategy["strategy_fingerprint"] = _canonical_hash(
            _strategy_fingerprint_payload(review_tierless_only_strategy)
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_review_tier_policy_only_historical_bypass",
                strategy_plan=review_tierless_only_strategy,
                max_parallel_branches=4,
                allow_historical_strategy_replay=True,
            )
        except ValueError as exc:
            _assert(
                "supported legacy strategy plans" in str(exc),
                "historical replay mode must not act as a general bypass for current plans that only drop closeout_policy.review_tier_policy",
            )
        else:
            raise AssertionError("historical replay mode must reject current plans that only omit review_tier_policy")


def _assert_current_strategy_cannot_omit_present_legacy_fields_from_fingerprint() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_current_legacy_omit_") as td:
        repo = Path(td)
        scope_paths = [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ]
        for rel in scope_paths:
            _write(repo / rel)

        strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope_paths,
            fast_profile="FAST_DEFAULT_PROVIDER",
            deep_profile="DEEP_DEFAULT_PROVIDER",
            strict_profile="STRICT_DEFAULT_PROVIDER",
            final_closeout_tier="STRICT",
            max_files_per_partition=3,
            followup_partition_ids=["part_01_docs", "part_02_tests", "part_03_tools"],
        )
        forged_current_strict = json.loads(json.dumps(strategy))
        forged_current_strict["_legacy_strategy_fingerprint_omit_keys"] = [
            "bounded_medium_profile",
            "strict_exception_profile",
            "partitioning_policy",
        ]
        forged_current_strict["strategy_fingerprint"] = review_orchestration._expected_strategy_fingerprint(
            forged_current_strict,
            omit_top_level_keys=["bounded_medium_profile", "strict_exception_profile", "partitioning_policy"],
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_current_strict_legacy_omit_alias",
                strategy_plan=forged_current_strict,
                max_parallel_branches=4,
            )
        except ValueError as exc:
            _assert(
                "strategy_plan.strategy_fingerprint must match the canonical hash" in str(exc),
                "current strict strategies must reject legacy omit fingerprints when the omitted top-level fields are still present",
            )
        else:
            raise AssertionError("current strict strategies must not admit legacy omit aliases for present top-level fields")

        strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope_paths,
            fast_profile="FAST_DEFAULT_PROVIDER",
            deep_profile="DEEP_DEFAULT_PROVIDER",
            strict_profile="STRICT_DEFAULT_PROVIDER",
            final_closeout_tier="MEDIUM",
            max_files_per_partition=3,
            followup_partition_ids=["part_03_tools"],
        )
        forged_present_field = json.loads(json.dumps(strategy))
        forged_present_field["strict_exception_profile"] = "FORGED_STRICT_PROVIDER"
        forged_present_field["_legacy_strategy_fingerprint_omit_keys"] = [
            "strict_exception_profile",
            "partitioning_policy",
        ]
        forged_present_field["strategy_fingerprint"] = review_orchestration._expected_strategy_fingerprint(
            forged_present_field,
            omit_top_level_keys=["strict_exception_profile", "partitioning_policy"],
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_present_field_legacy_omit",
                strategy_plan=forged_present_field,
                max_parallel_branches=4,
            )
        except ValueError as exc:
            _assert(
                "strategy_plan.strategy_fingerprint must match the canonical hash" in str(exc),
                "current strategies must not be able to hide present strict_exception_profile drift behind a legacy omit hash",
            )
        else:
            raise AssertionError("current strategies must reject legacy omit hashes when the omitted field is still present")

        blanked_current_fields = json.loads(json.dumps(strategy))
        blanked_current_fields["bounded_medium_profile"] = ""
        blanked_current_fields["strict_exception_profile"] = ""
        blanked_current_fields["partitioning_policy"] = {}
        blanked_current_fields["_legacy_strategy_fingerprint_omit_keys"] = [
            "bounded_medium_profile",
            "strict_exception_profile",
            "partitioning_policy",
        ]
        blanked_current_fields["strategy_fingerprint"] = review_orchestration._expected_strategy_fingerprint(
            blanked_current_fields,
            omit_top_level_keys=["bounded_medium_profile", "strict_exception_profile", "partitioning_policy"],
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_blank_current_fields_legacy_alias",
                strategy_plan=blanked_current_fields,
                max_parallel_branches=4,
            )
        except ValueError as exc:
            _assert(
                "must preserve explicit top-level reviewer-profile provenance" in str(exc),
                "current strategies must not be able to masquerade as legacy by blanking mandatory provenance fields",
            )
        else:
            raise AssertionError("current strategies must reject legacy omit hashes when mandatory provenance fields are blanked")

        omitted_current_fields = json.loads(json.dumps(strategy))
        omitted_current_fields.pop("bounded_medium_profile", None)
        omitted_current_fields.pop("strict_exception_profile", None)
        omitted_current_fields.pop("partitioning_policy", None)
        omitted_current_fields["strategy_fingerprint"] = review_orchestration._expected_strategy_fingerprint(
            omitted_current_fields,
            omit_top_level_keys=["bounded_medium_profile", "strict_exception_profile", "partitioning_policy"],
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_missing_current_fields_legacy_alias",
                strategy_plan=omitted_current_fields,
                max_parallel_branches=4,
            )
        except ValueError as exc:
            _assert(
                "must preserve explicit top-level reviewer-profile provenance" in str(exc),
                "current strategies must not be able to masquerade as legacy by omitting mandatory provenance fields",
            )
        else:
            raise AssertionError("current strategies must reject legacy omit hashes when mandatory provenance fields are missing")

        current_missing_profiles = json.loads(json.dumps(strategy))
        current_missing_profiles.pop("bounded_medium_profile", None)
        current_missing_profiles.pop("strict_exception_profile", None)
        current_missing_profiles["strategy_fingerprint"] = strategy["strategy_fingerprint"]
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_missing_current_profile_provenance",
                strategy_plan=current_missing_profiles,
                max_parallel_branches=4,
            )
        except ValueError as exc:
            _assert(
                "must preserve explicit top-level reviewer-profile provenance" in str(exc),
                "current strategies must reject omitted reviewer-profile provenance even when stage descriptors could reconstruct it",
            )
        else:
            raise AssertionError("current strategies must reject omitted reviewer-profile provenance")

        current_missing_partitioning_policy = json.loads(json.dumps(strategy))
        current_missing_partitioning_policy.pop("partitioning_policy", None)
        current_missing_partitioning_policy["strategy_fingerprint"] = strategy["strategy_fingerprint"]
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_missing_current_partitioning_policy",
                strategy_plan=current_missing_partitioning_policy,
                max_parallel_branches=4,
            )
        except ValueError as exc:
            _assert(
                "must preserve explicit top-level partitioning_policy provenance" in str(exc),
                "current strategies must reject omitted partitioning_policy even when helper logic could infer it from partitions",
            )
        else:
            raise AssertionError("current strategies must reject omitted partitioning_policy provenance")

        dropped_strict_only = json.loads(json.dumps(strategy))
        dropped_strict_only.pop("strict_exception_profile", None)
        dropped_strict_only["strategy_fingerprint"] = review_orchestration._expected_strategy_fingerprint(
            dropped_strict_only,
            omit_top_level_keys=["strict_exception_profile"],
        )
        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_strict_only_legacy_omit",
                strategy_plan=dropped_strict_only,
                max_parallel_branches=4,
            )
        except ValueError as exc:
            _assert(
                "must preserve explicit top-level reviewer-profile provenance" in str(exc),
                "legacy omit fallback must reject unsupported one-field strict_exception_profile omissions",
            )
        else:
            raise AssertionError("legacy omit fallback must reject strict_exception_profile-only omissions on current strategies")


def _assert_low_closeout_strategies_reject_legacy_medium_backfill() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_low_legacy_backfill_") as td:
        repo = Path(td)
        scope_paths = [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ]
        for rel in scope_paths:
            _write(repo / rel)

        strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope_paths,
            fast_profile="FAST_DEFAULT_PROVIDER",
            deep_profile="DEEP_DEFAULT_PROVIDER",
            strict_profile="STRICT_DEFAULT_PROVIDER",
            final_closeout_tier="LOW",
            review_tier_policy="LOW_ONLY",
            max_files_per_partition=3,
            followup_partition_ids=[],
        )
        legacy_like_low = json.loads(json.dumps(strategy))
        legacy_like_low.pop("strict_exception_profile", None)
        legacy_like_low.pop("partitioning_policy", None)
        legacy_payload = _strategy_fingerprint_payload(legacy_like_low)
        legacy_payload.pop("strict_exception_profile", None)
        legacy_payload.pop("partitioning_policy", None)
        legacy_like_low["strategy_fingerprint"] = _canonical_hash(legacy_payload)

        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_low_closeout_legacy_backfill",
                strategy_plan=legacy_like_low,
                max_parallel_branches=4,
            )
        except ValueError as exc:
            _assert(
                "must preserve explicit top-level reviewer-profile provenance" in str(exc),
                "current LOW closeout strategies must not reuse the historical medium replay backfill for strict_exception_profile",
            )
        else:
            raise AssertionError("current LOW closeout strategies must reject historical medium-style strict backfill")


def _assert_legacy_fingerprint_omit_keys_cannot_hide_unrelated_drift() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_legacy_omit_guard_") as td:
        repo = Path(td)
        scope_paths = [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ]
        for rel in scope_paths:
            _write(repo / rel)
        partitions = partition_review_scope_paths(
            repo_root=repo,
            scope_paths=scope_paths,
            max_files_per_partition=3,
        )
        strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope_paths,
            fast_profile="FAST_DEFAULT_PROVIDER",
            deep_profile="DEEP_DEFAULT_PROVIDER",
            strict_profile="STRICT_DEFAULT_PROVIDER",
            final_closeout_tier="STRICT",
            max_files_per_partition=3,
            followup_partition_ids=[str(part["partition_id"]) for part in partitions],
        )
        forged = json.loads(json.dumps(strategy))
        forged["agent_provider_id"] = "FORGED_PROVIDER"
        forged["_legacy_strategy_fingerprint_omit_keys"] = ["agent_provider_id"]
        forged["strategy_fingerprint"] = review_orchestration._expected_strategy_fingerprint(
            forged,
            omit_top_level_keys=["agent_provider_id"],
        )

        try:
            build_review_orchestration_bundle(
                repo_root=repo,
                review_id="review_orchestration_forged_legacy_omit_keys",
                strategy_plan=forged,
                max_parallel_branches=4,
            )
        except ValueError as exc:
            _assert(
                "strategy_plan.strategy_fingerprint must match the canonical hash" in str(exc),
                "forged legacy omit keys must be rejected as stale authoritative input",
            )
        else:
            raise AssertionError("caller-supplied legacy omit keys must not hide unrelated strategy drift")


def _assert_graph_only_rejects_stale_legacy_fingerprint_hint() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_orchestration_graph_legacy_hint_") as td:
        repo = Path(td)
        scope_paths = [
            "docs/contracts/alpha.md",
            "docs/contracts/beta.md",
            "tests/contract/test_alpha.py",
            "tools/loop/review_a.py",
            "tools/loop/review_b.py",
            "tools/loop/review_c.py",
        ]
        for rel in scope_paths:
            _write(repo / rel)

        strategy = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope_paths,
            fast_profile="FAST_DEFAULT_PROVIDER",
            deep_profile="DEEP_DEFAULT_PROVIDER",
            strict_profile="STRICT_DEFAULT_PROVIDER",
            final_closeout_tier="STRICT",
            max_files_per_partition=3,
            followup_partition_ids=["part_01_docs", "part_02_tests", "part_03_tools"],
        )
        forged = json.loads(json.dumps(strategy))
        forged.pop("bounded_medium_profile", None)
        forged.pop("strict_exception_profile", None)
        forged.pop("partitioning_policy", None)
        forged["_legacy_strategy_fingerprint_omit_keys"] = [
            "bounded_medium_profile",
            "strict_exception_profile",
            "partitioning_policy",
        ]
        forged["strategy_fingerprint"] = "deadbeef"

        try:
            build_review_orchestration_graph(
                repo_root=repo,
                review_id="review_orchestration_graph_stale_legacy_hint",
                strategy_plan=forged,
                max_parallel_branches=4,
            )
        except ValueError as exc:
            _assert(
                "must preserve explicit top-level reviewer-profile provenance" in str(exc),
                "graph-only orchestration compilation must reject stale fingerprints even when legacy omit hints are supported",
            )
        else:
            raise AssertionError("graph-only orchestration compilation must not accept stale legacy fingerprints")


def main() -> int:
    _assert_compiled_graph_shape()
    _assert_runtime_evidence()
    _assert_advisory_failures_do_not_block_authoritative_closeout()
    _assert_fast_stage_failures_block_authoritative_closeout()
    _assert_empty_followup_shape()
    _assert_no_followup_reconciliation_failures_block_authoritative_closeout()
    _assert_no_followup_success_executes_authoritative_closeout()
    _assert_large_partition_runtime_order_stays_lexically_stable()
    _assert_historical_strategy_plan_replay_stays_compatible()
    _assert_pre_tier_provenance_strict_strategy_replay_stays_compatible()
    _assert_legacy_non_strict_strategy_replay_recovers_strict_profile()
    _assert_tierless_strategy_replay_requires_explicit_historical_mode()
    _assert_current_strategy_cannot_omit_present_legacy_fields_from_fingerprint()
    _assert_low_closeout_strategies_reject_legacy_medium_backfill()
    _assert_legacy_fingerprint_omit_keys_cannot_hide_unrelated_drift()
    _assert_graph_only_rejects_stale_legacy_fingerprint_hint()
    print("[loop-review-orchestration] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
