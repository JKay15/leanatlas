#!/usr/bin/env python3
"""Execute sequential E2E scenarios locally.

Scenarios are meant to expose:
- cross-problem interference ("fix A, then B breaks")
- shared-library regressions (MAINTAINER overlay breaks consumers)
- state leaks across many runs

Usage:
  python tests/e2e/run_scenarios.py --profile core
  python tests/e2e/run_scenarios.py --scenario scenario_chain_core_3
  python tests/e2e/run_scenarios.py --profile nightly --keep-workdir

Notes:
- Requires `lake` in PATH.
- By default does NOT run `lake update` (use --update if you want).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import yaml  # type: ignore
import jsonschema  # type: ignore

# Local imports (repo-relative)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # add `leanatlas/` root
from tools.workflow.patch_scope import check_patch_scope
from tools.workflow.progress_signals import diagnostic_fingerprint
from tools.workflow.judge import judge_decide
from tools.workflow.run_cmd import run_cmd
from tools.workflow.shared_cache import ensure_workspace_lake_packages


DIAG_RE = re.compile(r'^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+): (?P<sev>error|warning|info): (?P<msg>.*)$')
DIAG_RE_PREFIX = re.compile(r'^(?P<sev>error|warning|info): (?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+): (?P<msg>.*)$')


def have_cmd(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def resolve_patch_ref(case_dir: Path, ref: str) -> Path:
    if "/" not in ref:
        return case_dir / "patches" / ref
    return case_dir / ref


def copy_overlay(overlay_path: Path, workdir: Path) -> List[str]:
    """Copy overlay tree into workdir and return repo-relative touched paths.

    We record *all* touched paths (not just .lean) to make patch-scope robust.
    """
    touched: List[str] = []
    for src in overlay_path.rglob('*'):
        if not src.is_file():
            continue
        rel = src.relative_to(overlay_path)
        dst = workdir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        touched.append(rel.as_posix())
    return sorted(set(touched))


def parse_diagnostics(output: str) -> List[Dict[str, Any]]:
    diags: List[Dict[str, Any]] = []
    for line in output.splitlines():
        m = DIAG_RE.match(line.strip())
        if not m:
            m = DIAG_RE_PREFIX.match(line.strip())
        if not m:
            continue
        file = m.group('file').replace('\\', '/')
        if file.startswith('./'):
            file = file[2:]
        sev = m.group('sev')
        msg = m.group('msg')
        line_i = int(m.group('line'))
        col_i = int(m.group('col'))
        diag = {
            "id": f"d{len(diags)}",
            "file": file,
            "severity": sev,
            "message": msg,
        }
        if sev == 'error':
            diag["range"] = {
                "start_line": line_i,
                "start_col": col_i,
                "end_line": line_i,
                "end_col": col_i,
            }
        diags.append(diag)
    return diags


def make_run_id(prefix: str) -> str:
    now = int(time.time() * 1000)
    h = hashlib.sha1(f"{prefix}-{now}-{os.getpid()}".encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{now}-{h}"


def hash_fixture_deps(fixture_root: Path) -> str:
    """Hash files that determine dependency graph/toolchain."""
    h = hashlib.sha256()
    for rel in (Path("lean-toolchain"), Path("lakefile.lean"), Path("lake-manifest.json")):
        p = fixture_root / rel
        h.update(rel.as_posix().encode("utf-8"))
        if p.exists():
            h.update(p.read_bytes())
        else:
            h.update(b"<missing>")
    return h.hexdigest()


def reset_workdir_preserve_lake(*, fixture_root: Path, workdir: Path) -> None:
    """Reset workspace content to fixture_root while preserving `.lake/` cache."""
    workdir.mkdir(parents=True, exist_ok=True)
    for child in workdir.iterdir():
        if child.name == ".lake":
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except FileNotFoundError:
                pass
    shutil.copytree(fixture_root, workdir, dirs_exist_ok=True)


def _tail_last_nonempty_line(path: Path, max_bytes: int = 8192) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes), os.SEEK_SET)
            data = f.read()
        txt = data.decode("utf-8", errors="replace")
        for line in reversed(txt.splitlines()):
            line = line.strip()
            if line:
                return line
    except Exception:
        return ""
    return ""


def _run_cmd_with_progress(
    *,
    scenario_label: str,
    phase: str,
    cmd: List[str],
    cwd: Path,
    log_dir: Path,
    label: str,
    timeout_s: int,
    env: Optional[Dict[str, str]] = None,
):
    res_holder: Dict[str, Any] = {}
    err_holder: Dict[str, BaseException] = {}
    t0 = time.time()
    stdout_path = log_dir / f"{label}.stdout.txt"
    stderr_path = log_dir / f"{label}.stderr.txt"
    last_progress_line = ""

    def _worker() -> None:
        try:
            res_holder["res"] = run_cmd(
                cmd=cmd,
                cwd=cwd,
                log_dir=log_dir,
                label=label,
                timeout_s=timeout_s,
                env=env,
                capture_text=True,
            )
        except BaseException as exc:
            err_holder["err"] = exc

    th = threading.Thread(target=_worker, daemon=True)
    th.start()
    while th.is_alive():
        th.join(timeout=10.0)
        if th.is_alive():
            elapsed_s = int(time.time() - t0)
            progress_line = _tail_last_nonempty_line(stderr_path) or _tail_last_nonempty_line(stdout_path)
            if progress_line and progress_line != last_progress_line:
                print(
                    f"[e2e-scenarios] {scenario_label} {phase} progress: {progress_line}",
                    flush=True,
                )
                last_progress_line = progress_line
            print(
                f"[e2e-scenarios] {scenario_label} {phase} still running elapsed_s={elapsed_s}",
                flush=True,
            )

    if "err" in err_holder:
        raise err_holder["err"]
    res = res_holder["res"]
    print(
        f"[e2e-scenarios] {scenario_label} {phase} done rc={int(res.span.get('exit_code', 1))} duration_ms={int(res.span.get('duration_ms', 0))}",
        flush=True,
    )
    return res


def _run_call_with_heartbeat(*, label: str, fn, heartbeat_s: int = 10):
    res_holder: Dict[str, Any] = {}
    err_holder: Dict[str, BaseException] = {}
    t0 = time.time()

    def _worker() -> None:
        try:
            res_holder["res"] = fn()
        except BaseException as exc:
            err_holder["err"] = exc

    th = threading.Thread(target=_worker, daemon=True)
    th.start()
    while th.is_alive():
        th.join(timeout=float(heartbeat_s))
        if th.is_alive():
            elapsed_s = int(time.time() - t0)
            print(f"[e2e-scenarios] {label} still running elapsed_s={elapsed_s}", flush=True)

    if "err" in err_holder:
        raise err_holder["err"]
    elapsed_ms = int((time.time() - t0) * 1000)
    print(f"[e2e-scenarios] {label} done elapsed_ms={elapsed_ms}", flush=True)
    return res_holder.get("res")


def lake_build(
    workdir: Path,
    target: str,
    *,
    scenario_label: str,
    phase: str,
    log_dir: Path,
    label: str,
    timeout_s: int,
) -> Tuple[int, str, int]:
    res = _run_cmd_with_progress(
        scenario_label=scenario_label,
        phase=phase,
        cmd=["lake", "build", target],
        cwd=workdir,
        log_dir=log_dir,
        label=label,
        timeout_s=timeout_s,
    )
    stdout = res.stdout_text or ""
    stderr = res.stderr_text or ""
    out = stdout + (f"\n{stderr}" if stderr else "")
    return int(res.span.get("exit_code", 1)), out, int(res.span.get("duration_ms", 0))


def _dedup_keep_order(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _expand_lake_targets(target: str, step_results: List[Dict[str, Any]]) -> List[str]:
    """Scenario convenience: `Problems` means all successful run_case build targets so far."""
    if target != 'Problems':
        return [target]
    targets: List[str] = []
    for s in step_results:
        if s.get('kind') != 'run_case' or not s.get('ok', False):
            continue
        res = s.get('result') or {}
        if res.get('final_status') != 'SUCCESS':
            continue
        bt = res.get('build_target')
        if isinstance(bt, str) and bt.strip():
            targets.append(bt.strip())
    targets = _dedup_keep_order(targets)
    return targets or [target]


def execute_case_in_workdir(
    *,
    workdir: Path,
    case_id: str,
    case_path: Path,
    meta: Dict[str, Any],
    out_dir: Path,
    expected_override: Optional[Dict[str, Any]] = None,
    mode: str = "OPERATOR",
    scenario_label: str = "scenario",
    lake_timeout_s: int = 900,
) -> Dict[str, Any]:
    """Execute one golden case *inside an existing workspace*.

    Returns a small summary dict used by scenario assertions.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = out_dir / "Reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    cmd_dir = out_dir / "Cmd"
    cmd_dir.mkdir(parents=True, exist_ok=True)

    exec_meta = meta.get("execution", {}) or {}
    fixture_dir = case_path / exec_meta.get("fixture_dir", "fixture")
    if not fixture_dir.exists():
        raise RuntimeError(f"missing fixture dir: {fixture_dir}")
    # Remove previous materialization of this case to avoid stale-file bleed.
    case_problem_dir = workdir / "Problems" / case_id
    if case_problem_dir.exists():
        shutil.rmtree(case_problem_dir, ignore_errors=True)
    copy_overlay(fixture_dir, workdir)

    patch_sequence: List[str] = meta.get('patch_sequence', []) or []
    overlays = [None] + patch_sequence

    # Budgets: default = baseline + patches unless overridden by case yaml
    max_attempts = max(1, 1 + len(patch_sequence))
    budgets = {
        "limits": {
            "max_attempts": int(max_attempts),
            "max_steps": 50,
            "max_external_queries": 5,
            "max_wall_time_ms": 180_000,
        },
        "counters": {
            "attempts_used": 0,
            "steps_used": 0,
            "external_queries_used": 0,
            "wall_time_ms": 0,
        },
    }
    # optional budgets override (case-level)
    if "budgets" in exec_meta:
        limits = (exec_meta.get("budgets", {}) or {}).get("limits", {}) or {}
        budgets["limits"].update({k: int(v) for k, v in limits.items()})

    build_target = exec_meta.get('build_target', f'Problems.{case_id}.Proof')
    main_decl = exec_meta.get('main_decl', f'Problems.{case_id}.main')

    attempt_lines: List[Dict[str, Any]] = []
    prev_fingerprint: Optional[str] = None
    stagnant_count = 0
    final_status: Optional[str] = None
    final_diags: List[Dict[str, Any]] = []
    stage_build_status = "SKIPPED"
    stage_retrieval_status = "SKIPPED"

    # expected hint: case yaml expected merged with override (scenario step may override)
    expected = dict(meta.get("expected", {}) or {})
    if expected_override:
        expected.update(expected_override)

    # Determine suspected family for Judge and for RunReport triage category
    cat = (expected.get("category", {}) or {})
    suspected_family = cat.get("family", "UNKNOWN")

    def do_build() -> Tuple[int, str]:
        rc, out, elapsed_ms = lake_build(
            workdir,
            build_target,
            scenario_label=scenario_label,
            phase=f"{case_id} attempt={budgets['counters']['attempts_used']} lake build {build_target}",
            log_dir=cmd_dir,
            label=f"a{budgets['counters']['attempts_used']}_lake_build",
            timeout_s=lake_timeout_s,
        )
        budgets['counters']['wall_time_ms'] += int(elapsed_ms)
        return rc, out

    for attempt_index, patch_ref in enumerate(overlays):
        touched_files: List[str] = []
        if patch_ref:
            overlay_path = resolve_patch_ref(case_path, patch_ref)
            if not overlay_path.exists():
                raise RuntimeError(f"missing patch overlay: {overlay_path}")
            touched_files = copy_overlay(overlay_path, workdir)

        budgets['counters']['attempts_used'] = attempt_index + 1

        patch_scope = check_patch_scope(
            problem_slug=case_id,
            mode=mode,
            touched_files=touched_files,
        )

        # Build
        print(
            f"[e2e-scenarios] {scenario_label} case={case_id} attempt={attempt_index} build_target={build_target}",
            flush=True,
        )
        rc, out = do_build()
        diags = parse_diagnostics(out)
        stage_build_status = "OK" if rc == 0 else "FAIL"
        final_diags = diags

        # Signals (deterministic)
        error_outside_problem = any(
            (d.get('severity') == 'error') and (not str(d.get('file', '')).startswith(f"Problems/{case_id}/"))
            for d in diags
        )
        fp = diagnostic_fingerprint([d for d in diags if d.get('severity') == 'error'])
        diag_changed = (prev_fingerprint is None) or (fp != prev_fingerprint)
        prev_fingerprint = fp

        imports_changed = any(p.endswith('Proof.lean') for p in touched_files)
        new_retrieval_hit = False
        tooling_failed = False

        stagnant = (not diag_changed) and (not imports_changed) and (not new_retrieval_hit)
        stagnant_count = (stagnant_count + 1) if stagnant else 0

        judge = judge_decide(
            mode=mode,
            patch_scope=patch_scope,
            suspected_family=suspected_family,
            stagnant_count=stagnant_count,
            signals={
                "diag_fingerprint": fp,
                "diag_changed": bool(diag_changed),
                "imports_changed": bool(imports_changed),
                "new_retrieval_hit": bool(new_retrieval_hit),
                "tooling_failed": bool(tooling_failed),
                "error_outside_problem": bool(error_outside_problem),
                "stagnant": bool(stagnant),
            },
            budgets=budgets,
        )

        # Determine final status
        if rc == 0:
            final_status = "SUCCESS"
        elif judge['decision'] == 'TRIAGED':
            final_status = "TRIAGED"
        else:
            final_status = None

        attempt_lines.append({
            "schema": "leanatlas.attempt_log_line",
            "schema_version": "0.4.0",
            "run_id": out_dir.name,
            "problem_slug": case_id,
            "attempt_index": int(attempt_index),
            "touched_files": touched_files,
            "patch_scope": patch_scope,
            "suspected_category": {
                "family": suspected_family,
                "code": cat.get("code", "UNKNOWN"),
                "standard": True,
            },
            "signals": {
                "diag_fingerprint": fp,
                "diag_changed": bool(diag_changed),
                "imports_changed": bool(imports_changed),
                "new_retrieval_hit": bool(new_retrieval_hit),
                "tooling_failed": bool(tooling_failed),
                "error_outside_problem": bool(error_outside_problem),
                "stagnant": bool(stagnant),
            },
            "stages": {
                "retrieval": {"status": stage_retrieval_status},
                "build": {"status": stage_build_status},
                "verify": {"status": "OK" if rc == 0 else "SKIPPED"},
            },
            "judge": judge,
            "budget": budgets,
            "events": [
                {"kind": "PATCH_APPLIED" if patch_ref else "BASELINE_BUILD", "attrs": {"patch": str(patch_ref) if patch_ref else ""}},
                {"kind": "LAKE_BUILD", "attrs": {"target": build_target, "exit_code": int(rc), "executed": True}},
            ],
        })

        if final_status is not None:
            break

    if final_status is None:
        # No more overlays/actions in this deterministic runner => treat as TRIAGED.
        final_status = "TRIAGED"

    # Write AttemptLog.jsonl
    attemptlog_path = reports_dir / "AttemptLog.jsonl"
    attemptlog_path.write_text("\n".join(json.dumps(l, ensure_ascii=False, sort_keys=True) for l in attempt_lines) + "\n", encoding="utf-8")

    # Minimal RetrievalTrace
    retrieval_trace = {
        "schema": "leanatlas.retrieval_trace",
        "schema_version": "0.3.0",
        "run_id": out_dir.name,
        "problem_slug": case_id,
        "domain": {"input_codes": [], "expanded_codes": []},
        "budget": {
            "max_external_queries": budgets["limits"]["max_external_queries"],
            "max_steps": budgets["limits"]["max_steps"],
            "used_external_queries": budgets["counters"]["external_queries_used"],
            "used_steps": budgets["counters"]["steps_used"],
        },
        "steps": [],
    }
    (reports_dir / "RetrievalTrace.json").write_text(json.dumps(retrieval_trace, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    # RunReport (minimal, deterministic)
    entrypoints = {
        "files": {
            "spec": f"Problems/{case_id}/Spec.lean",
            "proof": f"Problems/{case_id}/Proof.lean",
            "cache": f"Problems/{case_id}/Cache.lean",
            "scratch": f"Problems/{case_id}/Scratch.lean",
        }
    }
    targets = [{
        "id": "t_main",
        "role": "MAIN",
        "decl": main_decl,
        "file": f"Problems/{case_id}/Proof.lean",
    }]
    stages = {
        "retrieval": {"status": stage_retrieval_status},
        "build": {"status": "OK" if final_status == "SUCCESS" else "FAIL"},
        "verify": {"status": "OK" if final_status == "SUCCESS" else "SKIPPED"},
    }

    run_report: Dict[str, Any] = {
        "schema": "leanatlas.run_report",
        "schema_version": "0.3.0",
        "run_id": out_dir.name,
        "problem_slug": case_id,
        "status": final_status,
        "mode": mode,
        "context": {
            "git_sha": "unknown0",
            "lean_toolchain": (workdir / 'lean-toolchain').read_text(encoding='utf-8').strip(),
            "mathlib_rev": "unknown0",
        },
        "summary": {
            "title": f"scenario {case_id}",
            "one_line": f"{final_status} for {case_id}",
        },
        "entrypoints": entrypoints,
        "targets": targets,
        "stages": stages,
        "diagnostics": final_diags,
        "retrieval_trace_path": "RetrievalTrace.json",
    }

    if final_status == "SUCCESS":
        run_report["verification"] = {"no_sorry": True, "axioms": [], "warnings": []}
    else:
        # use expected category as a hint for triage object
        err_ids = [d["id"] for d in final_diags if d.get("severity") == "error"]
        if not err_ids and final_diags:
            err_ids = [final_diags[0]["id"]]
        if not err_ids:
            err_ids = ["d0"]
            final_diags.append({
                "id": "d0",
                "file": f"Problems/{case_id}/Proof.lean",
                "severity": "error",
                "message": "unknown error (no diagnostics parsed)",
                "range": {"start_line": 1, "start_col": 1, "end_line": 1, "end_col": 1},
            })
        run_report["hotspots"] = [{
            "id": "h0",
            "title": "Primary failure",
            "stage": "build",
            "target_id": "t_main",
            "diagnostic_ids": err_ids[:1],
            "trace_step_indices": [],
        }]
        run_report["triage"] = {
            "level": expected.get("triage_level", "FIXABLE"),
            "category": {"family": cat.get("family", "UNKNOWN"), "code": cat.get("code", "UNKNOWN"), "standard": True},
            "evidence": {"diagnostic_ids": err_ids[:1]},
            "next_actions": [{"kind": "REQUEST_GPTPRO_REPLAN", "description": "Review assumptions / definitions.", "patch": ""}],
        }

    (reports_dir / "RunReport.json").write_text(json.dumps(run_report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    # RunReport.md
    md = [
        f"# RunReport {out_dir.name}",
        "",
        f"- status: **{final_status}**",
        f"- mode: `{mode}`",
        "",
        "## Targets",
        f"- MAIN: `{main_decl}` in `{targets[0]['file']}`",
        "",
        "## Stages",
        f"- build: {stages['build']['status']}",
        f"- verify: {stages['verify']['status']}",
        "",
    ]
    if final_status != "SUCCESS":
        md += ["## Triage", f"- reason_code: `{attempt_lines[-1]['judge']['reason_code']}`"]
    (reports_dir / "RunReport.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    return {
        "final_status": final_status,
        "judge_reason_code": attempt_lines[-1]["judge"]["reason_code"],
        "triage_level": attempt_lines[-1]["judge"]["triage_level"],
        "build_target": build_target,
        "wall_time_ms": int(budgets["counters"]["wall_time_ms"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', default=None, choices=['smoke', 'core', 'nightly'], help='Run all executable scenarios in a profile')
    ap.add_argument('--tier', dest='legacy_tier', default=None, choices=['smoke', 'core', 'nightly'], help=argparse.SUPPRESS)
    ap.add_argument('--scenario', dest='scenario_id', default=None, help='Run a single scenario by id')
    ap.add_argument('--keep-workdir', action='store_true', help='Keep the temp workdir for debugging')
    ap.add_argument('--update', action='store_true', help='Run `lake update` before executing')
    ap.add_argument('--lake-timeout-s', type=int, default=900, help='Timeout (seconds) for each `lake build` invocation')
    ap.add_argument('--step-timeout-s', type=int, default=900, help='Timeout (seconds) for each `run_cmd` scenario step')
    args = ap.parse_args()
    selected_profile = args.legacy_tier or args.profile

    if not have_cmd('lake'):
        print('[e2e-scenarios] lake not found in PATH; skipping execution.')
        return 0

    repo_root = Path(__file__).resolve().parents[2]
    scenarios_root = repo_root / 'tests' / 'e2e' / 'scenarios'
    golden_root = repo_root / 'tests' / 'e2e' / 'golden'
    fixture_root = repo_root / 'tests' / 'e2e' / 'fixture_root'

    # collect scenarios
    all_scenarios: List[Path] = []
    for p in sorted(scenarios_root.iterdir()):
        if not p.is_dir():
            continue
        sc_yaml = p / 'scenario.yaml'
        if not sc_yaml.exists():
            continue
        meta = load_yaml(sc_yaml)
        if not (meta.get('execution', {}) or {}).get('enabled', False):
            continue
        if args.scenario_id and p.name != args.scenario_id:
            continue
        if selected_profile and meta.get('tier') != selected_profile:
            continue
        all_scenarios.append(p)

    if not all_scenarios:
        print('[e2e-scenarios] no scenarios selected')
        return 0

    print(f"[e2e-scenarios] selected {len(all_scenarios)} scenario(s)", flush=True)

    # Reuse the same shared workspace root as run_cases to avoid duplicate
    # huge `.lake` workspace trees across runners.
    shared_root = repo_root / ".cache" / "leanatlas" / "e2e_run_cases"
    shared_root.mkdir(parents=True, exist_ok=True)
    tmp_root = repo_root / ".cache" / "leanatlas" / "e2e_scenarios"
    tmp_root.mkdir(parents=True, exist_ok=True)

    # Backward-compat cleanup for older per-scenario workspace directories.
    for stale in tmp_root.glob("*__*"):
        if stale.is_dir():
            _run_call_with_heartbeat(
                label=f"remove stale scenario workspace {stale.name}",
                fn=lambda p=stale: shutil.rmtree(p, ignore_errors=True),
            )

    shared_workdir = shared_root / "workdir"
    deps_stamp_path = shared_root / "deps_stamp.sha256"
    desired_deps_stamp = hash_fixture_deps(fixture_root)
    existing_deps_stamp = deps_stamp_path.read_text(encoding="utf-8").strip() if deps_stamp_path.exists() else ""
    cold_init = bool((not shared_workdir.exists()) or (existing_deps_stamp != desired_deps_stamp))

    if cold_init:
        print("[e2e-scenarios] shared workspace cold-init (deps/toolchain changed or missing)", flush=True)
        _run_call_with_heartbeat(
            label="e2e-scenarios cold-init cleanup",
            fn=lambda: shutil.rmtree(shared_workdir, ignore_errors=True),
        )
        _run_call_with_heartbeat(
            label="e2e-scenarios cold-init copy fixture_root",
            fn=lambda: shutil.copytree(fixture_root, shared_workdir),
        )
    else:
        print("[e2e-scenarios] shared workspace warm-reset (reuse existing .lake cache)", flush=True)
        _run_call_with_heartbeat(
            label="e2e-scenarios warm-reset shared workdir",
            fn=lambda: reset_workdir_preserve_lake(fixture_root=fixture_root, workdir=shared_workdir),
        )
    deps_stamp_path.write_text(desired_deps_stamp + "\n", encoding="utf-8")

    cache_policy = _run_call_with_heartbeat(
        label="e2e-scenarios ensure shared lake cache",
        fn=lambda: ensure_workspace_lake_packages(
            repo_root=repo_root,
            workspace_root=shared_workdir,
            purpose="e2e_scenarios:shared_workdir",
        ),
    )
    print("[e2e-scenarios] shared workspace/cache ready", flush=True)
    if not cache_policy.ok:
        print(f"[e2e-scenarios][FAIL] shared cache policy not satisfied: {cache_policy.note}")
        return 2

    if args.update:
        _run_cmd_with_progress(
            scenario_label="global",
            phase="lake update",
            cmd=["lake", "update"],
            cwd=shared_workdir,
            log_dir=shared_workdir / "Cmd",
            label="lake_update_global",
            timeout_s=args.lake_timeout_s,
        )

    rc_all = 0
    for sc_dir in all_scenarios:
        sc_meta = load_yaml(sc_dir / 'scenario.yaml')
        scenario_id = sc_meta['id']
        scenario_run_id = make_run_id(scenario_id)
        scenario_label = f"{scenario_id} ({scenario_run_id})"
        print(f"[e2e-scenarios] start {scenario_label}", flush=True)
        workdir = shared_workdir
        print(f"[e2e-scenarios] {scenario_label} warm-reset shared workspace -> {workdir}", flush=True)
        _run_call_with_heartbeat(
            label=f"{scenario_label} warm-reset workspace",
            fn=lambda: reset_workdir_preserve_lake(fixture_root=fixture_root, workdir=workdir),
        )
        cache_policy = _run_call_with_heartbeat(
            label=f"{scenario_label} ensure workspace lake cache",
            fn=lambda: ensure_workspace_lake_packages(
                repo_root=repo_root,
                workspace_root=workdir,
                purpose=f"e2e_scenario:{scenario_id}",
            ),
        )
        print(f"[e2e-scenarios] {scenario_label} workspace/cache ready", flush=True)
        if not cache_policy.ok:
            print(f"[e2e-scenarios][FAIL] shared cache policy not satisfied: {cache_policy.note}")
            rc_all = 2
            continue

        if args.update:
            _run_cmd_with_progress(
                scenario_label=scenario_label,
                phase="lake update",
                cmd=['lake', 'update'],
                cwd=workdir,
                log_dir=workdir / "Cmd",
                label='lake_update',
                timeout_s=args.lake_timeout_s,
            )

        # scenario artifacts root
        artifacts_root = repo_root / 'artifacts' / 'e2e_scenarios' / scenario_id / scenario_run_id
        artifacts_root.mkdir(parents=True, exist_ok=True)

        step_results: List[Dict[str, Any]] = []
        ok = True

        for i, step in enumerate(sc_meta.get('steps', []) or []):
            kind = step.get('kind')
            step_name = f"step_{i:02d}_{kind}"
            print(f"[e2e-scenarios] {scenario_label} {step_name} start", flush=True)
            if kind == 'run_case':
                case_id = step['case_id']
                case_path = golden_root / case_id
                meta = load_yaml(case_path / 'case.yaml')
                expected_override = step.get('expect')
                out_dir = artifacts_root / f"{step_name}__{case_id}"
                res = execute_case_in_workdir(
                    workdir=workdir,
                    case_id=case_id,
                    case_path=case_path,
                    meta=meta,
                    out_dir=out_dir,
                    expected_override=expected_override,
                    mode="OPERATOR",
                    scenario_label=scenario_label,
                    lake_timeout_s=args.lake_timeout_s,
                )
                # expectation check
                expect = expected_override or (meta.get('expected', {}) or {})
                exp_status = expect.get('final_status')
                if exp_status and res['final_status'] != exp_status:
                    ok = False
                    step_results.append({"step": i, "kind": kind, "case_id": case_id, "ok": False, "reason": f"status {res['final_status']} != {exp_status}", "result": res})
                else:
                    # optional judge reason check
                    exp_reason = (expected_override or {}).get("judge_reason_code")
                    exp_level = (expected_override or {}).get("triage_level")
                    if exp_reason and res.get("judge_reason_code") != exp_reason:
                        ok = False
                        step_results.append({"step": i, "kind": kind, "case_id": case_id, "ok": False, "reason": f"judge_reason {res.get('judge_reason_code')} != {exp_reason}", "result": res})
                    elif exp_level and res.get("triage_level") != exp_level:
                        ok = False
                        step_results.append({"step": i, "kind": kind, "case_id": case_id, "ok": False, "reason": f"triage_level {res.get('triage_level')} != {exp_level}", "result": res})
                    else:
                        step_results.append({"step": i, "kind": kind, "case_id": case_id, "ok": True, "result": res})
                print(f"[e2e-scenarios] {scenario_label} {step_name} done ok={step_results[-1].get('ok', False)}", flush=True)

            elif kind == 'apply_overlay':
                overlay_ref = step['overlay']
                mode = step.get('mode', 'MAINTAINER')
                overlay_path = sc_dir / overlay_ref
                touched = copy_overlay(overlay_path, workdir)
                patch_scope = check_patch_scope(problem_slug=step.get("problem_slug_for_scope", "dummy"), mode=mode, touched_files=touched)
                step_results.append({"step": i, "kind": kind, "overlay": overlay_ref, "mode": mode, "ok": True, "touched_files": touched, "patch_scope": patch_scope})
                print(f"[e2e-scenarios] {scenario_label} {step_name} done ok=True", flush=True)

            elif kind == 'lake_build':
                target = step['target']
                targets = _expand_lake_targets(target, step_results)
                expect_rc = int(step.get('expect_rc', 0))
                elapsed_ms_total = 0
                rc = 0
                failed_target: Optional[str] = None
                out_chunks: List[str] = []
                diags: List[Dict[str, Any]] = []
                for t in targets:
                    rc_i, out_i, elapsed_i = lake_build(
                        workdir,
                        t,
                        scenario_label=scenario_label,
                        phase=f"{step_name} lake build {t}",
                        log_dir=artifacts_root / "Cmd",
                        label=f"{step_name}__lake_build_{t.replace('.', '_')}",
                        timeout_s=args.lake_timeout_s,
                    )
                    elapsed_ms_total += int(elapsed_i)
                    out_chunks.append(f"$ lake build {t}\n{out_i}")
                    diags.extend(parse_diagnostics(out_i))
                    if rc_i != 0:
                        rc = int(rc_i)
                        failed_target = t
                        break
                rep = {
                    "step": i,
                    "kind": kind,
                    "target": target,
                    "expanded_targets": targets,
                    "failed_target": failed_target,
                    "rc": int(rc),
                    "elapsed_ms": int(elapsed_ms_total),
                    "diagnostics": diags,
                    "output_tail": "\n".join("\n".join(out_chunks).splitlines()[-200:]),
                }
                (artifacts_root / f"{step_name}__lake_build.json").write_text(json.dumps(rep, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
                if rc != expect_rc:
                    ok = False
                    step_results.append({**rep, "ok": False, "reason": f"rc {rc} != {expect_rc}"})
                else:
                    step_results.append({**rep, "ok": True})
                print(f"[e2e-scenarios] {scenario_label} {step_name} done ok={step_results[-1].get('ok', False)}", flush=True)
            elif kind == 'run_cmd':
                step_ok = True
                raw_cmd = step.get('cmd') or []
                if not isinstance(raw_cmd, list) or not raw_cmd:
                    ok = False
                    step_results.append({"step": i, "kind": kind, "ok": False, "reason": 'missing cmd[]'})
                    continue

                def subst(s: str) -> str:
                    return (s
                        .replace('${WORKDIR}', str(workdir))
                        .replace('${REPO}', str(repo_root))
                        .replace('${ARTIFACTS}', str(artifacts_root))
                    )

                cmd = [subst(str(x)) for x in raw_cmd]
                if cmd and cmd[0] in {'python', 'python3'}:
                    cmd[0] = sys.executable
                cwd_mode = (step.get('cwd') or 'repo')
                if cwd_mode == 'workdir':
                    cwd = workdir
                elif cwd_mode == 'repo':
                    cwd = repo_root
                else:
                    # treat as path relative to workdir
                    cwd = workdir / str(cwd_mode)

                env = dict(os.environ)
                for k, v in (step.get('env') or {}).items():
                    env[str(k)] = subst(str(v))
                cmd_log_dir = artifacts_root / "Cmd"
                cmd_log_dir.mkdir(parents=True, exist_ok=True)
                res = _run_cmd_with_progress(
                    scenario_label=scenario_label,
                    phase=f"{step_name} run_cmd",
                    cmd=cmd,
                    cwd=Path(cwd),
                    log_dir=cmd_log_dir,
                    label=f"{step_name}__run_cmd",
                    timeout_s=max(1, int(step.get('timeout_s', args.step_timeout_s))),
                    env=env,
                )
                p_rc = int(res.span.get("exit_code", 1))
                p_out = (res.stdout_text or "") + (f"\n{res.stderr_text}" if res.stderr_text else "")
                elapsed_ms = int(res.span.get("duration_ms", 0))
                rep = {
                    "step": i,
                    "kind": kind,
                    "cmd": cmd,
                    "cwd": str(cwd),
                    "rc": p_rc,
                    "elapsed_ms": int(elapsed_ms),
                    "output": p_out,
                }
                (artifacts_root / f"{step_name}__run_cmd.json").write_text(json.dumps(rep, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')

                expect_rc = int(step.get('expect_rc', 0))
                if p_rc != expect_rc:
                    step_ok = False
                    ok = False
                    step_results.append({**rep, "ok": False, "reason": f"rc {p_rc} != {expect_rc}"})
                    continue

                # Optional outputs checks
                out_checks = []
                for eo in (step.get('expect_outputs') or []):
                    path_str = subst(str((eo or {}).get('path', '')))
                    if not path_str:
                        continue
                    out_path = Path(path_str)
                    if not out_path.is_absolute():
                        out_path = cwd / out_path
                    exists = out_path.exists()
                    check = {"path": str(out_path), "exists": bool(exists)}
                    schema_ref = (eo or {}).get('schema')
                    if exists and schema_ref and str(out_path).endswith('.json'):
                        sp = repo_root / str(schema_ref)
                        try:
                            schema = json.loads(sp.read_text(encoding='utf-8'))
                            data = json.loads(out_path.read_text(encoding='utf-8'))
                            jsonschema.Draft202012Validator(schema).validate(data)
                            check['schema_ok'] = True
                        except Exception as e:
                            check['schema_ok'] = False
                            check['schema_error'] = str(e)
                            step_ok = False
                    if not exists:
                        step_ok = False
                    out_checks.append(check)

                if not step_ok:
                    ok = False

                rep2 = {**rep, "outputs": out_checks}
                step_results.append({**rep2, "ok": bool(step_ok)})
                print(f"[e2e-scenarios] {scenario_label} {step_name} done ok={bool(step_ok)}", flush=True)

            elif kind == 'clean':
                # Conservative clean inside workspace
                for p in (workdir / "Problems").rglob("Reports"):
                    if p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                if (workdir / "artifacts").exists():
                    shutil.rmtree(workdir / "artifacts", ignore_errors=True)
                step_results.append({"step": i, "kind": kind, "ok": True})
                print(f"[e2e-scenarios] {scenario_label} {step_name} done ok=True", flush=True)

            else:
                ok = False
                step_results.append({"step": i, "kind": kind, "ok": False, "reason": "unknown kind"})
                print(f"[e2e-scenarios] {scenario_label} {step_name} done ok=False", flush=True)

        scenario_report = {
            "schema": "leanatlas.e2e_scenario_report",
            "schema_version": "0.1.0",
            "scenario_id": scenario_id,
            "run_id": scenario_run_id,
            "ok": bool(ok),
            "steps": step_results,
            "workdir": str(workdir),
        }
        (artifacts_root / "ScenarioReport.json").write_text(json.dumps(scenario_report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

        if ok:
            print(f"[e2e-scenarios][OK] {scenario_id} ({scenario_run_id})", flush=True)
        else:
            print(f"[e2e-scenarios][FAIL] {scenario_id} ({scenario_run_id})", flush=True)
            rc_all = 1

    if args.keep_workdir:
        print(f"[e2e-scenarios] kept shared workdir: {shared_workdir}", flush=True)
    else:
        print(f"[e2e-scenarios] shared workdir: {shared_workdir}", flush=True)

    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
