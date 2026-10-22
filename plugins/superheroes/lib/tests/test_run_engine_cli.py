"""Tests for engine_adapter.run_engine_cli (#777): no engine CLI inherits the parent's stdin.

The helper's seven edges (E1-E7) are unit-tested against a recording fake `run`; each of the four
callers that route through it is checked to hand its `run` no inheritable stdin; and one real spawn
proves a child whose parent holds an open, never-written stdin pipe still reads EOF at once.
"""
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_relay  # noqa: E402
import engine_adapter  # noqa: E402
import engine_authz  # noqa: E402
import engine_detect  # noqa: E402
import preflight_probe  # noqa: E402


class _Recorder:
    """A fake `run` that records every call's argv and kwargs and returns a fixed result."""

    def __init__(self, result=None):
        self.calls = []
        self.result = result if result is not None else SimpleNamespace(
            returncode=0, stdout="", stderr="")

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return self.result


def _no_inheritable_stdin(kwargs):
    """True when the call either pins stdin to DEVNULL or hands `input` a non-None value."""
    if "stdin" in kwargs:
        return kwargs["stdin"] is subprocess.DEVNULL and "input" not in kwargs
    return kwargs.get("input") is not None


# --- helper edges E1-E7 -------------------------------------------------------------------------

def test_e1_neither_stdin_nor_input_sets_devnull():
    fake = _Recorder()
    engine_adapter.run_engine_cli(["codex", "login", "status"], run=fake, capture_output=True)
    argv, kwargs = fake.calls[0]
    assert argv == ["codex", "login", "status"]
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["capture_output"] is True


@pytest.mark.parametrize("value", ["", "some text"])
def test_e2_input_given_passes_through_with_no_stdin_key(value):
    fake = _Recorder()
    engine_adapter.run_engine_cli(["codex"], run=fake, input=value)
    _argv, kwargs = fake.calls[0]
    assert kwargs["input"] == value
    assert "stdin" not in kwargs


def test_e3_devnull_stdin_passes_through_unchanged():
    fake = _Recorder()
    engine_adapter.run_engine_cli(["codex"], run=fake, stdin=subprocess.DEVNULL, timeout=5)
    _argv, kwargs = fake.calls[0]
    assert kwargs == {"stdin": subprocess.DEVNULL, "timeout": 5}


@pytest.mark.parametrize("value", [None, sys.stdin, 0, subprocess.PIPE],
                         ids=["none", "sys-stdin", "fd-0", "pipe"])
def test_e4_any_other_stdin_raises_before_run(value):
    fake = _Recorder()
    with pytest.raises(ValueError):
        engine_adapter.run_engine_cli(["codex"], run=fake, stdin=value)
    assert fake.calls == []


def test_e4_file_object_stdin_raises_before_run(tmp_path):
    fake = _Recorder()
    with open(tmp_path / "in.txt", "w", encoding="utf-8") as fh:
        with pytest.raises(ValueError):
            engine_adapter.run_engine_cli(["codex"], run=fake, stdin=fh)
    assert fake.calls == []


def test_e5_input_none_raises_before_run():
    fake = _Recorder()
    with pytest.raises(ValueError):
        engine_adapter.run_engine_cli(["codex"], run=fake, input=None)
    assert fake.calls == []


@pytest.mark.parametrize("stdin", [subprocess.DEVNULL, subprocess.PIPE, None])
def test_e6_both_stdin_and_input_raise_before_run(stdin):
    fake = _Recorder()
    with pytest.raises(ValueError):
        engine_adapter.run_engine_cli(["codex"], run=fake, stdin=stdin, input="x")
    assert fake.calls == []


def test_e7_run_none_uses_subprocess_run_and_returns_its_result(monkeypatch):
    seen = {}
    sentinel = object()

    def fake_subprocess_run(argv, **kwargs):
        seen["argv"], seen["kwargs"] = argv, kwargs
        return sentinel

    monkeypatch.setattr(engine_adapter.subprocess, "run", fake_subprocess_run)
    assert engine_adapter.run_engine_cli(("codex", "x")) is sentinel
    assert seen["argv"] == ["codex", "x"]
    assert seen["kwargs"]["stdin"] is subprocess.DEVNULL


def test_e7_returns_whatever_run_returns():
    sentinel = object()
    assert engine_adapter.run_engine_cli(["codex"], run=_Recorder(sentinel)) is sentinel


# --- the four callers ---------------------------------------------------------------------------

def test_site_engine_authz_carries_no_inheritable_stdin(tmp_path):
    fake = _Recorder()
    assert engine_authz.implementation_dispatch_allowed(str(tmp_path), "cursor", run=fake) is True
    assert len(fake.calls) == 1
    assert _no_inheritable_stdin(fake.calls[0][1])


def test_site_engine_detect_carries_no_inheritable_stdin(monkeypatch):
    monkeypatch.setattr(engine_detect.shutil, "which", lambda name: "/usr/bin/" + name)
    fake = _Recorder()
    engine_detect.probe(".", run=fake)
    assert len(fake.calls) == 2
    for _argv, kwargs in fake.calls:
        assert _no_inheritable_stdin(kwargs)


def test_site_cloud_relay_call_carries_no_inheritable_stdin():
    fake = _Recorder()
    code, _out, _err = cloud_relay._call(fake, ["claude", "agents", "--json"], {}, 5)
    assert code == 0
    assert len(fake.calls) == 1
    assert _no_inheritable_stdin(fake.calls[0][1])


def test_site_preflight_probe_carries_no_inheritable_stdin(monkeypatch):
    # probe_command already passed `input=""`, so the kwargs alone cannot tell the helper from a raw
    # `run(...)`: a spy on the helper proves the call is routed through it.
    routed = []
    real_helper = engine_adapter.run_engine_cli

    def spy(argv, run=None, **kwargs):
        routed.append(list(argv))
        return real_helper(argv, run=run, **kwargs)

    monkeypatch.setattr(engine_adapter, "run_engine_cli", spy)
    fake = _Recorder()
    result = preflight_probe.probe_command("t", ["t"], run=fake)
    assert result["ok"] is True
    assert routed == [["t"]]
    assert len(fake.calls) == 1
    assert _no_inheritable_stdin(fake.calls[0][1])


# --- real spawn ---------------------------------------------------------------------------------

_WRAPPER = """\
import subprocess, sys
sys.path.insert(0, %r)
import engine_adapter
proc = engine_adapter.run_engine_cli(
    [sys.executable, "-c", "import sys; sys.stdin.read()"], timeout=20)
sys.exit(proc.returncode)
""" % _LIB


def test_real_spawn_child_reads_eof_while_parent_holds_stdin_pipe_open():
    wrapper = subprocess.Popen([sys.executable, "-c", _WRAPPER], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        # The pipe is never written to or closed: an inheriting child would block in read().
        assert wrapper.wait(timeout=15) == 0
    finally:
        if wrapper.poll() is None:
            wrapper.kill()
            wrapper.wait()
        wrapper.stdin.close()
        wrapper.stdout.close()
        wrapper.stderr.close()
