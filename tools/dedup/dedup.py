#!/usr/bin/env python3
"""LeanAtlas DedupGate (phase3).

Phase-3 V0: source-backed scan for duplicate `instance` declarations.

This tool is deterministic and repo-safe (read-only). It produces a schema-valid
`DedupReport.json` and optional `DedupReport.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")
_KEYWORDS = {
    "∀",
    "fun",
    "Type",
    "Sort",
    "Prop",
    "let",
    "in",
    "if",
    "then",
    "else",
    "and",
    "or",
}
_INSTANCE_HEAD_RE = re.compile(r"\binstance\b([^:]*)\s*:", re.MULTILINE)


def _canonical_dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, obj: Any) -> None:
    _write_text(path, _canonical_dump(obj))


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_allowlist(repo_root: Path) -> List[Dict[str, Any]]:
    p = repo_root / "tools" / "dedup" / "allowlist.json"
    if not p.exists():
        return []
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [x for x in obj if isinstance(x, dict)] if isinstance(obj, list) else []


def _normalize_identifiers(signature: str) -> str:
    mapping: Dict[str, str] = {}
    counter = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal counter
        tok = m.group(0)
        if tok in _KEYWORDS or tok.isupper():
            return tok
        mapped = mapping.get(tok)
        if mapped is None:
            mapped = f"v{counter}"
            mapping[tok] = mapped
            counter += 1
        return mapped

    return _TOKEN_RE.sub(repl, signature)


def _normalize_type_signature(signature: str) -> str:
    s = signature.replace("\n", " ").replace("\t", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\bΠ\b", "∀", s)
    return _normalize_identifiers(s)


def _canonical_type_hash(signature: str) -> str:
    return _sha256(_normalize_type_signature(signature))


def _is_alias_rhs(rhs: str) -> Optional[str]:
    rhs = rhs.strip()
    if not rhs or rhs.startswith("by"):
        return None
    m = re.match(r"\(?\s*([A-Za-z_][A-Za-z0-9_'.]*)\s*\)?\s*$", rhs)
    if m is None:
        return None
    return m.group(1)


def _extract_decl_name(left: str) -> Optional[str]:
    left = re.sub(r"\[[^\]]*\]", " ", left)
    left = re.sub(r"[(){}\\[\\]]", " ", left)
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_']*", left)
    if not tokens:
        return None
    return tokens[-1]


@dataclass
class InstanceDecl:
    name: str
    module: str
    path: str
    line: int
    sig: str
    type_hash: str
    rhs_alias_of: Optional[str]

    def as_candidate(self, decision: str, evidence: Dict[str, Any], related: List[Dict[str, Any]]) -> Dict[str, Any]:
        candidate: Dict[str, Any] = {
            "candidate": {
                "name": self.name,
                "module": self.module,
                "loc": {
                    "path": self.path,
                    "range": [self.line - 1, 0, self.line - 1, 0],
                },
                "type": self.sig,
                "type_hash": self.type_hash,
                "kind": "instance",
            },
            "decision": decision,
            "evidence": evidence,
            "related": related,
        }
        if self.rhs_alias_of:
            candidate["candidate"]["alias_of"] = self.rhs_alias_of
        return candidate


def _collect_instance_blocks(lines: Sequence[str]) -> List[Tuple[int, List[str]]]:
    blocks: List[Tuple[int, List[str]]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if "instance" not in line:
            i += 1
            continue
        block: List[str] = []
        j = i
        while j < len(lines) and len(block) < 24:
            block.append(lines[j])
            if ":=" in lines[j]:
                break
            j += 1
        blocks.append((i, block))
        i = j + 1
    return blocks


def _parse_instances(repo_root: Path, scope: str = "LeanAtlas") -> List[InstanceDecl]:
    out: List[InstanceDecl] = []
    src_root = repo_root / "LeanAtlas"
    if not src_root.exists():
        return out
    wanted_scope = (scope or "LeanAtlas").strip()

    for lean_file in sorted(src_root.rglob("*.lean")):
        rel = lean_file.relative_to(repo_root)
        module = "LeanAtlas." + ".".join(rel.with_suffix("").parts[1:])
        if wanted_scope and not module.startswith(wanted_scope):
            continue
        try:
            text = lean_file.read_text(encoding="utf-8")
        except Exception:
            continue

        lines = text.splitlines()
        for start_i, block_lines in _collect_instance_blocks(lines):
            if not block_lines:
                continue
            block_text = " ".join([x.strip() for x in block_lines if x.strip()])
            if ":=" not in block_text:
                continue

            m_head = _INSTANCE_HEAD_RE.search(block_text)
            if not m_head:
                continue
            head = block_text[: m_head.end() - 1]
            rhs = block_text.split(":=", 1)[1]
            left = m_head.group(0)

            name = _extract_decl_name(left)
            if not name:
                continue

            signature = head.split(":", 1)[1].strip()
            if not signature:
                continue

            out.append(
                InstanceDecl(
                    name=name,
                    module=module,
                    path=str(rel),
                    line=start_i + 1,
                    sig=signature,
                    type_hash=_canonical_type_hash(signature),
                    rhs_alias_of=_is_alias_rhs(rhs),
                )
            )
    return out


def _allowlist_match(allowlist: Iterable[Dict[str, Any]], d: InstanceDecl) -> Optional[Dict[str, Any]]:
    for row in allowlist:
        names = row.get("names")
        th = row.get("type_hash")
        if th and th == d.type_hash:
            return row
        if isinstance(names, list):
            if d.name in names:
                return row
            if f"{d.module}.{d.name}" in names:
                return row
            if d.module in names:
                return row
            if d.type_hash in names:
                return row
    return None


def make_report(repo_root: Path, scope: str = "LeanAtlas") -> Dict[str, Any]:
    instances = _parse_instances(repo_root, scope=scope)
    allowlist = _load_allowlist(repo_root)

    by_hash: Dict[str, List[InstanceDecl]] = defaultdict(list)
    for decl in instances:
        by_hash[decl.type_hash].append(decl)

    candidates: List[Dict[str, Any]] = []
    actionable_duplicates = 0
    alias_candidates = 0
    allowlist_hits = 0

    for decl in instances:
        group = by_hash[decl.type_hash]
        allow_hit = _allowlist_match(allowlist, decl)
        related = [
            {
                "name": other.name,
                "module": other.module,
                "relation": "same_type_hash",
                "score": 1.0,
                "notes": f"same canonical type_hash as {decl.name}",
            }
            for other in group
            if other is not decl
        ]

        if len(group) <= 1:
            decision = "keep"
        elif decl.rhs_alias_of is not None:
            decision = "alias"
            alias_candidates += 1
        elif allow_hit is not None:
            decision = "allowlist"
            allowlist_hits += 1
        else:
            decision = "duplicate"
            actionable_duplicates += 1

        evidence: Dict[str, Any] = {
            "source": decl.path,
            "module": decl.module,
            "type_hash": decl.type_hash,
            "group_size": len(group),
            "decision_reason": "same_type_hash_group",
        }
        if decl.rhs_alias_of:
            evidence["alias_of"] = decl.rhs_alias_of
        if allow_hit is not None:
            evidence["allowlist"] = {"hit": allow_hit}

        candidates.append(decl.as_candidate(decision=decision, evidence=evidence, related=related))

    decision_counts = defaultdict(int)
    for c in candidates:
        decision_counts[c["decision"]] += 1

    summary: Dict[str, Any] = {
        "mode": "source_scan",
        "repo_root": str(repo_root),
        "generated_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "instances_scanned": len(instances),
        "duplicate_groups": sum(1 for g in by_hash.values() if len(g) > 1),
        "actionable_duplicates": actionable_duplicates,
        "allowlist_hits": allowlist_hits,
        "alias_candidates": alias_candidates,
        "decision_counts": dict(sorted(decision_counts.items())),
        "note": "Phase3 source-scan V0; env-scan replacement pending.",
    }

    source_roots = repo_root / "LeanAtlas"
    scanned_files = 0
    if source_roots.exists():
        scanned_files = len(list(source_roots.rglob("*.lean")))

    return {
        "version": "0.1",
        "candidates": candidates,
        "summary": summary,
        "meta": {
            "scope": "LeanAtlas/**/*.lean",
            "scanned_files": scanned_files,
        },
    }


def _render_markdown(report: Dict[str, Any]) -> str:
    s = report.get("summary", {})
    lines = [
        "# DedupReport",
        "",
        f"- instances_scanned: {s.get('instances_scanned', 0)}",
        f"- duplicate_groups: {s.get('duplicate_groups', 0)}",
        f"- actionable_duplicates: {s.get('actionable_duplicates', 0)}",
        f"- alias_candidates: {s.get('alias_candidates', 0)}",
        f"- allowlist_hits: {s.get('allowlist_hits', 0)}",
        "",
        "## decisions",
    ]
    for c in report.get("candidates", [])[:80]:
        cand = c.get("candidate", {})
        rel = c.get("related", [])
        rel_names = ", ".join([r.get("name", "") for r in rel[:3]])
        lines.append(f"- {cand.get('module', 'unknown')}::{cand.get('name')} -> {c.get('decision')} (related: {rel_names})")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".", help="Repo root to scan")
    ap.add_argument("--out-root", default=None, help="Directory for dedup report")
    ap.add_argument(
        "--out",
        dest="out",
        default=None,
        help="Backward-compatible alias: output file/directory for DedupReport (file must be .json if provided)",
    )
    ap.add_argument("--instances", action="store_true", help="Backward-compatible no-op flag")
    ap.add_argument("--scope", default="LeanAtlas", help="Backward-compatible scope filter; currently fixed to LeanAtlas")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    report = make_report(repo_root, scope=args.scope)

    if args.out:
        out_path = Path(args.out)
        if (out_path.exists() and out_path.is_dir()) or (not out_path.exists() and out_path.suffix == ""):
            out_root = out_path
            out_json = out_root / "DedupReport.json"
            out_md = out_root / "DedupReport.md"
        elif out_path.suffix.lower() == ".json":
            out_root = out_path.parent
            out_json = out_path
            out_md = out_path.with_suffix(".md")
        else:
            out_root = out_path.parent
            out_json = out_path
            out_md = out_path.with_name(out_path.name + ".md")
        out_root.mkdir(parents=True, exist_ok=True)
        _write_json(out_json, report)
        _write_text(out_md, _render_markdown(report))
        print(f"[dedup] wrote {out_json}")
    elif args.out_root:
        out_root = Path(args.out_root)
        out_root.mkdir(parents=True, exist_ok=True)
        _write_json(out_root / "DedupReport.json", report)
        _write_text(out_root / "DedupReport.md", _render_markdown(report))
        print(f"[dedup] wrote {out_root / 'DedupReport.json'}")
    else:
        print(_canonical_dump(report), end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
