"""Headless conformance-run contract for pilot framework surface exercise (C10).

Grades exercise records against a closed required-surface inventory so a conformance
report that skips a surface must never read as covered.

Non-goals: no CLI entry point and no browser driving — sibling orders own exercise
functions; this module owns the record contract, report aggregation, and run harness.
"""
import datetime
import re

SCHEMA = 1

RESULT_PASS = "pass"
RESULT_FAIL = "fail"
RESULT_SKIPPED = "skipped"
RESULT_REFUSED = "refused"
EXERCISE_RESULTS = frozenset({RESULT_PASS, RESULT_FAIL, RESULT_SKIPPED, RESULT_REFUSED})

REQUIRED_SURFACES = (
    "pilot_appctl.assert_unique_endpoints",
    "pilot_appctl.resolve_invocation",
    "pilot_artifacts.retain",
    "pilot_artifacts.sweep",
    "pilot_cleanup.cleanup_effect_receipt",
    "pilot_cleanup.receipt_valid_for",
    "pilot_cleanup.registry_record",
    "pilot_cleanup.resolve_containment",
    "pilot_cleanup.resurrection_plan",
    "pilot_mint.gate_off_receipt",
    "pilot_mint.run_gate_off_test",
    "pilot_reclaim.sweep",
    "pilot_wave.admit_work",
    "pilot_wave.assert_destructive_allowed",
    "pilot_wave.validate_step_result",
    "pilot_wave.wave_anchor",
    "pilot_wave.wave_phase",
)

REASON_RECORD_INVALID = "conformance-record-invalid"
REASON_RESULT_INVALID = "conformance-result-invalid"
REASON_EXERCISE_NAME_INVALID = "conformance-exercise-name-invalid"
REASON_EXERCISE_NAME_DUPLICATE = "conformance-exercise-name-duplicate"
REASON_SURFACES_EMPTY = "conformance-surfaces-empty"
REASON_SURFACE_UNKNOWN = "conformance-surface-unknown"
REASON_SURFACE_DUPLICATE = "conformance-surface-duplicate"
REASON_REASON_INVALID = "conformance-reason-invalid"
REASON_EVIDENCE_INVALID = "conformance-evidence-invalid"
REASON_EXERCISED_AT_INVALID = "conformance-exercised-at-invalid"
REASON_REQUIRED_SURFACES_INVALID = "conformance-required-surfaces-invalid"
REASON_WARNING_INVALID = "conformance-warning-invalid"
REASON_EXERCISE_FN_INVALID = "conformance-exercise-fn-invalid"
REASON_EXERCISE_RAISED = "conformance-exercise-raised"

_EXERCISE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}\Z")
_EVIDENCE_MAX_LEN = 500
_WARNING_VALUE_MAX_LEN = 200
_REASON_TOKEN_MAX_LEN = 64

_REQUIRED_RECORD_KEYS = frozenset({
    "schemaVersion",
    "exercise",
    "surfaces",
    "result",
    "reason",
    "evidence",
    "exercisedAt",
    "warnings",
})


class PilotConformanceError(Exception):
    """Conformance-contract refusal."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _has_control_char(value):
    return any(ord(ch) < 32 for ch in value)


def _validate_exercise_name(exercise):
    if not isinstance(exercise, str) or not _EXERCISE_NAME_RE.match(exercise):
        raise PilotConformanceError(REASON_EXERCISE_NAME_INVALID)


def _validate_surfaces(surfaces):
    if not isinstance(surfaces, list) or not surfaces:
        raise PilotConformanceError(REASON_SURFACES_EMPTY)
    seen = set()
    for surface in surfaces:
        # bite-axis: closed surface inventory — only REQUIRED_SURFACES members accepted.
        if not isinstance(surface, str) or surface not in REQUIRED_SURFACES:
            raise PilotConformanceError(REASON_SURFACE_UNKNOWN)
        if surface in seen:
            raise PilotConformanceError(REASON_SURFACE_DUPLICATE)
        seen.add(surface)


def _validate_result(result):
    # bite-axis: result membership — only string tokens in EXERCISE_RESULTS; truthy non-strings refuse.
    if not isinstance(result, str) or result not in EXERCISE_RESULTS:
        raise PilotConformanceError(REASON_RESULT_INVALID)


def _validate_reason(result, reason):
    if result == RESULT_PASS:
        if reason is not None:
            raise PilotConformanceError(REASON_REASON_INVALID)
        return
    if (
        not isinstance(reason, str)
        or not reason
        or reason.isspace()
        or any(ch.isspace() for ch in reason)
        or len(reason) > _REASON_TOKEN_MAX_LEN
    ):
        raise PilotConformanceError(REASON_REASON_INVALID)


def _validate_evidence(evidence):
    if (
        not isinstance(evidence, str)
        or not evidence
        or len(evidence) > _EVIDENCE_MAX_LEN
        or _has_control_char(evidence)
    ):
        raise PilotConformanceError(REASON_EVIDENCE_INVALID)


def _validate_exercised_at(exercised_at):
    if not isinstance(exercised_at, str):
        raise PilotConformanceError(REASON_EXERCISED_AT_INVALID)
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            datetime.datetime.strptime(exercised_at, fmt)
            return
        except ValueError:
            continue
    raise PilotConformanceError(REASON_EXERCISED_AT_INVALID)


def _validate_warnings(warnings):
    if warnings is None:
        return []
    if not isinstance(warnings, list):
        raise PilotConformanceError(REASON_WARNING_INVALID)
    normalized = []
    for warning in warnings:
        if not isinstance(warning, dict):
            raise PilotConformanceError(REASON_WARNING_INVALID)
        if "exercise" in warning:
            raise PilotConformanceError(REASON_WARNING_INVALID)
        copy = {}
        for key, value in warning.items():
            if (
                not isinstance(key, str)
                or not key
                or len(key) > _WARNING_VALUE_MAX_LEN
                or _has_control_char(key)
                or not isinstance(value, str)
                or not value
                or len(value) > _WARNING_VALUE_MAX_LEN
                or _has_control_char(value)
            ):
                raise PilotConformanceError(REASON_WARNING_INVALID)
            copy[key] = value
        normalized.append(copy)
    return normalized


def exercise_record(*, exercise, surfaces, result, reason, evidence, exercised_at, warnings=None):
    """Build and validate a canonical conformance exercise record."""
    _validate_exercise_name(exercise)
    _validate_surfaces(surfaces)
    _validate_result(result)
    _validate_reason(result, reason)
    _validate_evidence(evidence)
    _validate_exercised_at(exercised_at)
    warnings_normalized = _validate_warnings(warnings)
    return {
        "schemaVersion": SCHEMA,
        "exercise": exercise,
        "surfaces": sorted(surfaces),
        "result": result,
        "reason": reason,
        "evidence": evidence,
        "exercisedAt": exercised_at,
        "warnings": warnings_normalized,
    }


def validate_record(record):
    """Re-validate a record dict built elsewhere."""
    if not isinstance(record, dict):
        raise PilotConformanceError(REASON_RECORD_INVALID)
    keys = set(record.keys())
    if keys != _REQUIRED_RECORD_KEYS:
        raise PilotConformanceError(REASON_RECORD_INVALID)
    if record.get("schemaVersion") != SCHEMA:
        raise PilotConformanceError(REASON_RECORD_INVALID)
    exercise_record(
        exercise=record["exercise"],
        surfaces=record["surfaces"],
        result=record["result"],
        reason=record["reason"],
        evidence=record["evidence"],
        exercised_at=record["exercisedAt"],
        warnings=record["warnings"],
    )
    return record


def _validate_required_surfaces(required_surfaces):
    if not isinstance(required_surfaces, (tuple, list)) or not required_surfaces:
        raise PilotConformanceError(REASON_REQUIRED_SURFACES_INVALID)
    seen = set()
    for surface in required_surfaces:
        if not isinstance(surface, str) or not surface:
            raise PilotConformanceError(REASON_REQUIRED_SURFACES_INVALID)
        if surface in seen:
            raise PilotConformanceError(REASON_REQUIRED_SURFACES_INVALID)
        seen.add(surface)


def report(records, *, required_surfaces=REQUIRED_SURFACES):
    """Aggregate validated exercise records into a conformance report."""
    _validate_required_surfaces(required_surfaces)
    if not isinstance(records, list):
        raise PilotConformanceError(REASON_RECORD_INVALID)

    validated = []
    seen_exercises = set()
    for record in records:
        validated_record = validate_record(record)
        exercise_name = validated_record["exercise"]
        # bite-axis: exercise-name uniqueness — duplicate exercise names refuse at report time.
        if exercise_name in seen_exercises:
            raise PilotConformanceError(REASON_EXERCISE_NAME_DUPLICATE)
        seen_exercises.add(exercise_name)
        validated.append(validated_record)

    # bite-axis: coverage honesty — only pass records contribute to covered; unexercised is set difference.
    covered = set()
    for record in validated:
        if record["result"] == RESULT_PASS:
            covered.update(record["surfaces"])

    unexercised = sorted(set(required_surfaces) - covered)

    warnings = []
    for record in validated:
        for warning in record["warnings"]:
            warning_copy = dict(warning)
            warning_copy["exercise"] = record["exercise"]
            warnings.append(warning_copy)

    ok = (
        bool(validated)
        and not unexercised
        and all(record["result"] == RESULT_PASS for record in validated)
    )

    return {
        "schemaVersion": SCHEMA,
        "ok": ok,
        "exercises": validated,
        "surfaces": sorted(covered),
        "unexercised": unexercised,
        "warnings": warnings,
    }


def register(name, *, surfaces):
    """Decorator marking a callable as a conformance exercise function."""
    _validate_exercise_name(name)
    if not isinstance(surfaces, (list, tuple)):
        raise PilotConformanceError(REASON_SURFACES_EMPTY)
    _validate_surfaces(list(surfaces))

    def decorator(fn):
        fn.conformance_exercise = name
        fn.conformance_surfaces = tuple(sorted(surfaces))
        return fn

    return decorator


def _validate_exercise_fn(fn):
    if not callable(fn):
        raise PilotConformanceError(REASON_EXERCISE_FN_INVALID)
    exercise_name = getattr(fn, "conformance_exercise", None)
    exercise_surfaces = getattr(fn, "conformance_surfaces", None)
    if not isinstance(exercise_name, str) or not _EXERCISE_NAME_RE.match(exercise_name):
        raise PilotConformanceError(REASON_EXERCISE_FN_INVALID)
    if not isinstance(exercise_surfaces, tuple):
        raise PilotConformanceError(REASON_EXERCISE_FN_INVALID)
    try:
        _validate_surfaces(list(exercise_surfaces))
    except PilotConformanceError:
        raise PilotConformanceError(REASON_EXERCISE_FN_INVALID)


def _normalize_exception_reason(exc):
    reason = getattr(exc, "reason", None)
    if (
        isinstance(reason, str)
        and reason
        and not any(ch.isspace() for ch in reason)
        and len(reason) <= _REASON_TOKEN_MAX_LEN
    ):
        return reason
    return REASON_EXERCISE_RAISED


def run(exercise_fns, *, inputs, now):
    """Run registered exercise functions and return an aggregated conformance report."""
    if not isinstance(exercise_fns, list):
        raise PilotConformanceError(REASON_EXERCISE_FN_INVALID)
    for fn in exercise_fns:
        _validate_exercise_fn(fn)

    records = []
    for fn in exercise_fns:
        exercise_name = fn.conformance_exercise
        exercise_surfaces = list(fn.conformance_surfaces)
        try:
            returned = fn(inputs=inputs, now=now)
            try:
                records.append(validate_record(returned))
            except PilotConformanceError:
                records.append(exercise_record(
                    exercise=exercise_name,
                    surfaces=exercise_surfaces,
                    result=RESULT_FAIL,
                    reason=REASON_RECORD_INVALID,
                    evidence="exercise returned an invalid record",
                    exercised_at=now,
                ))
        except Exception as exc:
            # bite-axis: exercise exception normalization — never propagate; evidence is class name only.
            records.append(exercise_record(
                exercise=exercise_name,
                surfaces=exercise_surfaces,
                result=RESULT_FAIL,
                reason=_normalize_exception_reason(exc),
                evidence="exercise raised %s" % type(exc).__name__,
                exercised_at=now,
            ))

    return report(records)
