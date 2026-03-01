#!/usr/bin/env python3
"""Deterministic patch-scope evaluator.

Implements the OPERATOR/MAINTAINER file-edit policy described in
`docs/contracts/WORKFLOW_CONTRACT.md`.

Designed to be used by:
- the small-loop runner (Codex)
- the deterministic Judge
- contract tests (TDD)

Important:
- Inputs/outputs use **repo-relative POSIX paths**.
- Reports/artifacts caches are **ignored** (do not count as edits).
"""

from __future__ import annotations

from typing import Iterable, List, Dict, Any
import re

# ---- constants ----

IGNORED_PREFIXES = (
    "artifacts/",
    ".cache/",
    ".lake/",
)

SYSTEM_PREFIXES = (
    "LeanAtlas/",
    "tools/",
    "docs/contracts/",
    ".github/",
)

REASON_PRIORITY = {
    "SPEC_TOUCHED": 100,
    "SYSTEM_TOUCHED": 90,
    "OUTSIDE_PROBLEM_TOUCHED": 80,
    "PROBLEM_METADATA_TOUCHED": 70,
    "PROBLEM_INTERNAL_UNSAFE": 60,
    "NONLEAN_TOUCHED": 50,
    "UNKNOWN": 10,
    "OK": 0,
}

_VALID_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _is_posix_repo_path(p: str) -> bool:
    # No backslashes, no absolute, no parent traversal.
    return (
        p != ""
        and "\\" not in p
        and not p.startswith("/")
        and not p.startswith("./")
        and ".." not in p.split("/")
    )


def _is_ignored(problem_slug: str, p: str) -> bool:
    if any(p.startswith(pref) for pref in IGNORED_PREFIXES):
        return True
    # Problem run outputs
    if p.startswith(f"Problems/{problem_slug}/Reports/"):
        return True
    return False


def _violation(path: str, code: str) -> Dict[str, str]:
    return {"path": path, "code": code}


def evaluate_patch_scope(problem_slug: str, mode: str, touched_files: Iterable[str]) -> Dict[str, Any]:
    """Evaluate whether an attempt's touched files violate patch scope.

    Parameters
    ----------
    problem_slug:
      The current problem identifier (directory name under Problems/).
    mode:
      "OPERATOR" or "MAINTAINER".
    touched_files:
      Repo-relative POSIX paths detected as modified by the attempt.

    Returns
    -------
    A dict with:
      - verdict: "ALLOW" | "DISALLOW"
      - primary_reason_code: string
      - violations: [{path, code}]
      - ignored_paths: [path]
    """
    if mode not in ("OPERATOR", "MAINTAINER"):
        raise ValueError(f"unknown mode: {mode}")

    ignored: List[str] = []
    violations: List[Dict[str, str]] = []

    for raw in touched_files:
        p = raw.strip()
        if not p:
            continue

        # Path hygiene is enforced by contract; still validate here.
        if not _is_posix_repo_path(p):
            violations.append(_violation(p, "UNKNOWN"))
            continue

        if _is_ignored(problem_slug, p):
            ignored.append(p)
            continue

        if mode == "MAINTAINER":
            # Maintainers may edit anything; patch scope does not disallow here.
            continue

        # OPERATOR mode rules
        if p == f"Problems/{problem_slug}/Spec.lean":
            violations.append(_violation(p, "SPEC_TOUCHED"))
            continue

        if p.startswith(f"Problems/{problem_slug}/"):
            # Inside current problem
            if not p.endswith(".lean"):
                violations.append(_violation(p, "PROBLEM_METADATA_TOUCHED"))
                continue

            # Allowed Lean sources
            if p in (
                f"Problems/{problem_slug}/Proof.lean",
                f"Problems/{problem_slug}/Cache.lean",
                f"Problems/{problem_slug}/Scratch.lean",
            ):
                continue
            if p.startswith(f"Problems/{problem_slug}/Cache/"):
                # Only .lean allowed here (already checked)
                continue

            # Any other .lean file under the problem is considered unsafe by default.
            violations.append(_violation(p, "PROBLEM_INTERNAL_UNSAFE"))
            continue

        # Outside current problem
        if p.startswith("Problems/"):
            violations.append(_violation(p, "OUTSIDE_PROBLEM_TOUCHED"))
            continue

        if any(p.startswith(pref) for pref in SYSTEM_PREFIXES):
            violations.append(_violation(p, "SYSTEM_TOUCHED"))
            continue

        # Any other path is outside the problem and forbidden in OPERATOR mode.
        violations.append(_violation(p, "OUTSIDE_PROBLEM_TOUCHED"))

    # Determine primary reason
    if violations:
        primary = max(violations, key=lambda v: REASON_PRIORITY.get(v["code"], 0))["code"]
        verdict = "DISALLOW"
    else:
        primary = "OK"
        verdict = "ALLOW"

    if not _VALID_CODE.match(primary):
        primary = "UNKNOWN"

    # Sort violations by priority then path
    violations_sorted = sorted(
        violations,
        key=lambda v: (REASON_PRIORITY.get(v["code"], 0), v["path"]),
        reverse=True,
    )

    return {
        "verdict": verdict,
        "primary_reason_code": primary,
        "violations": violations_sorted,
        "ignored_paths": sorted(set(ignored)),
    }

# Backwards-compatible alias (older harnesses import check_patch_scope).
def check_patch_scope(problem_slug: str, mode: str, touched_files):
    """Alias for evaluate_patch_scope (kept for stability).

    Parameters are identical to evaluate_patch_scope.
    """
    return evaluate_patch_scope(problem_slug, mode, touched_files)
