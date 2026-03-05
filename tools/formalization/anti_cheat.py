#!/usr/bin/env python3
"""Deterministic anti-cheat checks for formalization artifacts and Lean code."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_POLICY: dict[str, Any] = {
    "version": "0.1",
    "fail_on_sorry": True,
    "fail_on_admit": True,
    "fail_on_axiom": True,
    "fail_on_opaque": True,
    "fail_on_stub_name": True,
    "fail_on_unmapped_atoms": True,
    "fail_on_unreferenced_anchors": True,
    "fail_on_passthrough_no_external": True,
    "fail_on_semantic_placeholder_no_external": True,
    "treat_external_passthrough_as_error": False,
    "min_noncomment_proof_lines": 2,
    "allow_axiom_file_regex": [r"(^|.*/)external_hooks/[^/]+\.lean$"],
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize(text: str) -> str:
    return " ".join(str(text).strip().split())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_issue(issues: list[dict[str, Any]], severity: str, code: str, message: str, ref: dict[str, Any]) -> None:
    issues.append({"severity": severity, "code": code, "message": message, "ref": ref})


def normalize_prop_text(text: str) -> str:
    t = normalize(str(text)).replace("→", "->")
    return re.sub(r"\s+", "", t)


def split_top_level_conj(text: str) -> list[str]:
    if not text:
        return []
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch == "∧" and depth == 0:
            part = normalize("".join(buf))
            if part:
                parts.append(part)
            buf = []
            continue
        buf.append(ch)
    tail = normalize("".join(buf))
    if tail:
        parts.append(tail)
    return parts


def split_top_level_colon(text: str) -> tuple[str, str] | None:
    depth = 0
    for i, ch in enumerate(text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            lhs = normalize(text[:i])
            rhs = normalize(text[i + 1 :])
            if lhs and rhs:
                return lhs, rhs
    return None


def parse_hyp_binders_from_header(header_text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(header_text):
        if header_text[i] != "(":
            i += 1
            continue
        depth = 1
        j = i + 1
        while j < len(header_text) and depth > 0:
            if header_text[j] == "(":
                depth += 1
            elif header_text[j] == ")":
                depth -= 1
            j += 1
        if depth != 0:
            break
        inside = header_text[i + 1 : j - 1]
        parsed = split_top_level_colon(inside)
        if parsed:
            lhs, rhs = parsed
            names = [x for x in lhs.split() if x]
            if names and all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_']*", n) for n in names):
                for name in names:
                    out.append((name, rhs))
        i = j
    return out


def extract_goal_text_from_header(header_text: str) -> str:
    marker = header_text.find(":= by")
    if marker < 0:
        return ""
    prefix = header_text[:marker]
    depth = 0
    last_colon = -1
    for i, ch in enumerate(prefix):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            last_colon = i
    if last_colon < 0:
        return ""
    return normalize(prefix[last_colon + 1 :])


def parse_theorem_blocks(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not path.exists() or path.suffix != ".lean":
        return out

    lines = path.read_text(encoding="utf-8").splitlines()
    start_re = re.compile(r"^\s*(theorem|lemma)\s+([A-Za-z0-9_']+)\b")
    top_re = re.compile(r"^\s*(theorem|def|namespace|end|lemma|axiom|opaque|abbrev|example|instance)\b")

    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = start_re.match(line)
        if m:
            starts.append((i, m.group(2)))

    for idx, (start_i, name) in enumerate(starts):
        next_i = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        header_end = None
        for j in range(start_i, min(next_i, len(lines))):
            if ":= by" in lines[j]:
                header_end = j
                break
        if header_end is None:
            continue

        body_start = header_end + 1
        body_end = next_i
        for j in range(body_start, next_i):
            if top_re.match(lines[j]):
                body_end = j
                break

        header_lines = lines[start_i : header_end + 1]
        body_lines = lines[body_start:body_end]
        header_text = "\n".join(header_lines)

        out[name] = {
            "line": start_i + 1,
            "header_text": header_text,
            "goal_text": extract_goal_text_from_header(header_text),
            "proof_lines": body_lines,
            "hyp_binders": parse_hyp_binders_from_header(header_text),
        }
    return out


def parse_declarations(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists() or path.suffix != ".lean":
        return out
    rx = re.compile(r"^\s*(theorem|lemma|def|abbrev|example|opaque|instance|axiom)\s+([A-Za-z_][A-Za-z0-9_']*)\b")
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        m = rx.match(line)
        if not m:
            continue
        out.append({"kind": m.group(1), "name": m.group(2), "line": i, "line_text": line})
    return out


def passthrough_hypotheses(*, proof_lines: list[str], hyp_names: list[str]) -> set[str]:
    stmts = [x.strip() for x in proof_lines if x.strip() and not x.strip().startswith("--")]
    if not stmts:
        return set()

    used: set[str] = set()
    for s in stmts:
        simple = bool(re.match(r"^(exact|refine)\b", s)) or bool(re.match(r"^simpa\b.*\busing\b", s))
        if not simple:
            return set()
        for h in hyp_names:
            if re.search(rf"\b{re.escape(h)}\b", s):
                used.add(h)
    return used


def semantic_placeholder_reasons(theorem_block: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    goal_text = str(theorem_block.get("goal_text", ""))
    if not goal_text:
        return reasons

    goal_norm = normalize_prop_text(goal_text)
    if not goal_norm:
        return reasons

    hyp_binders = theorem_block.get("hyp_binders", [])
    hyp_norms: list[tuple[str, str]] = []
    hyp_conj_parts: list[tuple[str, list[str]]] = []
    for hyp_name, hyp_ty in hyp_binders:
        ty_norm = normalize_prop_text(hyp_ty)
        if ty_norm:
            hyp_norms.append((str(hyp_name), ty_norm))
        parts = [normalize_prop_text(x) for x in split_top_level_conj(str(hyp_ty))]
        parts = [x for x in parts if x]
        if len(parts) >= 2:
            hyp_conj_parts.append((str(hyp_name), parts))

    direct = sorted([name for name, ty in hyp_norms if ty == goal_norm])
    if direct:
        reasons.append(f"goal type matches hypothesis type directly: {direct}")

    carried = sorted([name for name, parts in hyp_conj_parts if goal_norm in parts])
    if carried:
        reasons.append(f"goal appears as conjunct inside hypothesis: {carried}")

    goal_parts = [normalize_prop_text(x) for x in split_top_level_conj(goal_text)]
    goal_parts = [x for x in goal_parts if x]
    if len(goal_parts) >= 2:
        available: set[str] = {ty for _name, ty in hyp_norms}
        for _name, parts in hyp_conj_parts:
            available.update(parts)
        if all(gp in available for gp in goal_parts):
            reasons.append("all goal conjuncts already present in hypotheses")

    return sorted(set(reasons))


def line_is_allowed_for_axiom(path: Path, policy: dict[str, Any]) -> bool:
    for rx in policy.get("allow_axiom_file_regex", []):
        if re.match(str(rx), str(path)):
            return True
    return False


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


def _target_files_from_ledger(ledger: dict[str, Any], project_root: Path, issues: list[dict[str, Any]]) -> set[Path]:
    files: set[Path] = set()
    for b in ledger.get("formalization_bindings", []):
        if not isinstance(b, dict):
            continue
        lt = b.get("lean_target") if isinstance(b.get("lean_target"), dict) else {}
        fpath = str(lt.get("file_path", "")).strip()
        if not fpath:
            continue
        resolved = _resolve_target_file_path(fpath, project_root)
        if not _is_within_project_root(resolved, project_root):
            add_issue(
                issues,
                "ERROR",
                "LEAN_TARGET_OUTSIDE_PROJECT_ROOT",
                "lean_target.file_path resolves outside project_root",
                {
                    "binding_id": str(b.get("binding_id", "")),
                    "claim_id": str(b.get("claim_id", "")),
                    "project_root": str(project_root),
                    "resolved_file_path": str(resolved),
                },
            )
            continue
        files.add(resolved)
    return files


def run_anti_cheat_gate(
    *,
    ledger: dict[str, Any],
    target_lean_files: list[Path] | None = None,
    project_root: Path | None = None,
    policy: dict[str, Any] | None = None,
    consistency_report: dict[str, Any] | None = None,
    ledger_path: str = "",
) -> dict[str, Any]:
    merged_policy = dict(DEFAULT_POLICY)
    if policy:
        merged_policy.update(policy)

    issues: list[dict[str, Any]] = []
    if project_root is not None:
        resolved_project_root = Path(project_root).resolve()
    elif ledger_path:
        resolved_project_root = Path(ledger_path).resolve().parent
    else:
        resolved_project_root = DEFAULT_PROJECT_ROOT

    bindings = [x for x in ledger.get("formalization_bindings", []) if isinstance(x, dict)]

    if target_lean_files:
        target_files: set[Path] = set()
        for raw_path in target_lean_files:
            resolved = _resolve_target_file_path(str(raw_path), resolved_project_root)
            if not _is_within_project_root(resolved, resolved_project_root):
                add_issue(
                    issues,
                    "ERROR",
                    "LEAN_TARGET_OUTSIDE_PROJECT_ROOT",
                    "target_lean_files entry resolves outside project_root",
                    {
                        "project_root": str(resolved_project_root),
                        "resolved_file_path": str(resolved),
                    },
                )
                continue
            target_files.add(resolved)
    else:
        target_files = _target_files_from_ledger(ledger, resolved_project_root, issues)

    atom_ids = {str(x.get("atom_id", "")).strip() for x in ledger.get("clause_atoms", []) if isinstance(x, dict)}
    anchor_ids = {str(x.get("anchor_id", "")).strip() for x in ledger.get("lean_anchors", []) if isinstance(x, dict)}
    mapped_atoms = {str(x.get("atom_id", "")).strip() for x in ledger.get("atom_mappings", []) if isinstance(x, dict)}
    mapped_anchors = {str(x.get("anchor_id", "")).strip() for x in ledger.get("atom_mappings", []) if isinstance(x, dict)}

    unmapped_atoms = sorted(x for x in atom_ids if x and x not in mapped_atoms)
    if unmapped_atoms:
        sev = "ERROR" if bool(merged_policy.get("fail_on_unmapped_atoms", True)) else "WARN"
        add_issue(
            issues,
            sev,
            "UNMAPPED_ATOM",
            "clause_atom has no atom_mapping",
            {"count": len(unmapped_atoms), "atom_ids": unmapped_atoms[:100]},
        )

    unref_anchors = sorted(x for x in anchor_ids if x and x not in mapped_anchors)
    if unref_anchors:
        sev = "ERROR" if bool(merged_policy.get("fail_on_unreferenced_anchors", True)) else "WARN"
        add_issue(
            issues,
            sev,
            "UNREFERENCED_ANCHOR",
            "lean_anchor has no atom_mapping",
            {"count": len(unref_anchors), "anchor_ids": unref_anchors[:100]},
        )

    decls_by_file: dict[str, list[dict[str, Any]]] = {}
    theorem_by_file: dict[str, dict[str, dict[str, Any]]] = {}

    for f in sorted(target_files, key=lambda p: str(p)):
        if not f.exists():
            add_issue(issues, "ERROR", "LEAN_FILE_MISSING", "target Lean file not found", {"file_path": str(f)})
            continue

        raw_lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        in_block_comment = False
        for line_no, line in enumerate(raw_lines, start=1):
            code = line
            if in_block_comment:
                if "-/" in code:
                    code = code.split("-/", 1)[1]
                    in_block_comment = False
                else:
                    continue

            while "/-" in code:
                pre, post = code.split("/-", 1)
                if "-/" in post:
                    post = post.split("-/", 1)[1]
                    code = pre + " " + post
                else:
                    code = pre
                    in_block_comment = True
                    break

            code = code.split("--", 1)[0]
            stripped = code.strip()
            if not stripped:
                continue

            if bool(merged_policy.get("fail_on_sorry", True)) and re.search(r"\bsorry\b", code):
                add_issue(
                    issues,
                    "ERROR",
                    "SORRY_PRESENT",
                    "found `sorry` token in non-comment Lean code",
                    {"file_path": str(f), "line": line_no, "line_text": code},
                )
            if bool(merged_policy.get("fail_on_admit", True)) and re.search(r"\badmit\b", code):
                add_issue(
                    issues,
                    "ERROR",
                    "ADMIT_PRESENT",
                    "found `admit` token in non-comment Lean code",
                    {"file_path": str(f), "line": line_no, "line_text": code},
                )

        decls = parse_declarations(f)
        decls_by_file[str(f)] = decls
        theorem_by_file[str(f)] = parse_theorem_blocks(f)

        for d in decls:
            kind = str(d.get("kind", ""))
            name = str(d.get("name", ""))
            line = d.get("line")

            if kind == "axiom" and bool(merged_policy.get("fail_on_axiom", True)) and not line_is_allowed_for_axiom(f, merged_policy):
                add_issue(
                    issues,
                    "ERROR",
                    "AXIOM_DECLARATION_PRESENT",
                    "axiom declaration appears in target Lean file",
                    {"file_path": str(f), "declaration_name": name, "line": line},
                )
            if kind == "opaque" and bool(merged_policy.get("fail_on_opaque", True)):
                add_issue(
                    issues,
                    "ERROR",
                    "OPAQUE_DECLARATION_PRESENT",
                    "opaque declaration appears in target Lean file",
                    {"file_path": str(f), "declaration_name": name, "line": line},
                )
            if name.lower().endswith("_stub") and bool(merged_policy.get("fail_on_stub_name", True)):
                add_issue(
                    issues,
                    "ERROR",
                    "STUB_DECLARATION_PRESENT",
                    "declaration name ends with `_stub`",
                    {"file_path": str(f), "declaration_name": name, "line": line},
                )

    min_lines = int(merged_policy.get("min_noncomment_proof_lines", 2))
    for b in bindings:
        cid = str(b.get("claim_id", "")).strip()
        lt = b.get("lean_target") if isinstance(b.get("lean_target"), dict) else {}
        decl = str(lt.get("declaration_name", "")).strip()
        raw_fpath = str(lt.get("file_path", "")).strip()
        fkey = ""
        if raw_fpath:
            resolved_fpath = _resolve_target_file_path(raw_fpath, resolved_project_root)
            if not _is_within_project_root(resolved_fpath, resolved_project_root):
                add_issue(
                    issues,
                    "ERROR",
                    "LEAN_TARGET_OUTSIDE_PROJECT_ROOT",
                    "lean_target.file_path resolves outside project_root",
                    {
                        "binding_id": str(b.get("binding_id", "")),
                        "claim_id": cid,
                        "project_root": str(resolved_project_root),
                        "resolved_file_path": str(resolved_fpath),
                    },
                )
                continue
            fkey = str(resolved_fpath)

        ext_ids = [str(x).strip() for x in b.get("external_dependency_result_ids", []) if str(x).strip()]
        ext_status = str(b.get("external_dependency_status", "")).strip().upper()
        if ext_ids and ext_status not in {"FORMALIZED", "RESOLVED"}:
            add_issue(
                issues,
                "ERROR",
                "EXTERNAL_DEPENDENCY_PENDING",
                "external dependency is not resolved for binding",
                {
                    "claim_id": cid,
                    "binding_id": b.get("binding_id"),
                    "external_dependency_status": ext_status,
                    "external_result_ids": ext_ids,
                },
            )

        if not fkey:
            continue

        decls = decls_by_file.get(fkey, [])
        if decl and decl not in {str(x.get("name", "")) for x in decls}:
            add_issue(
                issues,
                "ERROR",
                "DECLARATION_NOT_FOUND",
                "lean_target declaration_name is missing in file",
                {"claim_id": cid, "binding_id": b.get("binding_id"), "declaration_name": decl, "file_path": fkey},
            )
            continue

        block = theorem_by_file.get(fkey, {}).get(decl)
        if not block:
            add_issue(
                issues,
                "WARN",
                "THEOREM_BLOCK_NOT_PARSED",
                "could not parse theorem block; skipped semantic checks",
                {"claim_id": cid, "declaration_name": decl, "file_path": fkey},
            )
            continue

        proof_lines = [x for x in block.get("proof_lines", []) if str(x).strip() and not str(x).strip().startswith("--")]
        if len(proof_lines) < min_lines:
            add_issue(
                issues,
                "WARN",
                "PROOF_TOO_SHORT",
                "proof body has very few non-comment lines",
                {
                    "claim_id": cid,
                    "declaration_name": decl,
                    "file_path": fkey,
                    "noncomment_proof_line_count": len(proof_lines),
                    "min_required": min_lines,
                },
            )

        hyp_names = [str(h[0]) for h in block.get("hyp_binders", [])]
        used_hyps = passthrough_hypotheses(proof_lines=block.get("proof_lines", []), hyp_names=hyp_names)
        if used_hyps:
            no_external = len(ext_ids) == 0
            if no_external and bool(merged_policy.get("fail_on_passthrough_no_external", True)):
                sev = "ERROR"
            elif (not no_external) and bool(merged_policy.get("treat_external_passthrough_as_error", False)):
                sev = "ERROR"
            else:
                sev = "WARN"
            add_issue(
                issues,
                sev,
                "OPAQUE_HYPOTHESIS_PATTERN",
                "proof appears to forward assumptions directly",
                {
                    "claim_id": cid,
                    "binding_id": b.get("binding_id"),
                    "declaration_name": decl,
                    "file_path": fkey,
                    "line": block.get("line"),
                    "forwarded_hypotheses": sorted(used_hyps),
                    "external_result_ids": ext_ids,
                },
            )

        sem_reasons = semantic_placeholder_reasons(block)
        if sem_reasons:
            no_external = len(ext_ids) == 0
            if no_external and bool(merged_policy.get("fail_on_semantic_placeholder_no_external", True)):
                sev = "ERROR"
                code = "SEMANTIC_PLACEHOLDER_NO_EXTERNAL"
            elif (not no_external) and bool(merged_policy.get("treat_external_passthrough_as_error", False)):
                sev = "ERROR"
                code = "SEMANTIC_PLACEHOLDER_WITH_EXTERNAL"
            else:
                sev = "WARN"
                code = "SEMANTIC_PLACEHOLDER_WITH_EXTERNAL" if not no_external else "SEMANTIC_PLACEHOLDER_NO_EXTERNAL"
            add_issue(
                issues,
                sev,
                code,
                "goal appears semantically already encoded in assumptions",
                {
                    "claim_id": cid,
                    "binding_id": b.get("binding_id"),
                    "declaration_name": decl,
                    "file_path": fkey,
                    "line": block.get("line"),
                    "goal_text": block.get("goal_text", ""),
                    "semantic_placeholder_reasons": sem_reasons,
                    "external_result_ids": ext_ids,
                },
            )

    if consistency_report is not None and isinstance(consistency_report, dict):
        csum = consistency_report.get("summary", {}) if isinstance(consistency_report.get("summary", {}), dict) else {}
        if bool(csum.get("pass", False)) is False:
            add_issue(
                issues,
                "ERROR",
                "CONSISTENCY_NOT_PASS",
                "consistency report did not pass",
                {"summary": csum},
            )

    issue_counts = dict(sorted(Counter(x["code"] for x in issues).items()))
    errors = [x for x in issues if x.get("severity") == "ERROR"]
    warnings = [x for x in issues if x.get("severity") == "WARN"]

    return {
        "schema": "leanatlas.formalization.anti_cheat",
        "schema_version": "0.1",
        "generated_at_utc": utc_now_iso(),
        "ledger_path": str(ledger_path),
        "project_root": str(resolved_project_root),
        "policy": merged_policy,
        "summary": {
            "pass": len(errors) == 0,
            "errors": len(errors),
            "warnings": len(warnings),
            "issue_code_counts": issue_counts,
            "target_lean_files": [str(x) for x in sorted(target_files, key=lambda p: str(p))],
        },
        "issues": issues,
    }


def _parse_target_files(raw: str) -> list[Path]:
    out: list[Path] = []
    for chunk in str(raw).split(","):
        val = chunk.strip()
        if val:
            out.append(Path(val))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Run deterministic anti-cheat checks on FormalizationLedger")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--report-out", required=True)
    ap.add_argument("--project-root", default="")
    ap.add_argument("--policy", default="")
    ap.add_argument("--consistency-report", default="")
    ap.add_argument("--target-lean-files", default="", help="comma-separated lean files")
    args = ap.parse_args()

    ledger_path = Path(args.ledger).resolve()
    report_path = Path(args.report_out).resolve()
    ledger = load_json(ledger_path)

    policy = None
    if args.policy:
        policy = load_json(Path(args.policy).resolve())

    consistency = None
    if args.consistency_report:
        cpath = Path(args.consistency_report).resolve()
        if cpath.exists():
            consistency = load_json(cpath)

    report = run_anti_cheat_gate(
        ledger=ledger,
        target_lean_files=_parse_target_files(args.target_lean_files),
        project_root=Path(args.project_root).resolve() if args.project_root else None,
        policy=policy,
        consistency_report=consistency,
        ledger_path=str(ledger_path),
    )
    dump_json(report_path, report)
    print(json.dumps({"report": str(report_path), "summary": report["summary"]}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
