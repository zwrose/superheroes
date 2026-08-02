"""Pilot wave deadline runtime and wave-end teardown.

Non-goals: app-instance control (pilot_appctl), automation-server fencing (C7),
cleanup/reclaim handlers (C9/A2b) — those arrive as injected handlers.
"""
import json
import math
import os
import stat
import time
from datetime import datetime

import pilot_journal
import pilot_lifecycle
import pilot_slot
import store_core

SCHEMA = 1

PHASE_RUNNING = "running"
PHASE_WINDING_DOWN = "winding-down"
PHASE_EXPIRED = "expired"

INTENT_COMPLETE = "complete"
INTENT_PARK = "park"

STEP_APP = "app-instance"
STEP_AUTOMATION = "automation-server"
STEP_CLEANUP = "cleanup"
STEP_RECLAIM = "reclaim"
FENCE_STEPS = (STEP_APP, STEP_AUTOMATION)
DESTRUCTIVE_STEPS = (STEP_CLEANUP, STEP_RECLAIM)
STEP_ORDER = FENCE_STEPS + DESTRUCTIVE_STEPS

STATUS_CONFIRMED = "confirmed"
STATUS_FAILED = "failed"
STATUS_UNAVAILABLE = "unavailable"
STATUS_INDETERMINATE = "indeterminate"
STATUS_REFUSED_PARK = "refused-park"
STATUS_NOT_REACHED = "not-reached"

DISPOSITION_TORN_DOWN = "torn-down"
DISPOSITION_PARKED = "parked"
DISPOSITION_INCOMPLETE = "incomplete"

REASON_DEADLINE_INVALID = "wave-deadline-invalid"
REASON_MARGIN_INVALID = "wave-margin-invalid"
REASON_CLOCK_INVALID = "wave-clock-invalid"
REASON_ANCHOR_INVALID = "wave-anchor-invalid"
REASON_SLOT_ENTRY_INVALID = "wave-slot-entry-invalid"
REASON_SLOTS_INVALID = "wave-slots-invalid"
REASON_STEP_UNAVAILABLE = "wave-step-unavailable"
REASON_STEP_FAILED = "wave-step-failed"
REASON_STEP_INDETERMINATE = "wave-step-indeterminate"
REASON_STEP_RESULT_INVALID = "wave-step-result-invalid"
REASON_STEP_RECEIPT_MISSING = "wave-step-receipt-missing"
REASON_STEP_OVERRAN = "wave-step-overran"
REASON_PARK_DESTRUCTIVE_REFUSED = "wave-park-destructive-refused"
REASON_PARK_LATCH_WRITE_FAILED = "wave-park-latch-write-failed"
REASON_PARK_LATCH_UNREADABLE = "wave-park-latch-unreadable"
REASON_FENCE_UNCONFIRMED = "wave-fence-unconfirmed"

_REASON_MAX_LEN = 500

# Bounded handler calls measure elapsed time on the injected monotonic clock and
# downgrade late answers to indeterminate — this cannot interrupt a hung in-process
# handler, only refuse its late answer.


class PilotWaveError(Exception):
    """Raised when wave validation refuses."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _is_str_path(value):
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


def _is_nonneg_number(value):
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    if math.isnan(value) or math.isinf(value):
        return False
    return value >= 0


def _is_real_number(value):
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    if math.isnan(value) or math.isinf(value):
        return False
    return True


def _fail(reason, **kwargs):
    result = {"ok": False, "reason": reason}
    result.update(kwargs)
    return result


def _ok(**kwargs):
    result = {"ok": True, "reason": None}
    result.update(kwargs)
    return result


def _blocker(reason, *, slot=None, slot_ref=None, step=None, detail=None):
    return {
        "reason": reason,
        "slot": slot,
        "slotRef": slot_ref,
        "step": step,
        "detail": detail,
    }


def _default_monotonic():
    return time.monotonic()


def park_latch_path(slots_dir_path, slot):
    if not _is_str_path(slots_dir_path):
        raise PilotWaveError(REASON_PARK_LATCH_WRITE_FAILED)
    slot = pilot_slot.validate_slot_id(slot)
    return os.path.join(slots_dir_path, slot, "park.json")


def _validate_latch_record(record, *, slot, slot_ref):
    if not isinstance(record, dict):
        return False
    if record.get("schemaVersion") != SCHEMA:
        return False
    if record.get("slot") != slot:
        return False
    if record.get("slotRef") != slot_ref:
        return False
    if not _is_iso8601_utc(record.get("latchedAt")):
        return False
    reason = record.get("reason")
    if not isinstance(reason, str):
        return False
    return True


def _read_latch_file(path):
    """Read park latch from disk. Never raises."""
    if not _is_str_path(path):
        return {"ok": False, "reason": REASON_PARK_LATCH_UNREADABLE, "record": None}
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {"ok": True, "reason": None, "record": None, "absent": True}
    except OSError:
        return {"ok": False, "reason": REASON_PARK_LATCH_UNREADABLE, "record": None}
    try:
        stat_result = os.fstat(fd)
        if not stat.S_ISREG(stat_result.st_mode):
            return {"ok": False, "reason": REASON_PARK_LATCH_UNREADABLE, "record": None}
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks).decode("utf-8")
    except OSError:
        return {"ok": False, "reason": REASON_PARK_LATCH_UNREADABLE, "record": None}
    except UnicodeDecodeError:
        return {"ok": False, "reason": REASON_PARK_LATCH_UNREADABLE, "record": None}
    finally:
        os.close(fd)
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {"ok": False, "reason": REASON_PARK_LATCH_UNREADABLE, "record": None}
    if not isinstance(parsed, dict):
        return {"ok": False, "reason": REASON_PARK_LATCH_UNREADABLE, "record": None}
    return {"ok": True, "reason": None, "record": parsed, "absent": False}


def _write_latch_file(path, record):
    """Durably persist a park latch record. Never raises."""
    if not _is_str_path(path):
        return {"ok": False, "reason": REASON_PARK_LATCH_WRITE_FAILED}
    if not isinstance(record, dict):
        return {"ok": False, "reason": REASON_PARK_LATCH_WRITE_FAILED}
    parent = os.path.dirname(os.path.abspath(path)) or "."
    try:
        pilot_lifecycle._refuse_unsafe_slot_dir(parent)
    except pilot_lifecycle.PilotLifecycleError:
        return {"ok": False, "reason": REASON_PARK_LATCH_WRITE_FAILED}
    if os.path.islink(path):
        return {"ok": False, "reason": REASON_PARK_LATCH_WRITE_FAILED}
    try:
        text = json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n"
        store_core.atomic_write(path, text)
        dir_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        return {"ok": False, "reason": REASON_PARK_LATCH_WRITE_FAILED}
    return {"ok": True, "reason": None}


def wave_anchor(*, launched_at, deadline_seconds, margin_seconds, monotonic=None):
    """Build the wave's deadline anchor. Returns {"ok", "reason", "anchor"}."""
    try:
        if launched_at is None or not _is_iso8601_utc(launched_at):
            return _fail(REASON_ANCHOR_INVALID, anchor=None)
        if not _is_nonneg_number(deadline_seconds):
            return _fail(REASON_DEADLINE_INVALID, anchor=None)
        if not _is_nonneg_number(margin_seconds):
            return _fail(REASON_MARGIN_INVALID, anchor=None)
        mono_fn = monotonic if monotonic is not None else _default_monotonic
        launched_at_mono = mono_fn()
        if not _is_real_number(launched_at_mono):
            return _fail(REASON_CLOCK_INVALID, anchor=None)
        anchor = {
            "schemaVersion": SCHEMA,
            "launchedAt": launched_at.strip(),
            "launchedAtMono": launched_at_mono,
            "deadlineSeconds": deadline_seconds,
            "marginSeconds": margin_seconds,
        }
        return _ok(anchor=anchor)
    except BaseException:
        return _fail(REASON_ANCHOR_INVALID, anchor=None)


def _validate_anchor(anchor):
    if not isinstance(anchor, dict):
        return False
    if anchor.get("schemaVersion") != SCHEMA:
        return False
    if not _is_iso8601_utc(anchor.get("launchedAt")):
        return False
    if not _is_real_number(anchor.get("launchedAtMono")):
        return False
    if not _is_nonneg_number(anchor.get("deadlineSeconds")):
        return False
    if not _is_nonneg_number(anchor.get("marginSeconds")):
        return False
    return True


def wave_phase(anchor, *, monotonic=None):
    """Returns {"ok", "reason", "phase", "elapsed", "terminusIn"}."""
    try:
        if not _validate_anchor(anchor):
            return _fail(
                REASON_CLOCK_INVALID,
                phase=None,
                elapsed=None,
                terminusIn=None,
            )
        mono_fn = monotonic if monotonic is not None else _default_monotonic
        now_mono = mono_fn()
        if not _is_real_number(now_mono):
            return _fail(
                REASON_CLOCK_INVALID,
                phase=None,
                elapsed=None,
                terminusIn=None,
            )
        launched_mono = anchor["launchedAtMono"]
        if now_mono < launched_mono:
            return _fail(
                REASON_CLOCK_INVALID,
                phase=None,
                elapsed=None,
                terminusIn=None,
            )
        elapsed = now_mono - launched_mono
        deadline = anchor["deadlineSeconds"]
        margin = anchor["marginSeconds"]
        terminus = deadline + margin
        if elapsed < deadline:
            phase = PHASE_RUNNING
        elif elapsed < terminus:
            phase = PHASE_WINDING_DOWN
        else:
            phase = PHASE_EXPIRED
        terminus_in = max(0.0, terminus - elapsed)
        return _ok(phase=phase, elapsed=elapsed, terminusIn=terminus_in)
    except BaseException:
        return _fail(
            REASON_CLOCK_INVALID,
            phase=None,
            elapsed=None,
            terminusIn=None,
        )


def admit_work(anchor, *, monotonic=None):
    """{"ok": bool, "reason": str|None, "phase": str} — False in every phase except running."""
    try:
        phase_result = wave_phase(anchor, monotonic=monotonic)
        if not phase_result["ok"]:
            return {
                "ok": False,
                "reason": phase_result["reason"],
                "phase": phase_result.get("phase"),
            }
        phase = phase_result["phase"]
        if phase != PHASE_RUNNING:
            return {"ok": False, "reason": None, "phase": phase}
        return {"ok": True, "reason": None, "phase": phase}
    except BaseException:
        return {"ok": False, "reason": REASON_CLOCK_INVALID, "phase": None}


def latch_park(slots_dir_path, slot, *, slot_ref, now, reason, timeout=30.0):
    """Durably record the park intent under the per-slot lock. {"ok", "reason", "latch"}."""
    try:
        if not _is_str_path(slots_dir_path):
            return _fail(REASON_PARK_LATCH_WRITE_FAILED, latch=None)
        if not _is_iso8601_utc(now):
            return _fail(REASON_PARK_LATCH_WRITE_FAILED, latch=None)
        if not isinstance(reason, str):
            return _fail(REASON_PARK_LATCH_WRITE_FAILED, latch=None)
        if not _is_timeout(timeout):
            return _fail(REASON_PARK_LATCH_WRITE_FAILED, latch=None)
        try:
            pilot_slot.validate_slot_id(slot)
        except pilot_slot.PilotSlotError:
            return _fail(REASON_PARK_LATCH_WRITE_FAILED, latch=None)
        try:
            pilot_slot.parse_slot_ref(slot_ref)
        except pilot_slot.PilotSlotError:
            return _fail(REASON_PARK_LATCH_WRITE_FAILED, latch=None)
        parsed_slot, _ = pilot_slot.parse_slot_ref(slot_ref)
        if parsed_slot != slot:
            return _fail(REASON_PARK_LATCH_WRITE_FAILED, latch=None)

        path = park_latch_path(slots_dir_path, slot)
        try:
            with pilot_lifecycle.slot_lock(slots_dir_path, slot, timeout=timeout):
                existing = _read_latch_file(path)
                if not existing["ok"]:
                    return _fail(REASON_PARK_LATCH_WRITE_FAILED, latch=None)
                if existing["record"] is not None:
                    if _validate_latch_record(
                        existing["record"], slot=slot, slot_ref=slot_ref
                    ):
                        return _ok(latch=existing["record"])
                    return _fail(REASON_PARK_LATCH_WRITE_FAILED, latch=None)
                latch = {
                    "schemaVersion": SCHEMA,
                    "slot": slot,
                    "slotRef": slot_ref,
                    "latchedAt": now.strip(),
                    "reason": reason,
                }
                written = _write_latch_file(path, latch)
                if not written["ok"]:
                    return _fail(written["reason"], latch=None)
                return _ok(latch=latch)
        except pilot_lifecycle.PilotLifecycleError as exc:
            return _fail(exc.reason, latch=None)
    except BaseException:
        return _fail(REASON_PARK_LATCH_WRITE_FAILED, latch=None)


def _latch_state_from_file(slots_dir_path, slot):
    """Read latch state from disk without acquiring the slot lock. Never raises."""
    path = park_latch_path(slots_dir_path, slot)
    loaded = _read_latch_file(path)
    if loaded.get("absent"):
        return {"latched": False, "unreadable": False, "latch": None}
    if not loaded["ok"]:
        return {"latched": True, "unreadable": True, "latch": None}
    record = loaded["record"]
    if record is None:
        return {"latched": False, "unreadable": False, "latch": None}
    if not isinstance(record, dict):
        return {"latched": True, "unreadable": True, "latch": None}
    if record.get("schemaVersion") != SCHEMA:
        return {"latched": True, "unreadable": True, "latch": None}
    if record.get("slot") != slot:
        return {"latched": True, "unreadable": True, "latch": None}
    if not _is_iso8601_utc(record.get("latchedAt")):
        return {"latched": True, "unreadable": True, "latch": None}
    if not isinstance(record.get("reason"), str):
        return {"latched": True, "unreadable": True, "latch": None}
    if not isinstance(record.get("slotRef"), str):
        return {"latched": True, "unreadable": True, "latch": None}
    return {"latched": True, "unreadable": False, "latch": record}


def read_park_latch(slots_dir_path, slot, *, timeout=30.0):
    """{"ok", "reason", "latched": bool, "latch": {...}|None}."""
    try:
        if not _is_str_path(slots_dir_path):
            return _fail(REASON_PARK_LATCH_UNREADABLE, latched=True, latch=None)
        if not _is_timeout(timeout):
            return _fail(REASON_PARK_LATCH_UNREADABLE, latched=True, latch=None)
        try:
            pilot_slot.validate_slot_id(slot)
        except pilot_slot.PilotSlotError:
            return _fail(REASON_PARK_LATCH_UNREADABLE, latched=True, latch=None)

        try:
            with pilot_lifecycle.slot_lock(slots_dir_path, slot, timeout=timeout):
                state = _latch_state_from_file(slots_dir_path, slot)
                if state["unreadable"]:
                    return _fail(
                        REASON_PARK_LATCH_UNREADABLE,
                        latched=True,
                        latch=state.get("latch"),
                    )
                if state["latched"]:
                    return _ok(latched=True, latch=state["latch"])
                return _ok(latched=False, latch=None)
        except pilot_lifecycle.PilotLifecycleError as exc:
            return _fail(exc.reason, latched=True, latch=None)
    except BaseException:
        return _fail(REASON_PARK_LATCH_UNREADABLE, latched=True, latch=None)


def _validate_receipt(receipt, *, step, slot_ref):
    if not isinstance(receipt, dict):
        return False
    if receipt.get("step") != step:
        return False
    if receipt.get("slotRef") != slot_ref:
        return False
    if not _is_iso8601_utc(receipt.get("observedAt")):
        return False
    evidence = receipt.get("evidence")
    if not isinstance(evidence, str) or not evidence:
        return False
    return True


def validate_step_result(result, *, step, slot_ref):
    """Map a handler S-E result to a step status."""
    try:
        if not isinstance(result, dict):
            return {
                "status": STATUS_INDETERMINATE,
                "reason": REASON_STEP_RESULT_INVALID,
                "receipt": None,
            }
        outcome = result.get("outcome")
        if outcome not in (
            pilot_journal.OUTCOME_APPLIED,
            pilot_journal.OUTCOME_NOT_APPLIED,
            pilot_journal.OUTCOME_INDETERMINATE,
        ):
            return {
                "status": STATUS_INDETERMINATE,
                "reason": REASON_STEP_RESULT_INVALID,
                "receipt": None,
            }
        if outcome == pilot_journal.OUTCOME_APPLIED:
            receipt = result.get("receipt")
            if not _validate_receipt(receipt, step=step, slot_ref=slot_ref):
                return {
                    "status": STATUS_INDETERMINATE,
                    "reason": REASON_STEP_RECEIPT_MISSING,
                    "receipt": None,
                }
            return {
                "status": STATUS_CONFIRMED,
                "reason": None,
                "receipt": receipt,
            }
        if outcome == pilot_journal.OUTCOME_NOT_APPLIED:
            return {
                "status": STATUS_FAILED,
                "reason": REASON_STEP_FAILED,
                "receipt": None,
            }
        return {
            "status": STATUS_INDETERMINATE,
            "reason": REASON_STEP_INDETERMINATE,
            "receipt": None,
        }
    except BaseException:
        return {
            "status": STATUS_INDETERMINATE,
            "reason": REASON_STEP_INDETERMINATE,
            "receipt": None,
        }


def assert_destructive_allowed(step, *, intent, latched):
    """Return {"ok", "reason"} — refuse destructive work when parked or latched."""
    try:
        if intent == INTENT_PARK or latched:
            return _fail(REASON_PARK_DESTRUCTIVE_REFUSED)
        return _ok()
    except BaseException:
        return _fail(REASON_PARK_DESTRUCTIVE_REFUSED)


def _empty_step_result(status, reason):
    return {
        "status": status,
        "reason": reason,
        "receipt": None,
        "elapsed": None,
    }


def _run_handler(step, entry, handlers, context, mono_fn, timeout_seconds):
    """Invoke a handler and return step result dict."""
    handler = handlers.get(step) if isinstance(handlers, dict) else None
    if handler is None:
        return _empty_step_result(STATUS_UNAVAILABLE, REASON_STEP_UNAVAILABLE)

    start = mono_fn()
    try:
        raw = handler(context)
    except BaseException as exc:
        reason_text = repr(exc)
        if len(reason_text) > _REASON_MAX_LEN:
            reason_text = reason_text[:_REASON_MAX_LEN]
        elapsed = mono_fn() - start
        return {
            "status": STATUS_INDETERMINATE,
            "reason": REASON_STEP_INDETERMINATE,
            "receipt": None,
            "elapsed": elapsed,
        }

    elapsed = mono_fn() - start
    validated = validate_step_result(
        raw, step=step, slot_ref=entry["slotRef"]
    )
    if (
        timeout_seconds is not None
        and _is_nonneg_number(timeout_seconds)
        and elapsed > timeout_seconds
    ):
        return {
            "status": STATUS_INDETERMINATE,
            "reason": REASON_STEP_OVERRAN,
            "receipt": None,
            "elapsed": elapsed,
        }
    return {
        "status": validated["status"],
        "reason": validated["reason"],
        "receipt": validated["receipt"],
        "elapsed": elapsed,
    }


def _all_fences_confirmed(steps):
    for step in FENCE_STEPS:
        if steps.get(step, {}).get("status") != STATUS_CONFIRMED:
            return False
    return True


def _journal_outcome_for_status(status):
    if status == STATUS_CONFIRMED:
        return pilot_journal.OUTCOME_APPLIED
    if status == STATUS_FAILED:
        return pilot_journal.OUTCOME_NOT_APPLIED
    return pilot_journal.OUTCOME_INDETERMINATE


def _run_destructive_step(
    step,
    entry,
    handlers,
    context,
    mono_fn,
    timeout_seconds,
    slots_dir_path,
    journal_path,
    now_fn,
    lock_timeout,
):
    """Run a destructive step with latch re-read and optional journaling."""
    slot = entry["slot"]
    slot_ref = entry["slotRef"]
    intent = entry["intent"]

    if intent == INTENT_PARK:
        return _empty_step_result(STATUS_REFUSED_PARK, REASON_PARK_DESTRUCTIVE_REFUSED)

    if not _all_fences_confirmed(context["steps"]):
        return _empty_step_result(STATUS_NOT_REACHED, REASON_FENCE_UNCONFIRMED)

    try:
        with pilot_lifecycle.slot_lock(slots_dir_path, slot, timeout=lock_timeout):
            latch_state = _latch_state_from_file(slots_dir_path, slot)
            latched = latch_state["latched"]
            allowed = assert_destructive_allowed(step, intent=intent, latched=latched)
            if not allowed["ok"]:
                return _empty_step_result(STATUS_REFUSED_PARK, allowed["reason"])
    except pilot_lifecycle.PilotLifecycleError as exc:
        return {
            "status": STATUS_INDETERMINATE,
            "reason": exc.reason,
            "receipt": None,
            "elapsed": None,
        }

    effect_id = None
    if step == STEP_CLEANUP:
        now = now_fn()
        begin = pilot_journal.begin_effect(
            journal_path,
            slot_ref=slot_ref,
            kind=pilot_journal.KIND_NAMESPACE_TOUCHED,
            at=now,
        )
        if not begin["ok"]:
            return {
                "status": STATUS_INDETERMINATE,
                "reason": REASON_STEP_INDETERMINATE,
                "receipt": None,
                "elapsed": None,
            }
        effect_id = begin["effectId"]

    result = _run_handler(step, entry, handlers, context, mono_fn, timeout_seconds)

    if step == STEP_CLEANUP and effect_id is not None:
        end_at = now_fn()
        pilot_journal.end_effect(
            journal_path,
            slot_ref=slot_ref,
            effect_id=effect_id,
            outcome=_journal_outcome_for_status(result["status"]),
            at=end_at,
            reason=result["reason"],
        )

    return result


def _compute_disposition(intent, steps):
    if intent == INTENT_COMPLETE:
        if all(steps.get(s, {}).get("status") == STATUS_CONFIRMED for s in STEP_ORDER):
            return DISPOSITION_TORN_DOWN
        return DISPOSITION_INCOMPLETE
    if intent == INTENT_PARK:
        fences_ok = all(
            steps.get(s, {}).get("status") == STATUS_CONFIRMED for s in FENCE_STEPS
        )
        destructive_refused = all(
            steps.get(s, {}).get("status") == STATUS_REFUSED_PARK
            for s in DESTRUCTIVE_STEPS
        )
        if fences_ok and destructive_refused:
            return DISPOSITION_PARKED
    return DISPOSITION_INCOMPLETE


def _collect_blockers(slot, slot_ref, intent, steps, disposition):
    blockers = []
    if disposition in (DISPOSITION_TORN_DOWN, DISPOSITION_PARKED):
        return blockers
    for step in STEP_ORDER:
        step_result = steps.get(step, {})
        status = step_result.get("status")
        if status == STATUS_CONFIRMED:
            continue
        if intent == INTENT_PARK and status == STATUS_REFUSED_PARK:
            continue
        blockers.append(_blocker(
            step_result.get("reason") or REASON_STEP_INDETERMINATE,
            slot=slot,
            slot_ref=slot_ref,
            step=step,
        ))
    return blockers


def teardown_slot(
    entry,
    *,
    handlers,
    slots_dir_path,
    journal_path,
    now_fn,
    monotonic=None,
):
    """Two-phase teardown for one slot entry."""
    try:
        if not isinstance(entry, dict):
            return {
                "slot": None,
                "slotRef": None,
                "intent": None,
                "steps": {},
                "disposition": DISPOSITION_INCOMPLETE,
                "blockers": [_blocker(REASON_SLOT_ENTRY_INVALID)],
            }

        slot = entry.get("slot")
        slot_ref = entry.get("slotRef")
        intent = entry.get("intent")
        timeout_seconds = entry.get("stepTimeoutSeconds")

        if (
            not isinstance(slot, str)
            or not slot
            or not isinstance(slot_ref, str)
            or intent not in (INTENT_COMPLETE, INTENT_PARK)
        ):
            return {
                "slot": slot if isinstance(slot, str) else None,
                "slotRef": slot_ref if isinstance(slot_ref, str) else None,
                "intent": intent,
                "steps": {},
                "disposition": DISPOSITION_INCOMPLETE,
                "blockers": [_blocker(
                    REASON_SLOT_ENTRY_INVALID,
                    slot=slot if isinstance(slot, str) else None,
                    slot_ref=slot_ref if isinstance(slot_ref, str) else None,
                )],
            }

        try:
            parsed_slot, _ = pilot_slot.parse_slot_ref(slot_ref)
            if parsed_slot != slot:
                raise pilot_slot.PilotSlotError("mismatch")
        except pilot_slot.PilotSlotError:
            return {
                "slot": slot,
                "slotRef": slot_ref,
                "intent": intent,
                "steps": {},
                "disposition": DISPOSITION_INCOMPLETE,
                "blockers": [_blocker(REASON_SLOT_ENTRY_INVALID, slot=slot, slot_ref=slot_ref)],
            }

        mono_fn = monotonic if monotonic is not None else _default_monotonic
        lock_timeout = 30.0

        context = {
            "step": None,
            "slot": slot,
            "slotRef": slot_ref,
            "intent": intent,
            "instance": entry.get("instance"),
            "allocation": entry.get("allocation"),
            "steps": {},
        }

        steps = {}
        for step in FENCE_STEPS:
            context["step"] = step
            steps[step] = _run_handler(
                step, entry, handlers, context, mono_fn, timeout_seconds
            )
        context["steps"] = steps

        for step in DESTRUCTIVE_STEPS:
            context["step"] = step
            if intent == INTENT_PARK:
                steps[step] = _empty_step_result(
                    STATUS_REFUSED_PARK, REASON_PARK_DESTRUCTIVE_REFUSED
                )
                continue
            if step == STEP_RECLAIM:
                cleanup_status = steps.get(STEP_CLEANUP, {}).get("status")
                if cleanup_status != STATUS_CONFIRMED:
                    steps[step] = _empty_step_result(STATUS_NOT_REACHED, None)
                    continue
            steps[step] = _run_destructive_step(
                step,
                entry,
                handlers,
                context,
                mono_fn,
                timeout_seconds,
                slots_dir_path,
                journal_path,
                now_fn,
                lock_timeout,
            )
            context["steps"] = steps

        disposition = _compute_disposition(intent, steps)
        blockers = _collect_blockers(slot, slot_ref, intent, steps, disposition)

        return {
            "slot": slot,
            "slotRef": slot_ref,
            "intent": intent,
            "steps": steps,
            "disposition": disposition,
            "blockers": blockers,
        }
    except BaseException:
        return {
            "slot": entry.get("slot") if isinstance(entry, dict) else None,
            "slotRef": entry.get("slotRef") if isinstance(entry, dict) else None,
            "intent": entry.get("intent") if isinstance(entry, dict) else None,
            "steps": {},
            "disposition": DISPOSITION_INCOMPLETE,
            "blockers": [_blocker(REASON_STEP_INDETERMINATE)],
        }


def run_teardown(
    slots,
    *,
    handlers,
    slots_dir_path,
    journal_path,
    now_fn,
    monotonic=None,
):
    """Run teardown_slot for each entry. Slots are independent."""
    try:
        if not isinstance(slots, (list, tuple)):
            return wave_report({
                "schemaVersion": SCHEMA,
                "complete": False,
                "slots": [],
                "counts": {"torn-down": 0, "parked": 0, "incomplete": 0},
                "blockers": [_blocker(REASON_SLOTS_INVALID)],
            })

        seen_slots = set()
        seen_slot_refs = set()
        results = []
        early_blockers = []

        for entry in slots:
            if not isinstance(entry, dict):
                early_blockers.append(_blocker(REASON_SLOT_ENTRY_INVALID))
                continue
            slot = entry.get("slot")
            slot_ref = entry.get("slotRef")
            if (
                not isinstance(slot, str)
                or not slot
                or not isinstance(slot_ref, str)
            ):
                early_blockers.append(_blocker(
                    REASON_SLOT_ENTRY_INVALID,
                    slot=slot if isinstance(slot, str) else None,
                    slot_ref=slot_ref if isinstance(slot_ref, str) else None,
                ))
                continue
            if slot in seen_slots or slot_ref in seen_slot_refs:
                early_blockers.append(_blocker(
                    REASON_SLOT_ENTRY_INVALID,
                    slot=slot,
                    slot_ref=slot_ref,
                ))
                continue
            seen_slots.add(slot)
            seen_slot_refs.add(slot_ref)
            results.append(teardown_slot(
                entry,
                handlers=handlers,
                slots_dir_path=slots_dir_path,
                journal_path=journal_path,
                now_fn=now_fn,
                monotonic=monotonic,
            ))

        if early_blockers:
            report = wave_report({
                "schemaVersion": SCHEMA,
                "complete": False,
                "slots": results,
                "counts": {"torn-down": 0, "parked": 0, "incomplete": 0},
                "blockers": early_blockers,
            })
            return report

        return wave_report({
            "schemaVersion": SCHEMA,
            "complete": False,
            "slots": results,
            "counts": {"torn-down": 0, "parked": 0, "incomplete": 0},
            "blockers": [],
        })
    except BaseException:
        return wave_report({
            "schemaVersion": SCHEMA,
            "complete": False,
            "slots": [],
            "counts": {"torn-down": 0, "parked": 0, "incomplete": 0},
            "blockers": [_blocker(REASON_SLOTS_INVALID)],
        })


def wave_report(results):
    """Build a wave teardown report from per-slot results."""
    try:
        if not isinstance(results, dict):
            return {
                "schemaVersion": SCHEMA,
                "complete": False,
                "slots": [],
                "counts": {"torn-down": 0, "parked": 0, "incomplete": 0},
                "blockers": [_blocker(REASON_SLOTS_INVALID)],
            }

        slots = results.get("slots")
        if not isinstance(slots, list):
            slots = []

        counts = {"torn-down": 0, "parked": 0, "incomplete": 0}
        blockers = list(results.get("blockers") or [])
        complete = True

        if not slots:
            complete = False

        for slot_result in slots:
            if not isinstance(slot_result, dict):
                complete = False
                counts["incomplete"] += 1
                blockers.append(_blocker(REASON_SLOT_ENTRY_INVALID))
                continue
            disposition = slot_result.get("disposition")
            if disposition == DISPOSITION_TORN_DOWN:
                counts["torn-down"] += 1
            elif disposition == DISPOSITION_PARKED:
                counts["parked"] += 1
            else:
                counts["incomplete"] += 1
                complete = False
            slot_blockers = slot_result.get("blockers") or []
            if slot_blockers:
                blockers.extend(slot_blockers)
                complete = False
            elif disposition not in (DISPOSITION_TORN_DOWN, DISPOSITION_PARKED):
                complete = False

        if not slots:
            complete = False

        return {
            "schemaVersion": SCHEMA,
            "complete": complete and not blockers,
            "slots": slots,
            "counts": counts,
            "blockers": blockers,
        }
    except BaseException:
        return {
            "schemaVersion": SCHEMA,
            "complete": False,
            "slots": [],
            "counts": {"torn-down": 0, "parked": 0, "incomplete": 0},
            "blockers": [_blocker(REASON_SLOTS_INVALID)],
        }
