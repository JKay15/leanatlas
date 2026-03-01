#!/usr/bin/env python3
"""Deterministic dummy agent for TDD of the Phase6 AgentEval pipeline.

Why this exists:
- CI cannot run Codex.
- We still need an end-to-end executable harness that exercises:
  run_pack / run_scenario (run mode) -> reports -> graders.

This script reads the run CONTEXT.json (path passed via env or adjacent to PROMPT.md)
and writes schema-valid artifacts into:
  Problems/<problem_slug>/Reports/<run_id>/

It also edits Problems/<problem_slug>/Proof.lean for SUCCESS runs to remove `sorry`
(so graders can enforce a strict no-sorry rule in a runner-only environment).

IMPORTANT: This is *not* a mathematical prover. It is a pipeline fixture.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


# Ensure repo root is on sys.path so we can import run_cmd.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.workflow.run_cmd import run_cmd


def sha256_text(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_template(rel: str) -> Dict[str, Any]:
    p = REPO_ROOT / rel
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    # Workspace root
    ws = os.environ.get("LEANATLAS_WORKSPACE") or os.environ.get("LEANATLAS_EVAL_WORKSPACE")
    if not ws:
        print("[dummy_agent][FAIL] Missing LEANATLAS_WORKSPACE", file=sys.stderr)
        return 2
    workspace = Path(ws)

    # Context location
    ctx_env = os.environ.get("LEANATLAS_CONTEXT_PATH") or os.environ.get("LEANATLAS_EVAL_CONTEXT")
    prompt_env = os.environ.get("LEANATLAS_PROMPT_PATH") or os.environ.get("LEANATLAS_EVAL_PROMPT")
    ctx_path: Path
    if ctx_env:
        ctx_path = Path(ctx_env)
    elif prompt_env:
        ctx_path = Path(prompt_env).parent / "CONTEXT.json"
    else:
        print("[dummy_agent][FAIL] Missing context path (LEANATLAS_CONTEXT_PATH or PROMPT)", file=sys.stderr)
        return 2

    if not ctx_path.exists():
        print(f"[dummy_agent][FAIL] CONTEXT.json not found: {ctx_path}", file=sys.stderr)
        return 2

    ctx = load_json(ctx_path)
    if not isinstance(ctx, dict):
        print("[dummy_agent][FAIL] CONTEXT.json must be an object", file=sys.stderr)
        return 2

    problem_slug = str(ctx.get("problem_slug", ""))
    run_id = os.environ.get("LEANATLAS_RUN_ID") or os.environ.get("LEANATLAS_EVAL_RUN_ID") or str(ctx.get("run_id", ""))
    expected = ctx.get("expected", {}) if isinstance(ctx.get("expected"), dict) else {}
    expected_status = expected.get("final_status")

    if not problem_slug or not run_id:
        print("[dummy_agent][FAIL] CONTEXT missing problem_slug or run_id", file=sys.stderr)
        return 2

    report_dir = workspace / "Problems" / problem_slug / "Reports" / run_id
    report_dir.mkdir(parents=True, exist_ok=True)

    # 1) Runner evidence span: run a trivial command to generate exec span + stdout/stderr files.
    cmd_res = run_cmd(
        cmd=["bash", "-lc", "echo dummy_agent"],
        cwd=workspace,
        log_dir=report_dir / "Cmd",
        label="dummy_agent",
        env=None,
        timeout_s=10,
        capture_text=False,
    )
    exec_span = cmd_res.span

    # 2) AttemptLog.jsonl
    attempt_line = load_template("tests/schema/fixtures/positive/attemptlog_min.json")
    attempt_line["problem_slug"] = problem_slug
    attempt_line["run_id"] = run_id
    attempt_line["attempt_index"] = 0
    attempt_line["exec_spans"] = [exec_span]
    # Keep patch_scope as OK (fixture already OK)
    (report_dir / "AttemptLog.jsonl").write_text(json.dumps(attempt_line, sort_keys=True) + "\n", encoding="utf-8")

    # 3) RetrievalTrace.json
    rt = load_template("tests/schema/fixtures/positive/retrievaltrace_min.json")
    rt["problem_slug"] = problem_slug
    rt["run_id"] = run_id
    write_json(report_dir / "RetrievalTrace.json", rt)

    # 4) pins_used.json (no schema; grader only requires presence)
    pins_path = REPO_ROOT / "tools" / "deps" / "pins.json"
    pins_sha = sha256_file(pins_path) if pins_path.exists() else sha256_text("missing")
    write_json(report_dir / "pins_used.json", {"pins_path": "tools/deps/pins.json", "pins_sha256": pins_sha})

    # 5) RunReport.json
    if expected_status == "SUCCESS":
        rr = load_template("tests/schema/fixtures/positive/runreport_success_min.json")
        rr["problem_slug"] = problem_slug
        rr["run_id"] = run_id
        rr["status"] = "SUCCESS"
        # Ensure environment stamp exists (template already has it).
        write_json(report_dir / "RunReport.json", rr)
    else:
        rr = load_template("tests/schema/fixtures/positive/runreport_triaged_with_refs.json")
        rr["problem_slug"] = problem_slug
        rr["run_id"] = run_id
        rr["status"] = "TRIAGED"
        tri = rr.get("triage", {}) if isinstance(rr.get("triage"), dict) else {}
        cat = tri.get("category", {}) if isinstance(tri.get("category"), dict) else {}
        fam = expected.get("triage_family")
        code = expected.get("triage_code")
        if fam:
            cat["family"] = fam
        if code:
            cat["code"] = code
        tri["category"] = cat
        rr["triage"] = tri
        write_json(report_dir / "RunReport.json", rr)

    # 6) For SUCCESS runs, patch Proof.lean to remove 'sorry' (so graders can enforce no-sorry).
    if expected_status == "SUCCESS":
        proof_path = workspace / "Problems" / problem_slug / "Proof.lean"
        if proof_path.exists():
            if problem_slug == "mk_convex_log_barrier":
                proof_path.write_text(
                    "\n".join(
                        [
                            "import Problems.mk_convex_log_barrier.Spec",
                            "",
                            "namespace Problems.mk_convex_log_barrier",
                            "",
                            "/-- Main proof entrypoint. -/",
                            "theorem main : Goal := by",
                            "  intro x hx",
                            "  simpa using Real.log_le_sub_one_of_pos hx",
                            "",
                            "end Problems.mk_convex_log_barrier",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )
            else:
                txt = proof_path.read_text(encoding="utf-8", errors="replace")
                txt = txt.replace("sorry", "by\n  -- dummy_agent removed sorry for pipeline TDD\n  trivial")
                txt = txt.replace("admit", "trivial")
                proof_path.write_text(txt, encoding="utf-8")

    print(f"[dummy_agent][OK] wrote reports to {report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
