#!/usr/bin/env python3
"""Contract test: tools/ must not call subprocess directly.

Rationale:
- Evidence-chain upgrades require a single run_cmd() wrapper.
- This is an engineering lever: tooling enforces truthfulness better than "don't hallucinate".

Rule:
- In tools/**.py, `import subprocess` is forbidden except in tools/workflow/run_cmd.py.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
ALLOW = {
    (TOOLS / "workflow" / "run_cmd.py").resolve(),
}


def main() -> int:
    bad = 0
    for p in TOOLS.rglob("*.py"):
        rp = p.resolve()
        if rp in ALLOW:
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        if "import subprocess" in txt:
            print(f"[tools_subprocess_wrapper][FAIL] {p}: imports subprocess (must use run_cmd wrapper)")
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
