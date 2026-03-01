#!/usr/bin/env python3
"""Core test: KB mining suggestions must be deterministic and reasonable.

This test is intentionally independent of Lean toolchain; it only uses
fixture RunReport artifacts.

Contract anchors:
- docs/contracts/SKILLS_GROWTH_CONTRACT.md
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "kb_mining_runs"
TOOL = ROOT / "tools" / "bench" / "mine_kb_suggestions.py"


def run_once(out_path: Path) -> dict:
    cmd = [sys.executable, str(TOOL), "--in", str(FIX), "--out", str(out_path)]
    p = subprocess.run(cmd, cwd=str(ROOT))
    if p.returncode != 0:
        raise RuntimeError(f"mine_kb_suggestions failed rc={p.returncode}")
    return json.loads(out_path.read_text(encoding="utf-8"))


def main() -> int:
    if not FIX.exists():
        print(f"[kb_mining][FAIL] missing fixtures: {FIX}", file=sys.stderr)
        return 2
    if not TOOL.exists():
        print(f"[kb_mining][FAIL] missing tool: {TOOL}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as td:
        out1 = Path(td) / "out1.json"
        out2 = Path(td) / "out2.json"

        r1 = run_once(out1)
        r2 = run_once(out2)

        # Determinism: byte-identical canonical JSON output.
        if out1.read_text(encoding="utf-8") != out2.read_text(encoding="utf-8"):
            print("[kb_mining][FAIL] output is not deterministic", file=sys.stderr)
            return 2

        # Shape checks
        if r1.get("schema") != "leanatlas.kb_suggestions":
            print(f"[kb_mining][FAIL] unexpected schema: {r1.get('schema')}", file=sys.stderr)
            return 2

        summary = r1.get("summary") or {}
        if summary.get("run_dir_count") != 4:
            print(f"[kb_mining][FAIL] expected 4 run dirs, got: {summary.get('run_dir_count')}", file=sys.stderr)
            return 2

        sugg = r1.get("suggestions")
        if not isinstance(sugg, list):
            print("[kb_mining][FAIL] suggestions must be a list", file=sys.stderr)
            return 2

        # Expect exactly one suggestion (3 runs of IMPORT/MISSING_IMPORT)
        if len(sugg) != 1:
            print(f"[kb_mining][FAIL] expected 1 suggestion, got {len(sugg)}", file=sys.stderr)
            return 2

        pat = (sugg[0].get("pattern") or {})
        if pat.get("triage_family") != "IMPORT" or pat.get("triage_code") != "MISSING_IMPORT":
            print(f"[kb_mining][FAIL] unexpected pattern: {pat}", file=sys.stderr)
            return 2

        counts = (sugg[0].get("counts") or {})
        if counts.get("run_count") != 3 or counts.get("distinct_problem_count") != 2:
            print(f"[kb_mining][FAIL] unexpected counts: {counts}", file=sys.stderr)
            return 2

        # Template miner should prefer drain3 when available.
        params = r1.get("params") or {}
        tm = params.get("template_miner")
        if tm not in {"drain3", "fallback"}:
            print(f"[kb_mining][FAIL] unexpected template_miner: {tm}", file=sys.stderr)
            return 2

        print("[kb_mining] OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
