#!/usr/bin/env python3
"""Contract: canonical review prompting helpers preserve exhaustive protocol semantics."""

from __future__ import annotations

import hashlib
import json
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop import (
    BASELINE_REVIEW_PROMPT_PROTOCOL_ID,
    EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
    build_controlled_review_prompt_experiment,
    build_review_prompt,
    inspect_review_prompt_protocol,
)


def _fail(msg: str) -> int:
    print(f"[loop-review-prompting][FAIL] {msg}", file=sys.stderr)
    return 2


def main() -> int:
    if BASELINE_REVIEW_PROMPT_PROTOCOL_ID != "review.prompt.baseline.v1":
        return _fail("baseline protocol id must stay review.prompt.baseline.v1")
    if EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID != "review.prompt.exhaustive.v1":
        return _fail("exhaustive protocol id must stay review.prompt.exhaustive.v1")

    baseline_prompt = build_review_prompt(
        review_id="baseline_demo",
        prompt_protocol_id=BASELINE_REVIEW_PROMPT_PROTOCOL_ID,
        review_tier="FAST",
        agent_provider_id="codex_cli",
        agent_profile="low",
        scope_paths=["docs/contracts/alpha.md", "tools/loop/review_runner.py"],
        instruction_scope_refs=["AGENTS.md"],
        required_context_refs=["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
    )
    baseline_info = inspect_review_prompt_protocol(baseline_prompt)
    if baseline_info.get("protocol_id") != BASELINE_REVIEW_PROMPT_PROTOCOL_ID:
        return _fail("baseline prompt must round-trip the baseline protocol id")
    if baseline_info.get("is_canonical") is not True:
        return _fail("baseline prompt must still be canonical")
    if baseline_info.get("checksum_match") is not True:
        return _fail("baseline prompt must carry a matching canonical checksum marker")
    if baseline_info.get("is_exhaustive") is not False:
        return _fail("baseline prompt must not claim exhaustive behavior")
    if baseline_info.get("missing_sections") != []:
        return _fail("baseline prompt must not miss required baseline sections")
    if "## Coverage Axes" in baseline_prompt or "## Anti-Dribble Requirements" in baseline_prompt:
        return _fail("baseline prompt must not include exhaustive-only coverage sections")

    exhaustive_prompt = build_review_prompt(
        review_id="exhaustive_demo",
        prompt_protocol_id=EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID,
        review_tier="MEDIUM",
        agent_provider_id="codex_cli",
        agent_profile="medium",
        scope_paths=["docs/contracts/alpha.md", "tools/loop/review_runner.py"],
        instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
        required_context_refs=[
            "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            "artifacts/verify/verify_report.json",
        ],
    )
    exhaustive_info = inspect_review_prompt_protocol(exhaustive_prompt)
    if exhaustive_info.get("protocol_id") != EXHAUSTIVE_REVIEW_PROMPT_PROTOCOL_ID:
        return _fail("exhaustive prompt must round-trip the exhaustive protocol id")
    if exhaustive_info.get("is_canonical") is not True:
        return _fail("exhaustive prompt must be canonical")
    if exhaustive_info.get("checksum_match") is not True:
        return _fail("exhaustive prompt must carry a matching canonical checksum marker")
    if exhaustive_info.get("exact_prompt_match") is not True:
        return _fail("exhaustive prompt must round-trip to the exact canonical prompt body")
    if exhaustive_info.get("is_exhaustive") is not True:
        return _fail("exhaustive prompt must advertise exhaustive behavior")
    if exhaustive_info.get("missing_sections") != []:
        return _fail("exhaustive prompt must include every required exhaustive section")
    for section in (
        "## Coverage Axes",
        "## Anti-Dribble Requirements",
        "## Finalization Checklist",
    ):
        if section not in exhaustive_prompt:
            return _fail(f"exhaustive prompt must include `{section}`")
    crlf_exhaustive_prompt = exhaustive_prompt.replace("\n", "\r\n")
    crlf_info = inspect_review_prompt_protocol(crlf_exhaustive_prompt)
    if crlf_info.get("is_canonical") is not True:
        return _fail("canonical exhaustive prompt should remain canonical under CRLF line endings")
    if crlf_info.get("exact_prompt_match") is not True:
        return _fail("CRLF canonical prompt should satisfy normalized exact prompt matching")

    experiment = build_controlled_review_prompt_experiment(
        review_id="prompt_experiment_demo",
        review_tier="MEDIUM",
        agent_provider_id="codex_cli",
        agent_profile="medium",
        scope_paths=["docs/contracts/alpha.md", "tools/loop/review_runner.py"],
        instruction_scope_refs=["AGENTS.md", "tools/AGENTS.md"],
        required_context_refs=[
            "docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md",
            "artifacts/verify/verify_report.json",
        ],
    )
    if experiment.get("control_variable") != "PROMPT_PROTOCOL_ONLY":
        return _fail("controlled experiment must expose control_variable=PROMPT_PROTOCOL_ONLY")
    if experiment.get("delta_policy") != "PROMPT_PROTOCOL_ONLY":
        return _fail("controlled experiment delta policy must be PROMPT_PROTOCOL_ONLY")
    if not experiment.get("shared_context_fingerprint"):
        return _fail("controlled experiment must materialize a shared_context_fingerprint")
    variants = {str(item.get("variant_id")): dict(item) for item in experiment.get("variants") or []}
    if set(variants) != {"baseline", "exhaustive"}:
        return _fail("controlled experiment must emit baseline and exhaustive variants")
    baseline_variant = variants["baseline"]
    exhaustive_variant = variants["exhaustive"]
    for field_name in (
        "scope_paths",
        "instruction_scope_refs",
        "required_context_refs",
        "agent_provider_id",
        "agent_profile",
        "review_tier",
    ):
        if baseline_variant.get(field_name) != exhaustive_variant.get(field_name):
            return _fail(f"controlled experiment variants must match on `{field_name}`")
    if baseline_variant.get("prompt_protocol_id") == exhaustive_variant.get("prompt_protocol_id"):
        return _fail("controlled experiment variants must differ only by prompt protocol id/text")
    if baseline_variant.get("prompt_fingerprint") == exhaustive_variant.get("prompt_fingerprint"):
        return _fail("controlled experiment variants must have different prompt fingerprints")
    if baseline_variant.get("shared_context_fingerprint") != exhaustive_variant.get("shared_context_fingerprint"):
        return _fail("controlled experiment variants must share the same context fingerprint")

    tampered_prompt = exhaustive_prompt.replace(
        "- If one category looks clean, keep scanning the other categories before finalizing.",
        "- Stop after the first plausible issue.",
    )
    tampered_info = inspect_review_prompt_protocol(tampered_prompt)
    if tampered_info.get("is_canonical") is not False:
        return _fail("tampered prompts must fail canonical inspection")
    if tampered_info.get("checksum_match") is not False:
        return _fail("tampered prompts must fail the canonical checksum guard")
    spoofed_lines = tampered_prompt.splitlines()
    spoofed_body = "\n".join(spoofed_lines[2:])
    if tampered_prompt.endswith("\n"):
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
    spoofed_prompt = "\n".join(spoofed_lines) + "\n"
    spoofed_info = inspect_review_prompt_protocol(spoofed_prompt)
    if spoofed_info.get("is_canonical") is not False:
        return _fail("prompts that recompute their own checksum must still fail canonical inspection")
    if spoofed_info.get("exact_prompt_match") is not False:
        return _fail("self-checksummed spoof must fail exact prompt reconstruction")

    print("[loop-review-prompting] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
