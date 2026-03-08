#!/usr/bin/env python3
"""Contract check: maintainer reviewer runner must harden closeout execution."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.review_canonical import load_canonical_review_result
from tools.loop.review_prompting import EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID, build_review_prompt
from tools.loop.review_runner import compute_review_scope_fingerprint, run_review_closure

FIXTURES = ROOT / "tests" / "contract" / "fixtures" / "review_runner"


def _fail(msg: str) -> int:
    print(f"[loop-review-runner][FAIL] {msg}", file=sys.stderr)
    return 2


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loop_review_runner_") as td:
        repo = Path(td)
        agents = repo / "AGENTS.md"
        _write(agents, "# root instructions\n")
        tools_agents = repo / "tools" / "AGENTS.md"
        _write(tools_agents, "# tools instructions\n")
        tracked = repo / "tools" / "loop" / "target.py"
        _write(tracked, "VALUE = 1\n")
        contract = repo / "docs" / "contracts" / "LOOP_WAVE_EXECUTION_CONTRACT.md"
        _write(contract, "# contract\n")
        verify_report = repo / "artifacts" / "verify" / "verify_report.json"
        _write(verify_report, "{\"ok\": true}\n")
        base_kwargs = {
            "instruction_scope_refs": ["AGENTS.md", "tools/AGENTS.md"],
            "required_context_refs": [
                "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
                "artifacts/verify/verify_report.json",
            ],
        }

        prompt = repo / "artifacts" / "reviews" / "prompt.md"
        _write(prompt, "# review prompt\n")
        canonical_prompt = repo / "artifacts" / "reviews" / "canonical_prompt.md"
        _write(
            canonical_prompt,
            build_review_prompt(
                review_id="canonical_prompt_case",
                prompt_protocol_id=EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
                review_tier="MEDIUM",
                agent_provider_id="codex_cli",
                agent_profile="medium",
                scope_paths=["tools/loop/target.py"],
                instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
                required_context_refs=base_kwargs["required_context_refs"],
            ),
        )
        required_protocol_prompt = repo / "artifacts" / "reviews" / "required_protocol_prompt.md"
        _write(
            required_protocol_prompt,
            build_review_prompt(
                review_id="required_protocol_success_case",
                prompt_protocol_id=EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
                review_tier="MEDIUM",
                agent_provider_id="codex_cli",
                agent_profile="medium",
                scope_paths=["tools/loop/target.py"],
                instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
                required_context_refs=base_kwargs["required_context_refs"],
            ),
        )

        helper = repo / "helper.py"
        _write(
            helper,
            (
                "from __future__ import annotations\n"
                "import os, pathlib, sys, time\n"
                "mode = os.environ['REVIEW_TEST_MODE']\n"
                "attempt = int(os.environ.get('LEANATLAS_REVIEW_ATTEMPT_INDEX', '1'))\n"
                "response = pathlib.Path(os.environ['LEANATLAS_REVIEW_RESPONSE_PATH'])\n"
                "response.parent.mkdir(parents=True, exist_ok=True)\n"
                "if mode == 'success':\n"
                "    response.write_text('No findings.\\n', encoding='utf-8')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'missing_response':\n"
                "    raise SystemExit(0)\n"
                "if mode == 'retry_then_success':\n"
                "    if attempt == 1:\n"
                "        raise SystemExit(7)\n"
                "    response.write_text('Recovered and clean.\\n', encoding='utf-8')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'json_terminal_only':\n"
                "    print('{\"type\":\"review.completed\",\"message\":{\"role\":\"assistant\",\"content\":[{\"type\":\"output_text\",\"text\":\"No findings via events.\"}]}}')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'json_replay_fixture':\n"
                "    fixture = pathlib.Path(os.environ['REVIEW_FIXTURE_PATH'])\n"
                "    print(fixture.read_text(encoding='utf-8'), end='')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'json_no_terminal':\n"
                "    print('{\"type\":\"review.started\",\"message\":{\"role\":\"system\",\"content\":\"working\"}}')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'json_tool_final_message':\n"
                "    print('{\"type\":\"tool.completed\",\"final_message\":\"tool output is not a review closeout\"}')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'json_incomplete_assistant_progress':\n"
                "    print('{\"type\":\"review.progress\",\"status\":\"incomplete\",\"message\":{\"role\":\"assistant\",\"content\":[{\"type\":\"output_text\",\"text\":\"still working\"}]}}')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'json_non_assistant_terminal':\n"
                "    print('{\"type\":\"tool.completed\",\"message\":{\"role\":\"system\",\"content\":[{\"type\":\"output_text\",\"text\":\"tool output is not a review closeout\"}]}}')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'json_nested_item_terminal':\n"
                "    print('{\"type\":\"item.completed\",\"item\":{\"type\":\"assistant_message\",\"final_message\":\"No findings via nested item.\"}}')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'mutate_scope_then_success':\n"
                "    target = pathlib.Path(os.environ['REVIEW_SCOPE_TARGET'])\n"
                "    target.write_text('VALUE = 99\\n', encoding='utf-8')\n"
                "    response.write_text('Stale success should not pass.\\n', encoding='utf-8')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'mutate_restore_scope_then_success':\n"
                "    target = pathlib.Path(os.environ['REVIEW_SCOPE_TARGET'])\n"
                "    original = target.read_text(encoding='utf-8')\n"
                "    target.write_text('VALUE = 99\\n', encoding='utf-8')\n"
                "    time.sleep(0.05)\n"
                "    target.write_text(original, encoding='utf-8')\n"
                "    response.write_text('Restored but stale.\\n', encoding='utf-8')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'response_stream_then_success':\n"
                "    for idx in range(5):\n"
                "        with response.open('a', encoding='utf-8') as handle:\n"
                "            handle.write(f'chunk {idx}\\n')\n"
                "        time.sleep(0.3)\n"
                "    with response.open('a', encoding='utf-8') as handle:\n"
                "        handle.write('No findings.\\n')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'partial_response_then_timeout':\n"
                "    response.write_text('partial response\\n', encoding='utf-8')\n"
                "    time.sleep(300)\n"
                "    raise SystemExit(0)\n"
                "if mode == 'delete_scope_then_success':\n"
                "    target = pathlib.Path(os.environ['REVIEW_SCOPE_TARGET'])\n"
                "    target.unlink()\n"
                "    response.write_text('Deleted but stale.\\n', encoding='utf-8')\n"
                "    raise SystemExit(0)\n"
                "if mode == 'timeout':\n"
                "    time.sleep(300)\n"
                "    raise SystemExit(0)\n"
                "if mode == 'semantic_idle_noise':\n"
                "    deadline = time.time() + 300\n"
                "    while time.time() < deadline:\n"
                "        print('provider warning: retrying', file=sys.stderr, flush=True)\n"
                "        time.sleep(0.2)\n"
                "    raise SystemExit(0)\n"
                "raise SystemExit(9)\n"
            ),
        )
        # Case 1: empty scope is forbidden.
        try:
            run_review_closure(
                repo_root=repo,
                review_id="empty_scope",
                prompt_path=prompt,
                response_path=repo / "artifacts" / "reviews" / "empty_scope_response.md",
                scope_paths=[],
                command=[sys.executable, str(helper)],
                **base_kwargs,
            )
        except ValueError as exc:
            if "scope_paths" not in str(exc):
                return _fail("empty-scope rejection should mention scope_paths")
        else:
            return _fail("run_review_closure must reject empty scope_paths")

        # Case 2: missing instruction scope refs are forbidden.
        try:
            run_review_closure(
                repo_root=repo,
                review_id="missing_instruction_scope",
                prompt_path=prompt,
                response_path=repo / "artifacts" / "reviews" / "missing_instruction_scope_response.md",
                scope_paths=["tools/loop/target.py"],
                command=[sys.executable, str(helper)],
                required_context_refs=base_kwargs["required_context_refs"],
            )
        except ValueError as exc:
            if "instruction_scope_refs" not in str(exc):
                return _fail("missing instruction scope rejection should mention instruction_scope_refs")
        else:
            return _fail("run_review_closure must reject empty instruction_scope_refs")

        # Case 3: incomplete active instruction scope chain is forbidden.
        try:
            run_review_closure(
                repo_root=repo,
                review_id="missing_active_chain",
                prompt_path=prompt,
                response_path=repo / "artifacts" / "reviews" / "missing_active_chain_response.md",
                scope_paths=["tools/loop/target.py"],
                command=[sys.executable, str(helper)],
                instruction_scope_refs=["AGENTS.md"],
                required_context_refs=base_kwargs["required_context_refs"],
            )
        except ValueError as exc:
            if "active AGENTS.md chain" not in str(exc):
                return _fail("incomplete active chain rejection should mention active AGENTS.md chain")
        else:
            return _fail("run_review_closure must reject instruction_scope_refs that omit active chain entries")

        # Case 4: missing required context refs are forbidden.
        try:
            run_review_closure(
                repo_root=repo,
                review_id="missing_required_context",
                prompt_path=prompt,
                response_path=repo / "artifacts" / "reviews" / "missing_required_context_response.md",
                scope_paths=["tools/loop/target.py"],
                command=[sys.executable, str(helper)],
                instruction_scope_refs=base_kwargs["instruction_scope_refs"],
            )
        except ValueError as exc:
            if "required_context_refs" not in str(exc):
                return _fail("missing required context rejection should mention required_context_refs")
        else:
            return _fail("run_review_closure must reject empty required_context_refs")

        # Case 5: successful review produces a REVIEW_RUN closeout with scope and context evidence.
        success_response = repo / "artifacts" / "reviews" / "success_response.md"
        success = run_review_closure(
            repo_root=repo,
            review_id="success_case",
            prompt_path=prompt,
            response_path=success_response,
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "success"},
            **base_kwargs,
        )
        if success["review_closeout"]["mode"] != "REVIEW_RUN":
            return _fail("successful review must return REVIEW_RUN closeout")
        if success.get("result_state") != "SUCCEEDED":
            return _fail("successful review must report result_state=SUCCEEDED")
        if Path(success["review_closeout"]["response_ref"]).read_text(encoding="utf-8").strip() != "No findings.":
            return _fail("successful review response artifact must be non-empty and preserved")
        success_attempts = _read_jsonl(Path(success["attempts_ref"]))
        if len(success_attempts) != 1 or success_attempts[0].get("status") != "SUCCEEDED":
            return _fail("successful review should record one SUCCEEDED attempt")
        context_pack = Path(success["context_pack_ref"])
        if not context_pack.exists():
            return _fail("successful review must persist a context pack artifact")
        context_obj = json.loads(context_pack.read_text(encoding="utf-8"))
        if context_obj.get("instruction_scope_refs") != ["AGENTS.md", "tools/AGENTS.md"]:
            return _fail("context pack must preserve normalized instruction_scope_refs")
        if context_obj.get("required_context_refs") != sorted(base_kwargs["required_context_refs"]):
            return _fail("context pack must preserve normalized required_context_refs")
        observation_policy = context_obj.get("observation_policy") or {}
        if observation_policy.get("minimum_observation_window_s") != 600:
            return _fail("context pack must record codex_cli minimum_observation_window_s=600 by default")
        if observation_policy.get("timeout_s") != 3600:
            return _fail("context pack must record codex_cli default timeout_s=3600")
        if observation_policy.get("idle_timeout_s") != 600:
            return _fail("context pack must record codex_cli default idle_timeout_s=600")
        if observation_policy.get("semantic_idle_timeout_s") != 1200:
            return _fail("context pack must record codex_cli default semantic_idle_timeout_s=1200")
        if success.get("semantic_response_source") != "response_file":
            return _fail("response-backed success must record semantic_response_source=response_file")
        success_canonical = load_canonical_review_result(Path(success["canonical_result_ref"]))
        if success_canonical.get("status") != "SUCCEEDED":
            return _fail("successful review must materialize canonical status=SUCCEEDED")
        if success_canonical.get("semantic_response_source") != "response_file":
            return _fail("successful review canonical payload must preserve response_file source")
        if success_canonical.get("terminal") is not True:
            return _fail("successful review canonical payload must be terminal")

        # Case 5b: canonical exhaustive prompts may be required before provider launch.
        required_protocol_success = run_review_closure(
            repo_root=repo,
            review_id="required_protocol_success_case",
            prompt_path=required_protocol_prompt,
            response_path=repo / "artifacts" / "reviews" / "required_protocol_success_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "success"},
            required_prompt_protocol_id=EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
            **base_kwargs,
        )
        if required_protocol_success["review_closeout"]["mode"] != "REVIEW_RUN":
            return _fail("canonical exhaustive prompts must satisfy required_prompt_protocol_id enforcement")

        # Case 5c: canonical prompts must match the frozen run inputs exactly.
        mismatched_prompt = repo / "artifacts" / "reviews" / "mismatched_canonical_prompt.md"
        _write(
            mismatched_prompt,
            build_review_prompt(
                review_id="required_protocol_success_case",
                prompt_protocol_id=EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
                review_tier="MEDIUM",
                agent_provider_id="codex_cli",
                agent_profile="medium",
                scope_paths=["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
                instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
                required_context_refs=base_kwargs["required_context_refs"],
            ),
        )
        try:
            run_review_closure(
                repo_root=repo,
                review_id="required_protocol_success_case",
                prompt_path=mismatched_prompt,
                response_path=repo / "artifacts" / "reviews" / "required_protocol_mismatch_response.md",
                scope_paths=["tools/loop/target.py"],
                command=[sys.executable, str(helper)],
                env={"REVIEW_TEST_MODE": "success"},
                required_prompt_protocol_id=EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
                **base_kwargs,
            )
        except ValueError as exc:
            if "frozen inputs" not in str(exc):
                return _fail("canonical prompt/input mismatch rejection must mention frozen inputs")
        else:
            return _fail("run_review_closure must reject canonical prompts whose frozen inputs differ from the run")

        # Case 5d: generic prompts must be rejected when exhaustive protocol is required.
        try:
            run_review_closure(
                repo_root=repo,
                review_id="required_protocol_failure_case",
                prompt_path=prompt,
                response_path=repo / "artifacts" / "reviews" / "required_protocol_failure_response.md",
                scope_paths=["tools/loop/target.py"],
                command=[sys.executable, str(helper)],
                required_prompt_protocol_id=EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
                **base_kwargs,
            )
        except ValueError as exc:
            if "required_prompt_protocol_id" not in str(exc):
                return _fail("required prompt protocol rejection must mention required_prompt_protocol_id")
        else:
            return _fail("run_review_closure must reject non-canonical prompts when exhaustive protocol is required")

        # Case 5e: canonical-looking but tampered prompts must also be rejected.
        spoofed_prompt = repo / "artifacts" / "reviews" / "spoofed_prompt.md"
        spoofed_text = canonical_prompt.read_text(encoding="utf-8").replace(
            "- If one category looks clean, keep scanning the other categories before finalizing.",
            "- Stop after the first plausible issue.",
        )
        spoofed_lines = spoofed_text.splitlines()
        spoofed_body = "\n".join(spoofed_lines[2:])
        if spoofed_text.endswith("\n"):
            spoofed_body += "\n"
        spoofed_sha = hashlib.sha256(
            json.dumps(
                {
                    "protocol_id": EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
                    "body_text": spoofed_body,
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        spoofed_lines[1] = f"<!-- LOOP_REVIEW_PROMPT_SHA256: {spoofed_sha} -->"
        spoofed_text = "\n".join(spoofed_lines) + "\n"
        _write(spoofed_prompt, spoofed_text)
        try:
            run_review_closure(
                repo_root=repo,
                review_id="required_protocol_spoofed_case",
                prompt_path=spoofed_prompt,
                response_path=repo / "artifacts" / "reviews" / "required_protocol_spoofed_response.md",
                scope_paths=["tools/loop/target.py"],
                command=[sys.executable, str(helper)],
                required_prompt_protocol_id=EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
                **base_kwargs,
            )
        except ValueError as exc:
            if "required_prompt_protocol_id" not in str(exc):
                return _fail("tampered prompt rejection must mention required_prompt_protocol_id")
        else:
            return _fail("run_review_closure must reject tampered prompts when exhaustive protocol is required")

        # Case 5f: non-canonical prompts must not claim canonical protocol ids in persisted context.
        spoofed_success = run_review_closure(
            repo_root=repo,
            review_id="spoofed_success_case",
            prompt_path=spoofed_prompt,
            response_path=repo / "artifacts" / "reviews" / "spoofed_success_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "success"},
            instruction_scope_refs=base_kwargs["instruction_scope_refs"],
            required_context_refs=base_kwargs["required_context_refs"],
        )
        spoofed_context = json.loads(Path(spoofed_success["context_pack_ref"]).read_text(encoding="utf-8"))
        if spoofed_context.get("prompt_protocol_id") is not None:
            return _fail("non-canonical prompts must not persist canonical prompt_protocol_id in context packs")
        if spoofed_context.get("declared_prompt_protocol_id") != EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID:
            return _fail("context packs should preserve the declared prompt protocol id for tampered prompts")

        # Case 6: stale input fingerprint must block invocation before accepting a review.
        original_fingerprint = compute_review_scope_fingerprint(repo_root=repo, scope_paths=["tools/loop/target.py"])
        _write(tracked, "VALUE = 2\n")
        stale = run_review_closure(
            repo_root=repo,
            review_id="stale_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "stale_response.md",
            scope_paths=["tools/loop/target.py"],
            expected_scope_fingerprint=original_fingerprint,
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "success"},
            **base_kwargs,
        )
        if stale.get("reason_code") != "STALE_INPUT":
            return _fail("stale input must report reason_code=STALE_INPUT")
        if stale["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("stale input must not be accepted as REVIEW_RUN")
        stale_attempts = _read_jsonl(Path(stale["attempts_ref"]))
        if stale_attempts[0].get("status") != "STALE_INPUT":
            return _fail("stale input attempt must be recorded with status=STALE_INPUT")
        if stale_attempts[0].get("command_span") is not None:
            return _fail("stale input must be rejected before command execution")
        stale_canonical = load_canonical_review_result(Path(stale["canonical_result_ref"]))
        if stale_canonical.get("status") != "STALE_INPUT":
            return _fail("stale input must materialize canonical status=STALE_INPUT")

        # Case 7: scope mutations during execution must invalidate an otherwise non-empty response.
        _write(tracked, "VALUE = 3\n")
        stale_during_run = run_review_closure(
            repo_root=repo,
            review_id="stale_during_run_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "stale_during_run_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "mutate_scope_then_success", "REVIEW_SCOPE_TARGET": str(tracked)},
            **base_kwargs,
        )
        if stale_during_run["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("scope mutations during execution must not produce REVIEW_RUN")
        if stale_during_run.get("reason_code") != "STALE_INPUT":
            return _fail("scope mutations during execution must report STALE_INPUT")
        stale_during_attempts = _read_jsonl(Path(stale_during_run["attempts_ref"]))
        if stale_during_attempts[0].get("status") != "STALE_INPUT":
            return _fail("scope mutations during execution must record STALE_INPUT")
        _write(tracked, "VALUE = 4\n")

        # Case 8: scope mutations reverted before process exit must still invalidate the review.
        stale_restore = run_review_closure(
            repo_root=repo,
            review_id="stale_restore_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "stale_restore_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "mutate_restore_scope_then_success", "REVIEW_SCOPE_TARGET": str(tracked)},
            **base_kwargs,
        )
        if stale_restore["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("restored scope mutations must not produce REVIEW_RUN")
        if stale_restore.get("reason_code") != "STALE_INPUT":
            return _fail("restored scope mutations must report STALE_INPUT")
        stale_restore_canonical = load_canonical_review_result(Path(stale_restore["canonical_result_ref"]))
        if stale_restore_canonical.get("status") != "STALE_INPUT":
            return _fail("restored scope mutations must materialize canonical status=STALE_INPUT")

        # Case 9: deleting a scoped file during execution must still persist a stale review record.
        _write(tracked, "VALUE = 5\n")
        deleted_scope = run_review_closure(
            repo_root=repo,
            review_id="deleted_scope_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "deleted_scope_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "delete_scope_then_success", "REVIEW_SCOPE_TARGET": str(tracked)},
            **base_kwargs,
        )
        if deleted_scope["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("deleted scoped files must not produce REVIEW_RUN")
        if deleted_scope.get("reason_code") != "STALE_INPUT":
            return _fail("deleted scoped files must report STALE_INPUT")
        deleted_attempts = _read_jsonl(Path(deleted_scope["attempts_ref"]))
        if deleted_attempts[0].get("status") != "STALE_INPUT":
            return _fail("deleted scoped files must record a STALE_INPUT attempt")
        _write(tracked, "VALUE = 6\n")

        # Case 10: shorter-than-policy timeboxes must be rejected unless explicitly overridden.
        try:
            run_review_closure(
                repo_root=repo,
                review_id="short_timebox_policy_case",
                prompt_path=prompt,
                response_path=repo / "artifacts" / "reviews" / "short_timebox_policy_response.md",
                scope_paths=["tools/loop/target.py"],
                command=[sys.executable, str(helper)],
                env={"REVIEW_TEST_MODE": "success"},
                timeout_s=30,
                idle_timeout_s=30,
                semantic_idle_timeout_s=30,
                **base_kwargs,
            )
        except ValueError as exc:
            if "minimum observation policy" not in str(exc):
                return _fail("short timebox rejection should mention minimum observation policy")
        else:
            return _fail("run_review_closure must reject short provider timeboxes unless explicitly overridden")

        # Case 11: retry after non-zero exit should succeed within bounded attempts.
        retry = run_review_closure(
            repo_root=repo,
            review_id="retry_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "retry_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "retry_then_success"},
            max_attempts=2,
            **base_kwargs,
        )
        if retry["review_closeout"]["mode"] != "REVIEW_RUN":
            return _fail("retry_then_success must eventually return REVIEW_RUN")
        retry_attempts = _read_jsonl(Path(retry["attempts_ref"]))
        if [rec.get("status") for rec in retry_attempts] != ["COMMAND_FAILED", "SUCCEEDED"]:
            return _fail("retry_then_success must record failed first attempt then success")

        # Case 12: partial response bytes must not override timeout classification.
        partial_timeout = run_review_closure(
            repo_root=repo,
            review_id="partial_response_timeout_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "partial_response_timeout.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "partial_response_then_timeout"},
            max_attempts=1,
            timeout_s=1,
            idle_timeout_s=1,
            semantic_idle_timeout_s=1,
            allow_timebox_override=True,
            **base_kwargs,
        )
        if partial_timeout["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("partial response followed by timeout must not produce REVIEW_RUN")
        if partial_timeout.get("reason_code") != "REVIEW_TIMEOUT":
            return _fail("partial response followed by timeout must report REVIEW_TIMEOUT")
        partial_attempts = _read_jsonl(Path(partial_timeout["attempts_ref"]))
        if partial_attempts[0].get("status") != "REVIEW_TIMEOUT":
            return _fail("partial response followed by timeout must record REVIEW_TIMEOUT")

        # Case 13: terminal JSON events may synthesize the canonical response artifact.
        event_only = run_review_closure(
            repo_root=repo,
            review_id="json_terminal_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "json_terminal_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "json_terminal_only"},
            **base_kwargs,
        )
        if event_only["review_closeout"]["mode"] != "REVIEW_RUN":
            return _fail("terminal JSON event should produce REVIEW_RUN")
        if Path(event_only["response_ref"]).read_text(encoding="utf-8").strip() != "No findings via events.":
            return _fail("terminal JSON event should synthesize the canonical response file")
        if event_only.get("semantic_response_source") != "provider_event_jsonl":
            return _fail("terminal JSON event success must record semantic_response_source=provider_event_jsonl")
        event_only_canonical = load_canonical_review_result(Path(event_only["canonical_result_ref"]))
        if event_only_canonical.get("extraction_kind") != "event.message.assistant":
            return _fail("terminal JSON event must record canonical extraction_kind=event.message.assistant")

        # Case 14: replaying the real agent_message trace must synthesize the canonical response artifact.
        replay_event = run_review_closure(
            repo_root=repo,
            review_id="json_replay_fixture_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "json_replay_fixture_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={
                "REVIEW_TEST_MODE": "json_replay_fixture",
                "REVIEW_FIXTURE_PATH": str(FIXTURES / "codex_round2_agent_message.stdout.jsonl"),
            },
            **base_kwargs,
        )
        if replay_event["review_closeout"]["mode"] != "REVIEW_RUN":
            return _fail("real agent_message replay must produce REVIEW_RUN")
        replay_text = Path(replay_event["response_ref"]).read_text(encoding="utf-8").strip()
        if "The patch closes some first-pass cases" not in replay_text:
            return _fail("real agent_message replay must synthesize the captured review message")
        replay_canonical = load_canonical_review_result(Path(replay_event["canonical_result_ref"]))
        if replay_canonical.get("extraction_kind") != "event.item.agent_message":
            return _fail("real agent_message replay must record extraction_kind=event.item.agent_message")

        # Case 15: top-level non-assistant final_message must not synthesize canonical responses.
        tool_final_message = run_review_closure(
            repo_root=repo,
            review_id="json_tool_final_message_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "json_tool_final_message_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "json_tool_final_message"},
            **base_kwargs,
        )
        if tool_final_message["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("top-level tool final_message must not produce REVIEW_RUN")
        if tool_final_message.get("reason_code") != "NO_TERMINAL_EVENT":
            return _fail("top-level tool final_message must report NO_TERMINAL_EVENT")

        # Case 16: non-assistant terminal-looking events must not synthesize canonical responses.
        non_assistant_event = run_review_closure(
            repo_root=repo,
            review_id="json_non_assistant_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "json_non_assistant_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "json_non_assistant_terminal"},
            **base_kwargs,
        )
        if non_assistant_event["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("non-assistant events must not produce REVIEW_RUN")
        if non_assistant_event.get("reason_code") != "NO_TERMINAL_EVENT":
            return _fail("non-assistant events must report NO_TERMINAL_EVENT")

        # Case 17: assistant progress with status=incomplete must not be treated as terminal.
        incomplete_event = run_review_closure(
            repo_root=repo,
            review_id="json_incomplete_assistant_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "json_incomplete_assistant_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "json_incomplete_assistant_progress"},
            **base_kwargs,
        )
        if incomplete_event["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("assistant progress with status=incomplete must not produce REVIEW_RUN")
        if incomplete_event.get("reason_code") != "NO_TERMINAL_EVENT":
            return _fail("assistant progress with status=incomplete must report NO_TERMINAL_EVENT")

        # Case 18: nested terminal event payloads may synthesize the canonical response artifact.
        nested_event = run_review_closure(
            repo_root=repo,
            review_id="json_nested_item_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "json_nested_item_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "json_nested_item_terminal"},
            **base_kwargs,
        )
        if nested_event["review_closeout"]["mode"] != "REVIEW_RUN":
            return _fail("nested terminal event should produce REVIEW_RUN")
        if Path(nested_event["response_ref"]).read_text(encoding="utf-8").strip() != "No findings via nested item.":
            return _fail("nested terminal event should synthesize the canonical response file")
        nested_canonical = load_canonical_review_result(Path(nested_event["canonical_result_ref"]))
        if nested_canonical.get("extraction_kind") != "event.item.assistant_message":
            return _fail("nested terminal event must record extraction_kind=event.item.assistant_message")

        # Case 19: missing response artifact and no terminal JSON event must end in tooling triage.
        missing = run_review_closure(
            repo_root=repo,
            review_id="missing_response_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "missing_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "missing_response"},
            max_attempts=1,
            **base_kwargs,
        )
        if missing["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("missing response artifact must not produce REVIEW_RUN")
        if missing["review_closeout"].get("skip_reason_code") != "TRIAGED_TOOLING":
            return _fail("missing response artifact must triage as TRIAGED_TOOLING")
        missing_attempts = _read_jsonl(Path(missing["attempts_ref"]))
        if missing_attempts[0].get("status") != "NO_TERMINAL_EVENT":
            return _fail("missing response artifact without terminal event must be recorded as NO_TERMINAL_EVENT")

        # Case 20: non-terminal JSON output must still triage as no semantic completion.
        no_terminal = run_review_closure(
            repo_root=repo,
            review_id="json_no_terminal_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "json_no_terminal_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "json_no_terminal"},
            **base_kwargs,
        )
        if no_terminal["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("non-terminal JSON output must not produce REVIEW_RUN")
        if no_terminal.get("reason_code") != "NO_TERMINAL_EVENT":
            return _fail("non-terminal JSON output must report NO_TERMINAL_EVENT")

        # Case 21: response-file semantic progress must also prevent transport idle expiry.
        response_growth_with_idle = run_review_closure(
            repo_root=repo,
            review_id="response_growth_transport_idle_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "response_growth_transport_idle_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "response_stream_then_success"},
            max_attempts=1,
            timeout_s=30,
            idle_timeout_s=1,
            semantic_idle_timeout_s=5,
            allow_timebox_override=True,
            **base_kwargs,
        )
        if response_growth_with_idle["review_closeout"]["mode"] != "REVIEW_RUN":
            return _fail("response-file semantic progress must keep transport idle from killing the review")
        if response_growth_with_idle.get("reason_code") != "OK":
            return _fail("response-file semantic progress should still finish with reason_code=OK")

        # Case 22: semantic-only timeout mode must honor semantic progress without transport idle.
        semantic_only = run_review_closure(
            repo_root=repo,
            review_id="semantic_only_progress_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "semantic_only_progress_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "response_stream_then_success"},
            max_attempts=1,
            timeout_s=30,
            idle_timeout_s=0,
            semantic_idle_timeout_s=1,
            allow_timebox_override=True,
            **base_kwargs,
        )
        if semantic_only["review_closeout"]["mode"] != "REVIEW_RUN":
            return _fail("semantic-only timeout mode must still accept growing semantic progress")
        if semantic_only.get("reason_code") != "OK":
            return _fail("semantic-only timeout mode should finish with reason_code=OK")

        # Case 23: semantic-idle noise must triage even if stderr keeps changing.
        semantic_idle = run_review_closure(
            repo_root=repo,
            review_id="semantic_idle_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "semantic_idle_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "semantic_idle_noise"},
            max_attempts=1,
            timeout_s=30,
            idle_timeout_s=30,
            semantic_idle_timeout_s=1,
            allow_timebox_override=True,
            **base_kwargs,
        )
        if semantic_idle["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("semantic-idle noise must not produce REVIEW_RUN")
        if semantic_idle["review_closeout"].get("skip_reason_code") != "TRIAGED_TOOLING":
            return _fail("semantic-idle noise must triage as TRIAGED_TOOLING")
        if semantic_idle.get("reason_code") != "SEMANTIC_IDLE_TIMEOUT":
            return _fail("semantic-idle noise must report SEMANTIC_IDLE_TIMEOUT")
        semantic_idle_attempts = _read_jsonl(Path(semantic_idle["attempts_ref"]))
        semantic_span = semantic_idle_attempts[0].get("command_span") or {}
        if semantic_idle_attempts[0].get("status") != "SEMANTIC_IDLE_TIMEOUT":
            return _fail("semantic-idle noise attempt must be recorded as SEMANTIC_IDLE_TIMEOUT")
        if semantic_span.get("timed_out") is not True or int(semantic_span.get("exit_code", -1)) != 124:
            return _fail("semantic-idle timeout must persist timed_out=true and exit_code=124 evidence")

        # Case 24: timeout must be bounded and persist timeout evidence.
        timed = run_review_closure(
            repo_root=repo,
            review_id="timeout_case",
            prompt_path=prompt,
            response_path=repo / "artifacts" / "reviews" / "timeout_response.md",
            scope_paths=["tools/loop/target.py"],
            command=[sys.executable, str(helper)],
            env={"REVIEW_TEST_MODE": "timeout"},
            max_attempts=1,
            timeout_s=1,
            idle_timeout_s=1,
            allow_timebox_override=True,
            **base_kwargs,
        )
        if timed["review_closeout"]["mode"] != "REVIEW_SKIPPED":
            return _fail("timeout must not produce REVIEW_RUN")
        if timed["review_closeout"].get("skip_reason_code") != "TRIAGED_TOOLING":
            return _fail("timeout must triage as TRIAGED_TOOLING")
        timeout_attempts = _read_jsonl(Path(timed["attempts_ref"]))
        span = timeout_attempts[0].get("command_span") or {}
        if timeout_attempts[0].get("status") != "REVIEW_TIMEOUT":
            return _fail("timeout attempt must be recorded as REVIEW_TIMEOUT")
        if span.get("timed_out") is not True or int(span.get("exit_code", -1)) != 124:
            return _fail("timeout attempt must persist timed_out=true and exit_code=124 evidence")

    print("[loop-review-runner] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
