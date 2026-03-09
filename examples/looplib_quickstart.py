"""Minimal standalone example for the in-repo looplib surface."""

from __future__ import annotations

from pathlib import Path

from looplib import (
    build_default_review_orchestration_bundle,
    materialize_batch_supervisor,
    publish_capability_event,
)


def main() -> None:
    repo_root = Path.cwd()
    publish_capability_event(
        repo_root=repo_root,
        publication_id="loop.quickstart.default_review_execution",
        producer_id="quickstart",
        summary="Default staged review execution is available.",
        resource_refs=["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
    )
    build_default_review_orchestration_bundle(
        repo_root=repo_root,
        review_id="quickstart_review",
        scope_paths=["tools/loop/review_orchestration.py"],
        instruction_scope_refs=["AGENTS.md"],
        required_context_refs=["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
    )
    materialize_batch_supervisor(
        repo_root=repo_root,
        batch_id="quickstart_batch",
        execplan_ref="docs/agents/execplans/20260308_loop_master_plan_completion_wave_v0.md",
        child_waves=[
            {
                "wave_id": "publish_default_review",
                "wave_kind": "CAPABILITY_PUBLISH",
                "resource_refs": ["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
                "summary": "Default staged review execution is available.",
            }
        ],
        instruction_scope_refs=["AGENTS.md"],
        required_context_refs=["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"],
    )


if __name__ == "__main__":
    main()
