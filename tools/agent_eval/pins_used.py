"""pins_used.json (runner-owned) writer.

Phase6 graders treat `pins_used.json` as a hard gate (missing => FAIL).

To avoid pushing this bookkeeping onto agent implementations (and to keep runs
comparable across agents), the *runner* owns this artifact.

This module writes a deterministic `pins_used.json` into a run's report directory.

See:
- docs/contracts/REPORTING_CONTRACT.md
- docs/schemas/PinsUsed.schema.json
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_pins_used(*, report_dir: Path, repo_root: Path, generated_by: str = "leanatlas.runner") -> Path:
    """Ensure `pins_used.json` exists in `report_dir`.

    The file is always (re)written to enforce a stable, comparable format.

    Args:
        report_dir: Problems/<slug>/Reports/<run_id>/
        repo_root: Repository root that contains tools/deps/pins.json
        generated_by: String identifier for the runner implementation.

    Returns:
        The path to pins_used.json.
    """

    pins_path = repo_root / "tools" / "deps" / "pins.json"
    if not pins_path.exists():
        raise FileNotFoundError(f"pins.json not found at: {pins_path}")

    pins_obj: Any = json.loads(pins_path.read_text(encoding="utf-8"))
    pins_sha256 = _sha256_file(pins_path)

    payload = {
        "schema": "leanatlas.pins_used",
        "schema_version": "0.1.0",
        "generated_by": generated_by,
        "pins_path": pins_path.relative_to(repo_root).as_posix(),
        "pins_sha256": pins_sha256,
        "pins": pins_obj,
    }

    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / "pins_used.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path
