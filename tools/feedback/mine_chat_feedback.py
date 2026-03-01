#!/usr/bin/env python3
"""Deterministically mine structured feedback items from chat feedback inbox files.

Input default:
  artifacts/feedback/inbox/**

Output default:
  artifacts/feedback/chat_feedback/latest.json

Design goals:
- Zero-LLM, reproducible transformation.
- Safe with empty/missing inbox (outputs an empty digest).
- Stable item ids via source+text hashing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


ROOT = Path(__file__).resolve().parents[2]

TEXT_EXTS = {".md", ".txt"}
STRUCTURED_EXTS = {".json"}
SUPPORTED_EXTS = TEXT_EXTS | STRUCTURED_EXTS

PREFIXES = (
    "feedback:",
    "issue:",
    "pain:",
    "request:",
    "missing:",
    "problem:",
    "should:",
)

BRACKET_PREFIXES = (
    "[feedback]",
    "[issue]",
    "[pain]",
    "[request]",
    "[missing]",
    "[problem]",
)

STRUCTURED_FIELDS = (
    "feedback",
    "issue",
    "request",
    "pain",
    "missing",
    "problem",
    "friction",
)

TRIAGE_CLASSES = {
    "contract_drift",
    "how_to_gap",
    "bug_missing_test",
    "one_off_preference",
}

SEVERITY_SLA_HOURS = {
    "S0": 4,
    "S1": 24,
    "S2": 72,
    "S3": 168,
}


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def _iter_sources(in_root: Path) -> Iterable[Path]:
    if not in_root.exists():
        return []
    files = []
    for p in sorted(in_root.rglob("*"), key=lambda x: x.as_posix()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUPPORTED_EXTS:
            continue
        files.append(p)
    return files


def _extract_lines_from_text(text: str) -> List[str]:
    def extract_tagged_payload(line: str) -> str:
        lo = line.lower()
        for p in PREFIXES:
            if lo.startswith(p):
                return _normalize_text(line[len(p):])
        for p in BRACKET_PREFIXES:
            if lo.startswith(p):
                return _normalize_text(line[len(p):])
        return ""

    out: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("- ") or line.startswith("* "):
            payload = extract_tagged_payload(line[2:].strip())
            if payload:
                out.append(payload)
            continue
        payload = extract_tagged_payload(line)
        if payload:
            out.append(payload)
    return [x for x in out if x]


def _extract_from_structured(obj: Any) -> List[str]:
    out: List[str] = []

    def consume(x: Any) -> None:
        if isinstance(x, str):
            t = _normalize_text(x)
            if t:
                out.append(t)
            return
        if isinstance(x, dict):
            # Common fields.
            for k in STRUCTURED_FIELDS:
                v = x.get(k)
                if isinstance(v, str) and _normalize_text(v):
                    out.append(_normalize_text(v))
            # Nested arrays.
            for k in ("items", "feedback_items", "requests"):
                v = x.get(k)
                if isinstance(v, list):
                    for it in v:
                        consume(it)
            return
        if isinstance(x, list):
            for it in x:
                consume(it)

    consume(obj)
    # Keep order, deduplicate.
    seen = set()
    uniq: List[str] = []
    for s in out:
        if s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    return uniq


def _classify_category(text: str) -> str:
    lo = text.lower()
    if any(k in lo for k in ("contract", "schema", "invariant", "gate")):
        return "contracts"
    if any(k in lo for k in ("test", "regression", "failing", "failure", "ci")):
        return "tests"
    if any(k in lo for k in ("automation", "schedule", "nightly", "weekly")):
        return "automations"
    if any(k in lo for k in ("skill", "knowledge base", "kb", "playbook", "routing")):
        return "skills"
    if any(k in lo for k in ("install", "setup", "bootstrap", "doctor", "dependency", "mcp")):
        return "setup"
    if any(k in lo for k in ("tool", "script", "runner", "command", "cache")):
        return "tooling"
    return "docs"


def _classify_triage_class(text: str) -> str:
    lo = text.lower()
    if any(k in lo for k in ("contract", "schema", "invariant", "drift", "policy", "spec")):
        return "contract_drift"
    if any(
        k in lo
        for k in (
            "bug",
            "broken",
            "regression",
            "error",
            "failed",
            "failing",
            "wrong result",
            "incorrect",
            "crash",
        )
    ):
        return "bug_missing_test"
    if any(k in lo for k in ("prefer", "style", "wording", "rename", "personal", "subjective")):
        return "one_off_preference"
    return "how_to_gap"


def _classify_severity(text: str) -> str:
    lo = text.lower()
    if any(k in lo for k in ("security", "privacy", "data loss", "leak", "dangerous", "unsafe")):
        return "S0"
    if any(k in lo for k in ("blocking", "blocked", "broken", "cannot", "can't", "fail", "critical", "urgent", "wrong result")):
        return "S1"
    if any(k in lo for k in ("should", "missing", "unclear", "confusing", "friction", "hard to find", "unknown how")):
        return "S2"
    return "S3"


def _required_actions(triage_class: str) -> List[str]:
    if triage_class == "contract_drift":
        return [
            "add_or_update_contract_clause",
            "add_contract_test",
            "update_docs_or_implementation",
        ]
    if triage_class == "bug_missing_test":
        return [
            "add_failing_regression_test",
            "fix_implementation",
            "verify_core_tests",
        ]
    if triage_class == "how_to_gap":
        return [
            "update_how_to_docs",
            "add_or_refresh_examples",
        ]
    return ["record_preference_decision"]


def _closure_criteria(triage_class: str) -> List[str]:
    if triage_class == "contract_drift":
        return [
            "contract_test_passes",
            "docs_or_contract_updated",
            "traceability_links_present",
        ]
    if triage_class == "bug_missing_test":
        return [
            "regression_test_added",
            "fix_merged",
            "core_tests_pass",
        ]
    if triage_class == "how_to_gap":
        return [
            "how_to_doc_merged",
            "example_or_check_added",
        ]
    return ["decision_recorded"]


def _target_bucket(category: str) -> str:
    mapping = {
        "contracts": "docs/contracts",
        "tests": "tests",
        "automations": "automations",
        "skills": ".agents/skills",
        "setup": "docs/setup",
        "tooling": "tools",
        "docs": "docs/agents",
    }
    return mapping.get(category, "docs/agents")


def _mk_item_id(source_rel: str, text: str) -> str:
    digest = hashlib.sha256(f"{source_rel}\n{text}".encode("utf-8")).hexdigest()
    return f"fb_{digest[:12]}"


def _safe_triage_class(v: Any, text: str) -> str:
    t = str(v or "").strip()
    if t in TRIAGE_CLASSES:
        return t
    return _classify_triage_class(text)


def _safe_severity(v: Any, text: str) -> str:
    s = str(v or "").strip()
    if s in SEVERITY_SLA_HOURS:
        return s
    return _classify_severity(text)


def _safe_links(v: Any) -> Dict[str, List[str]]:
    if not isinstance(v, dict):
        v = {}
    out = {
        "prs": [str(x) for x in list(v.get("prs") or []) if str(x).strip()],
        "tests": [str(x) for x in list(v.get("tests") or []) if str(x).strip()],
        "docs": [str(x) for x in list(v.get("docs") or []) if str(x).strip()],
        "release_notes": [str(x) for x in list(v.get("release_notes") or []) if str(x).strip()],
    }
    return out


def _load_forced_feedback_items(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    rows = obj.get("feedback")
    if not isinstance(rows, list):
        return []

    out: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, str):
            txt = _normalize_text(row)
            if txt:
                out.append({"text": txt, "enabled": True})
            continue
        if not isinstance(row, dict):
            continue
        if bool(row.get("enabled", True)) is False:
            continue
        txt = _normalize_text(str(row.get("text") or ""))
        if not txt:
            continue
        payload = dict(row)
        payload["text"] = txt
        out.append(payload)
    return out


def _count_by(items: Sequence[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items(), key=lambda x: x[0]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-root", default="artifacts/feedback/inbox", help="Input feedback inbox directory.")
    ap.add_argument("--out", default="artifacts/feedback/chat_feedback/latest.json", help="Output digest file.")
    ap.add_argument(
        "--force-file",
        default="tools/index/force_deposit.json",
        help="Optional force-deposit policy file. feedback[] entries are always deposited.",
    )
    args = ap.parse_args()

    in_root = Path(args.in_root)
    if not in_root.is_absolute():
        in_root = (ROOT / in_root).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (ROOT / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    force_file = Path(str(args.force_file))
    if not force_file.is_absolute():
        force_file = (ROOT / force_file).resolve()

    session_id = str(os.environ.get("LEANATLAS_SESSION_ID", "unknown_session"))
    agent_build_id = str(os.environ.get("LEANATLAS_AGENT_BUILD_ID", "unknown_build"))
    items: List[Dict[str, Any]] = []

    for src in _iter_sources(in_root):
        rel = src.relative_to(ROOT).as_posix() if src.is_relative_to(ROOT) else src.as_posix()
        lines: List[str] = []
        if src.suffix.lower() in STRUCTURED_EXTS:
            try:
                obj = json.loads(src.read_text(encoding="utf-8"))
            except Exception:
                obj = None
            if obj is not None:
                lines = _extract_from_structured(obj)
        else:
            text = src.read_text(encoding="utf-8", errors="replace")
            lines = _extract_lines_from_text(text)

        for text in lines:
            norm = _normalize_text(text)
            if not norm:
                continue
            category = _classify_category(norm)
            triage_class = _classify_triage_class(norm)
            if triage_class not in TRIAGE_CLASSES:
                triage_class = "how_to_gap"
            severity = _classify_severity(norm)
            sla_hours = int(SEVERITY_SLA_HOURS.get(severity, 72))
            feedback_id = _mk_item_id(rel, norm)
            items.append(
                {
                    "id": feedback_id,
                    "feedback_id": feedback_id,
                    "session_id": session_id,
                    "agent_build_id": agent_build_id,
                    "source_file": rel,
                    "text": norm,
                    "category": category,
                    "triage_class": triage_class,
                    "severity": severity,
                    "sla_hours": sla_hours,
                    "frequency_hint": "unknown",
                    "target_bucket": _target_bucket(category),
                    "status": "open",
                    "required_actions": _required_actions(triage_class),
                    "closure_criteria": _closure_criteria(triage_class),
                    "links": {
                        "prs": [],
                        "tests": [],
                        "docs": [],
                        "release_notes": [],
                    },
                }
            )

    forced_rows = _load_forced_feedback_items(force_file)
    for i, row in enumerate(forced_rows):
        text = _normalize_text(str(row.get("text") or ""))
        if not text:
            continue
        source_rel = str(row.get("source_file") or f"force_deposit:{force_file.as_posix()}#{i}")
        category = str(row.get("category") or _classify_category(text))
        triage_class = _safe_triage_class(row.get("triage_class"), text)
        severity = _safe_severity(row.get("severity"), text)
        sla_hours = int(row.get("sla_hours") or int(SEVERITY_SLA_HOURS.get(severity, 72)))
        target_bucket = str(row.get("target_bucket") or _target_bucket(category))
        feedback_id = str(row.get("feedback_id") or row.get("id") or _mk_item_id(source_rel, text))
        req_actions = row.get("required_actions")
        if not isinstance(req_actions, list) or not req_actions:
            req_actions = _required_actions(triage_class)
        closure = row.get("closure_criteria")
        if not isinstance(closure, list) or not closure:
            closure = _closure_criteria(triage_class)

        items.append(
            {
                "id": feedback_id,
                "feedback_id": feedback_id,
                "session_id": session_id,
                "agent_build_id": agent_build_id,
                "source_file": source_rel,
                "text": text,
                "category": category,
                "triage_class": triage_class,
                "severity": severity,
                "sla_hours": sla_hours,
                "frequency_hint": str(row.get("frequency_hint") or "user_forced"),
                "target_bucket": target_bucket,
                "status": str(row.get("status") or "open"),
                "required_actions": [str(x) for x in list(req_actions) if str(x).strip()],
                "closure_criteria": [str(x) for x in list(closure) if str(x).strip()],
                "links": _safe_links(row.get("links")),
            }
        )

    # Deduplicate by id and keep deterministic ordering.
    dedup: Dict[str, Dict[str, Any]] = {}
    for item in items:
        dedup[item["id"]] = item
    stable_items = sorted(dedup.values(), key=lambda x: str(x.get("id")))

    payload: Dict[str, Any] = {
        "schema": "leanatlas.chat_feedback_digest",
        "schema_version": "0.1.0",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_root": in_root.as_posix(),
        "item_count": len(stable_items),
        "items": stable_items,
        "summary": {
            "by_category": _count_by(stable_items, "category"),
            "by_severity": _count_by(stable_items, "severity"),
            "by_target_bucket": _count_by(stable_items, "target_bucket"),
        },
    }

    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rel_out = out_path.relative_to(ROOT).as_posix() if out_path.is_relative_to(ROOT) else out_path.as_posix()
    print(f"[chat-feedback] wrote {rel_out} (items={len(stable_items)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
