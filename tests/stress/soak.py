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
    args = ap.parse_args()
    selected_profile = args.legacy_tier or args.profile

    if not have_cmd("lake"):
        print("[soak] lake not found in PATH; skipping.")
        return 0

    repo_root = Path(__file__).resolve().parents[2]
    golden_root = repo_root / "tests" / "e2e" / "golden"
    fixture_root = repo_root / "tests" / "e2e" / "fixture_root"

    # collect executable cases (tier filter is exact, intentionally)
    cases: List[str] = []
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
        cases.append(meta["id"])

    if not cases:
        print("[soak] no cases selected")
        return 0

    # workspace
    tmp_root = repo_root / ".cache" / "leanatlas" / "soak"
    tmp_root.mkdir(parents=True, exist_ok=True)
    run_id = f"soak-{int(time.time())}"
    workdir = tmp_root / run_id
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(fixture_root, workdir)
    cache_policy = ensure_workspace_lake_packages(
        repo_root=repo_root,
        workspace_root=workdir,
        purpose="stress_soak_workspace",
    )
    if not cache_policy.ok:
        print(f"[soak][FAIL] shared cache policy not satisfied: {cache_policy.note}")
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
        print(f"[soak] iteration {it+1}/{args.iterations}: {order}")

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
            )
            total_wall += int(res.get("wall_time_ms", 0))
            exp = (meta.get("expected", {}) or {}).get("final_status")
            if exp and res["final_status"] != exp:
                failures += 1
                print(f"[soak][FAIL] {case_id}: got {res['final_status']} expected {exp} (judge={res.get('judge_reason_code')})")

        if args.build_all_each_iter:
            rc, out, elapsed_ms = lake_build(workdir, "Problems")
            total_wall += int(elapsed_ms)
            if rc != 0:
                failures += 1
                print(f"[soak][FAIL] lake build Problems after iter {it}: rc={rc}")

    print(f"[soak] done: iterations={args.iterations} cases={len(cases)} failures={failures} total_wall_ms={total_wall}")

    if not args.keep_workdir:
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        print(f"[soak] kept workdir: {workdir}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
