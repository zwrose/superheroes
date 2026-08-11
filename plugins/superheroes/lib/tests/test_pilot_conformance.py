"""Tests for pilot_conformance.py — headless conformance-run contract (C10)."""
import json
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
    """Inventory is normative: sorted, no duplicates, exactly 24 members."""
    assert len(pc.REQUIRED_SURFACES) == 24
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
    assert len(result["exercises"]) == 24


def test_edge_report_empty_ok_false_unexercised_all():
    """Edge 9: report([]) — ok is False and unexercised lists all 24 surfaces."""
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


def test_report_single_pass_record_ok_false():
    """bite-axis: closed inventory — one passing record cannot widen ok to True."""
    result = pc.report([_pass_record()])
    assert result["ok"] is False
    assert len(result["unexercised"]) == len(pc.REQUIRED_SURFACES) - 1


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


def test_register_happy_path():
    @pc.register("my-exercise", surfaces=[SAMPLE_SURFACE])
    def my_fn(inputs, now):
        return _pass_record()

    assert my_fn.conformance_exercise == "my-exercise"
    assert my_fn.conformance_surfaces == (SAMPLE_SURFACE,)
    assert callable(my_fn)


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
    assert len(result["unexercised"]) == 23


def test_edge_run_unregistered_callable_refuses_before_any_runs():
    """Edge 11: unregistered callable refuses before any exercise runs."""
    def plain_fn(inputs, now):
        return _pass_record()

    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.run([plain_fn], inputs={}, now=EXERCISED_AT)
    assert exc.value.reason == pc.REASON_EXERCISE_FN_INVALID


def test_run_duplicate_exercise_names_refused_before_execution():
    """bite-axis: pre-flight duplicate detection — neither exercise runs."""
    ran = []

    @pc.register("dup-preflight", surfaces=[SAMPLE_SURFACE])
    def first(inputs, now):
        ran.append("first")
        return _pass_record(exercise="dup-preflight", exercised_at=now)

    @pc.register("dup-preflight", surfaces=["pilot_wave.wave_anchor"])
    def second(inputs, now):
        ran.append("second")
        return _pass_record(
            exercise="dup-preflight",
            surfaces=["pilot_wave.wave_anchor"],
            exercised_at=now,
        )

    with pytest.raises(pc.PilotConformanceError) as exc:
        pc.run([first, second], inputs={}, now=EXERCISED_AT)
    assert exc.value.reason == pc.REASON_EXERCISE_NAME_DUPLICATE
    assert ran == []


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


def test_run_mismatched_exercise_name_normalized_to_fail():
    @pc.register("registered-name", surfaces=[SAMPLE_SURFACE])
    def lying_fn(inputs, now):
        return _pass_record(exercise="other-name", exercised_at=now)

    result = pc.run([lying_fn], inputs={}, now=EXERCISED_AT)
    record = result["exercises"][0]
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pc.REASON_RECORD_UNREGISTERED


def test_run_unregistered_surface_normalized_to_fail():
    @pc.register("surface-liar", surfaces=[SAMPLE_SURFACE])
    def lying_fn(inputs, now):
        return _pass_record(
            exercise="surface-liar",
            surfaces=[SAMPLE_SURFACE, "pilot_wave.wave_anchor"],
            exercised_at=now,
        )

    result = pc.run([lying_fn], inputs={}, now=EXERCISED_AT)
    record = result["exercises"][0]
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pc.REASON_RECORD_UNREGISTERED


def test_resolve_inputs_no_artifacts_dir_token(tmp_path, monkeypatch):
    import json

    from test_pilot_conformance_cleanup import (
        _cleanup_correct_script,
        _harness_layout,
        _three_slot_policy,
        _write_cleanup_script,
        _write_scripts,
    )

    monkeypatch.setattr("store_core.run_git", lambda *_args, **_kwargs: "main")
    _write_calibration_layer(tmp_path)
    policy_root = tmp_path / "policy"
    policy_root.mkdir()
    reach_root, _run_cwd, bin_dir, store_dir, cleanup_repo, _journal = _harness_layout(
        str(tmp_path)
    )
    plant, probe = _write_scripts(bin_dir)
    _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    policy = _three_slot_policy(store_dir, plant, probe)
    with open(
        policy_root / "example-project-pilot-policy.json",
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(policy, handle)

    def resolve_without_artifacts(cwd, root):
        return {
            "exists": True,
            "profile": str(tmp_path / ".claude" / "superheroes" / "test-pilot.md"),
        }

    monkeypatch.setattr("store.resolve", resolve_without_artifacts)

    inputs, resolution = pc.resolve_inputs(
        str(tmp_path),
        policy_root=str(policy_root),
        reach_roots=[reach_root],
        slot_ref="slot-a@1",
        branch="main",
        slot="slot-a",
        now=EXERCISED_AT,
    )
    assert "artifacts" not in inputs
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["artifacts"]["reason"] == pc.REASON_INPUT_NO_ARTIFACTS_DIR


def test_resolve_inputs_mint_environment_includes_path(tmp_path):
    _write_calibration_layer(tmp_path, include_mint=True)
    inputs, _resolution = pc.resolve_inputs(
        str(tmp_path), now=EXERCISED_AT, allow_live_effects=True,
    )
    assert "PATH" in inputs["mint"]["environment"]
    assert inputs["mint"]["environment"]["PATH"]


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


# --- default_exercises --------------------------------------------------------

def test_default_exercises_surface_union_equals_required_surfaces():
    """Closed-inventory guarantee: every required surface has exactly one exercise."""
    # bite-axis: inventory completeness — union of exercise surfaces must equal REQUIRED_SURFACES.
    exercised = set()
    for fn in pc.default_exercises():
        exercised.update(fn.conformance_surfaces)
    assert exercised == set(pc.REQUIRED_SURFACES)


def test_default_exercises_stable_order():
    names = [fn.conformance_exercise for fn in pc.default_exercises()]
    assert names == [
        "artifact-store",
        "boundary-refusals",
        "cleanup-end-to-end",
        "horizon-validity",
        "mint-gate-off",
        "ownership-probe",
        "reclaim-sweep",
        "wave-headless",
    ]


# --- resolve_inputs -----------------------------------------------------------

_MINIMAL_PILOT_JSON = (
    '"schemaVersion": 1, "signInPath": "attended",'
    '"attended": {"vehicle": "automation"},'
    '"credentialSet": [{"account": "owner", "role": "resource-owner"}],'
    '"captureSurface": ["cookies"],'
    '"captureOptions": {"indexedDB": false, "credentials": false},'
    '"validityProvenance": "server-probe",'
    '"identityProbe": {"path": "/api/me", "unseededExpectation": "no-session"},'
    '"cleanup": {"command": ["cleanup", "{namespace}"]},'
    '"administrativeMax": 4,'
    '"effectsEscape": {"canEscape": false, "evidence": "x"},'
    '"policyRef": {"declaration": "example-project-pilot-policy"}'
)


def _write_calibration_layer(tmp_path, *, include_mint=False):
    layer_dir = tmp_path / ".claude" / "superheroes"
    layer_dir.mkdir(parents=True)
    pilot_json = "{" + _MINIMAL_PILOT_JSON
    if include_mint:
        pilot_json += (
            ', "mint": {"envelope": {"enablingFlagEnvVar": "ALLOW",'
            ' "enabledScopes": ["dev"], "forbiddenScopes": ["prod"],'
            ' "gateOffTestCommand": ["true"]}, "sentinelIdentifier": "x"}'
        )
    pilot_json += "}"
    (layer_dir / "test-pilot.md").write_text(
        "## config\n\n```json test-pilot-config\n"
        '{"schemaVersion": 1, "pilot": %s}\n```\n' % pilot_json,
        encoding="utf-8",
    )


def test_resolve_inputs_no_calibration_all_absent(tmp_path):
    inputs, resolution = pc.resolve_inputs(str(tmp_path), now=EXERCISED_AT)
    assert inputs == {}
    assert len(resolution) == 9
    assert all(entry["state"] == "absent" for entry in resolution)
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["cleanup"]["reason"] == pc.REASON_INPUT_LIVE_EFFECTS_NOT_PERMITTED
    assert by_input["mint"]["reason"] == pc.REASON_INPUT_LIVE_EFFECTS_NOT_PERMITTED
    assert by_input["wave"]["reason"] == pc.REASON_INPUT_NO_SLOTS_DIR
    assert by_input["reclaim"]["reason"] == pc.REASON_INPUT_NO_SLOTS_DIR


def test_resolve_inputs_branch_unresolved_artifacts_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("store_core.run_git", lambda *_args, **_kwargs: None)
    _write_calibration_layer(tmp_path)
    inputs, resolution = pc.resolve_inputs(
        str(tmp_path),
        policy_root=str(tmp_path / "policy"),
        slot_ref="slot-a@1",
        now=EXERCISED_AT,
    )
    assert "artifacts" not in inputs
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["artifacts"]["state"] == "absent"
    assert by_input["artifacts"]["reason"] == pc.REASON_INPUT_BRANCH_UNRESOLVED


def test_resolve_inputs_pilot_block_no_policy_root_cleanup_absent(tmp_path):
    _write_calibration_layer(tmp_path)
    inputs, resolution = pc.resolve_inputs(str(tmp_path), now=EXERCISED_AT)
    assert "cleanup" not in inputs
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["cleanup"]["reason"] == pc.REASON_INPUT_LIVE_EFFECTS_NOT_PERMITTED


def test_resolve_inputs_wave_and_reclaim_resolved_with_slots_dir(tmp_path):
    slots_dir = tmp_path / "slots"
    slots_dir.mkdir()
    inputs, resolution = pc.resolve_inputs(
        str(tmp_path),
        slots_dir=str(slots_dir),
        slot_ref="slot-a@1",
        now=EXERCISED_AT,
    )
    assert inputs["wave"]["slots_dir"] == str(slots_dir)
    assert inputs["reclaim"]["slots_dir"] == str(slots_dir)
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["wave"]["state"] == "resolved"
    assert by_input["reclaim"]["state"] == "resolved"


def test_edge10_unreachable_reach_root_cleanup_absent(tmp_path):
    _write_calibration_layer(tmp_path, include_mint=True)
    policy_root = tmp_path / "policy"
    policy_root.mkdir()
    slots_dir = tmp_path / "slots"
    slots_dir.mkdir()
    inputs, resolution = pc.resolve_inputs(
        str(tmp_path),
        policy_root=str(policy_root),
        reach_roots=[str(tmp_path)],
        slots_dir=str(slots_dir),
        slot_ref="slot-a@1",
        now=EXERCISED_AT,
        allow_live_effects=True,
    )
    assert "cleanup" not in inputs
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["cleanup"]["state"] == "absent"
    assert by_input["cleanup"]["reason"] == "policy-root-in-reach"


_LIVE_EFFECT_SURFACES = frozenset({
    "pilot_cleanup.cleanup_effect_receipt",
    "pilot_cleanup.receipt_valid_for",
    "pilot_cleanup.registry_record",
    "pilot_cleanup.resolve_containment",
    "pilot_cleanup.resurrection_plan",
    "pilot_mint.gate_off_receipt",
    "pilot_mint.run_gate_off_test",
    "pilot_policy.ownership_probe_request",
})


def test_resolve_inputs_default_live_effects_cleanup_mint_absent(tmp_path):
    """bite-axis: live-effect containment — default resolve leaves effect inputs absent."""
    _write_calibration_layer(tmp_path, include_mint=True)
    policy_root = tmp_path / "policy"
    policy_root.mkdir()
    slots_dir = tmp_path / "slots"
    slots_dir.mkdir()
    inputs, resolution = pc.resolve_inputs(
        str(tmp_path),
        policy_root=str(policy_root),
        slots_dir=str(slots_dir),
        slot_ref="slot-a@1",
        now=EXERCISED_AT,
    )
    assert "cleanup" not in inputs
    assert "mint" not in inputs
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["cleanup"]["reason"] == pc.REASON_INPUT_LIVE_EFFECTS_NOT_PERMITTED
    assert by_input["mint"]["reason"] == pc.REASON_INPUT_LIVE_EFFECTS_NOT_PERMITTED


def test_default_run_report_live_effect_surfaces_unexercised(tmp_path):
    """bite-axis: live-effect containment — default run reports all eight surfaces unexercised."""
    report = pc.run(pc.default_exercises(), inputs={}, now=EXERCISED_AT)
    assert report["ok"] is False
    assert _LIVE_EFFECT_SURFACES <= set(report["unexercised"])


def test_resolve_inputs_cleanup_run_cwd_outside_reach(tmp_path, monkeypatch):
    import json

    from test_pilot_conformance_cleanup import (
        _cleanup_correct_script,
        _harness_layout,
        _three_slot_policy,
        _write_cleanup_script,
        _write_scripts,
    )

    import pilot_boundary

    monkeypatch.setattr("store_core.run_git", lambda *_args, **_kwargs: "main")
    _write_calibration_layer(tmp_path, include_mint=True)
    policy_root = tmp_path / "policy"
    policy_root.mkdir()
    slots_dir = tmp_path / "slots"
    slots_dir.mkdir()
    reach_root, _run_cwd, bin_dir, store_dir, cleanup_repo, _journal = _harness_layout(
        str(tmp_path)
    )
    plant, probe = _write_scripts(bin_dir)
    _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    policy = _three_slot_policy(store_dir, plant, probe)
    with open(
        policy_root / "example-project-pilot-policy.json",
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(policy, handle)

    inputs, resolution = pc.resolve_inputs(
        str(tmp_path),
        policy_root=str(policy_root),
        reach_roots=[reach_root],
        slots_dir=str(slots_dir),
        slot_ref="slot-a@1",
        branch="main",
        slot="slot-a",
        now=EXERCISED_AT,
        allow_live_effects=True,
    )
    assert "cleanup" in inputs
    run_cwd = inputs["cleanup"]["run_cwd"]
    assert pilot_boundary.is_outside_all_reach_roots(run_cwd, [reach_root])
    assert inputs["cleanup"].get("run_cwd_disposable") is True
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["cleanup"]["state"] == "resolved"


def test_resolve_inputs_ownership_probe_includes_reach_roots(tmp_path, monkeypatch):
    import json

    from test_pilot_conformance_cleanup import (
        _cleanup_correct_script,
        _harness_layout,
        _three_slot_policy,
        _write_cleanup_script,
        _write_scripts,
    )

    import pilot_boundary

    monkeypatch.setattr("store_core.run_git", lambda *_args, **_kwargs: "main")
    _write_calibration_layer(tmp_path, include_mint=True)
    policy_root = tmp_path / "policy"
    policy_root.mkdir()
    slots_dir = tmp_path / "slots"
    slots_dir.mkdir()
    reach_root, _run_cwd, bin_dir, store_dir, cleanup_repo, _journal = _harness_layout(
        str(tmp_path)
    )
    plant, probe = _write_scripts(bin_dir)
    _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    policy = _three_slot_policy(store_dir, plant, probe)
    with open(
        policy_root / "example-project-pilot-policy.json",
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(policy, handle)

    inputs, resolution = pc.resolve_inputs(
        str(tmp_path),
        policy_root=str(policy_root),
        reach_roots=[reach_root],
        slots_dir=str(slots_dir),
        slot_ref="slot-a@1",
        branch="main",
        slot="slot-a",
        now=EXERCISED_AT,
        allow_live_effects=True,
    )
    assert "ownership_probe" in inputs
    assert inputs["ownership_probe"]["reach_roots"] == [reach_root]
    probe_run_cwd = inputs["ownership_probe"]["run_cwd"]
    assert pilot_boundary.is_outside_all_reach_roots(probe_run_cwd, [reach_root])
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["ownership-probe"]["state"] == "resolved"


# --- CLI ----------------------------------------------------------------------

def _repo_root():
    return os.path.realpath(os.path.join(_HERE, "..", "..", "..", ".."))


def test_cli_stdout_parses_as_json(capsys):
    exit_code = pc.main([
        "pilot_conformance.py",
        "run",
        "--cwd",
        _repo_root(),
        "--now",
        EXERCISED_AT,
    ])
    captured = capsys.readouterr()
    assert exit_code == 1
    payload = json.loads(captured.out)
    assert "resolution" in payload
    assert payload["ok"] is False
    assert captured.err == ""


def test_edge1_cli_cwd_not_directory_returns_2(capsys, tmp_path):
    missing = str(tmp_path / "missing-dir")
    exit_code = pc.main(["pilot_conformance.py", "run", "--cwd", missing])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.strip() == pc.REASON_CLI_CWD_INVALID


def test_edge2_cli_now_non_utc_z_returns_2(capsys):
    exit_code = pc.main([
        "pilot_conformance.py",
        "run",
        "--cwd",
        _repo_root(),
        "--now",
        "2026-08-07T12:00:00+00:00",
    ])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.strip() == pc.REASON_CLI_NOW_INVALID


def test_edge3_cli_no_calibration_every_exercise_skipped(capsys):
    exit_code = pc.main([
        "pilot_conformance.py",
        "run",
        "--cwd",
        _repo_root(),
        "--now",
        EXERCISED_AT,
    ])
    captured = capsys.readouterr()
    assert exit_code == 1
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["unexercised"] == sorted(pc.REQUIRED_SURFACES)
    assert all(
        record["result"] == pc.RESULT_SKIPPED
        for record in payload["exercises"]
    )


def test_edge6_cli_exercise_raises_still_prints_report(monkeypatch, capsys):
    def _raising(_inputs, _now):
        raise RuntimeError("boom")

    _raising.conformance_exercise = "raises"
    _raising.conformance_surfaces = (SAMPLE_SURFACE,)

    monkeypatch.setattr(pc, "default_exercises", lambda: [_raising])
    exit_code = pc.main([
        "pilot_conformance.py",
        "run",
        "--cwd",
        _repo_root(),
        "--now",
        EXERCISED_AT,
    ])
    captured = capsys.readouterr()
    assert exit_code == 1
    payload = json.loads(captured.out)
    assert payload["exercises"][0]["result"] == pc.RESULT_FAIL


def test_edge7_cli_unregistered_exercise_returns_2(monkeypatch, capsys):
    def _plain(_inputs, _now):
        return _pass_record()

    monkeypatch.setattr(pc, "default_exercises", lambda: [_plain])
    exit_code = pc.main([
        "pilot_conformance.py",
        "run",
        "--cwd",
        _repo_root(),
        "--now",
        EXERCISED_AT,
    ])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.strip() == pc.REASON_EXERCISE_FN_INVALID


def test_edge8_cli_duplicate_exercise_names_returns_2(monkeypatch, capsys):
    ran = []

    @pc.register("dup", surfaces=[SAMPLE_SURFACE])
    def first(inputs, now):
        ran.append("first")
        return _pass_record(exercise="dup", exercised_at=now)

    @pc.register("dup", surfaces=["pilot_wave.wave_anchor"])
    def second(inputs, now):
        ran.append("second")
        return _pass_record(exercise="dup", surfaces=["pilot_wave.wave_anchor"], exercised_at=now)

    monkeypatch.setattr(pc, "default_exercises", lambda: [first, second])
    exit_code = pc.main([
        "pilot_conformance.py",
        "run",
        "--cwd",
        _repo_root(),
        "--now",
        EXERCISED_AT,
    ])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.strip() == pc.REASON_EXERCISE_NAME_DUPLICATE
    assert ran == []


def test_cli_default_never_resolves_live_effect_inputs(capsys):
    exit_code = pc.main([
        "pilot_conformance.py",
        "run",
        "--cwd",
        _repo_root(),
        "--now",
        EXERCISED_AT,
    ])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    by_input = {entry["input"]: entry for entry in payload["resolution"]}
    assert by_input["cleanup"]["reason"] == pc.REASON_INPUT_LIVE_EFFECTS_NOT_PERMITTED
    assert by_input["mint"]["reason"] == pc.REASON_INPUT_LIVE_EFFECTS_NOT_PERMITTED
    assert exit_code == 1


def test_edge9_cli_stdout_is_only_json(capsys):
    exit_code = pc.main([
        "pilot_conformance.py",
        "run",
        "--cwd",
        _repo_root(),
        "--now",
        EXERCISED_AT,
    ])
    captured = capsys.readouterr()
    assert exit_code == 1
    json.loads(captured.out)
    assert captured.out.endswith("\n")
    assert captured.err == ""
