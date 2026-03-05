#!/usr/bin/env python3
"""LOOP runtime (Wave-B M2 minimal).

This runtime focuses on deterministic execution/review transitions plus
append-only checkpointing for resume.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import ExecutionState, require_execution_transition
from .store import LoopStore


@dataclass(frozen=True)
class RuntimeBudgets:
    max_ai_review_rounds: int = 8
    max_same_fingerprint_rounds: int = 2
    max_wave_wall_clock_minutes: int = 120


class LoopRuntime:
    """Deterministic single-node runtime with append-only evidence + resume."""

    def __init__(self, *, repo_root: Path, run_key: str, state: dict[str, Any]) -> None:
        self.store = LoopStore(repo_root=repo_root, run_key=run_key)
        self.store.ensure_layout()
        self.state = state

    @staticmethod
    def _checkpoint_rel() -> str:
        return "state/checkpoints.jsonl"

    @staticmethod
    def _transitions_rel() -> str:
        return "wave_execution/transitions.jsonl"

    @staticmethod
    def _iterations_rel() -> str:
        return "wave_execution/iterations.jsonl"

    @classmethod
    def start(
        cls,
        *,
        repo_root: Path,
        run_key: str,
        wave_id: str,
        budgets: RuntimeBudgets | None = None,
    ) -> "LoopRuntime":
        b = budgets or RuntimeBudgets()
        store = LoopStore(repo_root=repo_root, run_key=run_key)
        store.ensure_layout()

        cp = store.cache_path(cls._checkpoint_rel())
        if cp.exists():
            raise FileExistsError(f"runtime already initialized for run_key={run_key}")

        state = {
            "version": "1",
            "run_key": run_key,
            "wave_id": wave_id,
            "current_state": ExecutionState.RUNNING.value,
            "used_ai_review_rounds": 0,
            "used_wall_clock_minutes": 0,
            "max_ai_review_rounds": b.max_ai_review_rounds,
            "max_same_fingerprint_rounds": b.max_same_fingerprint_rounds,
            "max_wave_wall_clock_minutes": b.max_wave_wall_clock_minutes,
            "last_finding_fingerprint": None,
            "consecutive_same_fingerprint": 0,
        }

        rt = cls(repo_root=repo_root, run_key=run_key, state=state)
        rt._append_transition(
            {
                "from": ExecutionState.PENDING.value,
                "to": ExecutionState.RUNNING.value,
                "reason_code": "WAVE_START",
                "at_utc": "1970-01-01T00:00:00Z",
            }
        )
        rt._append_checkpoint()
        return rt

    @classmethod
    def resume(cls, *, repo_root: Path, run_key: str) -> "LoopRuntime":
        store = LoopStore(repo_root=repo_root, run_key=run_key)
        cp = store.cache_path(cls._checkpoint_rel())
        if not cp.exists():
            raise FileNotFoundError(f"checkpoint log missing for run_key={run_key}")
        lines = [ln for ln in cp.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not lines:
            raise RuntimeError(f"empty checkpoint log for run_key={run_key}")
        state = json.loads(lines[-1])
        return cls(repo_root=repo_root, run_key=run_key, state=state)

    def submit_for_review(self, *, at_utc: str) -> None:
        cur = ExecutionState(self.state["current_state"])
        require_execution_transition(cur, ExecutionState.AI_REVIEW)
        self.state["current_state"] = ExecutionState.AI_REVIEW.value
        self._append_transition(
            {
                "from": cur.value,
                "to": ExecutionState.AI_REVIEW.value,
                "reason_code": "IMPLEMENTATION_SUBMITTED_FOR_REVIEW",
                "at_utc": at_utc,
            }
        )
        self._append_checkpoint()

    def apply_review(
        self,
        *,
        verdict: str,
        finding_fingerprint: str,
        wall_clock_used_minutes: int,
        at_utc: str,
    ) -> tuple[str, str]:
        cur = ExecutionState(self.state["current_state"])
        if cur != ExecutionState.AI_REVIEW:
            raise ValueError(f"apply_review requires AI_REVIEW state; got {cur.value}")

        used = int(self.state["used_ai_review_rounds"]) + 1
        max_rounds = int(self.state["max_ai_review_rounds"])
        max_same = int(self.state["max_same_fingerprint_rounds"])
        max_wall = int(self.state["max_wave_wall_clock_minutes"])

        if self.state.get("last_finding_fingerprint") == finding_fingerprint:
            consecutive = int(self.state["consecutive_same_fingerprint"]) + 1
        else:
            consecutive = 1

        to_state, reason = self._transition_from_review(
            verdict=verdict,
            used_rounds=used,
            max_rounds=max_rounds,
            repeated_fingerprint_count=consecutive,
            max_same_fingerprint_rounds=max_same,
            wall_clock_used_minutes=wall_clock_used_minutes,
            wall_clock_max_minutes=max_wall,
        )

        record = {
            "iteration_index": used,
            "verdict": verdict,
            "finding_fingerprint": finding_fingerprint,
            "wall_clock_used_minutes": wall_clock_used_minutes,
            "transition": {
                "from": ExecutionState.AI_REVIEW.value,
                "to": to_state,
                "reason_code": reason,
                "at_utc": at_utc,
            },
        }
        self._append_iteration(record)

        self._append_transition(record["transition"])
        self.state["current_state"] = to_state
        self.state["used_ai_review_rounds"] = used
        self.state["used_wall_clock_minutes"] = wall_clock_used_minutes
        self.state["last_finding_fingerprint"] = finding_fingerprint
        self.state["consecutive_same_fingerprint"] = consecutive
        self._append_checkpoint()
        return (to_state, reason)

    @staticmethod
    def _transition_from_review(
        *,
        verdict: str,
        used_rounds: int,
        max_rounds: int,
        repeated_fingerprint_count: int,
        max_same_fingerprint_rounds: int,
        wall_clock_used_minutes: int,
        wall_clock_max_minutes: int,
    ) -> tuple[str, str]:
        if repeated_fingerprint_count >= max_same_fingerprint_rounds:
            return (ExecutionState.TRIAGED.value, "REVIEW_STAGNATION")
        if verdict == "NON_RETRYABLE":
            return (ExecutionState.FAILED.value, "REVIEW_NON_RETRYABLE_FAULT")
        if verdict == "UNRESOLVED_BLOCKER":
            return (ExecutionState.TRIAGED.value, "REVIEW_UNRESOLVED_BLOCKER")
        if wall_clock_used_minutes >= wall_clock_max_minutes:
            return (ExecutionState.TRIAGED.value, "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED")
        if verdict == "REPAIRABLE":
            if used_rounds < max_rounds:
                return (ExecutionState.RUNNING.value, "REVIEW_REPAIR_LOOP")
            return (ExecutionState.TRIAGED.value, "REVIEW_BUDGET_EXHAUSTED")
        if verdict == "PASS":
            return (ExecutionState.PASSED.value, "REVIEW_PASS")
        return (ExecutionState.FAILED.value, "REVIEW_INVALID_VERDICT")

    def _append_checkpoint(self) -> None:
        self.store.append_jsonl(self._checkpoint_rel(), self.state, stream="cache")

    def _append_transition(self, obj: dict[str, Any]) -> None:
        self.store.append_jsonl(self._transitions_rel(), obj, stream="artifact")

    def _append_iteration(self, obj: dict[str, Any]) -> None:
        self.store.append_jsonl(self._iterations_rel(), obj, stream="artifact")

    def read_transitions(self) -> list[dict[str, Any]]:
        p = self.store.artifact_path(self._transitions_rel())
        if not p.exists():
            return []
        return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def read_iterations(self) -> list[dict[str, Any]]:
        p = self.store.artifact_path(self._iterations_rel())
        if not p.exists():
            return []
        return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
