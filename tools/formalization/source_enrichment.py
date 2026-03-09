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
INCLUDE_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
BIBLIOGRAPHY_RE = re.compile(r"\\bibliography\{([^}]+)\}")
ADDBIBRESOURCE_RE = re.compile(r"\\addbibresource(?:\[[^\]]*\])?\{([^}]+)\}")
WORD_RE = re.compile(r"[a-z0-9]+")
GENERIC_AUTHOR_YEAR_SUFFIX_RE = re.compile(r"^(?:|[a-z]{1,2}|etal[a-z]{0,2})$")


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


def signature_tokens(text: Any) -> list[str]:
    stopwords = {"with", "from", "into", "over", "under", "revisited", "paper", "result", "theorem"}
    out: list[str] = []
    seen: set[str] = set()
    for raw in WORD_RE.findall(normalize_ws(text).lower()):
        if len(raw) < 4 or raw in stopwords:
            continue
        candidates = [raw]
        if raw.endswith("s") and len(raw) > 4:
            candidates.append(raw[:-1])
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            out.append(candidate)
    return out


def collect_source_files(root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    root = root.expanduser()
    if root.is_file():
        if root.suffix.lower() == ".tex":
            bounded_root = _bounded_tex_source_root(root)
            if bounded_root is None:
                raise ValueError(f"unsupported TeX entrypoint: {root}")
            tex_files = ordered_tex_files(root)
            return (
                tex_files,
                _collect_bibliography_files(root=root, tex_files=tex_files),
                [],
            )
        if root.suffix.lower() == ".bib":
            return [], [root.resolve()], []
        if root.suffix.lower() == ".pdf":
            return [], [], [root.resolve()]
        raise ValueError(f"unsupported source file extension: {root}")
    tex_files = ordered_tex_files(root)
    bib_files = _collect_bibliography_files(root=root, tex_files=tex_files)
    pdf_files = sorted(path.resolve() for path in root.rglob("*.pdf"))
    return tex_files, bib_files, pdf_files


def _bounded_tex_source_root(root: Path) -> Path | None:
    root = root.expanduser()
    if root.is_dir():
        return root.resolve()
    if root.is_file() and root.suffix.lower() == ".tex":
        return root.resolve().parent
    return None


def _display_source_path(*, source_root: Path, path: Path) -> str:
    root = source_root.expanduser()
    resolved = path.expanduser().resolve()
    if root.is_absolute():
        return str(resolved)
    cwd = Path.cwd().resolve()
    try:
        return resolved.relative_to(cwd).as_posix()
    except ValueError:
        resolved_root = root.resolve()
        base_root = resolved_root.parent if root.suffix else resolved_root
        prefix = root.parent if root.suffix else root
        try:
            return (prefix / resolved.relative_to(base_root)).as_posix()
        except ValueError:
            return str(resolved)


def _resolve_bibliography_target(*, current_file: Path, raw_target: str, bounded_root: Path | None) -> Path | None:
    target = normalize_ws(raw_target)
    if not target:
        return None
    candidate = (current_file.parent / target).expanduser()
    if candidate.suffix.lower() != ".bib":
        candidate = candidate.with_suffix(".bib")
    candidate = candidate.resolve()
    if not candidate.exists():
        return None
    if bounded_root is not None:
        try:
            candidate.relative_to(bounded_root)
        except ValueError:
            return None
    return candidate


def _collect_referenced_bibliography_files(*, tex_files: list[Path], bounded_root: Path | None) -> list[Path]:
    referenced: list[Path] = []
    seen: set[Path] = set()
    for tex_file in tex_files:
        text = strip_tex_comments(tex_file.read_text(encoding="utf-8", errors="ignore"))
        for pattern in (BIBLIOGRAPHY_RE, ADDBIBRESOURCE_RE):
            for match in pattern.finditer(text):
                for raw_target in str(match.group(1)).split(","):
                    candidate = _resolve_bibliography_target(
                        current_file=tex_file,
                        raw_target=raw_target,
                        bounded_root=bounded_root,
                    )
                    if candidate is None or candidate in seen:
                        continue
                    seen.add(candidate)
                    referenced.append(candidate)
    return referenced


def _collect_bibliography_files(*, root: Path, tex_files: list[Path]) -> list[Path]:
    bounded_root = _bounded_tex_source_root(root)
    if bounded_root is None:
        return []
    referenced = _collect_referenced_bibliography_files(tex_files=tex_files, bounded_root=bounded_root)
    if referenced:
        return referenced
    active_tex_dirs = {tex_file.resolve().parent for tex_file in tex_files}
    candidate_bib_files = sorted(
        path.resolve()
        for path in bounded_root.rglob("*.bib")
        if path.resolve().parent in active_tex_dirs
    )
    if not candidate_bib_files:
        return []
    cited_keys: set[str] = set()
    for tex_file in tex_files:
        cited_keys.update(parse_citations_from_tex(tex_file).keys())
    if cited_keys:
        matching = [
            bib_file
            for bib_file in candidate_bib_files
            if cited_keys.intersection(parse_bibliography_keys(bib_file).keys())
        ]
        if matching:
            return matching
    if root.is_file():
        return []
    return candidate_bib_files


def ordered_tex_files(root: Path) -> list[Path]:
    root = root.expanduser()
    bounded_root = _bounded_tex_source_root(root)
    if root.is_file():
        if root.suffix.lower() != ".tex":
            raise ValueError(f"unsupported TeX entrypoint: {root}")
        tex_files = [root.resolve()]
    else:
        tex_files = sorted(path.resolve() for path in root.rglob("*.tex"))
    if not tex_files:
        return []

    def choose_entrypoint() -> Path | None:
        if root.is_file():
            return root.resolve()
        main_tex = (root / "main.tex").resolve()
        if main_tex in tex_files:
            return main_tex
        documentclass_entrypoints: list[Path] = []
        for path in tex_files:
            text = strip_tex_comments(path.read_text(encoding="utf-8", errors="ignore"))
            if "\\documentclass" in text:
                documentclass_entrypoints.append(path)
        if len(documentclass_entrypoints) > 1:
            raise ValueError(
                "ambiguous TeX directory root: multiple standalone TeX entrypoints without main.tex"
            )
        if documentclass_entrypoints:
            return documentclass_entrypoints[0]
        return None

    def resolve_include(current_file: Path, raw_target: str) -> Path | None:
        target = normalize_ws(raw_target)
        if not target:
            return None
        candidate = (current_file.parent / target).expanduser()
        if candidate.suffix.lower() != ".tex":
            candidate = candidate.with_suffix(".tex")
        candidate = candidate.resolve()
        if not candidate.exists():
            return None
        if bounded_root is not None:
            try:
                candidate.relative_to(bounded_root)
            except ValueError:
                return None
        return candidate

    ordered: list[Path] = []
    seen: set[Path] = set()

    def visit(path: Path) -> None:
        if path in seen:
            return
        seen.add(path)
        ordered.append(path)
        text = strip_tex_comments(path.read_text(encoding="utf-8", errors="ignore"))
        for match in INCLUDE_RE.finditer(text):
            include_path = resolve_include(path, str(match.group(1)))
            if include_path is not None:
                visit(include_path)

    entrypoint = choose_entrypoint()
    if entrypoint is not None:
        visit(entrypoint)
        return ordered
    for path in tex_files:
        visit(path)
    return ordered


def iter_tex_chunks(root: Path) -> list[dict[str, Any]]:
    root = root.expanduser()
    if root.is_file() and root.suffix.lower() != ".tex":
        return []
    bounded_root = _bounded_tex_source_root(root)
    ordered_files = ordered_tex_files(root)
    if not ordered_files:
        return []

    def resolve_include(current_file: Path, raw_target: str) -> Path | None:
        target = normalize_ws(raw_target)
        if not target:
            return None
        candidate = (current_file.parent / target).expanduser()
        if candidate.suffix.lower() != ".tex":
            candidate = candidate.with_suffix(".tex")
        candidate = candidate.resolve()
        if bounded_root is not None:
            try:
                candidate.relative_to(bounded_root)
            except ValueError:
                return None
        return candidate if candidate.exists() else None

    chunks: list[dict[str, Any]] = []
    expanded_roots: set[Path] = set()
    covered_files: set[Path] = set()

    def visit(path: Path, *, stack: tuple[Path, ...]) -> None:
        resolved = path.expanduser().resolve()
        if resolved in stack:
            return
        covered_files.add(resolved)
        text = strip_tex_comments(resolved.read_text(encoding="utf-8", errors="ignore"))
        cursor = 0
        current_line = 1
        for match in INCLUDE_RE.finditer(text):
            chunk_text = text[cursor : match.start()]
            if chunk_text:
                chunks.append(
                    {
                        "source_file": _display_source_path(source_root=root, path=resolved),
                        "text": chunk_text,
                        "line_start": current_line,
                    }
                )
                current_line += chunk_text.count("\n")
            include_text = text[match.start() : match.end()]
            current_line += include_text.count("\n")
            include_path = resolve_include(resolved, str(match.group(1)))
            if include_path is not None:
                visit(include_path, stack=(*stack, resolved))
            cursor = match.end()
        tail = text[cursor:]
        if tail:
            chunks.append(
                {
                    "source_file": _display_source_path(source_root=root, path=resolved),
                    "text": tail,
                    "line_start": current_line,
                }
            )

    for path in ordered_files:
        resolved = path.resolve()
        if resolved in expanded_roots or resolved in covered_files:
            continue
        expanded_roots.add(resolved)
        visit(resolved, stack=())
    return chunks


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


def parse_equations_from_text(
    text: str,
    *,
    source_file: Path | str,
    line_start: int = 1,
    auto_number_start: int = 1,
) -> tuple[list[dict[str, Any]], int]:
    equations: list[dict[str, Any]] = []
    auto_number = max(1, int(auto_number_start))
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
        else:
            auto_number = max(auto_number, equation_number + 1)
        start_line = line_start + text[: match.start()].count("\n")
        end_line = start_line + match.group(0).count("\n")
        equations.append(
            {
                "source_file": str(source_file),
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
    return equations, auto_number


def parse_equations(tex_file: Path, *, auto_number_start: int = 1) -> tuple[list[dict[str, Any]], int]:
    text = strip_tex_comments(tex_file.read_text(encoding="utf-8", errors="ignore"))
    return parse_equations_from_text(
        text,
        source_file=tex_file,
        line_start=1,
        auto_number_start=auto_number_start,
    )


def parse_citations_from_text(text: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for match in CITE_RE.finditer(text):
        for key in match.group(1).split(","):
            norm = normalize_ws(key)
            if norm:
                counter[norm] += 1
    return counter


def parse_citations_from_tex(tex_file: Path) -> Counter[str]:
    text = strip_tex_comments(tex_file.read_text(encoding="utf-8", errors="ignore"))
    return parse_citations_from_text(text)


def parse_bibliography_keys(bib_file: Path) -> Counter[str]:
    text = bib_file.read_text(encoding="utf-8", errors="ignore")
    counter: Counter[str] = Counter()
    for match in BIB_ENTRY_RE.finditer(text):
        key = normalize_ws(match.group(1))
        if key:
            counter[key] += 1
    return counter


def extract_bibtex_field(body: str, field_name: str) -> str:
    match = re.search(rf"\b{re.escape(field_name)}\s*=\s*", body, re.IGNORECASE)
    if not match:
        return ""
    idx = match.end()
    while idx < len(body) and body[idx].isspace():
        idx += 1
    if idx >= len(body):
        return ""
    opener = body[idx]
    if opener == "{":
        depth = 0
        chars: list[str] = []
        for ch in body[idx + 1 :]:
            if ch == "{":
                depth += 1
                chars.append(ch)
                continue
            if ch == "}":
                if depth == 0:
                    return normalize_ws("".join(chars).replace("{", "").replace("}", ""))
                depth -= 1
                chars.append(ch)
                continue
            chars.append(ch)
        return ""
    if opener == '"':
        chars: list[str] = []
        escaped = False
        for ch in body[idx + 1 :]:
            if ch == '"' and not escaped:
                return normalize_ws("".join(chars).replace("{", "").replace("}", ""))
            if ch == "\\" and not escaped:
                escaped = True
                chars.append(ch)
                continue
            escaped = False
            chars.append(ch)
    return ""


def parse_bibliography_titles(bib_file: Path) -> dict[str, str]:
    text = bib_file.read_text(encoding="utf-8", errors="ignore")
    matches = list(BIB_ENTRY_RE.finditer(text))
    titles: dict[str, str] = {}
    for index, match in enumerate(matches):
        key = normalize_ws(match.group(1))
        if not key:
            continue
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : body_end]
        title = extract_bibtex_field(body, "title")
        if title:
            titles[key] = title
    return titles


def ext_author_tokens(external: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for author in external.get("citation_authors", []):
        last = re.sub(r"[^a-z]", "", normalize_ws(author).lower().split()[-1] if normalize_ws(author) else "")
        if last:
            tokens.append(last)
    return dedupe_preserve(tokens)


def key_score(
    key: str,
    text: str,
    surnames: list[str],
    year: str,
    *,
    bibliography_title: str = "",
) -> tuple[int, int, int]:
    haystack = re.sub(r"[^a-z0-9]", "", key.lower())
    bibliography_haystack = re.sub(r"[^a-z0-9]", "", bibliography_title.lower())
    key_has_author_or_year_signal = bool(year and year in haystack) or any(
        surname and surname in haystack for surname in surnames
    )
    score = 0
    if year and year in haystack:
        score += 2
    author_matches = 0
    for surname in surnames:
        if surname and surname in haystack:
            score += 2
            author_matches += 1
    text_matches = 0
    for token in signature_tokens(text):
        if token == year or token in surnames:
            continue
        if token and token in haystack:
            text_matches += 1
            continue
        if token and key_has_author_or_year_signal and token in bibliography_haystack:
            text_matches += 1
    score += min(3, text_matches)
    return score, text_matches, author_matches


def generic_author_year_key(key: str, surnames: list[str], year: str) -> bool:
    if not year or not surnames:
        return False
    reduced = re.sub(r"[^a-z0-9]", "", key.lower())
    reduced = reduced.replace(year.lower(), "")
    for surname in sorted({token for token in surnames if token}, key=len, reverse=True):
        reduced = reduced.replace(surname, "")
    return bool(GENERIC_AUTHOR_YEAR_SUFFIX_RE.fullmatch(reduced))


def score_external_key_matches(
    external: dict[str, Any],
    *,
    key_counter: Counter[str],
    bibliography_titles_by_key: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    year = normalize_ws(external.get("citation_year", ""))
    surnames = ext_author_tokens(external)
    label = normalize_ws(external.get("citation_label", ""))
    name = normalize_ws(external.get("name", ""))
    text = f"{label} {name}"
    text_tokens = signature_tokens(text)
    scored: list[dict[str, Any]] = []
    for key in key_counter:
        bibliography_title = str((bibliography_titles_by_key or {}).get(key, ""))
        score, text_matches, author_matches = key_score(
            key,
            text,
            surnames,
            year,
            bibliography_title=bibliography_title,
        )
        if score <= 0:
            continue
        scored.append(
            {
                "key": key,
                "score": score,
                "text_matches": text_matches,
                "author_matches": author_matches,
                "has_bibliography_title": bool(normalize_ws(bibliography_title)),
                "generic_author_year": generic_author_year_key(key, surnames, year),
            }
        )
    scored.sort(key=lambda item: (-int(item["score"]), -int(item["text_matches"]), str(item["key"])))
    return scored, text_tokens


def select_external_keys(
    scored: list[dict[str, Any]],
    *,
    text_tokens: list[str],
    max_keys: int,
    require_text_match_if_text_available: bool = False,
) -> list[str]:
    if not scored:
        return []
    selected = list(scored)
    if any(int(item["text_matches"]) > 0 for item in selected):
        best_score = int(selected[0]["score"])
        best_matches = int(selected[0]["text_matches"])
        selected = [
            item
            for item in selected
            if int(item["score"]) == best_score and int(item["text_matches"]) == best_matches
        ]
    elif require_text_match_if_text_available and text_tokens:
        if len(selected) != 1:
            generic_scored = [item for item in selected if bool(item["generic_author_year"])]
            if len(generic_scored) != 1:
                return []
            selected = generic_scored
        if int(selected[0].get("author_matches", 0)) <= 0:
            return []
        if bool(selected[0]["generic_author_year"]):
            return []
    return dedupe_preserve([str(item["key"]) for item in selected])[: max(1, max_keys)]


def match_external_keys(
    external: dict[str, Any],
    *,
    key_counter: Counter[str],
    bibliography_titles_by_key: dict[str, str] | None = None,
    max_keys: int,
    require_text_match_if_text_available: bool = False,
) -> list[str]:
    scored, text_tokens = score_external_key_matches(
        external,
        key_counter=key_counter,
        bibliography_titles_by_key=bibliography_titles_by_key,
    )
    return select_external_keys(
        scored,
        text_tokens=text_tokens,
        max_keys=max_keys,
        require_text_match_if_text_available=require_text_match_if_text_available,
    )


def citation_dependency_signature(external: dict[str, Any]) -> tuple[str, tuple[str, ...], str, str]:
    title_tokens = signature_tokens(external.get("name", ""))
    if not title_tokens:
        title_tokens = signature_tokens(external.get("citation_label", ""))
    return (
        normalize_ws(external.get("source_kind", "")),
        tuple(ext_author_tokens(external)),
        normalize_ws(external.get("citation_year", "")),
        " ".join(title_tokens),
    )


def _dependency_title_tokens(external: dict[str, Any]) -> set[str]:
    title_tokens = signature_tokens(external.get("name", ""))
    if not title_tokens:
        title_tokens = signature_tokens(external.get("citation_label", ""))
    return set(title_tokens)


def _canonical_dependency_title_tokens(external: dict[str, Any]) -> set[str]:
    tokens = _dependency_title_tokens(external)
    return {
        token
        for token in tokens
        if not (token.endswith("s") and len(token) > 1 and token[:-1] in tokens)
    }


def _same_dependency_family(lhs: dict[str, Any], rhs: dict[str, Any]) -> bool:
    if tuple(ext_author_tokens(lhs)) != tuple(ext_author_tokens(rhs)):
        return False
    if normalize_ws(lhs.get("citation_year", "")) != normalize_ws(rhs.get("citation_year", "")):
        return False
    lhs_tokens = _canonical_dependency_title_tokens(lhs)
    rhs_tokens = _canonical_dependency_title_tokens(rhs)
    if not lhs_tokens or not rhs_tokens:
        return False
    if len(lhs_tokens) < 2 or len(rhs_tokens) < 2:
        return False
    return lhs_tokens == rhs_tokens


def assign_citation_keys(
    externals: list[dict[str, Any]],
    *,
    cite_counter: Counter[str],
    bibliography_titles_by_key: dict[str, str] | None = None,
    max_keys: int,
) -> list[list[str]]:
    scored_by_external: list[list[dict[str, Any]]] = []
    selected_by_external: list[list[str]] = []
    for external in externals:
        scored, text_tokens = score_external_key_matches(
            external,
            key_counter=cite_counter,
            bibliography_titles_by_key=bibliography_titles_by_key,
        )
        scored_by_external.append(scored)
        selected_by_external.append(
            select_external_keys(
                scored,
                text_tokens=text_tokens,
                max_keys=max_keys,
                require_text_match_if_text_available=True,
            )
        )

    key_to_external_indices: dict[str, list[int]] = defaultdict(list)
    for index, keys in enumerate(selected_by_external):
        for key in keys:
            key_to_external_indices[key].append(index)

    for key, indices in key_to_external_indices.items():
        if len(indices) <= 1:
            continue
        contenders: list[tuple[tuple[int, int, int], int]] = []
        for index in indices:
            candidate = next(
                (
                    item
                    for item in scored_by_external[index]
                    if str(item.get("key")) == key
                ),
                None,
            )
            if candidate is None:
                continue
            contenders.append(
                (
                    (
                        int(candidate.get("score", 0)),
                        int(candidate.get("text_matches", 0)),
                        int(bool(candidate.get("has_bibliography_title"))),
                    ),
                    index,
                )
            )
        if not contenders:
            continue
        contenders.sort(key=lambda item: item[0], reverse=True)
        best_tuple = contenders[0][0]
        winners = [index for score_tuple, index in contenders if score_tuple == best_tuple]
        if len(winners) != 1:
            winner_signatures = {
                citation_dependency_signature(externals[index])
                for index in winners
            }
            retained_indices = (
                {
                    index
                    for index in indices
                    if any(_same_dependency_family(externals[winner], externals[index]) for winner in winners)
                }
                if len(winner_signatures) == 1
                or all(
                    _same_dependency_family(externals[left], externals[right])
                    for left in winners
                    for right in winners
                )
                else set()
            )
            for index in indices:
                if index in retained_indices:
                    continue
                selected_by_external[index] = [
                    assigned_key
                    for assigned_key in selected_by_external[index]
                    if assigned_key != key
                ]
            continue
        winner = winners[0]
        retained_indices = {
            index
            for index in indices
            if index == winner or _same_dependency_family(externals[winner], externals[index])
        }
        for index in indices:
            if index in retained_indices:
                continue
            selected_by_external[index] = [
                assigned_key
                for assigned_key in selected_by_external[index]
                if assigned_key != key
            ]
    return selected_by_external


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
    bib_titles_by_key: dict[str, str] = {}
    next_auto_number = 1
    for chunk in iter_tex_chunks(source_root):
        parsed_equations, next_auto_number = parse_equations_from_text(
            str(chunk.get("text", "")),
            source_file=Path(str(chunk.get("source_file"))),
            line_start=int(chunk.get("line_start", 1)),
            auto_number_start=next_auto_number,
        )
        equations.extend(parsed_equations)
        cite_counter.update(parse_citations_from_text(str(chunk.get("text", ""))))
    for bib_file in bib_files:
        bib_key_counter.update(parse_bibliography_keys(bib_file))
        bib_titles_by_key.update(parse_bibliography_titles(bib_file))

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

    external_rows = [
        external
        for external in enriched.get("external_results", [])
        if isinstance(external, dict)
    ]
    matched_keys_by_external = assign_citation_keys(
        external_rows,
        cite_counter=cite_counter,
        bibliography_titles_by_key=bib_titles_by_key,
        max_keys=max_citation_keys,
    )
    external_hits = 0
    matched_index = 0
    for external in enriched.get("external_results", []):
        if not isinstance(external, dict):
            continue
        matched = matched_keys_by_external[matched_index]
        matched_index += 1
        prior_matched = [
            normalize_ws(key)
            for key in external.get("citation_keys_detected", [])
            if normalize_ws(key)
        ]
        citation_label = normalize_ws(external.get("citation_label", ""))
        bibliography_candidates = match_external_keys(
            external,
            key_counter=bib_key_counter,
            bibliography_titles_by_key=bib_titles_by_key,
            max_keys=max_citation_keys,
        )
        if matched:
            external_hits += 1
        external["citation_keys_detected"] = matched
        external["citation_key_usage_counts"] = [
            {"key": key, "count": int(cite_counter[key])}
            for key in matched
            if int(cite_counter.get(key, 0)) > 0
        ]
        external["bibliography_entry_candidates"] = bibliography_candidates
        external["bib_source_files"] = (
            [_display_source_path(source_root=source_root, path=path) for path in bib_files]
            if bibliography_candidates
            else []
        )
        prior_queries = [normalize_ws(query) for query in external.get("retrieval_queries", []) if normalize_ws(query)]
        stale_query_prefixes = tuple(
            f"{key} " for key in dedupe_preserve([*prior_matched, *matched]) if key
        )
        retrieval_queries = [
            query
            for query in prior_queries
            if query not in set(dedupe_preserve([*prior_matched, *matched]))
            and not any(query.startswith(prefix) for prefix in stale_query_prefixes)
        ]
        retrieval_queries.extend(f"{key} {citation_label}".strip() for key in matched if key)
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
