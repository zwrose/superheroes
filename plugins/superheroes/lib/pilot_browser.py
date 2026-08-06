"""Pilot browser layer — per-slot server/browser topology, pin integrity, socket dirs, fencing.

The framework never installs Playwright or any automation runtime. ``verify_pin`` only observes
and compares an externally supplied pin against a bounded subprocess observer.
"""
import contextlib
import hmac
import os
import re
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta

import pilot_bounded_run
import pilot_journal
import pilot_lifecycle
import pilot_slot
import store_core

PIN_SCHEMA_VERSION = 1

SUN_PATH_MAX = {"darwin": 104, "linux": 108}
MAX_SOCKET_FILENAME = 64

_SOCKET_DIR_PREFIX = "pb-"

REFUSAL_PIN_INVALID = "browser-pin-invalid"
REFUSAL_PIN_OBSERVER_INVALID = "browser-pin-observer-invalid"
REFUSAL_PIN_OBSERVER_UNSAFE = "browser-pin-observer-unsafe"
REFUSAL_PIN_OBSERVER_FAILED = "browser-pin-observer-failed"
REFUSAL_PIN_VERSION_MISMATCH = "browser-pin-version-mismatch"
REFUSAL_PIN_INTEGRITY_MISMATCH = "browser-pin-integrity-mismatch"

REFUSAL_SOCKET_PATH_TOO_LONG = "browser-socket-path-too-long"
REFUSAL_SOCKET_BASE_IN_WORKTREE = "browser-socket-base-in-worktree"
REFUSAL_SOCKET_DIR_EXISTS = "browser-socket-dir-exists"
REFUSAL_SOCKET_DIR_UNSAFE = "browser-socket-dir-unsafe"
REFUSAL_SOCKET_DIR_NOT_DIRECTORY = "browser-socket-dir-not-directory"
REFUSAL_SOCKET_DIR_UNREMOVABLE = "browser-socket-dir-unremovable"
REFUSAL_SOCKET_DIR_UNRECOGNIZED = "browser-socket-dir-unrecognized"
REFUSAL_WORKTREE_ROOT_UNRESOLVED = "browser-worktree-root-unresolved"

REFUSAL_SERVER_RECORD_INVALID = "browser-server-record-invalid"
REFUSAL_SERVER_RECORD_STALE = "browser-server-record-stale"
REFUSAL_FENCING_SLOTS_DIR_REQUIRED = "browser-fencing-slots-dir-required"
REFUSAL_SLOT_STATE_NOT_LIVE = "browser-slot-state-not-live"
REFUSAL_NOT_SERVER_CHILD = "browser-not-server-child"
REFUSAL_PID_UNREADABLE = "browser-pid-unreadable"
REFUSAL_TERMINAL_STATE_UNOBSERVED = "browser-terminal-state-unobserved"

REFUSAL_SHARED_CONTEXT_REFUSED = "browser-shared-context-refused"
REFUSAL_SERVER_SHARED_ACROSS_SLOTS = "browser-server-shared-across-slots-refused"
REFUSAL_SHARED_ACROSS_SLOTS = "browser-shared-across-slots-refused"
REFUSAL_MULTIPLE_SERVERS_FOR_SLOT = "browser-multiple-servers-for-slot"

REFUSAL_OPERATION_SLOT_REF_INVALID = "browser-operation-slot-ref-invalid"
REFUSAL_OPERATION_SLOT_MISMATCH = "browser-operation-slot-mismatch"

_PIN_REQUIRED_KEYS = frozenset({"schemaVersion", "version", "integrityDigest"})
_PIN_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_SERVER_RECORD_KEYS = frozenset({
    "schemaVersion", "slotRef", "generation", "socketDir",
    "serverPid", "browserPid", "pin", "createdAt",
})
_VALID_PID_MIN = 1

_LIVE_SLOT_STATES = frozenset({
    pilot_lifecycle.STATE_PROVISIONED,
    pilot_lifecycle.STATE_OCCUPIED,
})

_TERMINAL_EXIT_UNOBSERVED = object()


class PilotBrowserError(Exception):
    """Raised when browser-layer structural validation refuses."""

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


def _is_member(value, members):
    return isinstance(value, str) and value in members


def _is_str_path(value):
    return isinstance(value, str)


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


def _is_valid_version_string(value):
    if not isinstance(value, str) or not value:
        return False
    for ch in value:
        if ch.isspace() or ord(ch) < 32 or ord(ch) == 127:
            return False
    return True


def _later_timestamp(begin_at):
    """Return an ISO-8601 UTC timestamp strictly after begin_at."""
    try:
        dt = datetime.fromisoformat(begin_at[:-1] + "+00:00")
    except ValueError:
        return begin_at
    dt = dt + timedelta(microseconds=1)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%06dZ" % dt.microsecond


def _has_control_chars(text):
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in text)


def _path_related(base, other):
    """True when base is inside other or base is an ancestor of other."""
    base_real = os.path.realpath(base)
    other_real = os.path.realpath(other)
    try:
        common = os.path.commonpath([base_real, other_real])
    except ValueError:
        return False
    return common == base_real or common == other_real


def _minimal_subprocess_env():
    env = {}
    path = os.environ.get("PATH")
    if isinstance(path, str) and path:
        env["PATH"] = path
    return env


def _validate_observer(observer):
    if not isinstance(observer, dict) or set(observer.keys()) != frozenset({"command"}):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)
    command = observer["command"]
    if not isinstance(command, list) or not command:
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)
    for part in command:
        if not isinstance(part, str) or not part:
            raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)


def _path_components(path):
    parts = os.path.realpath(path).split(os.sep)
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _is_inside(path, root):
    path_parts = _path_components(path)
    root_parts = _path_components(root)
    if len(path_parts) < len(root_parts):
        return False
    return path_parts[:len(root_parts)] == root_parts


def _is_outside_all_reach_roots(path, reach_roots):
    real = os.path.realpath(path)
    for root in reach_roots:
        if _is_inside(real, root):
            return False
    return True


def _validate_observer_safety(observer, run_cwd, reach_roots):
    # bite-axis: observer safety — executable and run cwd must be absolute, owned, not
    # group/world-writable, and outside all reach roots; violation raises
    # REFUSAL_PIN_OBSERVER_UNSAFE.
    if not isinstance(reach_roots, list) or not reach_roots:
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_UNSAFE)
    for root in reach_roots:
        if not isinstance(root, str) or not os.path.isabs(root):
            raise PilotBrowserError(REFUSAL_PIN_OBSERVER_UNSAFE)

    command = observer["command"]
    if not isinstance(run_cwd, str) or not os.path.isdir(run_cwd):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_UNSAFE)

    executable = command[0]
    if not os.path.isabs(executable):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_UNSAFE)
    try:
        st = os.stat(executable)
    except OSError:
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_UNSAFE)
    if not stat.S_ISREG(st.st_mode):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_UNSAFE)
    if st.st_uid != os.getuid():
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_UNSAFE)
    if st.st_mode & 0o022:
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_UNSAFE)
    if not _is_outside_all_reach_roots(executable, reach_roots):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_UNSAFE)
    if not _is_outside_all_reach_roots(run_cwd, reach_roots):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_UNSAFE)

    for part in command[1:]:
        candidate = part if os.path.isabs(part) else os.path.join(run_cwd, part)
        resolved = os.path.realpath(candidate)
        if not _is_outside_all_reach_roots(resolved, reach_roots):
            raise PilotBrowserError(REFUSAL_PIN_OBSERVER_UNSAFE)


def validate_pin(pin):
    """Structural validation of a pin dict. Raises PilotBrowserError on refusal."""
    if not isinstance(pin, dict):
        raise PilotBrowserError(REFUSAL_PIN_INVALID)
    keys = set(pin.keys())
    if keys != _PIN_REQUIRED_KEYS:
        raise PilotBrowserError(REFUSAL_PIN_INVALID)
    if pin.get("schemaVersion") != PIN_SCHEMA_VERSION:
        raise PilotBrowserError(REFUSAL_PIN_INVALID)
    version = pin.get("version")
    if not _is_valid_version_string(version):
        raise PilotBrowserError(REFUSAL_PIN_INVALID)
    digest = pin.get("integrityDigest")
    if not isinstance(digest, str) or not _PIN_DIGEST_RE.match(digest):
        raise PilotBrowserError(REFUSAL_PIN_INVALID)
    return pin


def _run_bounded_observer(command, *, run_cwd, env, timeout_seconds, max_output_bytes):
  # bite-axis: observer execution — subprocess failure, oversized output, or non-single-line
  # UTF-8 stdout yields REFUSAL_PIN_OBSERVER_FAILED; only clean one-line output is returned.
    run = pilot_bounded_run.run_bounded(
        command,
        run_cwd=run_cwd,
        env=env,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        retain_output=True,
    )
    if (
        run["outcome"] != pilot_bounded_run.OUTCOME_COMPLETED
        or run["exitCode"] != 0
    ):
        return None
    return run["stdout"]


def verify_pin(pin, observer, *, run_cwd, reach_roots=None, timeout_seconds=20, max_output_bytes=4096):
    """Observe pin integrity via a bounded subprocess and compare version and digest."""
    pin = validate_pin(pin)
    _validate_observer(observer)
    if not _is_str_path(run_cwd):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)
    _validate_observer_safety(observer, run_cwd, reach_roots)
    if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)
    if not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)

    command = observer["command"]
    env = _minimal_subprocess_env()
    stdout = _run_bounded_observer(
        command,
        run_cwd=run_cwd,
        env=env,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )
    if stdout is None:
        return _fail(REFUSAL_PIN_OBSERVER_FAILED)

    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError:
        return _fail(REFUSAL_PIN_OBSERVER_FAILED)

    stripped = text.strip()
    if (
        not stripped
        or "\n" in stripped
        or _has_control_chars(stripped)
    ):
        return _fail(REFUSAL_PIN_OBSERVER_FAILED)

    parts = stripped.split(" ")
    if len(parts) != 2 or "" in parts:
        return _fail(REFUSAL_PIN_OBSERVER_FAILED)

    observed_version, observed_digest = parts
    if not hmac.compare_digest(observed_version, pin["version"]):
        return _fail(REFUSAL_PIN_VERSION_MISMATCH)
    if not hmac.compare_digest(observed_digest, pin["integrityDigest"]):
        return _fail(REFUSAL_PIN_INTEGRITY_MISMATCH)

    return _ok(version=pin["version"], integrityDigest=pin["integrityDigest"])


def _socket_cap(platform):
    if platform in SUN_PATH_MAX:
        return SUN_PATH_MAX[platform], platform
    smallest = min(SUN_PATH_MAX.values())
    return smallest, platform


def _resolve_worktree_root(worktree_root):
    if worktree_root is not None:
        if not _is_str_path(worktree_root):
            return None
        return os.path.realpath(worktree_root)
    try:
        return store_core.repo_root(os.getcwd())
    except store_core.RepoRootUnavailable:
        return None


def socket_dir_plan(slot_ref, *, base=None, launch_token=None, platform=None, worktree_root=None):
    """Plan a short unique socket directory path with measured SUN_PATH cap check."""
    try:
        slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        return _fail(REFUSAL_OPERATION_SLOT_REF_INVALID)

    if base is None:
        base = os.path.realpath(tempfile.gettempdir())
    elif not _is_str_path(base):
        return _fail(REFUSAL_SOCKET_PATH_TOO_LONG)

    base = os.path.realpath(base)

    resolved_worktree = _resolve_worktree_root(worktree_root)
    if resolved_worktree is None:
        return _fail(REFUSAL_WORKTREE_ROOT_UNRESOLVED)
    if _path_related(base, resolved_worktree):
        return _fail(REFUSAL_SOCKET_BASE_IN_WORKTREE)

    if platform is None:
        platform = sys.platform
    cap, recorded_platform = _socket_cap(platform)

    if launch_token is not None:
        if not isinstance(launch_token, str) or not launch_token:
            return _fail(REFUSAL_SOCKET_PATH_TOO_LONG)
        token = launch_token
    else:
        token = uuid.uuid4().hex[:8]

    dir_name = _SOCKET_DIR_PREFIX + token
    dir_path = os.path.join(base, dir_name)

    worst_case = os.path.join(dir_path, "x" * MAX_SOCKET_FILENAME)
    measured = len(worst_case.encode("utf-8")) + 1
    if measured > cap:
        return _fail(
            REFUSAL_SOCKET_PATH_TOO_LONG,
            path=None,
            slotRef=pilot_slot.format_slot_ref(slot, generation),
            cap=cap,
            measured=measured,
            platform=recorded_platform,
        )

    return _ok(
        path=dir_path,
        slotRef=pilot_slot.format_slot_ref(slot, generation),
        cap=cap,
        measured=measured,
        platform=recorded_platform,
    )


def create_socket_dir(plan):
    """Create a socket directory at plan path with mode 0o700."""
    if not isinstance(plan, dict) or plan.get("ok") is not True:
        return _fail(REFUSAL_SOCKET_DIR_UNSAFE)
    path = plan.get("path")
    if not _is_str_path(path):
        return _fail(REFUSAL_SOCKET_DIR_UNSAFE)

    if os.path.islink(path):
        return _fail(REFUSAL_SOCKET_DIR_UNSAFE)
    if os.path.lexists(path):
        return _fail(REFUSAL_SOCKET_DIR_EXISTS)

    try:
        os.makedirs(path, mode=0o700)
        st = os.stat(path, follow_symlinks=False)
        if not stat.S_ISDIR(st.st_mode):
            return _fail(REFUSAL_SOCKET_DIR_UNSAFE)
        if st.st_mode & 0o777 != 0o700:
            os.chmod(path, 0o700)
    except OSError:
        return _fail(REFUSAL_SOCKET_DIR_UNSAFE)

    return _ok(path=path)


def _remove_socket_dir_entry(dir_path, name):
    """Remove one enumerated entry from a socket directory; never follow symlinks."""
    entry_path = os.path.join(dir_path, name)
    try:
        st = os.lstat(entry_path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        try:
            os.unlink(entry_path)
        except OSError:
            return False
        return True
    if stat.S_ISREG(st.st_mode) or stat.S_ISSOCK(st.st_mode):
        try:
            os.unlink(entry_path)
        except OSError:
            return False
        return True
    if stat.S_ISDIR(st.st_mode):
        try:
            sub_entries = sorted(os.listdir(entry_path))
        except OSError:
            return False
        if sub_entries:
            return False
        try:
            os.rmdir(entry_path)
        except OSError:
            return False
        return True
    return False


def remove_socket_dir(path):
    """Remove a socket directory without following symlinks."""
    if not _is_str_path(path):
        return _fail(REFUSAL_SOCKET_DIR_NOT_DIRECTORY)
    if os.path.islink(path):
        return _fail(REFUSAL_SOCKET_DIR_UNSAFE)
    if not os.path.isdir(path):
        return _fail(REFUSAL_SOCKET_DIR_NOT_DIRECTORY)
    basename = os.path.basename(os.path.normpath(path))
    if not basename.startswith(_SOCKET_DIR_PREFIX):
        return _fail(REFUSAL_SOCKET_DIR_UNRECOGNIZED)
    try:
        entries = sorted(os.listdir(path))
    except OSError:
        return _fail(REFUSAL_SOCKET_DIR_UNREMOVABLE)
    removed_any = False
    for name in entries:
        if _remove_socket_dir_entry(path, name):
            removed_any = True
        else:
            result = _fail(REFUSAL_SOCKET_DIR_UNREMOVABLE)
            if removed_any:
                result["removedAny"] = True
            return result
    try:
        os.rmdir(path)
    except OSError:
        result = _fail(REFUSAL_SOCKET_DIR_UNREMOVABLE)
        if removed_any:
            result["removedAny"] = True
        return result
    return _ok()


def _is_valid_pid(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= _VALID_PID_MIN


def _validate_server_record(record):
    if not isinstance(record, dict):
        return False
    keys = set(record.keys())
    if keys != _SERVER_RECORD_KEYS:
        return False
    if record.get("schemaVersion") != PIN_SCHEMA_VERSION:
        return False
    slot_ref = record.get("slotRef")
    try:
        ref_slot, ref_gen = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        return False
    generation = record.get("generation")
    try:
        generation = pilot_slot.validate_generation(generation)
    except pilot_slot.PilotSlotError:
        return False
    if ref_gen != generation:
        return False
    socket_dir = record.get("socketDir")
    if not _is_str_path(socket_dir):
        return False
    if not _is_valid_pid(record.get("serverPid")):
        return False
    if not _is_valid_pid(record.get("browserPid")):
        return False
    try:
        validate_pin(record.get("pin"))
    except PilotBrowserError:
        return False
    if not _is_iso8601_utc(record.get("createdAt")):
        return False
    return True


def _default_ppid_of(pid):
    if not _is_valid_pid(pid):
        return None
    try:
        result = subprocess.run(
            ["ps", "-o", "ppid=", "-p", str(pid)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            timeout=20,
        )
        if result.returncode != 0:
            return None
        stdout = result.stdout
        if stdout is None or len(stdout) > 4096:
            return None
        text = stdout.decode("utf-8", errors="replace").strip()
        if not text or not text.isdigit():
            return None
        return int(text)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def assert_browser_is_server_child(server_pid, browser_pid, *, ppid_of=None):
    """Refuse when the browser process is not a direct child of the server."""
    if not _is_valid_pid(server_pid) or not _is_valid_pid(browser_pid):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)
    reader = ppid_of if ppid_of is not None else _default_ppid_of
    parent = reader(browser_pid)
    if parent is None:
        return _fail(REFUSAL_PID_UNREADABLE)
    if parent != server_pid:
        return _fail(REFUSAL_NOT_SERVER_CHILD)
    return _ok()


def begin_provision_server(journal_path, *, slot_ref, at, detail=None):
    """Write the provision begin record before any server/browser processes are spawned."""
    if not _is_str_path(journal_path):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)
    try:
        slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        return _fail(REFUSAL_OPERATION_SLOT_REF_INVALID)
    if not _is_iso8601_utc(at):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)

    formatted_ref = pilot_slot.format_slot_ref(slot, generation)
    begin_result = pilot_journal.begin_effect(
        journal_path,
        slot_ref=formatted_ref,
        kind=pilot_journal.KIND_BROWSER_SERVER_PROVISIONED,
        at=at,
        detail=detail,
    )
    if not begin_result["ok"]:
        return _fail(REFUSAL_SERVER_RECORD_INVALID, detail=begin_result.get("reason"))
    return _ok(effectId=begin_result["effectId"])


def provision_server(
    journal_path,
    *,
    slot_ref,
    generation,
    socket_dir,
    server_pid,
    browser_pid,
    pin,
    created_at,
    begin_at,
    effect_id,
    ppid_of=None,
):
    """Close a pre-spawn provision effect and validate the server+browser record.

    `effect_id` is required: it is the `effectId` returned by
    `begin_provision_server`, which journals before any process is spawned. There
    is no journal-after-the-fact ordering — omitting the argument is a TypeError,
    and passing a non-string or empty `effect_id` refuses.
    """
    if not _is_str_path(journal_path):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)
    try:
        slot, parsed_gen = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        return _fail(REFUSAL_OPERATION_SLOT_REF_INVALID)
    try:
        generation = pilot_slot.validate_generation(generation)
    except pilot_slot.PilotSlotError:
        return _fail(REFUSAL_SERVER_RECORD_INVALID)
    if parsed_gen != generation:
        return _fail(REFUSAL_SERVER_RECORD_INVALID)
    if not _is_str_path(socket_dir):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)
    if not _is_valid_pid(server_pid) or not _is_valid_pid(browser_pid):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)
    try:
        pin = validate_pin(pin)
    except PilotBrowserError:
        return _fail(REFUSAL_SERVER_RECORD_INVALID)
    if not _is_iso8601_utc(created_at) or not _is_iso8601_utc(begin_at):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)

    child_check = assert_browser_is_server_child(
        server_pid, browser_pid, ppid_of=ppid_of,
    )
    if not child_check["ok"]:
        return child_check

    formatted_ref = pilot_slot.format_slot_ref(slot, generation)
    record = {
        "schemaVersion": PIN_SCHEMA_VERSION,
        "slotRef": formatted_ref,
        "generation": generation,
        "socketDir": socket_dir,
        "serverPid": server_pid,
        "browserPid": browser_pid,
        "pin": dict(pin),
        "createdAt": created_at,
    }
    if not _validate_server_record(record):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)

    end_at = _later_timestamp(begin_at)

    if not isinstance(effect_id, str) or not effect_id:
        return _fail(REFUSAL_SERVER_RECORD_INVALID)
    end_result = pilot_journal.end_effect(
        journal_path,
        slot_ref=formatted_ref,
        effect_id=effect_id,
        kind=pilot_journal.KIND_BROWSER_SERVER_PROVISIONED,
        outcome=pilot_journal.OUTCOME_APPLIED,
        at=end_at,
    )
    if not end_result["ok"]:
        return _fail(REFUSAL_SERVER_RECORD_INVALID, detail=end_result.get("reason"))
    return _ok(record=record)


class _TeardownCleanupError(Exception):
    """Raised inside effect() so partial socket-dir cleanup journals as indeterminate."""


def _observe_terminal_exit(observer, pid):
    observation = observer(pid)
    if not isinstance(observation, dict):
        return _TERMINAL_EXIT_UNOBSERVED
    exited = observation.get("exited")
    if exited is not True:
        return _TERMINAL_EXIT_UNOBSERVED
    return observation.get("status")


def teardown_server(
    journal_path,
    *,
    server_record,
    torn_down_at,
    begin_at,
    observe_exit=None,
):
    """Tear down a server after an observed process exit; remove the socket directory."""
    if not _is_str_path(journal_path):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)
    if not _validate_server_record(server_record):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)
    if not _is_iso8601_utc(torn_down_at) or not _is_iso8601_utc(begin_at):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)

    server_pid = server_record["serverPid"]
    browser_pid = server_record["browserPid"]
    observer = observe_exit if observe_exit is not None else (lambda _pid: {"exited": False, "status": None})
    server_status = _observe_terminal_exit(observer, server_pid)
    if server_status is _TERMINAL_EXIT_UNOBSERVED:
        return _fail(REFUSAL_TERMINAL_STATE_UNOBSERVED)
    browser_status = _observe_terminal_exit(observer, browser_pid)
    if browser_status is _TERMINAL_EXIT_UNOBSERVED:
        return _fail(REFUSAL_TERMINAL_STATE_UNOBSERVED)

    socket_dir = server_record["socketDir"]
    slot_ref = server_record["slotRef"]

    end_at = _later_timestamp(begin_at)

    try:
        with pilot_journal.effect(
            journal_path,
            slot_ref=slot_ref,
            kind=pilot_journal.KIND_BROWSER_SERVER_TORN_DOWN,
            at=begin_at,
            detail={"serverPid": server_pid},
        ) as handle:
            remove_result = remove_socket_dir(socket_dir)
            if not remove_result["ok"]:
                if remove_result.get("removedAny"):
                    raise _TeardownCleanupError(remove_result["reason"])
                handle.mark_not_applied(at=end_at, reason=remove_result["reason"])
                return remove_result
            handle.mark_applied(at=end_at)
    except _TeardownCleanupError as exc:
        return _fail(str(exc))
    except pilot_journal.PilotJournalError as exc:
        return _fail(REFUSAL_SERVER_RECORD_INVALID, detail=str(exc.reason))

    receipt = {
        "slotRef": slot_ref,
        "generation": server_record["generation"],
        "socketDir": socket_dir,
        "serverPid": server_pid,
        "browserPid": browser_pid,
        "observedServerExitStatus": server_status,
        "observedBrowserExitStatus": browser_status,
        "socketDirRemoved": True,
        "torndownAt": torn_down_at,
    }
    return _ok(receipt=receipt)


def plan_topology(slot_ref, accounts):
    """Plan one server, one browser, and one context per account for a slot."""
    try:
        slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        return _fail(REFUSAL_OPERATION_SLOT_REF_INVALID)

    seen_keys = set()
    for entry in accounts:
        if isinstance(entry, dict):
            account = entry.get("account")
            if isinstance(account, str) and account:
                if account in seen_keys:
                    return _fail(REFUSAL_SHARED_CONTEXT_REFUSED)
                seen_keys.add(account)

    try:
        account_set = pilot_slot.slot_account_set(slot, generation, accounts)
    except pilot_slot.PilotSlotError as exc:
        return _fail(exc.reason)

    keys = pilot_slot.account_keys(account_set)
    contexts = [{"account": key, "contextKey": key} for key in keys]
    return _ok(
        slotRef=account_set["ref"],
        server={"count": 1},
        browser={"count": 1},
        contexts=contexts,
    )


def admit_server_registry(records):
    """Refuse ruled-out server/browser topology arrangements across live records."""
    if not isinstance(records, (list, tuple)):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)

    validated = []
    for record in records:
        if not _validate_server_record(record):
            return _fail(REFUSAL_SERVER_RECORD_INVALID)
        validated.append(record)

    slot_by_server_pid = {}
    slot_by_browser_pid = {}
    slots_seen = {}

    for record in validated:
        slot, _ = pilot_slot.parse_slot_ref(record["slotRef"])
        server_pid = record["serverPid"]
        browser_pid = record["browserPid"]

        if server_pid in slot_by_server_pid:
            if slot_by_server_pid[server_pid] != slot:
                return _fail(REFUSAL_SERVER_SHARED_ACROSS_SLOTS)
        else:
            slot_by_server_pid[server_pid] = slot

        if browser_pid in slot_by_browser_pid:
            if slot_by_browser_pid[browser_pid] != slot:
                return _fail(REFUSAL_SHARED_ACROSS_SLOTS)
        else:
            slot_by_browser_pid[browser_pid] = slot

        if slot in slots_seen:
            return _fail(REFUSAL_MULTIPLE_SERVERS_FOR_SLOT)
        slots_seen[slot] = record

    return _ok(accepted=len(validated))


def admit(operation_slot_ref, live_record, *, slots_dir=None):
    """Fencing chokepoint: refuse stale or mismatched browser operations."""
    if not _validate_server_record(live_record):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)

    if slots_dir is None:
        return _fail(REFUSAL_FENCING_SLOTS_DIR_REQUIRED)
    if not isinstance(slots_dir, str) or not slots_dir:
        return _fail(REFUSAL_FENCING_SLOTS_DIR_REQUIRED)
    if not os.path.isdir(slots_dir):
        return _fail(REFUSAL_FENCING_SLOTS_DIR_REQUIRED)

    try:
        op_slot, op_generation = pilot_slot.parse_slot_ref(operation_slot_ref)
    except pilot_slot.PilotSlotError:
        return _fail(REFUSAL_OPERATION_SLOT_REF_INVALID)

    rec_slot, _ = pilot_slot.parse_slot_ref(live_record["slotRef"])
    if op_slot != rec_slot:
        return _fail(REFUSAL_OPERATION_SLOT_MISMATCH)

    record_path = pilot_lifecycle.record_path(slots_dir, rec_slot)
    disk = pilot_lifecycle.read_record(record_path)
    if not disk["ok"]:
        return _fail(REFUSAL_SERVER_RECORD_STALE, slotRef=live_record["slotRef"])

    disk_record = disk["record"]
    disk_generation = disk_record["generation"]
    if live_record["generation"] != disk_generation:
        return _fail(REFUSAL_SERVER_RECORD_STALE, slotRef=live_record["slotRef"])

    disk_state = disk_record.get("state")
    if disk_state not in _LIVE_SLOT_STATES:
        return _fail(REFUSAL_SLOT_STATE_NOT_LIVE, slotRef=live_record["slotRef"])

    gen_check = pilot_lifecycle.generation_check(op_generation, disk_generation)
    if not gen_check["ok"]:
        return _fail(gen_check["reason"], slotRef=live_record["slotRef"])

    return _ok(slotRef=live_record["slotRef"])
