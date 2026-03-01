#!/usr/bin/env python3
"""Deterministically ingest MSC2020 CSV into a LeanAtlas domain-ontology bundle.

Design goals:
- stdlib-only (no new Python deps)
- deterministic output ordering
- explicit schema_version + data_version

See:
- docs/contracts/MCP_MSC2020_CONTRACT.md
- docs/setup/external/msc2020.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = "leanatlas.domain_ontology.bundle.v1"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


_CODE_2 = re.compile(r"^\d{2}$")
_CODE_3 = re.compile(r"^\d{2}[A-Z]$")
_CODE_5 = re.compile(r"^\d{2}[A-Z](?:\d{2}|xx)$")
_CODE_HYPHEN = re.compile(r"^\d{2}-[0-9A-Z]{2}$")


def normalize_code(code: str) -> str:
    code = code.strip()
    # Normalize xx to lowercase for canonical form (MSC commonly uses 'xx').
    if len(code) == 5 and code.endswith("XX"):
        code = code[:-2] + "xx"
    return code


def infer_level(code: str) -> Optional[int]:
    if _CODE_2.fullmatch(code):
        return 2
    if _CODE_3.fullmatch(code):
        return 3
    if _CODE_HYPHEN.fullmatch(code):
        return 5
    if _CODE_5.fullmatch(code):
        return 5
    return None


def infer_parent_code(code: str) -> Optional[str]:
    # 2-digit classes have no parent.
    if _CODE_2.fullmatch(code):
        return None
    # 3-digit: parent is 2-digit.
    if _CODE_3.fullmatch(code):
        return code[:2]
    # Hyphen: parent is 2-digit.
    if _CODE_HYPHEN.fullmatch(code):
        return code[:2]
    # 5-char normal: parent is 3-char.
    if _CODE_5.fullmatch(code):
        return code[:3]
    return None


def canonical_dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def read_rows(csv_path: Path) -> List[Dict[str, str]]:
    # MSC official CSV uses headers: code,text,description.
    # We also accept minor variants.
    raw = csv_path.read_text(encoding="utf-8", errors="replace")
    # csv module expects newline normalization.
    lines = raw.splitlines()
    if not lines:
        raise ValueError("empty CSV")

    reader = csv.DictReader(lines)
    if reader.fieldnames is None:
        raise ValueError("CSV missing header row")

    # Normalize header names.
    header_map = {}
    for h in reader.fieldnames:
        if h is None:
            continue
        k = h.strip().lower()
        header_map[k] = h

    def get(row: Dict[str, str], key: str) -> str:
        # key is normalized lowercase
        if key in header_map:
            v = row.get(header_map[key], "")
            return "" if v is None else str(v)
        return ""

    rows: List[Dict[str, str]] = []
    for row in reader:
        code = get(row, "code").strip()
        if not code:
            continue
        rows.append(
            {
                "code": code,
                "text": get(row, "text").strip(),
                "description": get(row, "description").strip(),
            }
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to MSC2020 CSV (official)")
    ap.add_argument("--output", required=True, help="Output bundle JSON path")
    ap.add_argument("--source-id", default="msc2020", help="Provider source_id")
    ap.add_argument(
        "--data-version",
        required=True,
        help="Human-readable version string, e.g. msc2020@2020",
    )
    ap.add_argument(
        "--license",
        default="CC BY-NC-SA",
        help="License string to embed in bundle metadata",
    )

    args = ap.parse_args()
    inp = Path(args.input)
    outp = Path(args.output)

    rows = read_rows(inp)
    if not rows:
        raise SystemExit("No rows found in CSV")

    input_sha256 = sha256_file(inp)
    source_id = str(args.source_id).strip()

    # First pass: normalize codes and collect.
    tmp: List[Tuple[str, str, str]] = []
    for r in rows:
        code = normalize_code(r["code"])
        text = r.get("text", "").strip()
        desc = r.get("description", "").strip()
        tmp.append((code, text, desc))

    # De-duplicate by code (keep first occurrence, deterministic by input order).
    seen = set()
    uniq: List[Tuple[str, str, str]] = []
    for code, text, desc in tmp:
        if code in seen:
            continue
        seen.add(code)
        uniq.append((code, text, desc))

    codes = {c for c, _, _ in uniq}

    nodes: List[Dict[str, Any]] = []
    for code, text, desc in uniq:
        level = infer_level(code)
        parent_code = infer_parent_code(code)
        parent_id = None
        if parent_code and parent_code in codes:
            parent_id = f"{source_id}:{parent_code}"

        nodes.append(
            {
                "id": f"{source_id}:{code}",
                "code": code,
                "source_id": source_id,
                "level": level,
                "text": text,
                "description": desc,
                "parent_id": parent_id,
            }
        )

    # Deterministic ordering.
    nodes.sort(key=lambda n: (n.get("code") or "", n.get("id") or ""))

    # Counts.
    counts = {
        "nodes": len(nodes),
        "by_level": {
            "2": sum(1 for n in nodes if n.get("level") == 2),
            "3": sum(1 for n in nodes if n.get("level") == 3),
            "5": sum(1 for n in nodes if n.get("level") == 5),
            "unknown": sum(1 for n in nodes if n.get("level") not in (2, 3, 5)),
        },
    }

    bundle = {
        "schema_version": SCHEMA_VERSION,
        "data_version": str(args.data_version).strip(),
        "source": {
            "source_id": source_id,
            "license": str(args.license).strip(),
            "input_sha256": input_sha256,
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "counts": counts,
        "nodes": nodes,
    }

    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(canonical_dump(bundle), encoding="utf-8")

    print(f"[msc.ingest][OK] wrote bundle: {outp} (nodes={len(nodes)})")
    print(f"[msc.ingest] input_sha256={input_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
