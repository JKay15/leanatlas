"""Shared Lake packages cache policy for LeanAtlas runners.

Policy goals:
- Keep one canonical shared cache under `.cache/leanatlas/shared_lake/packages`.
- Every runner workspace must hydrate `.lake/packages` from that shared cache.
- Avoid per-run full clones of `.lake/packages` whenever possible.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


DEFAULT_REQUIRED_PACKAGES: Tuple[str, ...] = ("mathlib", "importGraph")
WORKSPACE_SEED_MARKER = ".leanatlas_shared_cache_seed.json"


@dataclass(frozen=True)
class CacheResult:
    ok: bool
    hit: bool
    method: str
    shared_packages: str
    workspace_packages: str
    seed_source: Optional[str] = None
    seed_method: Optional[str] = None
    required_packages: Tuple[str, ...] = DEFAULT_REQUIRED_PACKAGES
    note: Optional[str] = None
    ts_utc: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "hit": self.hit,
            "method": self.method,
            "shared_packages": self.shared_packages,
            "workspace_packages": self.workspace_packages,
            "seed_source": self.seed_source,
            "seed_method": self.seed_method,
            "required_packages": list(self.required_packages),
            "note": self.note,
            "ts_utc": self.ts_utc,
        }


def _utc_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime())


def _safe_rmtree(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    shutil.rmtree(path, ignore_errors=True)


def _has_required_packages(packages_dir: Path, required: Sequence[str]) -> bool:
    if not packages_dir.exists() or not packages_dir.is_dir():
        return False
    return all((packages_dir / name).exists() for name in required)


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def canonical_shared_packages(repo_root: Path) -> Path:
    override = os.environ.get("LEANATLAS_SHARED_LAKE_PACKAGES")
    if override:
        return Path(override).expanduser().resolve()
    return (repo_root / ".cache" / "leanatlas" / "shared_lake" / "packages").resolve()


def candidate_seed_sources(repo_root: Path) -> List[Path]:
    out: List[Path] = []

    explicit = os.environ.get("LEANATLAS_LAKE_PACKAGES_SEED_FROM")
    if explicit:
        out.append(Path(explicit).expanduser().resolve())

    out.append((repo_root / ".lake" / "packages").resolve())
    out.append((repo_root / ".cache" / "leanatlas" / "e2e_shared_workspace" / "workdir" / ".lake" / "packages").resolve())
    out.append((repo_root / ".cache" / "leanatlas" / "e2e_run_cases" / "workdir" / ".lake" / "packages").resolve())

    dedup: List[Path] = []
    seen: set[str] = set()
    for p in out:
        k = str(p)
        if k in seen:
            continue
        seen.add(k)
        dedup.append(p)
    return dedup


def _seed_shared_packages_from_donor(
    *,
    shared_packages: Path,
    donor: Path,
    required: Sequence[str],
) -> tuple[bool, str]:
    if not _has_required_packages(donor, required):
        return False, ""

    shared_packages.parent.mkdir(parents=True, exist_ok=True)
    if shared_packages.exists() or shared_packages.is_symlink():
        _safe_rmtree(shared_packages)

    try:
        shutil.copytree(
            donor,
            shared_packages,
            dirs_exist_ok=False,
            copy_function=os.link,
            symlinks=True,
        )
        return True, "hardlink"
    except Exception:
        pass

    # Canonical cache initialization is a one-time cost; full copy fallback is acceptable here.
    shutil.copytree(
        donor,
        shared_packages,
        dirs_exist_ok=False,
        copy_function=shutil.copy2,
        symlinks=True,
    )
    return True, "copy"


def _seed_marker_path(workspace_packages: Path) -> Path:
    return workspace_packages / WORKSPACE_SEED_MARKER


def _read_seed_marker(workspace_packages: Path) -> Optional[Dict[str, Any]]:
    marker = _seed_marker_path(workspace_packages)
    if not marker.exists() or not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _write_seed_marker(
    *,
    workspace_packages: Path,
    shared_packages: Path,
    required: Sequence[str],
    method: str,
    purpose: str,
) -> None:
    marker = _seed_marker_path(workspace_packages)
    payload = {
        "schema": "leanatlas.shared_cache_seed",
        "schema_version": "1",
        "shared_packages": str(shared_packages),
        "required_packages": list(required),
        "method": method,
        "purpose": purpose,
        "ts_utc": _utc_stamp(),
    }
    marker.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _package_sentinel_rel(pkg_dir: Path) -> Optional[Path]:
    top_lean = sorted(p.name for p in pkg_dir.glob("*.lean") if p.is_file())
    if top_lean:
        return Path(top_lean[0])
    for name in ("lakefile.lean", "lake-manifest.json", "README.md"):
        p = pkg_dir / name
        if p.is_file():
            return Path(name)
    return None


def _same_inode(a: Path, b: Path) -> bool:
    sa = a.stat()
    sb = b.stat()
    return (sa.st_dev == sb.st_dev) and (sa.st_ino == sb.st_ino)


def workspace_links_to_shared(
    *,
    workspace_root: Path,
    shared_packages: Path,
    required_packages: Sequence[str] = DEFAULT_REQUIRED_PACKAGES,
) -> bool:
    workspace_packages = workspace_root / ".lake" / "packages"
    required = tuple(required_packages)
    if not _has_required_packages(workspace_packages, required):
        return False
    if not _has_required_packages(shared_packages, required):
        return False

    for pkg in required:
        shared_pkg = shared_packages / pkg
        workspace_pkg = workspace_packages / pkg
        if not shared_pkg.is_dir() or not workspace_pkg.is_dir():
            return False
        rel = _package_sentinel_rel(shared_pkg)
        if rel is None:
            return False
        shared_file = shared_pkg / rel
        workspace_file = workspace_pkg / rel
        if not workspace_file.is_file():
            return False
        if not _same_inode(shared_file, workspace_file):
            return False
    return True


def _seed_workspace_packages(
    *,
    workspace_packages: Path,
    shared_packages: Path,
    required: Sequence[str],
) -> str:
    if workspace_packages.exists() or workspace_packages.is_symlink():
        _safe_rmtree(workspace_packages)

    try:
        shutil.copytree(
            shared_packages,
            workspace_packages,
            dirs_exist_ok=False,
            copy_function=os.link,
            symlinks=True,
        )
        if _has_required_packages(workspace_packages, required):
            return "hardlink_copy"
    except Exception:
        pass

    if not _bool_env("LEANATLAS_ALLOW_HEAVY_PACKAGE_COPY", False):
        raise RuntimeError(
            "failed to seed workspace .lake/packages with hardlinks; refusing heavy copy by default. "
            "Set LEANATLAS_ALLOW_HEAVY_PACKAGE_COPY=1 to allow full copy fallback."
        )

    shutil.copytree(
        shared_packages,
        workspace_packages,
        dirs_exist_ok=False,
        copy_function=shutil.copy2,
        symlinks=True,
    )
    return "copy"


def workspace_has_seeded_packages(
    workspace_root: Path,
    *,
    shared_packages: Optional[Path] = None,
    required_packages: Sequence[str] = DEFAULT_REQUIRED_PACKAGES,
) -> bool:
    workspace_packages = workspace_root / ".lake" / "packages"
    required = tuple(required_packages)
    if not _has_required_packages(workspace_packages, required):
        return False

    marker = _read_seed_marker(workspace_packages)
    if marker is None:
        return False

    marker_required = marker.get("required_packages")
    if not isinstance(marker_required, list):
        return False
    marker_required_set = {str(x) for x in marker_required}
    if not set(required).issubset(marker_required_set):
        return False

    if shared_packages is not None:
        raw_shared = marker.get("shared_packages")
        if not isinstance(raw_shared, str) or not raw_shared.strip():
            return False
        try:
            marker_shared = Path(raw_shared).expanduser().resolve()
        except Exception:
            return False
        if marker_shared != shared_packages.resolve():
            return False

    return True


def ensure_workspace_lake_packages(
    *,
    repo_root: Path,
    workspace_root: Path,
    purpose: str,
    required_packages: Sequence[str] = DEFAULT_REQUIRED_PACKAGES,
) -> CacheResult:
    """Ensure `workspace_root/.lake/packages` is hydrated from canonical shared cache."""

    repo_root = repo_root.resolve()
    workspace_root = workspace_root.resolve()
    required = tuple(required_packages)
    ts = _utc_stamp()

    shared_packages = canonical_shared_packages(repo_root)
    workspace_packages = workspace_root / ".lake" / "packages"

    if workspace_has_seeded_packages(
        workspace_root,
        shared_packages=shared_packages,
        required_packages=required,
    ):
        return CacheResult(
            ok=True,
            hit=True,
            method="present",
            shared_packages=str(shared_packages),
            workspace_packages=str(workspace_packages),
            required_packages=required,
            note=f"workspace already seeded ({purpose})",
            ts_utc=ts,
        )

    if workspace_links_to_shared(
        workspace_root=workspace_root,
        shared_packages=shared_packages,
        required_packages=required,
    ):
        _write_seed_marker(
            workspace_packages=workspace_packages,
            shared_packages=shared_packages,
            required=required,
            method="legacy_hardlink_present",
            purpose=purpose,
        )
        return CacheResult(
            ok=True,
            hit=True,
            method="present_hardlinked",
            shared_packages=str(shared_packages),
            workspace_packages=str(workspace_packages),
            required_packages=required,
            note=f"workspace already hardlinked to shared cache ({purpose})",
            ts_utc=ts,
        )

    seed_source: Optional[str] = None
    seed_method: Optional[str] = None

    if not _has_required_packages(shared_packages, required):
        if shared_packages.exists() or shared_packages.is_symlink():
            _safe_rmtree(shared_packages)

        for donor in candidate_seed_sources(repo_root):
            ok, method = _seed_shared_packages_from_donor(
                shared_packages=shared_packages,
                donor=donor,
                required=required,
            )
            if ok:
                seed_source = str(donor)
                seed_method = method
                break

    if not _has_required_packages(shared_packages, required):
        note = (
            "no seeded shared Lake packages found; initialize dependencies first "
            "(e.g. run `lake update` in repo root or run one E2E bootstrap run)."
        )
        return CacheResult(
            ok=False,
            hit=False,
            method="missing",
            shared_packages=str(shared_packages),
            workspace_packages=str(workspace_packages),
            seed_source=seed_source,
            seed_method=seed_method,
            required_packages=required,
            note=note,
            ts_utc=ts,
        )

    (workspace_root / ".lake").mkdir(parents=True, exist_ok=True)

    try:
        method = _seed_workspace_packages(
            workspace_packages=workspace_packages,
            shared_packages=shared_packages,
            required=required,
        )
    except Exception as ex:
        return CacheResult(
            ok=False,
            hit=False,
            method="error",
            shared_packages=str(shared_packages),
            workspace_packages=str(workspace_packages),
            seed_source=seed_source,
            seed_method=seed_method,
            required_packages=required,
            note=f"workspace seed failed: {ex}",
            ts_utc=ts,
        )

    ok = _has_required_packages(workspace_packages, required)
    if ok:
        _write_seed_marker(
            workspace_packages=workspace_packages,
            shared_packages=shared_packages,
            required=required,
            method=method,
            purpose=purpose,
        )
    return CacheResult(
        ok=ok,
        hit=False,
        method=method,
        shared_packages=str(shared_packages),
        workspace_packages=str(workspace_packages),
        seed_source=seed_source,
        seed_method=seed_method,
        required_packages=required,
        note=f"seeded workspace packages for {purpose}",
        ts_utc=ts,
    )
