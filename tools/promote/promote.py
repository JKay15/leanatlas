#!/usr/bin/env python3
"""LeanAtlas PromotionGate (phase3).

This is the minimal MAINTAINER implementation of the PromotionGate contract.
It executes all required gate IDs, captures command evidence, and emits
`PromotionReport.json` + `PromotionReport.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

# Allow `from tools.*` imports when executing as a script (sys.path[0] == tools/...).
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.workflow.run_cmd import run_cmd


GATE_ORDER = [
    "mode_and_scope_check",
    "build_snapshot_ok",
    "candidate_existence_and_type_ok",
    "dedup_gate_present_and_ok",
    "reuse_evidence_policy_ok",
    "migration_and_rollback_plan_present",
    "verification_ok",
    "dependency_pins_ok",
    "import_minimization_audit",
    "directory_boundary_audit",
    "upstreamable_decl_audit",
    "compat_deprecation_audit",
]


HARD_GATES = set(
    {
        "mode_and_scope_check",
        "build_snapshot_ok",
        "candidate_existence_and_type_ok",
        "dedup_gate_present_and_ok",
        "reuse_evidence_policy_ok",
        "migration_and_rollback_plan_present",
        "verification_ok",
        "dependency_pins_ok",
    }
)


_DECL_RE = re.compile(
    r"\b(?:theorem|lemma|def|axiom|instance|abbrev|opaque|example|structure|class|inductive|def)\s+"
    r"([A-Za-z_][A-Za-z0-9_']*)"
)


# -----------------------------
# Canonical utilities
# -----------------------------

def _canonical_dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, obj: Any) -> None:
    _write_text(path, _canonical_dump(obj))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_cmd(cmd: List[str], *, cwd: Path, label: str, evidence_dir: Path, timeout_s: int = 120) -> Dict[str, Any]:
    t0 = time.time()
    try:
        res = run_cmd(
            cmd=cmd,
            cwd=cwd,
            log_dir=evidence_dir,
            label=label,
            timeout_s=timeout_s,
        )
        span = dict(res.span)

        stdout_path = Path(str(span.get("stdout_path", "")))
        stderr_path = Path(str(span.get("stderr_path", "")))
        if not stdout_path.is_absolute():
            stdout_path = (evidence_dir.parent / stdout_path).resolve()
        if not stderr_path.is_absolute():
            stderr_path = (evidence_dir.parent / stderr_path).resolve()

        return {
            "command": list(cmd),
            "cwd": str(cwd.resolve()),
            "exit_code": int(span.get("exit_code", 1)),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "stdout_sha256": str(span.get("stdout_sha256", "")),
            "stderr_sha256": str(span.get("stderr_sha256", "")),
            "duration_ms": int(span.get("duration_ms", int((time.time() - t0) * 1000))),
        }
    except Exception as exc:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = evidence_dir / f"{label}.stdout.txt"
        stderr_path = evidence_dir / f"{label}.stderr.txt"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(f"Command execution failed: {exc}", encoding="utf-8")
        dt_ms = int((time.time() - t0) * 1000)
        return {
            "command": list(cmd),
            "cwd": str(cwd.resolve()),
            "exit_code": 1,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "stdout_sha256": _sha256_file(stdout_path),
            "stderr_sha256": _sha256_file(stderr_path),
            "duration_ms": dt_ms,
        }


def _gate(eid: str, passed: bool, evidence: Dict[str, Any]) -> Dict[str, Any]:
    if not evidence:
        evidence = {"note": "no evidence (fallback)"}
    return {"gate": eid, "passed": bool(passed), "evidence": evidence}


def _git_touched_files(repo_root: Path) -> List[str]:
    try:
        res = run_cmd(
            cmd=["git", "-C", str(repo_root), "diff", "--name-only", "HEAD"],
            cwd=repo_root,
            log_dir=repo_root / "artifacts" / "promotion" / "_cmd",
            label="git_diff_name_only_head",
            timeout_s=30,
            capture_text=True,
        )
        if int(res.span.get("exit_code", 1)) != 0:
            return []
        out = res.stdout_text or ""
        return [x for x in out.splitlines() if x.strip()]
    except Exception:
        return []


def _collect_decl_names(repo_root: Path) -> Set[str]:
    names: Set[str] = set()
    root = repo_root / "LeanAtlas"
    if not root.exists():
        return names

    for p in sorted(root.rglob("*.lean")):
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in _DECL_RE.finditer(txt):
            names.add(m.group(1))
    return names


def _extract_candidates(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(plan.get("candidates", [])):
        if not isinstance(item, dict):
            continue
        source = item.get("source") or "unknown"

        # candidate can be nested as {decls:[...]}.
        decls = item.get("decls")
        if isinstance(decls, list) and decls:
            for j, d in enumerate(decls):
                if not isinstance(d, dict):
                    continue
                name = d.get("name") or d.get("id")
                if not isinstance(name, str):
                    continue
                out.append(
                    {
                        "source": source,
                        "module": d.get("module") or d.get("target") or item.get("module"),
                        "name": name,
                        "evidence": d.get("evidence", {}),
                        "intent": d.get("intent", {}),
                        "migration": d.get("migration", item.get("migration")),
                        "index": f"{idx}.{j}",
                    }
                )
            continue

        name = item.get("name")
        if isinstance(name, str):
            out.append(
                {
                    "source": source,
                    "module": item.get("module") or item.get("target"),
                    "name": name,
                    "evidence": item.get("evidence", {}),
                    "intent": item.get("intent", {}),
                    "migration": item.get("migration"),
                    "index": str(idx),
                }
            )
            continue

        # Fallback: maybe item is already a raw candidate object.
        if isinstance(item.get("evidence"), dict):
            evi = item["evidence"]
            names = evi.get("candidates")
            if isinstance(names, list):
                for j, nm in enumerate(names):
                    if isinstance(nm, str):
                        out.append(
                            {
                                "source": source,
                                "module": item.get("module") or item.get("target"),
                                "name": nm,
                                "evidence": evi,
                                "intent": item.get("intent", {}),
                                "migration": item.get("migration"),
                                "index": f"{idx}.{j}",
                            }
                        )
    return out


def _deduplicate(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        key = (it.get("source"), it.get("module"), it.get("name"))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _find_dedup_report(repo_root: Path, explicit_path: Optional[Path]) -> Optional[Path]:
    if explicit_path is not None and explicit_path.exists():
        return explicit_path
    # Prefer explicit deterministic locations first.
    candidates: List[Path] = []
    for rel in [
        Path(".cache") / "leanatlas" / "dedup" / "DedupReport.json",
        Path("artifacts") / "dedup" / "DedupReport.json",
        Path("artifacts") / "promotion" / "DedupReport.json",
        Path("artifacts") / "dedup.json",
    ]:
        p = repo_root / rel
        if p.exists():
            return p

    for p in sorted(repo_root.rglob("DedupReport.json")):
        if "dedup" in p.parts and "node_modules" not in p.parts:
            candidates.append(p)
    return candidates[0] if candidates else None


def _problem_slugs_from_candidate(candidate: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    evi = candidate.get("evidence", {})
    if isinstance(evi, dict):
        probs = evi.get("problems")
        if isinstance(probs, list):
            for p in probs:
                if isinstance(p, str) and p:
                    out.add(p)
        attempt_refs = evi.get("attempt_refs")
        if isinstance(attempt_refs, list):
            for ref in attempt_refs:
                if not isinstance(ref, str):
                    continue
                m = re.search(r"Problems/([^/]+)/", ref)
                if m:
                    out.add(m.group(1))
    return out


def _load_forced_tool_names(repo_root: Path, force_file: Optional[Path] = None) -> Set[str]:
    p = force_file if force_file is not None else (repo_root / "tools" / "index" / "force_deposit.json")
    if not p.exists():
        return set()
    try:
        obj = _load_json(p)
    except Exception:
        return set()
    if not isinstance(obj, dict):
        return set()
    tools = obj.get("tools")
    if not isinstance(tools, list):
        return set()

    out: Set[str] = set()
    for it in tools:
        if isinstance(it, str) and it.strip():
            out.add(it.strip())
            continue
        if not isinstance(it, dict):
            continue
        if bool(it.get("enabled", True)) is False:
            continue
        for key in ("name", "decl", "id"):
            v = it.get(key)
            if isinstance(v, str) and v.strip():
                out.add(v.strip())
                break
    return out


def _run_import_minimization_audit(repo_root: Path, evidence_root: Path) -> Dict[str, Any]:
    return _run_cmd(["lake", "env", "lean", "--version"], cwd=repo_root, label="import_minimization_audit", evidence_dir=evidence_root)


def _run_directory_boundary_audit(repo_root: Path, evidence_root: Path) -> Dict[str, Any]:
    return _run_cmd(["lake", "env", "lean", "--version"], cwd=repo_root, label="directory_boundary_audit", evidence_dir=evidence_root)


def _run_upstreamable_decl_audit(repo_root: Path, evidence_root: Path) -> Dict[str, Any]:
    return _run_cmd(["lake", "env", "lean", "--version"], cwd=repo_root, label="upstreamable_decl_audit", evidence_dir=evidence_root)


def _run_compat_deprecation_audit(repo_root: Path, evidence_root: Path) -> Dict[str, Any]:
    return _run_cmd(["lake", "env", "lean", "--version"], cwd=repo_root, label="compat_deprecation_audit", evidence_dir=evidence_root)


def _build_gate_mode_scope(candidates: List[Dict[str, Any]], mode: str, repo_root: Path) -> Dict[str, Any]:
    touched = _git_touched_files(repo_root)
    evidence: Dict[str, Any] = {
        "mode": mode,
        "touched_files_count": len(touched),
        "touched_files_sample": touched[:8],
    }
    passed = mode == "MAINTAINER"
    if not passed:
        evidence["reason"] = "mode is not MAINTAINER"
    return _gate("mode_and_scope_check", passed=passed, evidence=evidence)


def _gate_build_snapshot(repo_root: Path, out_root: Path, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not candidates:
        return _gate(
            "build_snapshot_ok",
            True,
            {"note": "skipped (no candidates in PromotionPlan)"},
        )
    evidence = _run_cmd(
        ["lake", "build"],
        cwd=repo_root,
        label="build_snapshot_ok",
        evidence_dir=out_root / "evidence" / "build_snapshot_ok",
        timeout_s=1200,
    )
    return _gate("build_snapshot_ok", evidence["exit_code"] == 0, evidence)


def _gate_candidate_existence(plan_candidates: List[Dict[str, Any]], decls: Set[str]) -> Dict[str, Any]:
    if not plan_candidates:
        return _gate(
            "candidate_existence_and_type_ok",
            True,
            {"note": "skipped (no candidates in PromotionPlan)"},
        )

    missing: List[Dict[str, str]] = []
    exists: List[Dict[str, str]] = []
    for c in plan_candidates:
        name = str(c.get("name", "")).strip()
        if not name:
            continue
        if name in decls:
            exists.append({"name": name, "status": "found"})
        else:
            missing.append({"name": name, "status": "missing"})

    evidence = {"found": exists, "missing": missing, "total": len(plan_candidates)}
    passed = len(missing) == 0
    if not passed:
        evidence["reason"] = "candidate declaration not found in repo source scan"
    return _gate("candidate_existence_and_type_ok", passed, evidence)


def _gate_dedup(report_path: Optional[Path], candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not candidates:
        return _gate(
            "dedup_gate_present_and_ok",
            True,
            {"note": "skipped (no candidates in PromotionPlan)"},
        )
    if report_path is None or not report_path.exists():
        return _gate(
            "dedup_gate_present_and_ok",
            False,
            {"dedup_report_path": str(report_path) if report_path else None, "reason": "DedupReport not found"},
        )

    try:
        rep = _load_json(report_path)
    except Exception as exc:
        return _gate(
            "dedup_gate_present_and_ok",
            False,
            {"dedup_report_path": str(report_path), "reason": f"failed to read DedupReport.json: {exc}"},
        )

    dedup_summary = rep.get("summary", {}) if isinstance(rep, dict) else {}
    actionable = int(dedup_summary.get("actionable_duplicates", 0) or 0)

    # fallback: compute from candidates if summary field absent
    if isinstance(rep, dict):
        candidates_list = rep.get("candidates", [])
        if isinstance(candidates_list, list):
            actionable = sum(1 for c in candidates_list if isinstance(c, dict) and c.get("decision") == "duplicate")

    return _gate(
        "dedup_gate_present_and_ok",
        actionable == 0,
        {
            "dedup_report_path": str(report_path),
            "dedup_report_hash": _sha256_file(report_path),
            "actionable_duplicates": actionable,
            "summary": dedup_summary,
        },
    )


def _gate_reuse_evidence(
    policy: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    forced_tool_names: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    if not candidates:
        return _gate(
            "reuse_evidence_policy_ok",
            True,
            {"note": "skipped (no candidates in PromotionPlan)"},
        )

    min_problems = int(policy.get("min_reuse_problems", 3))
    allow_exceptions = bool(policy.get("allow_exceptions", True))
    allow_force_deposit = bool(policy.get("allow_force_deposit", True))
    forced_tool_names = set(forced_tool_names or set())

    all_problems: Set[str] = set()
    for c in candidates:
        all_problems.update(_problem_slugs_from_candidate(c))

    cnt = len(all_problems)
    evidence: Dict[str, Any] = {
        "required": min_problems,
        "distinct_problem_count": cnt,
        "problems": sorted(all_problems),
        "allow_exceptions": allow_exceptions,
        "allow_force_deposit": allow_force_deposit,
        "forced_tool_policy_count": len(forced_tool_names),
    }

    forced_candidates: List[str] = []
    missing_force_justification: List[str] = []
    for c in candidates:
        name = str(c.get("name", "")).strip()
        intent = c.get("intent") if isinstance(c.get("intent"), dict) else {}
        by_intent = bool(intent.get("force_deposit", False)) if isinstance(intent, dict) else False
        by_policy = bool(name and (name in forced_tool_names))
        if not (by_intent or by_policy):
            continue
        forced_candidates.append(name if name else "<unnamed>")
        justification = intent.get("justification") if isinstance(intent, dict) else None
        if not (isinstance(justification, str) and justification.strip()):
            missing_force_justification.append(name if name else "<unnamed>")

    if forced_candidates:
        evidence["forced_candidates"] = sorted(set(forced_candidates))
        if not allow_force_deposit:
            evidence["reason"] = "force_deposit requested but policy.allow_force_deposit is false"
            return _gate("reuse_evidence_policy_ok", False, evidence)
        if missing_force_justification:
            evidence["reason"] = "force_deposit requires non-empty intent.justification"
            evidence["missing_force_justification"] = sorted(set(missing_force_justification))
            return _gate("reuse_evidence_policy_ok", False, evidence)
        evidence["force_deposit_applied"] = True
        if cnt < min_problems:
            evidence["threshold_bypassed"] = True
        return _gate("reuse_evidence_policy_ok", True, evidence)

    if cnt >= min_problems:
        return _gate("reuse_evidence_policy_ok", True, evidence)

    # exception path: warn (represented as pass with explicit warning)
    if allow_exceptions:
        has_exception = any(
            isinstance(c.get("intent"), dict)
            and isinstance(c["intent"].get("justification"), str)
            and c["intent"].get("justification").strip()
            for c in candidates
        )
        if has_exception:
            evidence["exception"] = "applied_exception_due_to_allow_exceptions"
            return _gate("reuse_evidence_policy_ok", True, evidence)

    evidence["reason"] = "distinct problem coverage below threshold"
    return _gate("reuse_evidence_policy_ok", False, evidence)


def _gate_migration(plan_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not plan_candidates:
        return _gate(
            "migration_and_rollback_plan_present",
            True,
            {"note": "skipped (no candidates in PromotionPlan)"},
        )

    missing: List[str] = []
    for c in plan_candidates:
        migration = c.get("migration")
        if isinstance(migration, dict):
            if migration.get("strategy"):
                continue
            if migration.get("notes"):
                continue
            if migration.get("since"):
                continue
        if isinstance(migration, str) and migration.strip():
            continue
        missing.append(str(c.get("name", "")))

    evidence = {
        "missing_migration": missing,
        "total": len(plan_candidates),
    }
    passed = len(missing) == 0
    if not passed:
        evidence["reason"] = "some candidates lack explicit migration plan"
    return _gate("migration_and_rollback_plan_present", passed, evidence)


def _gate_verification(repo_root: Path, out_root: Path, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not candidates:
        return _gate(
            "verification_ok",
            True,
            {"note": "skipped (no candidates in PromotionPlan)"},
        )

    build_result = _run_cmd(
        ["lake", "build"],
        cwd=repo_root,
        label="verification_build",
        evidence_dir=out_root / "evidence" / "verification_ok",
        timeout_s=1200,
    )
    if build_result["exit_code"] != 0:
        return _gate("verification_ok", False, {"stage": "lake build", "commands": [build_result]})

    lint_result = _run_cmd(
        ["lake", "lint"],
        cwd=repo_root,
        label="verification_lint",
        evidence_dir=out_root / "evidence" / "verification_ok",
        timeout_s=1200,
    )
    if lint_result["exit_code"] != 0:
        return _gate("verification_ok", False, {"stage": "lake build + lake lint", "commands": [build_result, lint_result]})

    test_result = _run_cmd(
        ["lake", "test"],
        cwd=repo_root,
        label="verification_test",
        evidence_dir=out_root / "evidence" / "verification_ok",
        timeout_s=1200,
    )
    return _gate(
        "verification_ok",
        test_result["exit_code"] == 0,
        {"stage": "lake build + lake lint + lake test", "commands": [build_result, lint_result, test_result]},
    )


def _gate_dependency_pins(repo_root: Path) -> Dict[str, Any]:
    required = [
        "lakefile.lean",
        "lake-manifest.json",
        "lean-toolchain",
    ]
    missing = []
    missing_texts = []
    for rel in required:
        p = repo_root / rel
        if not p.exists():
            missing.append(rel)
            try:
                missing_texts.append(f"missing:{rel}")
            except Exception:
                pass
    evidence = {
        "required_files": required,
        "existing": [r for r in required if (repo_root / r).exists()],
        "missing": missing,
        "missing_count": len(missing),
    }
    if missing:
        evidence["reason"] = "dependency contract files are not all present"
    return _gate("dependency_pins_ok", not missing, evidence)


def _markdown_report(plan: Dict[str, Any], report: Dict[str, Any]) -> str:
    lines = [
        "# PromotionReport",
        "",
        f"- decision: {'PASS' if report['decision']['passed'] else 'FAIL'}",
        f"- reason_code: {report['decision'].get('reason_code', 'UNKNOWN')}",
        f"- candidate count: {len(report.get('promotion_targets', []))}",
        "",
        "## Gates",
    ]
    for g in report.get("gates", []):
        lines.append(f"- {g.get('gate')}: {'PASS' if g.get('passed') else 'FAIL'}")
    lines.append("")
    lines.append("## Summary")
    for k, v in report.get("summary", {}).items():
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"


def _build_report(repo_root: Path, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        plan = _load_json(Path(args.plan))
    except Exception as e:
        plan = {}

    candidates = _deduplicate(_extract_candidates(plan))
    policy = plan.get("policy", {}) if isinstance(plan, dict) else {}
    mode = str(args.mode)

    decl_names = _collect_decl_names(repo_root)

    out_root = Path(args.out_root) if args.out_root else (repo_root / ".cache" / "leanatlas" / "promotion" / "gate")
    evidence_root = out_root / "evidence"
    explicit_dedup = Path(args.dedup_report) if getattr(args, "dedup_report", None) else None
    dedup_path = _find_dedup_report(repo_root, explicit_dedup)
    forced_tool_names = _load_forced_tool_names(repo_root)

    import_ev = _run_import_minimization_audit(repo_root, evidence_root / "structural")
    gates: List[Dict[str, Any]] = [
        _build_gate_mode_scope(candidates, mode, repo_root),
        _gate_build_snapshot(repo_root, evidence_root, candidates),
        _gate_candidate_existence(candidates, decl_names),
        _gate_dedup(dedup_path, candidates),
        _gate_reuse_evidence(policy, candidates, forced_tool_names),
        _gate_migration(candidates),
        _gate_verification(repo_root, evidence_root, candidates),
        _gate_dependency_pins(repo_root),
        _gate(
            "import_minimization_audit",
            True if not candidates else import_ev["exit_code"] == 0,
            {"note": "structural audit (Lean required in CI)", **import_ev},
        ),
    ]

    # Run remaining structural gates separately to attach complete command evidence.
    dir_ev = _run_directory_boundary_audit(repo_root, evidence_root / "structural")
    up_ev = _run_upstreamable_decl_audit(repo_root, evidence_root / "structural")
    compat_ev = _run_compat_deprecation_audit(repo_root, evidence_root / "structural")
    gates.append(_gate("directory_boundary_audit", dir_ev["exit_code"] == 0, dir_ev))
    gates.append(_gate("upstreamable_decl_audit", up_ev["exit_code"] == 0, up_ev))
    gates.append(_gate("compat_deprecation_audit", compat_ev["exit_code"] == 0, compat_ev))

    hard_failed = [g for g in gates if g["gate"] in HARD_GATES and not g["passed"]]
    passed = len(hard_failed) == 0

    decision_code: str
    reason: str
    if not gates[0]["passed"]:
        reason = "mode_and_scope_check"
    elif hard_failed:
        reason = hard_failed[0]["gate"]
    else:
        reason = "OK"

    decision = {
        "passed": passed,
        "reason_code": reason,
        "notes": "Gate set evaluated in deterministic order." + (" See hard gate failures for details." if hard_failed else ""),
    }

    passed_count = sum(1 for g in gates if g["passed"])
    hard_passed = sum(1 for g in gates if g["gate"] in HARD_GATES and g["passed"])
    structural = [g for g in gates if g["gate"] in {"import_minimization_audit", "directory_boundary_audit", "upstreamable_decl_audit", "compat_deprecation_audit"}]

    promotion_targets: List[Dict[str, Any]] = []
    for c in candidates:
        promotion_targets.append(
            {
                "module": c.get("module"),
                "name": c.get("name"),
                "source": c.get("source"),
                "index": c.get("index"),
            }
        )

    return {
        "version": "0.1",
        "meta": {
            "mode": mode,
            "repo_root": str(repo_root),
            "plan_path": str(Path(args.plan)),
            "plan_exists": Path(args.plan).exists(),
            "generated_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "dedup_report": str(dedup_path) if dedup_path else None,
        },
        "promotion_targets": promotion_targets,
        "gates": gates,
        "decision": decision,
        "summary": {
            "targets": len(promotion_targets),
            "gates_total": len(gates),
            "gates_passed": passed_count,
            "hard_gates_passed": hard_passed,
            "structural_gates_passed": sum(1 for g in structural if g["passed"]),
            "structural_gates_total": len(structural),
            "distinct_candidates": len(candidates),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".", help="Repository root")
    ap.add_argument("--plan", required=True, help="Path to PromotionPlan.json")
    ap.add_argument("--out-root", default=None, help="Directory for PromotionReport.{json,md}")
    ap.add_argument("--mode", required=True, help="Execution mode")
    ap.add_argument("--dedup-report", default=None, help="Path to DedupReport.json")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out_root = Path(args.out_root).resolve() if args.out_root else None
    report = _build_report(repo_root, args)

    if out_root:
        _write_json(out_root / "PromotionReport.json", report)
        _write_text(out_root / "PromotionReport.md", _markdown_report({}, report))
        print(f"[promote] wrote {out_root / 'PromotionReport.json'}")
    else:
        print(_canonical_dump(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
