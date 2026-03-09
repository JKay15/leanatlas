"""Role-neutral in-repo import surface for the reusable LOOP library."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "assert_review_reconciliation_ready": (".review", "assert_review_reconciliation_ready"),
    "BatchWaveRetryableError": (".session", "BatchWaveRetryableError"),
    "build_default_review_orchestration_bundle": (".review", "build_default_review_orchestration_bundle"),
    "build_default_review_policy": (".preferences", "build_default_review_policy"),
    "build_default_tiered_review_policy": (".review", "build_default_tiered_review_policy"),
    "build_pyramid_review_plan": (".review", "build_pyramid_review_plan"),
    "build_review_orchestration_bundle": (".review", "build_review_orchestration_bundle"),
    "build_review_orchestration_graph": (".review", "build_review_orchestration_graph"),
    "ensure_preference_record": (".session", "ensure_preference_record"),
    "execute_batch_supervisor": (".session", "execute_batch_supervisor"),
    "execute_review_orchestration_bundle": (".review", "execute_review_orchestration_bundle"),
    "issue_root_supervisor_exception": (".session", "issue_root_supervisor_exception"),
    "load_batch_supervisor": (".session", "load_batch_supervisor"),
    "LoopGraphRuntime": (".runtime", "LoopGraphRuntime"),
    "LoopResourceArbiter": (".runtime", "LoopResourceArbiter"),
    "LoopRuntime": (".runtime", "LoopRuntime"),
    "MaintainerLoopSession": (".session", "MaintainerLoopSession"),
    "materialize_batch_supervisor": (".session", "materialize_batch_supervisor"),
    "persist_review_reconciliation": (".review", "persist_review_reconciliation"),
    "publish_capability_event": (".session", "publish_capability_event"),
    "publish_supervisor_guidance_event": (".session", "publish_supervisor_guidance_event"),
    "record_human_external_input": (".session", "record_human_external_input"),
    "reconcile_review_rounds": (".review", "reconcile_review_rounds"),
    "rematerialize_context_pack": (".session", "rematerialize_context_pack"),
    "ResourceClass": (".runtime", "ResourceClass"),
    "ResourceConflict": (".runtime", "ResourceConflict"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))


__all__ = sorted(_EXPORTS)
