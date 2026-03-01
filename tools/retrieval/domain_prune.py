#!/usr/bin/env python3
"""Suggest retrieval pruning roots from a domain set.

This is a deterministic helper used by the domain-driven retrieval ladder.
It does NOT require MCP to be running.

Policy:
- If we cannot confidently map domain->directory roots, we do NOT prune.

Contracts:
- docs/contracts/MCP_MSC2020_CONTRACT.md (domain/roots semantics)
- docs/contracts/RETRIEVAL_TRACE_CONTRACT.md (DOMAIN_ROOTS_SUGGEST logging)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

# Reuse the same store implementation as the stdio MCP server.
from tools.lean_domain_mcp.domain_mcp_server import DomainStore


def canonical_dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", help="Bundle JSON path (optional)")
    ap.add_argument("--overlay", action="append", default=[], help="Overlay JSON path (may repeat)")
    ap.add_argument("--domain", action="append", default=[], help="Domain id or code (repeatable)")
    ap.add_argument("--repo-root", default=".", help="Repo root for existence checks")
    ap.add_argument("--out", help="Write JSON output to this file (else stdout)")

    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    store = DomainStore(repo_root)

    try:
        if args.bundle:
            store.load_bundle(Path(args.bundle))
        else:
            # No bundle: pruning can still work if overlay references existing ids,
            # but most likely it will be missing; we degrade.
            pass
        for p in args.overlay or []:
            store.apply_overlay(Path(p))
    except Exception as e:
        # If data cannot load, degrade: no pruning.
        payload = {
            "missing": True,
            "include_paths": ["."],
            "exclude_globs": [],
            "notes": [f"DATA_LOAD_FAILED: {e}"]
        }
        out_txt = canonical_dump(payload)
        if args.out:
            Path(args.out).write_text(out_txt, encoding="utf-8")
        else:
            print(out_txt, end="")
        return 0

    domains: List[str] = [d for d in (args.domain or []) if isinstance(d, str) and d.strip()]

    if not domains:
        payload = {
            "missing": True,
            "include_paths": ["."],
            "exclude_globs": [],
            "notes": ["No --domain provided; refusing to prune"]
        }
    else:
        roots = store.roots(domains)
        if roots.get("missing"):
            payload = {
                "missing": True,
                "include_paths": ["."],
                "exclude_globs": [],
                "notes": ["No directory_roots mapping found in overlay; refusing to prune"],
            }
        else:
            include_paths = sorted({r["path"] for r in roots.get("roots", [])})
            payload = {
                "missing": False,
                "include_paths": include_paths,
                "exclude_globs": [],
                "notes": ["Paths are suggestions; retrieval must still validate imports locally."],
            }

    out_txt = canonical_dump(payload)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(out_txt, encoding="utf-8")
    else:
        print(out_txt, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
