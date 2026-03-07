#!/usr/bin/env python3
"""Contract: authoritative review supersession / reconciliation runtime."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

try:
    import jsonschema
except Exception:
    print("[loop-review-reconciliation-runtime] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop import (  # noqa: E402
    assert_review_reconciliation_ready,
    build_pyramid_review_plan,
    build_review_orchestration_bundle,
    persist_review_reconciliation,
    reconcile_review_rounds,
)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _write(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {path.name}\n", encoding="utf-8")


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
        "strict_profile": "gpt-5.4-medium",
        "max_files_per_partition": 2,
        "followup_partition_ids": followup_partition_ids,
    }
    if effective_scope_paths is not None:
        kwargs["effective_scope_paths"] = effective_scope_paths
    return build_pyramid_review_plan(**kwargs)


def _schema_validator() -> jsonschema.Draft202012Validator:
    schema_path = ROOT / "docs" / "schemas" / "ReviewSupersessionReconciliation.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
    )


def _assert_full_reconciliation_settles_findings() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_reconciliation_runtime_") as td:
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
            followup_partition_ids=["part_03_tools_01"],
            effective_scope_paths=["tools/loop/review_a.py"],
        )
        bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_reconciliation_demo",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )

        reconciliation = reconcile_review_rounds(
            review_id="review_reconciliation_demo",
            orchestration_bundle=bundle,
            review_rounds=[
                {
                    "review_round_id": "fast_docs_round1",
                    "node_id": "fast_partition_scan__part_01_docs",
                    "at_utc": "2026-03-08T10:00:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.docs.scope-mismatch",
                            "finding_fingerprint": "fp_docs_scope_mismatch",
                            "severity": "S2_MAJOR",
                        }
                    ],
                },
                {
                    "review_round_id": "fast_tools_round1",
                    "node_id": "fast_partition_scan__part_03_tools_01",
                    "at_utc": "2026-03-08T10:01:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.tools.shared-loop-bug",
                            "finding_fingerprint": "fp_shared_loop_bug",
                            "severity": "S2_MAJOR",
                        }
                    ],
                },
                {
                    "review_round_id": "deep_tools_round1",
                    "node_id": "deep_partition_followup__part_03_tools_01",
                    "at_utc": "2026-03-08T10:02:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.tools.shared-loop-bug",
                            "finding_fingerprint": "fp_shared_loop_bug",
                            "severity": "S2_MAJOR",
                        }
                    ],
                },
                {
                    "review_round_id": "final_closeout_round1",
                    "node_id": "final_integrated_closeout",
                    "at_utc": "2026-03-08T10:03:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.tools.shared-loop-bug",
                            "finding_fingerprint": "fp_shared_loop_bug",
                            "severity": "S2_MAJOR",
                        }
                    ],
                },
            ],
            supersession_records=[
                {
                    "superseded_review_round_id": "fast_tools_round1",
                    "superseding_review_round_id": "deep_tools_round1",
                    "supersede_reason": "DEEPER_SCOPE_REVIEW_REPLACED_FAST_SCAN",
                    "supersede_created_at_utc": "2026-03-08T10:02:30Z",
                }
            ],
        )
        errors = sorted(_schema_validator().iter_errors(reconciliation), key=lambda err: list(err.absolute_path))
        _assert(not errors, "reconciliation artifact must validate against ReviewSupersessionReconciliation.schema.json")
        assert_review_reconciliation_ready(reconciliation)

        finding_rows = {
            (str(item["source_review_round_id"]), str(item["finding_key"])): dict(item)
            for item in reconciliation["finding_records"]
        }
        _assert(
            finding_rows[("fast_docs_round1", "finding.docs.scope-mismatch")]["disposition"] == "DISMISSED",
            "advisory finding absent from final integrated closeout must settle as DISMISSED",
        )
        _assert(
            finding_rows[("fast_tools_round1", "finding.tools.shared-loop-bug")]["disposition"] == "SUPERSEDED",
            "earlier advisory finding with a matching final closeout finding must settle as SUPERSEDED",
        )
        _assert(
            finding_rows[("deep_tools_round1", "finding.tools.shared-loop-bug")]["disposition"] == "SUPERSEDED",
            "later advisory follow-up finding must still settle as SUPERSEDED once final integrated closeout confirms it",
        )
        _assert(
            finding_rows[("final_closeout_round1", "finding.tools.shared-loop-bug")]["disposition"] == "CONFIRMED",
            "authoritative final closeout occurrence must settle as CONFIRMED",
        )
        authoritative = {
            str(item["finding_key"]): dict(item)
            for item in reconciliation["authoritative_findings"]
        }
        _assert(
            authoritative["finding.tools.shared-loop-bug"]["final_disposition"] == "CONFIRMED",
            "authoritative finding set must expose final confirmed findings",
        )
        _assert(
            authoritative["finding.docs.scope-mismatch"]["final_disposition"] == "DISMISSED",
            "authoritative finding set must expose dismissed advisory findings",
        )
        _assert(
            reconciliation["closeout_ready"] is True,
            "reconciliation artifact must mark closeout_ready once all findings settle",
        )


def _assert_same_finding_key_requires_scope_lineage_or_explicit_supersession() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_reconciliation_scope_lineage_") as td:
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
            followup_partition_ids=["part_03_tools_01"],
            effective_scope_paths=["tools/loop/review_a.py"],
        )
        bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_reconciliation_scope_lineage",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )

        reconciliation = reconcile_review_rounds(
            review_id="review_reconciliation_scope_lineage",
            orchestration_bundle=bundle,
            review_rounds=[
                {
                    "review_round_id": "fast_docs_round1",
                    "node_id": "fast_partition_scan__part_01_docs",
                    "at_utc": "2026-03-08T10:00:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.shared.generic",
                            "finding_fingerprint": "fp_shared_generic_docs",
                        }
                    ],
                },
                {
                    "review_round_id": "fast_tools_round1",
                    "node_id": "fast_partition_scan__part_03_tools_01",
                    "at_utc": "2026-03-08T10:01:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.shared.generic",
                            "finding_fingerprint": "fp_shared_generic_tools",
                        }
                    ],
                },
                {
                    "review_round_id": "final_closeout_round1",
                    "node_id": "final_integrated_closeout",
                    "at_utc": "2026-03-08T10:02:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.shared.generic",
                            "finding_fingerprint": "fp_shared_generic_final",
                        }
                    ],
                },
            ],
            supersession_records=[
                {
                    "superseded_review_round_id": "fast_tools_round1",
                    "superseding_review_round_id": "final_closeout_round1",
                    "supersede_reason": "AUTHORITATIVE_CLOSEOUT_REPLACED_PARTITION_LOCAL_ADVISORY",
                    "supersede_created_at_utc": "2026-03-08T10:02:30Z",
                }
            ],
        )

        finding_rows = {
            (str(item["source_review_round_id"]), str(item["finding_key"])): dict(item)
            for item in reconciliation["finding_records"]
        }
        _assert(
            finding_rows[("fast_docs_round1", "finding.shared.generic")]["disposition"] == "DISMISSED",
            "same finding_key from an unrelated scope lineage must not be merged into another partition's authoritative closeout",
        )
        _assert(
            finding_rows[("fast_tools_round1", "finding.shared.generic")]["disposition"] == "SUPERSEDED",
            "explicit supersession should still connect related scope lineages for the same finding_key",
        )
        authoritative = [dict(item) for item in reconciliation["authoritative_findings"]]
        _assert(
            len(authoritative) == 2,
            "same finding_key emitted from unrelated scope lineages must produce distinct authoritative findings",
        )
        _assert(
            len({str(item["finding_group_key"]) for item in authoritative}) == 2,
            "distinct authoritative findings must carry distinct finding_group_key values",
        )


def _assert_supersession_records_capture_late_output_dispositions() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_reconciliation_supersession_") as td:
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
            followup_partition_ids=["part_01_docs"],
            effective_scope_paths=["docs/contracts/alpha.md"],
        )
        bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_reconciliation_supersession",
            strategy_plan=strategy,
            max_parallel_branches=2,
        )

        reconciliation = reconcile_review_rounds(
            review_id="review_reconciliation_supersession",
            orchestration_bundle=bundle,
            review_rounds=[
                {
                    "review_round_id": "fast_docs_old_same",
                    "node_id": "fast_partition_scan__part_01_docs",
                    "at_utc": "2026-03-08T11:00:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.docs.same-key",
                            "finding_fingerprint": "fp_same",
                        }
                    ],
                },
                {
                    "review_round_id": "fast_docs_old_unique",
                    "node_id": "fast_partition_scan__part_01_docs",
                    "at_utc": "2026-03-08T11:01:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.docs.unique-old",
                            "finding_fingerprint": "fp_unique_old",
                        }
                    ],
                },
                {
                    "review_round_id": "fast_docs_old_rejected",
                    "node_id": "fast_partition_scan__part_01_docs",
                    "at_utc": "2026-03-08T11:02:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.docs.rejected-old",
                            "finding_fingerprint": "fp_rejected_old",
                        }
                    ],
                },
                {
                    "review_round_id": "deep_docs_new",
                    "node_id": "deep_partition_followup__part_01_docs",
                    "at_utc": "2026-03-08T11:03:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.docs.same-key",
                            "finding_fingerprint": "fp_same",
                        }
                    ],
                },
                {
                    "review_round_id": "final_docs_closeout",
                    "node_id": "final_integrated_closeout",
                    "at_utc": "2026-03-08T11:04:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.docs.same-key",
                            "finding_fingerprint": "fp_same",
                        }
                    ],
                },
            ],
            supersession_records=[
                {
                    "superseded_review_round_id": "fast_docs_old_same",
                    "superseding_review_round_id": "deep_docs_new",
                    "supersede_reason": "DEEPER_SCOPE_REVIEW_REPLACED_FAST_SCAN",
                    "supersede_created_at_utc": "2026-03-08T11:02:30Z",
                },
                {
                    "superseded_review_round_id": "fast_docs_old_unique",
                    "superseding_review_round_id": "deep_docs_new",
                    "supersede_reason": "DEEPER_SCOPE_REVIEW_REPLACED_FAST_SCAN",
                    "supersede_created_at_utc": "2026-03-08T11:02:31Z",
                },
                {
                    "superseded_review_round_id": "fast_docs_old_rejected",
                    "superseding_review_round_id": "deep_docs_new",
                    "supersede_reason": "DEEPER_SCOPE_REVIEW_REPLACED_FAST_SCAN",
                    "supersede_created_at_utc": "2026-03-08T11:02:32Z",
                    "late_output_disposition": "REJECTED_WITH_RATIONALE",
                    "late_output_rationale": "Old fast-scan output contradicted the later narrowed review scope.",
                },
            ],
        )

        rounds = {
            str(item["review_round_id"]): dict(item)
            for item in reconciliation["review_rounds"]
        }
        _assert(
            rounds["fast_docs_old_same"]["ingestion_disposition"] == "NOOP_ALREADY_COVERED",
            "superseded late output with the same finding key should be recorded as NOOP_ALREADY_COVERED",
        )
        _assert(
            rounds["fast_docs_old_unique"]["ingestion_disposition"] == "APPLIED",
            "superseded late output with a unique finding should still be ingested as APPLIED",
        )
        _assert(
            rounds["fast_docs_old_rejected"]["ingestion_disposition"] == "REJECTED_WITH_RATIONALE",
            "superseded late output should support explicit REJECTED_WITH_RATIONALE tracking",
        )
        finding_rows = {
            (str(item["source_review_round_id"]), str(item["finding_key"])): dict(item)
            for item in reconciliation["finding_records"]
        }
        _assert(
            finding_rows[("fast_docs_old_rejected", "finding.docs.rejected-old")]["disposition"] == "DISMISSED",
            "rejected superseded output must settle its finding as DISMISSED with rationale",
        )
        _assert(
            finding_rows[("fast_docs_old_unique", "finding.docs.unique-old")]["disposition"] == "DISMISSED",
            "a unique superseded advisory finding still absent from final closeout must settle as DISMISSED",
        )


def _assert_missing_authoritative_closeout_is_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_reconciliation_missing_closeout_") as td:
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
            followup_partition_ids=["part_03_tools_01"],
            effective_scope_paths=["tools/loop/review_a.py"],
        )
        bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_reconciliation_missing_closeout",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )
        try:
            reconcile_review_rounds(
                review_id="review_reconciliation_missing_closeout",
                orchestration_bundle=bundle,
                review_rounds=[
                    {
                        "review_round_id": "fast_tools_round1",
                        "node_id": "fast_partition_scan__part_03_tools_01",
                        "at_utc": "2026-03-08T12:00:00Z",
                        "findings": [
                            {
                                "finding_id": "finding.tools.only-fast",
                                "finding_fingerprint": "fp_tools_only_fast",
                            }
                        ],
                    }
                ],
            )
        except ValueError as exc:
            _assert(
                "authoritative closeout round" in str(exc),
                "runtime should reject reconciliation attempts that do not include final integrated closeout evidence",
            )
        else:
            raise AssertionError("reconciliation runtime must require at least one authoritative closeout round")


def _assert_older_superseder_is_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_reconciliation_supersession_order_") as td:
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
            followup_partition_ids=["part_03_tools_01"],
            effective_scope_paths=["tools/loop/review_a.py"],
        )
        bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_reconciliation_supersession_order",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )

        try:
            reconcile_review_rounds(
                review_id="review_reconciliation_supersession_order",
                orchestration_bundle=bundle,
                review_rounds=[
                    {
                        "review_round_id": "fast_tools_round1",
                        "node_id": "fast_partition_scan__part_03_tools_01",
                        "at_utc": "2026-03-08T12:00:00Z",
                        "findings": [
                            {
                                "finding_id": "finding.tools.order-check",
                                "finding_fingerprint": "fp_order_check",
                            }
                        ],
                    },
                    {
                        "review_round_id": "deep_tools_round1",
                        "node_id": "deep_partition_followup__part_03_tools_01",
                        "at_utc": "2026-03-08T12:01:00Z",
                        "findings": [
                            {
                                "finding_id": "finding.tools.order-check",
                                "finding_fingerprint": "fp_order_check",
                            }
                        ],
                    },
                    {
                        "review_round_id": "final_closeout_round1",
                        "node_id": "final_integrated_closeout",
                        "at_utc": "2026-03-08T12:02:00Z",
                        "findings": [
                            {
                                "finding_id": "finding.tools.order-check",
                                "finding_fingerprint": "fp_order_check",
                            }
                        ],
                    },
                ],
                supersession_records=[
                    {
                        "superseded_review_round_id": "deep_tools_round1",
                        "superseding_review_round_id": "fast_tools_round1",
                        "supersede_reason": "INVALID_OLDER_ROUND_CANNOT_SUPERSEDE_NEWER_ROUND",
                        "supersede_created_at_utc": "2026-03-08T12:01:30Z",
                    }
                ],
            )
        except ValueError as exc:
            _assert(
                "newer" in str(exc),
                "supersession runtime must reject records that point to an older round as the superseder",
            )
        else:
            raise AssertionError("older superseder must be rejected")


def _assert_persisted_artifacts_are_append_only() -> None:
    with tempfile.TemporaryDirectory(prefix="loop_review_reconciliation_persist_") as td:
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
            followup_partition_ids=["part_03_tools_01"],
            effective_scope_paths=["tools/loop/review_a.py"],
        )
        bundle = build_review_orchestration_bundle(
            repo_root=repo,
            review_id="review_reconciliation_persist",
            strategy_plan=strategy,
            max_parallel_branches=3,
        )
        reconciliation_a = reconcile_review_rounds(
            review_id="review_reconciliation_persist",
            orchestration_bundle=bundle,
            review_rounds=[
                {
                    "review_round_id": "fast_tools_round1",
                    "node_id": "fast_partition_scan__part_03_tools_01",
                    "at_utc": "2026-03-08T13:00:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.tools.persisted",
                            "finding_fingerprint": "fp_tools_persisted",
                        }
                    ],
                },
                {
                    "review_round_id": "final_closeout_round1",
                    "node_id": "final_integrated_closeout",
                    "at_utc": "2026-03-08T13:01:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.tools.persisted",
                            "finding_fingerprint": "fp_tools_persisted",
                        }
                    ],
                },
            ],
        )
        reconciliation_b = reconcile_review_rounds(
            review_id="review_reconciliation_persist",
            orchestration_bundle=bundle,
            review_rounds=[
                {
                    "review_round_id": "fast_tools_round1",
                    "node_id": "fast_partition_scan__part_03_tools_01",
                    "at_utc": "2026-03-08T13:00:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.tools.persisted",
                            "finding_fingerprint": "fp_tools_persisted",
                        }
                    ],
                },
                {
                    "review_round_id": "final_closeout_round1",
                    "node_id": "final_integrated_closeout",
                    "at_utc": "2026-03-08T13:01:00Z",
                    "findings": [
                        {
                            "finding_id": "finding.tools.persisted",
                            "finding_fingerprint": "fp_tools_persisted",
                        }
                    ],
                },
            ],
        )
        _assert(
            reconciliation_a == reconciliation_b,
            "identical inputs must produce identical reconciliation artifacts",
        )
        persisted_a = persist_review_reconciliation(
            repo_root=repo,
            run_key="a" * 64,
            reconciliation=reconciliation_a,
        )
        persisted_b = persist_review_reconciliation(
            repo_root=repo,
            run_key="b" * 64,
            reconciliation=reconciliation_b,
        )
        persisted_c = persist_review_reconciliation(
            repo_root=repo,
            run_key="a" * 64,
            reconciliation=reconciliation_b,
        )
        ledger_path = Path(persisted_a["ledger_ref"])
        journal_path_a = Path(persisted_a["journal_ref"])
        journal_path_b = Path(persisted_b["journal_ref"])
        _assert(ledger_path.exists(), "persist_review_reconciliation must materialize a ledger artifact")
        _assert(journal_path_a.exists(), "persist_review_reconciliation must materialize an append-only journal")
        _assert(journal_path_b.exists(), "persist_review_reconciliation must materialize an append-only journal")
        _assert(
            persisted_a["ledger_ref"] == persisted_b["ledger_ref"],
            "identical reconciliation inputs must reuse the same immutable ledger artifact path even across run keys",
        )
        _assert(
            persisted_a["ledger_ref"] == persisted_c["ledger_ref"],
            "replaying the same ledger under the original run key must still reuse the same immutable ledger artifact path",
        )
        _assert(
            persisted_a["journal_ref"] != persisted_b["journal_ref"],
            "append-only persistence journals should stay scoped to their originating run key",
        )
        journal_rows_a = [
            json.loads(line)
            for line in journal_path_a.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        journal_rows_b = [
            json.loads(line)
            for line in journal_path_b.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        _assert(
            len(journal_rows_a) == 2,
            "repeated persistence under the same run key should append journal rows without forking the immutable ledger",
        )
        _assert(
            len(journal_rows_b) == 1,
            "a different run key should receive its own append-only journal stream",
        )
        _assert(
            journal_rows_a[0]["ledger_ref"] == str(ledger_path),
            "journal row must point to the immutable reconciliation ledger artifact",
        )
        _assert(
            journal_rows_a[1]["ledger_ref"] == str(ledger_path),
            "repeated journal rows must continue pointing at the same immutable reconciliation ledger artifact",
        )
        _assert(
            journal_rows_b[0]["ledger_ref"] == str(ledger_path),
            "cross-run persistence must still point at the same immutable reconciliation ledger artifact",
        )


def main() -> int:
    _assert_full_reconciliation_settles_findings()
    _assert_same_finding_key_requires_scope_lineage_or_explicit_supersession()
    _assert_supersession_records_capture_late_output_dispositions()
    _assert_missing_authoritative_closeout_is_rejected()
    _assert_older_superseder_is_rejected()
    _assert_persisted_artifacts_are_append_only()
    print("[loop-review-reconciliation-runtime] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
