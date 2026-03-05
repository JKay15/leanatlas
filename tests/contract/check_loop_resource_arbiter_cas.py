#!/usr/bin/env python3
"""Contract check: LOOP resource arbiter lease/CAS/journal semantics."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.resource_arbiter import LoopResourceArbiter, ResourceClass, ResourceConflict


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loop_arbiter_m3_") as td:
        repo = Path(td)
        run_key = "a" * 64
        arbiter = LoopResourceArbiter(repo_root=repo, run_key=run_key)

        resource_id = "toolbox/index.json"
        h0 = "0" * 64
        h1 = "1" * 64
        arbiter.seed_resource(resource_id=resource_id, resource_hash=h0)

        lease_a = arbiter.acquire_lease(
            resource_id=resource_id,
            resource_class=ResourceClass.MUTABLE_CONTROLLED,
            owner="agent.a",
            now_utc="2026-03-05T00:00:00Z",
            ttl_seconds=300,
            cas_base_hash=h0,
        )
        _assert(lease_a["status"] == "ACQUIRED", "lease should be ACQUIRED")

        try:
            arbiter.acquire_lease(
                resource_id=resource_id,
                resource_class=ResourceClass.MUTABLE_CONTROLLED,
                owner="agent.b",
                now_utc="2026-03-05T00:01:00Z",
                ttl_seconds=300,
                cas_base_hash=h0,
            )
        except ResourceConflict as err:
            _assert(err.error_code == "LEASE_CONFLICT", "expected LEASE_CONFLICT")
        else:
            raise AssertionError("second owner should not acquire an active lease")

        commit = arbiter.cas_commit(
            resource_id=resource_id,
            lease_id=lease_a["lease_id"],
            owner="agent.a",
            expected_old_hash=h0,
            new_hash=h1,
            reason="update index",
            evidence_refs=["artifacts/changeset_01.patch"],
            committed_at_utc="2026-03-05T00:02:00Z",
        )
        _assert(commit["new_hash"] == h1, "journaled commit should use new_hash")
        arbiter.release_lease(
            resource_id=resource_id,
            lease_id=lease_a["lease_id"],
            owner="agent.a",
            released_at_utc="2026-03-05T00:03:00Z",
        )

        lease_b = arbiter.acquire_lease(
            resource_id=resource_id,
            resource_class=ResourceClass.MUTABLE_CONTROLLED,
            owner="agent.b",
            now_utc="2026-03-05T00:04:00Z",
            ttl_seconds=300,
            cas_base_hash=h1,
        )
        _assert(lease_b["status"] == "ACQUIRED", "lease_b should be ACQUIRED")

        try:
            arbiter.cas_commit(
                resource_id=resource_id,
                lease_id=lease_b["lease_id"],
                owner="agent.b",
                expected_old_hash=h0,
                new_hash="2" * 64,
                reason="stale write",
                evidence_refs=["artifacts/changeset_02.patch"],
                committed_at_utc="2026-03-05T00:05:00Z",
            )
        except ResourceConflict as err:
            _assert(err.error_code == "CAS_CONFLICT", "expected CAS_CONFLICT")
        else:
            raise AssertionError("stale CAS must fail with CAS_CONFLICT")

        conflicts = arbiter.read_conflicts(resource_id)
        conflict_types = [c["conflict_type"] for c in conflicts]
        _assert(
            conflict_types == ["LEASE_CONFLICT", "CAS_CONFLICT"],
            "conflicts must be append-only and deterministic",
        )

        journal = arbiter.read_journal(resource_id)
        _assert(len(journal) == 1, "expected exactly one successful commit")
        _assert(journal[0]["old_hash"] == h0 and journal[0]["new_hash"] == h1, "journal hash chain mismatch")

    print("[loop-resource-arbiter-cas] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
