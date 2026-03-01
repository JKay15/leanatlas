#!/usr/bin/env python3
"""Append chat feedback digest items into an append-only ledger JSONL."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[2]


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


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _feedback_id(item: Dict[str, Any]) -> str:
    fid = item.get("feedback_id")
    if isinstance(fid, str) and fid.strip():
        return fid
    iid = item.get("id")
    if isinstance(iid, str) and iid.strip():
        return iid
    return ""


def _ensure_links(item: Dict[str, Any]) -> Dict[str, List[str]]:
    links = item.get("links")
    if not isinstance(links, dict):
        links = {}
    out = {
        "prs": list(links.get("prs") or []),
        "tests": list(links.get("tests") or []),
        "docs": list(links.get("docs") or []),
        "release_notes": list(links.get("release_notes") or []),
    }
    for k in list(out.keys()):
        out[k] = [str(x) for x in out[k] if str(x).strip()]
    return out


def _as_ledger_line(item: Dict[str, Any], now: str) -> Dict[str, Any]:
    fid = _feedback_id(item)
    severity = str(item.get("severity") or "S2")
    sla_hours = int(item.get("sla_hours") or 72)
    triage_class = str(item.get("triage_class") or "how_to_gap")
    text = str(item.get("text") or "").strip()
    target_bucket = str(item.get("target_bucket") or "docs/agents")
    source_file = str(item.get("source_file") or "")
    session_id = str(item.get("session_id") or "unknown_session")
    agent_build_id = str(item.get("agent_build_id") or "unknown_build")
    required_actions = [str(x) for x in list(item.get("required_actions") or []) if str(x).strip()]
    closure_criteria = [str(x) for x in list(item.get("closure_criteria") or []) if str(x).strip()]

    return {
        "schema": "leanatlas.feedback_ledger_line",
        "schema_version": "0.1.0",
        "feedback_id": fid,
        "captured_at_utc": now,
        "first_seen_at_utc": now,
        "status": str(item.get("status") or "open"),
        "session_id": session_id,
        "agent_build_id": agent_build_id,
        "triage_class": triage_class,
        "severity": severity,
        "sla_hours": sla_hours,
        "frequency_hint": str(item.get("frequency_hint") or "unknown"),
        "source_file": source_file,
        "target_bucket": target_bucket,
        "user_intent_summary": text[:120],
        "observed_behavior": text,
        "expected_behavior": str(item.get("expected_behavior") or ""),
        "evidence_excerpt": text[:200],
        "required_actions": required_actions,
        "closure_criteria": closure_criteria,
        "links": _ensure_links(item),
    }


def _count_by(lines: Iterable[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for line in lines:
        v = str(line.get(key) or "unknown")
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--digest", default="artifacts/feedback/chat_feedback/latest.json")
    ap.add_argument("--ledger", default="artifacts/feedback/ledger/feedback_ledger.jsonl")
    ap.add_argument("--summary-out", default="artifacts/feedback/ledger/latest_append_summary.json")
    args = ap.parse_args()

    digest_path = Path(args.digest)
    if not digest_path.is_absolute():
        digest_path = (ROOT / digest_path).resolve()
    ledger_path = Path(args.ledger)
    if not ledger_path.is_absolute():
        ledger_path = (ROOT / ledger_path).resolve()
    summary_path = Path(args.summary_out)
    if not summary_path.is_absolute():
        summary_path = (ROOT / summary_path).resolve()

    digest_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    digest_obj = {}
    if digest_path.exists():
        try:
            digest_obj = json.loads(digest_path.read_text(encoding="utf-8"))
        except Exception:
            digest_obj = {}

    digest_items = list(digest_obj.get("items") or []) if isinstance(digest_obj, dict) else []
    digest_items = [x for x in digest_items if isinstance(x, dict)]

    existing_lines = list(_iter_jsonl(ledger_path))
    existing_ids = {
        str(line.get("feedback_id"))
        for line in existing_lines
        if isinstance(line.get("feedback_id"), str) and str(line.get("feedback_id")).strip()
    }

    now = _utc_now()
    append_lines: List[Dict[str, Any]] = []
    append_ids: List[str] = []
    for item in digest_items:
        fid = _feedback_id(item)
        if not fid or fid in existing_ids:
            continue
        line = _as_ledger_line(item, now=now)
        append_lines.append(line)
        append_ids.append(fid)
        existing_ids.add(fid)

    if append_lines:
        with ledger_path.open("a", encoding="utf-8") as f:
            for line in append_lines:
                f.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n")

    merged_lines = existing_lines + append_lines
    open_lines = [x for x in merged_lines if str(x.get("status") or "open").lower() in {"open", "triaged"}]
    summary: Dict[str, Any] = {
        "schema": "leanatlas.feedback_append_summary",
        "schema_version": "0.1.0",
        "generated_at_utc": now,
        "digest_path": digest_path.as_posix(),
        "ledger_path": ledger_path.as_posix(),
        "total_digest_items": len(digest_items),
        "existing_ledger_items": len(existing_lines),
        "appended_items": len(append_lines),
        "new_items_count": len(append_lines),
        "new_feedback_ids": sorted(append_ids),
        "ledger_total_items": len(merged_lines),
        "open_item_count": len(open_lines),
        "open_by_severity": _count_by(open_lines, "severity"),
        "open_by_triage_class": _count_by(open_lines, "triage_class"),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rel_summary = summary_path.relative_to(ROOT).as_posix() if summary_path.is_relative_to(ROOT) else summary_path.as_posix()
    print(f"[feedback-ledger] appended={len(append_lines)} summary={rel_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
