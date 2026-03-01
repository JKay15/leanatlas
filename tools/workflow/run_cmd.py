#!/usr/bin/env python3
"""Unified command runner with evidence capture.

Why this exists
--------------
Evidence-chain upgrades must not rely on Codex "describing" what it ran.
Instead, the runner captures command execution evidence in a deterministic,
structured form.

This wrapper is intentionally:
- stdlib-only
- non-shell (argv only)
- output-to-files first (so logs can be hashed and audited)

Contracts
---------
- docs/contracts/REPORTING_CONTRACT.md
- docs/contracts/RUNREPORT_CONTRACT.md
- docs/contracts/WORKFLOW_CONTRACT.md
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Union


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sanitize_label(label: str) -> str:
    out = []
    for ch in label:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out).strip("_")
    return s or "cmd"


@dataclass
class RunCmdResult:
    span: Dict[str, Any]
    stdout_text: Optional[str]
    stderr_text: Optional[str]


def run_cmd(
    *,
    cmd: Sequence[str],
    cwd: Union[str, Path],
    log_dir: Path,
    label: str,
    timeout_s: Optional[int] = None,
    env: Optional[Mapping[str, str]] = None,
    capture_text: bool = False,
    max_capture_bytes: int = 2 * 1024 * 1024,
) -> RunCmdResult:
    """Run a command and write stdout/stderr to files.

    Parameters
    ----------
    cmd:
      argv array (no shell).
    cwd:
      working directory.
    log_dir:
      where to write stdout/stderr files.
    label:
      filename prefix (caller-controlled; include stage/attempt index).
    timeout_s:
      optional timeout.
    env:
      optional environment overrides.
    capture_text:
      if True, also return stdout/stderr strings (bounded by max_capture_bytes).
    max_capture_bytes:
      max bytes read back into memory when capture_text=True.

    Returns
    -------
    RunCmdResult(span=..., stdout_text=?, stderr_text=?)

    Span fields (minimum):
      id, cmd, cwd, exit_code, stdout_path, stderr_path, stdout_sha256, stderr_sha256, duration_ms
    """

    if not cmd or not all(isinstance(x, str) and x for x in cmd):
        raise ValueError("cmd must be a non-empty sequence of non-empty strings")

    log_dir.mkdir(parents=True, exist_ok=True)
    safe = _sanitize_label(label)

    stdout_path = log_dir / f"{safe}.stdout.txt"
    stderr_path = log_dir / f"{safe}.stderr.txt"

    t0 = time.time()
    timed_out = False

    with stdout_path.open("w", encoding="utf-8", errors="replace") as out_f, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as err_f:
        try:
            p = subprocess.run(
                list(cmd),
                cwd=str(cwd),
                stdout=out_f,
                stderr=err_f,
                text=True,
                timeout=timeout_s,
                env=dict(env) if env is not None else None,
            )
            rc = int(p.returncode)
        except subprocess.TimeoutExpired:
            timed_out = True
            rc = 124

    dt_ms = int(round((time.time() - t0) * 1000.0))

    out_sha = _sha256_file(stdout_path)
    err_sha = _sha256_file(stderr_path)

    # Make paths portable: record relative to log_dir.parent when possible.
    base = log_dir.parent
    try:
        stdout_rel = stdout_path.relative_to(base).as_posix()
    except Exception:
        stdout_rel = stdout_path.as_posix()
    try:
        stderr_rel = stderr_path.relative_to(base).as_posix()
    except Exception:
        stderr_rel = stderr_path.as_posix()

    span: Dict[str, Any] = {
        "id": safe,
        "cmd": list(cmd),
        "cwd": str(Path(cwd).resolve()),
        "exit_code": rc,
        "stdout_path": stdout_rel,
        "stderr_path": stderr_rel,
        "stdout_sha256": out_sha,
        "stderr_sha256": err_sha,
        "duration_ms": dt_ms,
    }
    if timed_out:
        span["timed_out"] = True

    if not capture_text:
        return RunCmdResult(span=span, stdout_text=None, stderr_text=None)

    # Bounded read-back.
    out_bytes = stdout_path.read_bytes()[:max_capture_bytes]
    err_bytes = stderr_path.read_bytes()[:max_capture_bytes]
    stdout_text = out_bytes.decode("utf-8", errors="replace")
    stderr_text = err_bytes.decode("utf-8", errors="replace")
    return RunCmdResult(span=span, stdout_text=stdout_text, stderr_text=stderr_text)
