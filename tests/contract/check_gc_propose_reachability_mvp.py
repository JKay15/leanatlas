#!/usr/bin/env python3
"""Contract-ish test: GCGate.propose reachability MVP must actually propose quarantine for stale unreachable seeds.

Why core?
- We don't run Lean here.
- The GC proposer must remain deterministic and not a stub.

We create a tiny synthetic repo tree (no lake, no mathlib) and rely on the
fallback import scanner. The test checks that:
- domain progress clock is computed from Problems/*/State.json (ever_succeeded)
- staleness threshold triggers quarantine when seed is unreachable
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GC = ROOT / "tools" / "gc" / "gc.py"


def write(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def write_json(p: Path, obj) -> None:
    write(p, json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def minimal_state(slug: str, domain_id: str, status: str, ever_succeeded: bool) -> dict:
    return {
        "version": "0.2",
        "problem_slug": slug,
        "domain": {"domain_id": domain_id, "msc": []},
        "status": status,
        "ever_succeeded": bool(ever_succeeded),
        "counters": {"attempts": 1, "successes": 1 if ever_succeeded else 0, "triaged": 0, "last_status": status},
        "last_run": {"run_id": "RunReport_20260223_000000", "status": status, "run_report_path": f"Problems/{slug}/Reports/RunReport_20260223_000000/RunReport.json"},
    }


def main() -> int:
    if not GC.exists():
        print("[gc-propose][FAIL] missing tools/gc/gc.py", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="leanatlas_gc_fixture_") as td:
        repo = Path(td)

        # Local modules (Seeds)
        write(
            repo / "LeanAtlas" / "Incubator" / "Seeds" / "Demo" / "SeedA.lean",
            "import Mathlib\n\nnamespace LeanAtlas.Incubator.Seeds.Demo\n\n-- reachable seed\ntheorem seedA : True := by trivial\n\nend LeanAtlas.Incubator.Seeds.Demo\n",
        )
        write(
            repo / "LeanAtlas" / "Incubator" / "Seeds" / "Demo" / "SeedStale.lean",
            "import Mathlib\n\nnamespace LeanAtlas.Incubator.Seeds.Demo\n\n-- unreachable seed\ntheorem seedStale : True := by trivial\n\nend LeanAtlas.Incubator.Seeds.Demo\n",
        )

        # Toolbox (root)
        write(
            repo / "LeanAtlas" / "Toolbox" / "Imports.lean",
            "import Mathlib\n\nnamespace LeanAtlas.Toolbox\nend LeanAtlas.Toolbox\n",
        )

        # Problems: 10 SUCCESS to advance domain clock
        for i in range(10):
            slug = f"p_success_{i}"
            write_json(repo / "Problems" / slug / "State.json", minimal_state(slug, "Demo", "SUCCESS", True))

        # One ACTIVE problem that imports SeedA (so SeedA is used/reachable)
        write_json(repo / "Problems" / "p_active" / "State.json", minimal_state("p_active", "Demo", "ACTIVE", True))
        write(
            repo / "Problems" / "p_active" / "Proof.lean",
            "import LeanAtlas.Incubator.Seeds.Demo.SeedA\n\nnamespace Problems.p_active\n\n-- dummy proof\ntheorem ok : True := by trivial\n\nend Problems.p_active\n",
        )

        # gc_state: mark SeedStale as old (introduced at clock 0, never used)
        write_json(
            repo / "tools" / "index" / "gc_state.json",
            {
                "version": "0.2",
                "seeds": {
                    "LeanAtlas.Incubator.Seeds.Demo.SeedStale": {"state": "active", "introduced_at_clock": 0, "last_used_clock": 0},
                    "LeanAtlas.Incubator.Seeds.Demo.SeedA": {"state": "active", "introduced_at_clock": 0, "last_used_clock": 10},
                },
            },
        )

        out = repo / "out"
        cmd = [sys.executable, str(GC), "propose", "--repo-root", str(repo), "--out-root", str(out), "--mode", "OPERATOR"]
        p = subprocess.run(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if p.returncode != 0:
            print("[gc-propose][FAIL] proposer returned non-zero", file=sys.stderr)
            print(p.stdout)
            print(p.stderr, file=sys.stderr)
            return 1

        plan_path = out / "GCPlan.json"
        if not plan_path.exists():
            print("[gc-propose][FAIL] missing GCPlan.json", file=sys.stderr)
            return 1

        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        actions = plan.get("actions") or []
        # We expect quarantine for SeedStale because:
        # - domain_clock(Demo)=11 (10 successes + p_active ever_succeeded)
        # - last_used_clock=0 => staleness >= 8
        wanted = [a for a in actions if a.get("seed_id") == "LeanAtlas.Incubator.Seeds.Demo.SeedStale" and a.get("action") == "quarantine"]
        if not wanted:
            print("[gc-propose][FAIL] expected quarantine action for SeedStale", file=sys.stderr)
            print("actions:")
            print(json.dumps(actions, indent=2, ensure_ascii=False))
            return 1

        print("[gc-propose][OK] quarantine action present for stale unreachable seed")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
