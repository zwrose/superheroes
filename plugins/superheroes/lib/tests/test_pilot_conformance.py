"""Tests for pilot_conformance.py — headless conformance-run contract (C10)."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_conformance as pc  # noqa: E402

EXERCISED_AT = "2026-08-07T12:00:00Z"
SAMPLE_SURFACE = "pilot_wave.wave_phase"


def _pass_record(**overrides):
    base = {
        "exercise": "wave-phase",
        "surfaces": [SAMPLE_SURFACE],
        "result": pc.RESULT_PASS,
        "reason": None,
        "evidence": "ok",
        "exercised_at": EXERCISED_AT,
    }
    base.update(overrides)
    return pc.exercise_record(**base)


# --- REQUIRED_SURFACES inventory ----------------------------------------------

def test_required_surfaces_sorted_unique_and_count():
    """Inventory is normative: sorted, no duplicates, exactly 17 members."""
    assert len(pc.REQUIRED_SURFACES) == 17
    assert len(pc.REQUIRED_SURFACES) == len(set(pc.REQUIRED_SURFACES))
    assert list(pc.REQUIRED_SURFACES) == sorted(pc.REQUIRED_SURFACES)


# --- exercise_record happy path -----------------------------------------------

def test_exercise_record_happy_path():
    record = _pass_record(warnings=[{"code": "note"}])
    assert record["schemaVersion"] == pc.SCHEMA
    assert record["exercise"] == "wave-phase"
    assert record["surfaces"] == [SAMPLE_SURFACE]
    assert record["result"] == pc.RESULT_PASS
    assert record["reason"] is None
    assert record["evidence"] == "ok"
    assert record["exercisedAt"] == EXERCISED_AT
    assert record["warnings"] == [{"code": "note"}]


def test_exercise_record_warnings_none_normalizes_to_empty():
    record = _pass_record(warnings=None)
    assert record["warnings"] == []


def test_exercise_record_warnings_are_copies():
    original = [{"code": "note"}]
    record = _pass_record(warnings=original)
    assert record["warnings"] == original
    assert record["warnings"] is not original
    record["warnings"][0]["code"] = "mutated"
    assert original[0]["code"] == "note"


# --- fail-closed edges --------------------------------------------------------

@pytest.mark.parametrize("result", [True, 1])
def test_edge_result_truthy_non_string_refuses(result):
    """Edge 1: result given as non-string truthy value must refuse, not coerce."""
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.exercise_record(
            exercise="wave-phase",
            surfaces=[SAMPLE_SURFACE],
            result=result,
            reason="some-reason",
            evidence="x",
            exercised_at=EXERCISED_AT,
        )
    assert exc.value.reason == pc.REASON_RESULT_INVALID


def test_edge_reason_non_none_on_pass_refuses():
    """Edge 2: reason non-None on a pass record must refuse."""
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.exercise_record(
            exercise="wave-phase",
            surfaces=[SAMPLE_SURFACE],
            result=pc.RESULT_PASS,
            reason="not-allowed",
            evidence="ok",
            exercised_at=EXERCISED_AT,
        )
    assert exc.value.reason == pc.REASON_REASON_INVALID


def test_edge_reason_none_on_non_pass_refuses():
    """Edge 3: reason None on a non-pass record must refuse."""
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.exercise_record(
            exercise="wave-phase",
            surfaces=[SAMPLE_SURFACE],
            result=pc.RESULT_FAIL,
            reason=None,
            evidence="x",
            exercised_at=EXERCISED_AT,
        )
    assert exc.value.reason == pc.REASON_REASON_INVALID


@pytest.mark.parametrize("surfaces", [[], None])
def test_edge_surfaces_empty_or_none_refuses(surfaces):
    """Edge 4: surfaces=[] and surfaces=None both refuse with REASON_SURFACES_EMPTY."""
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.exercise_record(
            exercise="wave-phase",
            surfaces=surfaces,
            result=pc.RESULT_PASS,
            reason=None,
            evidence="ok",
            exercised_at=EXERCISED_AT,
        )
    assert exc.value.reason == pc.REASON_SURFACES_EMPTY


def test_edge_surface_not_in_required_surfaces_refuses():
    """Edge 5: surface string not in REQUIRED_SURFACES refuses."""
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.exercise_record(
            exercise="wave-phase",
            surfaces=["pilot_unknown.surface"],
            result=pc.RESULT_PASS,
            reason=None,
            evidence="ok",
            exercised_at=EXERCISED_AT,
        )
    assert exc.value.reason == pc.REASON_SURFACE_UNKNOWN


def test_edge_evidence_with_newline_refuses():
    """Edge 6: evidence containing newline refuses (control characters)."""
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.exercise_record(
            exercise="wave-phase",
            surfaces=[SAMPLE_SURFACE],
            result=pc.RESULT_PASS,
            reason=None,
            evidence="line1\nline2",
            exercised_at=EXERCISED_AT,
        )
    assert exc.value.reason == pc.REASON_EVIDENCE_INVALID


def test_edge_exercised_at_non_utc_z_refuses():
    """Edge 7: exercised_at in non-UTC or non-Z form refuses."""
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.exercise_record(
            exercise="wave-phase",
            surfaces=[SAMPLE_SURFACE],
            result=pc.RESULT_PASS,
            reason=None,
            evidence="ok",
            exercised_at="2026-08-07T12:00:00+00:00",
        )
    assert exc.value.reason == pc.REASON_EXERCISED_AT_INVALID


def test_edge_warnings_non_str_value_refuses():
    """Edge 8: warnings member carrying a non-str value refuses."""
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.exercise_record(
            exercise="wave-phase",
            surfaces=[SAMPLE_SURFACE],
            result=pc.RESULT_PASS,
            reason=None,
            evidence="ok",
            exercised_at=EXERCISED_AT,
            warnings=[{"code": 123}],
        )
    assert exc.value.reason == pc.REASON_WARNING_INVALID


def test_edge_warnings_reserved_exercise_key_refuses():
    """Edge 8: warnings member carrying reserved exercise key refuses."""
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.exercise_record(
            exercise="wave-phase",
            surfaces=[SAMPLE_SURFACE],
            result=pc.RESULT_PASS,
            reason=None,
            evidence="ok",
            exercised_at=EXERCISED_AT,
            warnings=[{"exercise": "reserved"}],
        )
    assert exc.value.reason == pc.REASON_WARNING_INVALID


# --- validate_record ------------------------------------------------------------

def test_validate_record_happy_path():
    record = _pass_record()
    assert pc.validate_record(record) is record


def test_validate_record_refuses_non_dict():
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.validate_record([])
    assert exc.value.reason == pc.REASON_RECORD_INVALID


def test_validate_record_refuses_missing_key():
    record = _pass_record()
    del record["evidence"]
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.validate_record(record)
    assert exc.value.reason == pc.REASON_RECORD_INVALID


def test_validate_record_refuses_unknown_key():
    record = _pass_record()
    record["extra"] = "x"
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.validate_record(record)
    assert exc.value.reason == pc.REASON_RECORD_INVALID


def test_validate_record_refuses_wrong_schema_version():
    record = _pass_record()
    record["schemaVersion"] = 99
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.validate_record(record)
    assert exc.value.reason == pc.REASON_RECORD_INVALID


# --- report ---------------------------------------------------------------------

def _all_surfaces_pass_records():
    """One pass record per required surface (grouped for brevity in tests)."""
    records = []
    for index, surface in enumerate(pc.REQUIRED_SURFACES):
        records.append(_pass_record(
            exercise="ex-%02d" % index,
            surfaces=[surface],
        ))
    return records


def test_report_happy_path_all_surfaces_covered():
    records = _all_surfaces_pass_records()
    result = pc.report(records)
    assert result["ok"] is True
    assert result["unexercised"] == []
    assert result["surfaces"] == sorted(pc.REQUIRED_SURFACES)
    assert len(result["exercises"]) == 17


def test_edge_report_empty_ok_false_unexercised_all():
    """Edge 9: report([]) — ok is False and unexercised lists all 17 surfaces."""
    result = pc.report([])
    assert result["ok"] is False
    assert result["unexercised"] == sorted(pc.REQUIRED_SURFACES)
    assert result["exercises"] == []


def test_edge_report_skipped_surface_in_unexercised_ok_false():
    """Edge 10: skipped record's surfaces appear in unexercised; ok is False."""
    records = _all_surfaces_pass_records()
    records[-1] = pc.exercise_record(
        exercise="ex-skipped",
        surfaces=[pc.REQUIRED_SURFACES[-1]],
        result=pc.RESULT_SKIPPED,
        reason="skipped-reason",
        evidence="skipped",
        exercised_at=EXERCISED_AT,
    )
    result = pc.report(records)
    assert result["ok"] is False
    assert pc.REQUIRED_SURFACES[-1] in result["unexercised"]


def test_report_duplicate_exercise_name_refuses():
    records = [
        _pass_record(exercise="dup-name"),
        _pass_record(exercise="dup-name", surfaces=["pilot_wave.wave_anchor"]),
    ]
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.report(records)
    assert exc.value.reason == pc.REASON_EXERCISE_NAME_DUPLICATE


def test_report_warnings_include_exercise_key():
    records = [
        _pass_record(warnings=[{"code": "note"}]),
    ]
    result = pc.report(records)
    assert result["warnings"] == [{"code": "note", "exercise": "wave-phase"}]


def test_report_fail_record_does_not_contribute_to_covered():
    records = [
        _pass_record(surfaces=list(pc.REQUIRED_SURFACES[:-1])),
        pc.exercise_record(
            exercise="fail-one",
            surfaces=[pc.REQUIRED_SURFACES[-1]],
            result=pc.RESULT_FAIL,
            reason="fail-token",
            evidence="failed",
            exercised_at=EXERCISED_AT,
        ),
    ]
    result = pc.report(records)
    assert result["ok"] is False
    assert pc.REQUIRED_SURFACES[-1] in result["unexercised"]


def test_edge_required_surfaces_duplicate_refuses():
    """Edge 14: required_surfaces containing a duplicate refuses."""
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.report([], required_surfaces=("a", "a"))
    assert exc.value.reason == pc.REASON_REQUIRED_SURFACES_INVALID


def test_report_required_surfaces_empty_refuses():
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.report([], required_surfaces=[])
    assert exc.value.reason == pc.REASON_REQUIRED_SURFACES_INVALID


# --- register -------------------------------------------------------------------

def test_register_happy_path():
    @pc.register("my-exercise", surfaces=[SAMPLE_SURFACE])
    def my_fn(inputs, now):
        return _pass_record()

    assert my_fn.conformance_exercise == "my-exercise"
    assert my_fn.conformance_surfaces == (SAMPLE_SURFACE,)
    assert my_fn is my_fn


def test_register_bad_name_at_import():
    with pytest.raises(pc.PilotConformanceError) as exc:
        @pc.register("BAD NAME", surfaces=[SAMPLE_SURFACE])
        def bad_fn(inputs, now):
            pass
    assert exc.value.reason == pc.REASON_EXERCISE_NAME_INVALID


def test_register_bad_surface_at_import():
    with pytest.raises(pc.PilotConformanceError) as exc:
        @pc.register("bad-surface", surfaces=["unknown.surface"])
        def bad_fn(inputs, now):
            pass
    assert exc.value.reason == pc.REASON_SURFACE_UNKNOWN


# --- run ------------------------------------------------------------------------

def test_run_happy_path():
    @pc.register("run-ok", surfaces=[SAMPLE_SURFACE])
    def ok_fn(inputs, now):
        return _pass_record(exercise="run-ok", exercised_at=now)

    result = pc.run([ok_fn], inputs={}, now=EXERCISED_AT)
    assert result["ok"] is False
    assert SAMPLE_SURFACE in result["surfaces"]
    assert len(result["unexercised"]) == 16


def test_edge_run_unregistered_callable_refuses_before_any_runs():
    """Edge 11: unregistered callable refuses before any exercise runs."""
    def plain_fn(inputs, now):
        return _pass_record()

    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.run([plain_fn], inputs={}, now=EXERCISED_AT)
    assert exc.value.reason == pc.REASON_EXERCISE_FN_INVALID


def test_edge_run_exception_without_reason_normalizes():
    """Edge 12: exception with no .reason normalizes to REASON_EXERCISE_RAISED."""
    @pc.register("raises-plain", surfaces=[SAMPLE_SURFACE])
    def raises_fn(inputs, now):
        raise RuntimeError("secret path /tmp/foo")

    result = pc.run([raises_fn], inputs={}, now=EXERCISED_AT)
    record = result["exercises"][0]
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pc.REASON_EXERCISE_RAISED
    assert record["evidence"] == "exercise raised RuntimeError"
    assert "/tmp/foo" not in record["evidence"]


def test_edge_run_exception_long_free_text_reason_uses_raised():
    """Edge 13: long free-text .reason uses REASON_EXERCISE_RAISED instead."""
    class CustomError(Exception):
        def __init__(self):
            self.reason = "this is a long free-text reason that should not pass the token guard"

    @pc.register("raises-custom", surfaces=[SAMPLE_SURFACE])
    def raises_fn(inputs, now):
        raise CustomError()

    result = pc.run([raises_fn], inputs={}, now=EXERCISED_AT)
    record = result["exercises"][0]
    assert record["reason"] == pc.REASON_EXERCISE_RAISED


def test_run_exception_with_valid_reason_token():
    class TokenError(Exception):
        def __init__(self):
            self.reason = "valid-token"

    @pc.register("raises-token", surfaces=[SAMPLE_SURFACE])
    def raises_fn(inputs, now):
        raise TokenError()

    result = pc.run([raises_fn], inputs={}, now=EXERCISED_AT)
    record = result["exercises"][0]
    assert record["reason"] == "valid-token"


def test_run_invalid_return_normalized_to_fail():
    @pc.register("bad-return", surfaces=[SAMPLE_SURFACE])
    def bad_fn(inputs, now):
        return {"not": "a record"}

    result = pc.run([bad_fn], inputs={}, now=EXERCISED_AT)
    record = result["exercises"][0]
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pc.REASON_RECORD_INVALID
    assert record["evidence"] == "exercise returned an invalid record"


def test_run_pilot_conformance_error_caught_and_normalized():
    @pc.register("raises-pc", surfaces=[SAMPLE_SURFACE])
    def raises_fn(inputs, now):
        raise pc.PilotConformanceError("surface-bad", detail="hidden")

    result = pc.run([raises_fn], inputs={}, now=EXERCISED_AT)
    record = result["exercises"][0]
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == "surface-bad"


def test_exercise_record_surface_duplicate_refuses():
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.exercise_record(
            exercise="wave-phase",
            surfaces=[SAMPLE_SURFACE, SAMPLE_SURFACE],
            result=pc.RESULT_PASS,
            reason=None,
            evidence="ok",
            exercised_at=EXERCISED_AT,
        )
    assert exc.value.reason == pc.REASON_SURFACE_DUPLICATE


def test_exercise_record_invalid_result_string_refuses():
    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.exercise_record(
            exercise="wave-phase",
            surfaces=[SAMPLE_SURFACE],
            result="unknown",
            reason="x",
            evidence="x",
            exercised_at=EXERCISED_AT,
        )
    assert exc.value.reason == pc.REASON_RESULT_INVALID


def test_exercise_record_fractional_exercised_at_accepted():
    record = _pass_record(exercised_at="2026-08-07T12:00:00.123456Z")
    assert record["exercisedAt"] == "2026-08-07T12:00:00.123456Z"
