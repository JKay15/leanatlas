#!/usr/bin/env python3
"""Contract: force-deposit policy must work across tools/skills/feedback.

Coverage:
- Promotion reuse gate can bypass Rule-of-Three only via explicit force-deposit
  signal + non-empty justification.
- KB suggestion miner can emit forced suggestions below threshold.
- Feedback miner can ingest explicitly forced feedback items without tagged inbox lines.
- Promotion verification policy includes `lake lint`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
KB_TOOL = ROOT / "tools" / "bench" / "mine_kb_suggestions.py"
FB_TOOL = ROOT / "tools" / "feedback" / "mine_chat_feedback.py"
KB_FIXTURE = ROOT / "tests" / "fixtures" / "kb_mining_runs"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_promotion_force_policy() -> None:
    from tools.promote.promote import _gate_reuse_evidence

    policy = {
        "min_reuse_problems": 3,
        "allow_exceptions": False,
        "allow_force_deposit": True,
    }

    # 1) force_deposit without justification must fail.
    c_bad = {
        "name": "LeanAtlas.Toolbox.BadForce",
        "evidence": {"problems": ["p1"]},
        "intent": {"force_deposit": True},
    }
    g_bad = _gate_reuse_evidence(policy, [c_bad], set())
    _assert(not bool(g_bad.get("passed")), "force_deposit without justification must fail")

    # 2) force_deposit with justification must pass.
    c_ok = {
        "name": "LeanAtlas.Toolbox.GoodForce",
        "evidence": {"problems": ["p1"]},
        "intent": {"force_deposit": True, "justification": "Human requested direct deposition for a high-impact tool."},
    }
    g_ok = _gate_reuse_evidence(policy, [c_ok], set())
    _assert(bool(g_ok.get("passed")), "force_deposit with justification must pass")
    ev_ok = g_ok.get("evidence") or {}
    _assert(bool(ev_ok.get("force_deposit_applied")), "force_deposit evidence marker must be present")

    # 3) registry-style forced tool names with justification must pass.
    c_reg = {
        "name": "LeanAtlas.Toolbox.RegistryForced",
        "evidence": {"problems": ["p1"]},
        "intent": {"justification": "Explicit force-deposit policy entry requested by user."},
    }
    g_reg = _gate_reuse_evidence(policy, [c_reg], {"LeanAtlas.Toolbox.RegistryForced"})
    _assert(bool(g_reg.get("passed")), "forced tool from policy set must pass with justification")

    # 4) below-threshold non-force must fail when exceptions are disabled.
    c_fail = {
        "name": "LeanAtlas.Toolbox.NoForce",
        "evidence": {"problems": ["p1"]},
        "intent": {},
    }
    g_fail = _gate_reuse_evidence(policy, [c_fail], set())
    _assert(not bool(g_fail.get("passed")), "below-threshold non-force candidate must fail")

    # 5) verification gate policy must include lake lint.
    promote_text = (ROOT / "tools" / "promote" / "promote.py").read_text(encoding="utf-8")
    _assert('["lake", "lint"]' in promote_text, "promotion verification must run lake lint")


def _check_kb_force_policy() -> None:
    _assert(KB_TOOL.exists(), "missing tools/bench/mine_kb_suggestions.py")
    _assert(KB_FIXTURE.exists(), "missing tests/fixtures/kb_mining_runs")

    with tempfile.TemporaryDirectory(prefix="leanatlas_force_kb_") as td:
        base = Path(td)
        out_default = base / "default.json"
        out_high = base / "high_no_force.json"
        out_forced = base / "high_force.json"
        force_file = base / "force_deposit.json"

        # Discover one real pattern from fixtures.
        p0 = _run(
            [
                sys.executable,
                str(KB_TOOL),
                "--in",
                str(KB_FIXTURE),
                "--out",
                str(out_default),
            ]
        )
        _assert(p0.returncode == 0, f"kb miner default run failed: {p0.stdout}")
        default_obj = _read_json(out_default)
        sugg = list(default_obj.get("suggestions") or [])
        _assert(sugg, "fixture must produce at least one baseline kb suggestion")
        pat = sugg[0].get("pattern") or {}
        fam = str(pat.get("triage_family") or "")
        code = str(pat.get("triage_code") or "")
        stage = str(pat.get("failure_stage") or "")
        _assert(fam and code, "baseline suggestion missing triage family/code")

        # High thresholds should remove normal suggestions.
        p1 = _run(
            [
                sys.executable,
                str(KB_TOOL),
                "--in",
                str(KB_FIXTURE),
                "--out",
                str(out_high),
                "--min_runs",
                "99",
                "--min_problems",
                "99",
            ]
        )
        _assert(p1.returncode == 0, f"kb miner high-threshold run failed: {p1.stdout}")
        high_obj = _read_json(out_high)
        _assert(len(list(high_obj.get("suggestions") or [])) == 0, "high-threshold run should produce zero suggestions")

        # Force file should recover one suggestion even below threshold.
        force_obj = {
            "schema": "leanatlas.force_deposit",
            "schema_version": "0.1.0",
            "tools": [],
            "skills": [
                {
                    "triage_family": fam,
                    "triage_code": code,
                    "failure_stage": stage,
                    "enabled": True,
                    "reason": "human_requested_force_deposit_for_skills",
                }
            ],
            "feedback": [],
        }
        force_file.write_text(json.dumps(force_obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        p2 = _run(
            [
                sys.executable,
                str(KB_TOOL),
                "--in",
                str(KB_FIXTURE),
                "--out",
                str(out_forced),
                "--min_runs",
                "99",
                "--min_problems",
                "99",
                "--force-file",
                str(force_file),
            ]
        )
        _assert(p2.returncode == 0, f"kb miner forced run failed: {p2.stdout}")
        forced_obj = _read_json(out_forced)
        forced_sugg = list(forced_obj.get("suggestions") or [])
        _assert(forced_sugg, "force-deposit should produce suggestion below threshold")
        _assert(
            any(bool((x.get("force_deposit") or {}).get("enabled")) for x in forced_sugg),
            "forced suggestion must carry force_deposit.enabled=true",
        )


def _check_feedback_force_policy() -> None:
    _assert(FB_TOOL.exists(), "missing tools/feedback/mine_chat_feedback.py")
    with tempfile.TemporaryDirectory(prefix="leanatlas_force_feedback_") as td:
        base = Path(td)
        inbox = base / "inbox"
        out = base / "out.json"
        force_file = base / "force_deposit.json"
        inbox.mkdir(parents=True, exist_ok=True)

        force_obj = {
            "schema": "leanatlas.force_deposit",
            "schema_version": "0.1.0",
            "tools": [],
            "skills": [],
            "feedback": [
                {
                    "enabled": True,
                    "text": "Force deposit this feedback item into tests bucket.",
                    "triage_class": "bug_missing_test",
                    "severity": "S1",
                    "target_bucket": "tests",
                    "justification": "Human explicitly requested immediate deposition.",
                }
            ],
        }
        force_file.write_text(json.dumps(force_obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        p = _run(
            [
                sys.executable,
                str(FB_TOOL),
                "--in-root",
                str(inbox),
                "--out",
                str(out),
                "--force-file",
                str(force_file),
            ]
        )
        _assert(p.returncode == 0, f"feedback miner forced run failed: {p.stdout}")
        obj = _read_json(out)
        items = list(obj.get("items") or [])
        _assert(len(items) == 1, f"expected 1 forced feedback item, got {len(items)}")
        item = items[0]
        _assert(str(item.get("triage_class")) == "bug_missing_test", "forced triage_class not applied")
        _assert(str(item.get("severity")) == "S1", "forced severity not applied")
        _assert(str(item.get("target_bucket")) == "tests", "forced target_bucket not applied")


def main() -> int:
    _check_promotion_force_policy()
    _check_kb_force_policy()
    _check_feedback_force_policy()
    print("[force-deposit-policy][PASS]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as ex:
        print(f"[force-deposit-policy][FAIL] {ex}")
        raise SystemExit(1)
