#!/usr/bin/env python3
"""Mine KB/Skill growth suggestions from AttemptLog/RunReport artifacts (deterministic).

This is a *deterministic* mining tool: it does NOT call any LLM and does NOT
require network access.

Industry anchor:
- Log-template mining (Drain / Drain3) to stabilize noisy diagnostics.
- Log clustering (LogCluster-style) to group recurring patterns.

Inputs:
- Any directory that contains run artifacts, e.g.
  - artifacts/telemetry/**
  - Problems/**/Reports/**
  - docs/examples/**

A "run directory" is detected by presence of at least one marker:
- AttemptLog.jsonl
- RunReport.json
- PromotionReport.json
- GCReport.json

Output:
- JSON written to --out (canonical JSON)
- Schema (informal for v0):
  {
    schema: "leanatlas.kb_suggestions",
    schema_version: "0.1.0",
    input: <string>,
    params: {...},
    suggestions: [...],
    warnings: [...]
  }

NOTE: This tool intentionally emits *suggestions*, not automatic edits.
A follow-up automation can convert suggestions into Change Proposals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]


# --------- Deterministic helpers ---------


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_16(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def warn(warnings: List[str], msg: str) -> None:
    warnings.append(msg)


RUN_MARKERS = {
    "AttemptLog.jsonl",
    "RunReport.json",
    "PromotionReport.json",
    "GCReport.json",
}


def looks_like_run_dir(d: Path) -> bool:
    if not d.is_dir():
        return False
    for m in RUN_MARKERS:
        if (d / m).exists():
            return True
    return False


def discover_run_dirs(root: Path) -> List[Path]:
    """Find run directories under root (deterministic ordering)."""
    if not root.exists():
        return []

    if root.is_file():
        if root.name in RUN_MARKERS:
            d = root.parent
            return [d] if looks_like_run_dir(d) else []
        return []

    run_dirs: List[Path] = []
    for marker in sorted(RUN_MARKERS):
        for p in root.rglob(marker):
            d = p.parent
            if looks_like_run_dir(d):
                run_dirs.append(d)

    return sorted(set(run_dirs), key=lambda x: x.as_posix())


def safe_read_json(path: Path, warnings: List[str], strict: bool) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        warn(warnings, f"failed to parse json: {path}: {e}")
        if strict:
            raise
        return None


# --------- Diagnostic template mining ---------


_NUM_RE = re.compile(r"\b\d+\b")
_HEX_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
_PATH_RE = re.compile(r"(?:[A-Za-z]:)?(?:/|\\)[^\s:]+")


def fallback_template(message: str) -> str:
    """A very small deterministic normalizer.

    Used only if Drain3 is unavailable. We still keep this because:
    - It is deterministic.
    - It provides a safe degradation path.
    """
    s = message
    s = _PATH_RE.sub("<PATH>", s)
    s = _HEX_RE.sub("<HEX>", s)
    s = _NUM_RE.sub("<NUM>", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


class TemplateMiner:
    """Template miner wrapper.

    Prefers Drain3 if installed; otherwise falls back to regex normalization.

    Important: we use the *template text* as stable ID, NOT Drain's cluster_id.
    """

    def __init__(self, warnings: List[str]):
        self._warnings = warnings
        self._mode = "fallback"
        self._drain = None

        try:
            from drain3.template_miner import TemplateMiner as _TM  # type: ignore
            from drain3.template_miner_config import TemplateMinerConfig  # type: ignore

            cfg = TemplateMinerConfig()
            # Keep it deterministic and lightweight.
            # The defaults are OK for our scale; we only disable persistence.
            cfg.profiling_enabled = False
            # Important: pass by keyword so config is not interpreted as persistence handler.
            self._drain = _TM(config=cfg)
            self._mode = "drain3"
        except Exception as e:
            warn(self._warnings, f"Drain3 not available; using fallback templates. ({e})")
            self._mode = "fallback"

    @property
    def mode(self) -> str:
        return self._mode

    def template_for(self, message: str) -> str:
        if self._drain is None:
            return fallback_template(message)

        # Drain3 returns a cluster that contains the template.
        res = self._drain.add_log_message(message)
        cluster = res.get("cluster") if isinstance(res, dict) else None
        if cluster is None:
            return fallback_template(message)
        tpl = getattr(cluster, "get_template", None)
        if callable(tpl):
            return str(tpl())
        # Fallback if API changes
        return str(getattr(cluster, "template_mined", fallback_template(message)))


# --------- Pattern grouping ---------


@dataclass(frozen=True)
class PatternKey:
    family: str
    code: str
    stage: str
    # Sorted unique template hashes.
    tpl_hashes: Tuple[str, ...]

    def stable_id(self) -> str:
        raw = json.dumps(
            {
                "family": self.family,
                "code": self.code,
                "stage": self.stage,
                "tpl": list(self.tpl_hashes),
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return sha256_16(raw)


def _main_hotspot_stage(rr: Dict[str, Any]) -> str:
    # Prefer the first hotspot stage as "main". Deterministic.
    hs = rr.get("hotspots")
    if isinstance(hs, list) and hs:
        for h in hs:
            if isinstance(h, dict):
                st = h.get("stage")
                if isinstance(st, str) and st:
                    return st
    return "build"


def _triage_family_code(rr: Dict[str, Any]) -> Tuple[str, str]:
    tri = rr.get("triage")
    if isinstance(tri, dict):
        cat = tri.get("category")
        if isinstance(cat, dict):
            fam = cat.get("family")
            code = cat.get("code")
            if isinstance(fam, str) and fam and isinstance(code, str) and code:
                return fam, code
    # If triage missing, treat as UNKNOWN.
    return "UNKNOWN", "UNKNOWN"


def _diagnostic_messages(rr: Dict[str, Any]) -> List[str]:
    diags = rr.get("diagnostics")
    out: List[str] = []
    if isinstance(diags, list):
        for d in diags:
            if not isinstance(d, dict):
                continue
            msg = d.get("message")
            sev = d.get("severity")
            # Prefer errors only.
            if sev is not None and isinstance(sev, str) and sev.lower() != "error":
                continue
            if isinstance(msg, str) and msg.strip():
                out.append(msg.strip())
    return out


def _cluster_online(keys: List[Tuple[PatternKey, str]]) -> Dict[str, List[Tuple[PatternKey, str]]]:
    """Group by exact PatternKey for v0.

    This is intentionally strict and deterministic. A v1 upgrade can add
    similarity clustering (LogCluster-style) inside each family/code bucket.

    Returns: stable_id -> list[(PatternKey, run_dir)]
    """

    out: Dict[str, List[Tuple[PatternKey, str]]] = {}
    for k, run_dir in keys:
        pid = k.stable_id()
        out.setdefault(pid, []).append((k, run_dir))
    return out


def _load_force_skill_rules(path: Path, warnings: List[str]) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        warn(warnings, f"force-file parse error: {path}: {e}")
        return []
    if not isinstance(obj, dict):
        warn(warnings, f"force-file must be an object: {path}")
        return []
    rules_raw = obj.get("skills")
    if not isinstance(rules_raw, list):
        return []

    out: List[Dict[str, str]] = []
    for it in rules_raw:
        if isinstance(it, str):
            # Support terse form "FAMILY/CODE[/STAGE]".
            parts = [x.strip() for x in it.split("/") if x.strip()]
            if len(parts) >= 2:
                rule = {"triage_family": parts[0], "triage_code": parts[1]}
                if len(parts) >= 3:
                    rule["failure_stage"] = parts[2]
                out.append(rule)
            continue

        if not isinstance(it, dict):
            continue
        if bool(it.get("enabled", True)) is False:
            continue
        fam = str(it.get("triage_family") or "").strip()
        code = str(it.get("triage_code") or "").strip()
        stage = str(it.get("failure_stage") or "").strip()
        if not fam or not code:
            continue
        rule: Dict[str, str] = {"triage_family": fam, "triage_code": code}
        if stage:
            rule["failure_stage"] = stage
        reason = str(it.get("reason") or "").strip()
        if reason:
            rule["reason"] = reason
        out.append(rule)
    return out


def _match_force_rule(key: PatternKey, rules: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    for r in rules:
        if str(r.get("triage_family", "")).strip() != key.family:
            continue
        if str(r.get("triage_code", "")).strip() != key.code:
            continue
        rs = str(r.get("failure_stage", "")).strip()
        if rs and rs != key.stage:
            continue
        return r
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input root (dir or file)")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--min_runs", type=int, default=3, help="Minimum runs for a suggestion")
    ap.add_argument("--min_problems", type=int, default=2, help="Minimum distinct problem_slug")
    ap.add_argument("--max_examples", type=int, default=3, help="Max example run dirs per suggestion")
    ap.add_argument(
        "--force-file",
        default="tools/index/force_deposit.json",
        help="Optional force-deposit policy file. skills[] entries can force suggestions below thresholds.",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Fail (non-zero) on parse errors / missing files",
    )
    args = ap.parse_args()

    inp = Path(args.inp)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    strict = bool(args.strict)
    warnings: List[str] = []
    force_file = Path(str(args.force_file))
    if not force_file.is_absolute():
        force_file = (ROOT / force_file).resolve()
    forced_rules = _load_force_skill_rules(force_file, warnings)

    run_dirs = discover_run_dirs(inp)
    if not inp.exists():
        warn(warnings, f"input root does not exist: {inp}")

    miner = TemplateMiner(warnings)

    # Collect per-run PatternKey inputs
    keyed: List[Tuple[PatternKey, str, str]] = []  # (key, run_dir, problem_slug)

    for d in run_dirs:
        rr_path = d / "RunReport.json"
        rr = safe_read_json(rr_path, warnings, strict) if rr_path.exists() else None
        if rr is None:
            # Without RunReport, we cannot extract triage/diagnostics reliably.
            continue

        problem_slug = rr.get("problem_slug")
        if not isinstance(problem_slug, str) or not problem_slug:
            problem_slug = "UNKNOWN"

        fam, code = _triage_family_code(rr)
        stage = _main_hotspot_stage(rr)

        msgs = _diagnostic_messages(rr)
        tpl_hashes: List[str] = []
        for m in msgs:
            tpl = miner.template_for(m)
            tpl_hashes.append(sha256_16(tpl))

        # Deterministic: unique+sorted
        tpl_hashes_sorted = tuple(sorted(set(tpl_hashes)))

        key = PatternKey(family=fam, code=code, stage=stage, tpl_hashes=tpl_hashes_sorted)
        keyed.append((key, d.as_posix(), problem_slug))

    # Deterministic ordering
    keyed.sort(key=lambda x: (x[0].family, x[0].code, x[0].stage, x[0].stable_id(), x[1]))

    clusters = _cluster_online([(k, rd) for (k, rd, _ps) in keyed])

    # Build suggestions
    suggestions: List[Dict[str, Any]] = []
    forced_suggestion_count = 0

    # For counting distinct problems per cluster
    cluster_problems: Dict[str, set] = {}
    for k, rd, ps in keyed:
        pid = k.stable_id()
        cluster_problems.setdefault(pid, set()).add(ps)

    for pid in sorted(clusters.keys()):
        items = clusters[pid]
        runs = [rd for (_k, rd) in items]
        distinct_problems = sorted(cluster_problems.get(pid, set()))
        meets_threshold = not (
            len(runs) < int(args.min_runs) and len(distinct_problems) < int(args.min_problems)
        )

        # Representative key (all keys identical in v0 exact-grouping)
        k0 = items[0][0]
        force_rule = _match_force_rule(k0, forced_rules)
        forced = force_rule is not None

        if not meets_threshold and not forced:
            continue

        item: Dict[str, Any] = {
            "suggestion_id": pid,
            "pattern": {
                "triage_family": k0.family,
                "triage_code": k0.code,
                "failure_stage": k0.stage,
                "diag_template_hashes": list(k0.tpl_hashes),
            },
            "counts": {
                "run_count": len(runs),
                "distinct_problem_count": len(distinct_problems),
            },
            "evidence": {
                "example_run_dirs": runs[: int(args.max_examples)],
                "problem_slugs": distinct_problems[: int(args.max_examples)],
            },
            # Intentionally minimal: actual KB text is created via Change Proposal.
            "recommended_next": {
                "action": "CREATE_KB_DRAFT",
                "kb_path": f"docs/agents/kb/draft/{pid}.md",
            },
        }
        if forced:
            forced_suggestion_count += 1
            item["force_deposit"] = {
                "enabled": True,
                "reason": str((force_rule or {}).get("reason") or "force_deposit_policy"),
                "policy_path": str(force_file),
            }
        suggestions.append(item)

    report: Dict[str, Any] = {
        "schema": "leanatlas.kb_suggestions",
        "schema_version": "0.1.0",
        "input": str(inp),
        "params": {
            "min_runs": int(args.min_runs),
            "min_problems": int(args.min_problems),
            "max_examples": int(args.max_examples),
            "template_miner": miner.mode,
            "force_file": str(force_file),
        },
        "summary": {
            "run_dir_count": len(run_dirs),
            "runs_with_runreport": len({rd for (_k, rd, _ps) in keyed}),
            "suggestion_count": len(suggestions),
            "forced_suggestion_count": forced_suggestion_count,
        },
        "suggestions": suggestions,
        "warnings": warnings,
    }

    out_path.write_text(canonical_json(report), encoding="utf-8")
    print(f"[bench.mine_kb_suggestions] wrote {out_path} (suggestions={len(suggestions)})")

    if strict and warnings:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[bench.mine_kb_suggestions] FATAL: {e}", file=sys.stderr)
        raise
