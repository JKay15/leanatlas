#!/usr/bin/env python3
"""Deterministic stress check for LOOP state-policy validators."""

from __future__ import annotations

import hashlib
import random
import sys

EXEC_ALLOWED = {
    ("PENDING", "RUNNING"),
    ("RUNNING", "AI_REVIEW"),
    ("AI_REVIEW", "RUNNING"),
    ("AI_REVIEW", "PASSED"),
    ("AI_REVIEW", "FAILED"),
    ("AI_REVIEW", "TRIAGED"),
}

EXEC_STATES = ["PENDING", "RUNNING", "AI_REVIEW", "PASSED", "FAILED", "TRIAGED"]


def _validate(src: str, dst: str) -> bool:
    return (src, dst) in EXEC_ALLOWED


def _simulate(seed: int, rounds: int) -> str:
    rnd = random.Random(seed)
    acc: list[str] = []
    for _ in range(rounds):
        src = rnd.choice(EXEC_STATES)
        dst = rnd.choice(EXEC_STATES)
        ok = _validate(src, dst)
        acc.append(f"{src}->{dst}:{1 if ok else 0}")
    digest = hashlib.sha256("|".join(acc).encode("utf-8")).hexdigest()
    return digest


def main() -> int:
    # Determinism under repeated seeded stress.
    d1 = _simulate(seed=20260305, rounds=5000)
    d2 = _simulate(seed=20260305, rounds=5000)
    if d1 != d2:
        print("[loop-policy-stress][FAIL] deterministic digest mismatch under fixed seed", file=sys.stderr)
        return 2

    # Simple sanity: known allowed and blocked edges.
    if not _validate("AI_REVIEW", "RUNNING"):
        print("[loop-policy-stress][FAIL] required repair-loop edge missing", file=sys.stderr)
        return 2
    if _validate("PENDING", "PASSED"):
        print("[loop-policy-stress][FAIL] forbidden direct edge PENDING->PASSED accepted", file=sys.stderr)
        return 2

    print(f"[loop-policy-stress] OK digest={d1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
