"""Managed dev-server lifecycle for Workhorse: resolve the port, start the
process (background), and tear it down on any terminal state / GATE / error so no
zombie outlives the run. One server serves both ⑤ (test-pilot) and the ⑨
spot-check. The start+health-poll path is integration-exercised; the bookkeeping
(port resolve, PID liveness, teardown) is unit-tested here.
"""
import os
import signal
import socket
import subprocess
import time

DEFAULT_PORT = 3000


def resolve_port(profile):
    """Port from the profile, else DEFAULT_PORT. Never raises."""
    if isinstance(profile, dict):
        p = profile.get("port")
        if isinstance(p, int) and 0 < p < 65536:
            return p
    return DEFAULT_PORT


def health_url(port, path="/"):
    if not path.startswith("/"):
        path = "/" + path
    return "http://localhost:%d%s" % (port, path)


def port_in_use(port, host="127.0.0.1"):
    """True iff something is already listening on `port` (a likely orphan from a
    prior hard-killed run). Never raises — an unexpected error reads as in-use
    (fail-safe: refuse to collide rather than risk double-binding)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0
    except OSError:
        return True
    finally:
        s.close()


def is_running(pid):
    """True iff a process with `pid` is alive. signal 0 == liveness probe."""
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


class PortInUseError(RuntimeError):
    """Raised by start() when the target port is already bound — surfaced loudly
    (design §3④), so the orchestrator GATEs with 'a server is already on :PORT
    (possible orphan from a prior run)' instead of silently colliding."""


def start(command, port, cwd=None, env=None):
    """Launch `command` in the background; return a handle dict. Refuses LOUDLY if
    the port is already bound (design §3④: reuse-or-fail, never silent-collide).
    The caller health-polls health_url(port) and MUST teardown(handle) on every
    terminal/GATE/error path. (Durable cross-session orphan reclaim — finding a
    server an EARLIER killed session left behind — is the resilience slice; here we
    fail loudly so the owner sees it rather than wedging on a stale server.)"""
    if port_in_use(port):
        raise PortInUseError(port)
    proc = subprocess.Popen(command, shell=True, cwd=cwd,
                            env={**os.environ, **(env or {}), "PORT": str(port)},
                            start_new_session=True)
    return {"pid": proc.pid, "port": port, "command": command, "_proc": proc}


def teardown(handle):
    """Kill the managed process (and its session group) if still alive. Idempotent
    and never raises — safe to call on any terminal/GATE/error path."""
    if not isinstance(handle, dict):
        return
    pid = handle.get("pid")
    if not isinstance(pid, int):
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not is_running(pid):
            return
        try:
            os.killpg(os.getpgid(pid), sig)
        except (OSError, ProcessLookupError):
            try:
                os.kill(pid, sig)
            except (OSError, ProcessLookupError):
                return
        time.sleep(0.2)
