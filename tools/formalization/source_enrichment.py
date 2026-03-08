#!/usr/bin/env python3
"""Deterministic formalization ledger source enrichment from LaTeX/Bib sources."""

from __future__ import annotations

import copy
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EQ_ENV_RE = re.compile(
    r"\\begin\{(?P<env>equation\*?|align\*?|gather\*?|multline\*?|eqnarray\*?)\}"
    r"(?P<body>.*?)"
    r"\\end\{(?P=env)\}",
    re.DOTALL,
)
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
TAG_RE = re.compile(r"\\tag\{([^}]+)\}")
CITE_RE = re.compile(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}")
BIB_ENTRY_RE = re.compile(r"@[a-zA-Z]+\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_ws(text: Any) -> str:
    return " ".join(str(text).strip().split())


def strip_tex_comments(text: str) -> str:
    out: list[str] = []
    for raw in text.splitlines():
        line: list[str] = []
        for index, ch in enumerate(raw):
            if ch == "%" and (index == 0 or raw[index - 1] != "\\"):
                break
            line.append(ch)
        out.append("".join(line))
    return "\n".join(out)


def dedupe_preserve(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def collect_source_files(root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    root = root.expanduser()
    if root.is_file():
        if root.suffix.lower() == ".tex":
            return [root], [], []
        if root.suffix.lower() == ".bib":
            return [], [root], []
        if root.suffix.lower() == ".pdf":
            return [], [], [root]
        raise ValueError(f"unsupported source file extension: {root}")
    tex_files = sorted(root.rglob("*.tex"))
    bib_files = sorted(root.rglob("*.bib"))
    pdf_files = sorted(root.rglob("*.pdf"))
    return tex_files, bib_files, pdf_files


def normalize_equation_text(raw_body: str) -> str:
    text = LABEL_RE.sub("", raw_body)
    text = TAG_RE.sub("", text)
    text = re.sub(r"\\nonumber\b", "", text)
    text = re.sub(r"\\notag\b", "", text)
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", text)
    text = re.sub(r"\\([a-zA-Z]+)", r"\1", text)
    text = text.replace("{", " ").replace("}", " ").replace("&", " ")
    text = re.sub(r"\\\\", " ; ", text)
    return normalize_ws(text)


def parse_equations(tex_file: Path) -> list[dict[str, Any]]:
    text = strip_tex_comments(tex_file.read_text(encoding="utf-8", errors="ignore"))
    equations: list[dict[str, Any]] = []
    auto_number = 1
    for match in EQ_ENV_RE.finditer(text):
        body = str(match.group("body"))
        labels = LABEL_RE.findall(body)
        tags = TAG_RE.findall(body)
        equation_number: int | None = None
        for tag in tags:
            number = re.search(r"\d+", tag)
            if number:
                equation_number = int(number.group(0))
                break
        if equation_number is None:
            for label in labels:
                number = re.search(r"(\d+)$", label)
                if number:
                    equation_number = int(number.group(1))
                    break
        if equation_number is None:
            equation_number = auto_number
        auto_number += 1
        start_line = text[: match.start()].count("\n") + 1
        end_line = start_line + match.group(0).count("\n")
        equations.append(
            {
                "source_file": str(tex_file),
                "line_start": start_line,
                "line_end": end_line,
                "environment": str(match.group("env")),
                "labels": labels,
                "tags": tags,
                "equation_number": equation_number,
                "raw_equation_text": normalize_ws(body),
                "normalized_equation_text": normalize_equation_text(body),
            }
        )
    return equations


def parse_citations_from_tex(tex_file: Path) -> Counter[str]:
    text = strip_tex_comments(tex_file.read_text(encoding="utf-8", errors="ignore"))
    counter: Counter[str] = Counter()
    for match in CITE_RE.finditer(text):
        for key in match.group(1).split(","):
            norm = normalize_ws(key)
            if norm:
                counter[norm] += 1
    return counter


def parse_bibliography_keys(bib_file: Path) -> Counter[str]:
    text = bib_file.read_text(encoding="utf-8", errors="ignore")
    counter: Counter[str] = Counter()
    for match in BIB_ENTRY_RE.finditer(text):
        key = normalize_ws(match.group(1))
        if key:
            counter[key] += 1
    return counter


def ext_author_tokens(external: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for author in external.get("citation_authors", []):
        last = re.sub(r"[^a-z]", "", normalize_ws(author).lower().split()[-1] if normalize_ws(author) else "")
        if last:
            tokens.append(last)
    return dedupe_preserve(tokens)


def key_score(key: str, text: str, surnames: list[str], year: str) -> int:
    haystack = key.lower()
    score = 0
    if year and year in haystack:
        score += 2
    for surname in surnames:
        if surname and surname in haystack:
            score += 2
    return score


def match_external_keys(external: dict[str, Any], *, key_counter: Counter[str], max_keys: int) -> list[str]:
    year = normalize_ws(external.get("citation_year", ""))
    surnames = ext_author_tokens(external)
    scored: list[tuple[int, str]] = []
    label = normalize_ws(external.get("citation_label", ""))
    name = normalize_ws(external.get("name", ""))
    for key in key_counter:
        score = key_score(key, f"{label} {name}", surnames, year)
        if score > 0:
            scored.append((score, key))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return dedupe_preserve([key for _score, key in scored])[:max(1, max_keys)]


def enrich_clause_link_with_equations(
    clause: dict[str, Any],
    *,
    equations_by_number: dict[int, list[dict[str, Any]]],
    max_expr: int,
) -> tuple[dict[str, Any], int]:
    enriched = dict(clause)
    refs = {
        int(value)
        for value in clause.get("equation_refs", [])
        if isinstance(value, int) and value > 0
    }
    if isinstance(clause.get("equation_number"), int):
        refs.add(int(clause["equation_number"]))
    if not refs:
        return enriched, 0

    labels: list[str] = []
    expressions: list[str] = []
    source_refs: list[dict[str, Any]] = []
    unresolved = 0
    for ref in sorted(refs):
        items = equations_by_number.get(ref, [])
        if not items:
            unresolved += 1
            continue
        for item in items[: max(1, max_expr)]:
            labels.extend(str(label) for label in item.get("labels", []) if normalize_ws(label))
            expr = normalize_ws(item.get("normalized_equation_text", ""))
            if expr:
                expressions.append(expr)
            source_refs.append(
                {
                    "source_file": str(item.get("source_file", "")),
                    "line_start": int(item.get("line_start", 1)),
                    "line_end": int(item.get("line_end", 1)),
                    "equation_number": int(item.get("equation_number", ref)),
                    "label": str(item.get("labels", [""])[0]) if item.get("labels") else "",
                    "environment": str(item.get("environment", "")),
                }
            )
    enriched["equation_label_candidates"] = dedupe_preserve(labels)
    enriched["equation_expression_candidates"] = dedupe_preserve(expressions)[: max(1, max_expr)]
    enriched["equation_expression_source_refs"] = source_refs[: max(1, max_expr)]
    if unresolved == 0:
        enriched["equation_ref_resolution"] = "MATCHED"
    elif unresolved < len(refs):
        enriched["equation_ref_resolution"] = "PARTIAL"
    else:
        enriched["equation_ref_resolution"] = "UNMATCHED"
    return enriched, unresolved


def enrich_ledger_from_sources(
    ledger: dict[str, Any],
    *,
    source_root: Path,
    max_equation_candidates: int = 3,
    max_citation_keys: int = 8,
) -> tuple[dict[str, Any], dict[str, Any]]:
    enriched = copy.deepcopy(ledger)
    tex_files, bib_files, pdf_files = collect_source_files(source_root)
    equations: list[dict[str, Any]] = []
    cite_counter: Counter[str] = Counter()
    bib_key_counter: Counter[str] = Counter()
    for tex_file in tex_files:
        equations.extend(parse_equations(tex_file))
        cite_counter.update(parse_citations_from_tex(tex_file))
    for bib_file in bib_files:
        bib_key_counter.update(parse_bibliography_keys(bib_file))

    equations_by_number: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for equation in equations:
        number = equation.get("equation_number")
        if isinstance(number, int):
            equations_by_number[number].append(equation)

    unresolved_total = 0
    bindings_enriched = 0
    for binding in enriched.get("formalization_bindings", []):
        if not isinstance(binding, dict):
            continue
        clause_links = binding.get("clause_links", [])
        if not isinstance(clause_links, list):
            continue
        new_clause_links: list[dict[str, Any]] = []
        changed = False
        for clause in clause_links:
            if not isinstance(clause, dict):
                new_clause_links.append(clause)
                continue
            new_clause, unresolved = enrich_clause_link_with_equations(
                clause,
                equations_by_number=equations_by_number,
                max_expr=max_equation_candidates,
            )
            unresolved_total += unresolved
            changed = changed or new_clause != clause
            new_clause_links.append(new_clause)
        if changed:
            binding["clause_links"] = new_clause_links
            bindings_enriched += 1

    external_hits = 0
    for external in enriched.get("external_results", []):
        if not isinstance(external, dict):
            continue
        existing_detected = [
            normalize_ws(key)
            for key in external.get("citation_keys_detected", [])
            if normalize_ws(key)
        ]
        existing_usage_counts = {
            normalize_ws(item.get("key", "")): int(item.get("count", 0))
            for item in external.get("citation_key_usage_counts", [])
            if isinstance(item, dict) and normalize_ws(item.get("key", ""))
        }
        existing_bibliography_candidates = [
            normalize_ws(key)
            for key in external.get("bibliography_entry_candidates", [])
            if normalize_ws(key)
        ]
        existing_bib_source_files = [
            normalize_ws(path)
            for path in external.get("bib_source_files", [])
            if normalize_ws(path)
        ]
        matched = match_external_keys(external, key_counter=cite_counter, max_keys=max_citation_keys)
        bibliography_candidates = match_external_keys(
            external,
            key_counter=bib_key_counter,
            max_keys=max_citation_keys,
        )
        merged_detected = dedupe_preserve(existing_detected + matched)
        merged_bibliography_candidates = dedupe_preserve(
            existing_bibliography_candidates + bibliography_candidates
        )
        if merged_detected:
            external_hits += 1
        external["citation_keys_detected"] = merged_detected
        merged_usage_counts = dict(existing_usage_counts)
        for key in matched:
            if int(cite_counter[key]) > 0:
                merged_usage_counts[key] = int(cite_counter[key])
        external["citation_key_usage_counts"] = [
            {"key": key, "count": int(merged_usage_counts[key])}
            for key in merged_detected
            if int(merged_usage_counts.get(key, 0)) > 0
        ]
        external["bibliography_entry_candidates"] = merged_bibliography_candidates
        external["bib_source_files"] = (
            dedupe_preserve(existing_bib_source_files + [str(path) for path in bib_files])
            if merged_bibliography_candidates
            else []
        )
        if matched:
            retrieval_queries = [normalize_ws(query) for query in external.get("retrieval_queries", []) if normalize_ws(query)]
            retrieval_queries.extend(f"{key} {normalize_ws(external.get('citation_label', ''))}".strip() for key in matched)
            external["retrieval_queries"] = dedupe_preserve([query for query in retrieval_queries if query])

    audit = enriched.setdefault("audit", {"coverage": {}, "notes": []})
    if not isinstance(audit, dict):
        raise ValueError("ledger.audit must be an object")
    audit["latex_enrichment"] = {
        "enabled": True,
        "source_root": str(source_root),
        "tex_file_count": len(tex_files),
        "bib_file_count": len(bib_files),
        "pdf_file_count": len(pdf_files),
        "equations_detected": len(equations),
        "equation_ref_unresolved_count": int(unresolved_total),
        "citation_keys_detected": len(cite_counter),
        "external_results_with_citation_key_hits": external_hits,
        "generated_at_utc": utc_now_iso(),
    }

    report = {
        "generated_at_utc": utc_now_iso(),
        "source_root": str(source_root),
        "summary": {
            "tex_file_count": len(tex_files),
            "bib_file_count": len(bib_files),
            "pdf_file_count": len(pdf_files),
            "equations_detected": len(equations),
            "bindings_enriched_with_equations": bindings_enriched,
            "equation_ref_unresolved_count": int(unresolved_total),
            "citation_keys_detected": len(cite_counter),
            "external_results_with_citation_key_hits": external_hits,
        },
        "equation_index": {"equations": equations},
        "citation_index": {"citation_key_counts": dict(sorted(cite_counter.items()))},
    }
    return enriched, report
