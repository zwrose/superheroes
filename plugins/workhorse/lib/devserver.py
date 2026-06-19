"""Managed dev-server lifecycle for Workhorse: resolve the port, start the
process (background), and tear it down on any terminal state / GATE / error so no
zombie outlives the run. One server serves both ⑤ (test-pilot) and the ⑨
spot-check. The start+health-poll path is integration-exercised; the bookkeeping
(port resolve, PID liveness, teardown) is unit-tested here.
"""
import json
import os
import signal
import socket
import subprocess
import time
import urllib.request
import control_plane
import hostinfo
import readout

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


def _pgid(pid):
    try:
        return os.getpgid(int(pid))
    except (OSError, ValueError, TypeError):
        return None


def poll_healthy(url, *, timeout, interval, opener=None):
    """Bounded health poll. Returns True on the first 2xx-4xx, else False at the
    deadline (design §8.1 — never hangs)."""
    opener = opener or (lambda u: urllib.request.urlopen(u, timeout=2))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = opener(url)
            code = getattr(r, "status", None) or (r.getcode() if hasattr(r, "getcode") else None)
            if code is not None and 200 <= code < 500:
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def write_sidecar(sidecar_path, handle, command, *, root=None):
    """Persist the managed-server identity so a later session can reclaim an orphan.
    `command` is scrubbed fail-closed (a durable free-text field, design §8.1/§4.2)."""
    cmd, _ok = readout.scrub(str(command), root=root)
    control_plane.atomic_write(sidecar_path, json.dumps({
        "pid": handle.get("pid"), "pgid": _pgid(handle.get("pid")),
        "port": handle.get("port"), "command": cmd, "bootId": hostinfo.boot_id()}))


def reclaim(sidecar_path, port, command, *, root=None):
    """Adopt a teardown handle for an orphaned managed server iff it corroborates:
    port AND scrubbed-command AND bootId all match (degrade to pid+port+command when
    bootId is unobtainable on either side — the named residual). None => unrecognized
    (caller GATEs); never adopt on bare pid liveness (a recycled PID would mis-kill)."""
    try:
        with open(sidecar_path, encoding="utf-8") as fh:
            sc = json.load(fh)
    except (OSError, ValueError):
        return None
    if sc.get("port") != port:
        return None
    cmd, _ok = readout.scrub(str(command), root=root)
    if sc.get("command") != cmd:
        return None
    rec_boot, cur_boot = sc.get("bootId"), hostinfo.boot_id()
    if rec_boot is not None and cur_boot is not None and rec_boot != cur_boot:
        return None   # rebooted -> recorded pgid is meaningless -> do not adopt
    return {"pid": sc.get("pid"), "pgid": sc.get("pgid"), "port": port,
            "command": sc.get("command")}
