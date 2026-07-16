"""Conservative server-context resolver for unattended test-pilot execution."""

import os
import re
from urllib.parse import urlparse

import devserver

SCHEMA_VERSION = 1
DEFAULT_READINESS_TIMEOUT = 30
DEFAULT_READINESS_INTERVAL = 0.5

_UNSAFE_ARG = re.compile(r"[;&|<>$`\\\n\r]")
_SAFE_NPM_SCRIPT = re.compile(r"^[A-Za-z0-9:_./-]+$")
# A per-worktree PORT assignment in .env.local (dotenv-style; `export ` prefix and
# surrounding quotes tolerated). The launch cwd's value is the port the dev server
# will ACTUALLY bind when the project's dev command reads .env.local (see #451).
_ENV_PORT_LINE = re.compile(r"^\s*(?:export\s+)?PORT\s*=\s*(.+?)\s*$")


def _park(reason, work_item=None):
    result = {"schemaVersion": SCHEMA_VERSION, "verdict": "park", "reason": reason}
    if work_item:
        result["workItem"] = work_item
    return result


def _base_url(profile):
    value = profile.get("baseUrl") or profile.get("base_url") or "http://localhost:%d" % _port(profile)
    return str(value).rstrip("/") if value else "http://localhost:%d" % _port(profile)


def _port(profile):
    return devserver.resolve_port(profile)


def _port_from_url(url, fallback):
    try:
        parsed = urlparse(url)
    except Exception:
        return fallback
    if parsed.port:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    if parsed.scheme == "http":
        return 80
    return fallback


def _readiness_url(profile, base_url):
    value = profile.get("readinessUrl") or profile.get("readiness_url")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return base_url + "/"


def _coerce_port(raw):
    """Parse a port from a raw string; return an int in (0, 65536) or None.

    Tolerates a surrounding quote pair and an unquoted trailing inline comment
    (dotenv `PORT=3003 # note`) so a real .env.local value is not silently missed."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text[:1] not in ('"', "'"):
        text = text.split("#", 1)[0].strip()  # drop an unquoted inline comment
    text = text.strip('"').strip("'")
    try:
        value = int(text)
    except (TypeError, ValueError):
        return None
    return value if 0 < value < 65536 else None


def _env_local_port(cwd):
    """Read PORT from <cwd>/.env.local (last assignment wins, dotenv-style).

    Returns an int in (0, 65536) or None. Never raises — a missing/unreadable
    file, or no valid PORT line, yields None so the band default stands. This is
    the launch cwd's declared port: what the project's dev server actually binds
    when its dev command resolves PORT from .env.local (#451)."""
    if not cwd or not isinstance(cwd, str):
        return None
    try:
        with open(os.path.join(cwd, ".env.local"), encoding="utf-8") as fh:
            lines = fh.readlines()
    except (OSError, ValueError):
        # OSError: missing/unreadable file. ValueError covers UnicodeDecodeError on a
        # non-UTF-8 file — honor the never-raises contract; the band default stands.
        return None
    resolved = None
    for line in lines:
        if line.lstrip().startswith("#"):
            continue
        match = _ENV_PORT_LINE.match(line)
        if not match:
            continue
        candidate = _coerce_port(match.group(1))
        if candidate is not None:
            resolved = candidate
    return resolved


def _replace_port(url, port):
    """Return `url` with its port component set to `port`, preserving scheme,
    host, and path. Never raises — an unparseable/hostless URL is returned as-is."""
    if not isinstance(url, str) or not url:
        return url
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return url
        return parsed._replace(netloc="%s:%d" % (host, port)).geturl()
    except Exception:
        return url


def _safe_argv(value):
    if not isinstance(value, list):
        return None
    if not value:
        return None
    cleaned = []
    for arg in value:
        if not isinstance(arg, str) or not arg or _UNSAFE_ARG.search(arg):
            return None
        cleaned.append(arg)
    return cleaned


def _package_argv(detection):
    argv = _safe_argv(detection.get("argv"))
    if argv:
        return argv
    script = detection.get("script")
    if isinstance(script, str) and _SAFE_NPM_SCRIPT.match(script):
        return ["npm", "run", script]
    return None


def _managed_context(profile, detection, work_item, base_url, readiness_url, disclosure):
    command = profile.get("devCommand")
    source = "profile"
    if command is None:
        command = profile.get("dev_command")
    if isinstance(command, str) and command.strip():
        return _park("profile devCommand must be an argv array for unattended launch", work_item)
    if command is not None:
        argv = _safe_argv(command)
        if not argv:
            return _park("profile devCommand contains unsafe argv elements", work_item)
    else:
        source = detection.get("source") or "detection"
        argv = _package_argv(detection) if source == "package.json" else _safe_argv(detection.get("argv"))
        if not argv:
            return _park("detected dev-server command has no safe argv metadata", work_item)

    return dict({
        "schemaVersion": SCHEMA_VERSION,
        "verdict": "managed",
        "workItem": work_item,
        "baseUrl": base_url,
        "readinessUrl": readiness_url,
        "command": argv,
        "shell": False,
        "source": source,
        "teardownRequired": True,
    }, **disclosure)


def _resolve_port_disclosure(profile, base_url, readiness_url, cwd):
    """Freeze the port the readiness probe (and injected env) must agree with.

    The launch cwd's .env.local PORT wins over the band default (#451): it is the
    port the project's dev server ACTUALLY binds when its dev command reads
    .env.local. Returns (base_url, readiness_url, disclosure) where disclosure
    carries port / portSource / portDisclosure (+ cwd when known) — all echoed
    into the phase record so a human sees exactly which port was probed and why."""
    port = profile.get("port")
    if not isinstance(port, int) or not 0 < port < 65536:
        port = _port_from_url(base_url, devserver.DEFAULT_PORT)

    env_port = _env_local_port(cwd)
    if env_port is not None and env_port != port:
        port = env_port
        base_url = _replace_port(base_url, env_port)
        readiness_url = _replace_port(readiness_url, env_port)

    if env_port is not None:
        port_source = "%s/.env.local" % cwd
    elif isinstance(profile.get("port"), int) and 0 < profile["port"] < 65536:
        port_source = "profile.port"
    elif profile.get("baseUrl") or profile.get("base_url"):
        port_source = "profile.baseUrl"
    else:
        port_source = "band-default"

    disclosure = {
        "port": port,
        "portSource": port_source,
        "portDisclosure": "probing :%d per %s" % (port, port_source),
    }
    if cwd:
        disclosure["cwd"] = cwd
    return base_url, readiness_url, disclosure


def resolve(profile, detection, work_item, cwd=None):
    """Return canonical server context: ready_external, managed, or park.

    `cwd` is the launch worktree; its .env.local PORT wins over the band default
    so the readiness probe follows the real bind (#451)."""
    if not isinstance(profile, dict):
        return _park("profile must be a JSON object", work_item)
    if not isinstance(detection, dict):
        return _park("detection must be a JSON object", work_item)

    base_url = _base_url(profile)
    readiness_url = _readiness_url(profile, base_url)
    base_url, readiness_url, disclosure = _resolve_port_disclosure(profile, base_url, readiness_url, cwd)

    if profile.get("mayManageServer") is False or profile.get("may_manage_server") is False:
        if detection.get("ready") is True or detection.get("externalReady") is True:
            return dict({
                "schemaVersion": SCHEMA_VERSION,
                "verdict": "ready_external",
                "workItem": work_item,
                "baseUrl": base_url,
                "readinessUrl": readiness_url,
                "teardownRequired": False,
            }, **disclosure)
        return _park("mayManageServer is false and no already-ready external server was confirmed", work_item)

    return _managed_context(profile, detection, work_item, base_url, readiness_url, disclosure)


def launch(context, *, cwd=None, start=None, poll_healthy=None, teardown=None,
           timeout=DEFAULT_READINESS_TIMEOUT, interval=DEFAULT_READINESS_INTERVAL):
    """Start and readiness-check a managed context, tearing down on setup failure."""
    if not isinstance(context, dict):
        return _park("server context must be a JSON object")
    if context.get("verdict") != "managed":
        return dict(context)

    start = start or devserver.start
    poll_healthy = poll_healthy or devserver.poll_healthy
    teardown = teardown or devserver.teardown

    try:
        handle = start(context["command"], context["port"], cwd=cwd, shell=False)
    except Exception as exc:
        return _park("dev server launch failed: %s" % exc, context.get("workItem"))

    try:
        ready = poll_healthy(context["readinessUrl"], timeout=timeout, interval=interval)
    except Exception as exc:
        teardown(handle)
        return _park("dev server readiness probe failed: %s" % exc, context.get("workItem"))
    if not ready:
        teardown(handle)
        return _park("dev server readiness timed out", context.get("workItem"))

    launched = dict(context)
    launched["handle"] = handle
    return launched


def finish(context, outcome, *, teardown=None):
    """Tear down a managed server for any terminal browser/test-pilot outcome."""
    if isinstance(context, dict) and context.get("verdict") == "managed" and context.get("handle"):
        (teardown or devserver.teardown)(context["handle"])
    return outcome
