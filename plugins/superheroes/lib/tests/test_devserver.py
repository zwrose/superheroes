import socket
import subprocess
import sys

import pytest

import devserver


def test_resolve_port_prefers_profile():
    assert devserver.resolve_port({"port": 4321}) == 4321


def test_resolve_port_defaults():
    assert devserver.resolve_port(None) == devserver.DEFAULT_PORT
    assert devserver.resolve_port({}) == devserver.DEFAULT_PORT


def test_health_url_built_from_port():
    assert devserver.health_url(3000) == "http://localhost:3000/"
    assert devserver.health_url(3000, path="/health") == "http://localhost:3000/health"


def test_port_in_use_detects_a_bound_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
    except PermissionError:
        s.close()
        pytest.skip("sandbox does not permit local socket bind")
    s.listen(1)
    port = s.getsockname()[1]
    try:
        assert devserver.port_in_use(port) is True
    finally:
        s.close()
    # a (now-)free port reads as not-in-use
    assert devserver.port_in_use(port) is False


def test_start_raises_port_in_use_error():
    # Pin that start() refuses loudly (PortInUseError) when the port is already bound,
    # before ever reaching Popen. Mirror test_port_in_use_detects_a_bound_socket's
    # socket setup so no real server is spawned.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
    except PermissionError:
        s.close()
        pytest.skip("sandbox does not permit local socket bind")
    s.listen(1)
    port = s.getsockname()[1]
    try:
        with pytest.raises(devserver.PortInUseError):
            devserver.start("true", port)
    finally:
        s.close()


def test_start_accepts_argv_command_with_shell_false(monkeypatch):
    calls = []
    monkeypatch.setattr(devserver, "port_in_use", lambda port: False)

    class Proc:
        pid = 123

    def fake_popen(command, shell, cwd, env, start_new_session):
        calls.append((command, shell, cwd, env["PORT"], start_new_session))
        return Proc()

    monkeypatch.setattr(devserver.subprocess, "Popen", fake_popen)

    handle = devserver.start(["npm", "run", "dev"], 5173, cwd="/tmp/app", shell=False)

    assert handle["command"] == ["npm", "run", "dev"]
    assert calls == [(["npm", "run", "dev"], False, "/tmp/app", "5173", True)]


def test_teardown_kills_a_live_pid():
    # Spawn the victim in ITS OWN session, exactly like production devserver.start,
    # so teardown's os.killpg targets the child's group — NOT the pytest runner's.
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                            start_new_session=True)
    handle = {"pid": proc.pid, "port": 3000, "command": "sleep"}
    assert proc.poll() is None              # alive before teardown
    devserver.teardown(handle)
    # proc.wait() is the deterministic "it died" signal AND reaps the child (so we
    # don't assert is_running on an unreaped zombie, which os.kill(pid,0) reports alive).
    assert proc.wait(timeout=5) is not None  # exited (a signal yields a negative code)


def test_teardown_of_dead_pid_is_noop():
    handle = {"pid": 2_147_483_000, "port": 3000, "command": "x"}  # implausible pid
    devserver.teardown(handle)  # must not raise
