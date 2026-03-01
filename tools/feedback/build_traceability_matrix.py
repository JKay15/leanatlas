#!/usr/bin/env python3
"""Build feedback traceability matrix from append-only ledger."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
CLOSED_STATUSES = {"closed", "resolved", "done"}


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _list_str(v: Any) -> List[str]:
    if not isinstance(v, list):
        return []
    return [str(x) for x in v if str(x).strip()]


def _links(item: Dict[str, Any]) -> Dict[str, List[str]]:
    links = item.get("links")
    if not isinstance(links, dict):
        links = {}
    return {
        "prs": _list_str(links.get("prs")),
        "tests": _list_str(links.get("tests")),
        "docs": _list_str(links.get("docs")),
        "release_notes": _list_str(links.get("release_notes")),
    }


def _parse_utc(s: str) -> dt.datetime | None:
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None


def _count_by(lines: Iterable[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for line in lines:
        value = str(line.get(key) or "unknown")
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="artifacts/feedback/ledger/feedback_ledger.jsonl")
    ap.add_argument("--out-csv", default="artifacts/feedback/traceability/latest.csv")
    ap.add_argument("--out-json", default="artifacts/feedback/traceability/latest.json")
    ap.add_argument("--strict-closed", action="store_true", default=False)
    args = ap.parse_args()

    ledger_path = Path(args.ledger)
    if not ledger_path.is_absolute():
        ledger_path = (ROOT / ledger_path).resolve()
    out_csv = Path(args.out_csv)
    if not out_csv.is_absolute():
        out_csv = (ROOT / out_csv).resolve()
    out_json = Path(args.out_json)
    if not out_json.is_absolute():
        out_json = (ROOT / out_json).resolve()

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    lines = list(_iter_jsonl(ledger_path))
    rows: List[Dict[str, str]] = []
    closed_without_links: List[str] = []
    open_sla_breaches: List[str] = []

    now = dt.datetime.now(dt.timezone.utc)
    for item in sorted(lines, key=lambda x: str(x.get("feedback_id") or "")):
        fid = str(item.get("feedback_id") or "")
        if not fid:
            continue
        status = str(item.get("status") or "open")
        triage_class = str(item.get("triage_class") or "how_to_gap")
        severity = str(item.get("severity") or "S2")
        sla_hours = int(item.get("sla_hours") or 72)
        target_bucket = str(item.get("target_bucket") or "")
        links = _links(item)
        has_links = any(len(links[k]) > 0 for k in ("prs", "tests", "docs", "release_notes"))
        if status.lower() in CLOSED_STATUSES and not has_links:
            closed_without_links.append(fid)

        seen_at = _parse_utc(str(item.get("first_seen_at_utc") or ""))
        if status.lower() not in CLOSED_STATUSES and seen_at is not None:
            elapsed_h = (now - seen_at).total_seconds() / 3600.0
            if elapsed_h > float(sla_hours):
                open_sla_breaches.append(fid)

        rows.append(
            {
                "feedback_id": fid,
                "status": status,
                "triage_class": triage_class,
                "severity": severity,
                "sla_hours": str(sla_hours),
                "target_bucket": target_bucket,
                "pr_links": ";".join(links["prs"]),
                "test_links": ";".join(links["tests"]),
                "doc_links": ";".join(links["docs"]),
                "release_links": ";".join(links["release_notes"]),
                "has_trace_links": "true" if has_links else "false",
            }
        )

    fieldnames = [
        "feedback_id",
        "status",
        "triage_class",
        "severity",
        "sla_hours",
        "target_bucket",
        "pr_links",
        "test_links",
        "doc_links",
        "release_links",
        "has_trace_links",
    ]
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    open_items = [x for x in lines if str(x.get("status") or "open").lower() not in CLOSED_STATUSES]
    summary: Dict[str, Any] = {
        "schema": "leanatlas.feedback_traceability_summary",
        "schema_version": "0.1.0",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ledger_path": ledger_path.as_posix(),
        "matrix_csv": out_csv.as_posix(),
        "item_count": len(rows),
        "open_count": len(open_items),
        "closed_count": len(rows) - len(open_items),
        "closed_without_links": sorted(closed_without_links),
        "open_sla_breaches": sorted(open_sla_breaches),
        "by_severity": _count_by(lines, "severity"),
        "by_triage_class": _count_by(lines, "triage_class"),
    }
    out_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    rel_json = out_json.relative_to(ROOT).as_posix() if out_json.is_relative_to(ROOT) else out_json.as_posix()
    if args.strict_closed and closed_without_links:
        print(f"[feedback-traceability][FAIL] closed_without_links={len(closed_without_links)} summary={rel_json}")
        return 1
    print(f"[feedback-traceability] rows={len(rows)} summary={rel_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
