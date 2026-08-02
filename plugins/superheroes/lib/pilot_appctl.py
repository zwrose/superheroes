"""Pilot per-slot app instance control — stand-up, readiness, durable record, stop.

Owns one slot's app process: resolve invocation, fence endpoints, write the instance
record before spawn, poll readiness with attribution, and stop with observed evidence.

Known residual (single-user local threat model): a process-group leader whose recorded
pid was reused by a different process running the same ``argv[0]`` would corroborate
via ``ps``. Same posture as ``pilot_lifecycle``'s check-then-use slot-directory guard.
"""
import json
import math
import os
import re
import secrets
import signal
import socket
import stat
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

import pilot_contract
import pilot_journal
import pilot_lifecycle
import pilot_slot
import store_core

SCHEMA = 1

STATE_STARTING = "starting"
STATE_READY = "ready"
STATE_STOPPED = "stopped"
STATE_INDETERMINATE = "indeterminate"

INSTANCE_STATES = frozenset({STATE_STARTING, STATE_READY, STATE_STOPPED, STATE_INDETERMINATE})
LAUNCHABLE_SLOT_STATES = frozenset({
    pilot_lifecycle.STATE_PROVISIONING,
    pilot_lifecycle.STATE_PROVISIONED,
})
ACTIVE_INSTANCE_STATES = frozenset({STATE_STARTING, STATE_READY, STATE_INDETERMINATE})

READINESS_ATTRIBUTION_NONCE = "nonce"
READINESS_ATTRIBUTION_UNATTRIBUTED = "unattributed"
READINESS_ATTRIBUTIONS = frozenset({
    READINESS_ATTRIBUTION_NONCE,
    READINESS_ATTRIBUTION_UNATTRIBUTED,
})

REASON_COMMAND_INVALID = "app-command-invalid"
REASON_PARAMS_INVALID = "app-params-invalid"
REASON_PLACEHOLDER_UNRESOLVED = "app-placeholder-unresolved"
REASON_PLACEHOLDER_IN_ARGV0 = "app-placeholder-in-argv0"
REASON_ENV_INVALID = "app-env-invalid"
REASON_ALLOCATION_INVALID = "app-allocation-invalid"
REASON_LAUNCH_INVALID = "app-launch-invalid"
REASON_CWD_INVALID = "app-cwd-invalid"
REASON_READINESS_URL_INVALID = "app-readiness-url-invalid"
REASON_BIND_CONFLICT = "app-bind-conflict"
REASON_ENDPOINT_DUPLICATE = "app-endpoint-duplicate"
REASON_SPAWN_FAILED = "app-spawn-failed"
REASON_READINESS_TIMEOUT = "app-readiness-timeout"
REASON_READINESS_TRANSPORT_ERROR = "app-readiness-transport-error"
REASON_READINESS_UNEXPECTED_STATUS = "app-readiness-unexpected-status"
REASON_READINESS_REDIRECT_REFUSED = "app-readiness-redirect-refused"
REASON_READINESS_UNATTRIBUTED = "app-readiness-unattributed"
REASON_PROCESS_EXITED = "app-process-exited"
REASON_GENERATION_MOVED = "app-generation-moved"
REASON_SLOT_STATE_NOT_LAUNCHABLE = "app-slot-state-not-launchable"
REASON_INSTANCE_RECORD_INVALID = "app-instance-record-invalid"
REASON_INSTANCE_RECORD_ABSENT = "app-instance-record-absent"
REASON_INSTANCE_RECORD_UNREADABLE = "app-instance-record-unreadable"
REASON_INSTANCE_RECORD_WRITE_FAILED = "app-instance-record-write-failed"
REASON_INSTANCE_RECORD_EXISTS = "app-instance-record-exists"
REASON_INSTANCE_PID_MISMATCH = "app-instance-pid-mismatch"
REASON_STOP_INDETERMINATE = "app-stop-indeterminate"
REASON_DECLARATION_UNEXERCISED = "app-declaration-unexercised"
REASON_JOURNAL_WRITE_FAILED = "app-journal-write-failed"

RETRYABLE_REASONS = frozenset({
    REASON_READINESS_TIMEOUT,
    REASON_READINESS_TRANSPORT_ERROR,
})

_BIND_CONFLICT_PATTERNS = (
    "address already in use",
    "eaddrinuse",
    "address in use",
)

_NONCE_RE = re.compile(r"^[0-9a-f]{32}$")

_AUTHORIZED_KEYS = frozenset({
    "schemaVersion", "slotRef", "baseUrl", "readinessUrl", "policyDigest",
})
_ALLOCATION_KEYS = frozenset({
    "host", "port", "hostnames", "containers", "envMetadata",
})


class PilotAppctlError(Exception):
    """Raised when app-control validation refuses."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _ok(**extra):
    out = {"ok": True, "reason": None}
    out.update(extra)
    return out


def _fail(reason, **extra):
    out = {"ok": False, "reason": reason}
    out.update(extra)
    return out


def _is_str_path(value):
    return isinstance(value, str)


def _is_timeout(value):
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    if math.isnan(value) or math.isinf(value):
        return False
    return True


def _is_callable(value):
    return callable(value)


def _is_iso8601_utc(value):
    if not isinstance(value, str) or not value:
        return False
    text = value.strip()
    if not text.endswith("Z"):
        return False
    try:
        dt = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        return False
    return dt.tzinfo is not None


def _utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _substitute_once(template, params):
    """Single left-to-right pass; returns (output, unresolved_names, error_reason)."""
    if not isinstance(template, str):
        return None, set(), REASON_PARAMS_INVALID
    unresolved = set()
    out = []
    i = 0
    n = len(template)
    while i < n:
        ch = template[i]
        if ch != "{":
            if ch == "}":
                return None, set(), REASON_PARAMS_INVALID
            out.append(ch)
            i += 1
            continue
        if i + 1 >= n:
            return None, set(), REASON_PARAMS_INVALID
        close = template.find("}", i + 1)
        if close == -1:
            return None, set(), REASON_PARAMS_INVALID
        inner = template[i + 1:close]
        if not inner or "{" in inner or "}" in inner:
            return None, set(), REASON_PARAMS_INVALID
        if inner in params:
            out.append(params[inner])
        else:
            unresolved.add(inner)
            out.append("{" + inner + "}")
        i = close + 1
    return "".join(out), unresolved, None


def _validate_readiness_scheme(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https")


def _normalize_host(host):
    if not isinstance(host, str):
        return None
    text = host.rstrip(".")
    return text.casefold()


def _is_command_argv(argv):
    if not isinstance(argv, list) or not argv:
        return False
    for part in argv:
        if not isinstance(part, str) or not part:
            return False
        if "\x00" in part:
            return False
    return True


def _validate_env_overlay(env):
    """Shared env overlay rules for resolve_invocation and _validate_launch."""
    if env is None:
        return _ok()
    if not isinstance(env, dict):
        return _fail(REASON_ENV_INVALID)
    for key, value in env.items():
        if not isinstance(key, str) or not key:
            return _fail(REASON_ENV_INVALID)
        if "=" in key or "\x00" in key:
            return _fail(REASON_ENV_INVALID)
        if not isinstance(value, str):
            return _fail(REASON_ENV_INVALID)
        if "\x00" in value:
            return _fail(REASON_ENV_INVALID)
    return _ok()


def _instance_log_paths(slots_dir_path, slot):
    slot_dir = os.path.join(slots_dir_path, slot)
    return (
        os.path.join(slot_dir, "app.stdout.log"),
        os.path.join(slot_dir, "app.stderr.log"),
    )


def _refuse_unsafe_dir(path):
    if os.path.islink(path):
        raise PilotAppctlError(REASON_CWD_INVALID)
    if os.path.lexists(path) and not os.path.isdir(path):
        raise PilotAppctlError(REASON_CWD_INVALID)


def instance_path(slots_dir_path, slot):
    if not _is_str_path(slots_dir_path):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    slot = pilot_slot.validate_slot_id(slot)
    return os.path.join(slots_dir_path, slot, "app.json")


def resolve_invocation(dev_command, *, params, readiness_url, env=None):
    """Substitute per-slot parameters into argv, readiness URL, and optional env."""
    if not _is_command_argv(dev_command):
        return _fail(REASON_COMMAND_INVALID)
    if not isinstance(params, dict):
        return _fail(REASON_PARAMS_INVALID)
    for key, value in params.items():
        if not isinstance(key, str) or not key or "{" in key or "}" in key:
            return _fail(REASON_PARAMS_INVALID)
        if not isinstance(value, str):
            return _fail(REASON_PARAMS_INVALID)

    if _argv0_has_placeholder(dev_command[0]):
        return _fail(REASON_PLACEHOLDER_IN_ARGV0)

    if not isinstance(readiness_url, str) or not readiness_url:
        return _fail(REASON_READINESS_URL_INVALID)

    resolved_argv = []
    all_unresolved = set()
    for part in dev_command:
        out, unresolved, err = _substitute_once(part, params)
        if err is not None:
            return _fail(err)
        all_unresolved.update(unresolved)
        resolved_argv.append(out)

    resolved_url, url_unresolved, url_err = _substitute_once(readiness_url, params)
    if url_err is not None:
        return _fail(url_err)
    all_unresolved.update(url_unresolved)

    if all_unresolved:
        return _fail(REASON_PLACEHOLDER_UNRESOLVED)

    if not _validate_readiness_scheme(resolved_url):
        return _fail(REASON_READINESS_URL_INVALID)

    env_check = _validate_env_overlay(env)
    if not env_check["ok"]:
        return env_check
    resolved_env = None if env is None else dict(env)

    return _ok(argv=resolved_argv, readinessUrl=resolved_url, env=resolved_env)


def _argv0_has_placeholder(argv0):
    """True when argv0 template contains a ``{name}`` placeholder."""
    if not isinstance(argv0, str):
        return False
    i = 0
    while i < len(argv0):
        if argv0[i] != "{":
            i += 1
            continue
        close = argv0.find("}", i + 1)
        if close == -1:
            return False
        inner = argv0[i + 1:close]
        if inner and "{" not in inner and "}" not in inner:
            return True
        i = close + 1
    return False


def assert_unique_endpoints(allocations):
    """Refuse duplicate (host, port) pairs across the wave before any spawn."""
    if not isinstance(allocations, list):
        return _fail(REASON_ALLOCATION_INVALID, duplicates=[])
    seen_refs = set()
    endpoint_map = {}
    duplicates = []
    for entry in allocations:
        if not isinstance(entry, dict):
            return _fail(REASON_ALLOCATION_INVALID, duplicates=[])
        slot_ref = entry.get("slotRef")
        host = entry.get("host")
        port = entry.get("port")
        try:
            pilot_slot.parse_slot_ref(slot_ref)
        except pilot_slot.PilotSlotError:
            return _fail(REASON_ALLOCATION_INVALID, duplicates=[])
        if not isinstance(host, str) or not host:
            return _fail(REASON_ALLOCATION_INVALID, duplicates=[])
        if not isinstance(port, int) or isinstance(port, bool):
            return _fail(REASON_ALLOCATION_INVALID, duplicates=[])
        if port < 1 or port > 65535:
            return _fail(REASON_ALLOCATION_INVALID, duplicates=[])
        if slot_ref in seen_refs:
            return _fail(REASON_ALLOCATION_INVALID, duplicates=[])
        seen_refs.add(slot_ref)
        norm_host = _normalize_host(host)
        key = (norm_host, port)
        if key in endpoint_map and endpoint_map[key] != slot_ref:
            pair = {
                "host": host,
                "port": port,
                "slotRefs": sorted([endpoint_map[key], slot_ref]),
            }
            if pair not in duplicates:
                duplicates.append(pair)
        else:
            endpoint_map[key] = slot_ref
    if duplicates:
        return _fail(REASON_ENDPOINT_DUPLICATE, duplicates=duplicates)
    return _ok(duplicates=[])


def check_endpoint_free(host, port, *, connect=None, timeout=0.25):
    """Return whether (host, port) accepts a new bind (nothing listening)."""
    try:
        if not isinstance(host, str) or not host:
            return _fail(REASON_ALLOCATION_INVALID)
        if "\x00" in host:
            return _fail(REASON_ALLOCATION_INVALID)
        try:
            host.encode("idna")
        except UnicodeError:
            return _fail(REASON_ALLOCATION_INVALID)
        if len(host) > 253:
            return _fail(REASON_ALLOCATION_INVALID)
        if not isinstance(port, int) or isinstance(port, bool):
            return _fail(REASON_ALLOCATION_INVALID)
        if port < 1 or port > 65535:
            return _fail(REASON_ALLOCATION_INVALID)
        if not _is_timeout(timeout):
            return _fail(REASON_ALLOCATION_INVALID)
        if connect is not None and not _is_callable(connect):
            return _fail(REASON_ALLOCATION_INVALID)
        if connect is None:
            def connect(addr, t):
                sock = socket.create_connection(addr, timeout=t)
                sock.close()
        try:
            connect((host, port), timeout)
            return _fail(REASON_BIND_CONFLICT)
        except ConnectionRefusedError:
            return _ok(observable=True)
        except socket.timeout:
            return _ok(observable=False)
        except (OSError, UnicodeError):
            return _fail(REASON_BIND_CONFLICT, observable=False)
    except BaseException:
        return _fail(REASON_BIND_CONFLICT)


def retry_gate(reason):
    """Allowlist-backed retry classification."""
    if not isinstance(reason, str):
        return {"retryable": False, "reason": reason}
    return {"retryable": reason in RETRYABLE_REASONS, "reason": reason}


def _validate_authorized(authorized):
    if not isinstance(authorized, dict):
        return False
    if set(authorized.keys()) != _AUTHORIZED_KEYS:
        return False
    if authorized.get("schemaVersion") != 1:
        return False
    try:
        pilot_slot.parse_slot_ref(authorized.get("slotRef"))
    except pilot_slot.PilotSlotError:
        return False
    base_url = authorized.get("baseUrl")
    readiness_url = authorized.get("readinessUrl")
    policy_digest = authorized.get("policyDigest")
    if not isinstance(base_url, str) or not base_url:
        return False
    if not isinstance(readiness_url, str) or not readiness_url:
        return False
    if not isinstance(policy_digest, str) or not policy_digest:
        return False
    return True


def _validate_allocation(allocation):
    if not isinstance(allocation, dict):
        return False
    if set(allocation.keys()) != _ALLOCATION_KEYS:
        return False
    host = allocation.get("host")
    port = allocation.get("port")
    hostnames = allocation.get("hostnames")
    containers = allocation.get("containers")
    env_metadata = allocation.get("envMetadata")
    if not isinstance(host, str) or not host:
        return False
    if not isinstance(port, int) or isinstance(port, bool):
        return False
    if port < 1 or port > 65535:
        return False
    if not isinstance(hostnames, list):
        return False
    for hn in hostnames:
        if not isinstance(hn, str):
            return False
    if not isinstance(containers, list):
        return False
    if not isinstance(env_metadata, dict):
        return False
    return True


def _validate_launch(launch):
    if not isinstance(launch, dict):
        return _fail(REASON_LAUNCH_INVALID)
    required = {
        "authorized", "slot", "slotRef", "cwd", "argv", "env", "allocation",
        "readinessUrl", "readinessAttribution", "readinessTimeoutSeconds", "pollSeconds",
    }
    if set(launch.keys()) != required:
        return _fail(REASON_LAUNCH_INVALID)
    try:
        slot = pilot_slot.validate_slot_id(launch.get("slot"))
        parsed_slot, _ = pilot_slot.parse_slot_ref(launch.get("slotRef"))
    except pilot_slot.PilotSlotError:
        return _fail(REASON_LAUNCH_INVALID)
    if slot != parsed_slot:
        return _fail(REASON_LAUNCH_INVALID)
    cwd = launch.get("cwd")
    if not _is_str_path(cwd) or not os.path.isabs(cwd):
        return _fail(REASON_CWD_INVALID)
    try:
        _refuse_unsafe_dir(cwd)
    except PilotAppctlError as exc:
        return _fail(exc.reason)
    if not os.path.isdir(cwd):
        return _fail(REASON_CWD_INVALID)
    if not _validate_authorized(launch.get("authorized")):
        return _fail(REASON_LAUNCH_INVALID)
    argv = launch.get("argv")
    if isinstance(argv, list):
        for part in argv:
            if isinstance(part, str) and "\x00" in part:
                return _fail(REASON_COMMAND_INVALID)
    if not _is_command_argv(argv):
        return _fail(REASON_LAUNCH_INVALID)
    env_check = _validate_env_overlay(launch.get("env"))
    if not env_check["ok"]:
        return env_check
    if not _validate_allocation(launch.get("allocation")):
        return _fail(REASON_ALLOCATION_INVALID)
    readiness_url = launch.get("readinessUrl")
    if not isinstance(readiness_url, str) or not readiness_url:
        return _fail(REASON_LAUNCH_INVALID)
    if not _validate_readiness_scheme(readiness_url):
        return _fail(REASON_READINESS_URL_INVALID)
    attribution = launch.get("readinessAttribution")
    if attribution not in READINESS_ATTRIBUTIONS:
        return _fail(REASON_LAUNCH_INVALID)
    timeout = launch.get("readinessTimeoutSeconds")
    poll = launch.get("pollSeconds")
    if not _is_timeout(timeout) or timeout <= 0:
        return _fail(REASON_LAUNCH_INVALID)
    if not _is_timeout(poll) or poll <= 0:
        return _fail(REASON_LAUNCH_INVALID)
    return _ok(slot=slot)


def _validate_stop_receipt(receipt):
    if not isinstance(receipt, dict):
        return False
    keys = set(receipt.keys())
    if keys != {"step", "slotRef", "observedAt", "evidence"}:
        return False
    if receipt.get("step") != "app-instance":
        return False
    try:
        pilot_slot.parse_slot_ref(receipt.get("slotRef"))
    except pilot_slot.PilotSlotError:
        return False
    if not _is_iso8601_utc(receipt.get("observedAt")):
        return False
    evidence = receipt.get("evidence")
    return isinstance(evidence, str) and bool(evidence)


def _validate_instance_record(instance):
    if not isinstance(instance, dict):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    if instance.get("schemaVersion") != SCHEMA:
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    slot = pilot_slot.validate_slot_id(instance.get("slot"))
    try:
        parsed_slot, _ = pilot_slot.parse_slot_ref(instance.get("slotRef"))
    except pilot_slot.PilotSlotError:
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    if instance.get("slot") != parsed_slot:
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    state = instance.get("state")
    if state not in INSTANCE_STATES:
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    pid = instance.get("pid")
    pgid = instance.get("pgid")
    if not isinstance(pid, int) or isinstance(pid, bool):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    if not isinstance(pgid, int) or isinstance(pgid, bool):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    nonce = instance.get("launchNonce")
    if not isinstance(nonce, str) or not _NONCE_RE.match(nonce):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    cwd = instance.get("cwd")
    if not _is_str_path(cwd) or not os.path.isabs(cwd):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    if not _validate_allocation(instance.get("allocation")):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    if not _is_command_argv(instance.get("command")):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    readiness_url = instance.get("readinessUrl")
    if not isinstance(readiness_url, str) or not readiness_url:
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    attribution = instance.get("readinessAttribution")
    if attribution not in READINESS_ATTRIBUTIONS:
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    started_at = instance.get("startedAt")
    updated_at = instance.get("updatedAt")
    if not _is_iso8601_utc(started_at) or not _is_iso8601_utc(updated_at):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    stdout_path = instance.get("stdoutPath")
    stderr_path = instance.get("stderrPath")
    if not _is_str_path(stdout_path) or not os.path.isabs(stdout_path):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    if not _is_str_path(stderr_path) or not os.path.isabs(stderr_path):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    stop_receipt = instance.get("stopReceipt")
    if stop_receipt is not None and not _validate_stop_receipt(stop_receipt):
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    if instance.get("slot") != slot:
        raise PilotAppctlError(REASON_INSTANCE_RECORD_INVALID)
    return slot


def _write_instance_file(path, instance):
    try:
        _validate_instance_record(instance)
    except (PilotAppctlError, pilot_slot.PilotSlotError):
        return _fail(REASON_INSTANCE_RECORD_INVALID)
    try:
        text = json.dumps(instance, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except (TypeError, ValueError):
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)
    parent = os.path.dirname(os.path.abspath(path)) or "."
    try:
        _refuse_unsafe_dir(parent)
    except PilotAppctlError as exc:
        return _fail(exc.reason)
    try:
        store_core.atomic_write(path, text)
        dir_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)
    return _ok()


def write_instance(slots_dir_path, slot, instance, *, timeout=30.0):
    """Durably persist a validated instance record under the per-slot lock."""
    if not _is_str_path(slots_dir_path):
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)
    if not _is_timeout(timeout):
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)
    try:
        slot = pilot_slot.validate_slot_id(slot)
    except pilot_slot.PilotSlotError:
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)
    path = instance_path(slots_dir_path, slot)
    try:
        with pilot_lifecycle.slot_lock(slots_dir_path, slot, timeout=timeout):
            return _write_instance_file(path, instance)
    except pilot_lifecycle.PilotLifecycleError:
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)
    except OSError:
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)


def _read_instance_from_path(path):
    """Load and validate an instance record from a path. Never raises."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return _fail(REASON_INSTANCE_RECORD_ABSENT, instance=None)
    except OSError:
        return _fail(REASON_INSTANCE_RECORD_UNREADABLE, instance=None)
    try:
        stat_result = os.fstat(fd)
        if not stat.S_ISREG(stat_result.st_mode):
            return _fail(REASON_INSTANCE_RECORD_UNREADABLE, instance=None)
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks).decode("utf-8")
    except OSError:
        return _fail(REASON_INSTANCE_RECORD_UNREADABLE, instance=None)
    except UnicodeDecodeError:
        return _fail(REASON_INSTANCE_RECORD_INVALID, instance=None)
    finally:
        os.close(fd)
    try:
        parsed = json.loads(raw)
    except ValueError:
        return _fail(REASON_INSTANCE_RECORD_INVALID, instance=None)
    if not isinstance(parsed, dict):
        return _fail(REASON_INSTANCE_RECORD_INVALID, instance=None)
    try:
        _validate_instance_record(parsed)
    except (PilotAppctlError, pilot_slot.PilotSlotError):
        return _fail(REASON_INSTANCE_RECORD_INVALID, instance=None)
    return _ok(instance=parsed)


def read_instance(slots_dir_path, slot):
    """Load and validate an instance record. Never raises."""
    if not _is_str_path(slots_dir_path):
        return _fail(REASON_INSTANCE_RECORD_UNREADABLE, instance=None)
    try:
        slot = pilot_slot.validate_slot_id(slot)
    except pilot_slot.PilotSlotError:
        return _fail(REASON_INSTANCE_RECORD_UNREADABLE, instance=None)
    path = instance_path(slots_dir_path, slot)
    return _read_instance_from_path(path)


def clear_instance(slots_dir_path, slot, *, timeout=30.0):
    """Remove the instance record under the per-slot lock."""
    if not _is_str_path(slots_dir_path):
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)
    if not _is_timeout(timeout):
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)
    try:
        slot = pilot_slot.validate_slot_id(slot)
    except pilot_slot.PilotSlotError:
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)
    path = instance_path(slots_dir_path, slot)
    try:
        with pilot_lifecycle.slot_lock(slots_dir_path, slot, timeout=timeout):
            try:
                os.unlink(path)
            except FileNotFoundError:
                return _ok()
            except OSError:
                return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)
            return _ok()
    except pilot_lifecycle.PilotLifecycleError:
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)
    except OSError:
        return _fail(REASON_INSTANCE_RECORD_WRITE_FAILED)


def _default_spawn(argv, *, cwd, env, stdout_path=None, stderr_path=None):
    merged = dict(os.environ)
    if env:
        merged.update(env)
    stdout_dest = subprocess.DEVNULL
    stderr_dest = subprocess.DEVNULL
    opened = []
    try:
        if stdout_path is not None:
            stdout_dest = open(stdout_path, "wb")
            opened.append(stdout_dest)
        if stderr_path is not None:
            stderr_dest = open(stderr_path, "wb")
            opened.append(stderr_dest)
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            env=merged,
            stdout=stdout_dest,
            stderr=stderr_dest,
            start_new_session=True,
        )
    except OSError:
        for handle in opened:
            try:
                handle.close()
            except OSError:
                pass
        raise
    for handle in opened:
        try:
            handle.close()
        except OSError:
            pass
    return proc


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _default_readiness_probe(url, *, timeout):
    opener = urllib.request.build_opener(_NoRedirectHandler)
    try:
        with opener.open(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": body, "error": None}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"status": exc.code, "body": body, "error": None}
    except Exception as exc:
        return {"status": None, "body": "", "error": str(exc)}


def _stderr_bind_conflict(stderr_path):
    if not isinstance(stderr_path, str) or not stderr_path:
        return False
    try:
        with open(stderr_path, "rb") as fh:
            text = fh.read().decode("utf-8", errors="replace").casefold()
    except OSError:
        return False
    return any(pat in text for pat in _BIND_CONFLICT_PATTERNS)


def _proc_exited(proc):
    return proc.poll() is not None


def _build_starting_record(launch, *, nonce, now, stdout_path, stderr_path):
    return {
        "schemaVersion": SCHEMA,
        "slot": launch["slot"],
        "slotRef": launch["slotRef"],
        "state": STATE_STARTING,
        "pid": 0,
        "pgid": 0,
        "launchNonce": nonce,
        "cwd": launch["cwd"],
        "allocation": launch["allocation"],
        "command": list(launch["argv"]),
        "readinessUrl": launch["readinessUrl"],
        "readinessAttribution": launch["readinessAttribution"],
        "stdoutPath": stdout_path,
        "stderrPath": stderr_path,
        "startedAt": now,
        "updatedAt": now,
        "stopReceipt": None,
    }


def _journal_end(journal_path, *, slot_ref, effect_id, outcome, at, reason=None):
    return pilot_journal.end_effect(
        journal_path,
        slot_ref=slot_ref,
        effect_id=effect_id,
        outcome=outcome,
        at=at,
        reason=reason,
    )


def _validate_stand_up_hooks(*, spawn, readiness_probe, monotonic, sleep):
    for hook in (spawn, readiness_probe, monotonic, sleep):
        if hook is not None and not _is_callable(hook):
            return _fail(REASON_LAUNCH_INVALID)
    return _ok()


def _stand_up_failure(reason, *, instance=None, degradations=None, **extra):
    return {
        "ok": False,
        "reason": reason,
        "instance": instance,
        "degradations": degradations if degradations is not None else [],
        **extra,
    }


def _compensate_running_child(instance_record, proc, pgid):
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            pass
    if instance_record is not None:
        instance_record["state"] = STATE_INDETERMINATE


def stand_up(launch, *, journal_path, slots_dir_path, now, now_fn, registry, declaration,
             spawn=None, readiness_probe=None, monotonic=None, sleep=None):
    """Stand up one slot's app instance with durable record and readiness polling."""
    use_default_spawn = spawn is None
    if spawn is None:
        spawn = _default_spawn
    if readiness_probe is None:
        readiness_probe = _default_readiness_probe
    if monotonic is None:
        monotonic = time.monotonic
    if sleep is None:
        sleep = time.sleep

    validated = _validate_launch(launch)
    if not validated["ok"]:
        return _stand_up_failure(validated["reason"])

    hook_check = _validate_stand_up_hooks(
        spawn=spawn,
        readiness_probe=readiness_probe,
        monotonic=monotonic,
        sleep=sleep,
    )
    if not hook_check["ok"]:
        return _stand_up_failure(hook_check["reason"])

    try:
        pilot_contract.require_exercised(registry, "app-lifecycle", declaration)
    except pilot_contract.PilotContractError:
        return _stand_up_failure(REASON_DECLARATION_UNEXERCISED)

    authorized = launch["authorized"]
    if authorized["slotRef"] != launch["slotRef"]:
        return _stand_up_failure(REASON_LAUNCH_INVALID)
    if authorized["readinessUrl"] != launch["readinessUrl"]:
        return _stand_up_failure(REASON_LAUNCH_INVALID)

    allocation = launch["allocation"]
    free = check_endpoint_free(allocation["host"], allocation["port"])
    if not free["ok"]:
        return _stand_up_failure(free["reason"])

    slot = launch["slot"]
    _, carried_gen = pilot_slot.parse_slot_ref(launch["slotRef"])
    effect_id = None
    instance_record = None
    proc = None
    pgid = None
    pid = None
    degradations = []
    stdout_path, stderr_path = _instance_log_paths(slots_dir_path, slot)

    try:
        with pilot_lifecycle.slot_lock(slots_dir_path, slot):
            slot_path = pilot_lifecycle.record_path(slots_dir_path, slot)
            loaded = pilot_lifecycle.read_record(slot_path)
            if not loaded["ok"]:
                return _stand_up_failure(REASON_SLOT_STATE_NOT_LAUNCHABLE)
            record = loaded["record"]
            if record["state"] not in LAUNCHABLE_SLOT_STATES:
                return _stand_up_failure(REASON_SLOT_STATE_NOT_LAUNCHABLE)
            gen_check = pilot_lifecycle.generation_check(carried_gen, record["generation"])
            if not gen_check["ok"]:
                return _stand_up_failure(
                    REASON_GENERATION_MOVED,
                    generationReason=gen_check["reason"],
                )

            inst_path = instance_path(slots_dir_path, slot)
            existing = _read_instance_from_path(inst_path)
            if existing["ok"]:
                if existing["instance"]["state"] in ACTIVE_INSTANCE_STATES:
                    return _stand_up_failure(REASON_INSTANCE_RECORD_EXISTS)

            nonce = secrets.token_hex(16)
            instance_record = _build_starting_record(
                launch,
                nonce=nonce,
                now=now,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            written = _write_instance_file(inst_path, instance_record)
            if not written["ok"]:
                return _stand_up_failure(REASON_INSTANCE_RECORD_WRITE_FAILED)

        begin = pilot_journal.begin_effect(
            journal_path,
            slot_ref=launch["slotRef"],
            kind=pilot_journal.KIND_APP_STARTED,
            at=now,
            detail={
                "port": allocation["port"],
                "argv0": launch["argv"][0],
                "launchNonce": nonce,
            },
        )
        if not begin["ok"]:
            return _stand_up_failure(
                REASON_JOURNAL_WRITE_FAILED,
                instance=instance_record,
            )
        effect_id = begin["effectId"]

        child_env = dict(launch["env"] or {})
        child_env["SUPERHEROES_PILOT_LAUNCH_NONCE"] = nonce
        child_env["SUPERHEROES_PILOT_SLOT_REF"] = launch["slotRef"]
        try:
            if use_default_spawn:
                proc = spawn(
                    launch["argv"],
                    cwd=launch["cwd"],
                    env=child_env,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                )
            else:
                proc = spawn(launch["argv"], cwd=launch["cwd"], env=child_env)
        except OSError as exc:
            end_at = now_fn()
            end = _journal_end(
                journal_path,
                slot_ref=launch["slotRef"],
                effect_id=effect_id,
                outcome=pilot_journal.OUTCOME_NOT_APPLIED,
                at=end_at,
                reason=str(exc),
            )
            if not end["ok"]:
                return _stand_up_failure(
                    REASON_JOURNAL_WRITE_FAILED,
                    instance=instance_record,
                )
            return _stand_up_failure(REASON_SPAWN_FAILED, instance=instance_record)

        pid = proc.pid
        try:
            pgid = os.getpgid(pid)
        except OSError:
            pgid = pid

        instance_record["pid"] = pid
        instance_record["pgid"] = pgid
        instance_record["updatedAt"] = now_fn()
        pid_write = write_instance(slots_dir_path, slot, instance_record)
        if not pid_write["ok"]:
            _compensate_running_child(instance_record, proc, pgid)
            instance_record["updatedAt"] = now_fn()
            write_instance(slots_dir_path, slot, instance_record)
            end_at = now_fn()
            end = _journal_end(
                journal_path,
                slot_ref=launch["slotRef"],
                effect_id=effect_id,
                outcome=pilot_journal.OUTCOME_INDETERMINATE,
                at=end_at,
                reason=REASON_INSTANCE_RECORD_WRITE_FAILED,
            )
            if not end["ok"]:
                return _stand_up_failure(
                    REASON_JOURNAL_WRITE_FAILED,
                    instance=instance_record,
                    pid=pid,
                    pgid=pgid,
                )
            return _stand_up_failure(
                REASON_INSTANCE_RECORD_WRITE_FAILED,
                instance=instance_record,
                pid=pid,
                pgid=pgid,
            )

        deadline = monotonic() + launch["readinessTimeoutSeconds"]
        poll_interval = launch["pollSeconds"]
        readiness_reason = None

        while True:
            if _proc_exited(proc):
                if _stderr_bind_conflict(instance_record.get("stderrPath")):
                    readiness_reason = REASON_BIND_CONFLICT
                else:
                    readiness_reason = REASON_PROCESS_EXITED
                break

            probe = readiness_probe(
                launch["readinessUrl"],
                timeout=min(1.0, poll_interval),
            )

            if probe.get("error"):
                if monotonic() >= deadline:
                    readiness_reason = REASON_READINESS_TIMEOUT
                    break
                sleep(poll_interval)
                continue

            status = probe.get("status")
            if status is not None and 300 <= status < 400:
                readiness_reason = REASON_READINESS_REDIRECT_REFUSED
                break

            if status is not None and 200 <= status < 300:
                if launch["readinessAttribution"] == READINESS_ATTRIBUTION_NONCE:
                    body = probe.get("body") or ""
                    if nonce in body:
                        if _proc_exited(proc):
                            readiness_reason = REASON_PROCESS_EXITED
                            break
                        readiness_reason = None
                        break
                    if monotonic() >= deadline:
                        readiness_reason = REASON_READINESS_UNATTRIBUTED
                        break
                    sleep(poll_interval)
                    continue
                degradations.append({
                    "kind": "readiness-unattributed",
                    "detail": "readiness accepted without launch attribution",
                })
                if _proc_exited(proc):
                    readiness_reason = REASON_PROCESS_EXITED
                    break
                readiness_reason = None
                break

            if monotonic() >= deadline:
                if probe.get("error"):
                    readiness_reason = REASON_READINESS_TRANSPORT_ERROR
                else:
                    readiness_reason = REASON_READINESS_UNEXPECTED_STATUS
                break
            sleep(poll_interval)

        if readiness_reason is not None:
            end_at = now_fn()
            end = _journal_end(
                journal_path,
                slot_ref=launch["slotRef"],
                effect_id=effect_id,
                outcome=pilot_journal.OUTCOME_INDETERMINATE,
                at=end_at,
                reason=readiness_reason,
            )
            if not end["ok"]:
                return _stand_up_failure(
                    REASON_JOURNAL_WRITE_FAILED,
                    instance=instance_record,
                    pid=pid,
                    pgid=pgid,
                )
            _compensate_running_child(instance_record, proc, pgid)
            instance_record["updatedAt"] = end_at
            write_instance(slots_dir_path, slot, instance_record)
            return _stand_up_failure(
                readiness_reason,
                instance=instance_record,
                degradations=degradations,
            )

        with pilot_lifecycle.slot_lock(slots_dir_path, slot):
            loaded = pilot_lifecycle.read_record(
                pilot_lifecycle.record_path(slots_dir_path, slot),
            )
            if not loaded["ok"]:
                stop(instance_record, now_fn=now_fn)
                end_at = now_fn()
                end = _journal_end(
                    journal_path,
                    slot_ref=launch["slotRef"],
                    effect_id=effect_id,
                    outcome=pilot_journal.OUTCOME_INDETERMINATE,
                    at=end_at,
                    reason=REASON_SLOT_STATE_NOT_LAUNCHABLE,
                )
                if not end["ok"]:
                    return _stand_up_failure(
                        REASON_JOURNAL_WRITE_FAILED,
                        instance=instance_record,
                        pid=pid,
                        pgid=pgid,
                        degradations=degradations,
                    )
                instance_record["updatedAt"] = end_at
                write_instance(slots_dir_path, slot, instance_record)
                return _stand_up_failure(
                    REASON_SLOT_STATE_NOT_LAUNCHABLE,
                    instance=instance_record,
                    degradations=degradations,
                )
            gen_check = pilot_lifecycle.generation_check(
                carried_gen,
                loaded["record"]["generation"],
            )
            if not gen_check["ok"]:
                # Child was spawned moments earlier in this same call; corroborate=True
                # is safe here because positivity is gated inside stop().
                stop(instance_record, now_fn=now_fn, corroborate=lambda _inst: True)
                end_at = now_fn()
                end = _journal_end(
                    journal_path,
                    slot_ref=launch["slotRef"],
                    effect_id=effect_id,
                    outcome=pilot_journal.OUTCOME_INDETERMINATE,
                    at=end_at,
                    reason=REASON_GENERATION_MOVED,
                )
                if not end["ok"]:
                    return _stand_up_failure(
                        REASON_JOURNAL_WRITE_FAILED,
                        instance=instance_record,
                        pid=pid,
                        pgid=pgid,
                        degradations=degradations,
                    )
                instance_record["updatedAt"] = end_at
                write_instance(slots_dir_path, slot, instance_record)
                return _stand_up_failure(
                    REASON_GENERATION_MOVED,
                    generationReason=gen_check["reason"],
                    instance=instance_record,
                    degradations=degradations,
                )

        instance_record["state"] = STATE_READY
        instance_record["updatedAt"] = now_fn()
        final_write = write_instance(slots_dir_path, slot, instance_record)
        end_at = now_fn()
        end = _journal_end(
            journal_path,
            slot_ref=launch["slotRef"],
            effect_id=effect_id,
            outcome=pilot_journal.OUTCOME_APPLIED,
            at=end_at,
        )
        if not end["ok"]:
            _compensate_running_child(instance_record, proc, pgid)
            instance_record["updatedAt"] = end_at
            write_instance(slots_dir_path, slot, instance_record)
            return _stand_up_failure(
                REASON_JOURNAL_WRITE_FAILED,
                instance=instance_record,
                pid=pid,
                pgid=pgid,
                degradations=degradations,
            )
        if not final_write["ok"]:
            _compensate_running_child(instance_record, proc, pgid)
            instance_record["updatedAt"] = end_at
            write_instance(slots_dir_path, slot, instance_record)
            return _stand_up_failure(
                REASON_INSTANCE_RECORD_WRITE_FAILED,
                pid=pid,
                pgid=pgid,
                instance=instance_record,
                degradations=degradations,
            )
        return {
            "ok": True,
            "reason": None,
            "instance": instance_record,
            "degradations": degradations,
        }
    except pilot_lifecycle.PilotLifecycleError:
        return _stand_up_failure(
            REASON_SLOT_STATE_NOT_LAUNCHABLE,
            instance=instance_record,
            degradations=degradations,
        )
    except BaseException as exc:
        if proc is not None and pgid is not None:
            _compensate_running_child(instance_record, proc, pgid)
            if instance_record is not None:
                instance_record["updatedAt"] = now_fn()
                write_instance(slots_dir_path, slot, instance_record)
        if effect_id is not None:
            end = _journal_end(
                journal_path,
                slot_ref=launch["slotRef"],
                effect_id=effect_id,
                outcome=pilot_journal.OUTCOME_INDETERMINATE,
                at=now_fn(),
                reason=repr(exc),
            )
            if not end["ok"]:
                return _stand_up_failure(
                    REASON_JOURNAL_WRITE_FAILED,
                    instance=instance_record,
                    pid=pid,
                    pgid=pgid,
                    degradations=degradations,
                )
        return _stand_up_failure(
            REASON_SPAWN_FAILED,
            instance=instance_record,
            pid=pid,
            pgid=pgid,
            degradations=degradations,
        )


def _default_corroborate(instance):
    pid = instance.get("pid")
    argv0 = instance.get("command", [""])[0]
    if not isinstance(pid, int):
        return False
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    output = (result.stdout or "").strip()
    if not output:
        return False
    exe_token = output.split(None, 1)[0]
    return exe_token == argv0 or os.path.basename(exe_token) == os.path.basename(argv0)


def _default_poll_alive(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True


def _default_terminate(pgid, sig):
    os.killpg(pgid, sig)


def _stop_refused_invalid():
    return {
        "ok": False,
        "reason": REASON_INSTANCE_RECORD_INVALID,
        "observed": False,
        "exit": None,
        "receipt": None,
    }


def stop(instance, *, now_fn, terminate=None, poll_alive=None, corroborate=None,
         check_free=None, wait_seconds=10.0, sleep=None, monotonic=None):
    """Stop an app instance with corroborated identity and two observations."""
    try:
        if not _is_callable(now_fn):
            return _stop_refused_invalid()
        if terminate is not None and not _is_callable(terminate):
            return _stop_refused_invalid()
        if poll_alive is not None and not _is_callable(poll_alive):
            return _stop_refused_invalid()
        if corroborate is not None and not _is_callable(corroborate):
            return _stop_refused_invalid()
        if check_free is not None and not _is_callable(check_free):
            return _stop_refused_invalid()
        if sleep is not None and not _is_callable(sleep):
            return _stop_refused_invalid()
        if monotonic is not None and not _is_callable(monotonic):
            return _stop_refused_invalid()
        if not _is_timeout(wait_seconds):
            return _stop_refused_invalid()

        if terminate is None:
            terminate = _default_terminate
        if poll_alive is None:
            poll_alive = _default_poll_alive
        if corroborate is None:
            corroborate = _default_corroborate
        if check_free is None:
            check_free = check_endpoint_free
        if sleep is None:
            sleep = time.sleep
        if monotonic is None:
            monotonic = time.monotonic

        if not isinstance(instance, dict):
            return _stop_refused_invalid()

        try:
            _validate_instance_record(instance)
        except (PilotAppctlError, pilot_slot.PilotSlotError):
            return _stop_refused_invalid()

        if instance.get("state") == STATE_STOPPED:
            receipt = instance.get("stopReceipt")
            if receipt is not None and _validate_stop_receipt(receipt):
                return {
                    "ok": True,
                    "reason": None,
                    "observed": True,
                    "exit": None,
                    "receipt": receipt,
                }

        if not corroborate(instance):
            return {
                "ok": False,
                "reason": REASON_INSTANCE_PID_MISMATCH,
                "observed": False,
                "exit": None,
                "receipt": None,
            }

        pid = instance["pid"]
        pgid = instance["pgid"]
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            return {
                "ok": False,
                "reason": REASON_STOP_INDETERMINATE,
                "observed": False,
                "exit": None,
                "receipt": None,
            }
        if not isinstance(pgid, int) or isinstance(pgid, bool) or pgid <= 0:
            return {
                "ok": False,
                "reason": REASON_STOP_INDETERMINATE,
                "observed": False,
                "exit": None,
                "receipt": None,
            }

        exit_code = None

        if poll_alive(pgid):
            try:
                terminate(pgid, signal.SIGTERM)
            except OSError:
                pass
            deadline = monotonic() + wait_seconds
            while poll_alive(pgid) and monotonic() < deadline:
                sleep(0.05)
            if poll_alive(pgid):
                try:
                    terminate(pgid, signal.SIGKILL)
                except OSError:
                    pass
                deadline = monotonic() + wait_seconds
                while poll_alive(pgid) and monotonic() < deadline:
                    sleep(0.05)

        try:
            _pid, status = os.waitpid(pid, os.WNOHANG)
            if _pid == pid:
                exit_code = os.waitstatus_to_exitcode(status)
        except ChildProcessError:
            pass
        except OSError:
            pass

        group_gone = not poll_alive(pgid)
        alloc = instance.get("allocation", {})
        host = alloc.get("host", "127.0.0.1")
        port = alloc.get("port", 0)
        endpoint_free = check_free(host, port)
        endpoint_observed = (
            endpoint_free.get("ok") is True
            and endpoint_free.get("observable", True) is not False
        )

        observed = group_gone and endpoint_observed
        now = now_fn()

        if observed:
            evidence = "process group gone; endpoint free"
            receipt = {
                "step": "app-instance",
                "slotRef": instance["slotRef"],
                "observedAt": now,
                "evidence": evidence,
            }
            instance["state"] = STATE_STOPPED
            instance["stopReceipt"] = receipt
            instance["updatedAt"] = now
            return {
                "ok": True,
                "reason": None,
                "observed": True,
                "exit": exit_code,
                "receipt": receipt,
            }

        detail_parts = []
        if not group_gone:
            detail_parts.append("process group still alive")
        if not endpoint_observed:
            detail_parts.append("endpoint still occupied")
        reason_detail = "; ".join(detail_parts) if detail_parts else "observations incomplete"
        instance["state"] = STATE_INDETERMINATE
        instance["updatedAt"] = now
        return {
            "ok": False,
            "reason": REASON_STOP_INDETERMINATE,
            "observed": False,
            "exit": exit_code,
            "receipt": None,
            "detail": reason_detail,
        }
    except BaseException:
        return _stop_refused_invalid()
