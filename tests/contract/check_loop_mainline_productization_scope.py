#!/usr/bin/env python3
"""Guardrail: LOOP mainline productization must stay LOOP-first, not a generic docs sweep."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def main() -> int:
    master_rel = "docs/agents/execplans/20260307_loop_core_parallel_nested_batch_v0.md"
    child_rel = "docs/agents/execplans/20260307_loop_mainline_productization_integration_v0.md"

    master = _read(master_rel)
    child = _read(child_rel)

    _assert(
        "LOOP mainline productization is the primary subject of that wave" in master,
        f"{master_rel} must explicitly say LOOP mainline productization is the primary subject of the wave",
    )
    _assert(
        "LeanAtlas project-level integration is supporting work" in master,
        f"{master_rel} must describe project-level integration as supporting work rather than the primary subject",
    )
    _assert(
        "not a generic whole-project documentation sweep" in master,
        f"{master_rel} must reject interpreting the wave as a generic whole-project documentation sweep",
    )
    _assert(
        ".cache/leanatlas/tmp/**" in master and "must be classified, not wholesale copied into mainline" in master,
        f"{master_rel} must classify experimental assets instead of implying a wholesale copy into mainline",
    )

    _assert(
        any(token in child for token in ("status: planned", "status: active", "status: done")),
        f"{child_rel} must carry an explicit status while remaining the authoritative child ExecPlan for the wave",
    )
    _assert(
        "LOOP mainline productization" in child and "project-level integration" in child,
        f"{child_rel} must scope both LOOP productization and project-level integration explicitly",
    )
    _assert(
        "LOOP is the primary subject" in child,
        f"{child_rel} must explicitly state that LOOP is the primary subject of the wave",
    )
    _assert(
        "project-level integration updates are supporting work" in child,
        f"{child_rel} must constrain project-level integration to support LOOP mainline adoption",
    )

    print("[loop-mainline-productization-scope] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
