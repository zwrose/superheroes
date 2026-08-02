"""Pilot slot lifecycle — state machine, generation allocation, serialized persistence.

Non-goals: no journal records (pilot_journal), no fencing enforcement, no recovery
entry points from failed — those belong to sibling modules and later sub-issues.
"""
import contextlib
import fcntl
import json
import os
import stat
import time
from datetime import datetime

import pilot_slot
import store
import store_core

SCHEMA = 1
INITIAL_GENERATION = 1

STATE_PROVISIONING = "provisioning"
STATE_PROVISIONED = "provisioned"
STATE_OCCUPIED = "occupied"
STATE_RELEASED = "released"
STATE_FAILED = "failed"
STATE_RETIRED = "retired"

SLOT_STATES = frozenset({
    STATE_PROVISIONING,
    STATE_PROVISIONED,
    STATE_OCCUPIED,
    STATE_RELEASED,
    STATE_FAILED,
    STATE_RETIRED,
})
TERMINAL_STATES = frozenset({STATE_RETIRED})

TRANSITIONS = {
    STATE_PROVISIONING: frozenset({STATE_PROVISIONED, STATE_FAILED}),
    STATE_PROVISIONED: frozenset({STATE_OCCUPIED, STATE_FAILED, STATE_RETIRED}),
    STATE_OCCUPIED: frozenset({STATE_RELEASED, STATE_FAILED, STATE_RETIRED}),
    STATE_RELEASED: frozenset({STATE_PROVISIONING, STATE_RETIRED}),
    STATE_FAILED: frozenset({STATE_RETIRED}),
    STATE_RETIRED: frozenset(),
}

REASON_STATE_INVALID = "slot-state-invalid"
REASON_TRANSITION_ILLEGAL = "slot-transition-illegal"
REASON_OCCUPIED = "slot-occupied"
REASON_RETIRED = "slot-retired"
REASON_RECORD_INVALID = "slot-record-invalid"
REASON_RECORD_ABSENT = "slot-record-absent"
REASON_RECORD_UNREADABLE = "slot-record-unreadable"
REASON_RECORD_WRITE_FAILED = "slot-record-write-failed"
REASON_GENERATION_STALE = "slot-generation-stale"
REASON_GENERATION_AHEAD = "slot-generation-ahead"
REASON_LOCK_UNAVAILABLE = "slot-lock-unavailable"
REASON_MUTATION_FAILED = "slot-mutation-failed"
REASON_GENERATION_ALLOCATION_REQUIRED = "slot-generation-allocation-required"
REASON_RECORD_SLOT_MISMATCH = "slot-record-slot-mismatch"
REASON_SLOT_DIR_UNSAFE = "slot-dir-unsafe"
REASON_RECORD_EXISTS = "slot-record-exists"
REASON_ROOT_UNRESOLVED = "slot-root-unresolved"


class PilotLifecycleError(Exception):
    """Raised when slot lifecycle validation or transition refuses."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _is_member(value, members):
    """True only when value is a str AND a member. Never raises on unhashable input."""
    return isinstance(value, str) and value in members


def _is_str_path(value):
    """True only for str paths accepted by this module."""
    return isinstance(value, str)


def _is_timeout(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


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


def _is_json_serialisable_detail(detail):
    if not isinstance(detail, dict):
        return False
    try:
        json.dumps(detail, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


def _validate_history_entry(entry):
    if not isinstance(entry, dict):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    at = entry.get("at")
    if not _is_iso8601_utc(at):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    from_state = entry.get("from")
    if from_state is not None and not _is_member(from_state, SLOT_STATES):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    to_state = entry.get("to")
    if not _is_member(to_state, SLOT_STATES):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    pilot_slot.validate_generation(entry.get("generation"))
    if "detail" in entry:
        detail = entry.get("detail")
        if not isinstance(detail, dict) or not detail:
            raise PilotLifecycleError(REASON_RECORD_INVALID)
        if not _is_json_serialisable_detail(detail):
            raise PilotLifecycleError(REASON_RECORD_INVALID)


def _validate_accounts(accounts):
    if not isinstance(accounts, list) or not accounts:
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    seen = set()
    for entry in accounts:
        if not isinstance(entry, dict):
            raise PilotLifecycleError(REASON_RECORD_INVALID)
        account = entry.get("account")
        role = entry.get("role")
        if not isinstance(account, str) or not account:
            raise PilotLifecycleError(REASON_RECORD_INVALID)
        if not isinstance(role, str) or not role:
            raise PilotLifecycleError(REASON_RECORD_INVALID)
        if account in seen:
            raise PilotLifecycleError(REASON_RECORD_INVALID)
        seen.add(account)


def _validate_record(record):
    if not isinstance(record, dict):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    schema = record.get("schemaVersion")
    if schema != SCHEMA:
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    slot = pilot_slot.validate_slot_id(record.get("slot"))
    generation = pilot_slot.validate_generation(record.get("generation"))
    state = record.get("state")
    if not _is_member(state, SLOT_STATES):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    _validate_accounts(record.get("accounts"))
    created_at = record.get("createdAt")
    updated_at = record.get("updatedAt")
    if not _is_iso8601_utc(created_at) or not _is_iso8601_utc(updated_at):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    history = record.get("history")
    if not isinstance(history, list) or not history:
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    for entry in history:
        _validate_history_entry(entry)
    last = history[-1]
    if last.get("to") != state:
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    if last.get("generation") != generation:
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    return slot, generation, state


def generation_check(carried, current):
    """Return ok/reason comparing a CARRIED generation against CURRENT."""
    try:
        carried_val = pilot_slot.validate_generation(carried)
        current_val = pilot_slot.validate_generation(current)
    except pilot_slot.PilotSlotError as exc:
        return {"ok": False, "reason": exc.reason}
    if carried_val == current_val:
        return {"ok": True, "reason": None}
    if carried_val < current_val:
        return {"ok": False, "reason": REASON_GENERATION_STALE}
    return {"ok": False, "reason": REASON_GENERATION_AHEAD}


def new_record(slot, accounts, *, now):
    """A brand-new slot at INITIAL_GENERATION in STATE_PROVISIONING."""
    slot = pilot_slot.validate_slot_id(slot)
    if not _is_iso8601_utc(now):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    if not isinstance(accounts, list):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    account_set = pilot_slot.slot_account_set(slot, INITIAL_GENERATION, accounts)
    return {
        "schemaVersion": SCHEMA,
        "slot": slot,
        "generation": INITIAL_GENERATION,
        "state": STATE_PROVISIONING,
        "accounts": list(account_set["accounts"]),
        "createdAt": now,
        "updatedAt": now,
        "history": [{
            "at": now,
            "from": None,
            "to": STATE_PROVISIONING,
            "generation": INITIAL_GENERATION,
        }],
    }


def transition(record, to, *, now, detail=None):
    """Return a NEW record moved to state ``to``. Never mutates ``record`` in place."""
    if not _is_iso8601_utc(now):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    _, generation, from_state = _validate_record(record)
    if not _is_member(to, SLOT_STATES):
        raise PilotLifecycleError(REASON_STATE_INVALID)
    if from_state == STATE_RETIRED:
        raise PilotLifecycleError(REASON_RETIRED)
    if to == STATE_OCCUPIED and from_state == STATE_OCCUPIED:
        raise PilotLifecycleError(REASON_OCCUPIED)
    # released → provisioning is a legal TRANSITIONS edge, but generation allocation
    # must go through begin_generation() so each attempt gets a unique slot@generation.
    if from_state == STATE_RELEASED and to == STATE_PROVISIONING:
        raise PilotLifecycleError(REASON_GENERATION_ALLOCATION_REQUIRED)
    if not _is_member(to, TRANSITIONS.get(from_state, frozenset())):
        raise PilotLifecycleError(REASON_TRANSITION_ILLEGAL)
    if detail is not None and (not isinstance(detail, dict) or not detail):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    if isinstance(detail, dict) and detail and not _is_json_serialisable_detail(detail):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    history_entry = {
        "at": now,
        "from": from_state,
        "to": to,
        "generation": generation,
    }
    if isinstance(detail, dict) and detail:
        history_entry["detail"] = dict(detail)
    new_rec = dict(record)
    new_rec["state"] = to
    new_rec["updatedAt"] = now
    new_rec["history"] = list(record["history"]) + [history_entry]
    return new_rec


def begin_generation(record, *, now):
    """Start the next provisioning attempt: generation += 1, state -> provisioning."""
    if not _is_iso8601_utc(now):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    _, generation, from_state = _validate_record(record)
    if from_state == STATE_RETIRED:
        raise PilotLifecycleError(REASON_RETIRED)
    if from_state != STATE_RELEASED:
        raise PilotLifecycleError(REASON_TRANSITION_ILLEGAL)
    new_generation = pilot_slot.validate_generation(generation + 1)
    history_entry = {
        "at": now,
        "from": from_state,
        "to": STATE_PROVISIONING,
        "generation": new_generation,
    }
    new_rec = dict(record)
    new_rec["generation"] = new_generation
    new_rec["state"] = STATE_PROVISIONING
    new_rec["updatedAt"] = now
    new_rec["history"] = list(record["history"]) + [history_entry]
    return new_rec


def slot_ref(record):
    """Return ``"<slot>@<generation>"`` via pilot_slot.format_slot_ref."""
    slot, generation, _ = _validate_record(record)
    return pilot_slot.format_slot_ref(slot, generation)


def provisioning_outcome(state):
    """Map a slot state to the partial-failure report outcome vocabulary."""
    if not _is_member(state, SLOT_STATES):
        raise PilotLifecycleError(REASON_STATE_INVALID)
    if state in (STATE_PROVISIONED, STATE_OCCUPIED, STATE_RELEASED):
        return "provisioned"
    if state in (STATE_FAILED, STATE_RETIRED):
        return "failed"
    return None


def slots_dir(cwd, root=None):
    """{"ok": bool, "reason": str|None, "path": str|None}. Never raises."""
    if not _is_str_path(cwd):
        return {"ok": False, "reason": REASON_ROOT_UNRESOLVED, "path": None}
    if root is not None and not _is_str_path(root):
        return {"ok": False, "reason": REASON_ROOT_UNRESOLVED, "path": None}
    try:
        if not os.path.exists(cwd):
            return {"ok": False, "reason": REASON_ROOT_UNRESOLVED, "path": None}
        resolved = store.resolve(cwd, root or store.store_root())
    except (OSError, store_core.RepoRootUnavailable):
        return {"ok": False, "reason": REASON_ROOT_UNRESOLVED, "path": None}
    return {
        "ok": True,
        "reason": None,
        "path": os.path.join(resolved["state_dir"], "pilot-slots"),
    }


def record_path(slots_dir_path, slot):
    if not _is_str_path(slots_dir_path):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    slot = pilot_slot.validate_slot_id(slot)
    return os.path.join(slots_dir_path, slot, "slot.json")


def lock_path(slots_dir_path, slot):
    if not _is_str_path(slots_dir_path):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    slot = pilot_slot.validate_slot_id(slot)
    return os.path.join(slots_dir_path, slot, ".slot.lock")


def _slot_dir_path(slots_dir_path, slot):
    slot = pilot_slot.validate_slot_id(slot)
    return os.path.join(slots_dir_path, slot)


def _refuse_unsafe_slot_dir(slot_dir):
    """Refuse a symlink or non-directory at the slot-directory component only.

    This check inspects the pathname at the moment of the call only — it is a
    check-then-use pattern and does not close a race against an attacker who can
    replace the directory between this check and subsequent operations. Under
    this project's single-user local threat model the guard is aimed at accidents
    and stale state, not a hostile local actor; a full fix would need
    directory-descriptor-relative operations (``os.open(dir, O_DIRECTORY)`` plus
    ``openat``-style access), which is deliberately not built here.

    This does not walk the full path ancestry — only the slot directory itself.
    """
    if os.path.islink(slot_dir):
        raise PilotLifecycleError(REASON_SLOT_DIR_UNSAFE)
    if os.path.lexists(slot_dir) and not os.path.isdir(slot_dir):
        raise PilotLifecycleError(REASON_SLOT_DIR_UNSAFE)


@contextlib.contextmanager
def slot_lock(slots_dir_path, slot, *, timeout=30.0, poll=0.05):
    """Exclusive advisory flock on the per-slot lock file."""
    if not _is_str_path(slots_dir_path):
        raise PilotLifecycleError(REASON_LOCK_UNAVAILABLE)
    if not _is_timeout(timeout) or not _is_timeout(poll):
        raise PilotLifecycleError(REASON_LOCK_UNAVAILABLE)
    slot = pilot_slot.validate_slot_id(slot)
    lock_file = lock_path(slots_dir_path, slot)
    slot_dir = _slot_dir_path(slots_dir_path, slot)
    _refuse_unsafe_slot_dir(slot_dir)
    try:
        os.makedirs(slot_dir, exist_ok=True)
        parent_dir = os.path.dirname(slot_dir)
        if parent_dir:
            parent_fd = os.open(parent_dir, os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        if os.path.islink(lock_file):
            raise PilotLifecycleError(REASON_SLOT_DIR_UNSAFE)
        if os.path.lexists(lock_file):
            if os.path.isdir(lock_file):
                raise PilotLifecycleError(REASON_SLOT_DIR_UNSAFE)
            lock_stat = os.stat(lock_file, follow_symlinks=False)
            if stat.S_ISSOCK(lock_stat.st_mode):
                raise PilotLifecycleError(REASON_SLOT_DIR_UNSAFE)
        fd = os.open(lock_file, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o644)
        lock_stat = os.fstat(fd)
        if not stat.S_ISREG(lock_stat.st_mode):
            os.close(fd)
            raise PilotLifecycleError(REASON_SLOT_DIR_UNSAFE)
        acquired = False
        deadline = time.monotonic() + timeout
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise PilotLifecycleError(REASON_LOCK_UNAVAILABLE)
                    time.sleep(poll)
            yield
        finally:
            if acquired:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(fd)
    except PilotLifecycleError:
        raise
    except OSError:
        raise PilotLifecycleError(REASON_LOCK_UNAVAILABLE)


def read_record(path):
    """Load and validate a slot record. Never raises."""
    if not _is_str_path(path):
        return {"ok": False, "reason": REASON_RECORD_UNREADABLE, "record": None}
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {"ok": False, "reason": REASON_RECORD_ABSENT, "record": None}
    except OSError:
        return {"ok": False, "reason": REASON_RECORD_UNREADABLE, "record": None}
    try:
        stat_result = os.fstat(fd)
        if not stat.S_ISREG(stat_result.st_mode):
            return {"ok": False, "reason": REASON_RECORD_UNREADABLE, "record": None}
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks).decode("utf-8")
    except OSError:
        return {"ok": False, "reason": REASON_RECORD_UNREADABLE, "record": None}
    except UnicodeDecodeError:
        return {"ok": False, "reason": REASON_RECORD_INVALID, "record": None}
    finally:
        os.close(fd)
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {"ok": False, "reason": REASON_RECORD_INVALID, "record": None}
    if not isinstance(parsed, dict):
        return {"ok": False, "reason": REASON_RECORD_INVALID, "record": None}
    try:
        _validate_record(parsed)
    except (PilotLifecycleError, pilot_slot.PilotSlotError):
        return {"ok": False, "reason": REASON_RECORD_INVALID, "record": None}
    return {"ok": True, "reason": None, "record": parsed}


def write_record(path, record):
    """Durably persist a validated slot record. Never raises."""
    if not _is_str_path(path):
        return {"ok": False, "reason": REASON_RECORD_WRITE_FAILED}
    try:
        _validate_record(record)
    except (PilotLifecycleError, pilot_slot.PilotSlotError):
        return {"ok": False, "reason": REASON_RECORD_INVALID}
    try:
        text = json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except (TypeError, ValueError):
        return {"ok": False, "reason": REASON_RECORD_WRITE_FAILED}
    parent = os.path.dirname(os.path.abspath(path)) or "."
    try:
        _refuse_unsafe_slot_dir(parent)
    except PilotLifecycleError as exc:
        return {"ok": False, "reason": exc.reason}
    try:
        store_core.atomic_write(path, text)
        dir_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        return {"ok": False, "reason": REASON_RECORD_WRITE_FAILED}
    return {"ok": True, "reason": None}


def mutate(slots_dir_path, slot, fn, *, timeout=30.0):
    """Serialized read-modify-write under the per-slot advisory lock."""
    if not _is_str_path(slots_dir_path):
        return {"ok": False, "reason": REASON_LOCK_UNAVAILABLE, "record": None}
    if not _is_timeout(timeout):
        return {"ok": False, "reason": REASON_LOCK_UNAVAILABLE, "record": None}
    try:
        with slot_lock(slots_dir_path, slot, timeout=timeout):
            path = record_path(slots_dir_path, slot)
            loaded = read_record(path)
            if not loaded["ok"]:
                return {"ok": False, "reason": loaded["reason"], "record": None}
            if loaded["record"]["slot"] != slot:
                return {
                    "ok": False,
                    "reason": REASON_RECORD_SLOT_MISMATCH,
                    "record": None,
                }
            try:
                new_record = fn(loaded["record"])
            except (pilot_slot.PilotSlotError, PilotLifecycleError) as exc:
                return {"ok": False, "reason": exc.reason, "record": None}
            except Exception:
                return {"ok": False, "reason": REASON_MUTATION_FAILED, "record": None}
            if not isinstance(new_record, dict):
                return {"ok": False, "reason": REASON_RECORD_INVALID, "record": None}
            try:
                if new_record.get("slot") != slot:
                    return {
                        "ok": False,
                        "reason": REASON_RECORD_SLOT_MISMATCH,
                        "record": None,
                    }
            except Exception:
                return {"ok": False, "reason": REASON_MUTATION_FAILED, "record": None}
            written = write_record(path, new_record)
            if not written["ok"]:
                return {"ok": False, "reason": written["reason"], "record": None}
            return {"ok": True, "reason": None, "record": new_record}
    except PilotLifecycleError as exc:
        return {"ok": False, "reason": exc.reason, "record": None}
    except OSError:
        return {"ok": False, "reason": REASON_LOCK_UNAVAILABLE, "record": None}


def create_slot(slots_dir_path, slot, accounts, *, now, timeout=30.0):
    """Create a slot's first record under the per-slot lock. Refuses if one exists."""
    if not _is_str_path(slots_dir_path):
        return {"ok": False, "reason": REASON_LOCK_UNAVAILABLE, "record": None}
    if not _is_timeout(timeout):
        return {"ok": False, "reason": REASON_LOCK_UNAVAILABLE, "record": None}
    try:
        with slot_lock(slots_dir_path, slot, timeout=timeout):
            path = record_path(slots_dir_path, slot)
            loaded = read_record(path)
            if loaded["ok"]:
                return {"ok": False, "reason": REASON_RECORD_EXISTS, "record": None}
            if loaded["reason"] != REASON_RECORD_ABSENT:
                return {"ok": False, "reason": loaded["reason"], "record": None}
            try:
                rec = new_record(slot, accounts, now=now)
            except (PilotLifecycleError, pilot_slot.PilotSlotError) as exc:
                return {"ok": False, "reason": exc.reason, "record": None}
            written = write_record(path, rec)
            if not written["ok"]:
                return {"ok": False, "reason": written["reason"], "record": None}
            return {"ok": True, "reason": None, "record": rec}
    except PilotLifecycleError as exc:
        return {"ok": False, "reason": exc.reason, "record": None}
    except OSError:
        return {"ok": False, "reason": REASON_LOCK_UNAVAILABLE, "record": None}
