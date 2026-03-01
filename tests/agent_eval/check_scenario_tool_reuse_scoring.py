#!/usr/bin/env python3
"""Unit-style e2e: scenario grader computes deterministic tool-reuse metrics.

We build a tiny synthetic scenario eval directory (no Lean build, no agent run)
that contains:
  - a baseline tool surface
  - a maintainer step that introduces a toolbox module
  - a run_task step whose Proof imports Toolbox.Imports, which imports the new module

Then we run tools/agent_eval/grade_scenario.py and assert:
  - scenario passes
  - tool_reuse.metrics.reuse_rate == 1.0
  - introduced module is marked reused by the later run_task
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    tmp_root = ROOT / "artifacts" / "_test_tmp_scenario_tool_reuse"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    eval_dir = tmp_root / "eval"

    # ------------------------------------------------------------------
    # Plan.json with 2 steps: overlay adds tool, run_task uses it.
    # ------------------------------------------------------------------
    plan = {
        "schema": "leanatlas.agent_eval_scenario_plan",
        "schema_version": "0.1.0",
        "eval_id": "test_tool_reuse",
        "scenario_id": "tool_reuse_synth_v0",
        "scenario_class": "SYNTH",
        "stamp": "2026-02-24T00-00-00Z",
        "scenario_path": "tests/agent_eval/scenarios/synth/tool_reuse.yaml",
        "steps": [
            {"step_index": 0, "kind": "apply_overlay", "label": "add_tool", "data": {}},
            {"step_index": 1, "kind": "run_task", "label": "use_tool", "data": {}},
        ],
    }
    _write_json(eval_dir / "Plan.json", plan)

    # ------------------------------------------------------------------
    # Workspace: LeanAtlas.Toolbox.Imports imports the new Util module.
    # ------------------------------------------------------------------
    ws = eval_dir / "workspace"
    (ws / "LeanAtlas" / "Toolbox" / "Test").mkdir(parents=True, exist_ok=True)
    (ws / "LeanAtlas" / "Toolbox" / "Imports.lean").write_text(
        "import LeanAtlas.Toolbox.Test.Util\n\n-- synthetic\n",
        encoding="utf-8",
    )
    (ws / "LeanAtlas" / "Toolbox" / "Test" / "Util.lean").write_text(
        "namespace LeanAtlas.Toolbox.Test\n\n-- synthetic tool decl\n\naxiom utilLemma : True\n\nend LeanAtlas.Toolbox.Test\n",
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # Tool-surface snapshots
    # baseline: only Imports exists
    # step0/step1: Imports + Util exists
    # ------------------------------------------------------------------
    baseline = {
        "schema": "leanatlas.agent_eval_tool_surface_snapshot",
        "schema_version": "0.1.0",
        "roots": ["LeanAtlas/Toolbox", "LeanAtlas/Incubator/Seeds", "LeanAtlas/Incubator/External"],
        "tool_files": ["LeanAtlas/Toolbox/Imports.lean"],
        "tool_modules": ["LeanAtlas.Toolbox.Imports"],
    }
    _write_json(eval_dir / "BaselineToolSurface.json", baseline)

    after = {
        **baseline,
        "tool_files": ["LeanAtlas/Toolbox/Imports.lean", "LeanAtlas/Toolbox/Test/Util.lean"],
        "tool_modules": ["LeanAtlas.Toolbox.Imports", "LeanAtlas.Toolbox.Test.Util"],
    }

    runs = eval_dir / "runs"
    step0 = runs / "0000_add_tool"
    step1 = runs / "0001_use_tool"
    _write_json(step0 / "ToolSurface.json", after)
    _write_json(step1 / "ToolSurface.json", after)

    # ------------------------------------------------------------------
    # run_task artifacts (snapshot/Reports/*)
    # ------------------------------------------------------------------
    run_id = "run_dummy_0001"
    prob = "prob_use_util"

    # CONTEXT.json (minimal fields grade_scenario reads)
    ctx = {
        "scenario_id": plan["scenario_id"],
        "scenario_class": plan["scenario_class"],
        "stamp": plan["stamp"],
        "step_index": 1,
        "step_label": "use_tool",
        "run_id": run_id,
        "task_id": "synth",
        "variant_id": "v0",
        "problem_slug": prob,
        "expected": {"final_status": "SUCCESS"},
        "tool_delta": {},
        "skill_delta": {},
        "keywords": [],
        "domain_hint": {},
    }
    _write_json(step1 / "CONTEXT.json", ctx)
    (step1 / "PROMPT.md").write_text("# synthetic prompt\n", encoding="utf-8")

    snap = step1 / "snapshot"
    reports = snap / "Reports" / run_id
    reports.mkdir(parents=True, exist_ok=True)

    # Minimal problem files (imports drive tool reuse closure)
    (snap / "Spec.lean").write_text("-- spec\n", encoding="utf-8")
    (snap / "Cache.lean").write_text("-- cache\n", encoding="utf-8")
    (snap / "Scratch.lean").write_text("-- scratch\n", encoding="utf-8")
    (snap / "Proof.lean").write_text(
        "import LeanAtlas.Toolbox.Imports\n\n-- use the tool decl name\n#check LeanAtlas.Toolbox.Test.utilLemma\n",
        encoding="utf-8",
    )

    # Runner-captured exec evidence files (not validated by grade_scenario, but schema requires sha fields).
    stdout_bytes = b"ok\n"
    stderr_bytes = b""
    (step1 / "exec").mkdir(parents=True, exist_ok=True)
    (step1 / "exec" / "stdout.txt").write_bytes(stdout_bytes)
    (step1 / "exec" / "stderr.txt").write_bytes(stderr_bytes)
    stdout_sha = _sha256_bytes(stdout_bytes)
    stderr_sha = _sha256_bytes(stderr_bytes)

    attempt_line = {
        "schema": "leanatlas.attempt_log_line",
        "schema_version": "0.1.0",
        "run_id": run_id,
        "problem_slug": prob,
        "attempt_index": 0,
        "touched_files": [f"Problems/{prob}/Proof.lean"],
        "patch_scope": {"verdict": "ALLOW", "primary_reason_code": "OK", "violations": [], "ignored_paths": []},
        "suspected_category": {"family": "UNKNOWN", "code": "UNKNOWN"},
        "signals": {
            "diag_fingerprint": "00000000",
            "diag_changed": False,
            "new_retrieval_hit": False,
            "imports_changed": False,
            "stagnant": False,
            "error_outside_problem": False,
        },
        "stages": {"retrieval": {"status": "OK"}, "build": {"status": "OK"}, "verify": {"status": "OK"}},
        "exec_spans": [
            {
                "id": "span0",
                "cmd": ["bash", "-lc", "true"],
                "cwd": "workspace",
                "exit_code": 0,
                "stdout_path": "exec/stdout.txt",
                "stderr_path": "exec/stderr.txt",
                "stdout_sha256": stdout_sha,
                "stderr_sha256": stderr_sha,
                "duration_ms": 1,
            }
        ],
        "judge": {"decision": "SUCCESS", "reason_code": "SUCCESS", "stagnant_count": 0, "K": 5, "budget_exceeded": []},
        "budget": {
            "limits": {"max_attempts": 1, "max_steps": 10, "max_external_queries": 0, "max_wall_time_ms": 1000},
            "counters": {"attempts_used": 1, "steps_used": 1, "external_queries_used": 0, "wall_time_ms": 1},
        },
    }
    (reports / "AttemptLog.jsonl").write_text(json.dumps(attempt_line) + "\n", encoding="utf-8")

    retrieval = {
        "schema": "leanatlas.retrieval_trace",
        "schema_version": "0.1.0",
        "run_id": run_id,
        "problem_slug": prob,
        "domain": {"input_codes": [], "expanded_codes": []},
        "budget": {"max_external_queries": 0, "max_steps": 5, "used_external_queries": 0, "used_steps": 0},
        "steps": [],
    }
    _write_json(reports / "RetrievalTrace.json", retrieval)
    _write_json(
        reports / "pins_used.json",
        {
            "schema": "leanatlas.pins_used",
            "schema_version": "0.1.0",
            "generated_by": "tests.synthetic",
            "pins_path": "tools/deps/pins.json",
            "pins_sha256": "0" * 64,
        },
    )

    run_report = {
        "schema": "leanatlas.run_report",
        "schema_version": "0.1.0",
        "run_id": run_id,
        "problem_slug": prob,
        "status": "SUCCESS",
        "mode": "OPERATOR",
        "context": {
            "git_sha": "deadbeef0",
            "lean_toolchain": "leanprover/lean4:v4.24.0",
            "mathlib_rev": "dummy",
            "tools": {
                "environment_stamp": {
                    "lean_toolchain": "leanprover/lean4:v4.24.0",
                    "mathlib_rev": "dummy",
                    "pins_sha256": "0" * 64,
                    "pinned_tools": {},
                }
            },
        },
        "summary": {"title": "ok", "one_line": "ok"},
        "entrypoints": {
            "files": {
                "spec": f"Problems/{prob}/Spec.lean",
                "proof": f"Problems/{prob}/Proof.lean",
                "cache": f"Problems/{prob}/Cache.lean",
                "scratch": f"Problems/{prob}/Scratch.lean",
            }
        },
        "targets": [{"id": "t0", "role": "MAIN", "decl": "Synth.main", "file": f"Problems/{prob}/Spec.lean"}],
        "stages": {"retrieval": {"status": "OK"}, "build": {"status": "OK"}, "verify": {"status": "OK"}},
        "diagnostics": [],
        "retrieval_trace_path": "RetrievalTrace.json",
        "verification": {"no_sorry": True, "axioms": [], "warnings": []},
    }
    _write_json(reports / "RunReport.json", run_report)

    # ------------------------------------------------------------------
    # Run the grader
    # ------------------------------------------------------------------
    cmd = [os.fspath(ROOT / "tools" / "agent_eval" / "grade_scenario.py"), "--eval-dir", os.fspath(eval_dir)]
    proc = subprocess.run([sys.executable, *cmd], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(f"[FAIL] grade_scenario returned {proc.returncode}")

    rep = json.loads((eval_dir / "ScenarioEvalReport.json").read_text(encoding="utf-8"))
    assert rep.get("passed") is True, f"scenario should pass, got: {rep.get('passed')}"
    tr = rep.get("tool_reuse")
    assert isinstance(tr, dict), "tool_reuse report missing"
    metrics = tr.get("metrics", {})
    assert metrics.get("introduced_total") == 1, f"expected 1 introduced module, got {metrics}"
    assert metrics.get("reused_total") == 1, f"expected 1 reused module, got {metrics}"
    assert abs(float(metrics.get("reuse_rate")) - 1.0) < 1e-9, f"expected reuse_rate 1.0, got {metrics}"

    intro = tr.get("introduced_modules", [])
    assert len(intro) == 1, f"expected 1 introduced entry, got {intro}"
    assert intro[0].get("module") == "LeanAtlas.Toolbox.Test.Util"
    assert intro[0].get("reused") is True
    assert "0001_use_tool" in intro[0].get("reused_by_steps", [])

    print("[scenario-tool-reuse][OK] deterministic reuse scoring works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
