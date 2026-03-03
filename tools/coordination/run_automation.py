#!/usr/bin/env python3
"""Run a registered automation locally (deterministic steps + optional advisor + verify).

Why this exists
--------------
Users should not have to reverse-engineer `automations/registry.json`.
This CLI is the local harness entrypoint to:

- list automations
- dry-run (print steps)
- run deterministic steps with evidence capture (stream logs)
- optionally run the automation's `advisor` execution path
- optionally run the automation's `verify` steps

Codex App mapping
-----------------
The scheduler/trigger lives in Codex App Automations UI.
This script does not replace scheduling. It provides an auditable local runner
for deterministic pre-steps and advisor handoff/verification semantics.

Contracts
---------
- docs/contracts/AUTOMATION_CONTRACT.md
- docs/contracts/THIRD_PARTY_DEPENDENCY_CONTRACT.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow `from tools.*` imports when executing as a script.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.workflow.env_stamp import get_environment_stamp
from tools.workflow.run_cmd import run_cmd


REGISTRY = ROOT / "automations" / "registry.json"
ARTIFACTS = ROOT / "artifacts" / "automation" / "runs"


def _repo_python() -> str:
    """Resolve a repository-local Python executable for deterministic automation runs."""
    venv_python = ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _normalize_cmd(cmd: List[str]) -> List[str]:
    """Preserve registry commands, but force plain python invocations to repo python."""
    if not cmd or cmd[0] not in {"python", "python3"}:
        return cmd
    return [_repo_python(), *cmd[1:]]


@dataclass
class Automation:
    id: str
    status: str
    mode: str
    purpose: str
    deterministic_steps: List[Dict[str, Any]]
    advisor: Dict[str, Any]
    verify_steps: List[Dict[str, Any]]


def _load_registry(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_automation(obj: Dict[str, Any]) -> Automation:
    det = (obj.get("deterministic") or {}).get("steps") or []
    ver = (obj.get("verify") or {}).get("steps") or []
    advisor = obj.get("advisor") if isinstance(obj.get("advisor"), dict) else {}
    return Automation(
        id=str(obj.get("id")),
        status=str(obj.get("status")),
        mode=str(obj.get("mode")),
        purpose=str(obj.get("purpose")),
        deterministic_steps=list(det),
        advisor=dict(advisor),
        verify_steps=list(ver),
    )


def _index_automations(reg: Dict[str, Any]) -> Dict[str, Automation]:
    autos = reg.get("automations") or []
    out: Dict[str, Automation] = {}
    for a in autos:
        if not isinstance(a, dict):
            continue
        aa = _parse_automation(a)
        out[aa.id] = aa
    return out


def _print_list(index: Dict[str, Automation]) -> None:
    rows = sorted(index.values(), key=lambda x: x.id)
    for a in rows:
        print(f"{a.id}\t[{a.status}]\tmode={a.mode}\t{a.purpose}")


def _run_steps(
    *,
    steps: List[Dict[str, Any]],
    cwd: Path,
    logs_dir: Path,
    prefix: str,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for i, step in enumerate(steps):
        name = str(step.get("name") or f"step{i}")
        cmd = step.get("cmd")
        if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
            raise ValueError(f"invalid cmd for step {name}: {cmd}")
        cmd_to_run = _normalize_cmd(list(cmd))
        label = f"{prefix}{i:02d}_{name}"
        res = run_cmd(
            cmd=cmd_to_run,
            cwd=cwd,
            log_dir=logs_dir,
            label=label,
            timeout_s=int(step.get("timeout_s") or 600),
            capture_text=False,
        )
        rc = int(res.span.get("exit_code", 1))
        ok = (rc == 0)
        results.append(
            {
                "name": name,
                "cmd": cmd_to_run,
                "ok": ok,
                "exit_code": rc,
                "evidence": res.span,
            }
        )
        if not ok:
            break
    return results


def _deep_get(obj: Dict[str, Any], dotted: str) -> Any:
    cur: Any = obj
    for key in dotted.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _probe_findings(repo_root: Path, probe: Dict[str, Any]) -> Tuple[Optional[bool], str]:
    kind = str(probe.get("kind") or "").strip()
    path = str(probe.get("path") or "").strip()
    field = str(probe.get("field") or "").strip()
    threshold = probe.get("threshold", 0)

    if not kind or not path:
        return (None, "missing advisor.probe.kind/path")

    p = repo_root / path
    if not p.exists():
        return (None, f"probe file missing: {path}")

    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception as ex:
        return (None, f"probe parse error: {path}: {ex}")

    value: Any = obj if not field else _deep_get(obj, field)
    if kind == "json_array_nonempty":
        if not isinstance(value, list):
            return (None, f"probe value is not list at field={field!r}")
        return (len(value) > 0, f"len({field})={len(value)}")

    if kind == "json_field_truthy":
        return (bool(value), f"truthy({field})={bool(value)}")

    if kind == "json_field_gt":
        try:
            v = float(value)
            t = float(threshold)
        except Exception:
            return (None, f"probe value/threshold not numeric at field={field!r}")
        return (v > t, f"{field}={v} > {t}")

    return (None, f"unknown advisor.probe.kind: {kind}")


def _write_advisor_handoff(
    *,
    run_dir: Path,
    automation: Automation,
    reason: str,
    should_run: bool,
) -> Path:
    out = run_dir / "advisor" / "handoff.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    outputs = automation.advisor.get("outputs")
    payload = {
        "schema": "leanatlas.automation_advisor_handoff",
        "schema_version": "0.1.0",
        "automation_id": automation.id,
        "purpose": automation.purpose,
        "mode": automation.mode,
        "skill": automation.advisor.get("skill"),
        "outputs": list(outputs) if isinstance(outputs, list) else [],
        "when": automation.advisor.get("when"),
        "should_run": should_run,
        "reason": reason,
        "note": (
            "Use this payload in Codex App automation prompt execution. "
            "Scheduler is external; this file is the local evidence handoff."
        ),
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def _run_advisor(
    *,
    automation: Automation,
    repo_root: Path,
    run_dir: Path,
    logs_dir: Path,
    det_ok: bool,
    advisor_mode: str,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "enabled": bool(automation.advisor.get("enabled")),
        "requested_mode": advisor_mode,
        "decision": "SKIPPED",
        "reason": "advisor mode is off",
        "should_run": False,
        "hints": [],
    }

    if advisor_mode == "off":
        handoff = _write_advisor_handoff(
            run_dir=run_dir,
            automation=automation,
            reason=result["reason"],
            should_run=False,
        )
        result["handoff"] = handoff.relative_to(run_dir).as_posix()
        return result

    if not bool(automation.advisor.get("enabled")):
        result["reason"] = "advisor.enabled is false"
        handoff = _write_advisor_handoff(
            run_dir=run_dir,
            automation=automation,
            reason=result["reason"],
            should_run=False,
        )
        result["handoff"] = handoff.relative_to(run_dir).as_posix()
        return result

    should_run = (advisor_mode == "force")
    reason = "advisor forced by --advisor-mode=force" if should_run else ""

    if not should_run:
        when = str(automation.advisor.get("when") or "findings")
        if not det_ok:
            should_run = True
            reason = "deterministic step failed"
        elif when != "findings":
            should_run = True
            reason = f"advisor.when={when}"
        else:
            probe = automation.advisor.get("probe")
            if isinstance(probe, dict):
                probe_hit, probe_reason = _probe_findings(repo_root, probe)
                if probe_hit is None:
                    result["hints"].append(f"findings probe unavailable: {probe_reason}")
                    should_run = False
                    reason = "no findings probe signal"
                else:
                    should_run = bool(probe_hit)
                    reason = f"findings probe: {probe_reason}"
            else:
                should_run = False
                reason = "advisor.when=findings but no advisor.probe configured"
                result["hints"].append("configure advisor.probe for auto mode")

    handoff = _write_advisor_handoff(
        run_dir=run_dir,
        automation=automation,
        reason=reason,
        should_run=should_run,
    )
    result["handoff"] = handoff.relative_to(run_dir).as_posix()
    result["should_run"] = should_run
    result["reason"] = reason

    if not should_run:
        result["decision"] = "SKIPPED"
        return result

    exec_cmd = automation.advisor.get("exec_cmd")
    if not isinstance(exec_cmd, list) or not exec_cmd or not all(isinstance(x, str) for x in exec_cmd):
        # No local executor configured: we still emit the handoff to Codex App.
        result["decision"] = "HANDOFF_ONLY"
        result["reason"] = f"{reason}; no advisor.exec_cmd configured"
        return result

    res = run_cmd(
        cmd=exec_cmd,
        cwd=repo_root,
        log_dir=logs_dir,
        label="advisor_00_exec",
        timeout_s=900,
        capture_text=False,
    )
    rc = int(res.span.get("exit_code", 1))
    result["decision"] = "EXECUTED" if rc == 0 else "FAILED"
    result["exit_code"] = rc
    result["evidence"] = res.span
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="List all registered automations")
    ap.add_argument("--id", dest="automation_id", default=None, help="Run a single automation by id")
    ap.add_argument("--verify", action="store_true", help="Also run the automation's verify steps")
    ap.add_argument(
        "--advisor-mode",
        choices=["off", "auto", "force"],
        default="off",
        help=(
            "Advisor execution mode. off: emit handoff only; "
            "auto: run when findings policy is met; force: run regardless of findings."
        ),
    )
    ap.add_argument("--dry-run", action="store_true", help="Print steps only; do not execute")
    ap.add_argument("--allow-planned", action="store_true", help="Allow running automations with status=planned")
    args = ap.parse_args()

    reg = _load_registry(REGISTRY)
    index = _index_automations(reg)

    if args.list:
        _print_list(index)
        return 0

    if not args.automation_id:
        ap.error("--id is required unless --list is used")

    a = index.get(args.automation_id)
    if a is None:
        raise SystemExit(f"unknown automation id: {args.automation_id}")

    if a.status != "active" and not args.allow_planned:
        raise SystemExit(f"automation {a.id} is not active (status={a.status}). Use --allow-planned to force.")

    if args.dry_run:
        print(f"automation: {a.id} [{a.status}] mode={a.mode}\n{a.purpose}\n")
        print("deterministic steps:")
        for s in a.deterministic_steps:
            print(f"  - {s.get('name')}: {s.get('cmd')}")
        print("\nadvisor:")
        print(f"  - enabled={bool(a.advisor.get('enabled'))}")
        print(f"  - when={a.advisor.get('when')}")
        if a.advisor.get("probe"):
            print(f"  - probe={a.advisor.get('probe')}")
        print(f"  - mode(requested)={args.advisor_mode}")
        if args.verify:
            print("\nverify steps:")
            for s in a.verify_steps:
                print(f"  - {s.get('name')}: {s.get('cmd')}")
        return 0

    run_id = f"{a.id}_{int(time.time())}"
    run_dir = ARTIFACTS / a.id / run_id
    logs_dir = run_dir / "Cmd"
    run_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {
        "schema": "leanatlas.automation_run_manifest",
        "schema_version": "0.2.0",
        "automation_id": a.id,
        "run_id": run_id,
        "started_epoch": int(time.time()),
        "env_stamp": get_environment_stamp(ROOT),
        "deterministic": [],
        "advisor": {},
        "verify": [],
        "status": "RUNNING",
    }

    ok = True

    det_res = _run_steps(steps=a.deterministic_steps, cwd=ROOT, logs_dir=logs_dir, prefix="det_")
    manifest["deterministic"] = det_res
    ok = ok and all(bool(x.get("ok")) for x in det_res)

    advisor_res = _run_advisor(
        automation=a,
        repo_root=ROOT,
        run_dir=run_dir,
        logs_dir=logs_dir,
        det_ok=ok,
        advisor_mode=args.advisor_mode,
    )
    manifest["advisor"] = advisor_res
    if advisor_res.get("decision") == "FAILED":
        ok = False

    if ok and args.verify:
        ver_res = _run_steps(steps=a.verify_steps, cwd=ROOT, logs_dir=logs_dir, prefix="ver_")
        manifest["verify"] = ver_res
        ok = ok and all(bool(x.get("ok")) for x in ver_res)

    manifest["status"] = "OK" if ok else "FAIL"
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    latest = ROOT / "artifacts" / "automation" / a.id / "latest_run_manifest.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"[automation] status={manifest['status']}  run_dir={run_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
