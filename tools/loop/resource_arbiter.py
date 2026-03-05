#!/usr/bin/env python3
"""Deterministic LOOP resource arbitration with lease/CAS/journal semantics."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .errors import LoopException
from .store import LoopStore


class ResourceClass(str, Enum):
    IMMUTABLE = "IMMUTABLE"
    APPEND_ONLY = "APPEND_ONLY"
    MUTABLE_CONTROLLED = "MUTABLE_CONTROLLED"


class ResourceConflict(LoopException):
    def __init__(self, *, error_code: str, message: str, trace_refs: list[str] | None = None) -> None:
        super().__init__(
            error_code=error_code,
            error_class="RETRYABLE_SYSTEM",
            retryable=True,
            message=message,
            trace_refs=trace_refs,
        )


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _parse_utc(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def _format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class LoopResourceArbiter:
    """Lease/CAS gate for MUTABLE_CONTROLLED resources."""

    def __init__(self, *, repo_root: Path, run_key: str) -> None:
        self.store = LoopStore(repo_root=repo_root, run_key=run_key)
        self.store.ensure_layout()

    @staticmethod
    def _token(resource_id: str) -> str:
        return hashlib.sha256(resource_id.encode("utf-8")).hexdigest()[:20]

    def _state_path(self, resource_id: str) -> Path:
        return self.store.cache_path(f"resources/state/{self._token(resource_id)}.json")

    def _lease_path(self, resource_id: str) -> Path:
        return self.store.cache_path(f"resources/leases/{self._token(resource_id)}.json")

    def _journal_rel(self, resource_id: str) -> str:
        return f"resources/journal/{self._token(resource_id)}.jsonl"

    def _conflict_rel(self, resource_id: str) -> str:
        return f"resources/conflicts/{self._token(resource_id)}.jsonl"

    def seed_resource(self, *, resource_id: str, resource_hash: str) -> None:
        if len(resource_hash) != 64:
            raise ValueError("resource_hash must be 64-char hex")
        path = self._state_path(resource_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _canonical_json(
                {
                    "version": "1",
                    "resource_id": resource_id,
                    "resource_hash": resource_hash,
                }
            ),
            encoding="utf-8",
        )

    def read_resource_hash(self, resource_id: str) -> str:
        p = self._state_path(resource_id)
        if not p.exists():
            raise FileNotFoundError(f"resource state missing: {resource_id}")
        return str(_load_json(p)["resource_hash"])

    def acquire_lease(
        self,
        *,
        resource_id: str,
        resource_class: ResourceClass,
        owner: str,
        now_utc: str,
        ttl_seconds: int,
        cas_base_hash: str,
    ) -> dict[str, Any]:
        if resource_class != ResourceClass.MUTABLE_CONTROLLED:
            raise ValueError("lease/CAS flow is required only for MUTABLE_CONTROLLED resources")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")

        state_hash = self.read_resource_hash(resource_id)
        lease_path = self._lease_path(resource_id)
        lease_path.parent.mkdir(parents=True, exist_ok=True)
        now_dt = _parse_utc(now_utc)

        if lease_path.exists():
            active = _load_json(lease_path)
            active_status = active.get("status")
            active_owner = active.get("owner")
            active_exp = _parse_utc(str(active.get("expires_at_utc")))
            if active_status == "ACQUIRED" and now_dt < active_exp and active_owner != owner:
                conflict = {
                    "version": "1",
                    "conflict_type": "LEASE_CONFLICT",
                    "resource_id": resource_id,
                    "resource_class": resource_class.value,
                    "actor": owner,
                    "conflicting_actor": active_owner,
                    "lease_id": active.get("lease_id"),
                    "snapshot_hash": state_hash,
                    "retry_decision": "RETRY",
                    "at_utc": now_utc,
                }
                path = self.store.append_jsonl(self._conflict_rel(resource_id), conflict, stream="artifact")
                raise ResourceConflict(
                    error_code="LEASE_CONFLICT",
                    message=f"active lease held by {active_owner}",
                    trace_refs=[str(path)],
                )
            if active_status == "ACQUIRED" and now_dt >= active_exp:
                active["status"] = "EXPIRED"
                active["released_at_utc"] = now_utc
                lease_path.write_text(_canonical_json(active), encoding="utf-8")

        lease_seed = f"{resource_id}|{owner}|{now_utc}|{cas_base_hash}"
        lease_id = "lease." + hashlib.sha256(lease_seed.encode("utf-8")).hexdigest()[:24]
        expires = _format_utc(now_dt + timedelta(seconds=ttl_seconds))
        lease = {
            "version": "1",
            "lease_id": lease_id,
            "resource_id": resource_id,
            "resource_class": resource_class.value,
            "owner": owner,
            "status": "ACQUIRED",
            "acquired_at_utc": now_utc,
            "expires_at_utc": expires,
            "cas_base_hash": cas_base_hash,
            "conflict_policy": "RETRY",
            "journal_path": str(self.store.artifact_path(self._journal_rel(resource_id))),
        }
        lease_path.write_text(_canonical_json(lease), encoding="utf-8")
        return lease

    def release_lease(self, *, resource_id: str, lease_id: str, owner: str, released_at_utc: str) -> dict[str, Any]:
        path = self._lease_path(resource_id)
        if not path.exists():
            raise FileNotFoundError(f"lease missing for resource: {resource_id}")
        lease = _load_json(path)
        if lease.get("lease_id") != lease_id:
            raise ValueError("lease_id mismatch")
        if lease.get("owner") != owner:
            raise ValueError("owner mismatch")
        if lease.get("status") not in {"ACQUIRED", "EXPIRED"}:
            raise ValueError("lease not active")
        lease["status"] = "RELEASED"
        lease["released_at_utc"] = released_at_utc
        path.write_text(_canonical_json(lease), encoding="utf-8")
        return lease

    def cas_commit(
        self,
        *,
        resource_id: str,
        lease_id: str,
        owner: str,
        expected_old_hash: str,
        new_hash: str,
        reason: str,
        evidence_refs: list[str],
        committed_at_utc: str,
    ) -> dict[str, Any]:
        lease_path = self._lease_path(resource_id)
        if not lease_path.exists():
            raise FileNotFoundError(f"lease missing for resource: {resource_id}")
        lease = _load_json(lease_path)
        if lease.get("lease_id") != lease_id:
            raise ValueError("lease_id mismatch")
        if lease.get("owner") != owner:
            raise ValueError("owner mismatch")
        if lease.get("status") != "ACQUIRED":
            raise ValueError("lease must be ACQUIRED")

        current_hash = self.read_resource_hash(resource_id)
        if current_hash != expected_old_hash:
            conflict = {
                "version": "1",
                "conflict_type": "CAS_CONFLICT",
                "resource_id": resource_id,
                "resource_class": lease.get("resource_class"),
                "actor": owner,
                "lease_id": lease_id,
                "expected_old_hash": expected_old_hash,
                "current_hash": current_hash,
                "retry_decision": "RETRY",
                "at_utc": committed_at_utc,
            }
            path = self.store.append_jsonl(self._conflict_rel(resource_id), conflict, stream="artifact")
            raise ResourceConflict(
                error_code="CAS_CONFLICT",
                message=f"CAS mismatch expected={expected_old_hash} current={current_hash}",
                trace_refs=[str(path)],
            )

        journal = {
            "version": "1",
            "resource_id": resource_id,
            "lease_id": lease_id,
            "actor": owner,
            "old_hash": expected_old_hash,
            "new_hash": new_hash,
            "reason": reason,
            "evidence_refs": list(evidence_refs),
            "committed_at_utc": committed_at_utc,
        }
        self.store.append_jsonl(self._journal_rel(resource_id), journal, stream="artifact")
        self.seed_resource(resource_id=resource_id, resource_hash=new_hash)
        lease["cas_new_hash"] = new_hash
        lease_path.write_text(_canonical_json(lease), encoding="utf-8")
        return journal

    def read_journal(self, resource_id: str) -> list[dict[str, Any]]:
        return _read_jsonl(self.store.artifact_path(self._journal_rel(resource_id)))

    def read_conflicts(self, resource_id: str) -> list[dict[str, Any]]:
        return _read_jsonl(self.store.artifact_path(self._conflict_rel(resource_id)))
