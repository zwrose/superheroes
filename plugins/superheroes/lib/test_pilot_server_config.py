"""Conservative server-context resolver for unattended test-pilot execution."""

import re
from urllib.parse import urlparse

import devserver

SCHEMA_VERSION = 1
DEFAULT_READINESS_TIMEOUT = 30
DEFAULT_READINESS_INTERVAL = 0.5

_UNSAFE_ARG = re.compile(r"[;&|<>$`\\\n\r]")
_SAFE_NPM_SCRIPT = re.compile(r"^[A-Za-z0-9:_./-]+$")


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


def _managed_context(profile, detection, work_item, base_url, readiness_url, port):
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

    return {
        "schemaVersion": SCHEMA_VERSION,
        "verdict": "managed",
        "workItem": work_item,
        "baseUrl": base_url,
        "readinessUrl": readiness_url,
        "port": port,
        "command": argv,
        "shell": False,
        "source": source,
        "teardownRequired": True,
    }


def resolve(profile, detection, work_item):
    """Return canonical server context: ready_external, managed, or park."""
    if not isinstance(profile, dict):
        return _park("profile must be a JSON object", work_item)
    if not isinstance(detection, dict):
        return _park("detection must be a JSON object", work_item)

    base_url = _base_url(profile)
    port = profile.get("port")
    if not isinstance(port, int) or not 0 < port < 65536:
        port = _port_from_url(base_url, devserver.DEFAULT_PORT)
    readiness_url = _readiness_url(profile, base_url)

    if profile.get("mayManageServer") is False or profile.get("may_manage_server") is False:
        if detection.get("ready") is True or detection.get("externalReady") is True:
            return {
                "schemaVersion": SCHEMA_VERSION,
                "verdict": "ready_external",
                "workItem": work_item,
                "baseUrl": base_url,
                "readinessUrl": readiness_url,
                "port": port,
                "teardownRequired": False,
            }
        return _park("mayManageServer is false and no already-ready external server was confirmed", work_item)

    return _managed_context(profile, detection, work_item, base_url, readiness_url, port)


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
