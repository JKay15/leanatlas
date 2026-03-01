#!/usr/bin/env python3
"""Core contract checks for RetrievalTrace invariants + Phase4 Domain MCP protocol smoke.

Why bundle these?
- The test registry is strict (all tests must be registered).
- This file is already registered as a core test; Phase4 uses it to add
  protocol-level TDD for Domain Ontology MCP without touching the registry.

Scope:
- RetrievalTrace invariants (Phase1/2)
- MCP protocol black-box checks for tools/lean_domain_mcp/domain_mcp_server.py (Phase4)

This test is deterministic and requires no external tooling.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs" / "examples" / "reports"


def fail(msg: str) -> None:
    raise ValueError(msg)


def check_retrievaltrace_examples() -> None:
    bad = 0
    for path in sorted(EXAMPLES.glob("*/RetrievalTrace.json")):
        try:
            tr = json.loads(path.read_text(encoding="utf-8"))
            steps = tr.get("steps", [])
            budget = tr.get("budget", {})
            used_steps = budget.get("used_steps")
            max_steps = budget.get("max_steps")
            used_ext = budget.get("used_external_queries")
            max_ext = budget.get("max_external_queries")

            if used_steps != len(steps):
                fail(f"{path}: budget.used_steps={used_steps} != len(steps)={len(steps)}")
            if isinstance(max_steps, int) and isinstance(used_steps, int) and used_steps > max_steps:
                fail(f"{path}: used_steps={used_steps} > max_steps={max_steps}")
            if isinstance(max_ext, int) and isinstance(used_ext, int) and used_ext > max_ext:
                fail(f"{path}: used_external_queries={used_ext} > max_external_queries={max_ext}")

            # step_index integrity
            for i, s in enumerate(steps):
                if s.get("step_index") != i:
                    fail(f"{path}: steps[{i}].step_index={s.get('step_index')} (expected {i})")

            print(f"[retrievaltrace-invariants][OK]   {path}")
        except Exception as e:
            bad += 1
            print(f"[retrievaltrace-invariants][FAIL] {path}: {e}", file=sys.stderr)

    if bad:
        raise SystemExit(1)


def run_domain_mcp_protocol_smoke() -> None:
    """Black-box MCP stdio test.

    We intentionally do not depend on any MCP client library.
    We just speak JSON-RPC 2.0 line-by-line.
    """

    server = ROOT / "tools" / "lean_domain_mcp" / "domain_mcp_server.py"
    if not server.exists():
        fail(f"Domain MCP server missing: {server}")

    # Mix a parse error line to assert -32700 handling.
    bad_line = '{"jsonrpc": "2.0", "id": 999, "method": "initialize"'  # missing closing }

    reqs = [
        bad_line,
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "clientInfo": {"name": "test"}},
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "domain/info", "arguments": {}},
            }
        ),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "domain/lookup", "arguments": {"query": "logic", "k": 3}},
            }
        ),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "domain/path", "arguments": {"id_or_code": "03E20"}},
            }
        ),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "domain/expand",
                    "arguments": {"codes": ["03E20"], "up_depth": 1, "down_depth": 0},
                },
            }
        ),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "domain/nope", "arguments": {}},
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 8, "method": "nope"}),
    ]

    inp = "\n".join(reqs) + "\n"
    p = subprocess.run(
        [sys.executable, str(server), "--msc2020-mini"],
        input=inp,
        text=True,
        capture_output=True,
        cwd=str(ROOT),
        timeout=8,
    )

    if p.returncode != 0:
        print("[domain-mcp][stderr]\n" + p.stderr, file=sys.stderr)
        fail(f"Domain MCP server exited with {p.returncode}")

    # Parse responses.
    responses = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if isinstance(obj, list):
            responses.extend(obj)
        else:
            responses.append(obj)

    by_id = {}
    saw_parse_error = False
    for r in responses:
        if r.get("id") is None and r.get("error", {}).get("code") == -32700:
            saw_parse_error = True
        if "id" in r and r.get("id") is not None:
            by_id[r["id"]] = r

    if not saw_parse_error:
        fail("Expected to see a -32700 Parse error response")

    # initialize
    init = by_id.get(1)
    if not init or "result" not in init:
        fail("Missing initialize result")
    if init["result"].get("protocolVersion") != "2025-11-25":
        fail(f"Unexpected protocolVersion: {init['result'].get('protocolVersion')}")

    # tools/list
    tl = by_id.get(2)
    tools = (tl or {}).get("result", {}).get("tools", [])
    names = [t.get("name") for t in tools if isinstance(t, dict)]
    if "domain/info" not in names:
        fail("tools/list missing domain/info")
    if any((not isinstance(n, str) or len(n) > 64 or len(n) < 1) for n in names):
        fail("tools/list contains invalid tool name length")

    # domain/info
    info = by_id.get(3)
    if info.get("result", {}).get("isError") is True:
        fail("domain/info returned isError=true")
    structured = info.get("result", {}).get("structuredContent", {})
    if structured.get("server_name") != "leanatlas-domain-mcp":
        fail("domain/info.server_name mismatch")
    if not structured.get("sources"):
        fail("domain/info.sources missing")

    # domain/lookup
    lookup = by_id.get(4)
    if lookup.get("result", {}).get("isError") is True:
        fail("domain/lookup returned isError=true")
    results = lookup.get("result", {}).get("structuredContent", {}).get("results", [])
    codes = [r.get("code") for r in results]
    expected = ["03", "03F40", "68V30"]
    if codes != expected:
        fail(f"domain/lookup codes mismatch: got {codes}, expected {expected}")

    # domain/path
    path = by_id.get(5)
    nodes = path.get("result", {}).get("structuredContent", {}).get("path", [])
    path_codes = [n.get("code") for n in nodes]
    if path_codes != ["03", "03E", "03E20"]:
        fail(f"domain/path(03E20) mismatch: {path_codes}")

    # domain/expand
    exp = by_id.get(6)
    ids = exp.get("result", {}).get("structuredContent", {}).get("ids", [])
    if ids != ["msc2020:03E", "msc2020:03E20"]:
        fail(f"domain/expand mismatch: {ids}")

    # unknown tool should be isError
    ut = by_id.get(7)
    if ut.get("result", {}).get("isError") is not True:
        fail("Unknown tool call should return isError=true")

    # unknown method
    um = by_id.get(8)
    if um.get("error", {}).get("code") != -32601:
        fail("Unknown method should return -32601")

    print("[domain-mcp][protocol-smoke][OK]")


def main() -> int:
    # 1) RetrievalTrace invariants
    check_retrievaltrace_examples()

    # 2) Domain MCP protocol smoke
    run_domain_mcp_protocol_smoke()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
