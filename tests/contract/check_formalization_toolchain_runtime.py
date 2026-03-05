#!/usr/bin/env python3
"""Contract check: formalization deterministic toolchain runtime (Milestone 2)."""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import jsonschema
except Exception:
    print("[formalization-toolchain] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.formalization.adapters.upgrade_experimental_ledger import upgrade_ledger
from tools.formalization.anti_cheat import run_anti_cheat_gate
from tools.formalization.apply_decisions import apply_decisions_to_worklist
from tools.formalization.build_worklist import build_worklist
from tools.formalization.strong_validation import run_strong_validation_gate


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "docs" / "schemas" / name).read_text(encoding="utf-8"))


def _validate(obj: dict[str, Any], schema_name: str) -> None:
    schema = _load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
    errs = list(validator.iter_errors(obj))
    if errs:
        raise AssertionError(f"schema {schema_name} validation failed: {errs[0].message}")


def _review(state: str = "AUTO_EXTRACTED", confidence: float = 0.8, note: str = "test") -> dict[str, Any]:
    return {
        "state": state,
        "confidence": confidence,
        "uncertainty_score": round(1.0 - confidence, 4),
        "last_updated_utc": "2026-03-05T00:00:00Z",
        "reviewer": None,
        "note": note,
    }


def _assert_strong_validation_invocation_shape(
    invocations: list[tuple[list[str], Path, int]],
    *,
    expected_warn_target: str,
    expected_cwd: Path,
    expected_timeout: int,
) -> None:
    _assert(len(invocations) == 2, "strong validation should run exactly two commands per target file")
    warn_cmd, warn_cwd, warn_timeout = invocations[0]
    axiom_cmd, axiom_cwd, axiom_timeout = invocations[1]
    expected_warn = str(Path(expected_warn_target).resolve())
    warn_target = str(Path(warn_cmd[4]).resolve()) if len(warn_cmd) >= 5 else ""
    _assert(
        warn_cmd[:4] == ["lake", "env", "lean", "--error=warning"] and warn_target == expected_warn,
        "warning-as-error command shape mismatch",
    )
    _assert(len(warn_cmd) == 5, "warning-as-error command should be exactly 5 arguments")
    _assert(len(axiom_cmd) == 4, "axiom audit command should be `lake env lean <tmpfile>`")
    _assert(axiom_cmd[:3] == ["lake", "env", "lean"], "axiom audit command prefix mismatch")
    _assert(axiom_cmd[3].endswith(".lean"), "axiom audit target should be a .lean file")
    _assert(warn_cwd == expected_cwd.resolve(), "warning-as-error cwd mismatch")
    _assert(axiom_cwd == expected_cwd.resolve(), "axiom audit cwd mismatch")
    _assert(warn_timeout == expected_timeout, "warning-as-error timeout mismatch")
    _assert(axiom_timeout == expected_timeout, "axiom audit timeout mismatch")


def _experimental_v02(lean_file: Path) -> dict[str, Any]:
    return {
        "ledger_meta": {
            "ledger_schema_version": "0.2.0-temp",
            "canonical_json": True,
            "doc": {"doc_id": "demo.doc"},
            "extraction_pipeline": {},
            "id_policy": {},
        },
        "review_workflow": {
            "workflow_version": "0.2",
            "states": [
                "AUTO_EXTRACTED",
                "NEEDS_REVIEW",
                "HUMAN_CONFIRMED",
                "HUMAN_EDITED",
                "HUMAN_REJECTED",
                "LOCKED",
            ],
            "transitions": [],
            "thresholds": {},
        },
        "source_spans": [
            {
                "span_id": "span.1",
                "page": 1,
                "role": "claim_statement",
                "text_sha256": "a" * 64,
            }
        ],
        "claims": [
            {
                "claim_id": "demo.claim.1",
                "claim_kind": "THEOREM",
                "display_label": "Theorem 1",
                "dependency_ids": [],
                "in_paper_proof_status": "IMPLICIT",
                "statement_span_ids": ["span.1"],
                "review": _review("AUTO_EXTRACTED", 0.9, "claim"),
            }
        ],
        "proofs": [
            {
                "proof_id": "demo.proof.1",
                "for_claim_ids": ["demo.claim.1"],
                "proof_type": "IMPLICIT_ARGUMENT",
                "body_span_ids": ["span.1"],
                "uses_internal_claim_ids": [],
                "uses_external_result_ids": [],
                "review": _review("NEEDS_REVIEW", 0.45, "implicit"),
            }
        ],
        "external_results": [
            {
                "external_result_id": "demo.external.1",
                "name": "External theorem X",
                "source_kind": "PAPER_CITATION",
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.55, "pending external"),
            }
        ],
        "claim_proof_links": [
            {
                "link_id": "demo.link.1",
                "claim_id": "demo.claim.1",
                "proof_id": "demo.proof.1",
                "link_type": "IMPLICIT",
                "confidence": 0.5,
                "evidence_span_ids": ["span.1"],
                "review": _review("NEEDS_REVIEW", 0.5, "link"),
            }
        ],
        "formalization_bindings": [
            {
                "binding_id": "demo.bind.1",
                "claim_id": "demo.claim.1",
                "formalization_status": "PARTIAL",
                "external_dependency_status": "UNRESOLVED",
                "external_dependency_result_ids": ["demo.external.1"],
                "lean_target": {
                    "module": "Temp.Demo",
                    "file_path": str(lean_file),
                    "declaration_name": "passthrough",
                    "line": 2,
                },
                "clause_links": [
                    {
                        "clause_id": "demo.clause.1",
                        "clause_span_id": "span.1",
                        "raw_clause_text": "If h then h.",
                        "mapping_type": "CONCLUSION",
                        "confidence": 0.4,
                        "review": _review("NEEDS_REVIEW", 0.4, "clause"),
                    }
                ],
                "review": _review("NEEDS_REVIEW", 0.52, "binding"),
            }
        ],
        "lean_reverse_links": [
            {
                "reverse_link_id": "demo.rev.1",
                "lean_ref": {
                    "module": "Temp.Demo",
                    "file_path": str(lean_file),
                    "declaration_name": "passthrough",
                    "line": 2,
                    "column": 1,
                },
                "target": {
                    "claim_id": "demo.claim.1",
                    "clause_id": "demo.clause.1",
                    "span_id": "span.1",
                },
                "review": _review("NEEDS_REVIEW", 0.51, "reverse link"),
            }
        ],
        "index": {"by_kind": {}, "by_section": {}, "tokens": []},
        "audit": {"coverage": {}, "notes": []},
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="formalization_toolchain_") as td:
        root = Path(td)
        lean_file = root / "Demo.lean"
        lean_file.write_text(
            "namespace Temp\n"
            "theorem passthrough (h : True) : True := by\n"
            "  exact h\n"
            "end Temp\n",
            encoding="utf-8",
        )

        v02 = _experimental_v02(lean_file)
        upgraded, upgrade_report = upgrade_ledger(v02)
        _validate(upgraded, "FormalizationLedger.schema.json")
        _assert(upgrade_report["counts"]["clause_atoms"] >= 1, "upgrade should materialize clause_atoms")
        _assert(upgrade_report["counts"]["lean_anchors"] >= 1, "upgrade should materialize lean_anchors")

        # Adapter hardening: sanitize legacy structured tokens, unknown fields, and sparse proofs.
        edge_src = copy.deepcopy(v02)
        edge_src["index"]["tokens"] = [{"token": "tok1"}]
        edge_src["proofs"] = [
            {
                "proof_id": "demo.proof.edge",
                "body_span_ids": ["span.1"],
                "proof_heading_span_id": 456,
                "review": _review(),
            }
        ]
        edge_src["claims"][0].pop("review", None)
        edge_src["claims"][0]["heading_span_id"] = 123
        edge_src["source_spans"][0]["text_sha256"] = "BADHASH"
        edge_src["source_spans"][0]["page"] = "abc"
        edge_src["clause_atoms"] = [
            {
                "atom_id": "edge.atom.1",
                "claim_id": "demo.claim.1",
                "logic_role": "GENERAL",
                "span_id": "span.1",
                "text": "edge text",
                "review": _review(),
                "unexpected": 1,
            }
        ]
        edge_src["lean_anchors"] = [
            {
                "anchor_id": "edge.anchor.1",
                "anchor_role": "DECL_POINT",
                "origin": "AUTO",
                "lean_ref": {},
                "review": _review(),
                "unexpected": 1,
            }
        ]
        edge_src["atom_mappings"] = [
            {
                "mapping_id": "edge.map.1",
                "atom_id": "edge.atom.1",
                "anchor_id": "edge.anchor.1",
                "relation": "EXACT",
                "review": _review(),
                "evidence": [{"span_id": "span.1"}],
                "unexpected": 1,
            }
        ]
        edge_src["lean_reverse_links"][0]["target"]["clause_id"] = 123
        edge_src["lean_reverse_links"][0].pop("review", None)
        edge_upgraded, _ = upgrade_ledger(edge_src)
        _validate(edge_upgraded, "FormalizationLedger.schema.json")
        _assert(edge_upgraded["index"]["tokens"] == ["tok1"], "adapter should normalize tokens to string list")
        _assert("unexpected" not in edge_upgraded["clause_atoms"][0], "adapter should strip unknown clause_atom fields")
        _assert("unexpected" not in edge_upgraded["lean_anchors"][0], "adapter should strip unknown lean_anchor fields")
        _assert("unexpected" not in edge_upgraded["atom_mappings"][0], "adapter should strip unknown atom_mapping fields")
        _assert(edge_upgraded["proofs"][0]["for_claim_ids"], "adapter should enforce non-empty proof.for_claim_ids")
        _assert(edge_upgraded["claims"][0]["heading_span_id"] is None, "adapter should sanitize non-string heading_span_id")
        _assert(
            edge_upgraded["proofs"][0]["proof_heading_span_id"] is None,
            "adapter should sanitize non-string proof_heading_span_id",
        )
        _assert(edge_upgraded["lean_anchors"][0]["clause_id"] is None, "adapter should sanitize non-string clause_id to null")
        _assert(
            len(edge_upgraded["source_spans"][0]["text_sha256"]) == 64,
            "adapter should normalize invalid source_spans.text_sha256 to 64-hex hash",
        )
        _assert(edge_upgraded["source_spans"][0]["page"] == 1, "adapter should normalize malformed source_spans.page to 1")

        # Determinism hardening: missing reviews should not introduce wall-clock drift.
        determinism_src = copy.deepcopy(v02)
        determinism_src["claims"][0].pop("review", None)
        det_a, _ = upgrade_ledger(copy.deepcopy(determinism_src))
        det_b, _ = upgrade_ledger(copy.deepcopy(determinism_src))
        _assert(
            json.dumps(det_a, ensure_ascii=False, sort_keys=True) == json.dumps(det_b, ensure_ascii=False, sort_keys=True),
            "upgrade_ledger must stay deterministic when fallback review is used",
        )

        worklist = build_worklist(upgraded, threshold=0.0)
        _validate(worklist, "ProofCompletionWorklist.schema.json")
        _assert(worklist["count"] >= 1, "worklist should include at least one item")
        first = worklist["items"][0]
        _assert("EXTERNAL_DEPENDENCY_PENDING" in first["issue_codes"], "missing external dependency issue code")

        decisions = [
            {
                "entity_id": first["entity_id"],
                "entity_type": first["entity_type"],
                "to": "CODEX_ATTEMPTED",
                "parent_id": first.get("parent_id"),
            },
            {
                "entity_id": first["entity_id"],
                "entity_type": first["entity_type"],
                "to": "CODEX_ATTEMPTED",
                "parent_id": first.get("parent_id"),
            },
        ]
        updated_worklist, apply_report = apply_decisions_to_worklist(
            worklist=worklist,
            decisions=decisions,
            ledger_path="/tmp/demo_ledger.json",
            decisions_path="/tmp/demo_decisions.json",
        )
        _validate(apply_report, "ProofCompletionDecisionApplyReport.schema.json")
        _assert(apply_report["changed_count"] == 1, "apply report changed_count mismatch")
        _assert(apply_report["noop_count"] == 1, "apply report noop_count mismatch")
        _assert(apply_report["applied_count"] == 2, "apply report applied_count mismatch")
        _assert(updated_worklist["items"][0]["state"] == "CODEX_ATTEMPTED", "worklist state should be updated")

        # Wrong entity_type must be rejected (must not mutate by entity_id-only fallback).
        before_state = updated_worklist["items"][0]["state"]
        updated_worklist_2, wrong_type_report = apply_decisions_to_worklist(
            worklist=updated_worklist,
            decisions=[
                {
                    "entity_id": first["entity_id"],
                    "entity_type": "WRONG_TYPE",
                    "to": "GPT52PRO_ESCALATED",
                    "parent_id": first.get("parent_id"),
                }
            ],
            ledger_path="/tmp/demo_ledger.json",
            decisions_path="/tmp/demo_decisions.json",
        )
        _assert(wrong_type_report["rejected_count"] == 1, "wrong entity type decision should be rejected")
        _assert(updated_worklist_2["items"][0]["state"] == before_state, "wrong type decision must not mutate item state")

        # Non-string parent_id must be rejected (must not degrade into omitted-parent fallback).
        updated_worklist_3, bad_parent_report = apply_decisions_to_worklist(
            worklist=updated_worklist_2,
            decisions=[
                {
                    "entity_id": first["entity_id"],
                    "entity_type": first["entity_type"],
                    "to": "GPT52PRO_ESCALATED",
                    "parent_id": 123,
                }
            ],
            ledger_path="/tmp/demo_ledger.json",
            decisions_path="/tmp/demo_decisions.json",
        )
        _assert(bad_parent_report["rejected_count"] == 1, "non-string parent_id decision should be rejected")
        _assert(updated_worklist_3["items"][0]["state"] == before_state, "bad parent_id decision must not mutate state")

        # Duplicate target keys must be treated as ambiguous and rejected.
        duplicate_worklist = {
            "schema_version": "0.1",
            "generated_at_utc": "2026-03-05T00:00:00Z",
            "threshold": 0.0,
            "count": 2,
            "counts": {"NEW": 2},
            "items": [
                {
                    "entity_id": "dup.entity",
                    "entity_type": "FORMALIZATION_BINDING",
                    "parent_id": "dup.parent",
                    "state": "NEW",
                    "confidence": 0.4,
                    "uncertainty_score": 0.6,
                    "risk_score": 0.8,
                    "issue_codes": ["X"],
                    "issue_count": 1,
                    "suggested_action": "a",
                },
                {
                    "entity_id": "dup.entity",
                    "entity_type": "FORMALIZATION_BINDING",
                    "parent_id": "dup.parent",
                    "state": "NEW",
                    "confidence": 0.5,
                    "uncertainty_score": 0.5,
                    "risk_score": 0.7,
                    "issue_codes": ["Y"],
                    "issue_count": 1,
                    "suggested_action": "b",
                },
            ],
        }
        duplicate_after, duplicate_report = apply_decisions_to_worklist(
            worklist=duplicate_worklist,
            decisions=[
                {
                    "entity_id": "dup.entity",
                    "entity_type": "FORMALIZATION_BINDING",
                    "parent_id": "dup.parent",
                    "to": "CODEX_ATTEMPTED",
                }
            ],
            ledger_path="/tmp/demo_ledger.json",
            decisions_path="/tmp/demo_decisions.json",
        )
        _assert(duplicate_report["rejected_count"] == 1, "ambiguous duplicate-key target must be rejected")
        _assert(
            [x["state"] for x in duplicate_after["items"]] == ["NEW", "NEW"],
            "ambiguous duplicate-key decision must not mutate any row",
        )

        # Omitted parent_id must also reject when (entity_id, entity_type) maps to multiple parents.
        mixed_parent_worklist = {
            "schema_version": "0.1",
            "generated_at_utc": "2026-03-05T00:00:00Z",
            "threshold": 0.0,
            "count": 2,
            "counts": {"NEW": 2},
            "items": [
                {
                    "entity_id": "mix.entity",
                    "entity_type": "FORMALIZATION_BINDING",
                    "parent_id": None,
                    "state": "NEW",
                    "confidence": 0.4,
                    "uncertainty_score": 0.6,
                    "risk_score": 0.8,
                    "issue_codes": ["X"],
                    "issue_count": 1,
                    "suggested_action": "a",
                },
                {
                    "entity_id": "mix.entity",
                    "entity_type": "FORMALIZATION_BINDING",
                    "parent_id": "mix.parent",
                    "state": "NEW",
                    "confidence": 0.5,
                    "uncertainty_score": 0.5,
                    "risk_score": 0.7,
                    "issue_codes": ["Y"],
                    "issue_count": 1,
                    "suggested_action": "b",
                },
            ],
        }
        mixed_parent_after, mixed_parent_report = apply_decisions_to_worklist(
            worklist=mixed_parent_worklist,
            decisions=[
                {
                    "entity_id": "mix.entity",
                    "entity_type": "FORMALIZATION_BINDING",
                    "to": "CODEX_ATTEMPTED",
                }
            ],
            ledger_path="/tmp/demo_ledger.json",
            decisions_path="/tmp/demo_decisions.json",
        )
        _assert(mixed_parent_report["rejected_count"] == 1, "omitted parent_id with multi-parent target must be rejected")
        _assert(
            [x["state"] for x in mixed_parent_after["items"]] == ["NEW", "NEW"],
            "omitted parent_id ambiguity must not mutate any row",
        )

        anti_cheat_report = run_anti_cheat_gate(
            ledger=upgraded,
            target_lean_files=[lean_file],
            project_root=root,
            policy={
                "min_noncomment_proof_lines": 1,
                "fail_on_unmapped_atoms": True,
                "fail_on_unreferenced_anchors": True,
            },
        )
        codes = {x["code"] for x in anti_cheat_report["issues"]}
        _assert("OPAQUE_HYPOTHESIS_PATTERN" in codes, "anti-cheat should flag passthrough hypothesis pattern")

        # Anti-cheat hardening:
        # 1) grouped binders `(h1 h2 : P)` must be parsed;
        # 2) lemma declarations must be checked (not skipped as theorem-only);
        # 3) external dependency context must be binding-local even if claim_id is shared.
        lean_mix = root / "DemoMix.lean"
        lean_mix.write_text(
            "namespace Temp\n"
            "theorem passthrough_no_ext (h1 h2 : True) : True := by\n"
            "  exact h1\n"
            "lemma passthrough_with_ext (h : True) : True := by\n"
            "  exact h\n"
            "end Temp\n",
            encoding="utf-8",
        )
        mix_ledger = {
            "formalization_bindings": [
                {
                    "binding_id": "mix.bind.no_ext",
                    "claim_id": "mix.claim.shared",
                    "formalization_status": "FORMALIZED",
                    "external_dependency_status": "NONE",
                    "external_dependency_result_ids": [],
                    "lean_target": {
                        "file_path": str(lean_mix),
                        "declaration_name": "passthrough_no_ext",
                    },
                    "review": _review(),
                },
                {
                    "binding_id": "mix.bind.with_ext",
                    "claim_id": "mix.claim.shared",
                    "formalization_status": "FORMALIZED",
                    "external_dependency_status": "UNRESOLVED",
                    "external_dependency_result_ids": ["mix.external.1"],
                    "lean_target": {
                        "file_path": str(lean_mix),
                        "declaration_name": "passthrough_with_ext",
                    },
                    "review": _review(),
                },
            ],
            "clause_atoms": [],
            "lean_anchors": [],
            "atom_mappings": [],
        }
        mix_report = run_anti_cheat_gate(
            ledger=mix_ledger,
            target_lean_files=[lean_mix],
            project_root=root,
            policy={
                "min_noncomment_proof_lines": 1,
                "fail_on_unmapped_atoms": False,
                "fail_on_unreferenced_anchors": False,
            },
        )
        opaque_rows = [x for x in mix_report["issues"] if x["code"] == "OPAQUE_HYPOTHESIS_PATTERN"]
        by_binding = {x["ref"]["binding_id"]: x for x in opaque_rows if isinstance(x.get("ref"), dict)}
        _assert("mix.bind.no_ext" in by_binding, "grouped-binder theorem should produce OPAQUE_HYPOTHESIS_PATTERN")
        _assert("mix.bind.with_ext" in by_binding, "lemma declaration should be parsed and checked")
        _assert(by_binding["mix.bind.no_ext"]["severity"] == "ERROR", "no-external passthrough must be ERROR")
        _assert(by_binding["mix.bind.with_ext"]["severity"] == "WARN", "with-external passthrough should be WARN by default")
        _assert(
            "h1" in (by_binding["mix.bind.no_ext"]["ref"].get("forwarded_hypotheses") or []),
            "grouped binders should expose forwarded hypothesis names",
        )
        _assert(
            not any(x["code"] == "THEOREM_BLOCK_NOT_PARSED" and x.get("ref", {}).get("declaration_name") == "passthrough_with_ext" for x in mix_report["issues"]),
            "lemma declarations should not be skipped by theorem-only parser",
        )

        # Axiom allowlist regex should allow files under external_hooks/*.lean.
        external_hooks_dir = root / "external_hooks"
        external_hooks_dir.mkdir(parents=True, exist_ok=True)
        external_axiom_file = external_hooks_dir / "Allowed.lean"
        external_axiom_file.write_text(
            "axiom ext_hook_axiom : True\n",
            encoding="utf-8",
        )
        axiom_allow_report = run_anti_cheat_gate(
            ledger={
                "formalization_bindings": [],
                "clause_atoms": [],
                "lean_anchors": [],
                "atom_mappings": [],
            },
            target_lean_files=[external_axiom_file],
            project_root=root,
            policy={
                "min_noncomment_proof_lines": 1,
                "fail_on_unmapped_atoms": False,
                "fail_on_unreferenced_anchors": False,
            },
        )
        _assert(
            not any(
                x["code"] == "AXIOM_DECLARATION_PRESENT"
                and str(Path(x.get("ref", {}).get("file_path", "")).resolve()) == str(external_axiom_file.resolve())
                for x in axiom_allow_report["issues"]
            ),
            "axiom declarations under external_hooks/*.lean should be allowlisted by regex",
        )
        not_external_hooks_dir = root / "not_external_hooks"
        not_external_hooks_dir.mkdir(parents=True, exist_ok=True)
        not_external_axiom_file = not_external_hooks_dir / "Bypass.lean"
        not_external_axiom_file.write_text(
            "axiom not_allowed_axiom : True\n",
            encoding="utf-8",
        )
        not_allowed_report = run_anti_cheat_gate(
            ledger={
                "formalization_bindings": [],
                "clause_atoms": [],
                "lean_anchors": [],
                "atom_mappings": [],
            },
            target_lean_files=[not_external_axiom_file],
            project_root=root,
            policy={
                "min_noncomment_proof_lines": 1,
                "fail_on_unmapped_atoms": False,
                "fail_on_unreferenced_anchors": False,
            },
        )
        _assert(
            any(
                x["code"] == "AXIOM_DECLARATION_PRESENT"
                and str(Path(x.get("ref", {}).get("file_path", "")).resolve()) == str(not_external_axiom_file.resolve())
                for x in not_allowed_report["issues"]
            ),
            "allowlist regex must not suppress axioms outside external_hooks/*.lean directory",
        )

        # Anti-cheat should support ledger-derived relative target resolution via project_root.
        anti_relative_ledger = {
            "formalization_bindings": [
                {
                    "binding_id": "anti.rel.bind.1",
                    "claim_id": "anti.rel.claim.1",
                    "formalization_status": "FORMALIZED",
                    "lean_target": {"file_path": lean_file.name, "declaration_name": "passthrough"},
                    "review": _review(),
                }
            ],
            "clause_atoms": [],
            "lean_anchors": [],
            "atom_mappings": [],
        }
        anti_relative_report = run_anti_cheat_gate(
            ledger=anti_relative_ledger,
            target_lean_files=None,
            project_root=root,
            policy={
                "min_noncomment_proof_lines": 1,
                "fail_on_unmapped_atoms": False,
                "fail_on_unreferenced_anchors": False,
            },
        )
        anti_relative_codes = {x["code"] for x in anti_relative_report["issues"]}
        _assert("LEAN_FILE_MISSING" not in anti_relative_codes, "relative ledger target should resolve under project_root")
        _assert(
            "OPAQUE_HYPOTHESIS_PATTERN" in anti_relative_codes,
            "relative ledger target should be scanned and produce expected anti-cheat signal",
        )

        # Anti-cheat should block ledger-derived targets resolving outside project_root.
        anti_outside_ledger = {
            "formalization_bindings": [
                {
                    "binding_id": "anti.out.bind.1",
                    "claim_id": "anti.out.claim.1",
                    "formalization_status": "FORMALIZED",
                    "lean_target": {"file_path": "../outside/Bypass.lean", "declaration_name": "bypass"},
                    "review": _review(),
                }
            ],
            "clause_atoms": [],
            "lean_anchors": [],
            "atom_mappings": [],
        }
        anti_outside_report = run_anti_cheat_gate(
            ledger=anti_outside_ledger,
            target_lean_files=None,
            project_root=root,
            policy={
                "min_noncomment_proof_lines": 1,
                "fail_on_unmapped_atoms": False,
                "fail_on_unreferenced_anchors": False,
            },
        )
        anti_outside_codes = {x["code"] for x in anti_outside_report["issues"]}
        _assert(
            "LEAN_TARGET_OUTSIDE_PROJECT_ROOT" in anti_outside_codes,
            "outside-root ledger target should be reported explicitly",
        )

        # Default anti-cheat project_root fallback must not depend on process CWD.
        cwd_a = root / "cwd_a"
        cwd_b = root / "cwd_b"
        cwd_a.mkdir(parents=True, exist_ok=True)
        cwd_b.mkdir(parents=True, exist_ok=True)
        old_cwd = Path.cwd()
        try:
            os.chdir(cwd_a)
            fallback_a = run_anti_cheat_gate(
                ledger={"formalization_bindings": [], "clause_atoms": [], "lean_anchors": [], "atom_mappings": []},
                target_lean_files=None,
                policy={
                    "min_noncomment_proof_lines": 1,
                    "fail_on_unmapped_atoms": False,
                    "fail_on_unreferenced_anchors": False,
                },
            )
            os.chdir(cwd_b)
            fallback_b = run_anti_cheat_gate(
                ledger={"formalization_bindings": [], "clause_atoms": [], "lean_anchors": [], "atom_mappings": []},
                target_lean_files=None,
                policy={
                    "min_noncomment_proof_lines": 1,
                    "fail_on_unmapped_atoms": False,
                    "fail_on_unreferenced_anchors": False,
                },
            )
        finally:
            os.chdir(old_cwd)
        _assert(
            fallback_a["project_root"] == fallback_b["project_root"] == str(ROOT.resolve()),
            "default anti-cheat project_root fallback should be deterministic and CWD-independent",
        )

        strong_ok_invocations: list[tuple[list[str], Path, int]] = []

        def fake_runner(cmd: list[str], cwd: Path, timeout_sec: int) -> dict[str, Any]:
            strong_ok_invocations.append((list(cmd), cwd.resolve(), int(timeout_sec)))
            if "--error=warning" in cmd:
                return {"ok": True, "returncode": 0, "stdout": "", "stderr": "", "cmd": cmd}
            return {
                "ok": True,
                "returncode": 0,
                "stdout": "'Temp.passthrough' does not depend on any axioms\n",
                "stderr": "",
                "cmd": cmd,
            }

        strong_ok = run_strong_validation_gate(
            ledger=upgraded,
            project_root=root,
            include_nonformalized=True,
            timeout_sec=123,
            command_runner=fake_runner,
        )
        _assert(strong_ok["summary"]["pass"] is True, "strong validation should pass with fake no-axiom runner")
        _assert_strong_validation_invocation_shape(
            strong_ok_invocations,
            expected_warn_target=str(lean_file),
            expected_cwd=root,
            expected_timeout=123,
        )
        _assert(
            strong_ok["file_reports"][0]["axiom_audit"]["cmd"][-1] == "<TEMP_AXIOM_AUDIT_FILE>",
            "strong validation report should scrub temp axiom-audit path for determinism",
        )

        # Relative lean_target file_path should resolve against project_root (not process CWD).
        relative_ledger = copy.deepcopy(upgraded)
        relative_ledger["formalization_bindings"][0]["formalization_status"] = "FORMALIZED"
        relative_ledger["formalization_bindings"][0]["lean_target"]["file_path"] = lean_file.name
        relative_invocations: list[tuple[list[str], Path, int]] = []

        def fake_relative_runner(cmd: list[str], cwd: Path, timeout_sec: int) -> dict[str, Any]:
            relative_invocations.append((list(cmd), cwd.resolve(), int(timeout_sec)))
            if "--error=warning" in cmd:
                return {"ok": True, "returncode": 0, "stdout": "", "stderr": "", "cmd": cmd}
            return {
                "ok": True,
                "returncode": 0,
                "stdout": "'Temp.passthrough' does not depend on any axioms\n",
                "stderr": "",
                "cmd": cmd,
            }

        strong_relative = run_strong_validation_gate(
            ledger=relative_ledger,
            project_root=root,
            include_nonformalized=False,
            timeout_sec=111,
            command_runner=fake_relative_runner,
        )
        _assert(strong_relative["summary"]["target_files"] == 1, "relative file_path should resolve under project_root")
        _assert_strong_validation_invocation_shape(
            relative_invocations,
            expected_warn_target=str(lean_file),
            expected_cwd=root,
            expected_timeout=111,
        )

        # Relative path traversal outside project_root must be blocked with explicit error.
        outside_ledger = copy.deepcopy(upgraded)
        outside_ledger["formalization_bindings"][0]["formalization_status"] = "FORMALIZED"
        outside_ledger["formalization_bindings"][0]["lean_target"]["file_path"] = "../outside/Bypass.lean"
        outside_calls: list[list[str]] = []

        def fake_outside_runner(cmd: list[str], cwd: Path, timeout_sec: int) -> dict[str, Any]:
            outside_calls.append(list(cmd))
            return {
                "ok": True,
                "returncode": 0,
                "stdout": "",
                "stderr": "",
                "cmd": cmd,
            }

        strong_outside = run_strong_validation_gate(
            ledger=outside_ledger,
            project_root=root,
            include_nonformalized=False,
            timeout_sec=88,
            command_runner=fake_outside_runner,
        )
        outside_codes = {x["code"] for x in strong_outside["issues"]}
        _assert(
            "LEAN_TARGET_OUTSIDE_PROJECT_ROOT" in outside_codes,
            "outside-root target path should be reported explicitly",
        )
        _assert(strong_outside["summary"]["pass"] is False, "outside-root target path should fail strong validation")
        _assert(strong_outside["summary"]["target_files"] == 0, "outside-root path should be blocked before command run")
        _assert(len(outside_calls) == 0, "outside-root target must not invoke lean commands")

        # Strict target selection: COMPLETE should be treated as completed/formalized target.
        complete_ledger = copy.deepcopy(upgraded)
        complete_ledger["formalization_bindings"][0]["formalization_status"] = "COMPLETE"
        complete_invocations: list[tuple[list[str], Path, int]] = []

        def fake_complete_runner(cmd: list[str], cwd: Path, timeout_sec: int) -> dict[str, Any]:
            complete_invocations.append((list(cmd), cwd.resolve(), int(timeout_sec)))
            if "--error=warning" in cmd:
                return {"ok": True, "returncode": 0, "stdout": "", "stderr": "", "cmd": cmd}
            return {
                "ok": True,
                "returncode": 0,
                "stdout": "'Temp.passthrough' does not depend on any axioms\n",
                "stderr": "",
                "cmd": cmd,
            }

        strong_complete = run_strong_validation_gate(
            ledger=complete_ledger,
            project_root=root,
            include_nonformalized=False,
            timeout_sec=222,
            command_runner=fake_complete_runner,
        )
        _assert(strong_complete["summary"]["target_files"] == 1, "COMPLETE status should still be validated")
        _assert_strong_validation_invocation_shape(
            complete_invocations,
            expected_warn_target=str(lean_file),
            expected_cwd=root,
            expected_timeout=222,
        )

        # Formalized row with missing lean_target fields must not silently bypass validation.
        missing_target_ledger = {
            "formalization_bindings": [
                {
                    "binding_id": "missing.bind.1",
                    "claim_id": "demo.claim.1",
                    "formalization_status": "FORMALIZED",
                    "lean_target": {},
                    "review": _review(),
                }
            ]
        }

        strong_missing = run_strong_validation_gate(
            ledger=missing_target_ledger,
            project_root=root,
            include_nonformalized=False,
            timeout_sec=77,
            command_runner=lambda cmd, cwd, timeout_sec: {
                "ok": True,
                "returncode": 0,
                "stdout": "",
                "stderr": "",
                "cmd": cmd,
            },
        )
        missing_codes = {x["code"] for x in strong_missing["issues"]}
        _assert("LEAN_TARGET_MISSING_FIELDS" in missing_codes, "missing target fields should be reported")
        _assert(strong_missing["summary"]["pass"] is False, "missing target fields should fail strong validation")

        strong_bad_invocations: list[tuple[list[str], Path, int]] = []

        def fake_bad_axiom_runner(cmd: list[str], cwd: Path, timeout_sec: int) -> dict[str, Any]:
            strong_bad_invocations.append((list(cmd), cwd.resolve(), int(timeout_sec)))
            if "--error=warning" in cmd:
                return {"ok": True, "returncode": 0, "stdout": "", "stderr": "", "cmd": cmd}
            return {
                "ok": True,
                "returncode": 0,
                "stdout": "'Temp.passthrough' depends on axioms: [Foo.bar]\n",
                "stderr": "",
                "cmd": cmd,
            }

        strong_bad = run_strong_validation_gate(
            ledger=upgraded,
            project_root=root,
            include_nonformalized=True,
            timeout_sec=321,
            command_runner=fake_bad_axiom_runner,
        )
        bad_codes = {x["code"] for x in strong_bad["issues"]}
        _assert(
            "DISALLOWED_AXIOM_DEPENDENCY" in bad_codes,
            "strong validation should report disallowed axioms",
        )
        _assert_strong_validation_invocation_shape(
            strong_bad_invocations,
            expected_warn_target=str(lean_file),
            expected_cwd=root,
            expected_timeout=321,
        )

        # Failure-path determinism: stderr/stdout tails should scrub random temp audit file paths.
        def fake_axiom_command_fail_runner(cmd: list[str], cwd: Path, timeout_sec: int) -> dict[str, Any]:
            if "--error=warning" in cmd:
                return {"ok": True, "returncode": 0, "stdout": "", "stderr": "", "cmd": cmd}
            return {
                "ok": False,
                "returncode": 1,
                "stdout": "/tmp/leanatlas_axiom_audit_abcd1234/Demo.axiom_audit.lean:11: note: prelude\n",
                "stderr": "/tmp/leanatlas_axiom_audit_abcd1234/Demo.axiom_audit.lean:12: error: boom\n",
                "cmd": cmd,
            }

        strong_fail = run_strong_validation_gate(
            ledger=upgraded,
            project_root=root,
            include_nonformalized=True,
            timeout_sec=333,
            command_runner=fake_axiom_command_fail_runner,
        )
        fail_codes = {x["code"] for x in strong_fail["issues"]}
        _assert("AXIOM_AUDIT_COMMAND_FAILED" in fail_codes, "failing axiom command should be reported")
        file_stderr = "\n".join(str(x) for x in strong_fail["file_reports"][0]["axiom_audit"]["stderr_tail"])
        _assert(
            "leanatlas_axiom_audit_" not in file_stderr,
            "axiom_audit stderr tail should scrub random temp audit paths",
        )
        file_stdout = "\n".join(str(x) for x in strong_fail["file_reports"][0]["axiom_audit"]["stdout_tail"])
        _assert(
            "leanatlas_axiom_audit_" not in file_stdout,
            "axiom_audit stdout tail should scrub random temp audit paths",
        )
        fail_refs = [x.get("ref", {}) for x in strong_fail["issues"] if x.get("code") == "AXIOM_AUDIT_COMMAND_FAILED"]
        fail_ref_stderr = "\n".join(str(v) for ref in fail_refs for v in (ref.get("stderr_tail") or []))
        _assert(
            "leanatlas_axiom_audit_" not in fail_ref_stderr,
            "AXIOM_AUDIT_COMMAND_FAILED stderr tail should scrub random temp audit paths",
        )

        # Determinism: same input should produce same output hashes.
        upgraded_again, _ = upgrade_ledger(copy.deepcopy(v02))
        _assert(
            json.dumps(upgraded, ensure_ascii=False, sort_keys=True)
            == json.dumps(upgraded_again, ensure_ascii=False, sort_keys=True),
            "upgrade_ledger must be deterministic",
        )

    print("[formalization-toolchain-runtime] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
