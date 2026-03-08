#!/usr/bin/env python3
"""Contract check: SDK run() executes Wave loop and materializes WaveExecutionLoopRun evidence."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

try:
    import jsonschema
except Exception:
    print("[loop-wave-exec-runtime] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[2]
WAVE_SCHEMA = ROOT / "docs" / "schemas" / "WaveExecutionLoopRun.schema.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.sdk import loop, run


def _fail(msg: str) -> int:
    print(f"[loop-wave-exec-runtime][FAIL] {msg}", file=sys.stderr)
    return 2


def main() -> int:
    if not WAVE_SCHEMA.exists():
        return _fail(f"missing schema: {WAVE_SCHEMA.relative_to(ROOT)}")
    schema = json.loads(WAVE_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)

    with tempfile.TemporaryDirectory(prefix="loop_wave_exec_runtime_") as td:
        repo = Path(td)
        spec = loop(
            loop_id="loop.wave.exec.runtime.v1",
            graph_mode="STATIC_USER_MODE",
            input_projection_hash="1" * 64,
            instruction_chain_hash="2" * 64,
            dependency_pin_set_id="pins.20260305",
            wave_id="loop.wave.exec.runtime.v1",
            assurance_level="STRICT",
        )
        out = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-wave-runtime-001",
            agent_provider="codex_cli",
            agent_profile="profiles/codex_review.json",
            instruction_scope_refs=[str(ROOT / "AGENTS.md")],
            review_history=[],
            review_plan=[
                {
                    "verdict": "REPAIRABLE",
                    "confidence": 0.72,
                    "finding_fingerprint": "a" * 64,
                    "findings": [
                        {
                            "finding_id": "finding.wave.runtime.round1",
                            "severity": "S2_MAJOR",
                            "repairable": True,
                            "summary": "Needs one deterministic repair.",
                            "evidence_refs": ["artifacts/review/finding_round1.md"],
                        }
                    ],
                },
                {
                    "verdict": "PASS",
                    "confidence": 0.97,
                    "finding_fingerprint": "b" * 64,
                    "findings": [
                        {
                            "finding_id": "finding.wave.runtime.round2",
                            "severity": "S3_MINOR",
                            "repairable": False,
                            "summary": "No blocking issue remains.",
                            "evidence_refs": ["artifacts/review/finding_round2.md"],
                        }
                    ],
                },
            ],
        )
        if out.get("response", {}).get("status") != "OK":
            return _fail("run() must return response.status=OK")

        refs = out.get("response", {}).get("trace_refs", [])
        wave_refs = [p for p in refs if p.endswith("WaveExecutionLoopRun.json")]
        if len(wave_refs) != 1:
            return _fail("trace_refs must contain exactly one WaveExecutionLoopRun.json reference")

        report_path = Path(wave_refs[0])
        if not report_path.exists():
            return _fail("WaveExecutionLoopRun.json ref path does not exist")
        report = json.loads(report_path.read_text(encoding="utf-8"))

        errs = list(validator.iter_errors(report))
        if errs:
            return _fail(f"WaveExecutionLoopRun artifact must satisfy schema; got {errs[0].message}")

        if report.get("final_decision", {}).get("state") != "PASSED":
            return _fail("review_plan(REPAIRABLE,PASS) should terminate PASSED")
        if report.get("budgets", {}).get("used_ai_review_rounds") != 2:
            return _fail("used_ai_review_rounds must equal consumed review rounds")
        if report.get("execution", {}).get("current_state") != "PASSED":
            return _fail("execution.current_state must equal PASSED")

        dirty = report.get("dirty_tree")
        if not isinstance(dirty, dict):
            return _fail("WaveExecutionLoopRun must include dirty_tree block")
        if dirty.get("checked") is not True:
            return _fail("dirty_tree.checked must be true")
        if dirty.get("in_git_repo") is not False:
            return _fail("temp runtime repo should report in_git_repo=false")
        if dirty.get("disposition") != "NO_GIT_CONTEXT":
            return _fail("temp runtime repo should report dirty_tree.disposition=NO_GIT_CONTEXT")

        evidence = report.get("evidence", {})
        for key in ("ai_review_prompt_ref", "ai_review_response_ref", "ai_review_summary_ref"):
            if not isinstance(evidence.get(key), str) or not evidence.get(key):
                return _fail(f"STRICT PASSED must include non-empty evidence.{key}")

        # Idempotent replay over an already terminal run should remain successful.
        out_replay = run(
            spec=spec,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-wave-runtime-002",
            agent_provider="codex_cli",
            agent_profile="profiles/codex_review.json",
            instruction_scope_refs=[str(ROOT / "AGENTS.md")],
            review_history=[],
            review_plan=[
                {
                    "verdict": "REPAIRABLE",
                    "confidence": 0.72,
                    "finding_fingerprint": "a" * 64,
                    "findings": [
                        {
                            "finding_id": "finding.wave.runtime.round1",
                            "severity": "S2_MAJOR",
                            "repairable": True,
                            "summary": "Needs one deterministic repair.",
                            "evidence_refs": ["artifacts/review/finding_round1.md"],
                        }
                    ],
                },
                {
                    "verdict": "PASS",
                    "confidence": 0.97,
                    "finding_fingerprint": "b" * 64,
                    "findings": [
                        {
                            "finding_id": "finding.wave.runtime.round2",
                            "severity": "S3_MINOR",
                            "repairable": False,
                            "summary": "No blocking issue remains.",
                            "evidence_refs": ["artifacts/review/finding_round2.md"],
                        }
                    ],
                },
            ],
        )
        if out_replay.get("response", {}).get("status") != "OK":
            return _fail("idempotent replay on terminal wave must remain response.status=OK")

        refs_replay = out_replay.get("response", {}).get("trace_refs", [])
        wave_refs_replay = [p for p in refs_replay if p.endswith("WaveExecutionLoopRun.json")]
        if len(wave_refs_replay) != 1:
            return _fail("idempotent replay must still include WaveExecutionLoopRun.json reference")
        report_replay = json.loads(Path(wave_refs_replay[0]).read_text(encoding="utf-8"))
        errs = list(validator.iter_errors(report_replay))
        if errs:
            return _fail(f"idempotent replay report must satisfy schema; got {errs[0].message}")
        if report_replay.get("final_decision", {}).get("state") != "PASSED":
            return _fail("idempotent replay must preserve PASSED terminal decision")

        # Prior review-history refs not present in current findings should still be accepted
        # when passed through history_context_refs for reviewer memory.
        spec_hist = loop(
            loop_id="loop.wave.exec.runtime.history.v1",
            graph_mode="STATIC_USER_MODE",
            input_projection_hash="3" * 64,
            instruction_chain_hash="4" * 64,
            dependency_pin_set_id="pins.20260305",
            wave_id="loop.wave.exec.runtime.history.v1",
            assurance_level="LIGHT",
        )
        out_hist = run(
            spec=spec_hist,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-wave-runtime-history-001",
            agent_provider="codex_cli",
            instruction_scope_refs=[str(ROOT / "AGENTS.md")],
            review_history=[
                {
                    "iteration_index": 9,
                    "contradiction_refs": ["legacy.finding.001"],
                }
            ],
            review_plan=[
                {
                    "verdict": "REPAIRABLE",
                    "confidence": 0.78,
                    "finding_fingerprint": "c" * 64,
                    "findings": [
                        {
                            "finding_id": "finding.wave.runtime.history.round1",
                            "severity": "S2_MAJOR",
                            "repairable": True,
                            "summary": "Carry legacy history context and repair once.",
                            "evidence_refs": ["artifacts/review/history_round1.md"],
                        }
                    ],
                },
                {
                    "verdict": "PASS",
                    "confidence": 0.93,
                    "finding_fingerprint": "d" * 64,
                    "findings": [
                        {
                            "finding_id": "finding.wave.runtime.history.round2",
                            "severity": "S3_MINOR",
                            "repairable": False,
                            "summary": "Current round has no contradiction.",
                            "evidence_refs": ["artifacts/review/history_round2.md"],
                        }
                    ],
                }
            ],
        )
        if out_hist.get("response", {}).get("status") != "OK":
            return _fail("run() with prior contradiction refs should still succeed when history context is carried")
        refs_hist = out_hist.get("response", {}).get("trace_refs", [])
        wave_refs_hist = [p for p in refs_hist if p.endswith("WaveExecutionLoopRun.json")]
        if len(wave_refs_hist) != 1:
            return _fail("history-carry run must include WaveExecutionLoopRun.json")
        report_hist = json.loads(Path(wave_refs_hist[0]).read_text(encoding="utf-8"))
        if "legacy.finding.001" not in report_hist.get("review_history_consistency", {}).get("contradiction_refs", []):
            return _fail("history contradiction ref should be preserved in review_history_consistency")
        if not any(
            "legacy.finding.001" in (rec.get("history_context_refs") or [])
            for rec in report_hist.get("iterations") or []
        ):
            return _fail("legacy history contradiction ref should be injected into history_context_refs")

        spec_non_consecutive = loop(
            loop_id="loop.wave.exec.runtime.non_consecutive.v1",
            graph_mode="STATIC_USER_MODE",
            input_projection_hash="5" * 64,
            instruction_chain_hash="6" * 64,
            dependency_pin_set_id="pins.20260305",
            wave_id="loop.wave.exec.runtime.non_consecutive.v1",
            assurance_level="LIGHT",
        )
        out_non_consecutive = run(
            spec=spec_non_consecutive,
            repo_root=repo,
            actor_identity="agent.codex",
            idempotency_key="idem-wave-runtime-non-consecutive-001",
            agent_provider="codex_cli",
            instruction_scope_refs=[str(ROOT / "AGENTS.md")],
            review_history=[],
            review_plan=[
                {
                    "verdict": "REPAIRABLE",
                    "confidence": 0.71,
                    "finding_fingerprint": "a" * 64,
                    "findings": [
                        {
                            "finding_id": "finding.wave.runtime.nonconsec.round1",
                            "severity": "S2_MAJOR",
                            "repairable": True,
                            "summary": "Round1 repairable.",
                            "evidence_refs": ["artifacts/review/nonconsec_round1.md"],
                        }
                    ],
                },
                {
                    "verdict": "REPAIRABLE",
                    "confidence": 0.73,
                    "finding_fingerprint": "b" * 64,
                    "findings": [
                        {
                            "finding_id": "finding.wave.runtime.nonconsec.round2",
                            "severity": "S2_MAJOR",
                            "repairable": True,
                            "summary": "Round2 repairable with different fingerprint.",
                            "evidence_refs": ["artifacts/review/nonconsec_round2.md"],
                        }
                    ],
                },
                {
                    "verdict": "PASS",
                    "confidence": 0.95,
                    "finding_fingerprint": "a" * 64,
                    "findings": [
                        {
                            "finding_id": "finding.wave.runtime.nonconsec.round3",
                            "severity": "S3_MINOR",
                            "repairable": False,
                            "summary": "Final pass after non-consecutive fingerprint repeat.",
                            "evidence_refs": ["artifacts/review/nonconsec_round3.md"],
                        }
                    ],
                },
            ],
        )
        if out_non_consecutive.get("response", {}).get("status") != "OK":
            return _fail("A,B,A non-consecutive fingerprint run should remain valid and return response.status=OK")
        refs_non_consecutive = out_non_consecutive.get("response", {}).get("trace_refs", [])
        wave_refs_non_consecutive = [p for p in refs_non_consecutive if p.endswith("WaveExecutionLoopRun.json")]
        if len(wave_refs_non_consecutive) != 1:
            return _fail("non-consecutive run must include WaveExecutionLoopRun.json")
        report_non_consecutive = json.loads(Path(wave_refs_non_consecutive[0]).read_text(encoding="utf-8"))
        errs = list(validator.iter_errors(report_non_consecutive))
        if errs:
            return _fail(f"non-consecutive run report must satisfy schema; got {errs[0].message}")
        if report_non_consecutive.get("final_decision", {}).get("state") != "PASSED":
            return _fail("A,B,A non-consecutive fingerprint run should terminate PASSED")
        if report_non_consecutive.get("derived_metrics", {}).get("max_consecutive_same_fingerprint") != 1:
            return _fail("A,B,A must yield max_consecutive_same_fingerprint=1")

    print("[loop-wave-exec-runtime] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
