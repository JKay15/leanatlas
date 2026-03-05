#!/usr/bin/env python3
"""Soak / stress runner for LeanAtlas E2E cases (manual/nightly).

Runs many golden cases sequentially in the *same* workspace.

This is intentionally "extreme": it tries to surface bugs like
- cross-case interference
- state leaks (cached outputs, uncleaned reports, etc.)
- flakiness across repetitions

Usage:
  python tests/stress/soak.py --iterations 10 --profile core --shuffle --seed 0
"""

from __future__ import annotations

import argparse
import os
import random
import uuid
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

import yaml  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.e2e.run_scenarios import (
    have_cmd,
    load_yaml,
    execute_case_in_workdir,
    lake_build,
    hash_fixture_deps,
    reset_workdir_preserve_lake,
)
from tools.workflow.shared_cache import ensure_workspace_lake_packages


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=10, help="Number of repetitions")
    ap.add_argument("--profile", choices=["smoke", "core", "nightly"], default="core", help="Select cases by profile")
    ap.add_argument("--tier", dest="legacy_tier", choices=["smoke", "core", "nightly"], help=argparse.SUPPRESS)
    ap.add_argument("--shuffle", action="store_true", help="Shuffle case order per iteration")
    ap.add_argument("--seed", type=int, default=0, help="Shuffle seed")
    ap.add_argument("--keep-workdir", action="store_true", help="Keep workspace for debugging")
    ap.add_argument("--update", action="store_true", help="Run `lake update` once before starting")
    ap.add_argument("--build_all_each_iter", action="store_true", help="Also run `lake build Problems` after each iteration")
    ap.add_argument("--lake-timeout-s", type=int, default=900, help="Timeout (seconds) for each `lake build` in case/scenario execution")
    args = ap.parse_args()
    selected_profile = args.legacy_tier or args.profile

    if not have_cmd("lake"):
        print("[soak] lake not found in PATH; skipping.", flush=True)
        return 0

    repo_root = Path(__file__).resolve().parents[2]
    golden_root = repo_root / "tests" / "e2e" / "golden"
    fixture_root = repo_root / "tests" / "e2e" / "fixture_root"

    # collect executable cases (tier filter is exact, intentionally)
    cases: List[str] = []
    expected_final_by_case: Dict[str, str] = {}
    for p in sorted(golden_root.iterdir()):
        if not p.is_dir():
            continue
        case_yaml = p / "case.yaml"
        if not case_yaml.exists():
            continue
        meta = load_yaml(case_yaml)
        exec_meta = meta.get("execution", {}) or {}
        if not exec_meta.get("enabled", False):
            continue
        if meta.get("tier") != selected_profile:
            continue
        case_id = meta["id"]
        cases.append(case_id)
        expected = (meta.get("expected", {}) or {})
        expected_final_by_case[case_id] = str(expected.get("final_status", "SUCCESS")).upper()

    if not cases:
        print("[soak] no cases selected", flush=True)
        return 0

    strict_build_all = all(expected_final_by_case.get(case_id, "SUCCESS") == "SUCCESS" for case_id in cases)
    if args.build_all_each_iter:
        mode = "strict" if strict_build_all else "observe_only"
        print(
            f"[soak] build_all_each_iter mode={mode} "
            f"(strict requires all selected cases expected SUCCESS)",
            flush=True,
        )

    # Reuse run_cases shared workspace so stress/scenario/case runners do not
    # materialize multiple giant `.lake` workspace trees.
    shared_root = repo_root / ".cache" / "leanatlas" / "e2e_run_cases"
    shared_root.mkdir(parents=True, exist_ok=True)
    shared_workdir = shared_root / "workdir"
    deps_stamp_path = shared_root / "deps_stamp.sha256"
    desired_deps_stamp = hash_fixture_deps(fixture_root)
    existing_deps_stamp = deps_stamp_path.read_text(encoding="utf-8").strip() if deps_stamp_path.exists() else ""
    cold_init = bool((not shared_workdir.exists()) or (existing_deps_stamp != desired_deps_stamp))

    if cold_init:
        print("[soak] shared workspace cold-init (deps/toolchain changed or missing)", flush=True)
        shutil.rmtree(shared_workdir, ignore_errors=True)
        shutil.copytree(fixture_root, shared_workdir)
    else:
        print("[soak] shared workspace warm-reset (reuse existing .lake cache)", flush=True)
        reset_workdir_preserve_lake(fixture_root=fixture_root, workdir=shared_workdir)
    deps_stamp_path.write_text(desired_deps_stamp + "\n", encoding="utf-8")

    run_id = f"soak-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    workdir = shared_workdir
    cache_policy = ensure_workspace_lake_packages(
        repo_root=repo_root,
        workspace_root=workdir,
        purpose="stress_soak_workspace:shared_workdir",
    )
    if not cache_policy.ok:
        print(f"[soak][FAIL] shared cache policy not satisfied: {cache_policy.note}", flush=True)
        return 2

    if args.update:
        subprocess.run(["lake", "update"], cwd=str(workdir))

    rng = random.Random(args.seed)

    total_wall = 0
    failures = 0

    for it in range(args.iterations):
        order = list(cases)
        if args.shuffle:
            rng.shuffle(order)
        print(f"[soak] iteration {it+1}/{args.iterations}: {order}", flush=True)

        for case_id in order:
            case_path = golden_root / case_id
            meta = load_yaml(case_path / "case.yaml")

            out_dir = repo_root / "artifacts" / "stress" / "soak" / run_id / f"iter_{it:03d}" / case_id
            res = execute_case_in_workdir(
                workdir=workdir,
                case_id=case_id,
                case_path=case_path,
                meta=meta,
                out_dir=out_dir,
                expected_override=None,
                mode="OPERATOR",
                scenario_label=f"soak:{run_id}:iter{it:03d}",
                lake_timeout_s=args.lake_timeout_s,
            )
            total_wall += int(res.get("wall_time_ms", 0))
            exp = (meta.get("expected", {}) or {}).get("final_status")
            if exp and res["final_status"] != exp:
                failures += 1
                print(
                    f"[soak][FAIL] {case_id}: got {res['final_status']} expected {exp} (judge={res.get('judge_reason_code')})",
                    flush=True,
                )

        if args.build_all_each_iter:
            rc, out, elapsed_ms = lake_build(
                workdir,
                "Problems",
                scenario_label=f"soak:{run_id}:iter{it:03d}",
                phase="build_all_each_iter",
                log_dir=repo_root / "artifacts" / "stress" / "soak" / run_id / "Cmd",
                label=f"iter_{it:03d}__build_all",
                timeout_s=args.lake_timeout_s,
            )
            total_wall += int(elapsed_ms)
            if rc != 0:
                if strict_build_all:
                    failures += 1
                    print(f"[soak][FAIL] lake build Problems after iter {it}: rc={rc}", flush=True)
                else:
                    print(
                        "[soak][WARN] lake build Problems returned non-zero in observe_only mode; "
                        "selected profile includes non-SUCCESS expected cases.",
                        flush=True,
                    )

    print(
        f"[soak] done: iterations={args.iterations} cases={len(cases)} failures={failures} total_wall_ms={total_wall}",
        flush=True,
    )

    if args.keep_workdir:
        print(f"[soak] kept shared workdir: {workdir}", flush=True)
    else:
        print(f"[soak] shared workdir: {workdir}", flush=True)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
