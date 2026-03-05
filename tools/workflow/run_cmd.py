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
import os
import re
import signal
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


def _as_positive_timeout(value: Optional[int]) -> Optional[float]:
    if value is None:
        return None
    if value <= 0:
        return None
    return float(value)


def _as_nonnegative_int(value: int) -> int:
    return max(0, int(value))


def _prepare_env(cwd: Union[str, Path], env: Optional[Mapping[str, str]]) -> Dict[str, str]:
    merged = dict(os.environ)
    if env is not None:
        merged.update({str(k): str(v) for k, v in env.items()})

    uv_cache_dir = str(merged.get("UV_CACHE_DIR") or "").strip()
    if uv_cache_dir:
        try:
            Path(uv_cache_dir).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return merged

    cache_dir = Path(cwd).resolve() / ".cache" / "leanatlas" / "uv_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    merged["UV_CACHE_DIR"] = str(cache_dir)
    return merged


def _terminate_process_tree(proc: subprocess.Popen[Any], *, grace_s: float = 0.5) -> None:
    """Best-effort termination for proc + children in the same process group."""
    if proc.poll() is not None:
        return

    pgid: Optional[int]
    try:
        pgid = os.getpgid(proc.pid)
    except Exception:
        pgid = None

    if pgid is not None:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except Exception:
            pass
    else:
        try:
            proc.terminate()
        except Exception:
            pass

    deadline = time.monotonic() + max(0.05, grace_s)
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.05)

    if pgid is not None:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except Exception:
            pass
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=1.0)
    except Exception:
        pass


def run_cmd(
    *,
    cmd: Sequence[str],
    cwd: Union[str, Path],
    log_dir: Path,
    label: str,
    timeout_s: Optional[int] = None,
    idle_timeout_s: Optional[int] = None,
    reconnect_grace_s: Optional[int] = None,
    reconnect_max_events: int = 0,
    reconnect_pattern: str = r"\breconnect(?:ing|ed|ion)?\b",
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
    idle_timeout_s:
      optional inactivity timeout in seconds (stdout/stderr unchanged).
    reconnect_grace_s:
      optional extra grace seconds granted when reconnect markers appear in output.
    reconnect_max_events:
      max reconnect-marker events that can grant grace.
    reconnect_pattern:
      regex pattern used to detect reconnect markers in incremental output.
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
    hard_timeout_s = _as_positive_timeout(timeout_s)
    idle_timeout_val_s = _as_positive_timeout(idle_timeout_s)
    reconnect_grace_val_s = _as_positive_timeout(reconnect_grace_s)
    reconnect_max_events_val = _as_nonnegative_int(reconnect_max_events)
    reconnect_re: Optional[re.Pattern[str]] = None
    if reconnect_grace_val_s is not None and reconnect_max_events_val > 0:
        reconnect_re = re.compile(reconnect_pattern, flags=re.IGNORECASE)
    timed_out = False
    cmd_env = _prepare_env(cwd, env)

    with stdout_path.open("w", encoding="utf-8", errors="replace") as out_f, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as err_f:
        p = subprocess.Popen(
            list(cmd),
            cwd=str(cwd),
            stdout=out_f,
            stderr=err_f,
            text=True,
            env=cmd_env,
            start_new_session=True,
        )
        start_mono = time.monotonic()
        hard_deadline_mono = (start_mono + hard_timeout_s) if hard_timeout_s is not None else None
        last_activity_mono = start_mono
        idle_extend_until_mono = start_mono
        last_stdout_size = 0
        last_stderr_size = 0
        scan_stdout_pos = 0
        scan_stderr_pos = 0
        reconnect_events_applied = 0
        rc: Optional[int] = None

        while True:
            polled = p.poll()
            if polled is not None:
                rc = int(polled)
                break

            now = time.monotonic()
            should_timeout = False
            if hard_deadline_mono is not None and now >= hard_deadline_mono:
                should_timeout = True
            elif idle_timeout_val_s is not None:
                stdout_size = stdout_path.stat().st_size
                stderr_size = stderr_path.stat().st_size
                if stdout_size != last_stdout_size or stderr_size != last_stderr_size:
                    last_stdout_size = stdout_size
                    last_stderr_size = stderr_size
                    last_activity_mono = now
                    if reconnect_re is not None:
                        if stdout_size < scan_stdout_pos:
                            scan_stdout_pos = 0
                        if stderr_size < scan_stderr_pos:
                            scan_stderr_pos = 0

                        reconnect_hits = 0
                        if stdout_size > scan_stdout_pos:
                            read_start = scan_stdout_pos
                            if (stdout_size - scan_stdout_pos) > 64 * 1024:
                                read_start = stdout_size - 64 * 1024
                            with stdout_path.open("rb") as sf:
                                sf.seek(read_start)
                                chunk = sf.read(stdout_size - read_start)
                            scan_stdout_pos = stdout_size
                            reconnect_hits += len(reconnect_re.findall(chunk.decode("utf-8", errors="replace")))
                        if stderr_size > scan_stderr_pos:
                            read_start = scan_stderr_pos
                            if (stderr_size - scan_stderr_pos) > 64 * 1024:
                                read_start = stderr_size - 64 * 1024
                            with stderr_path.open("rb") as ef:
                                ef.seek(read_start)
                                chunk = ef.read(stderr_size - read_start)
                            scan_stderr_pos = stderr_size
                            reconnect_hits += len(reconnect_re.findall(chunk.decode("utf-8", errors="replace")))

                        while reconnect_hits > 0 and reconnect_events_applied < reconnect_max_events_val:
                            reconnect_hits -= 1
                            reconnect_events_applied += 1
                            if hard_deadline_mono is not None and reconnect_grace_val_s is not None:
                                hard_deadline_mono += reconnect_grace_val_s
                            if reconnect_grace_val_s is not None:
                                idle_extend_until_mono = max(idle_extend_until_mono, now + reconnect_grace_val_s)
                elif (now - last_activity_mono) >= idle_timeout_val_s:
                    if now >= idle_extend_until_mono:
                        should_timeout = True

            if should_timeout:
                timed_out = True
                _terminate_process_tree(p)
                rc = 124
                break

            time.sleep(0.05)

        if rc is None:
            rc = int(p.wait())

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
    uv_cache_dir = str(cmd_env.get("UV_CACHE_DIR") or "")
    if uv_cache_dir:
        span["uv_cache_dir"] = uv_cache_dir

    if not capture_text:
        return RunCmdResult(span=span, stdout_text=None, stderr_text=None)

    # Bounded read-back.
    out_bytes = stdout_path.read_bytes()[:max_capture_bytes]
    err_bytes = stderr_path.read_bytes()[:max_capture_bytes]
    stdout_text = out_bytes.decode("utf-8", errors="replace")
    stderr_text = err_bytes.decode("utf-8", errors="replace")
    return RunCmdResult(span=span, stdout_text=stdout_text, stderr_text=stderr_text)
