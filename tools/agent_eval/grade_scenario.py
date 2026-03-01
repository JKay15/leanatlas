#!/usr/bin/env python3
"""Deterministic grader for Phase6.2 AgentEval scenarios.

Scenario eval dirs are produced by:
  tools/agent_eval/run_scenario.py --mode run

Layout (minimal):
  <eval_dir>/
    Plan.json
    runs/<step_uid>/
      CONTEXT.json
      PROMPT.md
      snapshot/
        Proof.lean
        Reports/<run_id>/RunReport.json
        Reports/<run_id>/AttemptLog.jsonl
        Reports/<run_id>/RetrievalTrace.json
        Reports/<run_id>/pins_used.json

This grader is deliberately **mechanical**:
- Validate required artifacts exist.
- Validate JSON schemas.
- Compare RunReport status/triage against the expected fields in CONTEXT.json.
- Enforce evidence-chain invariants (AttemptLog, patch-scope not violated, env-stamp present).

It produces:
  runs/<step_uid>/AgentEvalReport.json
  ScenarioEvalReport.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import jsonschema


SCHEMA_AGENT_REPORT = REPO_ROOT / "docs" / "schemas" / "AgentEvalReport.schema.json"
SCHEMA_SCENARIO_REPORT = REPO_ROOT / "docs" / "schemas" / "AgentEvalScenarioReport.schema.json"
SCHEMA_RUNREPORT = REPO_ROOT / "docs" / "schemas" / "RunReport.schema.json"
SCHEMA_ATTEMPT_LINE = REPO_ROOT / "docs" / "schemas" / "AttemptLogLine.schema.json"
SCHEMA_RETRIEVAL = REPO_ROOT / "docs" / "schemas" / "RetrievalTrace.schema.json"
SCHEMA_PINS_USED = REPO_ROOT / "docs" / "schemas" / "PinsUsed.schema.json"


def _module_name_from_relpath(rel_lean: Path) -> str:
    p = rel_lean.with_suffix("")
    return ".".join(p.parts)


_IMPORT_RE = re.compile(r"^\s*import\s+(?P<rest>.+)$")


def _strip_lean_comment(s: str) -> str:
    """Strip single-line Lean comments (`-- ...`)."""
    if "--" in s:
        return s.split("--", 1)[0]
    return s


def _parse_imports(text: str) -> List[str]:
    """Parse `import` lines and return a list of module names.

    Lean allows multiple module ids after a single `import` (Lean3 style),
    and Lean4 keeps compatibility in practice.
    We keep this parser intentionally simple and deterministic.
    """
    out: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("--"):
            continue
        m = _IMPORT_RE.match(line)
        if not m:
            continue
        rest = _strip_lean_comment(m.group("rest")).strip()
        if not rest:
            continue
        for tok in rest.split():
            if tok:
                out.append(tok.strip())
    return out


def _build_local_import_graph(workspace_root: Path) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """Build a local import graph from sources under the workspace.

    Only includes modules that have source files in this workspace.
    External modules (mathlib, std, etc.) are treated as leaves.
    """

    module_files: Dict[str, Path] = {}

    # Prefer LeanAtlas/**, but include root LeanAtlas.lean if present.
    leanatlas_root = workspace_root / "LeanAtlas"
    if leanatlas_root.exists():
        for p in leanatlas_root.rglob("*.lean"):
            rel = p.relative_to(workspace_root)
            module_files[_module_name_from_relpath(rel)] = p

    root_leanatlas = workspace_root / "LeanAtlas.lean"
    if root_leanatlas.exists():
        module_files[_module_name_from_relpath(root_leanatlas.relative_to(workspace_root))] = root_leanatlas

    modules = set(module_files.keys())
    graph: Dict[str, Set[str]] = {m: set() for m in modules}

    for mod, path in module_files.items():
        try:
            txt = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        imps = _parse_imports(txt)
        for imp in imps:
            if imp in modules:
                graph[mod].add(imp)

    return graph, modules


def _reachable_modules(roots: Iterable[str], graph: Dict[str, Set[str]]) -> Set[str]:
    seen: Set[str] = set()
    stack: List[str] = list(roots)
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        for nxt in graph.get(m, set()):
            if nxt not in seen:
                stack.append(nxt)
    return seen


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_schema(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(obj: Any, schema: Dict[str, Any]) -> List[str]:
    v = jsonschema.Draft202012Validator(schema)
    errs = sorted(v.iter_errors(obj), key=lambda e: list(e.absolute_path))
    msgs: List[str] = []
    for e in errs:
        loc = "/" + "/".join(str(p) for p in e.absolute_path)
        msgs.append(f"{loc}: {e.message}")
    return msgs


def _rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except Exception:
        return str(p)


def _mk_check(check_id: str, passed: bool, evidence: List[str], notes: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {"id": check_id, "passed": bool(passed), "evidence": list(evidence)}
    if notes:
        out["notes"] = notes
    return out


def _read_jsonl(path: Path, max_lines: int = 200) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Return (rows, errors)."""
    rows: List[Dict[str, Any]] = []
    errs: List[str] = []
    if not path.exists():
        return rows, ["missing"]
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()[:max_lines]):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
            else:
                errs.append(f"line[{i}] not an object")
        except Exception as e:
            errs.append(f"line[{i}] json error: {e}")
    if not rows:
        errs.append("no lines")
    return rows, errs


def _no_sorry(proof_path: Path) -> Tuple[bool, str]:
    if not proof_path.exists():
        return False, "missing Proof.lean"
    txt = proof_path.read_text(encoding="utf-8", errors="replace")
    bad = []
    if "sorry" in txt:
        bad.append("contains 'sorry'")
    # Lean has an `admit` shorthand in some setups; treat it as disallowed too.
    if "admit" in txt:
        bad.append("contains 'admit'")
    return (len(bad) == 0), ("; ".join(bad))


def _locate_report_dir(run_dir: Path, run_id: str) -> Path:
    """Find snapshot/Reports/<run_id>.

    If run_id isn't present (agent bug), fallback to the only child dir.
    """
    base = run_dir / "snapshot" / "Reports"
    if not base.exists():
        return base / run_id
    cand = base / run_id
    if cand.exists() and cand.is_dir():
        return cand
    kids = [p for p in base.iterdir() if p.is_dir()]
    if len(kids) == 1:
        return kids[0]
    return cand


def grade_one_run_task(
    *,
    eval_dir: Path,
    run_dir: Path,
    plan_eval_id: str,
    scenario_id: str,
    stamp: str,
    attempt_schema: Dict[str, Any],
    retrieval_schema: Dict[str, Any],
    pins_used_schema: Dict[str, Any],
    runreport_schema: Dict[str, Any],
    evalreport_schema: Dict[str, Any],
) -> Tuple[Dict[str, Any], bool]:
    """Grade a single run_task step directory."""

    checks: List[Dict[str, Any]] = []
    signals: Dict[str, float] = {}
    artifacts: List[str] = []
    notes: List[str] = []

    prompt_path = run_dir / "PROMPT.md"
    ctx_path = run_dir / "CONTEXT.json"

    checks.append(_mk_check("prompt_exists", prompt_path.exists(), [_rel(eval_dir, prompt_path)]))
    checks.append(_mk_check("context_exists", ctx_path.exists(), [_rel(eval_dir, ctx_path)]))

    if not ctx_path.exists():
        report = {
            "schema": "leanatlas.agent_eval_report",
            "schema_version": "0.1.0",
            "eval_id": f"{plan_eval_id}__{run_dir.name}",
            "task_id": "",
            "variant_id": "",
            "stamp": stamp,
            "passed": False,
            "deterministic_checks": checks,
            "signals": {},
            "artifacts": [],
            "notes": ["missing CONTEXT.json"],
        }
        errs = _validate(report, evalreport_schema)
        if errs:
            report["notes"] = report.get("notes", []) + ["INTERNAL: AgentEvalReport schema invalid", *errs]
        return report, False

    ctx = _load_json(ctx_path)
    task_id = str(ctx.get("task_id", ""))
    variant_id = str(ctx.get("variant_id", ""))
    problem_slug = str(ctx.get("problem_slug", ""))
    run_id = str(ctx.get("run_id", ""))
    expected = ctx.get("expected", {}) if isinstance(ctx, dict) else {}
    if not isinstance(expected, dict):
        expected = {}

    expected_status = expected.get("final_status")
    exp_fam = expected.get("triage_family")
    exp_code = expected.get("triage_code")

    reports_dir = _locate_report_dir(run_dir, run_id)
    runreport_path = reports_dir / "RunReport.json"
    attemptlog_path = reports_dir / "AttemptLog.jsonl"
    retrieval_path = reports_dir / "RetrievalTrace.json"
    pins_path = reports_dir / "pins_used.json"
    proof_path = run_dir / "snapshot" / "Proof.lean"

    artifacts.extend(
        [
            _rel(eval_dir, p)
            for p in [
                reports_dir,
                runreport_path,
                attemptlog_path,
                retrieval_path,
                pins_path,
                proof_path,
            ]
            if p.exists()
        ]
    )

    # RunReport
    checks.append(_mk_check("runreport_exists", runreport_path.exists(), [_rel(eval_dir, runreport_path)]))
    runreport_obj: Optional[Dict[str, Any]] = None
    if runreport_path.exists():
        try:
            runreport_obj = _load_json(runreport_path)
            errs = _validate(runreport_obj, runreport_schema)
            checks.append(
                _mk_check(
                    "runreport_schema_valid",
                    len(errs) == 0,
                    [_rel(eval_dir, runreport_path)],
                    "\n".join(errs[:6]) if errs else "",
                )
            )
        except Exception as e:
            checks.append(_mk_check("runreport_schema_valid", False, [_rel(eval_dir, runreport_path)], f"exception: {e}"))
    else:
        checks.append(_mk_check("runreport_schema_valid", False, [_rel(eval_dir, runreport_path)], "missing"))

    # AttemptLog
    checks.append(_mk_check("attemptlog_exists", attemptlog_path.exists(), [_rel(eval_dir, attemptlog_path)]))
    attempt_lines: List[Dict[str, Any]] = []
    if attemptlog_path.exists():
        rows, jsonl_errs = _read_jsonl(attemptlog_path)
        attempt_lines = rows
        signals["attempt_log_lines"] = float(len(attempt_lines))
        if jsonl_errs and jsonl_errs != ["no lines"]:
            notes.append("AttemptLog.jsonl parse issues: " + "; ".join(jsonl_errs[:3]))

        # schema validate first N
        sch_errs: List[str] = []
        for i, row in enumerate(attempt_lines[:200]):
            row_errs = _validate(row, attempt_schema)
            sch_errs.extend([f"line[{i}] {e}" for e in row_errs])
        ok = (len(sch_errs) == 0) and (len(attempt_lines) > 0)
        checks.append(_mk_check("attemptlog_schema_valid", ok, [_rel(eval_dir, attemptlog_path)], "\n".join(sch_errs[:6]) if sch_errs else ""))
    else:
        checks.append(_mk_check("attemptlog_schema_valid", False, [_rel(eval_dir, attemptlog_path)], "missing"))

    # Patch scope not violated (Phase5+): AttemptLogLine.patch_scope.verdict must be ALLOW.
    ps_ok = True
    for row in attempt_lines:
        ps = row.get("patch_scope")
        if isinstance(ps, dict) and ps.get("verdict") == "DISALLOW":
            ps_ok = False
            break
    checks.append(_mk_check("patch_scope_not_violated", ps_ok, [_rel(eval_dir, attemptlog_path)] if attemptlog_path.exists() else []))
    signals["patch_scope_ok"] = 1.0 if ps_ok else 0.0

    # RetrievalTrace
    checks.append(_mk_check("retrieval_trace_exists", retrieval_path.exists(), [_rel(eval_dir, retrieval_path)]))
    signals["has_retrieval_trace"] = 1.0 if retrieval_path.exists() else 0.0
    if retrieval_path.exists():
        try:
            rt = _load_json(retrieval_path)
            rerrs = _validate(rt, retrieval_schema)
            checks.append(_mk_check("retrieval_trace_schema_valid", len(rerrs) == 0, [_rel(eval_dir, retrieval_path)], "\n".join(rerrs[:6]) if rerrs else ""))
        except Exception as e:
            checks.append(_mk_check("retrieval_trace_schema_valid", False, [_rel(eval_dir, retrieval_path)], f"exception: {e}"))
    else:
        checks.append(_mk_check("retrieval_trace_schema_valid", False, [_rel(eval_dir, retrieval_path)], "missing"))

    # pins
    checks.append(_mk_check("pins_used_present", pins_path.exists(), [_rel(eval_dir, pins_path)]))
    if pins_path.exists():
        try:
            pins_obj = _load_json(pins_path)
            pins_errs = _validate(pins_obj, pins_used_schema)
            checks.append(
                _mk_check(
                    "pins_used_schema_valid",
                    len(pins_errs) == 0,
                    [_rel(eval_dir, pins_path)],
                    "\n".join(pins_errs[:6]) if pins_errs else "",
                )
            )
        except Exception as e:
            checks.append(_mk_check("pins_used_schema_valid", False, [_rel(eval_dir, pins_path)], f"exception: {e}"))
    else:
        checks.append(_mk_check("pins_used_schema_valid", False, [_rel(eval_dir, pins_path)], "missing"))

    # Compare expected status / triage
    status_ok = False
    triage_ok = True
    env_ok = False
    actual_status = None
    if runreport_obj and isinstance(runreport_obj, dict):
        actual_status = runreport_obj.get("status")
        status_ok = (expected_status is None) or (actual_status == expected_status)
        checks.append(
            _mk_check(
                "status_matches_expected",
                status_ok,
                [_rel(eval_dir, runreport_path)],
                f"expected={expected_status} actual={actual_status}",
            )
        )

        if actual_status == "TRIAGED":
            triage = runreport_obj.get("triage", {})
            cat = triage.get("category", {}) if isinstance(triage, dict) else {}
            fam = cat.get("family") if isinstance(cat, dict) else None
            code = cat.get("code") if isinstance(cat, dict) else None
            triage_ok = True
            if exp_fam and fam != exp_fam:
                triage_ok = False
            if exp_code and code != exp_code:
                triage_ok = False
            checks.append(
                _mk_check(
                    "triage_matches_expected",
                    triage_ok,
                    [_rel(eval_dir, runreport_path)],
                    f"expected_family={exp_fam} actual_family={fam} expected_code={exp_code} actual_code={code}",
                )
            )
        else:
            checks.append(_mk_check("triage_matches_expected", True, []))

        # Env stamp present (evidence-chain)
        ctx0 = runreport_obj.get("context", {})
        tools = ctx0.get("tools", {}) if isinstance(ctx0, dict) else {}
        env_stamp = tools.get("environment_stamp") if isinstance(tools, dict) else None
        env_ok = env_stamp is not None
        checks.append(_mk_check("env_stamp_present", env_ok, [_rel(eval_dir, runreport_path)]))
    else:
        checks.append(_mk_check("status_matches_expected", False, [_rel(eval_dir, runreport_path)], "missing RunReport"))
        checks.append(_mk_check("triage_matches_expected", False, [_rel(eval_dir, runreport_path)], "missing RunReport"))
        checks.append(_mk_check("env_stamp_present", False, [_rel(eval_dir, runreport_path)], "missing RunReport"))

    # no_sorry only required for SUCCESS expectations
    if expected_status == "SUCCESS":
        ok, msg = _no_sorry(proof_path)
        checks.append(_mk_check("no_sorry", ok, [_rel(eval_dir, proof_path)], msg))
        signals["no_sorry_ok"] = 1.0 if ok else 0.0
    else:
        checks.append(_mk_check("no_sorry", True, []))
        signals["no_sorry_ok"] = 1.0

    passed = all(c.get("passed") is True for c in checks)

    report: Dict[str, Any] = {
        "schema": "leanatlas.agent_eval_report",
        "schema_version": "0.1.0",
        "eval_id": f"{plan_eval_id}__{scenario_id}__{run_dir.name}",
        "task_id": task_id,
        "variant_id": variant_id,
        "stamp": stamp,
        "passed": bool(passed),
        "deterministic_checks": checks,
        "signals": signals,
        "artifacts": artifacts,
        "notes": notes,
    }

    rerrs = _validate(report, evalreport_schema)
    if rerrs:
        report["passed"] = False
        report["notes"] = report.get("notes", []) + ["INTERNAL: AgentEvalReport schema invalid", *rerrs]
        passed = False

    return report, bool(passed)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--eval-dir",
        required=True,
        help="Scenario eval dir: artifacts/agent_evals/scenarios/<scenario_id>/<stamp>",
    )
    args = ap.parse_args(argv)

    eval_dir = Path(args.eval_dir)
    plan_path = eval_dir / "Plan.json"
    if not plan_path.exists():
        plan_path = eval_dir / "ScenarioPlan.json"  # backwards-compat
    if not plan_path.exists():
        raise FileNotFoundError(f"Missing Plan.json (or ScenarioPlan.json) in {eval_dir}")

    plan = _load_json(plan_path)
    plan_eval_id = str(plan.get("eval_id"))
    scenario_id = str(plan.get("scenario_id"))
    stamp = str(plan.get("stamp"))

    runreport_schema = _load_schema(SCHEMA_RUNREPORT)
    attempt_schema = _load_schema(SCHEMA_ATTEMPT_LINE)
    retrieval_schema = _load_schema(SCHEMA_RETRIEVAL)
    pins_used_schema = _load_schema(SCHEMA_PINS_USED)
    evalreport_schema = _load_schema(SCHEMA_AGENT_REPORT)
    scenario_schema = _load_schema(SCHEMA_SCENARIO_REPORT)

    runs_root = eval_dir / "runs"
    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError("Plan.json steps must be a list")

    internal_errors: List[str] = []
    step_results: List[Dict[str, Any]] = []
    scenario_passed = True

    for step in steps:
        if not isinstance(step, dict):
            continue
        kind = str(step.get("kind"))
        idx = int(step.get("step_index"))
        label = str(step.get("label"))
        step_uid = f"{idx:04d}_{label}"
        step_dir = runs_root / step_uid

        if kind != "run_task":
            # Non-run steps: record presence only.
            ok = step_dir.exists()
            step_results.append({"step_uid": step_uid, "kind": kind, "passed": bool(ok)})
            if not ok:
                scenario_passed = False
                internal_errors.append(f"missing step dir for {step_uid} ({kind})")
            continue

        # run_task
        report, ok = grade_one_run_task(
            eval_dir=eval_dir,
            run_dir=step_dir,
            plan_eval_id=plan_eval_id,
            scenario_id=scenario_id,
            stamp=stamp,
            attempt_schema=attempt_schema,
            retrieval_schema=retrieval_schema,
            pins_used_schema=pins_used_schema,
            runreport_schema=runreport_schema,
            evalreport_schema=evalreport_schema,
        )
        (step_dir / "AgentEvalReport.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        step_results.append(
            {
                "step_uid": step_uid,
                "kind": kind,
                "passed": bool(ok),
                "report_path": _rel(eval_dir, step_dir / "AgentEvalReport.json"),
            }
        )
        if not ok:
            scenario_passed = False

    # ---------------------------------------------------------------------
    # Tool-surface timeline + scenario-level tool reuse scoring.
    # Deterministic: uses runner-produced ToolSurface.json + local import graph.
    # ---------------------------------------------------------------------
    tool_reuse_report: Optional[Dict[str, Any]] = None
    try:
        baseline_path = eval_dir / "BaselineToolSurface.json"
        if not baseline_path.exists():
            internal_errors.append("missing BaselineToolSurface.json (runner bug or old eval dir)")
        baseline_obj = _load_json(baseline_path) if baseline_path.exists() else {}
        prev_modules: Set[str] = set(baseline_obj.get("tool_modules", []) if isinstance(baseline_obj, dict) else [])
        prev_files: Set[str] = set(baseline_obj.get("tool_files", []) if isinstance(baseline_obj, dict) else [])

        workspace_root = eval_dir / "workspace"
        import_graph: Dict[str, Set[str]] = {}
        if workspace_root.exists():
            import_graph, _ = _build_local_import_graph(workspace_root)
        else:
            internal_errors.append("missing workspace/ (cannot compute import-closure tool reuse)")

        # Per run_task: which tool modules were reachable from the proof imports.
        run_task_use: Dict[str, Dict[str, Any]] = {}

        # Per step: tool surface diff.
        step_diffs: List[Dict[str, Any]] = []
        introduced: List[Dict[str, Any]] = []
        operator_introduced: List[str] = []

        # Precompute ordered step uids.
        ordered_steps: List[Tuple[int, str, str]] = []  # (pos, step_uid, kind)
        for s in steps:
            if not isinstance(s, dict):
                continue
            kind = str(s.get("kind"))
            idx = int(s.get("step_index"))
            label = str(s.get("label"))
            step_uid = f"{idx:04d}_{label}"
            ordered_steps.append((idx, step_uid, kind))

        # Process in order.
        for (idx, step_uid, kind) in ordered_steps:
            step_dir = runs_root / step_uid
            ts_path = step_dir / "ToolSurface.json"
            if not ts_path.exists():
                internal_errors.append(f"missing ToolSurface.json for step {step_uid} ({kind})")
                # Keep previous baseline to avoid cascading KeyError.
                step_diffs.append(
                    {
                        "step_uid": step_uid,
                        "kind": kind,
                        "tool_modules_count": int(len(prev_modules)),
                        "new_tool_modules": [],
                        "new_tool_files": [],
                        "tool_surface_path": _rel(eval_dir, ts_path),
                    }
                )
                continue

            ts_obj = _load_json(ts_path)
            cur_modules: Set[str] = set(ts_obj.get("tool_modules", []) if isinstance(ts_obj, dict) else [])
            cur_files: Set[str] = set(ts_obj.get("tool_files", []) if isinstance(ts_obj, dict) else [])

            new_mods = sorted(cur_modules - prev_modules)
            new_files = sorted(cur_files - prev_files)

            step_diffs.append(
                {
                    "step_uid": step_uid,
                    "kind": kind,
                    "tool_modules_count": int(len(cur_modules)),
                    "new_tool_modules": new_mods,
                    "new_tool_files": new_files,
                    "tool_surface_path": _rel(eval_dir, ts_path),
                }
            )

            for m in new_mods:
                introduced.append(
                    {
                        "module": m,
                        "introduced_at": step_uid,
                        "introduced_kind": kind,
                        "reused": False,
                        "reused_by_steps": [],
                    }
                )
                if kind == "run_task":
                    operator_introduced.append(m)

            # For run_task, compute reachable tool modules from the proof imports.
            if kind == "run_task":
                import_roots: Set[str] = set()
                snap_dir = step_dir / "snapshot"
                for fname in ["Spec.lean", "Proof.lean", "Cache.lean"]:
                    fp = snap_dir / fname
                    if not fp.exists():
                        continue
                    txt = fp.read_text(encoding="utf-8", errors="replace")
                    for imp in _parse_imports(txt):
                        import_roots.add(imp)
                reachable = _reachable_modules(sorted(import_roots), import_graph) if import_graph else set(import_roots)
                reachable_tool = sorted(set(reachable) & cur_modules)
                direct_tool = sorted(set(import_roots) & cur_modules)
                run_task_use[step_uid] = {
                    "import_roots": sorted(import_roots),
                    "direct_tool_imports": direct_tool,
                    "reachable_tool_modules": reachable_tool,
                }

            prev_modules = cur_modules
            prev_files = cur_files

        # Compute reuse for introduced modules.
        # A module introduced at step i is considered reused if any later run_task
        # has it in its reachable_tool_modules.
        step_pos: Dict[str, int] = {uid: i for i, (_idx, uid, _k) in enumerate(ordered_steps)}
        run_task_steps = [uid for (_idx, uid, k) in ordered_steps if k == "run_task"]
        for ent in introduced:
            mod = ent.get("module")
            intro_uid = ent.get("introduced_at")
            intro_pos = step_pos.get(str(intro_uid), -1)
            reused_by: List[str] = []
            for uid in run_task_steps:
                if step_pos.get(uid, -1) <= intro_pos:
                    continue
                use = run_task_use.get(uid, {})
                rmods = use.get("reachable_tool_modules", [])
                if isinstance(rmods, list) and mod in rmods:
                    reused_by.append(uid)
            ent["reused_by_steps"] = reused_by
            ent["reused"] = bool(reused_by)

        introduced_total = len(introduced)
        reused_total = sum(1 for e in introduced if e.get("reused") is True)
        reuse_rate: Optional[float] = None
        if introduced_total > 0:
            reuse_rate = float(reused_total) / float(introduced_total)

        tool_reuse_report = {
            "schema": "leanatlas.tool_reuse_report",
            "schema_version": "0.1.0",
            "baseline_tool_surface_path": _rel(eval_dir, baseline_path),
            "step_diffs": step_diffs,
            "introduced_modules": introduced,
            "run_task_tool_use": run_task_use,
            "metrics": {
                "introduced_total": int(introduced_total),
                "reused_total": int(reused_total),
                "reuse_rate": reuse_rate,
                "operator_introduced_total": int(len(operator_introduced)),
                "operator_introduced_modules": sorted(set(operator_introduced)),
            },
        }

        # Hard fail: OPERATOR run_task must NOT introduce tool modules.
        if operator_introduced:
            scenario_passed = False
            internal_errors.append(
                "operator introduced tool modules (patch-scope breach not caught by logs): "
                + ", ".join(sorted(set(operator_introduced))[:6])
            )
    except Exception as e:
        internal_errors.append(f"tool_reuse scoring exception: {e}")

    scenario_report: Dict[str, Any] = {
        "schema": "leanatlas.agent_eval_scenario_report",
        "schema_version": "0.1.0",
        "eval_id": plan_eval_id,
        "scenario_id": scenario_id,
        "stamp": stamp,
        "passed": bool(scenario_passed),
        "step_results": step_results,
    }
    if tool_reuse_report is not None:
        scenario_report["tool_reuse"] = tool_reuse_report
    if internal_errors:
        scenario_report["internal_errors"] = internal_errors

    serrs = _validate(scenario_report, scenario_schema)
    if serrs:
        scenario_report["passed"] = False
        scenario_report["internal_errors"] = internal_errors + ["INTERNAL: Scenario report schema invalid", *serrs]

    out_path = eval_dir / "ScenarioEvalReport.json"
    out_path.write_text(json.dumps(scenario_report, indent=2) + "\n", encoding="utf-8")
    print(f"[scenario-grade] wrote {out_path}")

    return 0 if scenario_report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
