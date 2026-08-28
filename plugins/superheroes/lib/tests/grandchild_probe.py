"""Shared readiness/retry orchestration for pilot process-group teardown tests."""
import os
import signal
import subprocess
import time
from collections import namedtuple
from contextlib import contextmanager
from unittest import mock

import pytest

# Escalating budgets for the setup race. p50 spawn latency is ~0.148 s, so the first
# rung still covers the common case; longer rungs are paid only when the host cannot
# start /bin/sh inside the previous budget — a machine that cannot do it in 45 s has a
# problem this test should report loudly as a setup race, not hide.
ATTEMPT_TIMEOUTS = (1, 2, 5, 15, 45)

GrandchildProbe = namedtuple(
    "GrandchildProbe", ("pid", "result", "elapsed", "timeout_used", "pgid")
)
ProbeTarget = namedtuple("ProbeTarget", ("script_path", "pid_path"))


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


def _process_group_alive(pgid):
    """Zombie-aware process-group liveness; mirrors engine_dispatch._process_group_alive."""
    if pgid is None:
        return False
    try:
        pgid = int(pgid)
    except (TypeError, ValueError):
        return False
    if pgid == 0:
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    except Exception:
        return True
    try:
        out = subprocess.run(
            ["ps", "-g", str(pgid), "-o", "state="],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode != 0:
            return True
        states = (out.stdout or "").strip().split()
        if not states:
            return True
        for state in states:
            if state and not state.startswith(("Z", "z")):
                return True
        return False
    except Exception:
        return True


def _wait_for_pgid_gone(pgid, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_group_alive(pgid):
            return True
        time.sleep(0.05)
    return False


def _best_effort_kill_pid(pid, expected_pgid=None):
    if expected_pgid is not None:
        try:
            if os.getpgid(pid) != expected_pgid:
                return
        except (ProcessLookupError, PermissionError):
            return
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, ValueError):
        pass


@contextmanager
def cleanup_grandchild_on_exit(pid, expected_pgid):
    """Best-effort SIGKILL of ``pid`` on every exit path; never masks exceptions."""
    try:
        yield
    finally:
        _best_effort_kill_pid(pid, expected_pgid)


def _compact_result(result):
    if not isinstance(result, dict):
        return repr(result)
    parts = []
    for key in ("outcome", "timedOut", "exit", "reason"):
        if key in result:
            parts.append(f"{key}={result[key]!r}")
    if parts:
        return "{" + ", ".join(parts) + "}"
    return repr(result)


def _format_attempt_diagnostics_table(attempt_records):
    lines = ["Per-attempt diagnostics:"]
    for record in attempt_records:
        lines.append(
            "  attempt {index}: budget={budget}s elapsed={elapsed:.2f}s "
            "pgid={pgid!r} leader_pgid={leader_pgid!r} group_gone={group_gone} "
            "result={result}".format(
                **record
            )
        )
    return "\n".join(lines)


def probe_grandchild(*, tmp_dir, script_body, run, attempt_timeouts=ATTEMPT_TIMEOUTS):
    """Drive `run(target, timeout_seconds)` until the fixture records a grandchild pid.

    ``run`` receives a ``ProbeTarget`` with ``script_path`` (the written fixture) and
    ``pid_path`` (where the grandchild should record its pid). ``script_body(pid_path)``
    is supplied by the caller and returns that attempt's fixture text.
    Returns GrandchildProbe(pid, result, elapsed, timeout_used, pgid).
    """
    budgets_tried = []
    attempt_records = []
    for attempt_index, budget in enumerate(attempt_timeouts):
        budgets_tried.append(budget)
        pid_path = os.path.join(tmp_dir, f"grandchild-{attempt_index}.pid")
        script_path = os.path.join(tmp_dir, f"fixture-{attempt_index}.sh")
        target = ProbeTarget(script_path=script_path, pid_path=pid_path)
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
            result = run(target, budget)
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

        try:
            leader_pgid = os.getpgid(pgid)
        except (ProcessLookupError, PermissionError):
            leader_pgid = None

        group_gone = _wait_for_pgid_gone(pgid, timeout=10)
        attempt_records.append(
            {
                "index": attempt_index,
                "budget": budget,
                "elapsed": elapsed,
                "pgid": pgid,
                "leader_pgid": leader_pgid,
                "group_gone": group_gone,
                "result": _compact_result(result),
            }
        )

        if leader_pgid is not None and leader_pgid != pgid:
            diagnostics = _format_attempt_diagnostics_table(attempt_records)
            pytest.fail(
                "captured leader was not its own group leader — "
                "`start_new_session` containment did not hold "
                f"(pid={pgid}, leader_pgid={leader_pgid}, budget={budget}s, "
                f"attempt={attempt_index})\n"
                f"{diagnostics}"
            )

        if not group_gone:
            diagnostics = _format_attempt_diagnostics_table(attempt_records)
            pytest.fail(
                "process group still alive after miss — teardown evidence, not a setup race "
                f"(pgid={pgid}, budget={budget}s, attempt={attempt_index})\n"
                f"{diagnostics}"
            )

        missed_pid = _try_read_grandchild_pid(pid_path)
        if missed_pid is not None:
            state = _observed_process_state(missed_pid)
            _best_effort_kill_pid(missed_pid, pgid)
            if state is not None:
                diagnostics = _format_attempt_diagnostics_table(attempt_records)
                pytest.fail(
                    f"grandchild pid {missed_pid} recorded after its process group "
                    f"(pgid={pgid}) was proven gone and is still alive ({state}) — "
                    "survivor evidence, not a setup race\n" + diagnostics
                )

    budget_list = ",".join(str(b) for b in budgets_tried)
    diagnostics = _format_attempt_diagnostics_table(attempt_records)
    pytest.fail(
        f"grandchild never recorded its pid in any attempt (budgets {budget_list}s); "
        "every attempt's process group was proven gone, so this is the setup race, "
        f"not a surviving grandchild\n{diagnostics}"
    )
