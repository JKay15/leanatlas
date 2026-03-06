#!/usr/bin/env python3
"""Contract check: LOOP Wave-A schemas + fixtures validate deterministically."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

try:
    import jsonschema
except Exception:
    print("[loop-schema] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "docs" / "schemas"
FIXTURES = ROOT / "tests" / "contract" / "fixtures" / "loop"
POS = FIXTURES / "positive"
NEG = FIXTURES / "negative"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


SCHEMA_FILES = {
    "loopdefinition": "LoopDefinition.schema.json",
    "looprun": "LoopRun.schema.json",
    "loopgraphspec": "LoopGraphSpec.schema.json",
    "resourcelease": "ResourceLease.schema.json",
    "instructionresolution": "InstructionResolutionReport.schema.json",
    "auditflagged": "AuditFlaggedEvent.schema.json",
    "canonicalreviewresult": "CanonicalReviewResult.schema.json",
    "loopsdkcall": "LoopSDKCallContract.schema.json",
    "waveexecutionlooprun": "WaveExecutionLoopRun.schema.json",
}


def _pick_schema(path: Path, validators: Dict[str, jsonschema.Draft202012Validator]) -> Tuple[jsonschema.Draft202012Validator, str]:
    for prefix, _name in SCHEMA_FILES.items():
        if path.name.startswith(prefix + "_"):
            return validators[prefix], prefix
    raise RuntimeError(f"unknown fixture prefix: {path.name}")


def _validate_one(path: Path, validators: Dict[str, jsonschema.Draft202012Validator]) -> list[str]:
    validator, schema_key = _pick_schema(path, validators)
    obj = _load_json(path)
    errs = sorted(validator.iter_errors(obj), key=lambda e: list(e.absolute_path))
    msgs: list[str] = []
    for e in errs:
        p = "/" + "/".join(str(x) for x in e.absolute_path)
        msgs.append(f"{schema_key}:{path.name}:{p}: {e.message}")
    return msgs


def main() -> int:
    missing_schema_files = [
        f"docs/schemas/{name}" for name in SCHEMA_FILES.values() if not (SCHEMAS / name).exists()
    ]
    if missing_schema_files:
        print("[loop-schema][FAIL] missing schema files:", file=sys.stderr)
        for m in missing_schema_files:
            print(f"  - {m}", file=sys.stderr)
        return 2

    validators: Dict[str, jsonschema.Draft202012Validator] = {}
    raw: Dict[str, Dict[str, Any]] = {}
    for key, fname in SCHEMA_FILES.items():
        schema = _load_json(SCHEMAS / fname)
        raw[key] = schema
        validators[key] = jsonschema.Draft202012Validator(
            schema,
            format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
        )

    bad = 0
    for f in sorted(POS.glob("*.json")):
        errs = _validate_one(f, validators)
        if errs:
            bad += 1
            print("[loop-schema][FAIL][positive]", *errs, sep="\n  ", file=sys.stderr)
        else:
            print(f"[loop-schema][OK][positive] {f.name}")

    for f in sorted(NEG.glob("*.json")):
        errs = _validate_one(f, validators)
        if not errs:
            bad += 1
            print(f"[loop-schema][FAIL][negative] {f.name}: expected errors but got none", file=sys.stderr)
        else:
            print(f"[loop-schema][OK][negative] {f.name} (got {len(errs)} errors)")

    # Focused semantic checks for policy-critical fields.
    exec_enum = raw["looprun"]["$defs"]["executionState"]["enum"]
    if "AI_REVIEW" not in exec_enum:
        print("[loop-schema][FAIL] LoopRun execution enum must include AI_REVIEW", file=sys.stderr)
        bad += 1
    if "HUMAN_REVIEW" in exec_enum:
        print("[loop-schema][FAIL] LoopRun execution enum must not include HUMAN_REVIEW", file=sys.stderr)
        bad += 1

    audit_required = set(raw["auditflagged"]["required"])
    for req in ("severity", "category", "evidence_refs", "run_key"):
        if req not in audit_required:
            print(f"[loop-schema][FAIL] AuditFlaggedEvent missing required field `{req}`", file=sys.stderr)
            bad += 1

    canonical_required = set(raw["canonicalreviewresult"].get("required") or [])
    for req in (
        "review_id",
        "attempt_index",
        "agent_provider_id",
        "provider_adapter_id",
        "status",
        "reason_code",
        "terminal",
        "response_ref",
    ):
        if req not in canonical_required:
            print(f"[loop-schema][FAIL] CanonicalReviewResult missing required field `{req}`", file=sys.stderr)
            bad += 1
    canonical_status_enum = (raw["canonicalreviewresult"].get("properties") or {}).get("status", {}).get("enum") or []
    for req in (
        "SUCCEEDED",
        "STALE_INPUT",
        "COMMAND_FAILED",
        "REVIEW_TIMEOUT",
        "SEMANTIC_IDLE_TIMEOUT",
        "RESPONSE_INVALID",
        "NO_TERMINAL_EVENT",
    ):
        if req not in canonical_status_enum:
            print(f"[loop-schema][FAIL] CanonicalReviewResult status enum missing `{req}`", file=sys.stderr)
            bad += 1
    source_schema = (raw["canonicalreviewresult"].get("properties") or {}).get("semantic_response_source") or {}
    source_any_of = source_schema.get("anyOf") or []
    flattened_source_values = {
        value
        for branch in source_any_of
        for value in ((branch.get("enum") or []) if isinstance(branch, dict) else [])
    }
    for req in ("response_file", "provider_event_jsonl"):
        if req not in flattened_source_values:
            print(f"[loop-schema][FAIL] CanonicalReviewResult semantic_response_source missing `{req}`", file=sys.stderr)
            bad += 1

    sdk_required = set(raw["loopsdkcall"]["required"])
    for req in ("idempotency_key", "actor_identity", "response"):
        if req not in sdk_required:
            print(f"[loop-schema][FAIL] LoopSDKCallContract missing required field `{req}`", file=sys.stderr)
            bad += 1
    sdk_props = raw["loopsdkcall"].get("properties", {})
    if "resolved_invocation_signature" not in sdk_props:
        print(
            "[loop-schema][FAIL] LoopSDKCallContract must expose `resolved_invocation_signature` for provider routing evidence",
            file=sys.stderr,
        )
        bad += 1

    review_verdict_enum = raw["waveexecutionlooprun"]["$defs"]["reviewVerdict"]["enum"]
    for req in ("PASS", "REPAIRABLE", "UNRESOLVED_BLOCKER", "NON_RETRYABLE"):
        if req not in review_verdict_enum:
            print(
                f"[loop-schema][FAIL] WaveExecutionLoopRun reviewVerdict enum missing `{req}`",
                file=sys.stderr,
            )
            bad += 1

    decision_reason_enum = raw["waveexecutionlooprun"]["$defs"]["decisionReason"]["enum"]
    for req in (
        "WAVE_START",
        "IMPLEMENTATION_SUBMITTED_FOR_REVIEW",
        "REVIEW_BUDGET_EXHAUSTED",
        "REVIEW_STAGNATION",
        "REVIEW_UNRESOLVED_BLOCKER",
        "REVIEW_NON_RETRYABLE_FAULT",
    ):
        if req not in decision_reason_enum:
            print(
                f"[loop-schema][FAIL] WaveExecutionLoopRun decisionReason enum missing `{req}`",
                file=sys.stderr,
            )
            bad += 1

    wave_required = set(raw["waveexecutionlooprun"]["required"])
    for req in (
        "assurance_level",
        "iterations",
        "budgets",
        "derived_metrics",
        "dirty_tree",
        "evidence",
        "final_decision",
        "agent_invocation",
        "review_history_consistency",
    ):
        if req not in wave_required:
            print(f"[loop-schema][FAIL] WaveExecutionLoopRun missing required field `{req}`", file=sys.stderr)
            bad += 1

    assurance_enum = raw["waveexecutionlooprun"]["$defs"]["assuranceLevel"]["enum"]
    for req in ("FAST", "LIGHT", "STRICT"):
        if req not in assurance_enum:
            print(f"[loop-schema][FAIL] WaveExecutionLoopRun assuranceLevel missing `{req}`", file=sys.stderr)
            bad += 1

    budget_props = raw["waveexecutionlooprun"]["properties"]["budgets"]["properties"]
    if budget_props["max_ai_review_rounds"].get("default") != 8:
        print("[loop-schema][FAIL] WaveExecutionLoopRun max_ai_review_rounds default must be 8", file=sys.stderr)
        bad += 1
    if budget_props["max_same_fingerprint_rounds"].get("default") != 2:
        print("[loop-schema][FAIL] WaveExecutionLoopRun max_same_fingerprint_rounds default must be 2", file=sys.stderr)
        bad += 1
    if budget_props["max_same_fingerprint_rounds"].get("const") != 2:
        print("[loop-schema][FAIL] WaveExecutionLoopRun max_same_fingerprint_rounds must be fixed at 2", file=sys.stderr)
        bad += 1
    if budget_props["max_wave_wall_clock_minutes"].get("default") != 120:
        print("[loop-schema][FAIL] WaveExecutionLoopRun max_wave_wall_clock_minutes default must be 120", file=sys.stderr)
        bad += 1

    transition_any_of = raw["waveexecutionlooprun"]["$defs"]["transition"].get("anyOf") or []
    if len(transition_any_of) < 6:
        print("[loop-schema][FAIL] WaveExecutionLoopRun transition.anyOf must enumerate allowed edges", file=sys.stderr)
        bad += 1
    expected_ts_pattern = "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
    transition_at = raw["waveexecutionlooprun"]["$defs"]["transition"]["properties"]["at_utc"]
    if transition_at.get("pattern") != expected_ts_pattern:
        print("[loop-schema][FAIL] transition.at_utc must enforce deterministic UTC timestamp pattern", file=sys.stderr)
        bad += 1
    final_at = raw["waveexecutionlooprun"]["properties"]["final_decision"]["properties"]["at_utc"]
    if final_at.get("pattern") != expected_ts_pattern:
        print("[loop-schema][FAIL] final_decision.at_utc must enforce deterministic UTC timestamp pattern", file=sys.stderr)
        bad += 1

    review_required = set(raw["waveexecutionlooprun"]["$defs"]["reviewRecord"]["required"])
    if "wall_clock_used_minutes" not in review_required:
        print("[loop-schema][FAIL] WaveExecutionLoopRun reviewRecord must require wall_clock_used_minutes", file=sys.stderr)
        bad += 1
    if "history_context_refs" not in review_required:
        print("[loop-schema][FAIL] WaveExecutionLoopRun reviewRecord must require history_context_refs", file=sys.stderr)
        bad += 1
    review_props = raw["waveexecutionlooprun"]["$defs"]["reviewRecord"]["properties"]
    if "history_context_refs" not in review_props:
        print("[loop-schema][FAIL] WaveExecutionLoopRun reviewRecord must expose history_context_refs", file=sys.stderr)
        bad += 1

    dirty_obj = raw["waveexecutionlooprun"]["properties"].get("dirty_tree", {})
    if "$ref" in dirty_obj:
        dirty_key = str(dirty_obj["$ref"]).split("/")[-1]
        dirty_props = raw["waveexecutionlooprun"]["$defs"].get(dirty_key, {}).get("properties", {})
        dirty_required = set(raw["waveexecutionlooprun"]["$defs"].get(dirty_key, {}).get("required", []))
    else:
        dirty_props = dirty_obj.get("properties", {})
        dirty_required = set(dirty_obj.get("required", []))
    for req in ("checked", "in_git_repo", "is_clean", "disposition", "head_commit", "changed_entry_count"):
        if req not in dirty_props:
            print(f"[loop-schema][FAIL] WaveExecutionLoopRun dirty_tree missing `{req}`", file=sys.stderr)
            bad += 1
    for req in ("checked", "in_git_repo", "is_clean", "disposition", "head_commit"):
        if req not in dirty_required:
            print(f"[loop-schema][FAIL] WaveExecutionLoopRun dirty_tree must require `{req}`", file=sys.stderr)
            bad += 1

    all_of = raw["waveexecutionlooprun"].get("allOf", [])
    no_git_rule = None
    for rule in all_of:
        try:
            flag = rule["if"]["properties"]["dirty_tree"]["properties"]["in_git_repo"]["const"]
        except Exception:
            flag = None
        if flag is False:
            no_git_rule = rule
            break
    if no_git_rule is None:
        print("[loop-schema][FAIL] WaveExecutionLoopRun missing no-git dirty_tree canonicalization rule", file=sys.stderr)
        bad += 1
    else:
        dt_then = no_git_rule.get("then", {}).get("properties", {}).get("dirty_tree", {}).get("properties", {})
        expected_consts = {
            ("disposition", "const", "NO_GIT_CONTEXT"),
            ("is_clean", "const", True),
            ("tracked_entry_count", "const", 0),
            ("untracked_entry_count", "const", 0),
            ("changed_entry_count", "const", 0),
        }
        for field, key, want in expected_consts:
            got = dt_then.get(field, {}).get(key)
            if got != want:
                print(
                    f"[loop-schema][FAIL] WaveExecutionLoopRun no-git rule must set dirty_tree.{field}.{key}={want!r}",
                    file=sys.stderr,
                )
                bad += 1

    evidence_props = raw["waveexecutionlooprun"]["properties"]["evidence"]["properties"]
    for req in ("ai_review_prompt_ref", "ai_review_response_ref", "ai_review_summary_ref"):
        if req not in evidence_props:
            print(f"[loop-schema][FAIL] WaveExecutionLoopRun evidence missing `{req}`", file=sys.stderr)
            bad += 1
    if "timeout_command_span" not in evidence_props:
        print("[loop-schema][FAIL] WaveExecutionLoopRun evidence missing `timeout_command_span`", file=sys.stderr)
        bad += 1

    timeout_def = raw["waveexecutionlooprun"]["$defs"].get("timeoutCommandSpan", {})
    timeout_required = set(timeout_def.get("required", []))
    for req in ("timed_out", "exit_code", "stdout_path", "stderr_path"):
        if req not in timeout_required:
            print(f"[loop-schema][FAIL] timeoutCommandSpan must require `{req}`", file=sys.stderr)
            bad += 1
    all_of_rules = raw["waveexecutionlooprun"].get("allOf") or []
    timeout_rule_found = False
    for rule in all_of_rules:
        try:
            reason = rule["if"]["properties"]["final_decision"]["properties"]["reason_code"]["const"]
        except Exception:
            reason = None
        if reason != "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED":
            continue
        req_fields = set(rule.get("then", {}).get("properties", {}).get("evidence", {}).get("required", []))
        if "timeout_command_span" in req_fields:
            timeout_rule_found = True
            break
    if not timeout_rule_found:
        print(
            "[loop-schema][FAIL] WaveExecutionLoopRun allOf must require evidence.timeout_command_span for REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED",
            file=sys.stderr,
        )
        bad += 1

    inv_obj = raw["waveexecutionlooprun"]["properties"].get("agent_invocation", {})
    if "$ref" in inv_obj:
        inv_key = str(inv_obj["$ref"]).split("/")[-1]
        inv_props = raw["waveexecutionlooprun"]["$defs"].get(inv_key, {}).get("properties", {})
    else:
        inv_props = inv_obj.get("properties", {})
    for req in ("agent_provider_id", "resolved_invocation", "instruction_scope_refs"):
        if req not in inv_props:
            print(f"[loop-schema][FAIL] WaveExecutionLoopRun agent_invocation missing `{req}`", file=sys.stderr)
            bad += 1

    hist_obj = raw["waveexecutionlooprun"]["properties"].get("review_history_consistency", {})
    if "$ref" in hist_obj:
        hist_key = str(hist_obj["$ref"]).split("/")[-1]
        hist_props = raw["waveexecutionlooprun"]["$defs"].get(hist_key, {}).get("properties", {})
    else:
        hist_props = hist_obj.get("properties", {})
    for req in ("contradiction_count", "potential_nitpick_count", "contradiction_refs"):
        if req not in hist_props:
            print(f"[loop-schema][FAIL] WaveExecutionLoopRun review_history_consistency missing `{req}`", file=sys.stderr)
            bad += 1

    all_of_rules = raw["waveexecutionlooprun"].get("allOf") or []
    if len(all_of_rules) < 5:
        print("[loop-schema][FAIL] WaveExecutionLoopRun allOf must include terminal + stagnation constraints", file=sys.stderr)
        bad += 1

    if bad:
        return 2

    print("[loop-schema] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
