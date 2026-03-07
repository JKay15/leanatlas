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

from tools.loop import (  # noqa: E402
    LoopGraphRuntime,
    build_pyramid_review_plan,
    build_review_orchestration_bundle,
    build_review_orchestration_graph,
    compute_review_scope_fingerprint,
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


def _strategy_fingerprint_payload(plan: dict) -> dict:
    partition_keys = ("partition_id", "scope_paths", "scope_fingerprint")
    stage_keys = {
        "fast_partition_scan": ("stage_id", "agent_profile", "partition_ids"),
        "deep_partition_followup": (
            "stage_id",
            "agent_profile",
            "partition_ids",
            "scope_paths",
            "scope_fingerprint",
        ),
        "final_integrated_closeout": (
            "stage_id",
            "agent_profile",
            "scope_paths",
            "scope_fingerprint",
            "scope_source",
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
            )
        authoritative_stages.append({key: stage.get(key) for key in keys})
    return {
        "version": str(plan.get("version") or ""),
        "strategy_id": str(plan.get("strategy_id") or ""),
        "agent_provider_id": str(plan.get("agent_provider_id") or ""),
        "partitioning_policy": dict(plan.get("partitioning_policy") or {}),
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


def _strategy(repo: Path, *, followup_partition_ids: list[str], effective_scope_paths: list[str] | None = None) -> dict:
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
            "agent_profile" not in stage_manifest["review_intake"],
            "non-review orchestration nodes must omit null agent_profile placeholders",
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
            stage_manifest["deep_partition_followup__part_02_tests"]["scope_fingerprint_basis"] == "REPO_FILE_BYTES",
            "deep stage manifest must record repository-byte fingerprint semantics when a full partition is replayed unchanged",
        )
        _assert(
            stage_manifest["final_integrated_closeout"]["allow_terminal_predecessors"] is True,
            "final closeout manifest must record sink execution after terminal advisory stages",
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
            reconciliation.get("finding_disposition_enum") == ["CONFIRMED", "DISMISSED", "SUPERSEDED"],
            "bundle must expose deterministic reconciliation dispositions",
        )
        _assert(
            reconciliation.get("required_fields")
            == [
                "finding_key",
                "source_stage_id",
                "source_partition_id",
                "disposition",
                "selected_partition_ids",
                "effective_scope_paths",
                "effective_scope_fingerprint",
            ],
            "bundle must require machine-readable finding-dedupe lineage",
        )

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
                "invalid final closeout scope should explain that STRICT closeout cannot widen or shrink beyond the effective main scope",
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
                "authoritative bundle compilation should reject top-level provenance drift before strict closeout metadata is compiled",
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
                "strategy_plan.partitioning_policy.max_files_per_partition must remain the helper-authored integer chunk size"
                in str(exc),
                "authoritative bundle compilation should reject replayed partitioning policies that coerce a non-integer chunk size into a no-op fingerprint fork",
            )
        else:
            raise AssertionError(
                "review orchestration bundle must reject replayed partitioning policies that encode chunk size as a string"
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
                return {"state": "PASSED", "reason_code": "STRICT_CLOSEOUT_EXECUTED"}
            return {"state": "PASSED", "reason_code": f"NODE_{node_id}_PASS"}

        rt = LoopGraphRuntime(repo_root=repo, run_key="d" * 64)
        summary = rt.execute(graph_spec=graph, node_executor=_executor)
        decisions = {str(item["node_id"]): dict(item) for item in summary["node_decisions"]}
        _assert(
            decisions["final_integrated_closeout"]["state"] == "PASSED",
            "final integrated closeout must still execute when advisory deep follow-up nodes are terminal failures",
        )
        _assert(
            decisions["final_integrated_closeout"]["reason_code"] == "STRICT_CLOSEOUT_EXECUTED",
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
                return {"state": "PASSED", "reason_code": "STRICT_CLOSEOUT_SHOULD_NOT_RUN"}
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
                return {"state": "PASSED", "reason_code": "STRICT_CLOSEOUT_SHOULD_NOT_RUN"}
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
                return {"state": "PASSED", "reason_code": "STRICT_CLOSEOUT_EXECUTED"}
            return {"state": "PASSED", "reason_code": f"NODE_{node_id}_PASS"}

        rt = LoopGraphRuntime(repo_root=repo, run_key="1" * 64)
        summary = rt.execute(graph_spec=graph, node_executor=_executor)
        decisions = {str(item["node_id"]): dict(item) for item in summary["node_decisions"]}
        _assert(
            decisions["finding_dedupe"]["state"] == "PASSED",
            "no-followup success path must still execute reconciliation before authoritative closeout",
        )
        _assert(
            decisions["final_integrated_closeout"]["reason_code"] == "STRICT_CLOSEOUT_EXECUTED",
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


def main() -> int:
    _assert_compiled_graph_shape()
    _assert_runtime_evidence()
    _assert_advisory_failures_do_not_block_authoritative_closeout()
    _assert_fast_stage_failures_block_authoritative_closeout()
    _assert_empty_followup_shape()
    _assert_no_followup_reconciliation_failures_block_authoritative_closeout()
    _assert_no_followup_success_executes_authoritative_closeout()
    _assert_large_partition_runtime_order_stays_lexically_stable()
    print("[loop-review-orchestration] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
