"""Tests for grandchild_probe's process-state probe on hosts without /proc."""
import os
import subprocess
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import grandchild_probe as gp  # noqa: E402


@pytest.fixture
def no_proc(monkeypatch, private_tmp):
    monkeypatch.setattr(
        gp,
        "_PROC_ROOT",
        os.path.join(private_tmp, "no-proc"),
    )


def _ps_state_direct(pid):
    out = subprocess.run(
        ["ps", "-p", str(pid), "-o", "state="],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return out.stdout.strip()


def _seed_zombie():
    # Caller holds the reference and never polls it, so nothing reaps the child
    # until the caller's own wait(). subprocess only auto-reaps Popen objects
    # that were garbage-collected while running.
    return subprocess.Popen(["/bin/sh", "-c", "exit 0"])


def _await_zombie(proc):
    deadline = time.monotonic() + 10
    last_state = ""
    while time.monotonic() < deadline:
        last_state = _ps_state_direct(proc.pid)
        if last_state.startswith("Z"):
            return
        time.sleep(0.05)
    pytest.fail(f"zombie state never observed; last ps state was {last_state!r}")


def test_seeded_zombie_reads_gone_without_proc(no_proc):
    # axis: a zombie is gone — kill(pid, 0) alone would call it alive
    proc = _seed_zombie()
    try:
        _await_zombie(proc)
        os.kill(proc.pid, 0)
        direct = _ps_state_direct(proc.pid)
        assert gp._observed_process_state(proc.pid) is None, (
            f"pid {proc.pid} ps state {direct!r}"
        )
    finally:
        proc.wait()


def test_live_process_reads_alive_without_proc(no_proc):
    # axis: a non-Z ps state reads alive when /proc is unavailable
    proc = subprocess.Popen(["/bin/sleep", "30"])
    try:
        state = gp._observed_process_state(proc.pid)
        assert state is not None and state.startswith("alive")
    finally:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        proc.wait()


def test_pid_reaped_between_kill_and_ps_reads_gone(no_proc, monkeypatch):
    # axis: ps could not say because the pid vanished after kill(pid, 0) — a second kill settles it gone
    proc = _seed_zombie()
    try:
        _await_zombie(proc)

        def _reap_then_unknown(pid):
            proc.wait()
            return None

        monkeypatch.setattr(gp, "_ps_process_state", _reap_then_unknown)
        state = gp._observed_process_state(proc.pid)
        assert state is None, f"a pid gone by the time ps ran must read gone; got {state!r}"
    finally:
        proc.wait()


def test_unknown_ps_state_reads_alive_even_for_a_zombie(no_proc, monkeypatch):
    # axis: unknown ps state is fail-closed alive, never gone
    proc = _seed_zombie()
    try:
        _await_zombie(proc)
        monkeypatch.setattr(gp, "_ps_process_state", lambda pid: None)
        state = gp._observed_process_state(proc.pid)
        assert state is not None and state.startswith("alive"), (
            f"an unknown ps state must read alive, never gone; got {state!r}"
        )
    finally:
        proc.wait()


def test_ps_process_state_is_none_for_a_reaped_pid():
    # axis: ps non-zero exit for absent pid yields None
    proc = subprocess.Popen(["/bin/sh", "-c", "exit 0"])
    proc.wait()
    assert gp._ps_process_state(proc.pid) is None


def test_ps_process_state_is_none_when_ps_raises(monkeypatch):
    # axis: ps exception yields None

    def _raise_oserror(*args, **kwargs):
        raise OSError("ps unavailable")

    monkeypatch.setattr(gp.subprocess, "run", _raise_oserror)
    assert gp._ps_process_state(os.getpid()) is None
