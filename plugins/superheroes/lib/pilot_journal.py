"""Pilot provisioning journal — durable effect records and partial-failure reports.

Append-only journal written before AND after each shared effect so crash windows
replay honestly as possibly-applied rather than never-happened.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import stat
import threading
import time
import uuid
from datetime import datetime

import pilot_slot

SCHEMA = 1

PHASE_BEGIN = "begin"
PHASE_END = "end"
PHASES = frozenset({PHASE_BEGIN, PHASE_END})

KIND_WORKTREE_CREATED = "worktree-created"
KIND_APP_STARTED = "app-started"
KIND_CREDENTIAL_MINTED = "credential-minted"
KIND_CREDENTIAL_SEEDED = "credential-seeded"
KIND_NAMESPACE_TOUCHED = "namespace-touched"
KIND_PROJECT_DECLARED = "project-declared"
KIND_BROWSER_SERVER_PROVISIONED = "browser-server-provisioned"
KIND_BROWSER_SERVER_TORN_DOWN = "browser-server-torn-down"
EFFECT_KINDS = frozenset({
    KIND_WORKTREE_CREATED,
    KIND_APP_STARTED,
    KIND_CREDENTIAL_MINTED,
    KIND_CREDENTIAL_SEEDED,
    KIND_NAMESPACE_TOUCHED,
    KIND_PROJECT_DECLARED,
    KIND_BROWSER_SERVER_PROVISIONED,
    KIND_BROWSER_SERVER_TORN_DOWN,
})

KIND_UNKNOWN = "unknown"

SCOPE_SLOT = "slot"
SCOPE_SHARED = "shared"
EFFECT_SCOPE = {
    KIND_WORKTREE_CREATED: SCOPE_SLOT,
    KIND_APP_STARTED: SCOPE_SLOT,
    KIND_CREDENTIAL_MINTED: SCOPE_SHARED,
    KIND_CREDENTIAL_SEEDED: SCOPE_SHARED,
    KIND_NAMESPACE_TOUCHED: SCOPE_SHARED,
    KIND_PROJECT_DECLARED: SCOPE_SHARED,
    KIND_BROWSER_SERVER_PROVISIONED: SCOPE_SLOT,
    KIND_BROWSER_SERVER_TORN_DOWN: SCOPE_SLOT,
}

OUTCOME_APPLIED = "applied"
OUTCOME_NOT_APPLIED = "not-applied"
OUTCOME_INDETERMINATE = "indeterminate"
END_OUTCOMES = frozenset({OUTCOME_APPLIED, OUTCOME_NOT_APPLIED, OUTCOME_INDETERMINATE})

STATE_APPLIED = "applied"
STATE_NOT_APPLIED = "not-applied"
STATE_POSSIBLY_APPLIED = "possibly-applied"
EFFECT_STATES = frozenset({STATE_APPLIED, STATE_NOT_APPLIED, STATE_POSSIBLY_APPLIED})

SLOT_OUTCOME_PROVISIONED = "provisioned"
SLOT_OUTCOME_FAILED = "failed"
SLOT_OUTCOMES = frozenset({SLOT_OUTCOME_PROVISIONED, SLOT_OUTCOME_FAILED})

REASON_JOURNAL_UNREADABLE = "journal-unreadable"
REASON_JOURNAL_WRITE_FAILED = "journal-write-failed"
REASON_RECORD_INVALID = "journal-record-invalid"
REASON_KIND_UNKNOWN = "journal-effect-kind-unknown"
REASON_OUTCOME_INVALID = "journal-outcome-invalid"
REASON_SLOT_REF_INVALID = "journal-slot-ref-invalid"
REASON_EFFECT_ID_INVALID = "journal-effect-id-invalid"
REASON_ORIGIN_MISSING = "journal-effect-origin-missing"
REASON_ORIGIN_AMBIGUOUS = "journal-effect-origin-ambiguous"
REASON_ORIGIN_INVALID = "journal-effect-origin-invalid"
REASON_ORIGIN_KIND_MISMATCH = "journal-effect-origin-kind-mismatch"
REASON_ORIGIN_SLOT_MISMATCH = "journal-effect-origin-slot-mismatch"
REASON_ALREADY_CLOSED = "journal-effect-already-closed"

BLOCK_SLOT_ENTRY_INVALID = "report-slot-entry-invalid"
BLOCK_SLOT_OUTCOME_INVALID = "report-slot-outcome-invalid"
BLOCK_FENCE_MISSING = "failed-slot-fence-missing"
BLOCK_FENCE_INVALID = "failed-slot-fence-invalid"
BLOCK_NOT_FENCED = "failed-slot-not-fenced"
BLOCK_FENCE_REF_MISMATCH = "failed-slot-fence-ref-mismatch"
BLOCK_JOURNAL_UNREADABLE = "failed-slot-journal-unreadable"
BLOCK_JOURNAL_TORN = "failed-slot-journal-torn"
BLOCK_JOURNAL_ANOMALY = "failed-slot-journal-anomaly"
BLOCK_SHARED_POSSIBLY_APPLIED = "failed-slot-shared-effect-possibly-applied"
BLOCK_NO_HEALTHY_SLOTS = "no-healthy-slots"
BLOCK_SLOTS_INVALID = "report-slots-invalid"
BLOCK_REPLAY_SHAPE_INVALID = "failed-slot-replay-shape-invalid"
BLOCK_REPLAY_SLOT_MISMATCH = "slot-replay-slot-mismatch"
BLOCK_SLOT_DUPLICATE = "report-slot-duplicate"

_EFFECT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_REASON_MAX_LEN = 500
DETAIL_MAX_BYTES = 8192
_LOCK_DEFAULT_TIMEOUT = 30.0
_LOCK_POLL_INTERVAL = 0.05
_write_verify_hook = threading.local()

_BEGIN_REQUIRED_KEYS = frozenset({
    "schemaVersion", "phase", "effectId", "slotRef", "kind", "at",
})
_END_REQUIRED_KEYS = frozenset({
    "schemaVersion", "phase", "effectId", "slotRef", "outcome", "at",
})


class PilotJournalError(Exception):
    """Raised when journal context-manager writes fail."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _is_member(value, members):
    """True only when value is a str AND a member. Never raises on unhashable input."""
    return isinstance(value, str) and value in members


def _is_str_path(value):
    return isinstance(value, str)


def _ok(**extra):
    out = {"ok": True, "reason": None}
    out.update(extra)
    return out


def _fail(reason, **extra):
    out = {"ok": False, "reason": reason}
    out.update(extra)
    return out


def _reject_constant(_tok):
    raise ValueError("non-finite JSON constant")


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


def _detail_encoded_size(detail):
    return len(
        json.dumps(detail, sort_keys=True, ensure_ascii=False).encode("utf-8"),
    )


def _is_json_serialisable_detail(detail):
    if detail is None:
        return True
    if not isinstance(detail, dict):
        return False
    try:
        json.dumps(detail, allow_nan=False)
    except (TypeError, ValueError):
        return False
    if _detail_encoded_size(detail) > DETAIL_MAX_BYTES:
        return False
    return True


def _validate_effect_id(effect_id):
    if not isinstance(effect_id, str) or not _EFFECT_ID_RE.match(effect_id):
        return False
    return True


def _validate_slot_ref(slot_ref):
    try:
        pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        return False
    return True


def _ensure_parent_dir(path):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _journal_lock_path(journal_path):
    return journal_path + ".lock"


def _journal_path_writable(journal_path):
    """True only when a write may proceed to lock acquisition."""
    if not _is_str_path(journal_path):
        return False
    if not journal_path:
        return False
    parent = os.path.dirname(os.path.abspath(journal_path)) or "."
    if os.path.islink(parent):
        return False
    if os.path.lexists(parent) and not os.path.isdir(parent):
        return False
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError:
        return False
    return os.path.isdir(parent)


def _acquire_journal_lock(journal_path, timeout=_LOCK_DEFAULT_TIMEOUT):
    """Acquire an advisory flock on a separate lock file beside the journal."""
    lock_file = _journal_lock_path(journal_path)
    parent = os.path.dirname(os.path.abspath(journal_path)) or "."
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError:
        return None
    if os.path.islink(lock_file):
        return None
    if os.path.lexists(lock_file):
        if os.path.isdir(lock_file):
            return None
        try:
            lock_stat = os.stat(lock_file, follow_symlinks=False)
            if stat.S_ISSOCK(lock_stat.st_mode):
                return None
        except OSError:
            return None
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        lock_stat = os.fstat(fd)
        if not stat.S_ISREG(lock_stat.st_mode):
            os.close(fd)
            return None
        acquired = False
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    return None
                time.sleep(_LOCK_POLL_INTERVAL)
        return fd
    except OSError:
        return None


def _release_journal_lock(lock_fd):
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(lock_fd)
    except OSError:
        pass


def _read_journal_text(journal_path):
    """Read a journal fail-closed. Returns a dict:
       {"ok": bool, "text": str, "torn": bool, "reason": str|None, "missing": bool}
    """
    fd = None
    try:
        fd = os.open(
            journal_path,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
        )
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return {
                "ok": False,
                "text": "",
                "torn": False,
                "reason": REASON_JOURNAL_UNREADABLE,
                "missing": False,
            }
        raw = b""
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            raw += chunk
    except FileNotFoundError:
        return {
            "ok": False,
            "text": "",
            "torn": False,
            "reason": None,
            "missing": True,
        }
    except OSError:
        return {
            "ok": False,
            "text": "",
            "torn": False,
            "reason": REASON_JOURNAL_UNREADABLE,
            "missing": False,
        }
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

    torn = False
    if raw and not raw.endswith(b"\n"):
        torn = True
        last_nl = raw.rfind(b"\n")
        if last_nl == -1:
            return {
                "ok": True,
                "text": "",
                "torn": True,
                "reason": None,
                "missing": False,
            }
        raw = raw[:last_nl + 1]

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "ok": False,
            "text": "",
            "torn": False,
            "reason": REASON_JOURNAL_UNREADABLE,
            "missing": False,
        }

    return {
        "ok": True,
        "text": text,
        "torn": torn,
        "reason": None,
        "missing": False,
    }


def _verify_end_effect_origin(journal_path, *, slot_ref, effect_id, kind):
    """Verify the effect ID names an open begin of the right kind for this slot.

    Precedence (first match wins):
    1. zero begin-phase records with this effectId → origin-missing
    2. more than one begin-phase record → origin-ambiguous
    3. exactly one begin but fails _validate_begin_record → origin-invalid
    4. exactly one valid begin but kind != argument → origin-kind-mismatch
    5. exactly one valid begin but slotRef != argument → origin-slot-mismatch
    6. any end-phase record with this effectId → already-closed
    7. otherwise → proceed (return None)
    """
    read_result = _read_journal_text(journal_path)
    if not read_result["ok"]:
        if read_result["missing"]:
            return REASON_ORIGIN_MISSING
        return REASON_JOURNAL_UNREADABLE

    begin_count = 0
    begin_record = None
    end_exists = False

    for line in read_result["text"].splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line, parse_constant=_reject_constant)
        except (ValueError, json.JSONDecodeError):
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("effectId") != effect_id:
            continue
        phase = obj.get("phase")
        if phase == PHASE_BEGIN:
            begin_count += 1
            if begin_count == 1:
                begin_record = obj
        elif phase == PHASE_END:
            end_exists = True

    if begin_count == 0:
        return REASON_ORIGIN_MISSING
    if begin_count > 1:
        return REASON_ORIGIN_AMBIGUOUS
    if not _validate_begin_record(begin_record):
        return REASON_ORIGIN_INVALID
    if begin_record.get("kind") != kind:
        return REASON_ORIGIN_KIND_MISMATCH
    if begin_record.get("slotRef") != slot_ref:
        return REASON_ORIGIN_SLOT_MISMATCH
    if end_exists:
        return REASON_ALREADY_CLOSED
    return None


def _write_record(journal_path, record, verify=None):
    """Durable single-write append. Returns ok/reason dict."""
    if not _journal_path_writable(journal_path):
        return _fail(REASON_JOURNAL_WRITE_FAILED)
    line = json.dumps(record, sort_keys=True) + "\n"
    encoded = line.encode("utf-8")
    lock_fd = _acquire_journal_lock(journal_path)
    if lock_fd is None:
        return _fail(REASON_JOURNAL_WRITE_FAILED)
    fd = None
    hook = verify
    if hook is None:
        hook = getattr(_write_verify_hook, "fn", None)
    try:
        if hook is not None:
            refusal = hook()
            if refusal is not None:
                return _fail(refusal)
        _ensure_parent_dir(journal_path)
        # O_NONBLOCK prevents an existing FIFO at journal_path from blocking open
        # before the regular-file fstat check can refuse the write.
        fd = os.open(
            journal_path,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
        )
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return _fail(REASON_JOURNAL_WRITE_FAILED)
        offset = 0
        while offset < len(encoded):
            written = os.write(fd, encoded[offset:])
            if written == 0:
                return _fail(REASON_JOURNAL_WRITE_FAILED)
            offset += written
        os.fsync(fd)
        parent = os.path.dirname(os.path.abspath(journal_path)) or "."
        dir_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return _ok()
    except OSError:
        return _fail(REASON_JOURNAL_WRITE_FAILED)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        _release_journal_lock(lock_fd)


def _build_begin_record(*, slot_ref, kind, at, detail, effect_id):
    record = {
        "schemaVersion": SCHEMA,
        "phase": PHASE_BEGIN,
        "effectId": effect_id,
        "slotRef": slot_ref,
        "kind": kind,
        "at": at,
    }
    if detail is not None:
        record["detail"] = detail
    return record


def _build_end_record(*, slot_ref, effect_id, outcome, at, reason):
    record = {
        "schemaVersion": SCHEMA,
        "phase": PHASE_END,
        "effectId": effect_id,
        "slotRef": slot_ref,
        "outcome": outcome,
        "at": at,
    }
    if reason is not None:
        record["reason"] = reason
    return record


def begin_effect(journal_path, *, slot_ref, kind, at, detail=None, effect_id=None):
    """Append a begin-phase journal record."""
    if not _is_str_path(journal_path):
        return _fail(REASON_JOURNAL_WRITE_FAILED)
    if not _validate_slot_ref(slot_ref):
        return _fail(REASON_SLOT_REF_INVALID)
    if not _is_member(kind, EFFECT_KINDS):
        return _fail(REASON_KIND_UNKNOWN)
    if not _is_iso8601_utc(at):
        return _fail(REASON_RECORD_INVALID)
    if not _is_json_serialisable_detail(detail):
        return _fail(REASON_RECORD_INVALID)
    if effect_id is None:
        effect_id = uuid.uuid4().hex
    elif not _validate_effect_id(effect_id):
        return _fail(REASON_EFFECT_ID_INVALID, effectId=None)

    record = _build_begin_record(
        slot_ref=slot_ref,
        kind=kind,
        at=at,
        detail=detail,
        effect_id=effect_id,
    )
    result = _write_record(journal_path, record)
    if not result["ok"]:
        return result
    return _ok(effectId=effect_id)


def end_effect(journal_path, *, slot_ref, effect_id, kind, outcome, at, reason=None):
    """Append an end-phase journal record."""
    if not _is_str_path(journal_path):
        return _fail(REASON_JOURNAL_WRITE_FAILED)
    if not _validate_slot_ref(slot_ref):
        return _fail(REASON_SLOT_REF_INVALID)
    if not _validate_effect_id(effect_id):
        return _fail(REASON_EFFECT_ID_INVALID)
    if not _is_member(kind, EFFECT_KINDS):
        return _fail(REASON_KIND_UNKNOWN)
    if not _is_member(outcome, END_OUTCOMES):
        return _fail(REASON_OUTCOME_INVALID)
    if not _is_iso8601_utc(at):
        return _fail(REASON_RECORD_INVALID)
    if reason is not None and not isinstance(reason, str):
        return _fail(REASON_RECORD_INVALID)

    record = _build_end_record(
        slot_ref=slot_ref,
        effect_id=effect_id,
        outcome=outcome,
        at=at,
        reason=reason,
    )

    def _verify():
        return _verify_end_effect_origin(
            journal_path,
            slot_ref=slot_ref,
            effect_id=effect_id,
            kind=kind,
        )

    _write_verify_hook.fn = _verify
    try:
        return _write_record(journal_path, record)
    finally:
        _write_verify_hook.fn = None


class _EffectHandle:
    """Handle yielded by effect() context manager."""

    def __init__(self, effect_id):
        self.effect_id = effect_id
        self._outcome = OUTCOME_INDETERMINATE
        self._end_at = None
        self._end_reason = None
        self._marked = False

    def mark_applied(self, *, at):
        self._outcome = OUTCOME_APPLIED
        self._end_at = at
        self._marked = True

    def mark_not_applied(self, *, at, reason=None):
        self._outcome = OUTCOME_NOT_APPLIED
        self._end_at = at
        self._end_reason = reason
        self._marked = True

    def mark_indeterminate(self, *, at, reason=None):
        self._outcome = OUTCOME_INDETERMINATE
        self._end_at = at
        self._end_reason = reason
        self._marked = True


@contextlib.contextmanager
def effect(journal_path, *, slot_ref, kind, at, detail=None, effect_id=None):
    """Context manager: begin before body, end after (or on exception)."""
    begin_result = begin_effect(
        journal_path,
        slot_ref=slot_ref,
        kind=kind,
        at=at,
        detail=detail,
        effect_id=effect_id,
    )
    if not begin_result["ok"]:
        raise PilotJournalError(begin_result["reason"])

    handle = _EffectHandle(begin_result["effectId"])
    body_raised = False
    try:
        yield handle
    except BaseException as exc:
        body_raised = True
        handle._outcome = OUTCOME_INDETERMINATE
        handle._end_at = at
        reason_text = repr(exc)
        if len(reason_text) > _REASON_MAX_LEN:
            reason_text = reason_text[:_REASON_MAX_LEN]
        handle._end_reason = reason_text
        handle._marked = True
        raise
    finally:
        if not handle._marked:
            # A clean exit is the caller's assertion that the effect completed; callers
            # that swallow their own errors must call mark_not_applied or let the
            # exception propagate — this context manager cannot distinguish swallowed
            # failure from success. mark_applied records applied with an explicit end
            # timestamp when needed.
            handle._outcome = OUTCOME_APPLIED
        end_at = handle._end_at if handle._marked else at
        end_reason = handle._end_reason if handle._outcome == OUTCOME_INDETERMINATE else (
            handle._end_reason if handle._outcome == OUTCOME_NOT_APPLIED else None
        )
        end_result = end_effect(
            journal_path,
            slot_ref=slot_ref,
            effect_id=handle.effect_id,
            kind=kind,
            outcome=handle._outcome,
            at=end_at,
            reason=end_reason,
        )
        # When the body raised, propagate that exception — the missing end record
        # replays as possibly-applied, which is the honest state. Only surface an
        # end-write failure when the body completed cleanly.
        if not end_result["ok"] and not body_raised:
            raise PilotJournalError(end_result["reason"])


def _validate_begin_record(record):
    if not isinstance(record, dict):
        return False
    keys = set(record.keys())
    if "detail" in keys:
        allowed = _BEGIN_REQUIRED_KEYS | {"detail"}
    else:
        allowed = _BEGIN_REQUIRED_KEYS
    if keys != allowed:
        return False
    if record.get("schemaVersion") != SCHEMA:
        return False
    if record.get("phase") != PHASE_BEGIN:
        return False
    if not _validate_effect_id(record.get("effectId")):
        return False
    if not _validate_slot_ref(record.get("slotRef")):
        return False
    kind = record.get("kind")
    if not _is_member(kind, EFFECT_KINDS):
        return False
    if not _is_iso8601_utc(record.get("at")):
        return False
    if "detail" in keys and not _is_json_serialisable_detail(record.get("detail")):
        return False
    return True


def _validate_end_record(record):
    if not isinstance(record, dict):
        return False
    keys = set(record.keys())
    if "reason" in keys:
        allowed = _END_REQUIRED_KEYS | {"reason"}
    else:
        allowed = _END_REQUIRED_KEYS
    if keys != allowed:
        return False
    if record.get("schemaVersion") != SCHEMA:
        return False
    if record.get("phase") != PHASE_END:
        return False
    if not _validate_effect_id(record.get("effectId")):
        return False
    if not _validate_slot_ref(record.get("slotRef")):
        return False
    outcome = record.get("outcome")
    if not _is_member(outcome, END_OUTCOMES):
        return False
    if not _is_iso8601_utc(record.get("at")):
        return False
    if "reason" in keys and record.get("reason") is not None:
        if not isinstance(record.get("reason"), str):
            return False
    return True


def _outcome_to_state(outcome):
    if outcome == OUTCOME_APPLIED:
        return STATE_APPLIED
    if outcome == OUTCOME_NOT_APPLIED:
        return STATE_NOT_APPLIED
    return STATE_POSSIBLY_APPLIED


def _unknown_effect_entry(*, effect_id=None, slot_ref=None, began_at=None, ended_at=None,
                          outcome=None, reason=None, detail=None):
    return {
        "effectId": effect_id,
        "kind": KIND_UNKNOWN,
        "scope": SCOPE_SHARED,
        "slotRef": slot_ref,
        "state": STATE_POSSIBLY_APPLIED,
        "beganAt": began_at,
        "endedAt": ended_at,
        "outcome": outcome,
        "reason": reason,
        "detail": detail,
    }


def _effect_entry_from_begin(record):
    return {
        "effectId": record["effectId"],
        "kind": record["kind"],
        "scope": EFFECT_SCOPE[record["kind"]],
        "slotRef": record["slotRef"],
        "state": STATE_POSSIBLY_APPLIED,
        "beganAt": record["at"],
        "endedAt": None,
        "outcome": None,
        "reason": None,
        "detail": record.get("detail"),
    }


def _effect_entry_from_end(record):
    return {
        "effectId": record["effectId"],
        "kind": KIND_UNKNOWN,
        "scope": SCOPE_SHARED,
        "slotRef": record["slotRef"],
        "state": STATE_POSSIBLY_APPLIED,
        "beganAt": None,
        "endedAt": record["at"],
        "outcome": record["outcome"],
        "reason": record.get("reason"),
        "detail": None,
    }


def _merge_begin_end(begin_entry, end_record):
    entry = dict(begin_entry)
    entry["endedAt"] = end_record["at"]
    entry["outcome"] = end_record["outcome"]
    entry["reason"] = end_record.get("reason")
    entry["state"] = _outcome_to_state(end_record["outcome"])
    return entry


def _build_effect_id_slot_ref_map(parsed_records):
    effect_id_slot_refs = {}
    for rec in parsed_records:
        if not isinstance(rec.get("raw"), dict):
            continue
        effect_id = rec["raw"].get("effectId")
        slot = rec["raw"].get("slotRef")
        if isinstance(effect_id, str) and isinstance(slot, str):
            effect_id_slot_refs.setdefault(effect_id, set()).add(slot)
    return effect_id_slot_refs


def _effect_id_involves_slot_ref(effect_id, slot_ref, effect_id_slot_refs):
    return slot_ref in effect_id_slot_refs.get(effect_id, set())


def _anomaly_involves_slot_ref(anomaly, slot_ref, parsed_records, effect_id_slot_refs):
    if "reason" not in anomaly and "record" in anomaly:
        return True
    effect_id = anomaly.get("effectId")
    if effect_id and _effect_id_involves_slot_ref(effect_id, slot_ref, effect_id_slot_refs):
        return True
    line = anomaly.get("line")
    if line is not None:
        for rec in parsed_records:
            if rec["line"] == line and rec["valid"] and isinstance(rec["raw"], dict):
                if rec["raw"].get("slotRef") == slot_ref:
                    return True
    return False


def _stamp_replay(result, journal_path, slot_ref):
    result["journalPath"] = journal_path
    result["slotRef"] = slot_ref
    return result


def replay(journal_path, *, slot_ref=None):
    """Replay journal into effect entries with fail-closed pairing."""
    if not _is_str_path(journal_path):
        return _stamp_replay(
            _fail(REASON_JOURNAL_UNREADABLE, effects=[], torn=False, anomalies=[]),
            journal_path,
            slot_ref,
        )
    if slot_ref is not None and not _validate_slot_ref(slot_ref):
        return _stamp_replay(
            _fail(REASON_SLOT_REF_INVALID, effects=[], torn=False, anomalies=[]),
            journal_path,
            slot_ref,
        )

    read_result = _read_journal_text(journal_path)
    if not read_result["ok"]:
        return _stamp_replay(
            _fail(REASON_JOURNAL_UNREADABLE, effects=[], torn=False, anomalies=[]),
            journal_path,
            slot_ref,
        )

    torn = read_result["torn"]
    if torn and not read_result["text"]:
        return _stamp_replay(
            _ok(effects=[], torn=True, anomalies=[]),
            journal_path,
            slot_ref,
        )

    lines = read_result["text"].splitlines()

    parsed_records = []
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line, parse_constant=_reject_constant)
        except (ValueError, json.JSONDecodeError):
            parsed_records.append({
                "line": line_no,
                "valid": False,
                "raw": None,
                "phase": None,
            })
            continue

        if isinstance(obj, list):
            parsed_records.append({
                "line": line_no,
                "valid": False,
                "raw": obj,
                "phase": None,
            })
            continue

        phase = obj.get("phase") if isinstance(obj, dict) else None
        if phase == PHASE_BEGIN:
            valid = _validate_begin_record(obj)
        elif phase == PHASE_END:
            valid = _validate_end_record(obj)
        else:
            valid = False

        parsed_records.append({
            "line": line_no,
            "valid": valid,
            "raw": obj if isinstance(obj, dict) else None,
            "phase": phase,
        })

    anomalies = []
    begins = {}
    ends = {}
    begin_order = []
    end_order = []
    invalid_entries = []
    begin_counts = {}
    end_counts = {}
    first_begin_idx = {}
    first_end_idx = {}

    for i, rec in enumerate(parsed_records):
        if not rec["valid"]:
            anomalies.append({"line": rec["line"], "record": rec["raw"]})
            if rec["raw"] is not None and isinstance(rec["raw"], dict):
                effect_id = rec["raw"].get("effectId")
                slot = rec["raw"].get("slotRef")
                if rec["phase"] == PHASE_BEGIN:
                    invalid_entries.append(_unknown_effect_entry(
                        effect_id=effect_id,
                        slot_ref=slot,
                        began_at=rec["raw"].get("at"),
                        detail=rec["raw"].get("detail"),
                    ))
                elif rec["phase"] == PHASE_END:
                    invalid_entries.append(_unknown_effect_entry(
                        effect_id=effect_id,
                        slot_ref=slot,
                        ended_at=rec["raw"].get("at"),
                        outcome=rec["raw"].get("outcome"),
                        reason=rec["raw"].get("reason"),
                    ))
                else:
                    invalid_entries.append(_unknown_effect_entry(
                        effect_id=effect_id,
                        slot_ref=slot,
                    ))
            else:
                invalid_entries.append(_unknown_effect_entry())
            continue

        record = rec["raw"]
        effect_id = record["effectId"]
        if record["phase"] == PHASE_BEGIN:
            if effect_id in begins:
                anomalies.append({
                    "line": rec["line"],
                    "reason": "duplicate-begin",
                    "effectId": effect_id,
                })
            begins[effect_id] = record
            begin_order.append(effect_id)
            begin_counts[effect_id] = begin_counts.get(effect_id, 0) + 1
            if effect_id not in first_begin_idx:
                first_begin_idx[effect_id] = i
        else:
            if effect_id in ends:
                anomalies.append({
                    "line": rec["line"],
                    "reason": "duplicate-end",
                    "effectId": effect_id,
                })
            ends[effect_id] = record
            end_order.append(effect_id)
            end_counts[effect_id] = end_counts.get(effect_id, 0) + 1
            if effect_id not in first_end_idx:
                first_end_idx[effect_id] = i

    anomaly_effect_ids = set()
    for effect_id, count in begin_counts.items():
        if count > 1:
            anomaly_effect_ids.add(effect_id)
    for effect_id, count in end_counts.items():
        if count > 1:
            anomaly_effect_ids.add(effect_id)

    paired_ids = set(first_begin_idx) & set(first_end_idx)
    for effect_id in paired_ids:
        if first_end_idx[effect_id] < first_begin_idx[effect_id]:
            anomalies.append({
                "reason": "end-before-begin",
                "effectId": effect_id,
            })
            anomaly_effect_ids.add(effect_id)

    for effect_id in paired_ids:
        if effect_id in anomaly_effect_ids:
            continue
        if begins[effect_id]["slotRef"] != ends[effect_id]["slotRef"]:
            anomalies.append({
                "reason": "slot-ref-mismatch",
                "effectId": effect_id,
            })
            anomaly_effect_ids.add(effect_id)

    effect_id_slot_refs = _build_effect_id_slot_ref_map(parsed_records)

    effects = []
    merged_from_begin = set()
    end_seen = {}
    invalid_entry_idx = 0

    for rec in parsed_records:
        if not rec["valid"]:
            if invalid_entry_idx < len(invalid_entries):
                entry = invalid_entries[invalid_entry_idx]
                invalid_entry_idx += 1
            else:
                entry = _unknown_effect_entry()
            effects.append((entry, True))
            continue

        record = rec["raw"]
        effect_id = record["effectId"]

        if record["phase"] == PHASE_BEGIN:
            entry = _effect_entry_from_begin(record)
            if effect_id in anomaly_effect_ids:
                entry["state"] = STATE_POSSIBLY_APPLIED
                effects.append((entry, False))
            elif (
                effect_id in ends
                and begin_counts.get(effect_id, 0) == 1
                and end_counts.get(effect_id, 0) == 1
            ):
                entry = _merge_begin_end(entry, ends[effect_id])
                merged_from_begin.add(effect_id)
                effects.append((entry, False))
            else:
                effects.append((entry, False))
        else:
            if effect_id not in begins:
                entry = _effect_entry_from_end(record)
                anomalies.append({
                    "line": rec["line"],
                    "reason": "orphan-end",
                    "effectId": effect_id,
                })
                effects.append((entry, False))
            elif effect_id in merged_from_begin:
                continue
            elif effect_id in anomaly_effect_ids:
                end_seen[effect_id] = end_seen.get(effect_id, 0) + 1
                if end_counts.get(effect_id, 0) > 1:
                    entry = _effect_entry_from_end(record)
                    effects.append((entry, False))

    if slot_ref is not None:
        filtered_effects = []
        for entry, from_invalid in effects:
            if from_invalid:
                filtered_effects.append(entry)
            elif entry.get("slotRef") == slot_ref:
                filtered_effects.append(entry)
        effects = filtered_effects
        anomalies = [
            a for a in anomalies
            if _anomaly_involves_slot_ref(a, slot_ref, parsed_records, effect_id_slot_refs)
        ]
    else:
        effects = [entry for entry, _from_invalid in effects]

    return _stamp_replay(
        _ok(effects=effects, torn=torn, anomalies=anomalies),
        journal_path,
        slot_ref,
    )


def _blocker(reason, *, slot=None, slot_ref=None, detail=None):
    return {
        "reason": reason,
        "slot": slot,
        "slotRef": slot_ref,
        "detail": detail,
    }


def _validate_replay_shape(replay_result):
    """Validate a replay result shape fail-closed. Returns blocker reason or None."""
    if not isinstance(replay_result, dict):
        return BLOCK_REPLAY_SHAPE_INVALID
    if replay_result.get("ok") is not True:
        return BLOCK_JOURNAL_UNREADABLE
    torn = replay_result.get("torn")
    if torn is not True and torn is not False:
        return BLOCK_REPLAY_SHAPE_INVALID
    if not isinstance(replay_result.get("anomalies"), list):
        return BLOCK_REPLAY_SHAPE_INVALID
    effects = replay_result.get("effects")
    if not isinstance(effects, list):
        return BLOCK_REPLAY_SHAPE_INVALID
    for effect in effects:
        if not isinstance(effect, dict):
            return BLOCK_REPLAY_SHAPE_INVALID
        state = effect.get("state")
        if not _is_member(state, EFFECT_STATES):
            return BLOCK_REPLAY_SHAPE_INVALID
        scope = effect.get("scope")
        if not _is_member(scope, frozenset({SCOPE_SLOT, SCOPE_SHARED})):
            return BLOCK_REPLAY_SHAPE_INVALID
        kind = effect.get("kind")
        if _is_member(kind, EFFECT_KINDS):
            if scope != EFFECT_SCOPE[kind]:
                return BLOCK_REPLAY_SHAPE_INVALID
        elif scope != SCOPE_SHARED:
            # Unknown or absent kind is unclassifiable — fail closed as shared.
            return BLOCK_REPLAY_SHAPE_INVALID
    return None


def _validate_replay_provenance(replay_result, slot_ref):
    """Verify replay stamp matches the report entry — provenance, not authentication.

    A caller that constructs a replay dict by hand can still forge the stamp.
    This check removes accidental cross-wiring (passing slot A's replay for slot B),
    which is the realistic failure mode.
    """
    if replay_result.get("slotRef") != slot_ref:
        return BLOCK_REPLAY_SLOT_MISMATCH
    return None


def _enumerate_replay_effects(replay_result, slot, slot_ref, blockers, warnings):
    """Enumerate possibly-applied effects from a validated replay result."""
    slot_warnings = []
    for effect in replay_result["effects"]:
        if effect.get("state") == STATE_POSSIBLY_APPLIED:
            slot_warnings.append(effect)
            if effect.get("scope") == SCOPE_SHARED:
                blockers.append(_blocker(
                    BLOCK_SHARED_POSSIBLY_APPLIED,
                    slot=slot,
                    slot_ref=slot_ref,
                    detail=effect.get("effectId"),
                ))
    for w in slot_warnings:
        warnings.append({"slot": slot, "slotRef": slot_ref, "effect": w})


def partial_failure_report(slots):
    """Build a fail-closed partial-failure report from slot provisioning results."""
    if not isinstance(slots, (list, tuple)):
        return {
            "schemaVersion": SCHEMA,
            "recommendLaunch": False,
            "blockers": [_blocker(BLOCK_SLOTS_INVALID)],
            "warnings": [],
            "failedSlots": [],
            "healthySlots": [],
        }

    blockers = []
    warnings = []
    failed_slots = []
    healthy_slots = []
    seen_slots = set()
    seen_slot_refs = set()

    for entry in slots:
        if not isinstance(entry, dict):
            blockers.append(_blocker(BLOCK_SLOT_ENTRY_INVALID))
            continue

        slot = entry.get("slot")
        slot_ref = entry.get("slotRef")
        outcome = entry.get("outcome")
        replay_result = entry.get("replay")
        fencing = entry.get("fencing")

        if (
            not isinstance(slot, str)
            or not slot
            or not isinstance(slot_ref, str)
            or not _validate_slot_ref(slot_ref)
            or outcome is None
        ):
            blockers.append(_blocker(
                BLOCK_SLOT_ENTRY_INVALID,
                slot=slot if isinstance(slot, str) else None,
                slot_ref=slot_ref if isinstance(slot_ref, str) else None,
            ))
            continue

        parsed_slot, _ = pilot_slot.parse_slot_ref(slot_ref)
        if parsed_slot != slot:
            blockers.append(_blocker(
                BLOCK_SLOT_ENTRY_INVALID,
                slot=slot,
                slot_ref=slot_ref,
            ))
            continue

        if slot in seen_slots or slot_ref in seen_slot_refs:
            blockers.append(_blocker(
                BLOCK_SLOT_DUPLICATE,
                slot=slot,
                slot_ref=slot_ref,
            ))
            continue
        seen_slots.add(slot)
        seen_slot_refs.add(slot_ref)

        if not _is_member(outcome, SLOT_OUTCOMES):
            blockers.append(_blocker(
                BLOCK_SLOT_OUTCOME_INVALID,
                slot=slot,
                slot_ref=slot_ref,
            ))
        elif outcome == SLOT_OUTCOME_PROVISIONED:
            if replay_result is None:
                healthy_slots.append({"slot": slot, "slotRef": slot_ref})
                continue
            shape_blocker = _validate_replay_shape(replay_result)
            if shape_blocker is not None:
                blockers.append(_blocker(
                    shape_blocker,
                    slot=slot,
                    slot_ref=slot_ref,
                ))
                healthy_slots.append({"slot": slot, "slotRef": slot_ref})
                continue
            provenance_blocker = _validate_replay_provenance(replay_result, slot_ref)
            if provenance_blocker is not None:
                blockers.append(_blocker(
                    provenance_blocker,
                    slot=slot,
                    slot_ref=slot_ref,
                ))
                healthy_slots.append({"slot": slot, "slotRef": slot_ref})
                continue
            if replay_result.get("torn") is True:
                blockers.append(_blocker(
                    BLOCK_JOURNAL_TORN,
                    slot=slot,
                    slot_ref=slot_ref,
                ))
            if replay_result.get("anomalies"):
                blockers.append(_blocker(
                    BLOCK_JOURNAL_ANOMALY,
                    slot=slot,
                    slot_ref=slot_ref,
                ))
            _enumerate_replay_effects(replay_result, slot, slot_ref, blockers, warnings)
            healthy_slots.append({"slot": slot, "slotRef": slot_ref})
            continue

        if replay_result is None:
            blockers.append(_blocker(
                BLOCK_SLOT_ENTRY_INVALID,
                slot=slot,
                slot_ref=slot_ref,
            ))
            continue

        failed_slots.append({"slot": slot, "slotRef": slot_ref})

        if fencing is None:
            blockers.append(_blocker(
                BLOCK_FENCE_MISSING,
                slot=slot,
                slot_ref=slot_ref,
            ))
        elif not isinstance(fencing, dict):
            blockers.append(_blocker(
                BLOCK_FENCE_INVALID,
                slot=slot,
                slot_ref=slot_ref,
            ))
        else:
            fenced = fencing.get("fenced")
            fence_ref = fencing.get("slotRef")
            if fenced is not True and fenced is not False:
                blockers.append(_blocker(
                    BLOCK_FENCE_INVALID,
                    slot=slot,
                    slot_ref=slot_ref,
                ))
            elif fence_ref != slot_ref:
                blockers.append(_blocker(
                    BLOCK_FENCE_REF_MISMATCH,
                    slot=slot,
                    slot_ref=slot_ref,
                ))
            elif fenced is False:
                blockers.append(_blocker(
                    BLOCK_NOT_FENCED,
                    slot=slot,
                    slot_ref=slot_ref,
                ))

        shape_blocker = _validate_replay_shape(replay_result)
        if shape_blocker is not None:
            blockers.append(_blocker(
                shape_blocker,
                slot=slot,
                slot_ref=slot_ref,
            ))
        else:
            provenance_blocker = _validate_replay_provenance(replay_result, slot_ref)
            if provenance_blocker is not None:
                blockers.append(_blocker(
                    provenance_blocker,
                    slot=slot,
                    slot_ref=slot_ref,
                ))
            else:
                if replay_result.get("torn") is True:
                    blockers.append(_blocker(
                        BLOCK_JOURNAL_TORN,
                        slot=slot,
                        slot_ref=slot_ref,
                    ))
                if replay_result.get("anomalies"):
                    blockers.append(_blocker(
                        BLOCK_JOURNAL_ANOMALY,
                        slot=slot,
                        slot_ref=slot_ref,
                    ))
                _enumerate_replay_effects(replay_result, slot, slot_ref, blockers, warnings)

    if not healthy_slots:
        blockers.append(_blocker(BLOCK_NO_HEALTHY_SLOTS))

    recommend_launch = (not blockers) and bool(healthy_slots)

    return {
        "schemaVersion": SCHEMA,
        "recommendLaunch": recommend_launch,
        "blockers": blockers,
        "warnings": warnings,
        "failedSlots": failed_slots,
        "healthySlots": healthy_slots,
    }
