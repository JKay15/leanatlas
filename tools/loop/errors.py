#!/usr/bin/env python3
"""Typed LOOP runtime/SDK errors with schema-aligned envelope fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ERROR_CLASSES = {
    "RETRYABLE_USER",
    "RETRYABLE_SYSTEM",
    "NON_RETRYABLE_CONTRACT",
    "NON_RETRYABLE_INFRA",
}


@dataclass(frozen=True)
class LoopErrorEnvelope:
    error_code: str
    error_class: str
    retryable: bool
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "error_code": self.error_code,
            "error_class": self.error_class,
            "retryable": self.retryable,
        }
        if self.message:
            out["message"] = self.message
        return out


class LoopException(RuntimeError):
    """Base typed exception for LOOP subsystems."""

    def __init__(
        self,
        *,
        error_code: str,
        error_class: str,
        retryable: bool,
        message: str | None = None,
        trace_refs: list[str] | None = None,
    ) -> None:
        if error_class not in ERROR_CLASSES:
            raise ValueError(f"unsupported error_class: {error_class}")
        super().__init__(message or error_code)
        self.error_code = error_code
        self.error_class = error_class
        self.retryable = retryable
        self.message = message
        self.trace_refs = list(trace_refs or [])

    def to_envelope(self) -> LoopErrorEnvelope:
        return LoopErrorEnvelope(
            error_code=self.error_code,
            error_class=self.error_class,
            retryable=self.retryable,
            message=self.message,
        )

    def to_response_error(self) -> dict[str, Any]:
        return self.to_envelope().to_dict()


def normalize_exception(exc: Exception) -> LoopException:
    """Map untyped exceptions into a deterministic LOOP error envelope."""

    if isinstance(exc, LoopException):
        return exc
    if isinstance(exc, FileNotFoundError):
        return LoopException(
            error_code="CHECKPOINT_NOT_FOUND",
            error_class="NON_RETRYABLE_CONTRACT",
            retryable=False,
            message=str(exc),
        )
    if isinstance(exc, ValueError):
        return LoopException(
            error_code="CONTRACT_VIOLATION",
            error_class="NON_RETRYABLE_CONTRACT",
            retryable=False,
            message=str(exc),
        )
    return LoopException(
        error_code="UNEXPECTED_RUNTIME_ERROR",
        error_class="NON_RETRYABLE_INFRA",
        retryable=False,
        message=str(exc),
    )
