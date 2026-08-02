"""Pilot provisioning journal — durable effect records and partial-failure reports.

Append-only journal written before AND after each shared effect so crash windows
replay honestly as possibly-applied rather than never-happened.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import re
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
EFFECT_KINDS = frozenset({
    KIND_WORKTREE_CREATED,
    KIND_APP_STARTED,
    KIND_CREDENTIAL_MINTED,
    KIND_CREDENTIAL_SEEDED,
    KIND_NAMESPACE_TOUCHED,
    KIND_PROJECT_DECLARED,
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

_EFFECT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_REASON_MAX_LEN = 500

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


def _is_json_serialisable_detail(detail):
    if detail is None:
        return True
    if not isinstance(detail, dict):
        return False
    try:
        json.dumps(detail, allow_nan=False)
    except (TypeError, ValueError):
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


def _write_record(journal_path, record):
    """Durable single-write append. Returns ok/reason dict."""
    line = json.dumps(record, sort_keys=True) + "\n"
    encoded = line.encode("utf-8")
    fd = None
    try:
        _ensure_parent_dir(journal_path)
        fd = os.open(
            journal_path,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT,
            0o600,
        )
        os.write(fd, encoded)
        os.fsync(fd)
        return _ok()
    except OSError:
        return _fail(REASON_JOURNAL_WRITE_FAILED)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


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
    if not _validate_slot_ref(slot_ref):
        return _fail(REASON_SLOT_REF_INVALID)
    if kind not in EFFECT_KINDS:
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


def end_effect(journal_path, *, slot_ref, effect_id, outcome, at, reason=None):
    """Append an end-phase journal record."""
    if not _validate_slot_ref(slot_ref):
        return _fail(REASON_SLOT_REF_INVALID)
    if not _validate_effect_id(effect_id):
        return _fail(REASON_EFFECT_ID_INVALID)
    if outcome not in END_OUTCOMES:
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
    return _write_record(journal_path, record)


class _EffectHandle:
    """Handle yielded by effect() context manager."""

    def __init__(self, effect_id):
        self.effect_id = effect_id
        self._outcome = OUTCOME_APPLIED
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
    try:
        yield handle
    except Exception as exc:
        handle._outcome = OUTCOME_INDETERMINATE
        handle._end_at = at
        reason_text = repr(exc)
        if len(reason_text) > _REASON_MAX_LEN:
            reason_text = reason_text[:_REASON_MAX_LEN]
        handle._end_reason = reason_text
        handle._marked = True
        raise
    finally:
        end_at = handle._end_at if handle._marked else at
        end_reason = handle._end_reason if handle._outcome == OUTCOME_INDETERMINATE else (
            handle._end_reason if handle._outcome == OUTCOME_NOT_APPLIED else None
        )
        end_effect(
            journal_path,
            slot_ref=slot_ref,
            effect_id=handle.effect_id,
            outcome=handle._outcome,
            at=end_at,
            reason=end_reason,
        )


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
    if record.get("kind") not in EFFECT_KINDS:
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
    if record.get("outcome") not in END_OUTCOMES:
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


def replay(journal_path, *, slot_ref=None):
    """Replay journal into effect entries with fail-closed pairing."""
    if slot_ref is not None and not _validate_slot_ref(slot_ref):
        return _fail(REASON_SLOT_REF_INVALID, effects=[], torn=False, anomalies=[])

    try:
        with open(journal_path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return _fail(REASON_JOURNAL_UNREADABLE, effects=[], torn=False, anomalies=[])

    torn = False
    if raw and not raw.endswith(b"\n"):
        torn = True
        last_nl = raw.rfind(b"\n")
        if last_nl == -1:
            return _ok(effects=[], torn=True, anomalies=[])
        raw = raw[:last_nl + 1]

    text = raw.decode("utf-8")
    lines = text.splitlines()

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

    if slot_ref is not None:
        filtered = []
        for rec in parsed_records:
            if not rec["valid"]:
                if rec["raw"] is not None and rec["raw"].get("slotRef") == slot_ref:
                    filtered.append(rec)
                elif rec["raw"] is None:
                    filtered.append(rec)
                continue
            if rec["raw"].get("slotRef") == slot_ref:
                filtered.append(rec)
        parsed_records = filtered

    anomalies = []
    begins = {}
    ends = {}
    begin_order = []
    end_order = []
    invalid_entries = []

    for rec in parsed_records:
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
        else:
            if effect_id in ends:
                anomalies.append({
                    "line": rec["line"],
                    "reason": "duplicate-end",
                    "effectId": effect_id,
                })
            ends[effect_id] = record
            end_order.append(effect_id)

    anomaly_effect_ids = set()
    for effect_id in begin_order:
        if begin_order.count(effect_id) > 1:
            anomaly_effect_ids.add(effect_id)
    for effect_id in end_order:
        if end_order.count(effect_id) > 1:
            anomaly_effect_ids.add(effect_id)

    for effect_id in set(begin_order) & set(end_order):
        begin_idx = None
        end_idx = None
        for i, rec in enumerate(parsed_records):
            if not rec["valid"] or rec["raw"]["effectId"] != effect_id:
                continue
            if rec["raw"]["phase"] == PHASE_BEGIN and begin_idx is None:
                begin_idx = i
            elif rec["raw"]["phase"] == PHASE_END and end_idx is None:
                end_idx = i
        if begin_idx is not None and end_idx is not None and end_idx < begin_idx:
            anomalies.append({
                "reason": "end-before-begin",
                "effectId": effect_id,
            })
            anomaly_effect_ids.add(effect_id)

    for effect_id in set(begin_order) & set(end_order):
        if effect_id in anomaly_effect_ids:
            continue
        if begins[effect_id]["slotRef"] != ends[effect_id]["slotRef"]:
            anomalies.append({
                "reason": "slot-ref-mismatch",
                "effectId": effect_id,
            })
            anomaly_effect_ids.add(effect_id)

    for effect_id in set(begin_order) & set(end_order):
        if begin_order.count(effect_id) > 1 or end_order.count(effect_id) > 1:
            anomaly_effect_ids.add(effect_id)

    begin_counts = {}
    end_counts = {}
    end_seen = {}
    for rec in parsed_records:
        if not rec["valid"]:
            continue
        eid = rec["raw"]["effectId"]
        if rec["raw"]["phase"] == PHASE_BEGIN:
            begin_counts[eid] = begin_counts.get(eid, 0) + 1
        else:
            end_counts[eid] = end_counts.get(eid, 0) + 1

    effects = []
    merged_from_begin = set()

    for rec in parsed_records:
        if not rec["valid"]:
            entry = invalid_entries.pop(0) if invalid_entries else _unknown_effect_entry()
            effects.append(entry)
            continue

        record = rec["raw"]
        effect_id = record["effectId"]

        if record["phase"] == PHASE_BEGIN:
            entry = _effect_entry_from_begin(record)
            if effect_id in anomaly_effect_ids:
                entry["state"] = STATE_POSSIBLY_APPLIED
                effects.append(entry)
            elif (
                effect_id in ends
                and begin_counts.get(effect_id, 0) == 1
                and end_counts.get(effect_id, 0) == 1
            ):
                entry = _merge_begin_end(entry, ends[effect_id])
                merged_from_begin.add(effect_id)
                effects.append(entry)
            else:
                effects.append(entry)
        else:
            if effect_id not in begins:
                entry = _effect_entry_from_end(record)
                anomalies.append({
                    "line": rec["line"],
                    "reason": "orphan-end",
                    "effectId": effect_id,
                })
                effects.append(entry)
            elif effect_id in merged_from_begin:
                continue
            elif effect_id in anomaly_effect_ids:
                end_seen[effect_id] = end_seen.get(effect_id, 0) + 1
                if end_counts.get(effect_id, 0) > 1:
                    entry = _effect_entry_from_end(record)
                    effects.append(entry)

    return _ok(effects=effects, torn=torn, anomalies=anomalies)


def _blocker(reason, *, slot=None, slot_ref=None, detail=None):
    return {
        "reason": reason,
        "slot": slot,
        "slotRef": slot_ref,
        "detail": detail,
    }


def partial_failure_report(slots):
    """Build a fail-closed partial-failure report from slot provisioning results."""
    blockers = []
    warnings = []
    failed_slots = []
    healthy_slots = []

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
            or replay_result is None
        ):
            blockers.append(_blocker(
                BLOCK_SLOT_ENTRY_INVALID,
                slot=slot if isinstance(slot, str) else None,
                slot_ref=slot_ref if isinstance(slot_ref, str) else None,
            ))
            continue

        if outcome not in SLOT_OUTCOMES:
            blockers.append(_blocker(
                BLOCK_SLOT_OUTCOME_INVALID,
                slot=slot,
                slot_ref=slot_ref,
            ))
        elif outcome == SLOT_OUTCOME_PROVISIONED:
            healthy_slots.append({"slot": slot, "slotRef": slot_ref})
            continue

        failed_slots.append({"slot": slot, "slotRef": slot_ref})
        slot_warnings = []

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

        if not isinstance(replay_result, dict) or replay_result.get("ok") is not True:
            blockers.append(_blocker(
                BLOCK_JOURNAL_UNREADABLE,
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

            for effect in replay_result.get("effects", []):
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
