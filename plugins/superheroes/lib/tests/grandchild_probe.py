"""Shared readiness/retry orchestration for pilot process-group teardown tests."""
import os
import signal
import subprocess
import time
from collections import namedtuple
from unittest import mock

import pytest

ATTEMPT_TIMEOUTS = (1, 2, 4, 8)  # seconds; escalating budgets for the setup race

GrandchildProbe = namedtuple(
    "GrandchildProbe", ("pid", "result", "elapsed", "timeout_used", "pgid")
)


def _write_executable(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(path, 0o755)


def _try_read_grandchild_pid(pid_file):
    if not os.path.isfile(pid_file):
        return None
    with open(pid_file, encoding="utf-8") as handle:
        raw = handle.read().strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _read_grandchild_pid(pid_file):
    if not os.path.isfile(pid_file):
        pytest.fail(f"grandchild pid file missing: {pid_file!r}")
    with open(pid_file, encoding="utf-8") as handle:
        raw = handle.read().strip()
    if not raw:
        pytest.fail(f"grandchild pid file empty: {pid_file!r}")
    try:
        return int(raw)
    except ValueError:
        pytest.fail(
            f"grandchild pid file not an integer: {pid_file!r} contents {raw!r}"
        )


def _observed_process_state(pid):
    """Return a description of ``pid`` if still present, else ``None`` when gone."""
    proc_stat = os.path.join("/proc", str(pid), "stat")
    if os.path.isfile(proc_stat):
        try:
            with open(proc_stat, encoding="utf-8") as handle:
                content = handle.read()
        except OSError as exc:
            return f"/proc/{pid}/stat unreadable: {exc}"
        close_paren = content.rfind(")")
        if close_paren < 0 or close_paren + 2 >= len(content):
            return f"/proc/{pid}/stat unparseable: {content!r}"
        state = content[close_paren + 2]
        if state == "Z":
            return None
        state_names = {
            "R": "running",
            "S": "sleeping",
            "D": "disk sleep",
            "T": "stopped",
            "t": "tracing stop",
            "X": "dead",
            "x": "dead",
            "Z": "zombie",
            "P": "parked",
            "I": "idle",
        }
        label = state_names.get(state, "unknown")
        return f"/proc state {state!r} ({label})"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        return "alive (kill(pid, 0) raised PermissionError; /proc unavailable)"
    return "alive (kill(pid, 0) succeeded; /proc unavailable)"


def _wait_for_process_gone(pid, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _observed_process_state(pid) is None:
            return True
        time.sleep(0.05)
    return False


def _wait_for_pgid_gone(pgid, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def _best_effort_kill_pid(pid):
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, ValueError):
        pass


def probe_grandchild(*, tmp_dir, script_body, run, attempt_timeouts=ATTEMPT_TIMEOUTS):
    """Drive `run(target, timeout_seconds)` until the fixture records a grandchild pid.

    `script_body(pid_file_path) -> str` is supplied BY THE CALLER and returns that attempt's
    fixture text, so each test keeps its own fixture shape verbatim and only the pid-file path
    varies per attempt.
    Returns GrandchildProbe(pid, result, elapsed, timeout_used, pgid).
    """
    budgets_tried = []
    for attempt_index, budget in enumerate(attempt_timeouts):
        budgets_tried.append(budget)
        pid_path = os.path.join(tmp_dir, f"grandchild-{attempt_index}.pid")
        script_path = os.path.join(tmp_dir, f"fixture-{attempt_index}.sh")
        _write_executable(script_path, script_body(pid_path))

        captured_pgid = [None]
        real_popen = subprocess.Popen

        def _recording_popen(*args, **kwargs):
            proc = real_popen(*args, **kwargs)
            if captured_pgid[0] is None:
                captured_pgid[0] = proc.pid
            return proc

        result = None
        elapsed = None
        popen_patcher = mock.patch.object(subprocess, "Popen", _recording_popen)
        try:
            popen_patcher.start()
            started = time.monotonic()
            result = run(script_path, budget)
            elapsed = time.monotonic() - started
        finally:
            popen_patcher.stop()

        pgid = captured_pgid[0]
        pid = _try_read_grandchild_pid(pid_path)
        if pid is not None:
            return GrandchildProbe(
                pid=pid,
                result=result,
                elapsed=elapsed,
                timeout_used=budget,
                pgid=pgid,
            )

        if pgid is None:
            pytest.fail(
                "no process group captured for grandchild probe attempt "
                f"{attempt_index} (budget {budget}s); nothing spawned"
            )

        if not _wait_for_pgid_gone(pgid, timeout=10):
            pytest.fail(
                "process group still alive after miss — teardown evidence, not a setup race "
                f"(pgid={pgid}, budget={budget}s, attempt={attempt_index})"
            )

        missed_pid = _try_read_grandchild_pid(pid_path)
        if missed_pid is not None:
            _best_effort_kill_pid(missed_pid)

    budget_list = ",".join(str(b) for b in budgets_tried)
    pytest.fail(
        f"grandchild never recorded its pid in any attempt (budgets {budget_list}s); "
        "every attempt's process group was proven gone, so this is the setup race, "
        "not a surviving grandchild"
    )
