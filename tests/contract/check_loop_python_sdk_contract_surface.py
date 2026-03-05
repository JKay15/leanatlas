#!/usr/bin/env python3
"""Contract check: Python SDK surface is pinned and aligned with LOOP MCP semantics."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

try:
    import jsonschema
except Exception:
    print("[loop-sdk-surface] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
SDK_CONTRACT = ROOT / "docs" / "contracts" / "LOOP_PYTHON_SDK_CONTRACT.md"
MCP_CONTRACT = ROOT / "docs" / "contracts" / "LOOP_MCP_CONTRACT.md"
SDK_SCHEMA = ROOT / "docs" / "schemas" / "LoopSDKCallContract.schema.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.sdk import loop, resume, run


def _fail(msg: str) -> int:
    print(f"[loop-sdk-surface][FAIL] {msg}", file=sys.stderr)
    return 2


def main() -> int:
    for p in (SDK_CONTRACT, MCP_CONTRACT, SDK_SCHEMA):
        if not p.exists():
            return _fail(f"missing required file: {p.relative_to(ROOT)}")

    sdk_doc = SDK_CONTRACT.read_text(encoding="utf-8")
    mcp_doc = MCP_CONTRACT.read_text(encoding="utf-8")
    schema = json.loads(SDK_SCHEMA.read_text(encoding="utf-8"))

    # SDK surface snippets
    for s in (
        "loop(...)",
        "serial(...)",
        "parallel(...)",
        "nested(...)",
        "run(...)",
        "resume(...)",
        "assurance_level",
        "agent_provider",
        "agent_profile",
        "review_history",
        "instruction_scope_refs",
        "resolved_invocation_signature",
    ):
        if s not in sdk_doc:
            return _fail(f"LOOP_PYTHON_SDK_CONTRACT missing `{s}`")

    # MCP/SDK group alignment
    groups = [
        "loop/definitions",
        "loop/runs",
        "loop/graphs",
        "loop/components",
        "loop/resources",
        "loop/audit",
        "loop/providers",
        "loop/review-history",
    ]
    for g in groups:
        if g + "/*" not in mcp_doc:
            return _fail(f"LOOP_MCP_CONTRACT missing API group `{g}/*`")
        if g not in schema["properties"]["api_group"]["enum"]:
            return _fail(f"LoopSDKCallContract schema missing api_group `{g}`")

    required = set(schema.get("required") or [])
    for req in ("idempotency_key", "actor_identity", "request", "response"):
        if req not in required:
            return _fail(f"LoopSDKCallContract missing required field `{req}`")

    assurance_prop = (schema.get("properties") or {}).get("assurance_level") or {}
    assurance_enum = assurance_prop.get("enum") or []
    if sorted(assurance_enum) != ["FAST", "LIGHT", "STRICT"]:
        return _fail("LoopSDKCallContract assurance_level enum must be FAST/LIGHT/STRICT")

    # Validate error envelope behavior using schema itself.
    validator = jsonschema.Draft202012Validator(schema)

    ok_call = {
        "version": "1",
        "call_id": "sdk_call_001",
        "api_group": "loop/runs",
        "operation": "start",
        "idempotency_key": "idem-001",
        "actor_identity": "agent.codex",
        "request": {"run_key_hint": "abc"},
        "response": {"status": "OK", "at_utc": "2026-03-05T00:00:00Z", "result_ref": "artifacts/x.json"}
    }
    errs = list(validator.iter_errors(ok_call))
    if errs:
        return _fail(f"valid OK sdk call should pass schema; got {errs[0].message}")

    bad_error_call = {
        "version": "1",
        "call_id": "sdk_call_002",
        "api_group": "loop/runs",
        "operation": "start",
        "idempotency_key": "idem-002",
        "actor_identity": "agent.codex",
        "request": {},
        "response": {"status": "ERROR", "at_utc": "2026-03-05T00:00:00Z"}
    }
    errs = list(validator.iter_errors(bad_error_call))
    if not errs:
        return _fail("ERROR sdk call without `response.error` must fail schema")

    with tempfile.TemporaryDirectory(prefix="loop_sdk_surface_") as td:
        repo = Path(td)
        spec = loop(
            loop_id="loop.sdk.surface.v1",
            graph_mode="STATIC_USER_MODE",
            input_projection_hash="1" * 64,
            instruction_chain_hash="2" * 64,
            dependency_pin_set_id="pins.20260305",
            wave_id="loop.wave.sdk.surface.v1",
        )

        run_default = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-surface-run-default",
        )
        errs = list(validator.iter_errors(run_default))
        if errs:
            return _fail(f"default run() output must satisfy LoopSDKCallContract; got {errs[0].message}")

        run_with_empty_history = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-surface-run-history-empty",
            agent_provider="codex_cli",
            agent_profile="profiles/codex_review.json",
            instruction_scope_refs=[str(ROOT / "AGENTS.md")],
            review_history=[],
        )
        errs = list(validator.iter_errors(run_with_empty_history))
        if errs:
            return _fail(f"run() with empty review_history must satisfy schema; got {errs[0].message}")
        if run_with_empty_history.get("resolved_invocation_signature") != "codex exec review":
            return _fail("run() with agent_provider=codex_cli must expose resolved_invocation_signature")
        review_history_ref = run_with_empty_history.get("review_history_ref")
        if not isinstance(review_history_ref, str) or not review_history_ref:
            return _fail("run() with review_history=[] must return non-empty review_history_ref")

        run_key_root = repo / ".cache" / "leanatlas" / "loop_runtime" / "by_key"
        run_key_candidates = sorted(p.name for p in run_key_root.iterdir() if p.is_dir())
        if not run_key_candidates:
            return _fail("run() should materialize at least one run_key directory")

        resume_default = resume(
            run_key=run_key_candidates[0],
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-surface-resume-default",
        )
        errs = list(validator.iter_errors(resume_default))
        if errs:
            return _fail(f"default resume() output must satisfy LoopSDKCallContract; got {errs[0].message}")

        run_with_history_a = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-surface-run-history-a",
            review_history=[{"iteration_index": 1, "findings": [{"finding_id": "finding.a", "flags": ["CONTRADICTION"]}]}],
        )
        run_with_history_b = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-surface-run-history-b",
            review_history=[{"iteration_index": 1, "findings": [{"finding_id": "finding.b", "flags": ["NITPICK"]}]}],
        )
        ref_b = run_with_history_b.get("review_history_ref")
        if not isinstance(ref_b, str) or not ref_b:
            return _fail("run() with review history must provide review_history_ref")
        history_txt = Path(ref_b).read_text(encoding="utf-8")
        if "finding.b" not in history_txt:
            return _fail("latest run() call must refresh persisted review_history content for same run_key")
        summary_ref_b = [
            p for p in run_with_history_b.get("response", {}).get("trace_refs", []) if p.endswith("review_history_consistency.json")
        ]
        if len(summary_ref_b) != 1:
            return _fail("run() with review history must include one review_history_consistency ref")
        summary_txt = Path(summary_ref_b[0]).read_text(encoding="utf-8")
        if "finding.a" in summary_txt:
            return _fail("review_history_consistency must reflect latest call input, not stale prior data")

    print("[loop-sdk-surface] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
