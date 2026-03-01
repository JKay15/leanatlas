#!/usr/bin/env python3
"""AttemptLog / RunReport / RetrievalTrace / Promotion / GC mining (deterministic).

This tool aggregates *existing* run artifacts into a machine-readable summary.

Inputs (root can be any of these):
- artifacts/telemetry/**            (automation-collected run roots)
- Problems/**/Reports/**           (local, gitignored runs)
- docs/examples/**                 (committed minimal examples)

A "run directory" is detected by the presence of at least one marker file:
- AttemptLog.jsonl
- PromotionReport.json
- GCReport.json

We opportunistically parse related files when present:
- RunReport.json
- RetrievalTrace.json

Design goals (Phase5 / platform):
- Deterministic: no network, no LLM, stable output for same inputs.
- Automation-friendly: if input root is missing/empty, still emit a valid report
  (so automation dry-runs don't rot in empty environments).

Strictness:
- default: best-effort; parsing errors become warnings; exit code stays 0
- --strict: any parsing / missing-file error becomes non-zero

Output (BENCH_CONTRACT v0):
- JSON with schema/schema_version/input/summary/warnings
- plus optional triage/retrieval/attempts/promotion/gc breakdowns
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


RUN_MARKERS = {
    "AttemptLog.jsonl",
    "PromotionReport.json",
    "GCReport.json",
}


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def warn(warnings: List[str], msg: str) -> None:
    warnings.append(msg)


def safe_read_json(path: Path, warnings: List[str], strict: bool) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        warn(warnings, f"failed to parse json: {path}: {e}")
        if strict:
            raise
        return None


def safe_read_jsonl(path: Path, warnings: List[str], strict: bool) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        out.append(obj)
                    else:
                        warn(warnings, f"jsonl line is not object: {path}:{i+1}")
                        if strict:
                            raise ValueError("jsonl line is not object")
                except Exception as e:
                    warn(warnings, f"failed to parse jsonl: {path}:{i+1}: {e}")
                    if strict:
                        raise
    except Exception as e:
        warn(warnings, f"failed to read jsonl: {path}: {e}")
        if strict:
            raise
    return out


def looks_like_run_dir(d: Path) -> bool:
    if not d.is_dir():
        return False
    for m in RUN_MARKERS:
        if (d / m).exists():
            return True
    return False


def discover_run_dirs(root: Path) -> List[Path]:
    """Find run directories under root.

    Heuristic: any directory that contains one of RUN_MARKERS.
    """
    if not root.exists():
        return []

    if root.is_file():
        # If a user points directly at a run file, use its parent.
        if root.name in RUN_MARKERS or root.name in {"RunReport.json", "RetrievalTrace.json"}:
            d = root.parent
            return [d] if looks_like_run_dir(d) else []
        return []

    run_dirs: List[Path] = []
    for marker in sorted(RUN_MARKERS):
        for p in root.rglob(marker):
            d = p.parent
            if looks_like_run_dir(d):
                run_dirs.append(d)

    # Deterministic ordering
    return sorted(set(run_dirs), key=lambda x: x.as_posix())


@dataclass
class Counters:
    counts: Dict[str, int]

    def inc(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + int(n)


def pct(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return float(num) / float(den)


def _cmd_binary(cmd: Any) -> Optional[str]:
    if not isinstance(cmd, list) or not cmd:
        return None
    if not all(isinstance(x, str) for x in cmd):
        return None
    bin0 = str(cmd[0]).strip()
    return bin0 if bin0 else None


def _cmd_key(cmd: Any) -> Optional[str]:
    """Normalize exec_spans.cmd into a stable usage key.

    Policy:
    - use `cmd[0]` as binary key
    - prefer `cmd[0] + cmd[1]` when argv[1] exists and is not a flag
    """
    if not isinstance(cmd, list) or not cmd:
        return None
    if not all(isinstance(x, str) for x in cmd):
        return None

    bin0 = str(cmd[0]).strip()
    if not bin0:
        return None

    if len(cmd) >= 2:
        argv1 = str(cmd[1]).strip()
        if argv1 and not argv1.startswith("-"):
            return f"{bin0} {argv1}"
    return bin0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input root (dir or file)")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Fail (non-zero) on parse errors / missing files",
    )
    args = ap.parse_args()

    inp = Path(args.inp)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    warnings: List[str] = []

    run_dirs = discover_run_dirs(inp)
    if not inp.exists():
        warn(warnings, f"input root does not exist: {inp}")

    strict = bool(args.strict)

    # Aggregates (AttemptLog/RunReport)
    run_status = Counters({})
    triage_family = Counters({})
    triage_code = Counters({})
    triage_level = Counters({})

    attempt_decisions = Counters({})
    attempt_reasons = Counters({})
    patch_scope_verdict = Counters({})
    signal_counts = Counters({})
    tool_binary_counts = Counters({})
    tool_command_counts = Counters({})
    tool_total_exec_spans = 0

    # Retrieval
    retrieval_results = Counters({})
    retrieval_layer_hits = Counters({})
    retrieval_layer_total = Counters({})
    runs_with_retrieval_hit = 0

    # Promotion
    promotion_decision = Counters({})  # PASSED / FAILED
    promotion_reason = Counters({})
    promotion_gate_fail = Counters({})

    # GC
    gc_action = Counters({})

    # Per-run parse
    for d in run_dirs:
        # AttemptLog.jsonl (optional)
        al_path = d / "AttemptLog.jsonl"
        if al_path.exists():
            attempts = safe_read_jsonl(al_path, warnings, strict)
            for a in attempts:
                j = a.get("judge") or {}
                if isinstance(j, dict):
                    dec = j.get("decision")
                    if isinstance(dec, str) and dec:
                        attempt_decisions.inc(dec)

                    rc = j.get("reason_code")
                    if isinstance(rc, str) and rc:
                        attempt_reasons.inc(rc)

                ps = a.get("patch_scope") or {}
                if isinstance(ps, dict):
                    v = ps.get("verdict")
                    if isinstance(v, str) and v:
                        patch_scope_verdict.inc(v)

                sig = a.get("signals") or {}
                if isinstance(sig, dict):
                    # Keep the signal surface small + stable.
                    for k in (
                        "new_retrieval_hit",
                        "stagnant",
                        "diag_changed",
                        "imports_changed",
                        "error_outside_problem",
                    ):
                        v = sig.get(k)
                        if v is True:
                            signal_counts.inc(k)

                spans = a.get("exec_spans")
                if isinstance(spans, list):
                    for i, span in enumerate(spans):
                        if not isinstance(span, dict):
                            warn(warnings, f"attempt exec_span is not object: {al_path}:{i+1}")
                            if strict:
                                raise ValueError("exec_span is not object")
                            continue
                        cmd = span.get("cmd")
                        b = _cmd_binary(cmd)
                        k = _cmd_key(cmd)
                        if b is None or k is None:
                            warn(warnings, f"attempt exec_span missing/invalid cmd: {al_path}:{i+1}")
                            if strict:
                                raise ValueError("exec_span cmd invalid")
                            continue
                        tool_total_exec_spans += 1
                        tool_binary_counts.inc(b)
                        tool_command_counts.inc(k)

        # RunReport.json (optional)
        rr_path = d / "RunReport.json"
        rr = safe_read_json(rr_path, warnings, strict) if rr_path.exists() else None
        if rr is not None:
            st = rr.get("status")
            if isinstance(st, str) and st:
                run_status.inc(st)

            tri = rr.get("triage")
            if isinstance(tri, dict):
                cat = tri.get("category")
                if isinstance(cat, dict):
                    fam = cat.get("family")
                    if isinstance(fam, str) and fam:
                        triage_family.inc(fam)
                    code = cat.get("code")
                    if isinstance(code, str) and code:
                        triage_code.inc(code)

                lvl = tri.get("level")
                if isinstance(lvl, str) and lvl:
                    triage_level.inc(lvl)

        # RetrievalTrace.json (optional)
        rt_path = d / "RetrievalTrace.json"
        rt = safe_read_json(rt_path, warnings, strict) if rt_path.exists() else None
        if rt is not None:
            steps = rt.get("steps")
            if isinstance(steps, list):
                any_hit = False
                for s in steps:
                    if not isinstance(s, dict):
                        continue
                    res = s.get("result")
                    if isinstance(res, str) and res:
                        retrieval_results.inc(res)
                        if res == "HIT":
                            any_hit = True

                    layer = s.get("layer")
                    if isinstance(layer, str) and layer:
                        retrieval_layer_total.inc(layer)
                        if s.get("result") == "HIT":
                            retrieval_layer_hits.inc(layer)

                if any_hit:
                    runs_with_retrieval_hit += 1

        # PromotionReport.json (optional)
        pr_path = d / "PromotionReport.json"
        pr = safe_read_json(pr_path, warnings, strict) if pr_path.exists() else None
        if pr is not None:
            dec = pr.get("decision")
            if isinstance(dec, dict):
                passed = dec.get("passed")
                if passed is True:
                    promotion_decision.inc("PASSED")
                elif passed is False:
                    promotion_decision.inc("FAILED")
                rc = dec.get("reason_code")
                if isinstance(rc, str) and rc:
                    promotion_reason.inc(rc)

            gates = pr.get("gates")
            if isinstance(gates, list):
                for g in gates:
                    if not isinstance(g, dict):
                        continue
                    gate_name = g.get("gate")
                    passed = g.get("passed")
                    if isinstance(gate_name, str) and gate_name and passed is False:
                        promotion_gate_fail.inc(gate_name)

        # GCReport.json (optional)
        gr_path = d / "GCReport.json"
        gr = safe_read_json(gr_path, warnings, strict) if gr_path.exists() else None
        if gr is not None:
            actions = gr.get("actions")
            if isinstance(actions, list):
                for a in actions:
                    if not isinstance(a, dict):
                        continue
                    act = a.get("action")
                    if isinstance(act, str) and act:
                        gc_action.inc(act)

    # Derived summaries
    total_runs = len(run_dirs)

    top_failure_families = sorted(
        ({"family": k, "count": v} for k, v in triage_family.counts.items()),
        key=lambda x: (-int(x["count"]), str(x["family"])),
    )

    total_retrieval_steps = sum(retrieval_results.counts.values())
    total_hits = retrieval_results.counts.get("HIT", 0)

    promotion_runs = sum(promotion_decision.counts.values())
    promotion_passed = promotion_decision.counts.get("PASSED", 0)
    top_commands = sorted(
        ({"command": k, "count": v} for (k, v) in tool_command_counts.counts.items()),
        key=lambda x: (-int(x["count"]), str(x["command"])),
    )[:20]

    report: Dict[str, Any] = {
        "schema": "leanatlas.bench.mine_attempt_logs",
        "schema_version": "0.3.0",
        "input": str(inp),
        "summary": {
            "run_count": total_runs,
            "runs_with_retrieval_hit": runs_with_retrieval_hit,
            "retrieval_hit_rate": round(pct(total_hits, total_retrieval_steps), 6),
            "promotion_run_count": int(promotion_runs),
            "promotion_pass_rate": round(pct(promotion_passed, promotion_runs), 6) if promotion_runs else 0.0,
        },
        "triage": {
            "run_status_counts": run_status.counts,
            "category_family_counts": triage_family.counts,
            "category_code_counts": triage_code.counts,
            "level_counts": triage_level.counts,
            "top_failure_families": top_failure_families,
        },
        "retrieval": {
            "step_result_counts": retrieval_results.counts,
            "layer_total_counts": retrieval_layer_total.counts,
            "layer_hit_counts": retrieval_layer_hits.counts,
        },
        "attempts": {
            "decision_counts": attempt_decisions.counts,
            "reason_code_counts": attempt_reasons.counts,
            "patch_scope_verdict_counts": patch_scope_verdict.counts,
            "signal_true_counts": signal_counts.counts,
        },
        "tool_usage": {
            "source": "AttemptLog.exec_spans[*].cmd",
            "command_key_policy": "binary_or_binary_argv1_nonflag",
            "total_exec_spans": int(tool_total_exec_spans),
            "binary_counts": tool_binary_counts.counts,
            "command_counts": tool_command_counts.counts,
            "top_commands": top_commands,
        },
        "promotion": {
            "decision_counts": promotion_decision.counts,
            "reason_code_counts": promotion_reason.counts,
            "gate_fail_counts": promotion_gate_fail.counts,
        },
        "gc": {
            "action_counts": gc_action.counts,
        },
        "warnings": warnings,
    }

    out_path.write_text(canonical_json(report), encoding="utf-8")
    print(f"[bench.mine_attempt_logs] wrote {out_path} (runs={total_runs})")

    if strict and warnings:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[bench.mine_attempt_logs] FATAL: {e}", file=sys.stderr)
        raise
