#!/usr/bin/env python3
"""Compare two bench JSON reports deterministically.

Why:
- Nightly runs generate bench summaries.
- Humans (and automations) need a stable "what changed" view.

This tool is intentionally *generic*:
- It does not assume business semantics.
- It only compares numeric summary fields and "*_counts" dictionaries.

If --old does not exist, the tool still emits a valid delta report
(baseline_missing=true) and exits 0.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_number(x: Any) -> bool:
    # bool is subclass of int; exclude it.
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def collect_summary_numbers(obj: Any) -> Dict[str, float]:
    """Collect numeric fields under top-level `summary` (flat only)."""
    if not isinstance(obj, dict):
        return {}
    s = obj.get("summary")
    if not isinstance(s, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in s.items():
        if isinstance(k, str) and is_number(v):
            out[k] = float(v)
    return out


def _is_counts_dict(d: Any) -> bool:
    if not isinstance(d, dict) or not d:
        return False
    for k, v in d.items():
        if not isinstance(k, str):
            return False
        if not isinstance(v, int) or isinstance(v, bool):
            return False
    return True


def collect_counts_dicts(obj: Any, prefix: str = "") -> Dict[str, Dict[str, int]]:
    """Recursively collect dicts whose name ends with `_counts` and values are ints."""
    out: Dict[str, Dict[str, int]] = {}
    if not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        if not isinstance(k, str):
            continue
        path = f"{prefix}.{k}" if prefix else k
        if k.endswith("_counts") and _is_counts_dict(v):
            out[path] = {str(kk): int(vv) for kk, vv in v.items()}
        # recurse
        if isinstance(v, dict):
            out.update(collect_counts_dicts(v, path))
    return out


@dataclass
class CountDelta:
    added: Dict[str, int]
    removed: Dict[str, int]
    changed: Dict[str, Dict[str, int]]  # key -> {old,new,delta}


def diff_counts(old: Dict[str, int], new: Dict[str, int]) -> CountDelta:
    keys = sorted(set(old.keys()) | set(new.keys()))
    added: Dict[str, int] = {}
    removed: Dict[str, int] = {}
    changed: Dict[str, Dict[str, int]] = {}

    for k in keys:
        o = old.get(k)
        n = new.get(k)
        if o is None and n is not None:
            added[k] = int(n)
            continue
        if n is None and o is not None:
            removed[k] = int(o)
            continue
        if o is None or n is None:
            continue
        if int(o) != int(n):
            changed[k] = {"old": int(o), "new": int(n), "delta": int(n) - int(o)}

    return CountDelta(added=added, removed=removed, changed=changed)


def top_k_changes(count_deltas: Dict[str, CountDelta], k: int = 20) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for path, d in count_deltas.items():
        for key, ch in d.changed.items():
            items.append({"path": path, "key": key, **ch})
        for key, val in d.added.items():
            items.append({"path": path, "key": key, "old": 0, "new": int(val), "delta": int(val)})
        for key, val in d.removed.items():
            items.append({"path": path, "key": key, "old": int(val), "new": 0, "delta": -int(val)})

    items.sort(key=lambda x: (-abs(int(x.get("delta", 0))), str(x.get("path")), str(x.get("key"))))
    return items[: max(0, int(k))]


def render_markdown(delta: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Bench delta")
    lines.append("")

    if delta.get("baseline_missing") is True:
        lines.append("Baseline missing: no --old report found. Showing new summary only.")
        lines.append("")

    sd = delta.get("summary_deltas") or {}
    if isinstance(sd, dict) and sd:
        lines.append("## Summary changes")
        for k in sorted(sd.keys()):
            v = sd[k]
            if not isinstance(v, dict):
                continue
            old = v.get("old")
            new = v.get("new")
            dlt = v.get("delta")
            lines.append(f"- {k}: {old} -> {new} (Δ {dlt})")
        lines.append("")

    top = delta.get("top_changes") or []
    if isinstance(top, list) and top:
        lines.append("## Top count deltas")
        for it in top[:10]:
            if not isinstance(it, dict):
                continue
            lines.append(
                f"- {it.get('path')}.{it.get('key')}: {it.get('old')} -> {it.get('new')} (Δ {it.get('delta')})"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=False, default=None, help="Old report path (baseline)")
    ap.add_argument("--new", required=True, help="New report path")
    ap.add_argument("--out", required=True, help="Delta JSON output path")
    ap.add_argument("--summary-md", default=None, help="Optional markdown summary output path")
    ap.add_argument("--top", type=int, default=20, help="How many top count deltas to include")
    args = ap.parse_args()

    new_path = Path(args.new)
    out_path = Path(args.out)
    if not new_path.exists():
        print(f"[bench.compare] ERROR: --new not found: {new_path}", file=sys.stderr)
        return 2

    old_path = Path(args.old) if args.old else None
    baseline_missing = False

    new_obj = load_json(new_path)
    old_obj = None
    if old_path is not None:
        if old_path.exists():
            try:
                old_obj = load_json(old_path)
            except Exception as e:
                print(f"[bench.compare] WARN: failed to parse --old {old_path}: {e}", file=sys.stderr)
                old_obj = None
                baseline_missing = True
        else:
            baseline_missing = True

    # Compare summary numbers
    new_sum = collect_summary_numbers(new_obj)
    old_sum = collect_summary_numbers(old_obj) if old_obj is not None else {}

    summary_deltas: Dict[str, Dict[str, float]] = {}
    for k in sorted(set(old_sum.keys()) | set(new_sum.keys())):
        o = old_sum.get(k)
        n = new_sum.get(k)
        if o is None:
            summary_deltas[k] = {"old": 0.0, "new": float(n), "delta": float(n)}
            continue
        if n is None:
            summary_deltas[k] = {"old": float(o), "new": 0.0, "delta": -float(o)}
            continue
        if float(o) != float(n):
            summary_deltas[k] = {"old": float(o), "new": float(n), "delta": float(n) - float(o)}

    # Compare *_counts dicts
    new_counts = collect_counts_dicts(new_obj)
    old_counts = collect_counts_dicts(old_obj) if old_obj is not None else {}

    count_deltas: Dict[str, CountDelta] = {}
    for path in sorted(set(old_counts.keys()) | set(new_counts.keys())):
        o = old_counts.get(path, {})
        n = new_counts.get(path, {})
        d = diff_counts(o, n)
        if d.added or d.removed or d.changed:
            count_deltas[path] = d

    top = top_k_changes(count_deltas, k=int(args.top))

    delta: Dict[str, Any] = {
        "schema": "leanatlas.bench.compare_reports",
        "schema_version": "0.1.0",
        "old": str(old_path) if old_path is not None else None,
        "new": str(new_path),
        "baseline_missing": bool(baseline_missing),
        "summary_deltas": summary_deltas,
        "count_deltas": {
            path: {
                "added": d.added,
                "removed": d.removed,
                "changed": d.changed,
            }
            for path, d in count_deltas.items()
        },
        "top_changes": top,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(canonical_json(delta), encoding="utf-8")
    print(f"[bench.compare] wrote {out_path}")

    if args.summary_md:
        md_path = Path(args.summary_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(delta), encoding="utf-8")
        print(f"[bench.compare] wrote {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
