#!/usr/bin/env python3
"""Convert LeanAtlas source-import edges JSON to Graphviz DOT.

This is a tiny deterministic adapter so humans (and Codex) can visualize import
structure without hand-editing.

Input format: JSON produced by `scripts/import_edges_from_source.lean`.

Output format: Graphviz DOT (directed graph).

Conventions:
- Edges are from importer -> imported.
- Output is stable (sorted).
- This tool does NOT invoke graphviz; it only writes DOT.

Example:
  python tools/module_graph/edges_to_dot.py \
    --in artifacts/module_graph/import_edges.json \
    --out artifacts/module_graph/import_edges.dot
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def _load_json(p: Path) -> Dict[str, Any]:
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Input JSON must be an object")
    return obj


def _as_edges(obj: Dict[str, Any]) -> List[Tuple[str, str]]:
    edges_obj = obj.get("edges")
    if not isinstance(edges_obj, list):
        raise ValueError("Input JSON must contain an 'edges' list")

    edges: List[Tuple[str, str]] = []
    for item in edges_obj:
        if not isinstance(item, dict):
            continue
        mod = item.get("module")
        imps = item.get("imports")
        if not isinstance(mod, str) or not isinstance(imps, list):
            continue
        for imp in imps:
            if isinstance(imp, str):
                edges.append((mod, imp))
    return edges


def _filter_edges(
    edges: List[Tuple[str, str]],
    *,
    include_prefixes: List[str],
    exclude_prefixes: List[str],
) -> List[Tuple[str, str]]:
    def keep_node(n: str) -> bool:
        if include_prefixes:
            if not any(n.startswith(p) for p in include_prefixes):
                return False
        if exclude_prefixes:
            if any(n.startswith(p) for p in exclude_prefixes):
                return False
        return True

    out: List[Tuple[str, str]] = []
    for a, b in edges:
        if keep_node(a) and keep_node(b):
            out.append((a, b))
    return out


def _dot_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _write_dot(
    out_path: Path,
    *,
    edges: List[Tuple[str, str]],
    label: str,
) -> None:
    nodes: Set[str] = set()
    for a, b in edges:
        nodes.add(a)
        nodes.add(b)

    # Stable ordering.
    nodes_sorted = sorted(nodes)
    edges_sorted = sorted(set(edges))

    lines: List[str] = []
    lines.append('digraph "LeanImports" {')
    lines.append('  rankdir=LR;')
    lines.append(f'  label="{_dot_escape(label)}";')
    lines.append('  labelloc="t";')

    # Declare nodes explicitly for stable output (even if isolated).
    for n in nodes_sorted:
        lines.append(f'  "{_dot_escape(n)}";')

    for a, b in edges_sorted:
        lines.append(f'  "{_dot_escape(a)}" -> "{_dot_escape(b)}";')

    lines.append('}')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Input JSON file")
    ap.add_argument("--out", dest="out_path", required=True, help="Output DOT file")
    ap.add_argument(
        "--include-prefix",
        action="append",
        default=[],
        help="Keep only nodes starting with this prefix (repeatable).",
    )
    ap.add_argument(
        "--exclude-prefix",
        action="append",
        default=[],
        help="Drop nodes starting with this prefix (repeatable).",
    )
    ap.add_argument(
        "--label",
        default="Lean module import graph (source-only)",
        help="Graph label (DOT top label).",
    )

    args = ap.parse_args()
    in_path = Path(args.in_path)
    out_path = Path(args.out_path)

    obj = _load_json(in_path)
    edges = _as_edges(obj)
    edges = _filter_edges(
        edges,
        include_prefixes=list(args.include_prefix),
        exclude_prefixes=list(args.exclude_prefix),
    )

    _write_dot(out_path, edges=edges, label=str(args.label))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
