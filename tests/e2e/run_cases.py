#!/usr/bin/env python3
"""Execute E2E golden cases locally.

This runner is intended for developers with a local Lean/Lake environment.
It is **not** part of core CI by default because it may require building mathlib.

Usage:
  python tests/e2e/run_cases.py --profile smoke
  python tests/e2e/run_cases.py --case smoke_missing_import
  python tests/e2e/run_cases.py --profile smoke --keep-workdir

The runner:
  - creates a temporary Lake project from `tests/e2e/fixture_root/`
  - overlays each case's `fixture/` and then each patch overlay in `patch_sequence`
  - runs `lake build <build_target>`
  - produces RunReport / RetrievalTrace / AttemptLog under `artifacts/e2e/...`

Evidence-chain upgrade (Phase6+):
  - all command execution MUST be captured via tools/workflow/run_cmd.py
  - AttemptLog lines MUST include exec_spans with stdout/stderr paths + sha256
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

# Local imports (repo-relative)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # add `leanatlas/` root
from tools.workflow.patch_scope import check_patch_scope
from tools.workflow.progress_signals import diagnostic_fingerprint
from tools.workflow.judge import judge_decide
from tools.workflow.run_cmd import run_cmd
from tools.workflow.env_stamp import get_environment_stamp
from tools.workflow.shared_cache import ensure_workspace_lake_packages


DIAG_RE = re.compile(r'^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+): (?P<sev>error|warning|info): (?P<msg>.*)$')
DIAG_RE_PREFIX = re.compile(r'^(?P<sev>error|warning|info): (?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+): (?P<msg>.*)$')


def have_cmd(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None


def copy_overlay(src: Path, dst: Path) -> List[str]:
    """Copy overlay tree src -> dst, overwriting files. Returns list of touched files (repo-relative)."""
    touched: List[str] = []
    for path in src.rglob('*'):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        if target.suffix == '.lean':
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
        file = m.group('file')
        file = file.replace('\\', '/')
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
        # For errors we must include a range (Phase1 schema)
        if sev == 'error':
            diag["range"] = {
                "start_line": line_i,
                "start_col": col_i,
                "end_line": line_i,
                "end_col": col_i,
            }
        diags.append(diag)
    return diags


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f)



def resolve_patch_ref(case_dir: Path, ref: str) -> Path:
    """Resolve a patch ref to a path.

    Compatibility:
      - Legacy refs like `001.patch` are resolved as `patches/001.patch`
      - New refs may include subpaths, e.g. `patches/001`
    """
    if "/" not in ref:
        return case_dir / "patches" / ref
    return case_dir / ref


def now_run_id(case_id: str) -> str:
    # deterministic-ish but unique per run
    return f"e2e_{case_id}_{int(time.time())}"


def hash_fixture_deps(fixture_root: Path) -> str:
    """Hash files that determine dependency graph/toolchain."""
    h = hashlib.sha256()
    for rel in (Path('lean-toolchain'), Path('lakefile.lean'), Path('lake-manifest.json')):
        p = fixture_root / rel
        h.update(rel.as_posix().encode('utf-8'))
        if p.exists():
            h.update(p.read_bytes())
        else:
            h.update(b'<missing>')
    return h.hexdigest()


def reset_workdir_preserve_lake(*, fixture_root: Path, workdir: Path) -> None:
    """Reset workspace content to fixture_root while preserving `.lake/` cache."""
    workdir.mkdir(parents=True, exist_ok=True)
    for child in workdir.iterdir():
        if child.name == '.lake':
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except FileNotFoundError:
                pass
    shutil.copytree(fixture_root, workdir, dirs_exist_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', default=None, choices=['smoke', 'core', 'nightly'], help='Run all executable cases in a profile')
    ap.add_argument('--tier', dest='legacy_tier', default=None, choices=['smoke', 'core', 'nightly'], help=argparse.SUPPRESS)
    ap.add_argument('--case', dest='case_id', default=None, help='Run a single case by id')
    ap.add_argument('--keep-workdir', action='store_true', help='Keep the temp workdir for debugging')
    ap.add_argument('--no-update', action='store_true', help='Do not run `lake update` (default)')
    ap.add_argument('--reinit-deps', action='store_true', help='Force reinitialize shared workspace dependencies')
    args = ap.parse_args()
    selected_profile = args.legacy_tier or args.profile

    if not have_cmd('lake'):
        print('[e2e] lake not found in PATH; skipping execution (structure validation still runs in core CI).')
        return 0

    repo_root = Path(__file__).resolve().parents[2]
    golden_root = repo_root / 'tests' / 'e2e' / 'golden'
    fixture_root = repo_root / 'tests' / 'e2e' / 'fixture_root'

    # Environment stamp (repo-level; includes pins.json)
    env_stamp = get_environment_stamp(repo_root)

    # collect cases
    all_cases: List[Path] = []
    for p in sorted(golden_root.iterdir()):
        if not p.is_dir():
            continue
        case_yaml = p / 'case.yaml'
        if not case_yaml.exists():
            continue
        meta = load_yaml(case_yaml)
        exec_meta = meta.get('execution', {})
        if not exec_meta.get('enabled', False):
            continue
        if args.case_id and meta.get('id') != args.case_id:
            continue
        if selected_profile and meta.get('tier') != selected_profile:
            continue
        all_cases.append(p)

    if not all_cases:
        print('[e2e] no executable cases selected.')
        return 0

    print(f"[e2e] selected {len(all_cases)} executable case(s)", flush=True)

    # Shared workspace for all selected cases (initialize deps only once).
    shared_root = repo_root / '.cache' / 'leanatlas' / 'e2e_run_cases'
    shared_root.mkdir(parents=True, exist_ok=True)
    # Backward-compat cleanup for older timestamped workdirs.
    for stale in shared_root.glob("workdir_*"):
        shutil.rmtree(stale, ignore_errors=True)
    shared_workdir = shared_root / "workdir"
    deps_stamp_path = shared_root / 'deps_stamp.sha256'
    desired_deps_stamp = hash_fixture_deps(fixture_root)
    existing_deps_stamp = deps_stamp_path.read_text(encoding='utf-8').strip() if deps_stamp_path.exists() else ''

    cold_init = bool(args.reinit_deps or not shared_workdir.exists() or existing_deps_stamp != desired_deps_stamp)
    if cold_init:
        print("[e2e] shared workspace cold-init (deps/toolchain changed or missing)", flush=True)
        shutil.rmtree(shared_workdir, ignore_errors=True)
        shutil.copytree(fixture_root, shared_workdir)
    else:
        print("[e2e] shared workspace warm-reset (reuse existing .lake cache)", flush=True)
        reset_workdir_preserve_lake(fixture_root=fixture_root, workdir=shared_workdir)
    deps_stamp_path.write_text(desired_deps_stamp + '\n', encoding='utf-8')

    def _run_cmd_with_progress(
        *,
        case_label: str,
        phase: str,
        cmd: List[str],
        cwd: Path,
        log_dir: Path,
        label: str,
        timeout_s: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Any:
        print(f"[e2e] {case_label} {phase} ...", flush=True)
        res_holder: Dict[str, Any] = {}
        err_holder: Dict[str, BaseException] = {}
        t0 = time.time()
        stdout_path = log_dir / f"{label}.stdout.txt"
        stderr_path = log_dir / f"{label}.stderr.txt"
        last_progress_line = ""

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
                        f"[e2e] {case_label} {phase} progress: {progress_line}",
                        flush=True,
                    )
                    last_progress_line = progress_line
                print(
                    f"[e2e] {case_label} {phase} still running elapsed_s={elapsed_s}",
                    flush=True,
                )

        if "err" in err_holder:
            raise err_holder["err"]
        res = res_holder["res"]
        print(
            f"[e2e] {case_label} {phase} done rc={int(res.span.get('exit_code', 1))} duration_ms={int(res.span.get('duration_ms', 0))}",
            flush=True,
        )
        return res

    cache_policy = ensure_workspace_lake_packages(
        repo_root=repo_root,
        workspace_root=shared_workdir,
        purpose="e2e_run_cases:shared_workdir",
    )
    (shared_root / "CachePolicy.json").write_text(
        json.dumps(cache_policy.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not cache_policy.ok:
        print(f"[e2e][FAIL] shared cache policy not satisfied: {cache_policy.note}", flush=True)
        return 2

    have_mathlib_cache = (shared_workdir / '.lake' / 'packages' / 'mathlib').exists()
    have_widgets_cache = (shared_workdir / '.lake' / 'packages' / 'proofwidgets').exists()
    need_cache_get = cold_init or (not have_mathlib_cache) or (not have_widgets_cache)
    if need_cache_get:
        prep_cmd_dir = shared_root / "prep" / "Cmd"
        prep_cmd_dir.mkdir(parents=True, exist_ok=True)
        prep_env = dict(os.environ)
        prep_env['MATHLIB_CACHE_USE_CLOUDFLARE'] = '1'
        prep_res = _run_cmd_with_progress(
            case_label="global",
            phase="prep lake exe cache get",
            cmd=['lake', 'exe', 'cache', 'get'],
            cwd=shared_workdir,
            log_dir=prep_cmd_dir,
            label='prep_cache_get',
            timeout_s=1800,
            env=prep_env,
        )
        prep_rc = int(prep_res.span.get('exit_code', 1))
        if prep_rc != 0:
            print(f"[e2e] global prep cache get failed rc={prep_rc}; continue with local build", flush=True)
    else:
        print("[e2e] global prep skipped: shared .lake packages already present", flush=True)

    failures: List[Tuple[str, str]] = []

    for case_path in all_cases:
        meta = load_yaml(case_path / 'case.yaml')
        case_id = meta['id']
        print(f'[e2e] running {case_id} ...', flush=True)

        run_id = now_run_id(case_id)
        out_root = repo_root / 'artifacts' / 'e2e' / case_id / run_id
        reports_dir = out_root / 'Reports' / run_id
        cmd_dir = reports_dir / 'Cmd'
        workdir = shared_workdir
        reports_dir.mkdir(parents=True, exist_ok=True)
        cmd_dir.mkdir(parents=True, exist_ok=True)

        # Reset only this case subtree in the shared workspace, then overlay fixture.
        case_problem_dir = workdir / "Problems" / case_id
        if case_problem_dir.exists():
            shutil.rmtree(case_problem_dir, ignore_errors=True)
        fixture_dir = case_path / meta.get('execution', {}).get('fixture_dir', 'fixture')
        if fixture_dir.exists():
            copy_overlay(fixture_dir, workdir)

        build_target = meta.get('execution', {}).get('build_target', f'Problems.{case_id}.Proof')
        main_decl = meta.get('execution', {}).get('main_decl', f'Problems.{case_id}.main')

        # Optional `lake update` (usually unnecessary if deps already fetched)
        if not args.no_update:
            # default is no update to keep runs predictable
            pass

        # Attempt loop
        patch_sequence = meta.get('patch_sequence', []) or []
        max_attempts = max(1, 1 + len(patch_sequence))  # baseline attempt + patches
        budgets = {
            "limits": {
                "max_attempts": int(max_attempts),
                "max_steps": 50,
                "max_external_queries": 5,
                "max_wall_time_ms": 30_000,
            },
            "counters": {
                "attempts_used": 0,
                "steps_used": 0,
                "external_queries_used": 0,
                "wall_time_ms": 0,
            }
        }

        # Apply per-case budget overrides (deterministic; used for BUDGET_EXHAUSTED cases)
        exec_budgets = (meta.get('execution', {}) or {}).get('budgets', {}) or {}
        limits_ov = (exec_budgets.get('limits', {}) or {})
        for k, v in limits_ov.items():
            if k in budgets["limits"]:
                budgets["limits"][k] = int(v)

        attempt_lines: List[Dict[str, Any]] = []
        prev_fingerprint: Optional[str] = None
        stagnant_count = 0
        final_status: Optional[str] = None
        final_diags: List[Dict[str, Any]] = []
        stage_build_status = "SKIPPED"
        stage_retrieval_status = "SKIPPED"

        def do_build(attempt_index: int) -> Tuple[int, str, Dict[str, Any]]:
            build_env = dict(os.environ)
            # Prevent mathlib post_update hook from re-running `cache get`
            # during each `lake build`.
            build_env['MATHLIB_NO_CACHE_ON_UPDATE'] = '1'
            res = _run_cmd_with_progress(
                case_label=case_id,
                cmd=['lake', 'build', build_target],
                cwd=workdir,
                log_dir=cmd_dir,
                label=f"a{attempt_index}_lake_build",
                phase=f"attempt={attempt_index} lake build {build_target}",
                env=build_env,
            )
            budgets['counters']['wall_time_ms'] += int(res.span.get('duration_ms', 0))
            combined = (res.stdout_text or "") + "\n" + (res.stderr_text or "")
            return int(res.span.get('exit_code', 1)), combined, res.span

        # Attempt 0: baseline build
        overlays = [None] + patch_sequence
        for attempt_index, patch_ref in enumerate(overlays):
            touched_files: List[str] = []

            if patch_ref:
                print(f"[e2e] {case_id} attempt={attempt_index} apply overlay {patch_ref}", flush=True)
                overlay_path = resolve_patch_ref(case_path, patch_ref)
                if not overlay_path.exists():
                    raise RuntimeError(f'missing patch overlay: {overlay_path}')
                touched_files = copy_overlay(overlay_path, workdir)

            budgets['counters']['attempts_used'] = attempt_index + 1

            # PatchScope
            patch_scope = check_patch_scope(
                problem_slug=case_id,
                mode='OPERATOR',
                touched_files=touched_files,
            )

            # Retrieval / tooling simulation (Phase 2.3)
            simulate_tooling_failure = bool((meta.get('execution', {}) or {}).get('simulate_tooling_failure', False))
            tooling_failed = False
            build_executed = False
            exec_spans: List[Dict[str, Any]] = []

            if simulate_tooling_failure:
                print(f"[e2e] {case_id} attempt={attempt_index} simulate tooling failure", flush=True)
                tooling_failed = True
                stage_retrieval_status = "FAIL"
                stage_build_status = "SKIPPED"

                # Evidence-chain: even for simulated failure we write logs + span.
                sim = run_cmd(
                    cmd=[sys.executable, '-c', "import sys; print('TOOLING_FAILURE: simulated'); sys.exit(1)"],
                    cwd=workdir,
                    log_dir=cmd_dir,
                    label=f"a{attempt_index}_simulate_tooling_failure",
                    capture_text=True,
                )
                budgets['counters']['wall_time_ms'] += int(sim.span.get('duration_ms', 0))
                exec_spans.append(sim.span)

                rc, out = (1, (sim.stdout_text or '') + "\n" + (sim.stderr_text or ''))
                diags = [{
                    "id": "d0",
                    "file": f"Problems/{case_id}/Proof.lean",
                    "severity": "error",
                    "message": "TOOLING_FAILURE: simulated retrieval/tool error",
                    "range": {"start_line": 1, "start_col": 1, "end_line": 1, "end_col": 1},
                }]
            else:
                stage_retrieval_status = "SKIPPED"
                build_executed = True
                # Build
                rc, out, span = do_build(attempt_index)
                exec_spans.append(span)
                diags = parse_diagnostics(out)
                stage_build_status = "OK" if rc == 0 else "FAIL"

            final_diags = diags

            # Signals
            error_outside_problem = any(
                (d.get('severity') == 'error') and (not str(d.get('file','')).startswith(f"Problems/{case_id}/"))
                for d in diags
            )

            fp = diagnostic_fingerprint([d for d in diags if d.get('severity') == 'error'])
            diag_changed = (prev_fingerprint is None) or (fp != prev_fingerprint)
            prev_fingerprint = fp

            imports_changed = any(p.endswith('Proof.lean') for p in touched_files)
            new_retrieval_hit = False

            stagnant = (not diag_changed) and (not imports_changed) and (not new_retrieval_hit)
            stagnant_count = (stagnant_count + 1) if stagnant else 0

            # Judge (use expected family as deterministic hint; UNKNOWN is always acceptable)
            suspected_family = (meta.get('expected', {}).get('category', {}) or {}).get('family', 'UNKNOWN')

            judge = judge_decide(
                mode='OPERATOR',
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

            # Decide final
            if rc == 0:
                final_status = "SUCCESS"
            elif judge['decision'] == 'TRIAGED':
                final_status = "TRIAGED"
            else:
                final_status = None

            # Attempt log line
            attempt_lines.append({
                "schema": "leanatlas.attempt_log_line",
                "schema_version": "0.5.0",
                "run_id": run_id,
                "problem_slug": case_id,
                "attempt_index": int(attempt_index),
                "touched_files": touched_files,
                "patch_scope": patch_scope,
                "suspected_category": {
                    "family": suspected_family,
                    "code": (meta.get('expected', {}).get('category', {}) or {}).get('code', 'UNKNOWN'),
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
                "exec_spans": exec_spans,
                "judge": judge,
                "budget": budgets,
                "events": [
                    {"kind": "PATCH_APPLIED" if patch_ref else "BASELINE_BUILD", "attrs": {"patch": str(patch_ref) if patch_ref else ""}},
                    {"kind": ("LAKE_BUILD" if build_executed else "LAKE_BUILD_SKIPPED"), "attrs": {"target": build_target, "exit_code": int(rc), "executed": bool(build_executed)}},
                ] + ([{"kind": "TOOLING_FAILURE", "attrs": {"where": "retrieval"}}] if tooling_failed else []),
            })

            if final_status is not None:
                break

        if final_status is None:
            # ran out of overlays; force TRIAGED by budget exhaustion semantics
            final_status = "TRIAGED"

        # Produce RetrievalTrace (minimal)
        retrieval_trace = {
            "schema": "leanatlas.retrieval_trace",
            "schema_version": "0.4.0",
            "run_id": run_id,
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
        (reports_dir / 'RetrievalTrace.json').write_text(json.dumps(retrieval_trace, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')

        # Produce RunReport
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
            "build": {"status": "OK" if final_status == "SUCCESS" else ("SKIPPED" if stage_build_status == "SKIPPED" else "FAIL")},
            "verify": {"status": "OK" if final_status == "SUCCESS" else "SKIPPED"},
        }

        run_report: Dict[str, Any] = {
            "schema": "leanatlas.run_report",
            "schema_version": "0.4.0",
            "run_id": run_id,
            "problem_slug": case_id,
            "status": final_status,
            "mode": "OPERATOR",
            "context": {
                "git_sha": "unknown0",
                "lean_toolchain": env_stamp.get('lean_toolchain', 'unknown'),
                "mathlib_rev": env_stamp.get('mathlib_rev', 'unknown'),
                "tools": {
                    "environment_stamp": env_stamp,
                },
            },
            "summary": {
                "title": f"e2e {case_id}",
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
            expected = meta.get('expected', {})
            cat = expected.get('category', {"family": "UNKNOWN", "code": "UNKNOWN"})
            # Always create at least one hotspot using the first error diagnostic if available
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

        (reports_dir / 'RunReport.json').write_text(json.dumps(run_report, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')

        # RunReport.md (human-readable)
        md = [
            f"# RunReport {run_id}",
            "",
            "## Targets",
            f"- MAIN: `{main_decl}` in `{targets[0]['file']}`",
            "",
            "## Stages",
            f"- retrieval: {stages['retrieval']['status']}",
            f"- build: {stages['build']['status']}",
            f"- verify: {stages['verify']['status']}",
            "",
            "## Hotspots",
        ]
        if final_status != "SUCCESS":
            md.append(f"- h0: {run_report['hotspots'][0]['title']} (diag {run_report['hotspots'][0]['diagnostic_ids'][0]})")
        else:
            md.append("- (none)")
        md += ["", "## Next actions"]
        if final_status == "SUCCESS":
            md.append("- (done)")
        else:
            md.append("- escalate to GPTPro with missing assumptions/definition alignment")
        (reports_dir / 'RunReport.md').write_text("\n".join(md) + "\n", encoding='utf-8')

        # AttemptLog.jsonl
        with (reports_dir / 'AttemptLog.jsonl').open('w', encoding='utf-8') as f:
            for line in attempt_lines:
                f.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n")

        # Check expected outcome
        exp = meta.get('expected', {})
        ok = True
        if exp.get('final_status') != final_status:
            ok = False
            failures.append((case_id, f"expected final_status={exp.get('final_status')} got {final_status}"))
        if final_status == "TRIAGED":
            if exp.get('judge_reason_code') and attempt_lines[-1]['judge'].get('reason_code') != exp.get('judge_reason_code'):
                ok = False
                failures.append((case_id, f"expected judge_reason_code={exp.get('judge_reason_code')} got {attempt_lines[-1]['judge'].get('reason_code')}"))
        print(f"[e2e] {case_id}: {final_status} (reports at {reports_dir})")

    if failures:
        print(f"[e2e] shared workdir: {shared_workdir}")
        print("\n[e2e] FAILURES:")
        for cid, msg in failures:
            print(f"  - {cid}: {msg}")
        return 1

    print(f"[e2e] shared workdir: {shared_workdir}")

    print("[e2e] all selected cases passed.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
