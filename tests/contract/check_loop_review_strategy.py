#!/usr/bin/env python3
"""Contract: staged narrowing and pyramid-review helpers stay deterministic."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop import (
    build_pyramid_review_plan,
    merge_partition_scope_paths,
    partition_review_scope_paths,
)


def _fail(msg: str) -> int:
    print(f"[loop-review-strategy][FAIL] {msg}", file=sys.stderr)
    return 2


def _write(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {path.name}\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loop_review_strategy_") as td:
        repo = Path(td)
        for rel in (
            "docs/contracts/a.md",
            "tests/contract/a.py",
            "tools/loop/a.py",
            "tools/loop/b.py",
            "tools/loop/c.py",
        ):
            _write(repo / rel)

        scope = [
            "tools/loop/c.py",
            "docs/contracts/a.md",
            "tools/loop/a.py",
            "tests/contract/a.py",
            "tools/loop/b.py",
        ]
        partitions = partition_review_scope_paths(
            repo_root=repo,
            scope_paths=scope,
            max_files_per_partition=2,
        )
        if len(partitions) != 4:
            return _fail("expected 4 deterministic partitions from docs/tests/tools grouping with tools chunked by size")
        partition_scopes = [part["scope_paths"] for part in partitions]
        expected_partition_scopes = [
            ["docs/contracts/a.md"],
            ["tests/contract/a.py"],
            ["tools/loop/a.py", "tools/loop/b.py"],
            ["tools/loop/c.py"],
        ]
        if partition_scopes != expected_partition_scopes:
            return _fail(f"unexpected partition scopes: {partition_scopes!r}")
        if any(not part.get("scope_fingerprint") for part in partitions):
            return _fail("each partition must persist a deterministic scope_fingerprint")

        merged = merge_partition_scope_paths(
            partitions=partitions,
            partition_ids=[partitions[1]["partition_id"], partitions[2]["partition_id"]],
        )
        if merged != ["tests/contract/a.py", "tools/loop/a.py", "tools/loop/b.py"]:
            return _fail(f"unexpected merged scope paths: {merged!r}")

        plan = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope,
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            max_files_per_partition=2,
            followup_partition_ids=[partitions[1]["partition_id"], partitions[2]["partition_id"]],
        )
        if plan.get("version") != "1":
            return _fail("plan version must be 1")
        if plan.get("strategy_id") != "review.pyramid_partition.v1":
            return _fail("unexpected strategy_id")
        if plan.get("partitioning_policy") != {
            "group_by": "TOP_LEVEL_SCOPE_PREFIX",
            "max_files_per_partition": 2,
        }:
            return _fail("plan must expose the helper-authored partitioning policy")
        if plan.get("full_scope_paths") != sorted(scope):
            return _fail("full_scope_paths must be normalized and sorted")
        stages = plan.get("stages") or []
        if [stage.get("stage_id") for stage in stages] != [
            "fast_partition_scan",
            "deep_partition_followup",
            "final_integrated_closeout",
        ]:
            return _fail("unexpected pyramid stage order")
        if stages[0].get("review_tier") != "FAST":
            return _fail("first stage must be FAST")
        if stages[0].get("closeout_eligible") is not False:
            return _fail("fast partition stage must not be closeout-eligible")
        if stages[0].get("finding_policy") != "ADVISORY_CONFIRM_REQUIRED":
            return _fail("fast partition stage must require confirmation for findings")
        expected_effective_scope = ["tests/contract/a.py", "tools/loop/a.py", "tools/loop/b.py"]
        if stages[1].get("candidate_partition_ids") != [part["partition_id"] for part in partitions]:
            return _fail("deep followup stage must keep the full candidate partition list for auditable narrowing")
        if stages[1].get("partition_ids") != [partitions[1]["partition_id"], partitions[2]["partition_id"]]:
            return _fail("deep followup stage must honor the selected followup partitions")
        if stages[1].get("scope_paths") != expected_effective_scope:
            return _fail("deep followup stage must preserve the narrowed effective scope")
        if stages[1].get("selection_policy") != "PARTITIONS_WITH_FINDINGS_OR_MANUAL_SELECTION":
            return _fail("deep followup stage must advertise finding-driven narrowing")
        if stages[2].get("closeout_eligible") is not True:
            return _fail("final integrated stage must be closeout-eligible")
        if stages[2].get("scope_paths") != expected_effective_scope:
            return _fail("final integrated stage must review the merged effective scope for the selected partitions")
        if stages[2].get("review_tier") != "STRICT":
            return _fail("final integrated stage must be STRICT")
        if stages[2].get("scope_source") != "MERGED_SELECTED_PARTITIONS":
            return _fail("final integrated stage must record that it comes from merged selected partitions")
        if plan.get("effective_scope_paths") != expected_effective_scope:
            return _fail("plan must expose the merged effective scope at top level")
        if plan.get("selected_partition_ids") != [partitions[1]["partition_id"], partitions[2]["partition_id"]]:
            return _fail("plan must expose the selected followup partitions")
        replayed_helper_plan = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope,
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            max_files_per_partition=2,
            followup_partition_ids=[partitions[1]["partition_id"], partitions[2]["partition_id"]],
            effective_scope_paths=merge_partition_scope_paths(
                partitions=partitions,
                partition_ids=[partitions[1]["partition_id"], partitions[2]["partition_id"]],
            ),
        )
        if replayed_helper_plan != plan:
            return _fail(
                "replaying helper-derived merged scope alongside followup_partition_ids must preserve "
                "the same plan provenance and fingerprint"
            )

        inferred_plan = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope,
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            max_files_per_partition=2,
            effective_scope_paths=expected_effective_scope,
        )
        inferred_stages = inferred_plan.get("stages") or []
        if inferred_plan.get("selected_partition_ids") != [partitions[1]["partition_id"], partitions[2]["partition_id"]]:
            return _fail("effective_scope_paths alone must infer the matching followup partitions")
        if inferred_stages[1].get("partition_ids") != [partitions[1]["partition_id"], partitions[2]["partition_id"]]:
            return _fail("deep followup stage must narrow when only effective_scope_paths is provided")
        if inferred_stages[1].get("scope_paths") != expected_effective_scope:
            return _fail("deep followup stage must preserve inferred effective scope at file granularity")
        if inferred_stages[2].get("scope_source") != "INFERRED_FROM_EFFECTIVE_SCOPE":
            return _fail("final integrated stage must record inferred effective-scope narrowing")

        manually_narrowed_plan = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope,
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            max_files_per_partition=2,
            followup_partition_ids=[partitions[1]["partition_id"], partitions[2]["partition_id"]],
            effective_scope_paths=["tools/loop/a.py"],
        )
        manual_stages = manually_narrowed_plan.get("stages") or []
        if manually_narrowed_plan.get("selected_partition_ids") != [partitions[2]["partition_id"]]:
            return _fail("manual effective scope override must drop selected partitions that no longer contain scope files")
        if manual_stages[1].get("partition_ids") != [partitions[2]["partition_id"]]:
            return _fail("deep followup stage must recompute partition_ids after manual file-level narrowing")
        if manual_stages[1].get("scope_paths") != ["tools/loop/a.py"]:
            return _fail("deep followup stage must preserve manual file-level narrowing exactly")
        if manual_stages[2].get("scope_source") != "MANUAL_EFFECTIVE_SCOPE_OVERRIDE":
            return _fail("final integrated stage must record manual effective-scope overrides")

        clean_fast_scan_plan = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope,
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            max_files_per_partition=2,
            followup_partition_ids=[],
        )
        clean_stages = clean_fast_scan_plan.get("stages") or []
        if clean_fast_scan_plan.get("selected_partition_ids") != []:
            return _fail("explicit empty followup_partition_ids must preserve the no-escalation outcome")
        if clean_stages[1].get("partition_ids") != []:
            return _fail("deep followup stage must show no selected partitions after a clean fast scan")
        if clean_stages[1].get("scope_paths") != []:
            return _fail("deep followup stage scope must be empty when nothing is escalated")
        if clean_stages[1].get("scope_source") != "NO_FOLLOWUP_SELECTION":
            return _fail("deep followup stage must record explicit no-followup selection")
        if clean_fast_scan_plan.get("effective_scope_paths") != sorted(scope):
            return _fail("final integrated closeout must stay on full scope when no follow-up partitions are selected")
        if clean_stages[2].get("scope_paths") != sorted(scope):
            return _fail("final integrated stage must stay full-scope after an empty follow-up selection")
        if clean_stages[2].get("scope_source") != "FULL_SCOPE_AFTER_EMPTY_FOLLOWUP":
            return _fail("final integrated stage must record that full-scope closeout followed an empty follow-up selection")

        clean_fast_scan_with_empty_scope = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=scope,
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            max_files_per_partition=2,
            followup_partition_ids=[],
            effective_scope_paths=[],
        )
        clean_with_empty_scope_stages = clean_fast_scan_with_empty_scope.get("stages") or []
        if clean_with_empty_scope_stages[1].get("scope_paths") != []:
            return _fail("empty effective_scope_paths with empty followup must still keep deep followup empty")
        if clean_fast_scan_with_empty_scope.get("effective_scope_paths") != sorted(scope):
            return _fail("empty effective_scope_paths with empty followup must keep integrated closeout on the full scope")

        large_scope: list[str] = []
        for idx in range(1, 106):
            rel = f"reviewscope/file_{idx:03d}.txt"
            _write(repo / rel)
            large_scope.append(rel)
        large_partitions = partition_review_scope_paths(
            repo_root=repo,
            scope_paths=large_scope,
            max_files_per_partition=1,
        )
        if len(large_partitions) != 105:
            return _fail("expected 105 one-file partitions for the large-scope follow-up ordering regression")
        large_partition_ids = [str(part["partition_id"]) for part in large_partitions]
        if large_partition_ids != sorted(large_partition_ids):
            return _fail("partition_review_scope_paths must emit lexically order-stable partition ids past part_100+")
        if not large_partition_ids[0].startswith("part_001_") or not large_partition_ids[99].startswith("part_100_"):
            return _fail("large-scope partition ids must zero-pad numeric prefixes so lexical and numeric order stay aligned")
        selected_large_followups = [
            large_partitions[99]["partition_id"],
            large_partitions[10]["partition_id"],
        ]
        large_plan = build_pyramid_review_plan(
            repo_root=repo,
            scope_paths=large_scope,
            fast_profile="gpt-5.4-low",
            deep_profile="gpt-5.4-medium",
            strict_profile="gpt-5.4-xhigh",
            max_files_per_partition=1,
            followup_partition_ids=selected_large_followups,
        )
        expected_large_followups = [
            large_partitions[10]["partition_id"],
            large_partitions[99]["partition_id"],
        ]
        if large_plan.get("selected_partition_ids") != expected_large_followups:
            return _fail(
                "explicit followup_partition_ids must preserve frozen partition order rather than lexicographically sorting part_100+ ids"
            )
        large_stages = large_plan.get("stages") or []
        if large_stages[1].get("partition_ids") != expected_large_followups:
            return _fail("deep followup stage must preserve frozen partition order for explicit part_100+ followup ids")
        expected_large_scope = merge_partition_scope_paths(
            partitions=large_partitions,
            partition_ids=expected_large_followups,
        )
        if large_stages[1].get("scope_paths") != expected_large_scope:
            return _fail("deep followup stage must preserve the merged scope lineage for explicit part_100+ followup ids")
        if large_stages[2].get("scope_paths") != expected_large_scope:
            return _fail("final integrated closeout stage must preserve merged scope lineage for explicit part_100+ followup ids")

    print("[loop-review-strategy] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
