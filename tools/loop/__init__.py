"""LOOP runtime package (Wave-B M1 minimal surface)."""

from .assurance import AssuranceLevel, evaluate_wave_completion_gate, normalize_assurance_level
from .dirty_tree_gate import collect_dirty_tree_snapshot, run_dirty_tree_gate, validate_dirty_tree_snapshot
from .errors import LoopErrorEnvelope, LoopException
from .graph_runtime import DynamicEntryViolation, LoopGraphRuntime
from .model import EXEC_ALLOWED, ExecutionState, require_execution_transition, validate_execution_trace
from .review_history import summarize_review_history
from .resource_arbiter import LoopResourceArbiter, ResourceClass, ResourceConflict
from .run_key import RunKeyInput, compute_run_key
from .runtime import LoopRuntime, RuntimeBudgets
from .sdk import loop, nested, parallel, resume, run, serial
from .store import LoopStore
from .wave_gate import assert_wave_execution_report, validate_wave_execution_report

__all__ = [
    "DynamicEntryViolation",
    "EXEC_ALLOWED",
    "ExecutionState",
    "AssuranceLevel",
    "LoopErrorEnvelope",
    "LoopException",
    "LoopGraphRuntime",
    "LoopResourceArbiter",
    "LoopStore",
    "LoopRuntime",
    "ResourceClass",
    "ResourceConflict",
    "RunKeyInput",
    "RuntimeBudgets",
    "compute_run_key",
    "collect_dirty_tree_snapshot",
    "evaluate_wave_completion_gate",
    "loop",
    "nested",
    "normalize_assurance_level",
    "parallel",
    "resume",
    "run",
    "require_execution_transition",
    "serial",
    "summarize_review_history",
    "run_dirty_tree_gate",
    "assert_wave_execution_report",
    "validate_wave_execution_report",
    "validate_dirty_tree_snapshot",
    "validate_execution_trace",
]
