#!/usr/bin/env python3
"""Ensure docs/testing/TEST_MATRIX.md matches tests/manifest.json.

Deterministic doc generation is part of TDD: the matrix must stay in sync.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "tools" / "tests" / "generate_test_matrix.py"
OUT = ROOT / "docs" / "testing" / "TEST_MATRIX.md"


def main() -> int:
    if not OUT.exists():
        print(f"[test-matrix][FAIL] missing {OUT.relative_to(ROOT)}", file=sys.stderr)
        return 2

    p = subprocess.run([sys.executable, str(GEN)], cwd=str(ROOT), capture_output=True, text=True)
    if p.returncode != 0:
        print("[test-matrix][FAIL] generator failed", file=sys.stderr)
        print(p.stdout)
        print(p.stderr, file=sys.stderr)
        return 2

    expected = p.stdout
    actual = OUT.read_text(encoding="utf-8")

    if actual != expected:
        print("[test-matrix][FAIL] TEST_MATRIX.md is out of date.", file=sys.stderr)
        print("[test-matrix] Regenerate with:", file=sys.stderr)
        print("  python tools/tests/generate_test_matrix.py --write", file=sys.stderr)
        return 2

    print("[test-matrix] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
