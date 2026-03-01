#!/usr/bin/env python3
"""LeanAtlas Domain Ontology MCP server (stdio, stdlib-only).

Goals (Phase4):
- Provide a stable `domain/*` tool surface backed by MSC2020 + optional local overlay.
- Be deterministic and safe by default.
- Degrade gracefully when data is missing (MCP is an accelerator, never a SPOF).

This is a minimal MCP implementation:
- JSON-RPC 2.0 over stdio, one JSON message per line.
- Implements: initialize, tools/list, tools/call.

Contracts:
- docs/contracts/MCP_MSC2020_CONTRACT.md
- docs/contracts/MCP_ADAPTER_CONTRACT.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SERVER_NAME = "leanatlas-domain-mcp"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-11-25"

BUNDLE_SCHEMA_V1 = "leanatlas.domain_ontology.bundle.v1"
OVERLAY_SCHEMA_V1 = "leanatlas.domain_ontology.overlay.v1"

# Tool name constraints (SEP-986-ish). We keep it here to avoid accidental drift.
_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_\-./]{1,64}$")


# -----------------------------
# Data model + loading
# -----------------------------

_CODE_2 = re.compile(r"^\d{2}$")
_CODE_3 = re.compile(r"^\d{2}[A-Z]$")
_CODE_5 = re.compile(r"^\d{2}[A-Z](?:\d{2}|xx)$")
_CODE_HYPHEN = re.compile(r"^\d{2}-[0-9A-Z]{2}$")


def _normalize_code(code: str) -> str:
    code = code.strip()
    if len(code) == 5 and code.endswith("XX"):
        code = code[:-2] + "xx"
    return code


def _infer_level(code: str) -> Optional[int]:
    if _CODE_2.fullmatch(code):
        return 2
    if _CODE_3.fullmatch(code):
        return 3
    if _CODE_HYPHEN.fullmatch(code):
        return 5
    if _CODE_5.fullmatch(code):
        return 5
    return None


def _infer_parent_code(code: str) -> Optional[str]:
    if _CODE_2.fullmatch(code):
        return None
    if _CODE_3.fullmatch(code):
        return code[:2]
    if _CODE_HYPHEN.fullmatch(code):
        return code[:2]
    if _CODE_5.fullmatch(code):
        return code[:3]
    return None


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _load_json(p: Path) -> Any:
    return json.loads(_read_text(p))


def _canonical_dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


@dataclass
class SourceMeta:
    source_id: str
    data_version: str
    license: str
    content_hash_sha256: str


class DomainStore:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.by_code: Dict[Tuple[str, str], str] = {}  # (source_id, code) -> id
        self.children: Dict[str, List[str]] = {}
        self.sources: List[SourceMeta] = []
        self.warnings: List[str] = []

    def load_mini_msc2020(self, csv_path: Path) -> None:
        source_id = "msc2020"
        rows = []
        raw = _read_text(csv_path)
        reader = csv.DictReader(raw.splitlines())
        for r in reader:
            code = _normalize_code((r.get("code") or "").strip())
            if not code:
                continue
            text = (r.get("text") or "").strip()
            desc = (r.get("description") or "").strip()
            rows.append((code, text, desc))

        codes = {c for c, _, _ in rows}
        for code, text, desc in rows:
            level = _infer_level(code)
            parent_code = _infer_parent_code(code)
            parent_id = None
            if parent_code and parent_code in codes:
                parent_id = f"{source_id}:{parent_code}"

            node = {
                "id": f"{source_id}:{code}",
                "code": code,
                "source_id": source_id,
                "level": level,
                "text": text,
                "description": desc,
                "parent_id": parent_id,
                "aliases": [],
                "keywords": [],
                "directory_roots": [],
                "notes": [],
            }
            self.nodes[node["id"]] = node
            self.by_code[(source_id, code)] = node["id"]

        # Build children index
        self._rebuild_children()

        content_hash = _sha256_bytes(raw.encode("utf-8"))
        self.sources.append(
            SourceMeta(
                source_id=source_id,
                data_version="msc2020-mini",
                license="CC BY-NC-SA",
                content_hash_sha256=content_hash,
            )
        )
        self.warnings.append("Loaded mini MSC2020 fixture (not full taxonomy)")

    def load_bundle(self, bundle_path: Path) -> None:
        blob = bundle_path.read_bytes()
        content_hash = _sha256_bytes(blob)
        obj = json.loads(blob.decode("utf-8", errors="replace"))

        schema_version = obj.get("schema_version")
        if schema_version != BUNDLE_SCHEMA_V1:
            raise ValueError(f"Unsupported bundle schema_version: {schema_version!r}")

        source = obj.get("source") or {}
        source_id = str(source.get("source_id") or "").strip()
        data_version = str(obj.get("data_version") or "").strip()
        license_str = str(source.get("license") or "").strip() or "UNKNOWN"

        if not source_id:
            raise ValueError("bundle.source.source_id missing")
        if not data_version:
            raise ValueError("bundle.data_version missing")

        nodes = obj.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("bundle.nodes must be a list")

        for n in nodes:
            if not isinstance(n, dict):
                continue
            nid = str(n.get("id") or "").strip()
            code = str(n.get("code") or "").strip()
            if not nid or not code:
                continue
            if n.get("source_id") != source_id:
                # Normalize to bundle-level source_id.
                n["source_id"] = source_id
            # Ensure extension fields exist.
            n.setdefault("aliases", [])
            n.setdefault("keywords", [])
            n.setdefault("directory_roots", [])
            n.setdefault("notes", [])
            self.nodes[nid] = n
            self.by_code[(source_id, code)] = nid

        self._rebuild_children()
        self.sources.append(
            SourceMeta(
                source_id=source_id,
                data_version=data_version,
                license=license_str,
                content_hash_sha256=content_hash,
            )
        )

    def apply_overlay(self, overlay_path: Path) -> None:
        obj = _load_json(overlay_path)
        schema_version = obj.get("schema_version")
        if schema_version != OVERLAY_SCHEMA_V1:
            raise ValueError(f"Unsupported overlay schema_version: {schema_version!r}")

        source_id = str(obj.get("source_id") or "").strip()
        if source_id != "local":
            raise ValueError("overlay.source_id must be 'local'")

        raw = overlay_path.read_bytes()
        content_hash = _sha256_bytes(raw)
        data_version = str(obj.get("data_version") or "").strip() or "local@unknown"

        overrides = obj.get("overrides") or {}
        if not isinstance(overrides, dict):
            raise ValueError("overlay.overrides must be an object")

        allowed_keys = {"aliases", "keywords", "directory_roots", "notes"}
        for target_id, patch in overrides.items():
            if target_id not in self.nodes:
                raise ValueError(f"overlay override target id not found: {target_id}")
            if not isinstance(patch, dict):
                raise ValueError(f"overlay override for {target_id} must be object")
            for k in patch.keys():
                if k not in allowed_keys:
                    raise ValueError(
                        f"overlay override for {target_id} contains forbidden field: {k}"
                    )

            node = self.nodes[target_id]
            for k in allowed_keys:
                if k in patch:
                    v = patch.get(k)
                    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                        raise ValueError(f"overlay field {k} for {target_id} must be string[]")
                    # Deterministic merge: append unique, keep sorted.
                    merged = set(node.get(k) or []) | set(v)
                    node[k] = sorted(merged)

        new_nodes = obj.get("new_nodes") or []
        if not isinstance(new_nodes, list):
            raise ValueError("overlay.new_nodes must be a list")

        for n in new_nodes:
            if not isinstance(n, dict):
                continue
            nid = str(n.get("id") or "").strip()
            if not nid.startswith("local:"):
                raise ValueError(f"new local node id must start with 'local:', got: {nid}")
            if nid in self.nodes:
                raise ValueError(f"new local node id conflicts with existing id: {nid}")
            code = str(n.get("code") or "").strip()
            if not code:
                raise ValueError(f"new local node missing code: {nid}")
            parent_id = n.get("parent_id")
            if parent_id is not None and parent_id not in self.nodes:
                raise ValueError(f"new local node parent_id not found: {parent_id}")

            # Enforce extension fields presence.
            n.setdefault("source_id", "local")
            n.setdefault("aliases", [])
            n.setdefault("keywords", [])
            n.setdefault("directory_roots", [])
            n.setdefault("notes", [])

            self.nodes[nid] = n
            self.by_code[("local", code)] = nid

        self._rebuild_children()

        self.sources.append(
            SourceMeta(
                source_id="local",
                data_version=data_version,
                license="INTERNAL",
                content_hash_sha256=content_hash,
            )
        )

    def _rebuild_children(self) -> None:
        self.children = {}
        for nid, n in self.nodes.items():
            pid = n.get("parent_id")
            if not pid:
                continue
            self.children.setdefault(pid, []).append(nid)
        # Deterministic order
        for pid in self.children:
            self.children[pid].sort(key=lambda cid: (self.nodes[cid].get("code") or "", cid))

    # --------------
    # Query helpers
    # --------------

    def _resolve(self, code_or_id: str, default_source: str = "msc2020") -> Optional[str]:
        s = (code_or_id or "").strip()
        if not s:
            return None
        if ":" in s:
            # id
            return s if s in self.nodes else None
        # code
        key = (default_source, _normalize_code(s))
        return self.by_code.get(key)

    def get_nodes(self, ids: List[str], default_source: str = "msc2020") -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for x in ids:
            nid = self._resolve(x, default_source=default_source)
            if nid and nid in self.nodes:
                out.append(self.nodes[nid])
        return out

    def path(self, code_or_id: str, include_self: bool = True) -> List[Dict[str, Any]]:
        nid = self._resolve(code_or_id)
        if not nid:
            return []
        cur = nid
        chain: List[str] = []
        while cur:
            chain.append(cur)
            pid = self.nodes[cur].get("parent_id")
            cur = pid if pid in self.nodes else None
        chain.reverse()
        if not include_self and chain:
            chain = chain[:-1]
        return [self.nodes[i] for i in chain]

    def children_of(self, code_or_id: str, depth: int = 1) -> List[Dict[str, Any]]:
        nid = self._resolve(code_or_id)
        if not nid:
            return []

        out: List[str] = []

        def rec(cur: str, d: int) -> None:
            if d <= 0:
                return
            for c in self.children.get(cur, []):
                out.append(c)
                rec(c, d - 1)

        rec(nid, depth)
        return [self.nodes[i] for i in out]

    def expand(
        self,
        ids_or_codes: List[str],
        up_depth: int = 1,
        down_depth: int = 0,
        include_siblings: bool = False,
    ) -> List[str]:
        start_ids = [self._resolve(x) for x in ids_or_codes]
        start_ids = [x for x in start_ids if x]
        seen = set(start_ids)

        # Up
        cur_level = list(start_ids)
        for _ in range(max(0, up_depth)):
            nxt = []
            for nid in cur_level:
                pid = self.nodes[nid].get("parent_id")
                if pid and pid in self.nodes and pid not in seen:
                    seen.add(pid)
                    nxt.append(pid)
            cur_level = nxt

        # Down
        frontier = list(start_ids)
        for _ in range(max(0, down_depth)):
            nxt = []
            for nid in frontier:
                for c in self.children.get(nid, []):
                    if c not in seen:
                        seen.add(c)
                        nxt.append(c)
            frontier = nxt

        # Siblings
        if include_siblings:
            for nid in list(start_ids):
                pid = self.nodes[nid].get("parent_id")
                if pid and pid in self.nodes:
                    for sib in self.children.get(pid, []):
                        if sib not in seen:
                            seen.add(sib)

        # Deterministic order: by (source_id, code)
        ordered = sorted(
            seen,
            key=lambda i: (
                self.nodes[i].get("source_id") or "",
                self.nodes[i].get("code") or "",
                i,
            ),
        )
        return ordered

    def roots(self, ids_or_codes: List[str]) -> Dict[str, Any]:
        ids = [self._resolve(x) for x in ids_or_codes]
        ids = [x for x in ids if x]
        roots: List[Dict[str, Any]] = []
        for nid in ids:
            node = self.nodes[nid]
            for r in node.get("directory_roots") or []:
                rp = (self.repo_root / r).resolve() if not os.path.isabs(r) else Path(r)
                roots.append(
                    {
                        "path": r,
                        "exists": rp.exists(),
                        "source": nid,
                    }
                )
        # de-dup deterministically
        uniq = {}
        for x in roots:
            key = (x["path"], x["exists"])
            uniq[key] = x
        roots = sorted(uniq.values(), key=lambda x: (x["path"], str(x["exists"])))
        return {
            "missing": len(roots) == 0,
            "repo_root": str(self.repo_root),
            "roots": roots,
        }

    def lookup(
        self,
        query: str,
        k: int = 10,
        source_filter: Optional[List[str]] = None,
        level_filter: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []
        qn = q.lower()

        def allowed(n: Dict[str, Any]) -> bool:
            if source_filter and n.get("source_id") not in source_filter:
                return False
            if level_filter and n.get("level") not in level_filter:
                return False
            return True

        res: List[Tuple[float, str]] = []  # (score, id)

        # Code-like query: treat as code prefix boost.
        code_like = bool(re.fullmatch(r"[0-9A-Za-z\-]{2,10}", q))

        for nid, n in self.nodes.items():
            if not allowed(n):
                continue
            code = str(n.get("code") or "")
            text = str(n.get("text") or "")
            desc = str(n.get("description") or "")
            aliases = " ".join(n.get("aliases") or [])
            keywords = " ".join(n.get("keywords") or [])
            hay = f"{code} {text} {desc} {aliases} {keywords}".lower()

            score = 0.0
            if code.lower() == qn:
                score = 100.0
            elif code_like and code.lower().startswith(qn):
                score = 90.0
            else:
                if qn in text.lower():
                    score += 10.0
                if qn in desc.lower():
                    score += 5.0
                if qn in aliases.lower():
                    score += 7.0
                if qn in keywords.lower():
                    score += 3.0

                # token overlap (lightweight, deterministic)
                toks = [t for t in re.split(r"[^a-z0-9]+", qn) if t]
                if toks:
                    hit = 0
                    for t in toks:
                        if t in hay:
                            hit += 1
                    score += float(hit)

            if score > 0:
                res.append((score, nid))

        # Deterministic sort.
        res.sort(
            key=lambda x: (
                -x[0],
                str(self.nodes[x[1]].get("code") or ""),
                x[1],
            )
        )

        out: List[Dict[str, Any]] = []
        for score, nid in res[: max(0, int(k))]:
            n = self.nodes[nid]
            out.append(
                {
                    "id": nid,
                    "code": n.get("code"),
                    "text": n.get("text"),
                    "description": n.get("description"),
                    "source_id": n.get("source_id"),
                    "level": n.get("level"),
                    "score": score,
                }
            )
        return out


# -----------------------------
# MCP server (minimal)
# -----------------------------


def _err(code: int, message: str, data: Any = None) -> Dict[str, Any]:
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    return e


def _is_valid_tool_name(name: str) -> bool:
    return bool(_TOOL_NAME_RE.fullmatch(name or ""))


class MCPServer:
    def __init__(self, store: DomainStore) -> None:
        self.store = store
        self._tools = self._build_tools()

    def _build_tools(self) -> List[Dict[str, Any]]:
        # Keep descriptions short; structuredContent carries the real payload.
        tools = [
            {
                "name": "domain/info",
                "description": "Get domain ontology server + source versions.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": True},
            },
            {
                "name": "domain/validate_hint",
                "description": "Validate a human hint (code or text) into candidates.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"hint": {"type": "string"}, "k": {"type": "integer"}},
                    "required": ["hint"],
                    "additionalProperties": True,
                },
            },
            {
                "name": "domain/lookup",
                "description": "Lookup domain nodes by query.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "k": {"type": "integer"},
                        "source_filter": {"type": "array", "items": {"type": "string"}},
                        "level_filter": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["query"],
                    "additionalProperties": True,
                },
            },
            {
                "name": "domain/get",
                "description": "Get nodes by ids or codes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ids": {"type": "array", "items": {"type": "string"}},
                        "codes": {"type": "array", "items": {"type": "string"}},
                        "default_source": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
            },
            {
                "name": "domain/path",
                "description": "Get ancestor path for a node.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id_or_code": {"type": "string"},
                        "include_self": {"type": "boolean"},
                    },
                    "required": ["id_or_code"],
                    "additionalProperties": True,
                },
            },
            {
                "name": "domain/children",
                "description": "Get children nodes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id_or_code": {"type": "string"},
                        "depth": {"type": "integer"},
                    },
                    "required": ["id_or_code"],
                    "additionalProperties": True,
                },
            },
            {
                "name": "domain/expand",
                "description": "Expand domain set around ids/codes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ids": {"type": "array", "items": {"type": "string"}},
                        "codes": {"type": "array", "items": {"type": "string"}},
                        "up_depth": {"type": "integer"},
                        "down_depth": {"type": "integer"},
                        "include_siblings": {"type": "boolean"},
                    },
                    "additionalProperties": True,
                },
            },
            {
                "name": "domain/roots",
                "description": "Suggest repo directory roots for domains (overlay-driven).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ids": {"type": "array", "items": {"type": "string"}},
                        "codes": {"type": "array", "items": {"type": "string"}},
                    },
                    "additionalProperties": True,
                },
            },
        ]

        # Optional compatibility aliases.
        tools.extend(
            [
                {
                    "name": "msc_info",
                    "description": "(alias) MSC2020 info.",
                    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": True},
                },
                {
                    "name": "msc_lookup",
                    "description": "(alias) MSC2020 lookup.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}, "k": {"type": "integer"}},
                        "required": ["query"],
                        "additionalProperties": True,
                    },
                },
                {
                    "name": "msc_path",
                    "description": "(alias) MSC2020 path.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"code": {"type": "string"}},
                        "required": ["code"],
                        "additionalProperties": True,
                    },
                },
            ]
        )

        # Sanity: enforce name rules.
        for t in tools:
            if not _is_valid_tool_name(t.get("name", "")):
                raise RuntimeError(f"Invalid tool name: {t.get('name')}")

        return tools

    def handle_request(self, req: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(req, dict):
            return {"jsonrpc": "2.0", "id": None, "error": _err(-32600, "Invalid Request")}

        if req.get("jsonrpc") != "2.0":
            return {"jsonrpc": "2.0", "id": req.get("id"), "error": _err(-32600, "Invalid Request")}

        method = req.get("method")
        rid = req.get("id")
        params = req.get("params")

        # Notifications: no id => no response.
        is_notification = "id" not in req

        try:
            if method == "initialize":
                res = self._initialize(params)
                return None if is_notification else {"jsonrpc": "2.0", "id": rid, "result": res}
            if method == "notifications/initialized":
                return None
            if method == "tools/list":
                res = {"tools": self._tools}
                return None if is_notification else {"jsonrpc": "2.0", "id": rid, "result": res}
            if method == "tools/call":
                res = self._tools_call(params)
                return None if is_notification else {"jsonrpc": "2.0", "id": rid, "result": res}

            return None if is_notification else {"jsonrpc": "2.0", "id": rid, "error": _err(-32601, "Method not found")}
        except Exception as e:
            return None if is_notification else {"jsonrpc": "2.0", "id": rid, "error": _err(-32603, "Internal error", str(e))}

    def _initialize(self, params: Any) -> Dict[str, Any]:
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValueError("initialize params must be object")

        pv = params.get("protocolVersion")
        if pv is not None and pv not in (PROTOCOL_VERSION, "2025-03-26"):
            # Strict: refuse unknown versions.
            raise ValueError(f"Unsupported protocolVersion: {pv}")

        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }

    def _tools_call(self, params: Any) -> Dict[str, Any]:
        if not isinstance(params, dict):
            raise ValueError("tools/call params must be object")

        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("tools/call requires string field: name")

        args = params.get("arguments")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise ValueError("tools/call arguments must be object")

        # Dispatch.
        if name == "domain/info" or name == "msc_info":
            payload = self._tool_domain_info()
            return _tool_ok(payload)

        if name == "domain/validate_hint":
            hint = args.get("hint")
            if not isinstance(hint, str) or not hint.strip():
                return _tool_err("hint must be non-empty string")
            k = int(args.get("k") or 8)
            payload = {
                "normalized_hint": hint.strip(),
                "is_code_like": bool(re.fullmatch(r"[0-9A-Za-z\-]{2,10}", hint.strip())),
                "candidates": self.store.lookup(hint.strip(), k=k),
                "warnings": [],
            }
            return _tool_ok(payload)

        if name == "domain/lookup" or name == "msc_lookup":
            q = args.get("query")
            if not isinstance(q, str) or not q.strip():
                return _tool_err("query must be non-empty string")
            k = int(args.get("k") or 10)
            source_filter = args.get("source_filter")
            level_filter = args.get("level_filter")
            if name == "msc_lookup":
                source_filter = ["msc2020"]

            payload = {
                "query": q,
                "k": k,
                "results": self.store.lookup(
                    q,
                    k=k,
                    source_filter=source_filter if isinstance(source_filter, list) else None,
                    level_filter=level_filter if isinstance(level_filter, list) else None,
                ),
            }
            return _tool_ok(payload)

        if name == "domain/get":
            ids = args.get("ids")
            codes = args.get("codes")
            default_source = args.get("default_source")
            default_source = default_source if isinstance(default_source, str) and default_source else "msc2020"

            reqs: List[str] = []
            if isinstance(ids, list):
                reqs.extend([str(x) for x in ids])
            if isinstance(codes, list):
                reqs.extend([str(x) for x in codes])

            if not reqs:
                return _tool_err("Provide ids[] or codes[]")

            nodes = self.store.get_nodes(reqs, default_source=default_source)
            return _tool_ok({"nodes": nodes})

        if name == "domain/path" or name == "msc_path":
            if name == "msc_path":
                code = args.get("code")
                if not isinstance(code, str) or not code.strip():
                    return _tool_err("code must be non-empty string")
                id_or_code = code
                include_self = True
            else:
                id_or_code = args.get("id_or_code")
                if not isinstance(id_or_code, str) or not id_or_code.strip():
                    return _tool_err("id_or_code must be non-empty string")
                include_self = bool(args.get("include_self", True))

            nodes = self.store.path(id_or_code, include_self=include_self)
            return _tool_ok({"path": nodes})

        if name == "domain/children":
            id_or_code = args.get("id_or_code")
            if not isinstance(id_or_code, str) or not id_or_code.strip():
                return _tool_err("id_or_code must be non-empty string")
            depth = int(args.get("depth") or 1)
            nodes = self.store.children_of(id_or_code, depth=depth)
            return _tool_ok({"children": nodes})

        if name == "domain/expand":
            ids = args.get("ids")
            codes = args.get("codes")
            reqs: List[str] = []
            if isinstance(ids, list):
                reqs.extend([str(x) for x in ids])
            if isinstance(codes, list):
                reqs.extend([str(x) for x in codes])
            if not reqs:
                return _tool_err("Provide ids[] or codes[]")
            up_depth = int(args.get("up_depth") or 1)
            down_depth = int(args.get("down_depth") or 0)
            include_siblings = bool(args.get("include_siblings") or False)
            ids_out = self.store.expand(reqs, up_depth=up_depth, down_depth=down_depth, include_siblings=include_siblings)
            return _tool_ok({"ids": ids_out})

        if name == "domain/roots":
            ids = args.get("ids")
            codes = args.get("codes")
            reqs: List[str] = []
            if isinstance(ids, list):
                reqs.extend([str(x) for x in ids])
            if isinstance(codes, list):
                reqs.extend([str(x) for x in codes])
            if not reqs:
                return _tool_err("Provide ids[] or codes[]")
            return _tool_ok(self.store.roots(reqs))

        return _tool_err(f"Unknown tool name: {name}")

    def _tool_domain_info(self) -> Dict[str, Any]:
        # Aggregate a simple bundle version string.
        parts = [f"{s.source_id}:{s.content_hash_sha256[:8]}" for s in self.store.sources]
        data_bundle_version = "+".join(parts) if parts else "EMPTY"

        counts = {
            "nodes": len(self.store.nodes),
            "by_level": {
                "2": sum(1 for n in self.store.nodes.values() if n.get("level") == 2),
                "3": sum(1 for n in self.store.nodes.values() if n.get("level") == 3),
                "5": sum(1 for n in self.store.nodes.values() if n.get("level") == 5),
            },
        }

        return {
            "server_name": SERVER_NAME,
            "server_version": SERVER_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": BUNDLE_SCHEMA_V1,
            "data_bundle_version": data_bundle_version,
            "sources": [s.__dict__ for s in self.store.sources],
            "counts": counts,
            "warnings": list(self.store.warnings),
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }


def _tool_ok(structured: Any) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": "OK"}],
        "structuredContent": structured,
        "isError": False,
    }


def _tool_err(msg: str) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": msg}],
        "structuredContent": {"error": msg},
        "isError": True,
    }


def _write_resp(resp: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def run_stdio(server: MCPServer) -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            _write_resp({"jsonrpc": "2.0", "id": None, "error": _err(-32700, "Parse error", str(e))})
            continue

        if isinstance(req, list):
            # Batch.
            out: List[Dict[str, Any]] = []
            for one in req:
                resp = server.handle_request(one)
                if resp is not None:
                    out.append(resp)
            if out:
                _write_resp(out)
            continue

        resp = server.handle_request(req)
        if resp is not None:
            _write_resp(resp)

    return 0


def smoke_test(store: DomainStore) -> int:
    # Minimal deterministic checks.
    info = MCPServer(store)._tool_domain_info()
    if not info.get("sources"):
        print("[domain-mcp][smoke][FAIL] no sources loaded", file=sys.stderr)
        return 2

    # lookup should be deterministic for the mini fixture.
    res = store.lookup("logic", k=5)
    if not res:
        print("[domain-mcp][smoke][FAIL] lookup returned empty", file=sys.stderr)
        return 2

    # path check
    p = store.path("03E20")
    if not p:
        print("[domain-mcp][smoke][FAIL] path(03E20) empty", file=sys.stderr)
        return 2

    print("[domain-mcp][smoke][OK] sources=", [s.source_id for s in store.sources])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", help="Path to domain bundle JSON (msc2020 ingest output)")
    ap.add_argument(
        "--overlay",
        action="append",
        default=[],
        help="Path to overlay JSON (may repeat).",
    )
    ap.add_argument(
        "--msc2020-mini",
        action="store_true",
        help="Load a small built-in MSC2020 fixture for tests/dev.",
    )
    ap.add_argument(
        "--repo-root",
        default=".",
        help="Repo root used to validate directory_roots existence.",
    )
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="Run deterministic smoke checks and exit (no stdio MCP).",
    )

    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    store = DomainStore(repo_root=repo_root)

    try:
        if args.bundle:
            store.load_bundle(Path(args.bundle))
        if args.msc2020_mini:
            csv_path = Path(__file__).resolve().parent / "data" / "msc2020_mini.csv"
            store.load_mini_msc2020(csv_path)
        for op in args.overlay or []:
            store.apply_overlay(Path(op))
    except Exception as e:
        print(f"[domain-mcp][FAIL] failed to load data: {e}", file=sys.stderr)
        if args.smoke:
            return 2
        # In stdio mode, we still start but with empty store so client can degrade.
        store.warnings.append(f"DATA_LOAD_FAILED: {e}")

    if args.smoke:
        return smoke_test(store)

    server = MCPServer(store)
    return run_stdio(server)


if __name__ == "__main__":
    raise SystemExit(main())
