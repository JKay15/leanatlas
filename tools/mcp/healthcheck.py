#!/usr/bin/env python3
"""MCP healthcheck (stub).

This script is intentionally deterministic and safe by default.

Planned behavior (Phase1/2):
- Check whether configured MCP endpoints are reachable.
- Probe a small set of representative tools (e.g., list tools, lightweight query).
- Record latency, failures, and fallback recommendations.

Current behavior (stub):
- Writes a minimal JSON report so that automation/TDD wiring can land early.

Exit codes:
- 0: report produced (even if MCP unavailable)
- 2: invalid arguments
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--out", required=True, help="Output JSON path under artifacts/")
  args = ap.parse_args()

  out_path = Path(args.out)
  out_path.parent.mkdir(parents=True, exist_ok=True)

  report = {
    "version": "0.1",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "checks": [
      {
        "id": "stub",
        "status": "UNKNOWN",
        "note": "healthcheck not implemented yet; this is a deterministic placeholder",
      }
    ],
    "recommendations": [
      {
        "id": "fallback_required",
        "note": "All core workflows MUST degrade gracefully when MCP is unavailable.",
      }
    ],
  }

  out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
  print(f"[mcp.healthcheck] wrote {out_path}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
