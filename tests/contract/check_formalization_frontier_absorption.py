#!/usr/bin/env python3
"""Contract: formalization frontier helpers must exist on committed mainline paths."""

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
        from tools.formalization.source_enrichment import enrich_ledger_from_sources, parse_equations
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
    for snippet in (
        "parsed LaTeX/Bib sources",
        "PDF roots may still be supplied as bounded source inputs",
    ):
        if snippet not in ledger_contract:
            return _fail(f"FORMALIZATION_LEDGER_CONTRACT.md missing `{snippet}`")
    for snippet in ("ExternalSourcePack", "human ingress", "review todo", "reverse-link resync"):
        if snippet not in governance_contract:
            return _fail(f"FORMALIZATION_GOVERNANCE_CONTRACT.md missing `{snippet}`")
    if "source enrichment from LaTeX/Bib evidence" not in governance_contract:
        return _fail("FORMALIZATION_GOVERNANCE_CONTRACT.md must describe source enrichment as LaTeX/Bib-based")
    if "source enrichment from LaTeX/PDF evidence" in governance_contract:
        return _fail("FORMALIZATION_GOVERNANCE_CONTRACT.md must not advertise raw PDF extraction support")
    if "coverage/file-discovery inputs" in governance_contract:
        return _fail("FORMALIZATION_GOVERNANCE_CONTRACT.md must not overstate PDF roots as file-discovery inputs")
    if "four canonical schemas above" in governance_contract:
        return _fail("FORMALIZATION_GOVERNANCE_CONTRACT.md must not undercount the canonical governance artifacts after ExternalSourcePack promotion")
    if "five canonical" not in governance_contract:
        return _fail("FORMALIZATION_GOVERNANCE_CONTRACT.md must describe the promoted canonical governance artifact count")
    if "audit coverage and file discovery" in ledger_contract:
        return _fail("FORMALIZATION_LEDGER_CONTRACT.md must not promise PDF-root file discovery that source enrichment does not implement")
    if "formalization front-end helpers" not in loop_mainline.lower():
        return _fail("LOOP_MAINLINE.md must route users to committed formalization front-end helpers")
    plan_doc = (ROOT / "docs" / "agents" / "execplans" / "20260308_formalization_enrichment_absorption_v0.md").read_text(
        encoding="utf-8"
    )
    if "LaTeX/PDF-derived equation and citation information" in plan_doc:
        return _fail("formalization absorption ExecPlan must not overstate source enrichment as raw LaTeX/PDF extraction")
    for snippet in (
        "LaTeX/Bib-derived equation and citation information",
        "bounded PDF roots as source inputs",
    ):
        if snippet not in plan_doc:
            return _fail(f"formalization absorption ExecPlan missing `{snippet}`")

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
        if pdf_enriched["external_results"][0].get("citation_keys_detected"):
            return _fail("source enrichment reruns must drop stale citation keys when the current source root provides no citation evidence")
        if pdf_enriched["external_results"][0].get("citation_key_usage_counts"):
            return _fail("source enrichment reruns must drop stale citation usage counts when the current source root provides no citation evidence")
        if pdf_enriched["external_results"][0].get("bibliography_entry_candidates"):
            return _fail("source enrichment reruns must drop stale bibliography candidates when the current source root provides no bibliography evidence")
        if pdf_enriched["external_results"][0].get("retrieval_queries"):
            return _fail("PDF-only reruns must drop stale citation-key retrieval queries when the current source root provides no citation evidence")
        if pdf_report["summary"]["pdf_file_count"] != 1:
            return _fail("source enrichment should accept bounded PDF roots without raising")
        if pdf_report["summary"]["citation_keys_detected"] != 0:
            return _fail("PDF-only source roots must not report citation-key extraction when no TeX citations were parsed")
        if pdf_report["summary"]["external_results_with_citation_key_hits"] != 0:
            return _fail("PDF-only reruns must count only current-run citation hits")
        pdf_clause = pdf_enriched["formalization_bindings"][0]["clause_links"][0]
        if pdf_clause.get("equation_expression_candidates"):
            return _fail("PDF-only reruns must drop stale equation candidates when the current source root contributes no equations")
        if pdf_clause.get("equation_expression_source_refs"):
            return _fail("PDF-only reruns must drop stale equation source refs when the current source root contributes no equations")
        if pdf_clause.get("equation_ref_resolution") != "UNMATCHED":
            return _fail("PDF-only reruns must recompute equation ref resolution against the current source root")
        if pdf_report["summary"]["equation_ref_unresolved_count"] != 1:
            return _fail("PDF-only reruns must count unresolved equation refs from the current source root")
        no_equation_root = root / "no_equation_sources"
        no_equation_root.mkdir()
        (no_equation_root / "main.tex").write_text(
            "The section text no longer includes equation environments or citation commands.\n",
            encoding="utf-8",
        )
        no_equation_enriched, no_equation_report = enrich_ledger_from_sources(
            ledger=copy.deepcopy(enriched),
            source_root=no_equation_root,
        )
        if no_equation_enriched["external_results"][0].get("citation_keys_detected"):
            return _fail("ordinary TeX reruns must drop stale citation keys when the current source root no longer cites the dependency")
        if no_equation_enriched["external_results"][0].get("bibliography_entry_candidates"):
            return _fail("ordinary TeX reruns must drop stale bibliography candidates when the current source root no longer binds a bibliography")
        if no_equation_enriched["external_results"][0].get("retrieval_queries"):
            return _fail("ordinary TeX reruns must drop stale citation-key retrieval queries when the current source root no longer cites the dependency")
        no_equation_clause = no_equation_enriched["formalization_bindings"][0]["clause_links"][0]
        if no_equation_clause.get("equation_expression_candidates"):
            return _fail("ordinary TeX reruns must drop stale equation candidates when the current source root yields no equations")
        if no_equation_clause.get("equation_expression_source_refs"):
            return _fail("ordinary TeX reruns must drop stale equation source refs when the current source root yields no equations")
        if no_equation_clause.get("equation_ref_resolution") != "UNMATCHED":
            return _fail("ordinary TeX reruns must recompute equation ref resolution against the current source root")
        if no_equation_report["summary"]["equation_ref_unresolved_count"] != 1:
            return _fail("ordinary TeX reruns must count unresolved equation refs from the current source root")
        file_root_escape = root / "file_root_escape"
        (file_root_escape / "paper").mkdir(parents=True)
        (file_root_escape / "outside").mkdir()
        file_root_entry = file_root_escape / "paper" / "main.tex"
        file_root_entry.write_text(
            "\\input{../outside/secret}\n",
            encoding="utf-8",
        )
        (file_root_escape / "outside" / "secret.tex").write_text(
            "\\begin{equation} x = y \\end{equation}\n",
            encoding="utf-8",
        )
        file_root_ledger = copy.deepcopy(ledger)
        file_root_ledger["formalization_bindings"][0]["clause_links"][0]["equation_refs"] = [1]
        file_root_enriched, file_root_report = enrich_ledger_from_sources(
            ledger=file_root_ledger,
            source_root=file_root_entry,
        )
        if file_root_report["summary"]["tex_file_count"] != 1:
            return _fail("file-root source enrichment must ignore TeX includes outside the declared source root")
        if file_root_report["summary"]["equations_detected"] != 0:
            return _fail("file-root source enrichment must not index equations from out-of-root TeX includes")
        if file_root_enriched["formalization_bindings"][0]["clause_links"][0].get("equation_ref_resolution") == "MATCHED":
            return _fail("file-root source enrichment must not resolve equation refs from out-of-root TeX includes")
        file_root_bib_root = root / "file_root_bib_fallback"
        file_root_bib_root.mkdir()
        file_root_bib_entry = file_root_bib_root / "section.tex"
        file_root_bib_entry.write_text(
            "\\begin{equation} x = y \\end{equation}\n",
            encoding="utf-8",
        )
        (file_root_bib_root / "refs.bib").write_text(
            "@article{smith2024section,\n"
            "  title={Bandit Algorithms for Bounds},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        (file_root_bib_root / "other.bib").write_text(
            "@article{standalone2024,\n"
            "  title={Standalone Result},\n"
            "  author={Other, Pat},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        file_root_bib_ledger = copy.deepcopy(ledger)
        file_root_bib_ledger["external_results"] = [
            {
                "external_result_id": "smith.file.root",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-file-root"),
            }
        ]
        file_root_bib_enriched, file_root_bib_report = enrich_ledger_from_sources(
            ledger=file_root_bib_ledger,
            source_root=file_root_bib_entry,
        )
        if file_root_bib_report["summary"]["bib_file_count"] != 0:
            return _fail("single-file TeX source enrichment must not fall back to every sibling bibliography file when the entrypoint names none")
        if file_root_bib_enriched["external_results"][0].get("bibliography_entry_candidates"):
            return _fail("single-file TeX source enrichment must not attach bibliography candidates from unrelated sibling .bib files")
        if file_root_bib_enriched["external_results"][0].get("bib_source_files"):
            return _fail("single-file TeX source enrichment must not attach sibling bibliography file paths without explicit or citation-backed proof")
        non_generic_key_root = root / "nongeneric_key_sources"
        non_generic_key_root.mkdir()
        (non_generic_key_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024bandit} throughout.\n",
            encoding="utf-8",
        )
        (non_generic_key_root / "refs.bib").write_text(
            "@article{smith2024bandit,\n"
            "  title={Bandit Algorithms},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        non_generic_key_ledger = copy.deepcopy(ledger)
        non_generic_key_ledger["external_results"] = [
            {
                "external_result_id": "wrong.2024.only",
                "name": "Graph Limits Revisited",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Other and Example (2024) Graph Limits Revisited",
                "citation_authors": ["Pat Other", "Eli Example"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "non-generic-year-only"),
            }
        ]
        non_generic_key_enriched, non_generic_key_report = enrich_ledger_from_sources(
            ledger=non_generic_key_ledger,
            source_root=non_generic_key_root,
        )
        if non_generic_key_enriched["external_results"][0].get("citation_keys_detected"):
            return _fail("source enrichment must not accept a non-generic cited key when only the year matches and author/title evidence is absent")
        if non_generic_key_report["summary"]["external_results_with_citation_key_hits"] != 0:
            return _fail("source enrichment must not count year-only non-generic key matches as current-run citation hits")
        multi_doc_root = root / "multi_doc_sources"
        multi_doc_root.mkdir()
        (multi_doc_root / "main.tex").write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\input{body}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        (multi_doc_root / "body.tex").write_text(
            "\\begin{equation} m = n \\end{equation}\n",
            encoding="utf-8",
        )
        (multi_doc_root / "standalone.tex").write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\begin{equation} q = r \\end{equation}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        multi_doc_ledger = copy.deepcopy(ledger)
        multi_doc_ledger["formalization_bindings"][0]["clause_links"][0]["equation_refs"] = [2]
        multi_doc_enriched, multi_doc_report = enrich_ledger_from_sources(
            ledger=multi_doc_ledger,
            source_root=multi_doc_root,
        )
        if multi_doc_report["summary"]["tex_file_count"] != 2:
            return _fail("directory-root source enrichment must restrict TeX indexing to the chosen entrypoint closure")
        if multi_doc_report["summary"]["equations_detected"] != 1:
            return _fail("directory-root source enrichment must not index equations from unrelated standalone TeX documents")
        if multi_doc_enriched["formalization_bindings"][0]["clause_links"][0].get("equation_ref_resolution") == "MATCHED":
            return _fail("directory-root source enrichment must not resolve equation refs against unrelated standalone TeX documents")
        ambiguous_doc_root = root / "ambiguous_doc_sources"
        ambiguous_doc_root.mkdir()
        (ambiguous_doc_root / "paper.tex").write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\cite{paper2024}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        (ambiguous_doc_root / "supplement.tex").write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\cite{supplement2024}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        (ambiguous_doc_root / "refs.bib").write_text(
            "@article{paper2024,\n"
            "  title={Paper Result},\n"
            "  author={Doe, Dana},\n"
            "  year={2024}\n"
            "}\n"
            "@article{supplement2024,\n"
            "  title={Supplement Result},\n"
            "  author={Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        try:
            enrich_ledger_from_sources(
                ledger=copy.deepcopy(ledger),
                source_root=ambiguous_doc_root,
            )
        except ValueError as exc:
            if "multiple standalone TeX entrypoints" not in str(exc):
                return _fail("ambiguous multi-document TeX roots must fail with a dedicated ambiguity error")
        else:
            return _fail("ambiguous multi-document TeX roots must be rejected instead of guessing an entrypoint")
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
        clause_atom_issue_ledger = copy.deepcopy(enriched)
        clause_atom_issue_ledger["clause_atoms"][0]["review"] = _review("HUMAN_CONFIRMED", 0.95, "clause-atom-confirmed")
        clause_atom_issue_ledger["clause_atoms"][0]["text"] = "confirmed atom text"
        clause_atom_issue_ledger["clause_atoms"][0]["logic_role"] = "premise"
        clause_atom_issue_ledger["clause_atoms"][0]["claim_id"] = "demo.claim.1"
        clause_atom_todo = build_review_todo(
            ledger=clause_atom_issue_ledger,
            consistency_report={
                "issues": [
                    {
                        "severity": "WARN",
                        "code": "UNMAPPED_ATOM",
                        "ref": {"atom_id": clause_atom_issue_ledger["clause_atoms"][0]["atom_id"]},
                    }
                ]
            },
            focus=["CLAUSE_ATOM"],
            min_risk=0.0,
            top_k=10,
            include_locked=False,
        )
        if clause_atom_todo["count"] != 1:
            return _fail("CLAUSE_ATOM todo focus must still surface atom-scoped UNMAPPED_ATOM issues for high-confidence confirmed atoms")
        clause_atom_item = clause_atom_todo["items"][0]
        if clause_atom_item.get("issue_count") != 1:
            return _fail("CLAUSE_ATOM todo items must count linked atom-scoped consistency issues")
        if clause_atom_item.get("issue_codes", {}).get("UNMAPPED_ATOM") != 1:
            return _fail("CLAUSE_ATOM todo items must preserve UNMAPPED_ATOM issue codes")

        structured_issue_ledger = copy.deepcopy(enriched)
        structured_issue_ledger["atom_mappings"][0]["mismatch_kind"] = None
        structured_todo = build_review_todo(
            ledger=structured_issue_ledger,
            consistency_report={
                "issues": [
                    {
                        "severity": "WARN",
                        "code": "MAPPING_ANCHOR_MISSING",
                        "ref": {
                            "clause_id": "demo.clause.eq_1",
                            "binding_id": "demo.bind.1",
                        },
                    }
                ]
            },
            focus=["ATOM_MAPPING"],
            min_risk=0.0,
            top_k=10,
            include_locked=False,
        )
        mapping_rows = [
            row
            for row in structured_todo["items"]
            if row.get("entity_type") == "ATOM_MAPPING" and row.get("entity_id") == "demo.map.1"
        ]
        if len(mapping_rows) != 1:
            return _fail("review todo must keep the target atom mapping when clause/binding-scoped issues are present")
        mapping_row = mapping_rows[0]
        if mapping_row["issue_count"] != 1:
            return _fail("review todo must attach clause/binding-scoped consistency issues to schema-valid atom mappings")
        if mapping_row["pointers"].get("clause_id") != "demo.clause.eq_1":
            return _fail("review todo must derive clause_id pointers from schema-valid mapping context")
        if mapping_row["pointers"].get("binding_id") != "demo.bind.1":
            return _fail("review todo must derive binding_id pointers from schema-valid mapping context")
        if mapping_row["pointers"].get("mismatch_kind") is not None:
            return _fail("review todo must preserve schema-valid null mismatch_kind as null")
        if any(reason == "mismatch=None" for reason in mapping_row.get("reasons", [])):
            return _fail("review todo must not treat null mismatch_kind as a real mismatch")
        null_binding_ref_todo = build_review_todo(
            ledger=structured_issue_ledger,
            consistency_report={
                "issues": [
                    {
                        "severity": "WARN",
                        "code": "MAPPING_ANCHOR_MISSING",
                        "ref": {
                            "clause_id": "demo.clause.eq_1",
                            "binding_id": None,
                        },
                    }
                ]
            },
            focus=["ATOM_MAPPING"],
            min_risk=0.0,
            top_k=10,
            include_locked=False,
        )
        null_binding_rows = [
            row
            for row in null_binding_ref_todo["items"]
            if row.get("entity_type") == "ATOM_MAPPING" and row.get("entity_id") == "demo.map.1"
        ]
        if len(null_binding_rows) != 1:
            return _fail("review todo must keep clause-scoped mapping rows visible when ref.binding_id is explicitly null")
        if null_binding_rows[0]["issue_count"] != 1:
            return _fail("review todo must fall back to clause-scoped mapping issues when ref.binding_id is null")
        anchor_todo = build_review_todo(
            ledger=structured_issue_ledger,
            consistency_report={
                "issues": [
                    {
                        "severity": "WARN",
                        "code": "MAPPING_ANCHOR_MISSING",
                        "ref": {
                            "clause_id": "demo.clause.eq_1",
                            "binding_id": "demo.bind.1",
                        },
                    }
                ]
            },
            focus=["LEAN_ANCHOR"],
            min_risk=0.0,
            top_k=10,
            include_locked=False,
        )
        anchor_rows = [
            row
            for row in anchor_todo["items"]
            if row.get("entity_type") == "LEAN_ANCHOR" and row.get("entity_id") == "demo.anchor.1"
        ]
        if len(anchor_rows) != 1:
            return _fail("review todo must still surface clause-scoped Lean-anchor work when binding_id is present")
        if anchor_rows[0]["issue_count"] != 1:
            return _fail("review todo must attach clause-scoped consistency issues to Lean anchors even when the issue also carries binding_id")

        smith_root = root / "smith_sources"
        smith_root.mkdir()
        (smith_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024bandits} in the main result.\n",
            encoding="utf-8",
        )
        (smith_root / "refs.bib").write_text(
            "@article{smith2024bandits,\n"
            "  title={Bandit Algorithms for Bounds},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n"
            "@article{smith2024graphs,\n"
            "  title={Graph Limits Revisited},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        smith_ledger = copy.deepcopy(ledger)
        smith_ledger["external_results"] = [
            {
                "external_result_id": "smith.bandits",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-bandits"),
            },
            {
                "external_result_id": "smith.graphs",
                "name": "Graph Limits Revisited",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Graph Limits Revisited",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-graphs"),
            },
        ]
        smith_enriched, _smith_report = enrich_ledger_from_sources(
            ledger=smith_ledger,
            source_root=smith_root,
        )
        if smith_enriched["external_results"][0].get("citation_keys_detected") != ["smith2024bandits"]:
            return _fail("source enrichment must keep same-author/same-year citation keys aligned to title text")
        if smith_enriched["external_results"][1].get("citation_keys_detected"):
            return _fail("source enrichment must not assign unrelated same-author/same-year citation keys")

        smith_key_root = root / "smith_key_sources"
        smith_key_root.mkdir()
        (smith_key_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024a} throughout.\n",
            encoding="utf-8",
        )
        (smith_key_root / "paper.pdf").write_text("compiled pdf placeholder\n", encoding="utf-8")
        (smith_key_root / "refs.bib").write_text(
            "@article{smith2024a,\n"
            "  title={Bandit Algorithms for Bounds},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        smith_key_ledger = copy.deepcopy(ledger)
        smith_key_ledger["external_results"] = [
            {
                "external_result_id": "smith.keyed",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-keyed"),
            }
        ]
        smith_key_enriched, smith_key_report = enrich_ledger_from_sources(
            ledger=smith_key_ledger,
            source_root=smith_key_root,
        )
        if smith_key_enriched["external_results"][0].get("citation_keys_detected") != ["smith2024a"]:
            return _fail("source enrichment must preserve cited author-year BibTeX keys when they are uniquely determined")
        if smith_key_report["summary"]["external_results_with_citation_key_hits"] != 1:
            return _fail("source enrichment must count uniquely matched author-year BibTeX keys as current-run citation hits")
        smith_key_file_enriched, smith_key_file_report = enrich_ledger_from_sources(
            ledger=smith_key_ledger,
            source_root=smith_key_root / "paper.tex",
        )
        if smith_key_file_report["summary"]["bib_file_count"] != 1:
            return _fail("file-root source enrichment must still discover bibliography files under the declared source root")
        if smith_key_file_report["summary"]["pdf_file_count"] != 0:
            return _fail("single-file .tex source enrichment must not count sibling PDFs as bounded inputs")
        if smith_key_file_enriched["external_results"][0].get("citation_keys_detected") != ["smith2024a"]:
            return _fail("file-root source enrichment must preserve cited author-year BibTeX keys when they are uniquely determined")
        smith_generic_root = root / "smith_generic_sources"
        smith_generic_root.mkdir()
        (smith_generic_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024} throughout.\n",
            encoding="utf-8",
        )
        smith_generic_ledger = copy.deepcopy(ledger)
        smith_generic_ledger["external_results"] = [
            {
                "external_result_id": "smith.generic.no_text_match",
                "name": "Completely Different Result",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Completely Different Result",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-generic-no-match"),
            }
        ]
        smith_generic_enriched, smith_generic_report = enrich_ledger_from_sources(
            ledger=smith_generic_ledger,
            source_root=smith_generic_root,
        )
        if smith_generic_enriched["external_results"][0].get("citation_keys_detected"):
            return _fail("source enrichment must not assign generic author-year citation keys when title text provides no supporting match")
        if smith_generic_report["summary"]["external_results_with_citation_key_hits"] != 0:
            return _fail("source enrichment must not count unmatched generic author-year keys as current-run citation hits")
        closure_root = root / "closure_bib_sources"
        closure_root.mkdir()
        (closure_root / "main.tex").write_text(
            "\\input{body}\n\\bibliography{refs}\n",
            encoding="utf-8",
        )
        (closure_root / "body.tex").write_text(
            "We rely on \\cite{smith2024closure} throughout.\n",
            encoding="utf-8",
        )
        (closure_root / "refs.bib").write_text(
            "@article{smith2024closure,\n"
            "  title={Bandit Algorithms for Bounds},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        (closure_root / "standalone.tex").write_text(
            "Standalone document using \\cite{standalone2024}.\n",
            encoding="utf-8",
        )
        (closure_root / "zzz_standalone.bib").write_text(
            "@article{smith2024closure,\n"
            "  title={Unrelated Standalone Title},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n"
            "@article{standalone2024,\n"
            "  title={Standalone Result},\n"
            "  author={Other, Pat},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        closure_ledger = copy.deepcopy(ledger)
        closure_ledger["external_results"] = [
            {
                "external_result_id": "smith.closure",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-closure"),
            }
        ]
        closure_enriched, closure_report = enrich_ledger_from_sources(
            ledger=closure_ledger,
            source_root=closure_root,
        )
        if closure_report["summary"]["bib_file_count"] != 1:
            return _fail("directory-root source enrichment must restrict bibliography discovery to the active TeX closure")
        closure_bib_files = closure_enriched["external_results"][0].get("bib_source_files", [])
        if len(closure_bib_files) != 1 or not str(closure_bib_files[0]).endswith("refs.bib"):
            return _fail("source enrichment must not leak unrelated bibliography files from standalone TeX projects into active-document matches")

        smith_slug_root = root / "smith_slug_sources"
        smith_slug_root.mkdir()
        (smith_slug_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024foo} throughout.\n",
            encoding="utf-8",
        )
        (smith_slug_root / "refs.bib").write_text(
            "@article{smith2024foo,\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        smith_slug_ledger = copy.deepcopy(ledger)
        smith_slug_ledger["external_results"] = [
            {
                "external_result_id": "smith.slugged",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-slugged"),
            }
        ]
        smith_slug_enriched, smith_slug_report = enrich_ledger_from_sources(
            ledger=smith_slug_ledger,
            source_root=smith_slug_root,
        )
        if smith_slug_enriched["external_results"][0].get("citation_keys_detected") != ["smith2024foo"]:
            return _fail("source enrichment must preserve uniquely cited author-year BibTeX keys even when the key uses a non-title suffix")
        if smith_slug_report["summary"]["external_results_with_citation_key_hits"] != 1:
            return _fail("source enrichment must count uniquely cited non-generic author-year BibTeX keys as current-run citation hits")

        smith_slug_titled_root = root / "smith_slug_titled_sources"
        smith_slug_titled_root.mkdir()
        (smith_slug_titled_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024foo} throughout.\n",
            encoding="utf-8",
        )
        (smith_slug_titled_root / "refs.bib").write_text(
            "@article{smith2024foo,\n"
            "  title={Supplementary Bandit Paper},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        smith_slug_titled_ledger = copy.deepcopy(ledger)
        smith_slug_titled_ledger["external_results"] = [
            {
                "external_result_id": "smith.slugged.titled",
                "name": "Unique Results",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Unique Results",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-slugged-titled"),
            }
        ]
        smith_slug_titled_enriched, smith_slug_titled_report = enrich_ledger_from_sources(
            ledger=smith_slug_titled_ledger,
            source_root=smith_slug_titled_root,
        )
        if smith_slug_titled_enriched["external_results"][0].get("citation_keys_detected") != ["smith2024foo"]:
            return _fail("source enrichment must preserve uniquely cited non-generic author-year keys even when bibliography titles use different wording")
        if smith_slug_titled_report["summary"]["external_results_with_citation_key_hits"] != 1:
            return _fail("source enrichment must count uniquely cited non-generic author-year keys even when bibliography titles differ from the external metadata text")

        smith_nobib_root = root / "smith_nobib_sources"
        smith_nobib_root.mkdir()
        (smith_nobib_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024foo} throughout.\n",
            encoding="utf-8",
        )
        smith_nobib_ledger = copy.deepcopy(ledger)
        smith_nobib_ledger["external_results"] = [
            {
                "external_result_id": "smith.nobib.bandits",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-nobib-bandits"),
            },
            {
                "external_result_id": "smith.nobib.graphs",
                "name": "Graph Limits Revisited",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Graph Limits Revisited",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-nobib-graphs"),
            },
        ]
        smith_nobib_enriched, smith_nobib_report = enrich_ledger_from_sources(
            ledger=smith_nobib_ledger,
            source_root=smith_nobib_root,
        )
        if smith_nobib_enriched["external_results"][0].get("citation_keys_detected"):
            return _fail("source enrichment must not assign a cited author-year key to multiple no-bib same-author/same-year external results")
        if smith_nobib_enriched["external_results"][1].get("citation_keys_detected"):
            return _fail("source enrichment must not assign ambiguous no-bib citation keys to unrelated external results")
        if smith_nobib_report["summary"]["external_results_with_citation_key_hits"] != 0:
            return _fail("source enrichment must not count ambiguous no-bib author-year matches as current-run citation hits")

        smith_nobib_closure_root = root / "smith_nobib_closure_sources"
        smith_nobib_closure_root.mkdir()
        (smith_nobib_closure_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024closure} throughout.\n",
            encoding="utf-8",
        )
        (smith_nobib_closure_root / "refs.bib").write_text(
            "@article{smith2024closure,\n"
            "  title={Bandit Algorithms for Bounds},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        template_dir = smith_nobib_closure_root / "templates"
        template_dir.mkdir()
        (template_dir / "refs.bib").write_text(
            "@article{smith2024closure,\n"
            "  title={Unrelated Template Title},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        smith_nobib_closure_ledger = copy.deepcopy(ledger)
        smith_nobib_closure_ledger["external_results"] = [
            {
                "external_result_id": "smith.nobib.closure",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-nobib-closure"),
            }
        ]
        smith_nobib_closure_enriched, _smith_nobib_closure_report = enrich_ledger_from_sources(
            ledger=smith_nobib_closure_ledger,
            source_root=smith_nobib_closure_root / "paper.tex",
        )
        nobib_closure_sources = smith_nobib_closure_enriched["external_results"][0].get("bib_source_files", [])
        if len(nobib_closure_sources) != 1 or Path(nobib_closure_sources[0]).name != "refs.bib" or "templates" in nobib_closure_sources[0]:
            return _fail("source enrichment no-bib fallback must restrict bibliography evidence to the active TeX closure")

        smith_explicit_subdir_root = root / "smith_explicit_subdir_sources"
        smith_explicit_subdir_root.mkdir()
        (smith_explicit_subdir_root / "paper.tex").write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "We rely on \\cite{smith2024subdir} throughout.\n"
            "\\bibliography{bib/refs}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        (smith_explicit_subdir_root / "bib").mkdir()
        (smith_explicit_subdir_root / "bib" / "refs.bib").write_text(
            "@article{smith2024subdir,\n"
            "  title={Bandit Algorithms for Bounds},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        smith_explicit_subdir_ledger = copy.deepcopy(ledger)
        smith_explicit_subdir_ledger["external_results"] = [
            {
                "external_result_id": "smith.subdir",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-subdir"),
            }
        ]
        smith_explicit_subdir_enriched, smith_explicit_subdir_report = enrich_ledger_from_sources(
            ledger=smith_explicit_subdir_ledger,
            source_root=smith_explicit_subdir_root / "paper.tex",
        )
        if smith_explicit_subdir_report["summary"]["bib_file_count"] != 1:
            return _fail("source enrichment must honor explicitly referenced bibliography files in subdirectories")
        explicit_subdir_sources = smith_explicit_subdir_enriched["external_results"][0].get("bib_source_files", [])
        if len(explicit_subdir_sources) != 1 or not explicit_subdir_sources[0].endswith("bib/refs.bib"):
            return _fail("source enrichment must retain explicitly referenced bibliography paths even when the bib file lives outside the active TeX directory")

        smith_shared_root = root / "smith_shared_sources"
        smith_shared_root.mkdir()
        (smith_shared_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024shared} twice in the development.\n",
            encoding="utf-8",
        )
        (smith_shared_root / "refs.bib").write_text(
            "@article{smith2024shared,\n"
            "  title={Bandit Algorithms for Bounds},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        smith_shared_ledger = copy.deepcopy(ledger)
        smith_shared_ledger["external_results"] = [
            {
                "external_result_id": "smith.shared.dep_a",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-shared-a"),
            },
            {
                "external_result_id": "smith.shared.dep_b",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-shared-b"),
            },
        ]
        smith_shared_enriched, smith_shared_report = enrich_ledger_from_sources(
            ledger=smith_shared_ledger,
            source_root=smith_shared_root,
        )
        if smith_shared_enriched["external_results"][0].get("citation_keys_detected") != ["smith2024shared"]:
            return _fail("source enrichment must preserve shared citation keys for same-paper dependencies")
        if smith_shared_enriched["external_results"][1].get("citation_keys_detected") != ["smith2024shared"]:
            return _fail("source enrichment must preserve shared citation keys for every same-paper dependency row")
        if smith_shared_report["summary"]["external_results_with_citation_key_hits"] != 2:
            return _fail("source enrichment must count every same-paper dependency row that keeps the shared citation key")

        smith_shared_variant_ledger = copy.deepcopy(smith_shared_ledger)
        smith_shared_variant_ledger["external_results"][0]["citation_label"] = "Smith et al. (2024)"
        smith_shared_variant_ledger["external_results"][1]["citation_label"] = "Smith and Doe (2024)"
        smith_shared_variant_enriched, smith_shared_variant_report = enrich_ledger_from_sources(
            ledger=smith_shared_variant_ledger,
            source_root=smith_shared_root,
        )
        if smith_shared_variant_enriched["external_results"][0].get("citation_keys_detected") != ["smith2024shared"]:
            return _fail("source enrichment must preserve shared citation keys across same-paper citation-label variants")
        if smith_shared_variant_enriched["external_results"][1].get("citation_keys_detected") != ["smith2024shared"]:
            return _fail("source enrichment must preserve shared citation keys across same-paper citation-label variants for every row")
        if smith_shared_variant_report["summary"]["external_results_with_citation_key_hits"] != 2:
            return _fail("source enrichment must count same-paper citation-label variants as current-run citation hits")
        smith_shared_approx_ledger = copy.deepcopy(smith_shared_ledger)
        smith_shared_approx_ledger["external_results"][1]["name"] = "Bandit Bounds"
        smith_shared_approx_ledger["external_results"][1]["citation_label"] = "Smith and Doe (2024) Bandit Bounds"
        smith_shared_approx_ledger["external_results"][1]["source_kind"] = "BOOK_CITATION"
        smith_shared_approx_enriched, smith_shared_approx_report = enrich_ledger_from_sources(
            ledger=smith_shared_approx_ledger,
            source_root=smith_shared_root,
        )
        if smith_shared_approx_enriched["external_results"][0].get("citation_keys_detected") != ["smith2024shared"]:
            return _fail("source enrichment must keep the cited key on the exact-title dependency row when subset-title siblings are present")
        if smith_shared_approx_enriched["external_results"][1].get("citation_keys_detected"):
            return _fail("source enrichment must not preserve shared citation keys for subset-title sibling externals")
        if smith_shared_approx_report["summary"]["external_results_with_citation_key_hits"] != 1:
            return _fail("source enrichment must count only the exact-title dependency row when subset-title siblings are present")
        smith_shared_overlap_ledger = copy.deepcopy(smith_shared_ledger)
        smith_shared_overlap_ledger["external_results"][1]["name"] = "Bandit Bounds for Graphs"
        smith_shared_overlap_ledger["external_results"][1]["citation_label"] = "Smith and Doe (2024) Bandit Bounds for Graphs"
        smith_shared_overlap_enriched, smith_shared_overlap_report = enrich_ledger_from_sources(
            ledger=smith_shared_overlap_ledger,
            source_root=smith_shared_root,
        )
        if smith_shared_overlap_enriched["external_results"][0].get("citation_keys_detected") != ["smith2024shared"]:
            return _fail("source enrichment must keep the cited key on the best same-author/same-year title match")
        if smith_shared_overlap_enriched["external_results"][1].get("citation_keys_detected"):
            return _fail("source enrichment must not preserve shared citation keys for unrelated same-author/same-year titles that only partially overlap")
        if smith_shared_overlap_report["summary"]["external_results_with_citation_key_hits"] != 1:
            return _fail("source enrichment must count only the truly matched dependency row when same-author/same-year titles merely overlap")

        alias_root = root / "smith_alias_sources"
        alias_root.mkdir()
        (alias_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024arxiv,smith2024journal} throughout.\n",
            encoding="utf-8",
        )
        (alias_root / "refs.bib").write_text(
            "@article{smith2024arxiv,\n"
            "  title={Bandit Algorithms for Bounds},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n"
            "@article{smith2024journal,\n"
            "  title={Bandit Algorithms for Bounds},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        alias_ledger = copy.deepcopy(ledger)
        alias_ledger["external_results"] = [
            {
                "external_result_id": "smith.alias",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-alias"),
            }
        ]
        alias_enriched, alias_report = enrich_ledger_from_sources(
            ledger=alias_ledger,
            source_root=alias_root,
        )
        if set(alias_enriched["external_results"][0].get("citation_keys_detected", [])) != {"smith2024arxiv", "smith2024journal"}:
            return _fail("source enrichment must preserve equally valid cited citation-key aliases for the same dependency")
        if alias_report["summary"]["external_results_with_citation_key_hits"] != 1:
            return _fail("source enrichment must count a dependency with equally valid cited citation-key aliases as a current-run citation hit")
        generic_key_root = root / "generic_key_sources"
        generic_key_root.mkdir()
        (generic_key_root / "paper.tex").write_text(
            "We rely on \\cite{ref1} throughout.\n",
            encoding="utf-8",
        )
        (generic_key_root / "refs.bib").write_text(
            "@article{ref1,\n"
            "  title={Bandit Algorithms for Bounds},\n"
            "  author={Other, Pat},\n"
            "  year={1990}\n"
            "}\n",
            encoding="utf-8",
        )
        generic_key_ledger = copy.deepcopy(ledger)
        generic_key_ledger["external_results"] = [
            {
                "external_result_id": "smith.generic.key",
                "name": "Bandit Algorithms for Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithms for Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-generic-key"),
            }
        ]
        generic_key_enriched, generic_key_report = enrich_ledger_from_sources(
            ledger=generic_key_ledger,
            source_root=generic_key_root,
        )
        if generic_key_enriched["external_results"][0].get("citation_keys_detected"):
            return _fail("source enrichment must not bind cited generic BibTeX keys to externals on bibliography-title overlap alone")
        if generic_key_report["summary"]["external_results_with_citation_key_hits"] != 0:
            return _fail("source enrichment must not count generic cited keys as hits when author/year evidence disagrees")

        smith_overlap_root = root / "smith_overlap_sources"
        smith_overlap_root.mkdir()
        (smith_overlap_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024algbounds,smith2024lowerbounds} in the comparison section.\n",
            encoding="utf-8",
        )
        (smith_overlap_root / "refs.bib").write_text(
            "@article{smith2024algbounds,\n"
            "  title={Bandit Algorithmic Bounds},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n"
            "@article{smith2024lowerbounds,\n"
            "  title={Lower Bounds for Bandits},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        smith_overlap_ledger = copy.deepcopy(ledger)
        smith_overlap_ledger["external_results"] = [
            {
                "external_result_id": "smith.overlap",
                "name": "Bandit Algorithmic Bounds",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Bandit Algorithmic Bounds",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-overlap"),
            }
        ]
        smith_overlap_enriched, _smith_overlap_report = enrich_ledger_from_sources(
            ledger=smith_overlap_ledger,
            source_root=smith_overlap_root,
        )
        if smith_overlap_enriched["external_results"][0].get("citation_keys_detected") != ["smith2024algbounds"]:
            return _fail("source enrichment must keep only the best-scoring same-author/same-year citation key")

        smith_nested_root = root / "smith_nested_sources"
        smith_nested_root.mkdir()
        (smith_nested_root / "paper.tex").write_text(
            "We rely on \\cite{smith2024cluster,smith2024lower} in the appendix discussion.\n",
            encoding="utf-8",
        )
        (smith_nested_root / "refs.bib").write_text(
            "@article{smith2024cluster,\n"
            "  title={Sparse {C}lustering Methods},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n"
            "@article{smith2024lower,\n"
            "  title={Lower Bounds for Clustering},\n"
            "  author={Smith, Sam and Doe, Dana},\n"
            "  year={2024}\n"
            "}\n",
            encoding="utf-8",
        )
        smith_nested_ledger = copy.deepcopy(ledger)
        smith_nested_ledger["external_results"] = [
            {
                "external_result_id": "smith.cluster",
                "name": "Sparse Clustering Methods",
                "source_kind": "PAPER_CITATION",
                "citation_label": "Smith and Doe (2024) Sparse Clustering Methods",
                "citation_authors": ["Sam Smith", "Dana Doe"],
                "citation_year": 2024,
                "dependency_status": "UNRESOLVED",
                "review": _review("NEEDS_REVIEW", 0.5, "smith-nested"),
            }
        ]
        smith_nested_enriched, _smith_nested_report = enrich_ledger_from_sources(
            ledger=smith_nested_ledger,
            source_root=smith_nested_root,
        )
        if smith_nested_enriched["external_results"][0].get("citation_keys_detected") != ["smith2024cluster"]:
            return _fail("source enrichment must parse nested-brace BibTeX titles before disambiguating same-author/same-year citation keys")

        numbered_tex = root / "numbered_equations.tex"
        numbered_tex.write_text(
            "\\begin{equation}\\tag{10} x = y \\end{equation}\n"
            "\\begin{equation} y = z \\end{equation}\n",
            encoding="utf-8",
        )
        numbered_equations, _next_number = parse_equations(numbered_tex)
        if [eq.get("equation_number") for eq in numbered_equations] != [10, 11]:
            return _fail("source enrichment must advance global auto-numbering after an explicitly numbered equation")

        multifile_root = root / "multifile_sources"
        multifile_root.mkdir()
        (multifile_root / "main.tex").write_text(
            "\\begin{equation} a = b \\end{equation}\n"
            "\\input{body}\n"
            "\\begin{equation} e = f \\end{equation}\n",
            encoding="utf-8",
        )
        (multifile_root / "body.tex").write_text(
            "\\begin{equation} c = d \\end{equation}\n",
            encoding="utf-8",
        )
        multifile_ledger = copy.deepcopy(ledger)
        multifile_ledger["formalization_bindings"][0]["clause_links"][0]["equation_refs"] = [2]
        multifile_enriched, _multifile_report = enrich_ledger_from_sources(
            ledger=multifile_ledger,
            source_root=multifile_root,
        )
        multifile_clause = multifile_enriched["formalization_bindings"][0]["clause_links"][0]
        if multifile_clause.get("equation_ref_resolution") != "MATCHED":
            return _fail("source enrichment must preserve global auto-numbering across multi-file TeX roots")
        if multifile_clause.get("equation_expression_candidates") != ["c = d"]:
            return _fail("source enrichment must resolve equation refs against the inline include order of the globally numbered multi-file equation stream")
        multifile_ref = multifile_clause.get("equation_expression_source_refs", [{}])[0]
        if not str(multifile_ref.get("source_file", "")).endswith("body.tex"):
            return _fail("source enrichment must honor document include order when numbering equations across multiple TeX files")

        shared_root = root / "shared_sources"
        shared_root.mkdir()
        (shared_root / "appendix.tex").write_text(
            "\\begin{equation} q = r \\end{equation}\n",
            encoding="utf-8",
        )
        bounded_root = root / "bounded_sources"
        bounded_root.mkdir()
        (bounded_root / "main.tex").write_text(
            "\\input{../shared_sources/appendix}\n",
            encoding="utf-8",
        )
        bounded_ledger = copy.deepcopy(ledger)
        bounded_ledger["formalization_bindings"][0]["clause_links"][0]["equation_refs"] = [1]
        bounded_enriched, bounded_report = enrich_ledger_from_sources(
            ledger=bounded_ledger,
            source_root=bounded_root,
        )
        bounded_clause = bounded_enriched["formalization_bindings"][0]["clause_links"][0]
        if bounded_clause.get("equation_ref_resolution") != "UNMATCHED":
            return _fail("source enrichment must ignore TeX includes that escape the declared bounded source root")
        if bounded_report["summary"]["equations_detected"] != 0:
            return _fail("source enrichment must not count equations from TeX files outside the declared bounded source root")

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
        rerun_resynced, _rerun_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(resynced),
            annotation_files=[lean_file, sibling_lean],
        )
        rerun_ann_links = [x for x in rerun_resynced.get("lean_reverse_links", []) if x.get("link_origin") == "AUTO_FROM_ANNOTATION"]
        if sorted(
            (str(link.get("lean_ref", {}).get("file_path", "")), str(link.get("reverse_link_id", "")))
            for link in rerun_ann_links
        ) != sorted(
            (str(link.get("lean_ref", {}).get("file_path", "")), str(link.get("reverse_link_id", "")))
            for link in ann_links
        ):
            return _fail("reverse-link resync must be idempotent across identical reruns on unchanged ledgers")

        attr_lean = root / "AttrDemo.lean"
        attr_lean.write_text(
            "namespace Temp.Attr\n"
            "@[simp] theorem attr_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.attr\n"
            "  trivial\n"
            "private theorem hidden_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.hidden\n"
            "  trivial\n"
            "end Temp.Attr\n",
            encoding="utf-8",
        )
        attr_resynced, _attr_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[attr_lean],
        )
        attr_links = [
            x
            for x in attr_resynced.get("lean_reverse_links", [])
            if x.get("link_origin") == "AUTO_FROM_ANNOTATION"
        ]
        attr_by_span = {
            str(link.get("target", {}).get("span_id")): link
            for link in attr_links
        }
        if attr_by_span.get("span.attr", {}).get("lean_ref", {}).get("declaration_name") != "attr_decl":
            return _fail("reverse-link resync must recognize attributed theorem declarations")
        if attr_by_span.get("span.hidden", {}).get("lean_ref", {}).get("declaration_name") != "hidden_decl":
            return _fail("reverse-link resync must recognize private theorem declarations")
        multiline_attr_lean = root / "MultilineAttrDemo.lean"
        multiline_attr_lean.write_text(
            "namespace Temp.MultiAttr\n"
            "@[simp,\n"
            "  simp] theorem multi_attr_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.multi_attr\n"
            "  trivial\n"
            "end Temp.MultiAttr\n",
            encoding="utf-8",
        )
        multiline_attr_resynced, _multiline_attr_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[multiline_attr_lean],
        )
        multiline_attr_link = next(
            (
                link
                for link in multiline_attr_resynced.get("lean_reverse_links", [])
                if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
                and link.get("target", {}).get("span_id") == "span.multi_attr"
            ),
            None,
        )
        if not multiline_attr_link:
            return _fail("reverse-link resync must preserve annotations after multi-line attribute headers")
        if multiline_attr_link.get("lean_ref", {}).get("declaration_name") != "multi_attr_decl":
            return _fail("reverse-link resync must recognize declarations after multi-line attribute headers")
        cwd = Path.cwd()
        try:
            os.chdir(root)
            relative_resynced, _relative_report = resync_annotation_reverse_links(
                ledger=copy.deepcopy(enriched),
                annotation_files=[Path("AttrDemo.lean")],
            )
        finally:
            os.chdir(cwd)
        relative_ids = sorted(
            link["reverse_link_id"]
            for link in relative_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
        )
        absolute_ids = sorted(link["reverse_link_id"] for link in attr_links)
        if relative_ids != absolute_ids:
            return _fail("reverse-link resync should derive stable reverse_link_id values independent of annotation path spelling")
        relative_stored_ledger = copy.deepcopy(attr_resynced)
        for link in relative_stored_ledger.get("lean_reverse_links", []):
            if link.get("link_origin") != "AUTO_FROM_ANNOTATION":
                continue
            lean_ref = link.get("lean_ref", {})
            lean_ref = lean_ref if isinstance(lean_ref, dict) else {}
            file_path = Path(str(lean_ref.get("file_path", "")))
            try:
                lean_ref["file_path"] = file_path.resolve().relative_to(root).as_posix()
            except ValueError:
                continue
            link["lean_ref"] = lean_ref
        shifted_cwd = root / "shifted_cwd"
        shifted_cwd.mkdir()
        cwd = Path.cwd()
        try:
            os.chdir(shifted_cwd)
            relative_stored_resynced, _relative_stored_report = resync_annotation_reverse_links(
                ledger=copy.deepcopy(relative_stored_ledger),
                annotation_files=[attr_lean],
            )
        finally:
            os.chdir(cwd)
        relative_stored_links = [
            x
            for x in relative_stored_resynced.get("lean_reverse_links", [])
            if x.get("link_origin") == "AUTO_FROM_ANNOTATION"
        ]
        if sorted(link["reverse_link_id"] for link in relative_stored_links) != absolute_ids:
            return _fail("reverse-link resync must stay idempotent when stored annotation file paths are relative and the caller cwd changes")

        multi_namespace_lean = root / "MultiNamespace.lean"
        multi_namespace_lean.write_text(
            "namespace Temp.First\n"
            "theorem first_decl : True := by\n"
            "  trivial\n"
            "end Temp.First\n"
            "namespace Temp.Second\n"
            "theorem second_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.multi\n"
            "  trivial\n"
            "end Temp.Second\n",
            encoding="utf-8",
        )
        multi_namespace_resynced, _multi_namespace_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[multi_namespace_lean],
        )
        multi_namespace_links = [
            link
            for link in multi_namespace_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
        ]
        multi_namespace_link = next(
            (link for link in multi_namespace_links if link.get("target", {}).get("span_id") == "span.multi"),
            None,
        )
        if not multi_namespace_link:
            return _fail("reverse-link resync must preserve annotations that appear in later namespace blocks")
        if multi_namespace_link.get("lean_ref", {}).get("module") != "Temp.Second":
            return _fail("reverse-link resync must infer module names from the annotation's active namespace block")

        top_level_after_namespace_lean = root / "TopLevelAfterNamespace.lean"
        top_level_after_namespace_lean.write_text(
            "namespace Temp.First\n"
            "theorem first_decl : True := by\n"
            "  trivial\n"
            "end Temp.First\n"
            "theorem top_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.top\n"
            "  trivial\n",
            encoding="utf-8",
        )
        top_level_after_namespace_resynced, _top_level_after_namespace_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[top_level_after_namespace_lean],
        )
        top_level_after_namespace_link = next(
            (
                link
                for link in top_level_after_namespace_resynced.get("lean_reverse_links", [])
                if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
                and link.get("target", {}).get("span_id") == "span.top"
            ),
            None,
        )
        if not top_level_after_namespace_link:
            return _fail("reverse-link resync must preserve annotations that return to top-level scope after a namespace block ends")
        if top_level_after_namespace_link.get("lean_ref", {}).get("module") != "":
            return _fail("reverse-link resync must preserve top-level module scope after a preceding namespace block closes")

        relative_namespace_lean = root / "RelativeNamespace.lean"
        relative_namespace_lean.write_text(
            "namespace Outer\n"
            "namespace Sibling\n"
            "theorem nested_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.relative\n"
            "  trivial\n"
            "end Sibling\n"
            "end Outer\n",
            encoding="utf-8",
        )
        relative_namespace_resynced, _relative_namespace_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[relative_namespace_lean],
        )
        relative_namespace_link = next(
            (
                link
                for link in relative_namespace_resynced.get("lean_reverse_links", [])
                if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
                and link.get("target", {}).get("span_id") == "span.relative"
            ),
            None,
        )
        if not relative_namespace_link:
            return _fail("reverse-link resync must preserve annotations inside nested relative namespace blocks")
        if relative_namespace_link.get("lean_ref", {}).get("module") != "Outer.Sibling":
            return _fail("reverse-link resync must compose nested relative namespace blocks into the active module path")
        repeated_namespace_lean = root / "RepeatedNamespace.lean"
        repeated_namespace_lean.write_text(
            "namespace Outer\n"
            "namespace Outer.Sibling\n"
            "theorem repeated_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.repeated\n"
            "  trivial\n"
            "end Outer.Sibling\n"
            "end Outer\n",
            encoding="utf-8",
        )
        repeated_namespace_resynced, _repeated_namespace_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[repeated_namespace_lean],
        )
        repeated_namespace_link = next(
            (
                link
                for link in repeated_namespace_resynced.get("lean_reverse_links", [])
                if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
                and link.get("target", {}).get("span_id") == "span.repeated"
            ),
            None,
        )
        if not repeated_namespace_link:
            return _fail("reverse-link resync must preserve annotations inside repeated qualified namespace headers")
        if repeated_namespace_link.get("lean_ref", {}).get("module") != "Outer.Outer.Sibling":
            return _fail("reverse-link resync must keep repeated qualified namespace headers relative to the current namespace scope")

        section_namespace_lean = root / "SectionNamespace.lean"
        section_namespace_lean.write_text(
            "namespace Outer\n"
            "section Local\n"
            "theorem local_decl : True := by\n"
            "  trivial\n"
            "end Local\n"
            "theorem scoped_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.section\n"
            "  trivial\n"
            "end Outer\n",
            encoding="utf-8",
        )
        section_namespace_resynced, _section_namespace_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[section_namespace_lean],
        )
        section_namespace_link = next(
            (
                link
                for link in section_namespace_resynced.get("lean_reverse_links", [])
                if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
                and link.get("target", {}).get("span_id") == "span.section"
            ),
            None,
        )
        if not section_namespace_link:
            return _fail("reverse-link resync must preserve annotations that appear after non-namespace end blocks inside a namespace")
        if section_namespace_link.get("lean_ref", {}).get("module") != "Outer":
            return _fail("reverse-link resync must ignore section/end blocks when inferring namespace module scope")

        pre_namespace_lean = root / "PreNamespace.lean"
        pre_namespace_lean.write_text(
            "theorem pre_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.pre\n"
            "  trivial\n"
            "namespace Later.Namespace\n"
            "theorem later_decl : True := by\n"
            "  trivial\n"
            "end Later.Namespace\n",
            encoding="utf-8",
        )
        pre_namespace_resynced, _pre_namespace_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[pre_namespace_lean],
        )
        pre_namespace_link = next(
            (
                link
                for link in pre_namespace_resynced.get("lean_reverse_links", [])
                if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
                and link.get("target", {}).get("span_id") == "span.pre"
            ),
            None,
        )
        if not pre_namespace_link:
            return _fail("reverse-link resync must preserve annotations that appear before the first namespace block in a file")
        if pre_namespace_link.get("lean_ref", {}).get("module") != "":
            return _fail("reverse-link resync must keep top-level annotations top-level even if a later namespace block appears in the same file")

        no_namespace_lean = root / "NoNamespace.lean"
        no_namespace_lean.write_text(
            "theorem plain_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.nonamespace\n"
            "  trivial\n",
            encoding="utf-8",
        )
        no_namespace_resynced, _no_namespace_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[no_namespace_lean],
        )
        no_namespace_link = next(
            (
                link
                for link in no_namespace_resynced.get("lean_reverse_links", [])
                if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
                and link.get("target", {}).get("span_id") == "span.nonamespace"
            ),
            None,
        )
        if not no_namespace_link:
            return _fail("reverse-link resync must preserve annotations in files with no namespace blocks")
        if no_namespace_link.get("lean_ref", {}).get("module") != "":
            return _fail("reverse-link resync must preserve empty module scope for files with no namespace blocks")

        collision_a = root / "CollisionA.lean"
        collision_b = root / "CollisionB.lean"
        collision_text = (
            "namespace Temp.Collision\n"
            "private theorem hidden_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.shared\n"
            "  trivial\n"
            "end Temp.Collision\n"
        )
        collision_a.write_text(collision_text, encoding="utf-8")
        collision_b.write_text(collision_text, encoding="utf-8")
        collision_resynced, _collision_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[collision_a, collision_b],
        )
        collision_links = [
            link
            for link in collision_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
        ]
        if len(collision_links) != 2:
            return _fail("reverse-link resync must preserve one AUTO_FROM_ANNOTATION link per matching file even when declaration metadata repeats")
        if len({link["reverse_link_id"] for link in collision_links}) != 2:
            return _fail("reverse-link resync must keep AUTO_FROM_ANNOTATION ids unique across different files with identical declaration metadata")

        workspace_a = root / "workspace_a"
        workspace_b = root / "workspace_b"
        for workspace in (workspace_a, workspace_b):
            workspace.mkdir()
            (workspace / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.0.0'\n", encoding="utf-8")
        portable_rel = Path("Formalization") / "PortableDemo.lean"
        portable_a = workspace_a / portable_rel
        portable_b = workspace_b / portable_rel
        portable_a.parent.mkdir(parents=True, exist_ok=True)
        portable_b.parent.mkdir(parents=True, exist_ok=True)
        portable_text = (
            "namespace Temp.Portable\n"
            "theorem portable_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.portable\n"
            "  trivial\n"
            "end Temp.Portable\n"
        )
        portable_a.write_text(portable_text, encoding="utf-8")
        portable_b.write_text(portable_text, encoding="utf-8")
        portable_a_resynced, _portable_a_report = resync_annotation_reverse_links(
            ledger=_ledger(portable_a),
            annotation_files=[portable_a],
        )
        portable_b_resynced, _portable_b_report = resync_annotation_reverse_links(
            ledger=_ledger(portable_b),
            annotation_files=[portable_b],
        )
        portable_a_ids = sorted(
            link["reverse_link_id"]
            for link in portable_a_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
        )
        portable_b_ids = sorted(
            link["reverse_link_id"]
            for link in portable_b_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
        )
        if portable_a_ids != portable_b_ids:
            return _fail("reverse-link resync should derive stable AUTO_FROM_ANNOTATION ids independent of checkout root path")
        portable_dual_resynced, _portable_dual_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[portable_a, portable_b],
        )
        portable_dual_links = [
            link
            for link in portable_dual_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
            and link.get("target", {}).get("span_id") == "span.portable"
        ]
        if len(portable_dual_links) != 2:
            return _fail("reverse-link resync must preserve one AUTO_FROM_ANNOTATION link per same-layout workspace when they are resynced together")
        if len({link["reverse_link_id"] for link in portable_dual_links}) != 2:
            return _fail("reverse-link resync must keep simultaneous same-layout workspace annotation ids unique")
        portable_partial_resynced, _portable_partial_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(portable_dual_resynced),
            annotation_files=[portable_a],
        )
        portable_partial_links = [
            link
            for link in portable_partial_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
            and link.get("target", {}).get("span_id") == "span.portable"
        ]
        if len(portable_partial_links) != 2:
            return _fail("partial reverse-link resync must preserve same-layout workspace links that were not targeted")
        moved_portable_resynced, _moved_portable_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(portable_a_resynced),
            annotation_files=[portable_b],
        )
        moved_portable_links = [
            link
            for link in moved_portable_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
        ]
        if len(moved_portable_links) != 1:
            return _fail("reverse-link resync must refresh prior AUTO_FROM_ANNOTATION rows instead of duplicating them across checkout roots")
        if moved_portable_links[0].get("lean_ref", {}).get("file_path") != str(portable_b.resolve()):
            return _fail("reverse-link resync must refresh the surviving AUTO_FROM_ANNOTATION row to the current checkout path")
        portable_multi_a = workspace_a / "Formalization" / "PortableMulti.lean"
        portable_multi_b = workspace_b / "Formalization" / "PortableMulti.lean"
        portable_multi_text = (
            "namespace Temp.Portable\n"
            "theorem portable_multi_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.portable.a\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.portable.b\n"
            "  trivial\n"
            "end Temp.Portable\n"
        )
        portable_multi_a.write_text(portable_multi_text, encoding="utf-8")
        portable_multi_b.write_text(portable_multi_text, encoding="utf-8")
        portable_multi_a_resynced, _portable_multi_a_report = resync_annotation_reverse_links(
            ledger=_ledger(portable_multi_a),
            annotation_files=[portable_multi_a],
        )
        moved_portable_multi_resynced, _moved_portable_multi_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(portable_multi_a_resynced),
            annotation_files=[portable_multi_b],
        )
        moved_portable_multi_links = [
            link
            for link in moved_portable_multi_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
            and link.get("target", {}).get("span_id") in {"span.portable.a", "span.portable.b"}
        ]
        if len(moved_portable_multi_links) != 2:
            return _fail("reverse-link resync must refresh multi-annotation files in place when the stable file identity moves across checkout roots")
        if {link.get("lean_ref", {}).get("file_path") for link in moved_portable_multi_links} != {str(portable_multi_b.resolve())}:
            return _fail("reverse-link resync must rewrite every surviving multi-annotation row to the current checkout path")

        unmarked_root = root / "unmarked_workspace"
        unmarked_a = unmarked_root / "a" / "Demo.lean"
        unmarked_b = unmarked_root / "b" / "Demo.lean"
        unmarked_a.parent.mkdir(parents=True, exist_ok=True)
        unmarked_b.parent.mkdir(parents=True, exist_ok=True)
        unmarked_text = (
            "namespace Temp.Unmarked\n"
            "private theorem hidden_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.unmarked\n"
            "  trivial\n"
            "end Temp.Unmarked\n"
        )
        unmarked_a.write_text(unmarked_text, encoding="utf-8")
        unmarked_b.write_text(unmarked_text, encoding="utf-8")
        unmarked_resynced, _unmarked_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[unmarked_a, unmarked_b],
        )
        unmarked_links = [
            link
            for link in unmarked_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
            and link.get("target", {}).get("span_id") == "span.unmarked"
        ]
        if len(unmarked_links) != 2:
            return _fail("reverse-link resync must preserve one AUTO_FROM_ANNOTATION link per same-basename file in unmarked workspaces")
        if len({link["reverse_link_id"] for link in unmarked_links}) != 2:
            return _fail("reverse-link resync must keep AUTO_FROM_ANNOTATION ids unique for same-basename files in unmarked workspaces")
        unmarked_reordered_resynced, _unmarked_reordered_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[unmarked_b, unmarked_a],
        )
        unmarked_ids_by_file = {
            str(link.get("lean_ref", {}).get("file_path", "")): str(link.get("reverse_link_id", ""))
            for link in unmarked_links
        }
        reordered_ids_by_file = {
            str(link.get("lean_ref", {}).get("file_path", "")): str(link.get("reverse_link_id", ""))
            for link in unmarked_reordered_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
            and link.get("target", {}).get("span_id") == "span.unmarked"
        }
        if reordered_ids_by_file != unmarked_ids_by_file:
            return _fail("reverse-link resync must derive the same AUTO_FROM_ANNOTATION ids regardless of annotation file discovery order")

        unmarked_portable_root = root / "unmarked_portable"
        unmarked_portable_a = unmarked_portable_root / "workspace_a" / "Formalization" / "Demo.lean"
        unmarked_portable_b = unmarked_portable_root / "workspace_b" / "Formalization" / "Demo.lean"
        unmarked_portable_a.parent.mkdir(parents=True, exist_ok=True)
        unmarked_portable_b.parent.mkdir(parents=True, exist_ok=True)
        unmarked_portable_text = (
            "namespace Temp.UnmarkedPortable\n"
            "theorem portable_decl : True := by\n"
            "  -- LEAN_LINK claim_id=demo.claim.1 clause_id=demo.clause.eq_1 span_id=span.unmarked_portable\n"
            "  trivial\n"
            "end Temp.UnmarkedPortable\n"
        )
        unmarked_portable_a.write_text(unmarked_portable_text, encoding="utf-8")
        unmarked_portable_b.write_text(unmarked_portable_text, encoding="utf-8")
        unmarked_portable_dual_resynced, _unmarked_portable_dual_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(enriched),
            annotation_files=[unmarked_portable_a, unmarked_portable_b],
        )
        unmarked_portable_partial_resynced, _unmarked_portable_partial_report = resync_annotation_reverse_links(
            ledger=copy.deepcopy(unmarked_portable_dual_resynced),
            annotation_files=[unmarked_portable_a],
        )
        unmarked_portable_links = [
            link
            for link in unmarked_portable_partial_resynced.get("lean_reverse_links", [])
            if link.get("link_origin") == "AUTO_FROM_ANNOTATION"
            and link.get("target", {}).get("span_id") == "span.unmarked_portable"
        ]
        if len(unmarked_portable_links) != 2:
            return _fail("partial reverse-link resync must preserve marker-less same-layout workspace links that were not targeted")

        null_clause_ledger = copy.deepcopy(enriched)
        null_clause_ledger["formalization_bindings"][0]["clause_links"] = [{"clause_id": None}]
        null_clause_ledger["clause_atoms"][0]["parent_clause_id"] = None
        null_clause_ledger["lean_anchors"][0]["clause_id"] = None
        null_clause_todo = build_review_todo(
            ledger=null_clause_ledger,
            consistency_report=None,
            focus=["ATOM_MAPPING"],
            min_risk=0.0,
            top_k=10,
            include_locked=False,
        )
        null_pointers = null_clause_todo["items"][0]["pointers"]
        if null_pointers.get("clause_id") is not None:
            return _fail("review todo must treat schema-valid null clause ids as absent, not as the literal string None")
        if null_pointers.get("binding_id") is not None:
            return _fail("review todo must not derive bogus binding ids from null clause buckets")

        ambiguous_binding_ledger = copy.deepcopy(enriched)
        ambiguous_binding_ledger["formalization_bindings"].append(
            {
                "binding_id": "demo.bind.2",
                "claim_id": "demo.claim.1",
                "formalization_status": "PARTIAL",
                "external_dependency_status": "UNRESOLVED",
                "external_dependency_result_ids": ["demo.external.1"],
                "lean_target": {
                    "module": "Temp.Demo",
                    "file_path": str(lean_file),
                    "declaration_name": "later_decl",
                    "line": 4,
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
                        "review": _review("NEEDS_REVIEW", 0.4, "clause-ambiguous"),
                    }
                ],
                "review": _review("NEEDS_REVIEW", 0.52, "binding-ambiguous"),
            }
        )
        ambiguous_todo = build_review_todo(
            ledger=ambiguous_binding_ledger,
            consistency_report={
                "issues": [
                    {
                        "severity": "WARN",
                        "code": "MAPPING_ANCHOR_MISSING",
                        "ref": {
                            "clause_id": "demo.clause.eq_1",
                            "binding_id": "demo.bind.2",
                        },
                    }
                ]
            },
            focus=["ATOM_MAPPING"],
            min_risk=0.0,
            top_k=10,
            include_locked=False,
        )
        ambiguous_rows = [
            row
            for row in ambiguous_todo["items"]
            if row.get("entity_type") == "ATOM_MAPPING" and row.get("entity_id") == "demo.map.1"
        ]
        if len(ambiguous_rows) != 1:
            return _fail("review todo must keep the target atom mapping visible even when a clause maps to multiple bindings")
        if ambiguous_rows[0]["pointers"].get("binding_id") is not None:
            return _fail("review todo must not guess a binding pointer when the clause maps to multiple bindings")
        if ambiguous_rows[0]["issue_count"] != 0:
            return _fail("review todo must not attach binding-scoped issues to mappings whose binding cannot be determined unambiguously")

        relative_source_root = Path("relative_source_bundle")
        relative_source_dir = root / relative_source_root
        relative_source_dir.mkdir()
        (relative_source_dir / "main.tex").write_text(
            "\\begin{equation}\n"
            "  x = y\n"
            "\\end{equation}\n",
            encoding="utf-8",
        )
        relative_source_ledger = copy.deepcopy(ledger)
        cwd = Path.cwd()
        try:
            os.chdir(root)
            relative_source_enriched, relative_source_report = enrich_ledger_from_sources(
                ledger=relative_source_ledger,
                source_root=relative_source_root,
            )
        finally:
            os.chdir(cwd)
        relative_equations = relative_source_report["equation_index"]["equations"]
        if not relative_equations:
            return _fail("relative source-root enrichment should still produce an equation index")
        if relative_equations[0].get("source_file") != "relative_source_bundle/main.tex":
            return _fail("source enrichment must preserve repo-relative equation source paths when source_root is relative")
        relative_source_ref = relative_source_enriched["formalization_bindings"][0]["clause_links"][0].get(
            "equation_expression_source_refs",
            [{}],
        )[0]
        if relative_source_ref.get("source_file") != "relative_source_bundle/main.tex":
            return _fail("source enrichment must preserve repo-relative clause source refs when source_root is relative")

    print("[formalization-frontier] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
