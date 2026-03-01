#!/usr/bin/env python3
"""Contract test: exec_spans evidence must exist and match sha256.

This enforces the Phase6 evidence-chain upgrade:
- AttemptLog.jsonl includes exec_spans
- stdout_path/stderr_path exist within the run directory
- sha256 hashes match file contents
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs" / "examples" / "reports"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not EXAMPLES.exists():
        print("[exec_span_evidence] docs/examples/reports missing; skipping")
        return 0

    bad = 0
    for run_dir in sorted([p for p in EXAMPLES.iterdir() if p.is_dir()]):
        al = run_dir / "AttemptLog.jsonl"
        if not al.exists():
            continue
        for i, line in enumerate(al.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            obj = json.loads(line)
            spans = obj.get("exec_spans")
            if not isinstance(spans, list) or not spans:
                print(f"[exec_span_evidence][FAIL] {run_dir.name}: line {i} missing exec_spans")
                bad += 1
                continue
            for sp in spans:
                stdout_rel = sp.get("stdout_path")
                stderr_rel = sp.get("stderr_path")
                if not isinstance(stdout_rel, str) or not isinstance(stderr_rel, str):
                    print(f"[exec_span_evidence][FAIL] {run_dir.name}: invalid stdout/stderr path")
                    bad += 1
                    continue
                stdout_p = run_dir / stdout_rel
                stderr_p = run_dir / stderr_rel
                if not stdout_p.exists():
                    print(f"[exec_span_evidence][FAIL] {run_dir.name}: missing {stdout_rel}")
                    bad += 1
                if not stderr_p.exists():
                    print(f"[exec_span_evidence][FAIL] {run_dir.name}: missing {stderr_rel}")
                    bad += 1
                # hash check
                if stdout_p.exists():
                    got = sha256_file(stdout_p)
                    exp = sp.get("stdout_sha256")
                    if exp != got:
                        print(f"[exec_span_evidence][FAIL] {run_dir.name}: stdout sha mismatch")
                        bad += 1
                if stderr_p.exists():
                    got = sha256_file(stderr_p)
                    exp = sp.get("stderr_sha256")
                    if exp != got:
                        print(f"[exec_span_evidence][FAIL] {run_dir.name}: stderr sha mismatch")
                        bad += 1

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
