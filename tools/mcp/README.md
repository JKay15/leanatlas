# tools/mcp

This directory contains LeanAtlas MCP integration helpers and healthchecks (determinism first).

- `healthcheck.py`: probes MCP servers (e.g. lean-lsp-mcp, Domain/MSC MCP) and writes a machine-readable report.

Hard rule:
- The default workflow must still exit cleanly **when MCP is unavailable** (SUCCESS or TRIAGED).

Therefore healthcheck outputs are mainly used for:
- automations (generate a fix PR / suggest install actions)
- CI/nightly early warning (catch tool drift before it breaks real runs)
