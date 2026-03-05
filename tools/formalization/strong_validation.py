#!/usr/bin/env python3
"""Deterministic strong validation checks for formalization Lean targets."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tools.workflow.run_cmd import run_cmd


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize(text: str) -> str:
    return " ".join(str(text).strip().split())


def short_tail(text: str, lines: int = 30) -> list[str]:
    arr = str(text).splitlines()
    return arr[-lines:] if len(arr) > lines else arr


def _sanitize_temp_paths_for_report(text: str) -> str:
    # Keep reports deterministic by scrubbing randomized tempdir fragments.
    return re.sub(r"leanatlas_axiom_audit_[A-Za-z0-9_.-]+", "<TEMP_AXIOM_AUDIT_DIR>", str(text))


def _short_tail_sanitized(text: str, lines: int = 30) -> list[str]:
    return short_tail(_sanitize_temp_paths_for_report(text), lines=lines)


def default_command_runner(cmd: list[str], cwd: Path, timeout_sec: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="leanatlas_strong_validation_cmd_") as td:
        result = run_cmd(
            cmd=cmd,
            cwd=Path(cwd).resolve(),
            log_dir=Path(td),
            label="strong_validation",
            timeout_s=max(1, int(timeout_sec)),
            capture_text=True,
        )
        span = result.span
        return {
            "ok": int(span.get("exit_code", 1)) == 0,
            "returncode": int(span.get("exit_code", 1)),
            "stdout": result.stdout_text or "",
            "stderr": result.stderr_text or "",
            "cmd": cmd,
            "timeout": bool(span.get("timed_out", False)),
        }


def _resolve_target_file_path(raw_path: str, project_root: Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def _is_within_project_root(path: Path, project_root: Path) -> bool:
    try:
        path.resolve().relative_to(project_root.resolve())
        return True
    except Exception:
        return False


def _sanitize_axiom_cmd_for_report(cmd: Any) -> list[str]:
    arr = [str(x) for x in (cmd if isinstance(cmd, list) else [])]
    if len(arr) >= 4 and arr[:3] == ["lake", "env", "lean"]:
        arr[-1] = "<TEMP_AXIOM_AUDIT_FILE>"
    return arr


def collect_targets(
    ledger: dict[str, Any],
    include_nonformalized: bool,
    *,
    project_root: Path,
) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    out: dict[str, set[str]] = defaultdict(set)
    issues: list[dict[str, Any]] = []
    for b in ledger.get("formalization_bindings", []):
        if not isinstance(b, dict):
            continue
        status = str(b.get("formalization_status", "")).strip().upper()
        if (not include_nonformalized) and status not in {"FORMALIZED", "COMPLETED", "COMPLETE"}:
            continue
        lt = b.get("lean_target") if isinstance(b.get("lean_target"), dict) else {}
        fpath = str(lt.get("file_path", "")).strip()
        decl = str(lt.get("declaration_name", "")).strip()
        if not fpath or not decl:
            issues.append(
                {
                    "severity": "ERROR",
                    "code": "LEAN_TARGET_MISSING_FIELDS",
                    "message": "formalized binding is missing required lean_target fields",
                    "ref": {
                        "binding_id": str(b.get("binding_id", "")),
                        "claim_id": str(b.get("claim_id", "")),
                        "formalization_status": status,
                        "has_file_path": bool(fpath),
                        "has_declaration_name": bool(decl),
                    },
                }
            )
            continue
        resolved_path = _resolve_target_file_path(fpath, project_root)
        if not _is_within_project_root(resolved_path, project_root):
            issues.append(
                {
                    "severity": "ERROR",
                    "code": "LEAN_TARGET_OUTSIDE_PROJECT_ROOT",
                    "message": "formalized binding lean_target.file_path resolves outside project_root",
                    "ref": {
                        "binding_id": str(b.get("binding_id", "")),
                        "claim_id": str(b.get("claim_id", "")),
                        "project_root": str(project_root),
                        "resolved_file_path": str(resolved_path),
                    },
                }
            )
            continue
        out[str(resolved_path)].add(decl)
    return out, issues


def parse_print_axioms_output(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    rx_dep = re.compile(r"^'([^']+)' depends on axioms: \[(.*)\]$")
    rx_none = re.compile(r"^'([^']+)' does not depend on any axioms$")
    for raw in str(text).splitlines():
        line = normalize(raw)
        if not line:
            continue
        m_dep = rx_dep.match(line)
        if m_dep:
            name = m_dep.group(1)
            body = m_dep.group(2).strip()
            axioms = [normalize(x) for x in body.split(",") if normalize(x)]
            out[name] = axioms
            continue
        m_none = rx_none.match(line)
        if m_none:
            out[m_none.group(1)] = []
    return out


def detect_primary_namespace(file_text: str) -> str:
    for raw in file_text.splitlines():
        m = re.match(r"^\s*namespace\s+([A-Za-z0-9_'.]+)\s*$", raw)
        if m:
            return str(m.group(1)).strip()
    return ""


def run_strong_validation_gate(
    *,
    ledger: dict[str, Any],
    project_root: Path,
    allow_axioms: set[str] | None = None,
    allow_trust_compiler: bool = False,
    include_nonformalized: bool = False,
    timeout_sec: int = 240,
    command_runner: Callable[[list[str], Path, int], dict[str, Any]] | None = None,
    ledger_path: str = "",
) -> dict[str, Any]:
    runner = command_runner or default_command_runner
    project_root = Path(project_root).resolve()
    allowed_axioms = {normalize(x) for x in (allow_axioms or {"propext", "Classical.choice", "Quot.sound"}) if normalize(x)}
    if allow_trust_compiler:
        allowed_axioms.add("Lean.trustCompiler")

    targets, pre_issues = collect_targets(
        ledger,
        include_nonformalized=include_nonformalized,
        project_root=project_root,
    )

    issues: list[dict[str, Any]] = list(pre_issues)
    file_reports: list[dict[str, Any]] = []

    for fpath in sorted(targets):
        decls = sorted(targets[fpath])
        fp = Path(fpath)
        rep: dict[str, Any] = {
            "file_path": str(fp),
            "declarations": decls,
            "warning_as_error": {},
            "axiom_audit": {},
        }

        if not fp.exists():
            issues.append(
                {
                    "severity": "ERROR",
                    "code": "LEAN_FILE_MISSING",
                    "message": "target Lean file missing for strong validation",
                    "ref": {"file_path": str(fp)},
                }
            )
            file_reports.append(rep)
            continue

        cmd_warn = ["lake", "env", "lean", "--error=warning", str(fp)]
        res_warn = runner(cmd_warn, project_root, int(timeout_sec))
        rep["warning_as_error"] = {
            "ok": bool(res_warn.get("ok", False)),
            "cmd": res_warn.get("cmd", []),
            "returncode": res_warn.get("returncode"),
            "stderr_tail": _short_tail_sanitized(res_warn.get("stderr", "")),
            "stdout_tail": _short_tail_sanitized(res_warn.get("stdout", "")),
        }
        if not bool(res_warn.get("ok", False)):
            issues.append(
                {
                    "severity": "ERROR",
                    "code": "LEAN_WARNING_AS_ERROR_FAILED",
                    "message": "`lake env lean --error=warning` failed",
                    "ref": {
                        "file_path": str(fp),
                        "returncode": res_warn.get("returncode"),
                        "stderr_tail": _short_tail_sanitized(res_warn.get("stderr", "")),
                    },
                }
            )

        with tempfile.TemporaryDirectory(prefix="leanatlas_axiom_audit_") as tmpdir:
            tmp_file = Path(tmpdir) / f"{fp.stem}.axiom_audit.lean"
            base = fp.read_text(encoding="utf-8")
            primary_namespace = detect_primary_namespace(base)

            query_name_by_decl: dict[str, str] = {}
            for d in decls:
                if "." in d or not primary_namespace:
                    query_name_by_decl[d] = d
                else:
                    query_name_by_decl[d] = f"{primary_namespace}.{d}"

            probe_lines = ["", "-- LeanAtlas axiom audit (auto-generated)"]
            for d in decls:
                probe_lines.append(f"#print axioms {query_name_by_decl[d]}")
            tmp_file.write_text(base + "\n" + "\n".join(probe_lines) + "\n", encoding="utf-8")

            cmd_axiom = ["lake", "env", "lean", str(tmp_file)]
            res_axiom = runner(cmd_axiom, project_root, int(timeout_sec))
            merged = str(res_axiom.get("stdout", "")) + "\n" + str(res_axiom.get("stderr", ""))
            parsed = parse_print_axioms_output(merged)

            decl_reports: list[dict[str, Any]] = []
            for d in decls:
                qname = query_name_by_decl.get(d, d)
                axioms = parsed.get(qname)
                if axioms is None:
                    axioms = parsed.get(d)

                if axioms is None:
                    decl_reports.append(
                        {
                            "declaration": d,
                            "query_name": qname,
                            "parsed": False,
                            "axioms": [],
                            "disallowed_axioms": [],
                        }
                    )
                    issues.append(
                        {
                            "severity": "ERROR",
                            "code": "AXIOM_AUDIT_PARSE_MISSING",
                            "message": "no `#print axioms` result parsed for declaration",
                            "ref": {"file_path": str(fp), "declaration": d},
                        }
                    )
                    continue

                disallowed = [a for a in axioms if a not in allowed_axioms]
                decl_reports.append(
                    {
                        "declaration": d,
                        "query_name": qname,
                        "parsed": True,
                        "axioms": axioms,
                        "disallowed_axioms": disallowed,
                    }
                )
                if disallowed:
                    issues.append(
                        {
                            "severity": "ERROR",
                            "code": "DISALLOWED_AXIOM_DEPENDENCY",
                            "message": "declaration depends on non-permitted axioms",
                            "ref": {
                                "file_path": str(fp),
                                "declaration": d,
                                "disallowed_axioms": disallowed,
                                "allowed_axioms": sorted(allowed_axioms),
                            },
                        }
                    )

            rep["axiom_audit"] = {
                "ok": bool(res_axiom.get("ok", False)),
                "cmd": _sanitize_axiom_cmd_for_report(res_axiom.get("cmd", [])),
                "returncode": res_axiom.get("returncode"),
                "decl_reports": decl_reports,
                "stderr_tail": _short_tail_sanitized(res_axiom.get("stderr", "")),
                "stdout_tail": _short_tail_sanitized(res_axiom.get("stdout", "")),
            }
            if not bool(res_axiom.get("ok", False)):
                issues.append(
                    {
                        "severity": "ERROR",
                        "code": "AXIOM_AUDIT_COMMAND_FAILED",
                        "message": "axiom audit command failed",
                        "ref": {
                            "file_path": str(fp),
                            "returncode": res_axiom.get("returncode"),
                            "stderr_tail": _short_tail_sanitized(res_axiom.get("stderr", "")),
                        },
                    }
                )

        file_reports.append(rep)

    code_counts = dict(sorted(Counter(i.get("code", "") for i in issues if str(i.get("code", "")).strip()).items()))
    errors = [i for i in issues if i.get("severity") == "ERROR"]
    warnings = [i for i in issues if i.get("severity") == "WARN"]

    return {
        "schema": "leanatlas.formalization.strong_validation",
        "schema_version": "0.1",
        "generated_at_utc": utc_now_iso(),
        "ledger_path": str(ledger_path),
        "project_root": str(project_root),
        "settings": {
            "include_nonformalized": bool(include_nonformalized),
            "timeout_sec": int(timeout_sec),
            "allow_axioms": sorted(allowed_axioms),
        },
        "summary": {
            "pass": len(errors) == 0,
            "errors": len(errors),
            "warnings": len(warnings),
            "issue_code_counts": code_counts,
            "target_files": len(file_reports),
            "target_declarations": sum(len(x.get("declarations", [])) for x in file_reports),
        },
        "issues": issues,
        "file_reports": file_reports,
    }


def _parse_allow_axioms(raw: str) -> set[str]:
    return {normalize(x) for x in str(raw).split(",") if normalize(x)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Run deterministic strong validation on FormalizationLedger")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--report-out", required=True)
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--allow-axioms", default="propext,Classical.choice,Quot.sound")
    ap.add_argument("--allow-trust-compiler", action="store_true")
    ap.add_argument("--include-nonformalized", action="store_true")
    ap.add_argument("--timeout-sec", type=int, default=240)
    args = ap.parse_args()

    ledger_path = Path(args.ledger).resolve()
    report_path = Path(args.report_out).resolve()
    ledger = load_json(ledger_path)

    report = run_strong_validation_gate(
        ledger=ledger,
        project_root=Path(args.project_root),
        allow_axioms=_parse_allow_axioms(args.allow_axioms),
        allow_trust_compiler=bool(args.allow_trust_compiler),
        include_nonformalized=bool(args.include_nonformalized),
        timeout_sec=int(args.timeout_sec),
        ledger_path=str(ledger_path),
    )

    dump_json(report_path, report)
    print(json.dumps({"report": str(report_path), "summary": report["summary"]}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
