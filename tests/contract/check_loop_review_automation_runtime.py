#!/usr/bin/env python3
"""Contract: default staged review execution must be automatic and preference-backed."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> int:
    print(f"[loop-review-automation-runtime][FAIL] {msg}", file=sys.stderr)
    return 2


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _runtime_env(
    stage: dict[str, object],
    *,
    review_mode: str = "clean",
    reasoning_effort: str | None = None,
) -> dict[str, str]:
    return {
        "REVIEW_MODE": review_mode,
        "REVIEW_STAGE_ID": str(stage.get("stage_id") or ""),
        "REVIEW_RUNTIME_MODEL": "gpt-5.4",
        "REVIEW_RUNTIME_PROVIDER": "openai",
        "REVIEW_RUNTIME_REASONING_EFFORT": reasoning_effort or str(stage.get("agent_profile") or "low"),
    }


def main() -> int:
    try:
        from tools.loop.review_orchestration import (
            build_default_review_orchestration_bundle,
            execute_review_orchestration_bundle,
        )
        from tools.loop.user_preferences import default_preference_artifact_path
    except Exception as exc:  # noqa: BLE001
        return _fail(f"missing default review automation runtime: {exc}")

    with tempfile.TemporaryDirectory(prefix="loop_review_automation_") as td:
        repo = Path(td)
        _write(repo / "AGENTS.md", "# root\n")
        _write(repo / "tools" / "AGENTS.md", "# tools\n")
        _write(repo / "docs" / "contracts" / "LOOP_WAVE_EXECUTION_CONTRACT.md", "# contract\n")
        _write(repo / "docs" / "agents" / "execplans" / "active_plan.md", "# plan\n")
        _write(repo / "tools" / "loop" / "target.py", "VALUE = 1\n")

        helper = repo / "review_helper.py"
        _write(
            helper,
            (
                "from __future__ import annotations\n"
                "import json, os, pathlib, sys\n"
                "response = pathlib.Path(os.environ['LEANATLAS_REVIEW_RESPONSE_PATH'])\n"
                "response.parent.mkdir(parents=True, exist_ok=True)\n"
                "mode = os.environ.get('REVIEW_MODE', 'clean')\n"
                "stage_id = os.environ.get('REVIEW_STAGE_ID', '')\n"
                "for label, env_key in (\n"
                "    ('model', 'REVIEW_RUNTIME_MODEL'),\n"
                "    ('provider', 'REVIEW_RUNTIME_PROVIDER'),\n"
                "    ('reasoning effort', 'REVIEW_RUNTIME_REASONING_EFFORT'),\n"
                "):\n"
                "    value = os.environ.get(env_key)\n"
                "    if value:\n"
                "        print(f'{label}: {value}', flush=True)\n"
                "if mode == 'skip':\n"
                "    raise SystemExit(0)\n"
                "if mode == 'structured_no_findings' and stage_id == 'final_integrated_closeout':\n"
                "    response.write_text(json.dumps({'findings': []}, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'final_json_findings' and stage_id == 'final_integrated_closeout':\n"
                "    response.write_text(json.dumps({'findings': [\n"
                "        {'finding_id': 'finding.final.001', 'severity': 'S1_CRITICAL', 'repairable': True, 'evidence': ['artifacts/reviews/finding_001.md'], 'summary': 'Final closeout issue one'},\n"
                "        {'finding_id': 'finding.final.002', 'severity': 'S2_MAJOR', 'repairable': True, 'evidence': ['artifacts/reviews/finding_002.md'], 'summary': 'Final closeout issue two'}\n"
                "    ]}, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'raw_prose' and stage_id == 'final_integrated_closeout':\n"
                "    response.write_text('This closeout is suspicious, but I am not returning structured finding records.\\n', encoding='utf-8')\n"
                "    raise SystemExit(0)\n"
                "response.write_text('No findings.\\n', encoding='utf-8')\n"
                "raise SystemExit(0)\n"
            ),
        )

        preference_path = default_preference_artifact_path(repo)
        if preference_path.exists():
            return _fail("preference artifact should not exist before default review automation materializes it")

        bundle = build_default_review_orchestration_bundle(
            repo_root=repo,
            review_id="default review/execution",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        if not preference_path.exists():
            return _fail("default review automation must auto-stage the default preference artifact")
        if bundle["preferences_ref"] != str(preference_path):
            return _fail("default review automation must expose the staged preference artifact path")
        closeout_policy = dict(bundle["strategy_plan"]["closeout_policy"])
        if closeout_policy.get("review_tier_policy") != "LOW_PLUS_MEDIUM":
            return _fail("default review automation must preserve LOW_PLUS_MEDIUM tier policy")
        final_stage = next(
            stage for stage in (bundle["strategy_plan"].get("stages") or []) if stage.get("stage_id") == "final_integrated_closeout"
        )
        if final_stage["review_tier"] != "LOW":
            return _fail("default review automation must use LOW as the default integrated closeout tier")

        escalated_bundle = build_default_review_orchestration_bundle(
            repo_root=repo,
            review_id="default_review_followup",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
            followup_partition_ids=["part_01_tools"],
        )
        escalated_final_stage = next(
            stage
            for stage in (escalated_bundle["strategy_plan"].get("stages") or [])
            if stage.get("stage_id") == "final_integrated_closeout"
        )
        if escalated_final_stage["review_tier"] != "MEDIUM":
            return _fail("default review automation must escalate the integrated closeout tier when follow-up partitions are selected")

        result = execute_review_orchestration_bundle(
            repo_root=repo,
            review_id="default review/execution",
            orchestration_bundle=bundle["orchestration_bundle"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
            prompt_root=repo / "artifacts" / "reviews",
            command_factory=lambda _stage, _prompt_path, _response_path: [sys.executable, str(helper)],
            env_factory=lambda stage: _runtime_env(stage),
        )
        if result["final_status"] != "PASSED":
            return _fail("automatic staged review execution must pass when all stage reviews are clean")
        reconciliation_ref = Path(str(result["reconciliation_ref"]))
        if not reconciliation_ref.exists():
            return _fail("automatic staged review execution must persist a reconciliation artifact")
        reconciliation = _read_json(reconciliation_ref)
        authoritative_round_id = str(reconciliation.get("authoritative_closeout_review_round_id") or "")
        authoritative_round = next(
            (
                dict(item)
                for item in (reconciliation.get("review_rounds") or [])
                if str(item.get("review_round_id") or "") == authoritative_round_id
            ),
            {},
        )
        if authoritative_round.get("stage_id") != "final_integrated_closeout":
            return _fail("automatic staged review execution must preserve final integrated closeout authority")
        review_round_refs = [Path(ref) for ref in result["review_round_response_refs"]]
        if not review_round_refs:
            return _fail("automatic staged review execution must preserve review response refs")
        if any(path.read_text(encoding="utf-8").strip() != "No findings." for path in review_round_refs):
            return _fail("automatic staged review execution must preserve stage review outputs")

        mismatch_bundle = build_default_review_orchestration_bundle(
            repo_root=repo,
            review_id="default_review_profile_mismatch",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        mismatch_final_stage = next(
            stage
            for stage in (mismatch_bundle["strategy_plan"].get("stages") or [])
            if stage.get("stage_id") == "final_integrated_closeout"
        )
        if mismatch_final_stage.get("agent_profile") != "low":
            return _fail("runtime profile mismatch regression expects a low final reviewer stage")
        mismatch_result = execute_review_orchestration_bundle(
            repo_root=repo,
            review_id="default_review_profile_mismatch",
            orchestration_bundle=mismatch_bundle["orchestration_bundle"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
            prompt_root=repo / "artifacts" / "reviews_profile_mismatch",
            command_factory=lambda _stage, _prompt_path, _response_path: [sys.executable, str(helper)],
            env_factory=lambda stage: _runtime_env(
                stage,
                reasoning_effort=(
                    "xhigh" if str(stage.get("stage_id") or "") == "final_integrated_closeout" else None
                ),
            ),
        )
        if mismatch_result["final_status"] != "TRIAGED":
            return _fail("review automation must triage reviewer runtime profile mismatches")
        if mismatch_result.get("reason_code") != "REVIEWER_PROFILE_MISMATCH":
            return _fail("review automation must preserve REVIEWER_PROFILE_MISMATCH")
        if mismatch_result.get("failed_stage_id") != "final_integrated_closeout":
            return _fail("review automation must point to the mismatched reviewer stage")
        mismatch_summaries = [Path(ref) for ref in mismatch_result["review_round_summary_refs"]]
        mismatch_summary = _read_json(mismatch_summaries[-1])
        if (mismatch_summary.get("observed_runtime_metadata") or {}).get("reasoning_effort") != "xhigh":
            return _fail("triaged review automation must preserve observed mismatched runtime metadata")

        structured_clean_bundle = build_default_review_orchestration_bundle(
            repo_root=repo,
            review_id="default_review_structured_clean",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        structured_clean_result = execute_review_orchestration_bundle(
            repo_root=repo,
            review_id="default_review_structured_clean",
            orchestration_bundle=structured_clean_bundle["orchestration_bundle"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
            prompt_root=repo / "artifacts" / "reviews_structured_clean",
            command_factory=lambda _stage, _prompt_path, _response_path: [sys.executable, str(helper)],
            env_factory=lambda stage: _runtime_env(stage, review_mode="structured_no_findings"),
        )
        if structured_clean_result["final_status"] != "PASSED":
            return _fail("structured no-findings reviewer payloads must still close the review bundle cleanly")
        structured_clean_reconciliation = _read_json(Path(str(structured_clean_result["reconciliation_ref"])))
        if list(structured_clean_reconciliation.get("finding_records") or []):
            return _fail("structured no-findings reviewer payloads must not materialize synthetic findings")

        json_bundle = build_default_review_orchestration_bundle(
            repo_root=repo,
            review_id="default_review_json",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        json_result = execute_review_orchestration_bundle(
            repo_root=repo,
            review_id="default_review_json",
            orchestration_bundle=json_bundle["orchestration_bundle"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
            prompt_root=repo / "artifacts" / "reviews_json",
            command_factory=lambda _stage, _prompt_path, _response_path: [sys.executable, str(helper)],
            env_factory=lambda stage: _runtime_env(stage, review_mode="final_json_findings"),
        )
        if json_result["final_status"] != "PASSED":
            return _fail("structured review findings should still produce a passing executed review bundle")
        json_reconciliation = _read_json(Path(str(json_result["reconciliation_ref"])))
        finding_records = list(json_reconciliation.get("finding_records") or [])
        if sorted(str(item.get("source_finding_id") or "") for item in finding_records) != [
            "finding.final.001",
            "finding.final.002",
        ]:
            return _fail("reconciliation must preserve individual structured finding ids from reviewer output")

        raw_bundle = build_default_review_orchestration_bundle(
            repo_root=repo,
            review_id="default_review_raw_prose",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        raw_result = execute_review_orchestration_bundle(
            repo_root=repo,
            review_id="default_review_raw_prose",
            orchestration_bundle=raw_bundle["orchestration_bundle"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
            prompt_root=repo / "artifacts" / "reviews_raw",
            command_factory=lambda _stage, _prompt_path, _response_path: [sys.executable, str(helper)],
            env_factory=lambda stage: _runtime_env(stage, review_mode="raw_prose"),
        )
        if raw_result["final_status"] != "TRIAGED":
            return _fail("review automation must triage reviewer output that is not reconcilable into structured findings")
        if raw_result.get("reason_code") != "UNPARSEABLE_REVIEW_OUTPUT":
            return _fail("raw prose reviewer output must preserve the unparseable-output reason code")
        if raw_result.get("reconciliation_ref") is not None:
            return _fail("review automation must not publish reconciliation output for unparseable reviewer responses")

        skipped_bundle = build_default_review_orchestration_bundle(
            repo_root=repo,
            review_id="default_review_skip",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        skipped_result = execute_review_orchestration_bundle(
            repo_root=repo,
            review_id="default_review_skip",
            orchestration_bundle=skipped_bundle["orchestration_bundle"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
            prompt_root=repo / "artifacts" / "reviews_skip",
            command_factory=lambda _stage, _prompt_path, _response_path: [sys.executable, str(helper)],
            env_factory=lambda stage: _runtime_env(
                stage,
                review_mode="skip" if str(stage.get("stage_id") or "") == "fast_partition_scan" else "clean",
            ),
        )
        if skipped_result["final_status"] != "TRIAGED":
            return _fail("review automation must triage when a reviewer stage produces no closeout evidence")
        if skipped_result.get("reason_code") != "NO_TERMINAL_EVENT":
            return _fail("skipped reviewer stages must preserve the underlying closeout reason_code")
        if skipped_result.get("reconciliation_ref") is not None:
            return _fail("triaged review automation must not publish authoritative reconciliation output")
        skipped_summaries = [Path(ref) for ref in skipped_result["review_round_summary_refs"]]
        if not skipped_summaries:
            return _fail("triaged review automation must still preserve the failed stage summary refs")
        skipped_summary = _read_json(skipped_summaries[0])
        if dict(skipped_summary.get("review_closeout") or {}).get("mode") != "REVIEW_SKIPPED":
            return _fail("triaged review automation must surface the skipped review closeout mode")

    with tempfile.TemporaryDirectory(prefix="loop_review_automation_runkey_a_") as td_a:
        repo_a = Path(td_a)
        _write(repo_a / "AGENTS.md", "# root\n")
        _write(repo_a / "tools" / "AGENTS.md", "# tools\n")
        _write(repo_a / "docs" / "contracts" / "LOOP_WAVE_EXECUTION_CONTRACT.md", "# contract\n")
        _write(repo_a / "docs" / "agents" / "execplans" / "active_plan.md", "# plan A\n")
        _write(repo_a / "docs" / "agents" / "execplans" / "alt_plan.md", "# alt plan A\n")
        _write(repo_a / "tools" / "loop" / "target.py", "VALUE = 1\n")
        helper_a = repo_a / "review_helper.py"
        _write(
            helper_a,
            (
                "from pathlib import Path\n"
                "import os\n"
                "for label, env_key in (('model', 'REVIEW_RUNTIME_MODEL'), ('provider', 'REVIEW_RUNTIME_PROVIDER'), ('reasoning effort', 'REVIEW_RUNTIME_REASONING_EFFORT')):\n"
                "    value = os.environ.get(env_key)\n"
                "    if value:\n"
                "        print(f'{label}: {value}', flush=True)\n"
                "p = Path(os.environ['LEANATLAS_REVIEW_RESPONSE_PATH'])\n"
                "p.parent.mkdir(parents=True, exist_ok=True)\n"
                "p.write_text('No findings.\\n', encoding='utf-8')\n"
            ),
        )
        bundle_a = build_default_review_orchestration_bundle(
            repo_root=repo_a,
            review_id="default_review_runkey",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        result_a = execute_review_orchestration_bundle(
            repo_root=repo_a,
            review_id="default_review_runkey",
            orchestration_bundle=bundle_a["orchestration_bundle"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
            prompt_root=repo_a / "artifacts" / "reviews",
            command_factory=lambda _stage, _prompt_path, _response_path: [sys.executable, str(helper_a)],
            env_factory=lambda stage: _runtime_env(stage),
        )

    with tempfile.TemporaryDirectory(prefix="loop_review_automation_runkey_b_") as td_b:
        repo_b = Path(td_b)
        _write(repo_b / "AGENTS.md", "# root\n")
        _write(repo_b / "tools" / "AGENTS.md", "# tools\n")
        _write(repo_b / "docs" / "contracts" / "LOOP_WAVE_EXECUTION_CONTRACT.md", "# contract\n")
        _write(repo_b / "docs" / "agents" / "execplans" / "active_plan.md", "# plan B updated\n")
        _write(repo_b / "docs" / "agents" / "execplans" / "alt_plan.md", "# alt plan B\n")
        _write(repo_b / "tools" / "loop" / "target.py", "VALUE = 1\n")
        helper_b = repo_b / "review_helper.py"
        _write(
            helper_b,
            (
                "from pathlib import Path\n"
                "import os\n"
                "for label, env_key in (('model', 'REVIEW_RUNTIME_MODEL'), ('provider', 'REVIEW_RUNTIME_PROVIDER'), ('reasoning effort', 'REVIEW_RUNTIME_REASONING_EFFORT')):\n"
                "    value = os.environ.get(env_key)\n"
                "    if value:\n"
                "        print(f'{label}: {value}', flush=True)\n"
                "p = Path(os.environ['LEANATLAS_REVIEW_RESPONSE_PATH'])\n"
                "p.parent.mkdir(parents=True, exist_ok=True)\n"
                "p.write_text('No findings.\\n', encoding='utf-8')\n"
            ),
        )
        bundle_b = build_default_review_orchestration_bundle(
            repo_root=repo_b,
            review_id="default_review_runkey",
            scope_paths=["tools/loop/target.py"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/active_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
        )
        result_b = execute_review_orchestration_bundle(
            repo_root=repo_b,
            review_id="default_review_runkey",
            orchestration_bundle=bundle_b["orchestration_bundle"],
            instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
            required_context_refs=[
                "docs/agents/execplans/alt_plan.md",
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            ],
            prompt_root=repo_b / "artifacts" / "reviews",
            command_factory=lambda _stage, _prompt_path, _response_path: [sys.executable, str(helper_b)],
            env_factory=lambda stage: _runtime_env(stage),
        )
        if result_a["run_key"] == result_b["run_key"]:
            return _fail("review automation run identity must change when required_context_refs change")

        print("[loop-review-automation-runtime] OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
