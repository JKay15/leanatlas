#!/usr/bin/env python3
"""Contract check: blocking wave gate rejects schema/policy violations."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "contract" / "fixtures" / "loop" / "positive" / "waveexecutionlooprun_min.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.wave_gate import validate_wave_execution_report
from tools.loop.dirty_tree_gate import collect_dirty_tree_snapshot, validate_dirty_tree_snapshot
import tools.loop.dirty_tree_gate as dirty_tree_gate_mod


def _fail(msg: str) -> int:
    print(f"[loop-wave-blocking-gate][FAIL] {msg}", file=sys.stderr)
    return 2


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _max_consecutive(iterations: list[dict]) -> int:
    last = None
    run = 0
    best = 0
    for rec in iterations:
        fp = str(((rec.get("ai_review") or {}).get("finding_fingerprint")) or "")
        if fp and fp == last:
            run += 1
        else:
            run = 1 if fp else 0
            last = fp if fp else None
        best = max(best, run)
    return max(0, best)


def _tail_consecutive(iterations: list[dict]) -> int:
    last = None
    run = 0
    for rec in iterations:
        fp = str(((rec.get("ai_review") or {}).get("finding_fingerprint")) or "")
        if fp and fp == last:
            run += 1
        else:
            run = 1 if fp else 0
            last = fp if fp else None
    return max(0, run)


def _refresh_replay_fields(report: dict) -> None:
    iterations = report.get("iterations") or []
    budgets = report.get("budgets") or {}
    execution = report.get("execution") or {}
    review_hist = report.get("review_history_consistency") or {}
    transitions = execution.get("transitions") or []
    last_fp = None
    if iterations:
        last_fp = str(((iterations[-1].get("ai_review") or {}).get("finding_fingerprint")) or "") or None
    state = {
        "version": "1",
        "run_key": str(report.get("run_key") or ""),
        "wave_id": str(report.get("wave_id") or ""),
        "current_state": str(execution.get("current_state") or ""),
        "used_ai_review_rounds": int(budgets.get("used_ai_review_rounds", 0)),
        "used_wall_clock_minutes": int(budgets.get("used_wall_clock_minutes", 0)),
        "max_ai_review_rounds": int(budgets.get("max_ai_review_rounds", 0)),
        "max_same_fingerprint_rounds": int(budgets.get("max_same_fingerprint_rounds", 0)),
        "max_wave_wall_clock_minutes": int(budgets.get("max_wave_wall_clock_minutes", 0)),
        "last_finding_fingerprint": last_fp,
        "consecutive_same_fingerprint": _tail_consecutive(iterations),
    }
    payload = {
        "transitions": transitions,
        "iterations": iterations,
        "review_history_consistency": review_hist,
        "state": state,
    }
    replay_digest = hashlib.sha256(
        (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()
    report.setdefault("derived_metrics", {})
    report["derived_metrics"]["max_consecutive_same_fingerprint"] = max(1, _max_consecutive(iterations))
    report["derived_metrics"]["replay_digest"] = replay_digest


def main() -> int:
    if not FIXTURE.exists():
        return _fail(f"missing fixture: {FIXTURE.relative_to(ROOT)}")

    good = _load_fixture()
    if not isinstance(good.get("dirty_tree"), dict):
        return _fail("positive fixture must include dirty_tree evidence block")
    if "disposition" not in good["dirty_tree"]:
        return _fail("positive fixture dirty_tree must include disposition")
    _refresh_replay_fields(good)
    errs = validate_wave_execution_report(good, repo_root=ROOT)
    if errs:
        return _fail(f"positive fixture must pass blocking gate, got: {errs[0]}")

    bad_trace = copy.deepcopy(good)
    bad_trace["execution"]["transitions"][2], bad_trace["execution"]["transitions"][3] = (
        bad_trace["execution"]["transitions"][3],
        bad_trace["execution"]["transitions"][2],
    )
    _refresh_replay_fields(bad_trace)
    errs = validate_wave_execution_report(bad_trace, repo_root=ROOT)
    if not errs or not any("contiguous" in e for e in errs):
        return _fail("non-contiguous transition chain must fail blocking gate")

    bad_history = copy.deepcopy(good)
    bad_history["review_history_consistency"]["contradiction_count"] = 1
    bad_history["review_history_consistency"]["contradiction_refs"] = ["finding.waveA.round1.001"]
    bad_history["iterations"][1]["history_context_refs"] = ["artifacts/waveA/review_history_until_round1.json"]
    _refresh_replay_fields(bad_history)
    errs = validate_wave_execution_report(bad_history, repo_root=ROOT)
    if not errs or not any("history_context_refs" in e for e in errs):
        return _fail("missing contradiction ref propagation into later history_context_refs must fail")

    bad_terminal = copy.deepcopy(good)
    bad_terminal["execution"]["current_state"] = "TRIAGED"
    _refresh_replay_fields(bad_terminal)
    errs = validate_wave_execution_report(bad_terminal, repo_root=ROOT)
    if not errs or not any(("final_decision" in e) or ("/execution/current_state" in e) for e in errs):
        return _fail("execution.current_state/final_decision mismatch must fail")

    external_history_ok = copy.deepcopy(good)
    external_history_ok["review_history_consistency"]["contradiction_count"] = 1
    external_history_ok["review_history_consistency"]["contradiction_refs"] = ["legacy.finding.001"]
    for rec in external_history_ok.get("iterations", []):
        refs = rec.get("history_context_refs") or []
        if "legacy.finding.001" not in refs:
            refs.append("legacy.finding.001")
        rec["history_context_refs"] = refs
    _refresh_replay_fields(external_history_ok)
    errs = validate_wave_execution_report(external_history_ok, repo_root=ROOT)
    if errs:
        return _fail(f"external history refs should pass when propagated via history_context_refs, got: {errs[0]}")

    external_history_first_round_only = copy.deepcopy(good)
    external_history_first_round_only["review_history_consistency"]["contradiction_count"] = 1
    external_history_first_round_only["review_history_consistency"]["contradiction_refs"] = ["legacy.finding.001"]
    external_history_first_round_only["iterations"][0]["history_context_refs"] = ["legacy.finding.001"]
    external_history_first_round_only["iterations"][1]["history_context_refs"] = [
        "artifacts/waveA/review_history_until_round1.json"
    ]
    _refresh_replay_fields(external_history_first_round_only)
    errs = validate_wave_execution_report(external_history_first_round_only, repo_root=ROOT)
    if not errs or not any("later-round history_context_refs" in e for e in errs):
        return _fail("history refs present only in first round must fail later-round propagation rule")

    bad_reuse_review_evidence = copy.deepcopy(good)
    bad_reuse_review_evidence["iterations"][1]["ai_review"]["prompt_ref"] = bad_reuse_review_evidence["iterations"][0][
        "ai_review"
    ]["prompt_ref"]
    bad_reuse_review_evidence["iterations"][1]["ai_review"]["response_ref"] = bad_reuse_review_evidence["iterations"][0][
        "ai_review"
    ]["response_ref"]
    _refresh_replay_fields(bad_reuse_review_evidence)
    errs = validate_wave_execution_report(bad_reuse_review_evidence, repo_root=ROOT)
    if not errs or not any("review closure" in e for e in errs):
        return _fail("reused prompt/response refs across rounds must fail with review closure error")

    bad_iteration_index = copy.deepcopy(good)
    bad_iteration_index["iterations"][1]["iteration_index"] = 1
    _refresh_replay_fields(bad_iteration_index)
    errs = validate_wave_execution_report(bad_iteration_index, repo_root=ROOT)
    if not errs or not any("iteration_index" in e for e in errs):
        return _fail("non-contiguous review iteration_index must fail blocking gate")

    bad_derived_metric = copy.deepcopy(good)
    bad_derived_metric["derived_metrics"]["max_consecutive_same_fingerprint"] = 2
    errs = validate_wave_execution_report(bad_derived_metric, repo_root=ROOT)
    if not errs or not any(("max_consecutive_same_fingerprint" in e) or ("/final_decision" in e) for e in errs):
        return _fail("tampered derived max_consecutive_same_fingerprint must fail schema or replay consistency gate")

    bad_replay_digest = copy.deepcopy(good)
    bad_replay_digest["derived_metrics"]["replay_digest"] = "f" * 64
    errs = validate_wave_execution_report(bad_replay_digest, repo_root=ROOT)
    if not errs or not any("replay_digest" in e for e in errs):
        return _fail("tampered replay_digest must fail replay consistency gate")

    bad_provider_invocation = copy.deepcopy(good)
    bad_provider_invocation["agent_invocation"]["agent_provider_id"] = "codex_cli"
    bad_provider_invocation["agent_invocation"]["resolved_invocation"] = ["claude", "exec", "review"]
    _refresh_replay_fields(bad_provider_invocation)
    errs = validate_wave_execution_report(bad_provider_invocation, repo_root=ROOT)
    if not errs or not any("resolved_invocation must match agent_provider_id" in e for e in errs):
        return _fail("mismatched agent provider routing must fail blocking gate")

    bad_scope_refs = copy.deepcopy(good)
    bad_scope_refs["agent_invocation"]["instruction_scope_refs"] = ["docs/contracts/LOOP_WAVE_EXECUTION_CONTRACT.md"]
    _refresh_replay_fields(bad_scope_refs)
    errs = validate_wave_execution_report(bad_scope_refs, repo_root=ROOT)
    if not errs or not any("instruction_scope_refs must include AGENTS.md" in e for e in errs):
        return _fail("instruction_scope_refs missing AGENTS.md chain must fail blocking gate")

    bad_budget_reason = copy.deepcopy(good)
    bad_budget_reason["execution"]["current_state"] = "TRIAGED"
    bad_budget_reason["execution"]["transitions"][-1]["to"] = "TRIAGED"
    bad_budget_reason["execution"]["transitions"][-1]["reason_code"] = "REVIEW_BUDGET_EXHAUSTED"
    bad_budget_reason["iterations"][-1]["transition"]["to"] = "TRIAGED"
    bad_budget_reason["iterations"][-1]["transition"]["reason_code"] = "REVIEW_BUDGET_EXHAUSTED"
    bad_budget_reason["final_decision"]["state"] = "TRIAGED"
    bad_budget_reason["final_decision"]["reason_code"] = "REVIEW_BUDGET_EXHAUSTED"
    _refresh_replay_fields(bad_budget_reason)
    errs = validate_wave_execution_report(bad_budget_reason, repo_root=ROOT)
    if not errs or not any(("REVIEW_BUDGET_EXHAUSTED" in e) or ("used_ai_review_rounds" in e) for e in errs):
        return _fail("REVIEW_BUDGET_EXHAUSTED without exhausted retry budget must fail blocking gate")

    bad_stagnation_reason = copy.deepcopy(good)
    bad_stagnation_reason["execution"]["current_state"] = "TRIAGED"
    bad_stagnation_reason["execution"]["transitions"][-1]["to"] = "TRIAGED"
    bad_stagnation_reason["execution"]["transitions"][-1]["reason_code"] = "REVIEW_STAGNATION"
    bad_stagnation_reason["iterations"][-1]["transition"]["to"] = "TRIAGED"
    bad_stagnation_reason["iterations"][-1]["transition"]["reason_code"] = "REVIEW_STAGNATION"
    bad_stagnation_reason["final_decision"]["state"] = "TRIAGED"
    bad_stagnation_reason["final_decision"]["reason_code"] = "REVIEW_STAGNATION"
    bad_stagnation_reason["derived_metrics"]["max_consecutive_same_fingerprint"] = 1
    _refresh_replay_fields(bad_stagnation_reason)
    bad_stagnation_reason["derived_metrics"]["max_consecutive_same_fingerprint"] = 1
    errs = validate_wave_execution_report(bad_stagnation_reason, repo_root=ROOT)
    if not errs or not any(("REVIEW_STAGNATION" in e) or ("max_consecutive_same_fingerprint" in e) for e in errs):
        return _fail("REVIEW_STAGNATION without repeated fingerprint threshold must fail blocking gate")

    bad_dirty_pass = copy.deepcopy(good)
    bad_dirty_pass["dirty_tree"] = {
        "checked": True,
        "in_git_repo": True,
        "is_clean": False,
        "disposition": "DIRTY_PENDING",
        "head_commit": "1111111111111111111111111111111111111111",
        "tracked_entry_count": 1,
        "untracked_entry_count": 0,
        "changed_entry_count": 1,
        "status_porcelain_sample": [" M tools/loop/wave_gate.py"],
    }
    _refresh_replay_fields(bad_dirty_pass)
    errs = validate_wave_execution_report(bad_dirty_pass, repo_root=ROOT)
    if not errs or not any(("dirty tree" in e.lower()) or ("/dirty_tree" in e) for e in errs):
        return _fail("PASSED report with dirty in-git worktree must fail blocking gate")

    timeout_missing_evidence = copy.deepcopy(good)
    timeout_missing_evidence["execution"]["current_state"] = "TRIAGED"
    timeout_missing_evidence["execution"]["transitions"][-1]["to"] = "TRIAGED"
    timeout_missing_evidence["execution"]["transitions"][-1]["reason_code"] = "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED"
    timeout_missing_evidence["iterations"][-1]["transition"]["to"] = "TRIAGED"
    timeout_missing_evidence["iterations"][-1]["transition"]["reason_code"] = "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED"
    timeout_missing_evidence["iterations"][-1]["wall_clock_used_minutes"] = 120
    timeout_missing_evidence["budgets"]["used_wall_clock_minutes"] = 120
    timeout_missing_evidence["final_decision"]["state"] = "TRIAGED"
    timeout_missing_evidence["final_decision"]["reason_code"] = "REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED"
    timeout_missing_evidence.get("evidence", {}).pop("timeout_command_span", None)
    _refresh_replay_fields(timeout_missing_evidence)
    errs = validate_wave_execution_report(timeout_missing_evidence, repo_root=ROOT)
    if not errs or not any("timeout_command_span" in e for e in errs):
        return _fail("REVIEW_WALL_CLOCK_BUDGET_EXHAUSTED without timeout_command_span must fail schema gate")

    timeout_with_evidence = copy.deepcopy(timeout_missing_evidence)
    timeout_with_evidence.setdefault("evidence", {})["timeout_command_span"] = {
        "timed_out": True,
        "exit_code": 124,
        "stdout_path": "artifacts/loop_runtime/by_key/aaa/wave_execution/reviewer_timeout.stdout.txt",
        "stderr_path": "artifacts/loop_runtime/by_key/aaa/wave_execution/reviewer_timeout.stderr.txt",
    }
    _refresh_replay_fields(timeout_with_evidence)
    errs = validate_wave_execution_report(timeout_with_evidence, repo_root=ROOT)
    if errs:
        return _fail(f"timeout evidence payload should satisfy blocking gate, got: {errs[0]}")

    with tempfile.TemporaryDirectory(prefix="dirty_tree_gate_") as td:
        repo = Path(td)
        snap_no_git = collect_dirty_tree_snapshot(repo)
        errs_no_git = validate_dirty_tree_snapshot(snap_no_git, final_state="PASSED")
        if errs_no_git:
            return _fail(f"no-git context should pass DirtyTreeGate baseline, got: {errs_no_git[0]}")
        malformed_no_git = copy.deepcopy(snap_no_git)
        malformed_no_git["is_clean"] = False
        malformed_no_git["changed_entry_count"] = 1
        malformed_no_git["status_porcelain_sample"] = [" M fake.txt"]
        errs_malformed_no_git = validate_dirty_tree_snapshot(malformed_no_git, final_state="PASSED")
        if not errs_malformed_no_git or not any("in_git_repo=false requires" in e for e in errs_malformed_no_git):
            return _fail("malformed no-git snapshot must fail DirtyTreeGate canonical-shape validation")

    with tempfile.TemporaryDirectory(prefix="dirty_tree_gate_git_") as td:
        repo = Path(td)
        # Deterministic local git setup for gate smoke.
        import subprocess

        p = subprocess.run(["git", "init"], cwd=repo, capture_output=True, text=True, check=False)
        if p.returncode != 0:
            return _fail("git init failed in dirty-tree gate smoke")
        (repo / "dirty.txt").write_text("x\n", encoding="utf-8")
        snap_dirty = collect_dirty_tree_snapshot(repo)
        errs_dirty = validate_dirty_tree_snapshot(snap_dirty, final_state="PASSED")
        if not errs_dirty or not any("PASSED run in git repo requires clean worktree" in e for e in errs_dirty):
            return _fail("DirtyTreeGate should fail PASSED in-git dirty snapshot")
        (repo / "subdir").mkdir(parents=True, exist_ok=True)
        snap_from_subdir = collect_dirty_tree_snapshot(repo / "subdir")
        if snap_from_subdir.get("in_git_repo") is not True:
            return _fail("subdir inside git repo must still report in_git_repo=true")
        errs_subdir = validate_dirty_tree_snapshot(snap_from_subdir, final_state="PASSED")
        if not errs_subdir or not any("PASSED run in git repo requires clean worktree" in e for e in errs_subdir):
            return _fail("subdir git snapshot must still enforce PASSED clean-worktree rule")

    # Probe failures for git root detection must fail-closed (not NO_GIT_CONTEXT clean).
    original_run_git = dirty_tree_gate_mod._run_git

    def _fake_git_probe_failure(repo_root: Path, args: list[str], *, label: str) -> dict:
        if args == ["rev-parse", "--show-toplevel"]:
            return {
                "ok": False,
                "exit_code": 128,
                "stdout": "",
                "stderr": "fatal: cannot change to '/broken/path': No such file or directory",
            }
        return original_run_git(repo_root, args, label=label)

    dirty_tree_gate_mod._run_git = _fake_git_probe_failure
    try:
        snap_probe_failed = collect_dirty_tree_snapshot(ROOT)
    finally:
        dirty_tree_gate_mod._run_git = original_run_git

    if snap_probe_failed.get("disposition") == "NO_GIT_CONTEXT":
        return _fail("git probe failure must not be downgraded to NO_GIT_CONTEXT")
    if snap_probe_failed.get("in_git_repo") is not True or snap_probe_failed.get("is_clean") is not False:
        return _fail("git probe failure must fail-closed as in_git_repo=true and is_clean=false")
    errs_probe_failed = validate_dirty_tree_snapshot(snap_probe_failed, final_state="PASSED")
    if not errs_probe_failed or not any("clean worktree" in e for e in errs_probe_failed):
        return _fail("git probe failure snapshot must block PASSED final state")

    print("[loop-wave-blocking-gate] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
