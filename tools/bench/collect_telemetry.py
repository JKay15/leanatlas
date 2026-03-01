#!/usr/bin/env python3
"""Collect run telemetry into a unified, gitignored root (deterministic).

Purpose:
- Ensure telemetry-driven automations do not depend on ad-hoc local paths.
- Provide one stable input root: `artifacts/telemetry/**`.

Behavior:
- Discover run directories under configured source roots.
- Copy known telemetry files into `--out-root` with stable destination paths.
- Emit a deterministic index JSON for audit/debug.

This tool never writes outside `artifacts/**` by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


RUN_MARKERS = {
    "AttemptLog.jsonl",
    "RunReport.json",
    "RetrievalTrace.json",
    "PromotionReport.json",
    "GCReport.json",
}

DEFAULT_SOURCES = [
    "artifacts/automation/runs",
    "artifacts/automation_nightly",
    "Problems",
    "docs/examples/reports",
]


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def looks_like_run_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any((path / marker).exists() for marker in RUN_MARKERS)


def discover_run_dirs(root: Path) -> List[Path]:
    if not root.exists():
        return []

    if root.is_file():
        if root.name in RUN_MARKERS and looks_like_run_dir(root.parent):
            return [root.parent]
        return []

    found: List[Path] = []
    for marker in sorted(RUN_MARKERS):
        for p in root.rglob(marker):
            d = p.parent
            if looks_like_run_dir(d):
                found.append(d)
    return sorted(set(found), key=lambda p: p.as_posix())


def stable_key(parts: Sequence[str]) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def sanitize_source_name(rel: str) -> str:
    out = rel.strip().replace("\\", "/").strip("/")
    if not out:
        return "repo_root"
    return out.replace("/", "__")


def copy_files(src_dir: Path, dst_dir: Path) -> List[str]:
    copied: List[str] = []
    dst_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(RUN_MARKERS):
        sp = src_dir / name
        if not sp.exists():
            continue
        shutil.copy2(sp, dst_dir / name)
        copied.append(name)
    return copied


def iter_sources(repo_root: Path, source_roots: Iterable[str]) -> List[Path]:
    out: List[Path] = []
    for rel in source_roots:
        p = (repo_root / rel).resolve()
        # Keep deterministic source order and de-dup by resolved path.
        if p not in out:
            out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".", help="Repository root")
    ap.add_argument("--out-root", default="artifacts/telemetry", help="Destination root (gitignored)")
    ap.add_argument(
        "--source",
        action="append",
        dest="sources",
        default=None,
        help="Additional source root (repo-relative). Repeatable.",
    )
    ap.add_argument("--clean", action="store_true", help="Delete out-root before collecting")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out_root = (repo_root / args.out_root).resolve()
    sources = args.sources or list(DEFAULT_SOURCES)

    if args.clean and out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    warnings: List[str] = []
    entries: List[Dict[str, Any]] = []

    for src_root in iter_sources(repo_root, sources):
        rel_src = src_root.relative_to(repo_root).as_posix() if src_root.is_relative_to(repo_root) else src_root.as_posix()
        src_name = sanitize_source_name(rel_src)

        if not src_root.exists():
            warnings.append(f"source missing: {rel_src}")
            continue

        for run_dir in discover_run_dirs(src_root):
            rel_run = run_dir.relative_to(repo_root).as_posix() if run_dir.is_relative_to(repo_root) else run_dir.as_posix()
            run_key = stable_key([src_name, rel_run])
            dst_dir = out_root / src_name / run_key
            copied = copy_files(run_dir, dst_dir)

            if not copied:
                continue

            entries.append(
                {
                    "source_root": rel_src,
                    "source_run_dir": rel_run,
                    "dest_dir": dst_dir.relative_to(repo_root).as_posix()
                    if dst_dir.is_relative_to(repo_root)
                    else dst_dir.as_posix(),
                    "files": copied,
                }
            )

    entries.sort(key=lambda x: (str(x["source_root"]), str(x["source_run_dir"])))

    index = {
        "schema": "leanatlas.telemetry_collection_index",
        "schema_version": "0.1.0",
        "sources": list(sources),
        "out_root": args.out_root,
        "summary": {
            "entry_count": len(entries),
        },
        "entries": entries,
        "warnings": warnings,
    }

    index_path = out_root / "index.json"
    index_path.write_text(canonical_json(index), encoding="utf-8")
    print(f"[telemetry.collect] entries={len(entries)} out={index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
