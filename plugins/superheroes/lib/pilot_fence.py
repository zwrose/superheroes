"""Reassignment acceptance probe — grades reach-checks and applies fail-closed retirement.

Scope: this module grades the probe and applies the fail-closed retirement. ``failed → retired``
is an edge that already exists in ``pilot_lifecycle``'s transition table — this module supplies
the *reason* to take it, not a new transition. Making a failed slot reusable again is deliberately
**not** built here.

Non-goals: no pause/reassign/resume runtime work — callers report reach-check answers; this module
grades them and applies the fail-closed ``retire`` consequence when the probe does not pass.
"""
from datetime import datetime

import pilot_lifecycle
import pilot_slot

SCHEMA = 1

CHECK_BROWSER = "browser"
CHECK_PORT = "port"
CHECK_WORKTREE = "worktree"
CHECK_DATASTORE = "datastore"
REQUIRED_CHECKS = ("browser", "port", "worktree", "datastore")

ANSWER_UNREACHABLE = "unreachable"
ANSWER_REACHABLE = "reachable"
ANSWER_INDETERMINATE = "indeterminate"
ANSWERS = frozenset({ANSWER_UNREACHABLE, ANSWER_REACHABLE, ANSWER_INDETERMINATE})

VERDICT_TRUSTED = "trusted"
VERDICT_RETIRE = "retire"

RETIRE_DETAIL_REASON = "reassignment-probe-failed"

REASON_FENCE_SLOT_REF_INVALID = "fence-slot-ref-invalid"
REASON_FENCE_CHECKS_INVALID = "fence-checks-invalid"
REASON_FENCE_CHECK_UNKNOWN = "fence-check-unknown"
REASON_FENCE_CHECK_MISSING = "fence-check-missing"
REASON_FENCE_ANSWER_INVALID = "fence-answer-invalid"
REASON_FENCE_CHECK_FAILED = "fence-check-failed"
REASON_FENCE_RESULT_INVALID = "fence-result-invalid"
REASON_FENCE_RESULT_SLOT_MISMATCH = "fence-result-slot-mismatch"
REASON_FENCE_NOW_INVALID = "fence-now-invalid"
REASON_FENCE_SLOTS_DIR_INVALID = "fence-slots-dir-invalid"
REASON_FENCE_VERDICT_NOT_APPLICABLE = "fence-verdict-not-applicable"


def _ok(**extra):
    out = {"ok": True, "reason": None}
    out.update(extra)
    return out


def _fail(reason, **extra):
    out = {"ok": False, "reason": reason}
    out.update(extra)
    return out


def _is_str_path(value):
    return isinstance(value, str) and bool(value)


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


def _is_mapping(value):
    return isinstance(value, dict)


def _valid_slot_ref(ref):
    try:
        pilot_slot.parse_slot_ref(ref)
    except pilot_slot.PilotSlotError:
        return False
    return True


def _probe_refuse(reason, slot_ref=None):
    return {
        "ok": False,
        "reason": reason,
        "slotRef": slot_ref,
        "verdict": VERDICT_RETIRE,
        "checks": {},
        "failed": [],
    }


def _validate_probe_result(result):
    if not isinstance(result, dict):
        return False
    verdict = result.get("verdict")
    if verdict not in (VERDICT_TRUSTED, VERDICT_RETIRE):
        return False
    slot_ref_val = result.get("slotRef")
    if slot_ref_val is None:
        return True
    return _valid_slot_ref(slot_ref_val)


def reassignment_probe_result(slot_ref, checks):
    """Grade reach-check answers for a reassignment probe. Never raises."""
    if not _valid_slot_ref(slot_ref):
        return _probe_refuse(REASON_FENCE_SLOT_REF_INVALID, slot_ref=None)
    if not _is_mapping(checks):
        return _probe_refuse(REASON_FENCE_CHECKS_INVALID, slot_ref=slot_ref)
    for key in checks:
        if key not in REQUIRED_CHECKS:
            return _probe_refuse(REASON_FENCE_CHECK_UNKNOWN, slot_ref=slot_ref)
    for name in REQUIRED_CHECKS:
        if name not in checks:
            return _probe_refuse(REASON_FENCE_CHECK_MISSING, slot_ref=slot_ref)
    graded = {}
    for name in REQUIRED_CHECKS:
        answer = checks[name]
        if not isinstance(answer, str) or answer not in ANSWERS:
            return _probe_refuse(REASON_FENCE_ANSWER_INVALID, slot_ref=slot_ref)
        graded[name] = answer
    failed = [
        name
        for name in REQUIRED_CHECKS
        if graded[name] != ANSWER_UNREACHABLE
    ]
    if failed:
        return {
            "ok": True,
            "reason": REASON_FENCE_CHECK_FAILED,
            "slotRef": slot_ref,
            "verdict": VERDICT_RETIRE,
            "checks": dict(graded),
            "failed": failed,
        }
    return {
        "ok": True,
        "reason": None,
        "slotRef": slot_ref,
        "verdict": VERDICT_TRUSTED,
        "checks": dict(graded),
        "failed": [],
    }


def apply_probe_verdict(slots_dir_path, slot_ref, result, *, now):
    """Apply a ``retire`` probe verdict to the slot record. Never raises."""
    if not _is_str_path(slots_dir_path):
        return _fail(REASON_FENCE_SLOTS_DIR_INVALID, applied=False, record=None)
    if not _is_iso8601_utc(now):
        return _fail(REASON_FENCE_NOW_INVALID, applied=False, record=None)
    if not _valid_slot_ref(slot_ref):
        return _fail(REASON_FENCE_SLOT_REF_INVALID, applied=False, record=None)
    if not _validate_probe_result(result):
        return _fail(REASON_FENCE_RESULT_INVALID, applied=False, record=None)
    if result.get("slotRef") != slot_ref:
        return _fail(REASON_FENCE_RESULT_SLOT_MISMATCH, applied=False, record=None)
    verdict = result["verdict"]
    if verdict == VERDICT_TRUSTED:
        return _ok(
            reason=REASON_FENCE_VERDICT_NOT_APPLICABLE,
            applied=False,
            record=None,
        )
    slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    failed = result.get("failed") or []

    def _retire(record):
        gen_result = pilot_lifecycle.generation_check(generation, record["generation"])
        if not gen_result["ok"]:
            raise pilot_lifecycle.PilotLifecycleError(gen_result["reason"])
        return pilot_lifecycle.transition(
            record,
            pilot_lifecycle.STATE_RETIRED,
            now=now,
            detail={"reason": RETIRE_DETAIL_REASON, "failed": failed},
        )

    mutated = pilot_lifecycle.mutate(slots_dir_path, slot, _retire)
    if not mutated["ok"]:
        return _fail(mutated["reason"], applied=False, record=None)
    return _ok(applied=True, record=mutated["record"])
