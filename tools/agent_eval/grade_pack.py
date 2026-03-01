#!/usr/bin/env python3
"""Deterministic grader for Phase6 agent-eval pack runs.

Input:
- An eval directory produced by `tools/agent_eval/run_pack.py` in materialize/run modes.
  (i.e. it contains Plan.json and per-run workspaces under `runs/<task>/<variant>/workspace`).

Output:
- Writes **one** `AgentEvalReport.json` per run under:
    `runs/<task>/<variant>/AgentEvalReport.json`

Why per-run?
- The schema `docs/schemas/AgentEvalReport.schema.json` is designed for a single task+variant evaluation.

This grader is intentionally conservative:
- It only uses deterministic evidence (presence of required files + JSON schema validity + exact status fields).
- It does not use any LLM/rubric scoring.

Exit code:
- 0 if all runs pass
- 1 if any run fails
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))


import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_RUNREPORT = REPO_ROOT / "docs" / "schemas" / "RunReport.schema.json"
SCHEMA_ATTEMPT = REPO_ROOT / "docs" / "schemas" / "AttemptLogLine.schema.json"
SCHEMA_EVALREPORT = REPO_ROOT / "docs" / "schemas" / "AgentEvalReport.schema.json"
SCHEMA_PINS_USED = REPO_ROOT / "docs" / "schemas" / "PinsUsed.schema.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_schema(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(instance: Any, schema: Dict[str, Any]) -> List[str]:
    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(instance), key=lambda e: e.path)
    out: List[str] = []
    for e in errors:
        loc = "/".join([str(p) for p in e.path]) or "<root>"
        out.append(f"{loc}: {e.message}")
    return out


def _read_jsonl(path: Path) -> List[Any]:
    rows: List[Any] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _rel(eval_dir: Path, p: Path) -> str:
    try:
        return str(p.relative_to(eval_dir))
    except Exception:
        return str(p)


def _mk_check(check_id: str, passed: bool, evidence: List[str], notes: str = "") -> Dict[str, Any]:
    out = {"id": check_id, "passed": bool(passed), "evidence": list(evidence)}
    if notes:
        out["notes"] = notes
    return out


def _module_name_from_relpath(rel_lean: Path) -> str:
    p = rel_lean.with_suffix("")
    return ".".join(p.parts)


def _snapshot_tool_surface(workspace_root: Path) -> Dict[str, Any]:
    """Compute current tool surface snapshot (same structure as BaselineToolSurface.json)."""
    roots = [
        workspace_root / "LeanAtlas" / "Toolbox",
        workspace_root / "LeanAtlas" / "Incubator" / "Seeds",
        workspace_root / "LeanAtlas" / "Incubator" / "External",
    ]
    files: List[str] = []
    modules: List[str] = []
    for r in roots:
        if not r.exists():
            continue
        for p in r.rglob("*.lean"):
            try:
                rel = p.relative_to(workspace_root)
            except Exception:
                continue
            files.append(str(rel))
            modules.append(_module_name_from_relpath(rel))
    files = sorted(set(files))
    modules = sorted(set(modules))
    return {
        "schema": "leanatlas.agent_eval_tool_surface_snapshot",
        "schema_version": "0.1.0",
        "roots": ["LeanAtlas/Toolbox", "LeanAtlas/Incubator/Seeds", "LeanAtlas/Incubator/External"],
        "tool_files": files,
        "tool_modules": modules,
    }


def grade_one_run(
    *,
    eval_dir: Path,
    plan_eval_id: str,
    stamp: str,
    task_id: str,
    variant_id: str,
    problem_slug: str,
    run_id: str,
    expected: Dict[str, Any],
	tool_delta: Dict[str, Any],
	skill_delta: Dict[str, Any],
    runreport_schema: Dict[str, Any],
    attempt_schema: Dict[str, Any],
    evalreport_schema: Dict[str, Any],
    pins_used_schema: Dict[str, Any],
) -> Tuple[Dict[str, Any], bool]:
    """Return (AgentEvalReport, passed)."""

    run_dir = eval_dir / "runs" / task_id / variant_id
    ws_dir = run_dir / "workspace"
    report_dir = ws_dir / "Problems" / problem_slug / "Reports" / run_id

    checks: List[Dict[str, Any]] = []
    notes: List[str] = []
    artifacts: List[str] = []
    signals: Dict[str, float] = {}

    # Basic existence
    checks.append(_mk_check("workspace_present", ws_dir.exists(), [_rel(eval_dir, ws_dir)]))
    if not ws_dir.exists():
        # Hard fail
        rep = {
            "schema": "leanatlas.agent_eval_report",
            "schema_version": "1.0.0",
            "eval_id": f"{plan_eval_id}__{task_id}__{variant_id}".replace("::", "__"),
            "task_id": task_id,
            "variant_id": variant_id,
            "stamp": stamp,
            "passed": False,
            "deterministic_checks": checks,
            "signals": signals,
            "artifacts": artifacts,
            "notes": notes + ["workspace missing"],
        }
        # Ensure schema validity even on fail
        _ = _validate(rep, evalreport_schema)
        return rep, False

    runreport_path = report_dir / "RunReport.json"
    attemptlog_path = report_dir / "AttemptLog.jsonl"
    pins_path = report_dir / "pins_used.json"

    checks.append(_mk_check("runreport_present", runreport_path.exists(), [_rel(eval_dir, runreport_path)]))
    checks.append(_mk_check("attemptlog_present", attemptlog_path.exists(), [_rel(eval_dir, attemptlog_path)]))
    checks.append(_mk_check("pins_used_present", pins_path.exists(), [_rel(eval_dir, pins_path)]))

    if runreport_path.exists():
        artifacts.append(_rel(eval_dir, runreport_path))
    if attemptlog_path.exists():
        artifacts.append(_rel(eval_dir, attemptlog_path))
    if pins_path.exists():
        artifacts.append(_rel(eval_dir, pins_path))

    # Schema checks
    runreport_obj = None
    rr_schema_ok = False
    if runreport_path.exists():
        try:
            runreport_obj = _load_json(runreport_path)
            rr_errs = _validate(runreport_obj, runreport_schema)
            rr_schema_ok = len(rr_errs) == 0
            checks.append(_mk_check("runreport_schema_valid", rr_schema_ok, [_rel(eval_dir, runreport_path)], "\n".join(rr_errs[:8])))
        except Exception as e:
            checks.append(_mk_check("runreport_schema_valid", False, [_rel(eval_dir, runreport_path)], f"exception: {e}"))

    attempt_lines: List[Any] = []
    al_schema_ok = False
    if attemptlog_path.exists():
        try:
            attempt_lines = _read_jsonl(attemptlog_path)
            signals["attempt_lines"] = float(len(attempt_lines))
            # Validate first N lines
            errs: List[str] = []
            for i, row in enumerate(attempt_lines[:200]):
                row_errs = _validate(row, attempt_schema)
                errs.extend([f"line[{i}] {e}" for e in row_errs])
            al_schema_ok = len(errs) == 0 and len(attempt_lines) > 0
            checks.append(_mk_check("attemptlog_schema_valid", al_schema_ok, [_rel(eval_dir, attemptlog_path)], "\n".join(errs[:8]) if errs else ""))
        except Exception as e:
            checks.append(_mk_check("attemptlog_schema_valid", False, [_rel(eval_dir, attemptlog_path)], f"exception: {e}"))

    if pins_path.exists():
        try:
            pins_obj = _load_json(pins_path)
            pins_errs = _validate(pins_obj, pins_used_schema)
            checks.append(
                _mk_check(
                    "pins_used_schema_valid",
                    len(pins_errs) == 0,
                    [_rel(eval_dir, pins_path)],
                    "\n".join(pins_errs[:8]) if pins_errs else "",
                )
            )
        except Exception as e:
            checks.append(_mk_check("pins_used_schema_valid", False, [_rel(eval_dir, pins_path)], f"exception: {e}"))
    else:
        checks.append(_mk_check("pins_used_schema_valid", False, [_rel(eval_dir, pins_path)], "missing"))

    # Patch scope: hard fail if any violated (Phase5+): patch_scope.verdict must be ALLOW.
    ps_ok = True
    if attempt_lines:
        for row in attempt_lines:
            ps = row.get("patch_scope")
            if isinstance(ps, dict) and ps.get("verdict") == "DISALLOW":
                ps_ok = False
                break
    checks.append(_mk_check("patch_scope_not_violated", ps_ok, [_rel(eval_dir, attemptlog_path)] if attemptlog_path.exists() else []))

    # Compare status
    status_ok = False
    triage_ok = True
    if runreport_obj and isinstance(runreport_obj, dict):
        actual_status = runreport_obj.get("status")
        expected_status = expected.get("final_status")
        status_ok = (expected_status is None) or (actual_status == expected_status)
        checks.append(_mk_check("status_matches_expected", status_ok, [_rel(eval_dir, runreport_path)], f"expected={expected_status} actual={actual_status}"))

        if actual_status == "TRIAGED":
            triage = runreport_obj.get("triage", {})
            cat = triage.get("category", {}) if isinstance(triage, dict) else {}
            fam = cat.get("family") if isinstance(cat, dict) else None
            code = cat.get("code") if isinstance(cat, dict) else None
            exp_fam = expected.get("triage_family")
            exp_code = expected.get("triage_code")
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

        # Env stamp present
        ctx = runreport_obj.get("context", {})
        tools = ctx.get("tools", {}) if isinstance(ctx, dict) else {}
        env_stamp = tools.get("environment_stamp") if isinstance(tools, dict) else None
        env_ok = env_stamp is not None
        checks.append(_mk_check("env_stamp_present", env_ok, [_rel(eval_dir, runreport_path)]))
    else:
        checks.append(_mk_check("status_matches_expected", False, [_rel(eval_dir, runreport_path)], "missing RunReport"))
        checks.append(_mk_check("triage_matches_expected", False, [_rel(eval_dir, runreport_path)], "missing RunReport"))
        checks.append(_mk_check("env_stamp_present", False, [_rel(eval_dir, runreport_path)], "missing RunReport"))

    # Tool-delta checks (deterministic, file-surface based).
    baseline_path = run_dir / "BaselineToolSurface.json"
    baseline_ok = baseline_path.exists()
    checks.append(_mk_check("baseline_tool_surface_present", baseline_ok, [_rel(eval_dir, baseline_path)]))

    if baseline_ok:
        try:
            baseline = _load_json(baseline_path)
            bmods = baseline.get("tool_modules")
            if not isinstance(bmods, list) or not all(isinstance(x, str) for x in bmods):
                raise ValueError("BaselineToolSurface.json missing tool_modules[]")
            baseline_mods = set(bmods)
            current = _snapshot_tool_surface(ws_dir)
            current_mods = set(current.get("tool_modules", []))
            new_mods = sorted(current_mods - baseline_mods)
            signals["new_tool_modules"] = float(len(new_mods))

            max_new = tool_delta.get("max_new_modules")
            if isinstance(max_new, int):
                ok = len(new_mods) <= max_new
                checks.append(
                    _mk_check(
                        "tool_delta_max_new_modules",
                        ok,
                        [_rel(eval_dir, baseline_path)],
                        f"max={max_new} new={len(new_mods)} sample={new_mods[:8]}",
                    )
                )
            else:
                checks.append(_mk_check("tool_delta_max_new_modules", True, []))

            exp_mods = tool_delta.get("expected_new_modules")
            if isinstance(exp_mods, list) and exp_mods and all(isinstance(x, str) for x in exp_mods):
                missing = [m for m in exp_mods if m not in current_mods]
                ok = len(missing) == 0
                checks.append(
                    _mk_check(
                        "tool_delta_expected_modules_present",
                        ok,
                        [_rel(eval_dir, baseline_path)],
                        f"missing={missing}",
                    )
                )
            else:
                checks.append(_mk_check("tool_delta_expected_modules_present", True, []))

            exp_decls = tool_delta.get("expected_new_decls")
            if isinstance(exp_decls, list) and exp_decls and all(isinstance(x, str) for x in exp_decls):
                # Search only in files belonging to newly created modules.
                cur_files = current.get("tool_files", [])
                new_files: List[Path] = []
                for rf in cur_files:
                    if not isinstance(rf, str) or not rf.endswith(".lean"):
                        continue
                    mod = _module_name_from_relpath(Path(rf))
                    if mod in new_mods:
                        new_files.append(ws_dir / rf)

                missing_decls: List[str] = []
                for d in exp_decls:
                    found = False
                    for fp in new_files:
                        try:
                            txt = fp.read_text(encoding="utf-8")
                        except Exception:
                            continue
                        if d in txt:
                            found = True
                            break
                    if not found:
                        missing_decls.append(d)
                ok = len(missing_decls) == 0
                checks.append(
                    _mk_check(
                        "tool_delta_expected_decls_present",
                        ok,
                        [_rel(eval_dir, baseline_path)] + [_rel(eval_dir, p) for p in new_files[:4]],
                        f"missing={missing_decls}",
                    )
                )
            else:
                checks.append(_mk_check("tool_delta_expected_decls_present", True, []))

        except Exception as e:
            checks.append(_mk_check("tool_delta_checks", False, [_rel(eval_dir, baseline_path)], f"exception: {e}"))

    # Skill-delta is not deterministically gradeable per-run yet.
    if skill_delta.get("expected_new_kb_tags"):
        notes.append(f"soft: expected_new_kb_tags={skill_delta.get('expected_new_kb_tags')}")
    if skill_delta.get("expected_new_skills"):
        notes.append("soft: expected_new_skills present")

    # Compute pass
    passed = all(c["passed"] for c in checks)

    report = {
        "schema": "leanatlas.agent_eval_report",
        "schema_version": "1.0.0",
        "eval_id": f"{plan_eval_id}__{task_id}__{variant_id}".replace("::", "__"),
        "task_id": task_id,
        "variant_id": variant_id,
        "stamp": stamp,
        "passed": passed,
        "deterministic_checks": checks,
        "signals": signals,
        "artifacts": artifacts,
        "notes": notes,
    }

    # Validate self
    schema_errs = _validate(report, evalreport_schema)
    if schema_errs:
        # If we ever produce an invalid report, mark as failed and attach errors.
        report["passed"] = False
        report["notes"] = notes + ["INTERNAL: AgentEvalReport schema invalid", *schema_errs]

    return report, bool(report.get("passed"))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-dir", required=True, help="Eval dir: artifacts/agent_evals/<eval_id>/<stamp>")
    args = ap.parse_args(argv)

    eval_dir = Path(args.eval_dir)
    plan_path = eval_dir / "Plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Missing Plan.json in {eval_dir}")

    plan = _load_json(plan_path)
    plan_eval_id = str(plan.get("eval_id"))
    stamp = str(plan.get("stamp"))

    runreport_schema = _load_schema(SCHEMA_RUNREPORT)
    attempt_schema = _load_schema(SCHEMA_ATTEMPT)
    evalreport_schema = _load_schema(SCHEMA_EVALREPORT)
    pins_used_schema = _load_schema(SCHEMA_PINS_USED)

    any_fail = False
    for r in plan.get("runs", []):
        rep, passed = grade_one_run(
            eval_dir=eval_dir,
            plan_eval_id=plan_eval_id,
            stamp=stamp,
            task_id=r["task_id"],
            variant_id=r["variant_id"],
            problem_slug=r["problem_slug"],
            run_id=r["run_id"],
            expected=r.get("expected", {}),
            tool_delta=r.get("tool_delta", {}),
            skill_delta=r.get("skill_delta", {}),
            runreport_schema=runreport_schema,
            attempt_schema=attempt_schema,
            evalreport_schema=evalreport_schema,
            pins_used_schema=pins_used_schema,
        )
        run_dir = eval_dir / "runs" / r["task_id"] / r["variant_id"]
        out_path = run_dir / "AgentEvalReport.json"
        out_path.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"[agent-eval] wrote: {out_path}")
        if not passed:
            any_fail = True

    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
