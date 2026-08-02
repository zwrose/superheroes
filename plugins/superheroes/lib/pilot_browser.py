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
import threading
import uuid
from datetime import datetime, timedelta

import pilot_journal
import pilot_lifecycle
import pilot_slot

PIN_SCHEMA_VERSION = 1

SUN_PATH_MAX = {"darwin": 104, "linux": 108}
MAX_SOCKET_FILENAME = 64

_SOCKET_DIR_PREFIX = "pb-"

REFUSAL_PIN_INVALID = "browser-pin-invalid"
REFUSAL_PIN_OBSERVER_INVALID = "browser-pin-observer-invalid"
REFUSAL_PIN_OBSERVER_FAILED = "browser-pin-observer-failed"
REFUSAL_PIN_VERSION_MISMATCH = "browser-pin-version-mismatch"
REFUSAL_PIN_INTEGRITY_MISMATCH = "browser-pin-integrity-mismatch"

REFUSAL_SOCKET_PATH_TOO_LONG = "browser-socket-path-too-long"
REFUSAL_SOCKET_BASE_IN_WORKTREE = "browser-socket-base-in-worktree"
REFUSAL_SOCKET_DIR_EXISTS = "browser-socket-dir-exists"
REFUSAL_SOCKET_DIR_UNSAFE = "browser-socket-dir-unsafe"
REFUSAL_SOCKET_DIR_NOT_DIRECTORY = "browser-socket-dir-not-directory"
REFUSAL_SOCKET_DIR_UNREMOVABLE = "browser-socket-dir-unremovable"

REFUSAL_SERVER_RECORD_INVALID = "browser-server-record-invalid"
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


def _validate_observer(observer):
    if not isinstance(observer, dict) or set(observer.keys()) != frozenset({"command"}):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)
    command = observer["command"]
    if not isinstance(command, list) or not command:
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)
    for part in command:
        if not isinstance(part, str) or not part:
            raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)


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


def _terminate_and_wait(proc):
    with contextlib.suppress(Exception):
        proc.kill()
        proc.wait(timeout=5)


def _run_bounded_observer(command, *, run_cwd, env, timeout_seconds, max_output_bytes):
  # bite-axis: observer execution — subprocess failure, oversized output, or non-single-line
  # UTF-8 stdout yields REFUSAL_PIN_OBSERVER_FAILED; only clean one-line output is returned.
    proc = subprocess.Popen(
        command,
        cwd=run_cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        shell=False,
        env=env,
    )
    try:
        stdout_holder = []
        read_error = []

        def _read_stdout():
            try:
                stdout_holder.append(proc.stdout.read(max_output_bytes + 1))
            except Exception as exc:
                read_error.append(exc)

        reader = threading.Thread(target=_read_stdout, daemon=True)
        reader.start()
        reader.join(timeout=timeout_seconds)

        if reader.is_alive():
            _terminate_and_wait(proc)
            return None

        if read_error:
            _terminate_and_wait(proc)
            return None

        stdout = stdout_holder[0] if stdout_holder else b""

        if len(stdout) > max_output_bytes:
            _terminate_and_wait(proc)
            return None

        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            _terminate_and_wait(proc)
            return None

        if proc.returncode != 0:
            return None

        return stdout
    except Exception:
        _terminate_and_wait(proc)
        return None
    finally:
        if proc.poll() is None:
            _terminate_and_wait(proc)
        if proc.stdout:
            proc.stdout.close()


def verify_pin(pin, observer, *, run_cwd, timeout_seconds=20, max_output_bytes=4096):
    """Observe pin integrity via a bounded subprocess and compare version and digest."""
    pin = validate_pin(pin)
    _validate_observer(observer)
    if not _is_str_path(run_cwd):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)
    if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)
    if not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool):
        raise PilotBrowserError(REFUSAL_PIN_OBSERVER_INVALID)

    command = observer["command"]
    env = dict(os.environ)
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

    if worktree_root is not None:
        if not _is_str_path(worktree_root):
            return _fail(REFUSAL_SOCKET_BASE_IN_WORKTREE)
        if _path_related(base, worktree_root):
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
            sub_entries = os.listdir(entry_path)
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
    try:
        entries = os.listdir(path)
    except OSError:
        return _fail(REFUSAL_SOCKET_DIR_UNREMOVABLE)
    for name in entries:
        if not _remove_socket_dir_entry(path, name):
            return _fail(REFUSAL_SOCKET_DIR_UNREMOVABLE)
    try:
        os.rmdir(path)
    except OSError:
        return _fail(REFUSAL_SOCKET_DIR_UNREMOVABLE)
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
    ppid_of=None,
):
    """Journal and validate a per-generation server+browser provisioning."""
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

    try:
        with pilot_journal.effect(
            journal_path,
            slot_ref=formatted_ref,
            kind=pilot_journal.KIND_BROWSER_SERVER_PROVISIONED,
            at=begin_at,
            detail={"socketDir": socket_dir, "serverPid": server_pid},
        ) as handle:
            handle.mark_applied(at=end_at)
    except pilot_journal.PilotJournalError as exc:
        return _fail(REFUSAL_SERVER_RECORD_INVALID, detail=str(exc.reason))

    return _ok(record=record)


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
    observer = observe_exit if observe_exit is not None else (lambda _pid: {"exited": False, "status": None})
    observation = observer(server_pid)
    if not isinstance(observation, dict):
        return _fail(REFUSAL_TERMINAL_STATE_UNOBSERVED)
    exited = observation.get("exited")
    status = observation.get("status")
    # Never infer exit from socket file absence — that is a second read of the same
    # liveness marker the design refuses.
    if exited is not True:
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
                handle.mark_not_applied(at=end_at, reason=remove_result["reason"])
                return remove_result
            handle.mark_applied(at=end_at)
    except pilot_journal.PilotJournalError as exc:
        return _fail(REFUSAL_SERVER_RECORD_INVALID, detail=str(exc.reason))

    receipt = {
        "slotRef": slot_ref,
        "generation": server_record["generation"],
        "socketDir": socket_dir,
        "serverPid": server_pid,
        "browserPid": server_record["browserPid"],
        "observedExitStatus": status,
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


def admit(operation_slot_ref, live_record):
    """Fencing chokepoint: refuse stale or mismatched browser operations."""
    if not _validate_server_record(live_record):
        return _fail(REFUSAL_SERVER_RECORD_INVALID)

    try:
        op_slot, op_generation = pilot_slot.parse_slot_ref(operation_slot_ref)
    except pilot_slot.PilotSlotError:
        return _fail(REFUSAL_OPERATION_SLOT_REF_INVALID)

    rec_slot, _ = pilot_slot.parse_slot_ref(live_record["slotRef"])
    if op_slot != rec_slot:
        return _fail(REFUSAL_OPERATION_SLOT_MISMATCH)

    rec_generation = live_record["generation"]
    gen_check = pilot_lifecycle.generation_check(op_generation, rec_generation)
    if not gen_check["ok"]:
        return _fail(gen_check["reason"], slotRef=live_record["slotRef"])

    return _ok(slotRef=live_record["slotRef"])
