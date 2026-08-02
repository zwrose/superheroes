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


class PilotLifecycleError(Exception):
    """Raised when slot lifecycle validation or transition refuses."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


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


def _validate_history_entry(entry):
    if not isinstance(entry, dict):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    at = entry.get("at")
    if not _is_iso8601_utc(at):
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    from_state = entry.get("from")
    if from_state is not None and from_state not in SLOT_STATES:
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    to_state = entry.get("to")
    if to_state not in SLOT_STATES:
        raise PilotLifecycleError(REASON_RECORD_INVALID)
    pilot_slot.validate_generation(entry.get("generation"))
    if "detail" in entry:
        detail = entry.get("detail")
        if not isinstance(detail, dict) or not detail:
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
    if state not in SLOT_STATES:
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
    if to not in SLOT_STATES:
        raise PilotLifecycleError(REASON_STATE_INVALID)
    if from_state == STATE_RETIRED:
        raise PilotLifecycleError(REASON_RETIRED)
    if to == STATE_OCCUPIED and from_state == STATE_OCCUPIED:
        raise PilotLifecycleError(REASON_OCCUPIED)
    # released → provisioning is a legal TRANSITIONS edge, but generation allocation
    # must go through begin_generation() so each attempt gets a unique slot@generation.
    if from_state == STATE_RELEASED and to == STATE_PROVISIONING:
        raise PilotLifecycleError(REASON_GENERATION_ALLOCATION_REQUIRED)
    if to not in TRANSITIONS.get(from_state, frozenset()):
        raise PilotLifecycleError(REASON_TRANSITION_ILLEGAL)
    if detail is not None and (not isinstance(detail, dict) or not detail):
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
    if state not in SLOT_STATES:
        raise PilotLifecycleError(REASON_STATE_INVALID)
    if state in (STATE_PROVISIONED, STATE_OCCUPIED, STATE_RELEASED):
        return "provisioned"
    if state in (STATE_FAILED, STATE_RETIRED):
        return "failed"
    return None


def slots_dir(cwd, root=None):
    """``<state_dir>/pilot-slots`` for the resolved test-pilot store entry."""
    resolved = store.resolve(cwd, root or store.store_root())
    return os.path.join(resolved["state_dir"], "pilot-slots")


def record_path(slots_dir_path, slot):
    slot = pilot_slot.validate_slot_id(slot)
    return os.path.join(slots_dir_path, slot, "slot.json")


def lock_path(slots_dir_path, slot):
    slot = pilot_slot.validate_slot_id(slot)
    return os.path.join(slots_dir_path, slot, ".slot.lock")


def _slot_dir_path(slots_dir_path, slot):
    slot = pilot_slot.validate_slot_id(slot)
    return os.path.join(slots_dir_path, slot)


def _refuse_unsafe_slot_dir(slot_dir):
    """Refuse a symlink or non-directory at the slot-directory component only.

    This does not walk the full path ancestry — only the slot directory itself.
    """
    if os.path.exists(slot_dir):
        if os.path.islink(slot_dir):
            raise PilotLifecycleError(REASON_SLOT_DIR_UNSAFE)
        if not os.path.isdir(slot_dir):
            raise PilotLifecycleError(REASON_SLOT_DIR_UNSAFE)


@contextlib.contextmanager
def slot_lock(slots_dir_path, slot, *, timeout=30.0, poll=0.05):
    """Exclusive advisory flock on the per-slot lock file."""
    slot = pilot_slot.validate_slot_id(slot)
    lock_file = lock_path(slots_dir_path, slot)
    slot_dir = _slot_dir_path(slots_dir_path, slot)
    _refuse_unsafe_slot_dir(slot_dir)
    os.makedirs(slot_dir, exist_ok=True)
    if os.path.islink(lock_file):
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


def read_record(path):
    """Load and validate a slot record. Never raises."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        return {"ok": False, "reason": REASON_RECORD_UNREADABLE, "record": None}
    except UnicodeDecodeError:
        return {"ok": False, "reason": REASON_RECORD_INVALID, "record": None}
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
    try:
        _validate_record(record)
    except (PilotLifecycleError, pilot_slot.PilotSlotError):
        return {"ok": False, "reason": REASON_RECORD_INVALID}
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
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
    try:
        with slot_lock(slots_dir_path, slot, timeout=timeout):
            path = record_path(slots_dir_path, slot)
            loaded = read_record(path)
            if loaded["ok"]:
                return {"ok": False, "reason": REASON_RECORD_EXISTS, "record": None}
            if loaded["reason"] == REASON_RECORD_INVALID:
                return {"ok": False, "reason": REASON_RECORD_INVALID, "record": None}
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
