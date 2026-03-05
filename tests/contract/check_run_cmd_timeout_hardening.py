#!/usr/bin/env python3
"""Contract test: run_cmd timeout paths must converge and clean child processes.

Guards against reviewer tool hangs in isolated workspaces.
"""

from __future__ import annotations

import os
import re
import signal
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.workflow.run_cmd import run_cmd


def _fail(msg: str) -> int:
    print(f"[run-cmd-timeout-hardening][FAIL] {msg}", file=sys.stderr)
    return 2


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Different uid/process namespace; treat as alive for safety.
        return True


def _kill_if_alive(pid: int) -> None:
    if not _is_alive(pid):
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _parse_first_pid(text: str) -> int | None:
    m = re.search(r"\b(\d{2,})\b", text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="run_cmd_timeout_hardening_") as td:
        root = Path(td)
        logs = root / "logs"

        # Case 1: hard timeout must terminate the full process tree.
        child_cmd = (
            "import subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(300)']); "
            "print(p.pid, flush=True); "
            "time.sleep(300)"
        )
        res = run_cmd(
            cmd=[sys.executable, "-c", child_cmd],
            cwd=root,
            log_dir=logs,
            label="hard_timeout_child_tree",
            timeout_s=1,
            capture_text=True,
        )
        if int(res.span.get("exit_code", -1)) != 124 or not bool(res.span.get("timed_out")):
            return _fail("hard-timeout case must produce exit_code=124 and timed_out=true")

        child_pid = _parse_first_pid(res.stdout_text or "")
        if child_pid is None:
            return _fail("failed to parse spawned child pid from stdout evidence")

        # Give the OS a moment to reap the process group.
        time.sleep(0.3)
        if _is_alive(child_pid):
            _kill_if_alive(child_pid)
            return _fail("timeout must not leave orphan child process alive")

        # Case 2: idle timeout must terminate silent/stalled command quickly.
        t0 = time.time()
        res_idle = run_cmd(
            cmd=[sys.executable, "-c", "import time; time.sleep(300)"],
            cwd=root,
            log_dir=logs,
            label="idle_timeout_silent",
            timeout_s=20,
            idle_timeout_s=1,
            capture_text=False,
        )
        dt = time.time() - t0
        if int(res_idle.span.get("exit_code", -1)) != 124 or not bool(res_idle.span.get("timed_out")):
            return _fail("idle-timeout case must produce exit_code=124 and timed_out=true")
        if dt > 8:
            return _fail(f"idle-timeout should converge quickly; observed {dt:.2f}s")

        # Case 3: reconnect-aware dynamic grace should allow recovery after base idle timeout.
        reconnect_cmd = (
            "import time; "
            "print('reconnecting 1/5', flush=True); "
            "time.sleep(2.4); "
            "print('done', flush=True)"
        )
        res_reconnect = run_cmd(
            cmd=[sys.executable, "-c", reconnect_cmd],
            cwd=root,
            log_dir=logs,
            label="idle_timeout_reconnect_grace",
            timeout_s=20,
            idle_timeout_s=1,
            reconnect_grace_s=3,
            reconnect_max_events=5,
            capture_text=True,
        )
        if int(res_reconnect.span.get("exit_code", -1)) != 0:
            return _fail("reconnect grace case should complete successfully instead of timing out")
        if "done" not in (res_reconnect.stdout_text or ""):
            return _fail("reconnect grace case should preserve recovered output")

        # Case 4: run_cmd should enforce a writable default UV cache baseline.
        res_uv_cache_default = run_cmd(
            cmd=[sys.executable, "-c", "import os; print(os.environ.get('UV_CACHE_DIR', ''))"],
            cwd=root,
            log_dir=logs,
            label="uv_cache_default",
            capture_text=True,
        )
        uv_cache_default = (res_uv_cache_default.stdout_text or "").strip()
        expected_default = str((root / ".cache" / "leanatlas" / "uv_cache").resolve())
        if uv_cache_default != expected_default:
            return _fail("run_cmd must inject deterministic UV_CACHE_DIR default under cwd/.cache/leanatlas/uv_cache")
        if not Path(uv_cache_default).exists():
            return _fail("run_cmd default UV_CACHE_DIR path must be created before command execution")

        # Case 5: explicit UV_CACHE_DIR override should be preserved.
        custom_uv_cache = root / "custom_uv_cache"
        res_uv_cache_custom = run_cmd(
            cmd=[sys.executable, "-c", "import os; print(os.environ.get('UV_CACHE_DIR', ''))"],
            cwd=root,
            log_dir=logs,
            label="uv_cache_custom",
            capture_text=True,
            env={"UV_CACHE_DIR": str(custom_uv_cache)},
        )
        if (res_uv_cache_custom.stdout_text or "").strip() != str(custom_uv_cache):
            return _fail("run_cmd must preserve caller-provided UV_CACHE_DIR override")

    print("[run-cmd-timeout-hardening] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
