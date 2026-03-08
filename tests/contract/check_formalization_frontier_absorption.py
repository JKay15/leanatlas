#!/usr/bin/env python3
"""Contract: formalization frontier helpers must exist on committed mainline paths."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import jsonschema
except Exception:
    print("[formalization-frontier] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> int:
    print(f"[formalization-frontier][FAIL] {msg}", file=sys.stderr)
    return 2


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "docs" / "schemas" / name).read_text(encoding="utf-8"))


def _validate(obj: dict[str, Any], schema_name: str) -> None:
    schema = _load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
    errs = list(validator.iter_errors(obj))
    if errs:
        raise AssertionError(f"{schema_name} validation failed: {errs[0].message}")


def _review(state: str = "NEEDS_REVIEW", confidence: float = 0.5, note: str = "test") -> dict[str, Any]:
    return {
        "state": state,
        "confidence": confidence,
        "uncertainty_score": round(1.0 - confidence, 4),
        "last_updated_utc": "2026-03-08T00:00:00Z",
        "reviewer": None,
        "note": note,
    }


def _ledger(lean_file: Path) -> dict[str, Any]:
    return {
        "ledger_meta": {
            "ledger_schema_version": "0.3.0",
            "canonical_json": True,
            "doc": {"doc_id": "demo.doc"},
            "extraction_pipeline": {},
            "id_policy": {},
        },
        "review_workflow": {
            "workflow_version": "0.3",
            "states": [
                "AUTO_EXTRACTED",
                "NEEDS_REVIEW",
                "HUMAN_CONFIRMED",
                "HUMAN_EDITED",
                "HUMAN_REJECTED",
                "LOCKED",
            ],
            "transitions": [],
            "thresholds": {"auto_extracted_min_confidence": 0.78},
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
                "uses_external_result_ids": ["demo.external.1"],
                "review": _review("NEEDS_REVIEW", 0.45, "proof"),
            }
        ],
        "external_results": [
            {
                "external_result_id": "demo.external.1",
                "name": "Bandit Theory Book",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Lattimore and Szepesvari (2020)",
                "citation_authors": ["Tor Lattimore", "Csaba Szepesvari"],
                "citation_year": 2020,
                "citation_keys_detected": ["lattimore2020bandit"],
                "retrieval_queries": ["lattimore2020bandit Bandit Theory"],
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.55, "external"),
            },
            {
                "external_result_id": "demo.external.2",
                "name": "Unused Reference",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Unused and Example (2024)",
                "citation_authors": ["Uma Unused", "Eli Example"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.4, "external-unused"),
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
                    "declaration_name": "demo_decl",
                    "line": 2,
                    "column": 1,
                },
                "clause_links": [
                    {
                        "clause_id": "demo.clause.eq_1",
                        "clause_span_id": "span.1",
                        "raw_clause_text": "Equation (1) implies the desired bound.",
                        "mapping_type": "CONCLUSION",
                        "confidence": 0.4,
                        "equation_refs": [1],
                        "review": _review("NEEDS_REVIEW", 0.4, "clause"),
                    }
                ],
                "review": _review("NEEDS_REVIEW", 0.52, "binding"),
            }
        ],
        "lean_reverse_links": [
            {
                "reverse_link_id": "demo.rev.1",
                "link_origin": "AUTO_FROM_BINDING",
                "lean_ref": {
                    "module": "Temp.Demo",
                    "file_path": str(lean_file),
                    "declaration_name": "demo_decl",
                    "line": 2,
                    "column": 1,
                },
                "target": {
                    "claim_id": "demo.claim.1",
                    "clause_id": "demo.clause.eq_1",
                    "span_id": "span.1",
                },
                "review": _review("NEEDS_REVIEW", 0.51, "reverse link"),
            }
        ],
        "clause_atoms": [
            {
                "atom_id": "demo.atom.1",
                "parent_clause_id": "demo.clause.eq_1",
                "claim_id": "demo.claim.1",
                "span_id": "span.1",
                "text": "desired bound",
                "logic_role": "CONCLUSION",
                "alignment_hint": "",
                "source": "AUTO_FROM_CLAUSE_LINK",
                "review": _review("NEEDS_REVIEW", 0.4, "atom"),
                "notes": "",
            }
        ],
        "lean_anchors": [
            {
                "anchor_id": "demo.anchor.1",
                "origin": "AUTO_FROM_REVERSE_LINK",
                "anchor_role": "DECL_POINT",
                "claim_id": "demo.claim.1",
                "clause_id": "demo.clause.eq_1",
                "span_id": "span.1",
                "lean_ref": {
                    "module": "Temp.Demo",
                    "file_path": str(lean_file),
                    "declaration_name": "demo_decl",
                    "line": 2,
                    "column": 1,
                },
                "review": _review("NEEDS_REVIEW", 0.51, "anchor"),
                "notes": "",
            }
        ],
        "atom_mappings": [
            {
                "mapping_id": "demo.map.1",
                "atom_id": "demo.atom.1",
                "anchor_id": "demo.anchor.1",
                "relation": "HEURISTIC",
                "mismatch_kind": "NONE",
                "confidence": 0.4,
                "evidence": ["span.1"],
                "review": _review("NEEDS_REVIEW", 0.4, "mapping"),
                "notes": "",
            }
        ],
        "index": {"by_kind": {}, "by_section": {}, "tokens": []},
        "audit": {"coverage": {}, "notes": []},
    }


def main() -> int:
    try:
        from tools.formalization.external_source_pack import build_external_source_pack
        from tools.formalization.resync_reverse_links import resync_annotation_reverse_links
        from tools.formalization.review_todo import build_review_todo
        from tools.formalization.source_enrichment import enrich_ledger_from_sources
    except Exception as ex:  # noqa: BLE001
        return _fail(f"missing committed formalization frontier helper surface: {ex}")

    for rel in (
        "tools/formalization/external_source_pack.py",
        "tools/formalization/source_enrichment.py",
        "tools/formalization/review_todo.py",
        "tools/formalization/resync_reverse_links.py",
        "docs/schemas/ExternalSourcePack.schema.json",
    ):
        if not (ROOT / rel).exists():
            return _fail(f"missing committed mainline file: {rel}")

    ledger_contract = (ROOT / "docs" / "contracts" / "FORMALIZATION_LEDGER_CONTRACT.md").read_text(encoding="utf-8")
    governance_contract = (ROOT / "docs" / "contracts" / "FORMALIZATION_GOVERNANCE_CONTRACT.md").read_text(encoding="utf-8")
    loop_mainline = (ROOT / "docs" / "agents" / "LOOP_MAINLINE.md").read_text(encoding="utf-8")
    for snippet in ("source enrichment", "reverse-link resync", "review todo"):
        if snippet not in ledger_contract.lower():
            return _fail(f"FORMALIZATION_LEDGER_CONTRACT.md missing `{snippet}`")
    for snippet in ("ExternalSourcePack", "human ingress", "review todo", "reverse-link resync"):
        if snippet not in governance_contract:
            return _fail(f"FORMALIZATION_GOVERNANCE_CONTRACT.md missing `{snippet}`")
    if "formalization front-end helpers" not in loop_mainline.lower():
        return _fail("LOOP_MAINLINE.md must route users to committed formalization front-end helpers")

    with tempfile.TemporaryDirectory(prefix="formalization_frontier_") as td:
        root = Path(td)
        lean_file = root / "Demo.lean"
        lean_file.write_text(
            "namespace Temp\n"
            "theorem demo_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.1\n"
            "  trivial\n"
            "theorem later_decl : True := by\n"
            "  trivial\n"
            "end Temp\n",
            encoding="utf-8",
        )
        sibling_dir = root / "Nested"
        sibling_dir.mkdir()
        sibling_lean = sibling_dir / "Demo.lean"
        sibling_lean.write_text(
            "namespace Temp.Nested\n"
            "theorem nested_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.1\n"
            "  trivial\n"
            "end Temp.Nested\n",
            encoding="utf-8",
        )
        tex_root = root / "sources"
        tex_root.mkdir()
        tex_file = tex_root / "paper.tex"
        tex_file.write_text(
            "\\begin{equation}\\label{eq:one} x + y = z \\end{equation}\n"
            "As shown in \\eqref{eq:one} and \\cite{lattimore2020bandit}.",
            encoding="utf-8",
        )
        bib_file = tex_root / "refs.bib"
        bib_file.write_text(
            "@book{lattimore2020bandit,\n"
            "  title={Bandit Algorithms},\n"
            "  author={Lattimore, Tor and Szepesvari, Csaba},\n"
            "  year={2020}\n"
            "}\n"
            "@article{unused2024example,\n"
            "  title={Unused Reference},\n"
            "  author={Unused, Uma and Example, Eli},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        pdf_file = root / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n% minimal test pdf\n")

        ledger = _ledger(lean_file)
        pack_inputs = root / "external_user_inputs.json"
        pack_inputs.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "external_result_id": "demo.external.1",
                            "citation_key": "lattimore2020bandit",
                            "latex_root": "sources",
                            "pdf_path": "paper.pdf",
                            "note": "user supplied sources",
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        pack = build_external_source_pack(
            ledger=copy.deepcopy(ledger),
            ledger_path=root / "ledger.json",
            user_inputs_path=pack_inputs,
            cache_dir=root / "cache",
            network_enabled=False,
        )
        _validate(pack, "ExternalSourcePack.schema.json")
        if pack["summary"]["with_user_assets"] != 1:
            return _fail("external source pack should capture user assets")
        if pack["items"][0]["user_inputs"]["entry_count"] != 1:
            return _fail("external source pack must deduplicate user entries that match by both id and citation key")
        if pack["items"][0]["selected_material"]["mode"] != "LATEX_USER":
            return _fail("external source pack should prefer user LaTeX roots")
        if Path(pack["items"][0]["materials"]["user_latex_roots"][0]["path"]).resolve() != tex_root.resolve():
            return _fail("external source pack should resolve relative asset paths against the ingress file location")

        enriched, enrichment_report = enrich_ledger_from_sources(
            ledger=copy.deepcopy(ledger),
            source_root=tex_root,
        )
        if "latex_enrichment" not in enriched.get("audit", {}):
            return _fail("source enrichment must write audit.latex_enrichment")
        clause = enriched["formalization_bindings"][0]["clause_links"][0]
        if clause.get("equation_ref_resolution") != "MATCHED":
            return _fail("source enrichment should resolve explicit equation refs from LaTeX sources")
        if "lattimore2020bandit" not in enriched["external_results"][0].get("citation_keys_detected", []):
            return _fail("source enrichment should enrich external_results citation keys")
        if enriched["external_results"][1].get("citation_keys_detected"):
            return _fail("source enrichment must not treat bibliography-only entries as cited keys")
        if "unused2024example" not in enriched["external_results"][1].get("bibliography_entry_candidates", []):
            return _fail("source enrichment should still report matched bibliography candidates separately")
        pdf_enriched, pdf_report = enrich_ledger_from_sources(
            ledger=copy.deepcopy(enriched),
            source_root=pdf_file,
        )
        if "lattimore2020bandit" not in pdf_enriched["external_results"][0].get("citation_keys_detected", []):
            return _fail("source enrichment must preserve pre-existing citation keys when the current source root has no new hits")
        if pdf_report["summary"]["pdf_file_count"] != 1:
            return _fail("source enrichment should accept bounded PDF roots without raising")
        if enrichment_report["summary"]["equations_detected"] < 1:
            return _fail("source enrichment report should index equations")

        todo = build_review_todo(
            ledger=enriched,
            consistency_report={"issues": [{"severity": "WARN", "code": "UNMAPPED_ATOM", "ref": {"mapping_id": "demo.map.1"}}]},
            focus=["ATOM_MAPPING", "LEAN_ANCHOR"],
            min_risk=0.0,
            top_k=10,
            include_locked=False,
        )
        if todo["count"] < 1:
            return _fail("review todo should surface at least one prioritized review item")

        resynced, resync_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[lean_file, sibling_lean],
        )
        ann_links = [x for x in resynced.get("lean_reverse_links", []) if x.get("link_origin") == "AUTO_FROM_ANNOTATION"]
        if len(ann_links) != 2:
            return _fail("reverse-link resync should rebuild one AUTO_FROM_ANNOTATION link per annotated Lean file")
        if ann_links[0]["lean_ref"].get("declaration_name") != "demo_decl":
            return _fail("reverse-link resync should infer declaration name from Lean source")
        if len({link["reverse_link_id"] for link in ann_links}) != 2:
            return _fail("reverse-link resync should avoid collisions across same-basename Lean files")
        if resync_report["annotation_links"] != 2:
            return _fail("reverse-link resync report should count annotation links")

    print("[formalization-frontier] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
