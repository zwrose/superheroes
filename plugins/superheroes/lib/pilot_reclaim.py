"""Pilot slot reclaim — quarantine, sweep, and deletion authorization.

When a pilot slot is reclaimed from a stale occupant, the occupant's payload directory
is renamed aside into quarantine, never deleted. Permanent deletion requires both a
72-hour grace period and a terminal receipt proving an independently observed process
exit.
"""
import errno
import json
import os
import re
import shutil
import stat
from datetime import datetime, timedelta

import pilot_slot
import store_core

SCHEMA = 1
GRACE_HOURS = 72
QUARANTINE_DIR_NAME = ".pilot-quarantine"
SIDECAR_SUFFIX = ".quarantine.json"
SEGMENT_WARN_COUNT = 20

MOVE_PENDING = "pending"
MOVE_MOVED = "moved"
MOVE_STATES = frozenset({MOVE_PENDING, MOVE_MOVED})

STATUS_QUARANTINED = "quarantined"
STATUS_DELETION_AUTHORIZED = "deletion-authorized"
STATUS_DELETED = "deleted"
SIDECAR_STATUSES = frozenset({
    STATUS_QUARANTINED,
    STATUS_DELETION_AUTHORIZED,
    STATUS_DELETED,
})

LIVENESS_SOURCES = frozenset({
    "heartbeat-record", "mtime", "process-table", "lock-probe",
})
TERMINAL_SOURCES = frozenset({"process-exit-status"})

REASON_SLOTS_DIR_INVALID = "reclaim-slots-dir-invalid"
REASON_SOURCE_INVALID = "reclaim-source-invalid"
REASON_SOURCE_INSIDE_SLOT_STORE = "reclaim-source-inside-slot-store"
REASON_SLOT_REF_INVALID = "reclaim-slot-ref-invalid"
REASON_REASON_INVALID = "reclaim-reason-invalid"
REASON_OCCUPANT_INVALID = "reclaim-occupant-invalid"
REASON_NOW_INVALID = "reclaim-now-invalid"
REASON_ENTRY_EXISTS = "reclaim-entry-exists"
REASON_CROSS_DEVICE = "reclaim-cross-device"
REASON_RENAME_FAILED = "reclaim-rename-failed"
REASON_SIDECAR_WRITE_FAILED = "reclaim-sidecar-write-failed"
REASON_SIDECAR_ABSENT = "reclaim-sidecar-absent"
REASON_SIDECAR_UNREADABLE = "reclaim-sidecar-unreadable"
REASON_SIDECAR_INVALID = "reclaim-sidecar-invalid"
REASON_GRACE_NOT_ELAPSED = "reclaim-grace-not-elapsed"
REASON_RECEIPT_INVALID = "reclaim-receipt-invalid"
REASON_RECEIPT_SOURCE_NOT_TERMINAL = "reclaim-receipt-source-not-terminal"
REASON_RECEIPT_NOT_INDEPENDENT = "reclaim-receipt-not-independent"
REASON_OCCUPANT_UNBOUND = "reclaim-occupant-unbound"
REASON_RECEIPT_BINDING_MISMATCH = "reclaim-receipt-binding-mismatch"
REASON_RECEIPT_PREDATES_LIVENESS = "reclaim-receipt-predates-liveness"
REASON_ENTRY_NOT_MOVED = "reclaim-entry-not-moved"
REASON_STATUS_NOT_DELETABLE = "reclaim-status-not-deletable"
REASON_DELETE_FAILED = "reclaim-delete-failed"
REASON_QUARANTINE_DIR_UNREADABLE = "reclaim-quarantine-dir-unreadable"
REASON_JOURNAL_SEGMENTS_HIGH = "reclaim-journal-segments-high"

_OCCUPANT_KEYS = frozenset({"pid", "processInstance", "livenessSource", "observedAt"})
_SIDECAR_REQUIRED_KEYS = frozenset({
    "schemaVersion", "entryName", "originalPath", "slot", "slotRef", "generation",
    "reason", "quarantinedAt", "expiresAt", "move", "status", "occupant",
})
_RECEIPT_REQUIRED_KEYS = frozenset({
    "schemaVersion", "source", "pid", "processInstance", "waitStatus",
    "entryName", "slotRef", "observedAt",
})
_REASON_MAX_LEN = 500
_PROCESS_INSTANCE_MAX_LEN = 200
_JOURNAL_SEGMENT_RE = re.compile(r"^journal\.\d+\.ndjson\Z")


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


def _is_exact_int(value, minimum=None):
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    if minimum is not None and value < minimum:
        return False
    return True


def _is_member(value, members):
    return isinstance(value, str) and value in members


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


def _parse_iso8601_utc(value):
    return datetime.fromisoformat(value.strip()[:-1] + "+00:00")


def _compact_timestamp(now):
    return now.replace("-", "").replace(":", "").replace(".", "")


def _expires_at_informational(now):
    """Compute expiresAt for the sidecar (informational only).

    No predicate in this module ever reads expiresAt — the grace period is always
    recomputed from quarantinedAt.
    """
    return _add_hours_iso8601(now, GRACE_HOURS)


def _add_hours_iso8601(now, hours):
    dt = _parse_iso8601_utc(now)
    return (dt + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _fsync_dir(dir_path):
    dir_fd = os.open(dir_path, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _path_contained_in(path, container):
    """True when path is equal to container or strictly inside it."""
    try:
        real_path = os.path.realpath(path)
        real_container = os.path.realpath(container)
    except OSError:
        return False
    if real_path == real_container:
        return True
    try:
        common = os.path.commonpath([real_path, real_container])
    except ValueError:
        return False
    return common == real_container


def _path_is_ancestor_of(path, descendant):
    """True when path is a strict ancestor of descendant."""
    try:
        real_path = os.path.realpath(path)
        real_desc = os.path.realpath(descendant)
    except OSError:
        return False
    if real_path == real_desc:
        return False
    try:
        common = os.path.commonpath([real_path, real_desc])
    except ValueError:
        return False
    return common == real_path


def _source_inside_slot_store(source_path, slots_dir_path):
    if _path_contained_in(source_path, slots_dir_path):
        return True
    if _path_is_ancestor_of(source_path, slots_dir_path):
        return True
    quarantine = os.path.join(slots_dir_path, QUARANTINE_DIR_NAME)
    if _path_contained_in(source_path, quarantine):
        return True
    return False


def _validate_slots_dir(slots_dir_path):
    if not _is_str_path(slots_dir_path) or not slots_dir_path:
        return _fail(REASON_SLOTS_DIR_INVALID)
    return None


def _validate_source_path(source_path):
    if not _is_str_path(source_path):
        return _fail(REASON_SOURCE_INVALID)
    if not os.path.isabs(source_path):
        return _fail(REASON_SOURCE_INVALID)
    if not os.path.lexists(source_path):
        return _fail(REASON_SOURCE_INVALID)
    if os.path.islink(source_path):
        return _fail(REASON_SOURCE_INVALID)
    if not os.path.isdir(source_path):
        return _fail(REASON_SOURCE_INVALID)
    return None


def _is_valid_reason(reason):
    return _is_str_path(reason) and bool(reason) and len(reason) <= _REASON_MAX_LEN


def _validate_reason(reason):
    if not _is_valid_reason(reason):
        return _fail(REASON_REASON_INVALID)
    return None


def _validate_now(now):
    if not _is_iso8601_utc(now):
        return _fail(REASON_NOW_INVALID)
    return None


def _validate_slot_ref(slot_ref):
    try:
        pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        return _fail(REASON_SLOT_REF_INVALID)
    return None


def _occupant_dict(occupant):
    return {
        "pid": occupant["pid"],
        "processInstance": occupant["processInstance"],
        "livenessSource": occupant["livenessSource"],
        "observedAt": occupant["observedAt"],
    }


def quarantine_dir(slots_dir_path):
    """Return the quarantine directory path under slots_dir_path."""
    refused = _validate_slots_dir(slots_dir_path)
    if refused is not None:
        return refused
    return _ok(path=os.path.join(slots_dir_path, QUARANTINE_DIR_NAME))


def validate_occupant(occupant):
    """Validate an occupant block and return a fresh copy."""
    if not isinstance(occupant, dict) or set(occupant.keys()) != _OCCUPANT_KEYS:
        return _fail(REASON_OCCUPANT_INVALID, occupant=None)
    pid = occupant["pid"]
    if pid is not None and not _is_exact_int(pid, minimum=1):
        return _fail(REASON_OCCUPANT_INVALID, occupant=None)
    process_instance = occupant["processInstance"]
    if process_instance is not None:
        if not _is_str_path(process_instance) or not process_instance:
            return _fail(REASON_OCCUPANT_INVALID, occupant=None)
        if len(process_instance) > _PROCESS_INSTANCE_MAX_LEN:
            return _fail(REASON_OCCUPANT_INVALID, occupant=None)
    liveness_source = occupant["livenessSource"]
    if not _is_member(liveness_source, LIVENESS_SOURCES):
        return _fail(REASON_OCCUPANT_INVALID, occupant=None)
    observed_at = occupant["observedAt"]
    if not _is_iso8601_utc(observed_at):
        return _fail(REASON_OCCUPANT_INVALID, occupant=None)
    return _ok(occupant=_occupant_dict(occupant))


def terminal_receipt(*, pid, process_instance, wait_status, entry_name, slot_ref,
                     observed_at):
    """Mint a terminal process-exit receipt.

    The caller must mint this at its real wait/reap seam — immediately after
    ``os.waitpid``/``Popen.wait()`` returns for that process — and nowhere else.
    """
    if not _is_exact_int(pid, minimum=1):
        return _fail(REASON_RECEIPT_INVALID, receipt=None)
    if not _is_str_path(process_instance) or not process_instance:
        return _fail(REASON_RECEIPT_INVALID, receipt=None)
    if len(process_instance) > _PROCESS_INSTANCE_MAX_LEN:
        return _fail(REASON_RECEIPT_INVALID, receipt=None)
    if not _is_exact_int(wait_status):
        return _fail(REASON_RECEIPT_INVALID, receipt=None)
    if not _is_str_path(entry_name) or not entry_name:
        return _fail(REASON_RECEIPT_INVALID, receipt=None)
    try:
        pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        return _fail(REASON_RECEIPT_INVALID, receipt=None)
    if not _is_iso8601_utc(observed_at):
        return _fail(REASON_RECEIPT_INVALID, receipt=None)
    receipt = {
        "schemaVersion": SCHEMA,
        "source": "process-exit-status",
        "pid": pid,
        "processInstance": process_instance,
        "waitStatus": wait_status,
        "entryName": entry_name,
        "slotRef": slot_ref,
        "observedAt": observed_at,
    }
    return _ok(receipt=receipt)


def _validate_receipt_structural(receipt):
    if not isinstance(receipt, dict) or set(receipt.keys()) != _RECEIPT_REQUIRED_KEYS:
        return False
    if receipt["schemaVersion"] != SCHEMA:
        return False
    if not _is_str_path(receipt["source"]) or not receipt["source"]:
        return False
    if not _is_exact_int(receipt["pid"], minimum=1):
        return False
    process_instance = receipt["processInstance"]
    if not _is_str_path(process_instance) or not process_instance:
        return False
    if len(process_instance) > _PROCESS_INSTANCE_MAX_LEN:
        return False
    if not _is_exact_int(receipt["waitStatus"]):
        return False
    if not _is_str_path(receipt["entryName"]) or not receipt["entryName"]:
        return False
    try:
        pilot_slot.parse_slot_ref(receipt["slotRef"])
    except pilot_slot.PilotSlotError:
        return False
    if not _is_iso8601_utc(receipt["observedAt"]):
        return False
    return True


def _validate_receipt_dict(receipt):
    if not _validate_receipt_structural(receipt):
        return False
    if not _is_member(receipt["source"], TERMINAL_SOURCES):
        return False
    return True


def _validate_sidecar_dict(sidecar):
    if not isinstance(sidecar, dict):
        return False
    if not _SIDECAR_REQUIRED_KEYS.issubset(set(sidecar.keys())):
        return False
    extra_keys = set(sidecar.keys()) - _SIDECAR_REQUIRED_KEYS
    allowed_extra = frozenset({"terminalReceipt", "deletionAuthorizedAt", "deletedAt"})
    if not extra_keys.issubset(allowed_extra):
        return False
    if sidecar["schemaVersion"] != SCHEMA:
        return False
    if not _is_str_path(sidecar["entryName"]) or not sidecar["entryName"]:
        return False
    if not _is_str_path(sidecar["originalPath"]) or not sidecar["originalPath"]:
        return False
    try:
        pilot_slot.validate_slot_id(sidecar["slot"])
    except pilot_slot.PilotSlotError:
        return False
    try:
        pilot_slot.validate_generation(sidecar["generation"])
    except pilot_slot.PilotSlotError:
        return False
    if not _is_valid_reason(sidecar["reason"]):
        return False
    if not _is_iso8601_utc(sidecar["quarantinedAt"]):
        return False
    if not _is_iso8601_utc(sidecar["expiresAt"]):
        return False
    if not _is_member(sidecar["move"], MOVE_STATES):
        return False
    if not _is_member(sidecar["status"], SIDECAR_STATUSES):
        return False
    occ = validate_occupant(sidecar["occupant"])
    if not occ["ok"]:
        return False
    try:
        parsed_slot, parsed_gen = pilot_slot.parse_slot_ref(sidecar["slotRef"])
    except pilot_slot.PilotSlotError:
        return False
    if parsed_slot != sidecar["slot"] or parsed_gen != sidecar["generation"]:
        return False
    return True


def _sidecar_entry_name(path):
    base = os.path.basename(path)
    if not base.endswith(SIDECAR_SUFFIX):
        return None
    return base[: -len(SIDECAR_SUFFIX)]


def _write_sidecar(path, sidecar):
    try:
        text = json.dumps(sidecar, indent=2, sort_keys=True, allow_nan=False) + "\n"
        store_core.atomic_write(path, text)
        _fsync_dir(os.path.dirname(os.path.abspath(path)))
    except OSError:
        return False
    return True


def quarantine_entry(slots_dir_path, source_path, *, slot_ref, reason, occupant, now):
    """Rename a stale occupant payload into quarantine with a durable sidecar."""
    entry_name = None
    entry_path = None
    sidecar_path = None

    refused = _validate_slots_dir(slots_dir_path)
    if refused is not None:
        return refused
    refused = _validate_source_path(source_path)
    if refused is not None:
        return refused
    if _source_inside_slot_store(source_path, slots_dir_path):
        return _fail(
            REASON_SOURCE_INSIDE_SLOT_STORE,
            entryName=None, entryPath=None, sidecarPath=None,
        )
    refused = _validate_slot_ref(slot_ref)
    if refused is not None:
        return refused
    refused = _validate_reason(reason)
    if refused is not None:
        return refused
    occ = validate_occupant(occupant)
    if not occ["ok"]:
        return _fail(
            REASON_OCCUPANT_INVALID,
            entryName=None, entryPath=None, sidecarPath=None,
        )
    refused = _validate_now(now)
    if refused is not None:
        return refused

    slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    compact = _compact_timestamp(now)
    entry_name = "%s-gen%d-%s" % (slot, generation, compact)

    qdir_result = quarantine_dir(slots_dir_path)
    qdir = qdir_result["path"]
    entry_path = os.path.join(qdir, entry_name)
    sidecar_path = entry_path + SIDECAR_SUFFIX

    try:
        os.makedirs(qdir, exist_ok=True)
    except OSError:
        return _fail(
            REASON_SIDECAR_WRITE_FAILED,
            entryName=None, entryPath=None, sidecarPath=None,
        )

    if os.path.lexists(entry_path) or os.path.lexists(sidecar_path):
        return _fail(
            REASON_ENTRY_EXISTS,
            entryName=None, entryPath=None, sidecarPath=None,
        )

    try:
        original_path = os.path.realpath(source_path)
    except OSError:
        return _fail(
            REASON_SOURCE_INVALID,
            entryName=None, entryPath=None, sidecarPath=None,
        )

    pending_sidecar = {
        "schemaVersion": SCHEMA,
        "entryName": entry_name,
        "originalPath": original_path,
        "slot": slot,
        "slotRef": slot_ref,
        "generation": generation,
        "reason": reason,
        "quarantinedAt": now,
        "expiresAt": _expires_at_informational(now),
        "move": MOVE_PENDING,
        "status": STATUS_QUARANTINED,
        "occupant": occ["occupant"],
    }
    if not _write_sidecar(sidecar_path, pending_sidecar):
        return _fail(
            REASON_SIDECAR_WRITE_FAILED,
            entryName=None, entryPath=None, sidecarPath=None,
        )

    try:
        os.rename(source_path, entry_path)
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            return _fail(
                REASON_CROSS_DEVICE,
                entryName=None, entryPath=None, sidecarPath=None,
            )
        return _fail(
            REASON_RENAME_FAILED,
            entryName=None, entryPath=None, sidecarPath=None,
        )

    try:
        source_parent = os.path.dirname(os.path.abspath(source_path)) or "."
        _fsync_dir(source_parent)
        _fsync_dir(qdir)
    except OSError:
        pass

    moved_sidecar = dict(pending_sidecar)
    moved_sidecar["move"] = MOVE_MOVED
    if not _write_sidecar(sidecar_path, moved_sidecar):
        return _fail(
            REASON_SIDECAR_WRITE_FAILED,
            entryName=entry_name, entryPath=entry_path, sidecarPath=sidecar_path,
        )

    return _ok(
        entryName=entry_name,
        entryPath=entry_path,
        sidecarPath=sidecar_path,
    )


def read_sidecar(path):
    """Load and validate a quarantine sidecar. Never raises."""
    if not _is_str_path(path):
        return _fail(REASON_SIDECAR_UNREADABLE, sidecar=None)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return _fail(REASON_SIDECAR_ABSENT, sidecar=None)
    except OSError:
        return _fail(REASON_SIDECAR_UNREADABLE, sidecar=None)
    try:
        stat_result = os.fstat(fd)
        if not stat.S_ISREG(stat_result.st_mode):
            return _fail(REASON_SIDECAR_UNREADABLE, sidecar=None)
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks).decode("utf-8")
    except OSError:
        return _fail(REASON_SIDECAR_UNREADABLE, sidecar=None)
    except UnicodeDecodeError:
        return _fail(REASON_SIDECAR_UNREADABLE, sidecar=None)
    finally:
        os.close(fd)
    try:
        parsed = json.loads(raw)
    except ValueError:
        return _fail(REASON_SIDECAR_INVALID, sidecar=None)
    if not _validate_sidecar_dict(parsed):
        return _fail(REASON_SIDECAR_INVALID, sidecar=None)
    return _ok(sidecar=parsed)


def authorize_deletion(sidecar, receipt, *, now):
    """Pure authorization check — touches no filesystem."""
    if not _validate_sidecar_dict(sidecar):
        return _fail(REASON_SIDECAR_INVALID)
    refused = _validate_now(now)
    if refused is not None:
        return refused
    if sidecar["move"] != MOVE_MOVED:
        return _fail(REASON_ENTRY_NOT_MOVED)
    if sidecar["status"] == STATUS_DELETED:
        return _fail(REASON_STATUS_NOT_DELETABLE)
    quarantined_at = _parse_iso8601_utc(sidecar["quarantinedAt"])
    now_dt = _parse_iso8601_utc(now)
    grace_end = quarantined_at + timedelta(hours=GRACE_HOURS)
    if now_dt < grace_end:
        return _fail(REASON_GRACE_NOT_ELAPSED)
    if not _validate_receipt_structural(receipt):
        return _fail(REASON_RECEIPT_INVALID)
    if receipt["source"] not in TERMINAL_SOURCES:
        return _fail(REASON_RECEIPT_SOURCE_NOT_TERMINAL)
    occupant = sidecar["occupant"]
    if receipt["source"] == occupant["livenessSource"]:
        return _fail(REASON_RECEIPT_NOT_INDEPENDENT)
    if occupant["pid"] is None or occupant["processInstance"] is None:
        return _fail(REASON_OCCUPANT_UNBOUND)
    if (receipt["pid"] != occupant["pid"]
            or receipt["processInstance"] != occupant["processInstance"]
            or receipt["entryName"] != sidecar["entryName"]
            or receipt["slotRef"] != sidecar["slotRef"]):
        return _fail(REASON_RECEIPT_BINDING_MISMATCH)
    receipt_at = _parse_iso8601_utc(receipt["observedAt"])
    occupant_at = _parse_iso8601_utc(occupant["observedAt"])
    if receipt_at < occupant_at:
        return _fail(REASON_RECEIPT_PREDATES_LIVENESS)
    return _ok()


def _grace_elapsed(sidecar, now):
    quarantined_at = _parse_iso8601_utc(sidecar["quarantinedAt"])
    now_dt = _parse_iso8601_utc(now)
    return now_dt >= quarantined_at + timedelta(hours=GRACE_HOURS)


def _list_entry(entry_name, sidecar_path, entry_path, reason=None):
    return {
        "entryName": entry_name,
        "sidecarPath": sidecar_path,
        "entryPath": entry_path,
        "reason": reason,
    }


def _scan_journal_segments(slots_dir_path, warned):
    try:
        names = os.listdir(slots_dir_path)
    except OSError:
        return
    for name in names:
        if name.startswith("."):
            continue
        slot_dir = os.path.join(slots_dir_path, name)
        if not os.path.isdir(slot_dir):
            continue
        try:
            pilot_slot.validate_slot_id(name)
        except pilot_slot.PilotSlotError:
            continue
        try:
            files = os.listdir(slot_dir)
        except OSError:
            continue
        segment_count = sum(
            1 for f in files if _JOURNAL_SEGMENT_RE.match(f)
        )
        if segment_count >= SEGMENT_WARN_COUNT:
            warned.append({
                "slot": name,
                "segmentCount": segment_count,
                "reason": REASON_JOURNAL_SEGMENTS_HIGH,
            })


def _delete_entry(qdir, sidecar, sidecar_path, entry_path, receipt, now,
                  deleted, warned, retained):
    entry_name = sidecar["entryName"]
    authorized = dict(sidecar)
    authorized["status"] = STATUS_DELETION_AUTHORIZED
    authorized["terminalReceipt"] = receipt
    authorized["deletionAuthorizedAt"] = now
    if not _write_sidecar(sidecar_path, authorized):
        retained.append(_list_entry(
            entry_name, sidecar_path, entry_path,
            REASON_SIDECAR_WRITE_FAILED,
        ))
        return
    try:
        shutil.rmtree(entry_path)
    except OSError:
        warned.append(_list_entry(
            entry_name, sidecar_path, entry_path, REASON_DELETE_FAILED,
        ))
        retained.append(_list_entry(
            entry_name, sidecar_path, entry_path, REASON_DELETE_FAILED,
        ))
        return
    tombstone = dict(authorized)
    tombstone["status"] = STATUS_DELETED
    tombstone["deletedAt"] = now
    if not _write_sidecar(sidecar_path, tombstone):
        warned.append(_list_entry(
            entry_name, sidecar_path, entry_path, REASON_SIDECAR_WRITE_FAILED,
        ))
        retained.append(_list_entry(
            entry_name, sidecar_path, entry_path, REASON_SIDECAR_WRITE_FAILED,
        ))
        return
    deleted.append(_list_entry(entry_name, sidecar_path, entry_path, None))


def sweep(slots_dir_path, *, now, receipts=None):
    """Sweep the quarantine area — warn, retain, or delete per policy."""
    deleted = []
    warned = []
    retained = []
    refusals = []

    refused = _validate_slots_dir(slots_dir_path)
    if refused is not None:
        return refused
    refused = _validate_now(now)
    if refused is not None:
        return refused
    if receipts is not None and not isinstance(receipts, dict):
        return _fail(
            REASON_RECEIPT_INVALID,
            deleted=deleted, warned=warned, retained=retained, refusals=refusals,
        )
    if receipts is None:
        receipts = {}

    qdir_result = quarantine_dir(slots_dir_path)
    qdir = qdir_result["path"]

    if not os.path.isdir(qdir):
        _scan_journal_segments(slots_dir_path, warned)
        return _ok(deleted=deleted, warned=warned, retained=retained, refusals=refusals)

    try:
        entries = os.listdir(qdir)
    except OSError:
        return _fail(
            REASON_QUARANTINE_DIR_UNREADABLE,
            deleted=deleted, warned=warned, retained=retained, refusals=refusals,
        )

    sidecar_paths = {}
    payload_dirs = set()
    for name in entries:
        full = os.path.join(qdir, name)
        if name.endswith(SIDECAR_SUFFIX) and os.path.isfile(full):
            en = _sidecar_entry_name(name)
            if en is not None:
                sidecar_paths[en] = full
        elif os.path.isdir(full) and not name.endswith(SIDECAR_SUFFIX):
            payload_dirs.add(name)

    for entry_name in sorted(payload_dirs):
        if entry_name not in sidecar_paths:
            entry_path = os.path.join(qdir, entry_name)
            warned.append(_list_entry(
                entry_name, "", entry_path, REASON_SIDECAR_ABSENT,
            ))
            retained.append(_list_entry(
                entry_name, "", entry_path, REASON_SIDECAR_ABSENT,
            ))

    for entry_name in sorted(sidecar_paths):
        sidecar_path = sidecar_paths[entry_name]
        entry_path = os.path.join(qdir, entry_name)

        loaded = read_sidecar(sidecar_path)
        if not loaded["ok"]:
            warned.append(_list_entry(
                entry_name, sidecar_path, entry_path, loaded["reason"],
            ))
            retained.append(_list_entry(
                entry_name, sidecar_path, entry_path, loaded["reason"],
            ))
            continue

        sidecar = loaded["sidecar"]

        if sidecar["move"] == MOVE_PENDING:
            if os.path.lexists(entry_path):
                repaired = dict(sidecar)
                repaired["move"] = MOVE_MOVED
                if _write_sidecar(sidecar_path, repaired):
                    sidecar = repaired
                warned.append(_list_entry(
                    entry_name, sidecar_path, entry_path, None,
                ))
                retained.append(_list_entry(
                    entry_name, sidecar_path, entry_path, None,
                ))
                continue
            warned.append(_list_entry(
                entry_name, sidecar_path, entry_path, REASON_ENTRY_NOT_MOVED,
            ))
            retained.append(_list_entry(
                entry_name, sidecar_path, entry_path, REASON_ENTRY_NOT_MOVED,
            ))
            continue

        if sidecar["status"] == STATUS_DELETED:
            retained.append(_list_entry(
                entry_name, sidecar_path, entry_path, None,
            ))
            continue

        if sidecar["status"] == STATUS_DELETION_AUTHORIZED:
            if os.path.lexists(entry_path):
                receipt = sidecar.get("terminalReceipt")
                _delete_entry(
                    qdir, sidecar, sidecar_path, entry_path, receipt, now,
                    deleted, warned, retained,
                )
            else:
                tombstone = dict(sidecar)
                tombstone["status"] = STATUS_DELETED
                tombstone["deletedAt"] = now
                _write_sidecar(sidecar_path, tombstone)
                retained.append(_list_entry(
                    entry_name, sidecar_path, entry_path, None,
                ))
            continue

        receipt = receipts.get(entry_name)
        if receipt is not None:
            auth = authorize_deletion(sidecar, receipt, now=now)
            if auth["ok"]:
                _delete_entry(
                    qdir, sidecar, sidecar_path, entry_path, receipt, now,
                    deleted, warned, retained,
                )
            else:
                retained.append(_list_entry(
                    entry_name, sidecar_path, entry_path, auth["reason"],
                ))
                if _grace_elapsed(sidecar, now):
                    warned.append(_list_entry(
                        entry_name, sidecar_path, entry_path, auth["reason"],
                    ))
            continue

        retained.append(_list_entry(
            entry_name, sidecar_path, entry_path, None,
        ))
        if _grace_elapsed(sidecar, now):
            warned.append(_list_entry(
                entry_name, sidecar_path, entry_path, REASON_GRACE_NOT_ELAPSED,
            ))

    _scan_journal_segments(slots_dir_path, warned)
    return _ok(deleted=deleted, warned=warned, retained=retained, refusals=refusals)
