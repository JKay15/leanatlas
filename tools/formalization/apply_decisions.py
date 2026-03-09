#!/usr/bin/env python3
"""Apply deterministic state decisions to ProofCompletionWorklist."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

COMPLETION_STATES = {
    "NEW",
    "CODEX_ATTEMPTED",
    "GPT52PRO_ESCALATED",
    "TRIAGED_UNPROVABLE_CANDIDATE",
    "COMPLETED",
}

# Deterministic default transition policy for completion workflow.
DEFAULT_TRANSITIONS: set[tuple[str, str]] = {
    ("NEW", "CODEX_ATTEMPTED"),
    ("NEW", "GPT52PRO_ESCALATED"),
    ("NEW", "TRIAGED_UNPROVABLE_CANDIDATE"),
    ("NEW", "COMPLETED"),
    ("CODEX_ATTEMPTED", "GPT52PRO_ESCALATED"),
    ("CODEX_ATTEMPTED", "TRIAGED_UNPROVABLE_CANDIDATE"),
    ("CODEX_ATTEMPTED", "COMPLETED"),
    ("GPT52PRO_ESCALATED", "TRIAGED_UNPROVABLE_CANDIDATE"),
    ("GPT52PRO_ESCALATED", "COMPLETED"),
    ("TRIAGED_UNPROVABLE_CANDIDATE", "COMPLETED"),
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize(text: str) -> str:
    return " ".join(str(text).strip().split())


def _collect_decisions(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if isinstance(doc, dict):
        arr = doc.get("decisions", [])
        if isinstance(arr, list):
            return [x for x in arr if isinstance(x, dict)]
    return []


def _norm_state(value: Any) -> str:
    s = normalize(str(value)).upper()
    return s if s in COMPLETION_STATES else ""


def _resolve_target(
    items_by_key: dict[tuple[str, str, str | None], list[dict[str, Any]]],
    *,
    entity_id: str,
    entity_type: str,
    parent_id: str | None,
    allow_parent_fallback: bool,
) -> dict[str, Any] | None:
    if allow_parent_fallback and parent_id is None:
        matches: list[dict[str, Any]] = []
        for (eid, ety, _pid), bucket in items_by_key.items():
            if eid == entity_id and ety == entity_type:
                matches.extend(bucket)
        if len(matches) == 1:
            return matches[0]
        return None

    key = (entity_id, entity_type, parent_id)
    exact_matches = items_by_key.get(key, [])
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        return None
    return None


def _recompute_counts(worklist: dict[str, Any]) -> None:
    items = [x for x in worklist.get("items", []) if isinstance(x, dict)]
    state_counts = Counter(str(x.get("state", "")).strip() for x in items if str(x.get("state", "")).strip())
    worklist["count"] = len(items)
    worklist["counts"] = dict(sorted(state_counts.items()))


def apply_decisions_to_worklist(
    *,
    worklist: dict[str, Any],
    decisions: list[dict[str, Any]] | dict[str, Any],
    ledger_path: str,
    decisions_path: str,
    force_transitions: bool = False,
    dry_run: bool = False,
    check_skipped: bool = False,
    generated_at_utc: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = copy.deepcopy(worklist)
    items = [x for x in updated.get("items", []) if isinstance(x, dict)]
    items_by_key: dict[tuple[str, str, str | None], list[dict[str, Any]]] = {}
    for x in items:
        entity_id = str(x.get("entity_id", "")).strip()
        if not entity_id:
            continue
        key = (
            entity_id,
            str(x.get("entity_type", "")).strip(),
            x.get("parent_id") if isinstance(x.get("parent_id"), str) else None,
        )
        items_by_key.setdefault(key, []).append(x)

    decision_rows = _collect_decisions(decisions)
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    changed_count = 0
    noop_count = 0

    for idx, dec in enumerate(decision_rows, start=1):
        entity_id = str(dec.get("entity_id", "")).strip()
        entity_type = str(dec.get("entity_type", "FORMALIZATION_BINDING")).strip() or "FORMALIZATION_BINDING"
        has_parent_field = "parent_id" in dec
        parent_id_raw = dec.get("parent_id")
        if has_parent_field and (parent_id_raw is not None) and (not isinstance(parent_id_raw, str)):
            from_state = "NEW"
            to_state = _norm_state(dec.get("to", dec.get("to_state", dec.get("state", dec.get("new_state", ""))))) or "NEW"
            rejected.append(
                {
                    "index": idx,
                    "entity_id": entity_id or "__MISSING_ENTITY_ID__",
                    "entity_type": entity_type,
                    "parent_id": None,
                    "from": from_state,
                    "to": to_state,
                    "outcome": "REJECTED",
                }
            )
            continue
        parent_id = parent_id_raw if isinstance(parent_id_raw, str) else None

        target = _resolve_target(
            items_by_key,
            entity_id=entity_id,
            entity_type=entity_type,
            parent_id=parent_id,
            allow_parent_fallback=not has_parent_field,
        )

        from_state = _norm_state((target or {}).get("state", "NEW")) or "NEW"
        to_state = _norm_state(dec.get("to", dec.get("to_state", dec.get("state", dec.get("new_state", "")))))

        # Keep report schema-valid even when rejected by filling canonical defaults.
        report_row = {
            "index": idx,
            "entity_id": entity_id or "__MISSING_ENTITY_ID__",
            "entity_type": entity_type,
            "parent_id": parent_id,
            "from": from_state,
            "to": to_state or from_state,
        }

        if target is None:
            report_row["outcome"] = "REJECTED"
            rejected.append(report_row)
            continue
        if not to_state:
            report_row["outcome"] = "REJECTED"
            rejected.append(report_row)
            continue

        if from_state == to_state:
            report_row["outcome"] = "NOOP"
            applied.append(report_row)
            noop_count += 1
            continue

        if (not force_transitions) and ((from_state, to_state) not in DEFAULT_TRANSITIONS):
            report_row["outcome"] = "REJECTED"
            rejected.append(report_row)
            continue

        if not dry_run:
            target["state"] = to_state
        report_row["outcome"] = "CHANGED"
        applied.append(report_row)
        changed_count += 1

    if not dry_run:
        _recompute_counts(updated)

    report = {
        "generated_at_utc": generated_at_utc or utc_now_iso(),
        "ledger_path": str(ledger_path),
        "decisions_path": str(decisions_path),
        "dry_run": bool(dry_run),
        "check_skipped": bool(check_skipped),
        "force_transitions": bool(force_transitions),
        "applied": applied,
        "applied_count": len(applied),
        "changed_count": int(changed_count),
        "noop_count": int(noop_count),
        "rejected": rejected,
        "rejected_count": len(rejected),
    }
    return updated, report


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply ProofCompletion decisions to worklist")
    ap.add_argument("--worklist", required=True)
    ap.add_argument("--decisions", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--report-out", default="")
    ap.add_argument("--ledger-path", default="")
    ap.add_argument("--force-transitions", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-check", action="store_true")
    args = ap.parse_args()

    worklist_path = Path(args.worklist).resolve()
    decisions_path = Path(args.decisions).resolve()
    output_path = Path(args.output).resolve()

    worklist = load_json(worklist_path)
    decisions_doc = load_json(decisions_path)

    updated, report = apply_decisions_to_worklist(
        worklist=worklist,
        decisions=decisions_doc,
        ledger_path=args.ledger_path or str(worklist_path),
        decisions_path=str(decisions_path),
        force_transitions=bool(args.force_transitions),
        dry_run=bool(args.dry_run),
        check_skipped=bool(args.skip_check),
    )

    if not args.dry_run:
        dump_json(output_path, updated)
    if args.report_out:
        dump_json(Path(args.report_out).resolve(), report)

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
