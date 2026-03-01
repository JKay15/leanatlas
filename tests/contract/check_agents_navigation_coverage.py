"""AGENTS-root navigation coverage.

Goal: starting from repo-root AGENTS.md, the documentation graph must allow a tool/agent
(or a human) to discover every major functional directory node.

This is a *deterministic* doc-lint. It prevents silent drift where new capabilities
are added but not linked from the navigation chain.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Local-only directories that may exist in a developer checkout but are not
# part of the repo's navigable surface area.
IGNORE_TOP_LEVEL = {
    '.git',
    '.venv',
    '.cache',
    '__pycache__',
}

BRACE_RE = re.compile(r"\{([^{}]+)\}")
PATH_RE = re.compile(r"(?:(?:\.|[A-Za-z0-9_])[-A-Za-z0-9_./{}|,*]+(?:/[-A-Za-z0-9_./{}|,*]+)+)")


def expand_braces(s: str) -> list[str]:
    m = BRACE_RE.search(s)
    if not m:
        return [s]
    pre = s[: m.start()]
    post = s[m.end() :]
    opts = [o.strip() for o in m.group(1).split(",") if o.strip()]
    out: list[str] = []
    for opt in opts:
        out.extend(expand_braces(pre + opt + post))
    return out


def extract_refs(text: str) -> set[str]:
    cands: set[str] = set()
    for m in PATH_RE.finditer(text):
        s = m.group(0).strip('`"\'')
        if s.startswith("http"):
            continue
        if "<" in s or ">" in s:
            continue
        # Disallow shorthand like a|b|c in canonical docs (hard to index deterministically)
        # We still parse it here for robustness, but canonical docs should avoid it.
        parts = s.split("|")
        for part in parts:
            for ex in expand_braces(part):
                cands.add(ex)
    return cands


def resolve_ref(ref: str) -> Path | None:
    ref = ref.strip()
    ref = ref.rstrip(".,;:)")  # trailing punctuation only
    if ref.endswith("/**"):
        ref = ref[: -3]
    if ref.endswith("/*"):
        ref = ref[: -2]
    ref = ref.replace("{", "").replace("}", "")
    p = (REPO / ref).resolve()
    try:
        p.relative_to(REPO)
    except Exception:
        return None
    return p


def bfs_from_agents_root() -> tuple[set[Path], set[Path]]:
    start = REPO / "AGENTS.md"
    q: list[Path] = [start]
    seen_files: set[Path] = set()
    seen_dirs: set[Path] = set()

    while q:
        f = q.pop(0)
        if f in seen_files:
            continue
        if not f.exists() or not f.is_file():
            continue
        seen_files.add(f)
        text = f.read_text(encoding="utf-8", errors="ignore")
        refs = extract_refs(text)
        for r in refs:
            p = resolve_ref(r)
            if not p or not p.exists():
                continue
            if p.is_dir():
                if p not in seen_dirs:
                    seen_dirs.add(p)
                    for name in ("AGENTS.md", "README.md"):
                        cand = p / name
                        if cand.exists() and cand.is_file():
                            q.append(cand)
            else:
                if p.suffix in (".md", ".txt", ".yaml", ".yml", ".json", ".py", ".sh", ".lean"):
                    q.append(p)

    return seen_files, seen_dirs


def functional_dirs() -> set[Path]:
    """Define the 'functional directory nodes' we require to be discoverable.

    Rule: top-level dirs + second-level dirs under key roots.
    """
    out: set[Path] = set()

    for d in REPO.iterdir():
        if d.is_dir() and d.name not in IGNORE_TOP_LEVEL:
            out.add(d)

    for root_name in ("tools", "docs", "tests", "LeanAtlas", ".agents/skills"):
        root = REPO / root_name
        if root.exists() and root.is_dir():
            for d in root.iterdir():
                if d.is_dir() and d.name != "__pycache__":
                    out.add(d)

    return out


def is_covered(d: Path, reachable: set[Path]) -> bool:
    if d in reachable:
        return True
    for p in reachable:
        try:
            p.relative_to(d)
            return True
        except Exception:
            pass
    return False


def main() -> None:
    files, dirs = bfs_from_agents_root()
    reachable = set(files) | set(dirs)

    fun = functional_dirs()
    missing = [str(d.relative_to(REPO)) for d in sorted(fun, key=lambda x: str(x)) if not is_covered(d, reachable)]

    if missing:
        msg = "\n".join(["AGENTS navigation coverage FAILED. Missing functional dirs:"] + [f"- {m}" for m in missing])
        raise SystemExit(msg)

    # Write a small report (useful for debugging in CI)
    report = {
        "reachable_files": sorted(str(p.relative_to(REPO)) for p in files),
        "reachable_dirs": sorted(str(p.relative_to(REPO)) for p in dirs),
        "functional_dirs": sorted(str(p.relative_to(REPO)) for p in fun),
    }
    out_path = REPO / "artifacts" / "nav" / "agents_nav_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
