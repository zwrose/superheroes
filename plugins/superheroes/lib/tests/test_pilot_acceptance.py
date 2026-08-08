"""Tests for pilot_acceptance.py — acceptance matrix contract (C10)."""
import json
import os
import subprocess
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_acceptance as pa  # noqa: E402

_VALID_SHA1 = "a" * 40
_VALID_SHA256 = "b" * 64
_GENERATED_AT = "2026-08-08T12:00:00Z"


def _reference(**overrides):
    base = {"project": "example", "commit": _VALID_SHA1, "dirty": False}
    base.update(overrides)
    return base


def _report_data(**overrides):
    base = {
        "ok": True,
        "unexercised": [],
        "exercises": [],
    }
    base.update(overrides)
    return base


def _declarations_block(**overrides):
    base = {
        "ok": True,
        "rows": [
            {
                "kind": "session-surface",
                "slotRef": "slot-a@1",
                "status": "attested",
                "declarationDigest": "abc123",
                "reason": None,
            }
        ],
    }
    base.update(overrides)
    return base


def _exercise(name, surfaces, result="pass"):
    return {
        "exercise": name,
        "surfaces": list(surfaces),
        "result": result,
    }


# --- reference ----------------------------------------------------------------

@pytest.mark.parametrize("commit", [_VALID_SHA1, _VALID_SHA256])
def test_reference_accepts_valid_oid_lengths(commit):
    ref = pa.reference("my-project", commit, dirty=False)
    assert ref == {"project": "my-project", "commit": commit, "dirty": False}


@pytest.mark.parametrize(
    "commit",
    [
        "",
        "abc",
        "main",
        "HEAD",
        "A" * 40,
        "g" * 40,
        123,
    ],
)
def test_reference_refuses_invalid_commit(commit):
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.reference("proj", commit, dirty=False)
    assert exc.value.reason == pa.REASON_REFERENCE_COMMIT_INVALID


@pytest.mark.parametrize("project", ["", None, 1, "bad\x00name"])
def test_reference_refuses_invalid_project(project):
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.reference(project, _VALID_SHA1, dirty=False)
    assert exc.value.reason == pa.REASON_REFERENCE_PROJECT_INVALID


@pytest.mark.parametrize("dirty", [None, 1, "true", []])
def test_reference_refuses_non_boolean_dirty(dirty):
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.reference("proj", _VALID_SHA1, dirty=dirty)
    assert exc.value.reason == pa.REASON_REFERENCE_DIRTY_INVALID


# --- row valid combinations ---------------------------------------------------

def test_row_exercised_valid():
    evidence = {"exercise": "wave-headless", "surface": "pilot_wave.wave_phase"}
    row_data = pa.row(area="test", claim="claim", status=pa.STATUS_EXERCISED, evidence=evidence)
    assert row_data["status"] == pa.STATUS_EXERCISED
    assert row_data["evidence"] == evidence


def test_row_attested_valid():
    evidence = {"kind": "session-surface", "slotRef": "slot-a@1", "digest": "d1"}
    row_data = pa.row(area="test", claim="claim", status=pa.STATUS_ATTESTED, evidence=evidence)
    assert row_data["status"] == pa.STATUS_ATTESTED


def test_row_declared_limit_valid():
    row_data = pa.row(
        area="declared-limit",
        claim="limit claim",
        status=pa.STATUS_DECLARED_LIMIT,
        limit_id="lid",
        closure_path="path",
        ruling=pa.RULING_OWNER_RULED,
    )
    assert row_data["limit_id"] == "lid"


def test_row_unexercised_valid():
    row_data = pa.row(
        area="test",
        claim="claim",
        status=pa.STATUS_UNEXERCISED,
        evidence={"reason": "some-token"},
    )
    assert row_data["evidence"]["reason"] == "some-token"


def test_row_prose_residue_valid():
    row_data = pa.row(area="test", claim="claim", status=pa.STATUS_PROSE_RESIDUE)
    assert row_data["evidence"] is None


def test_row_not_applicable_valid():
    row_data = pa.row(area="test", claim="claim", status=pa.STATUS_NOT_APPLICABLE)
    assert row_data["status"] == pa.STATUS_NOT_APPLICABLE


# --- row invalid combinations -------------------------------------------------

def test_row_exercised_missing_evidence_refuses():
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.row(area="a", claim="c", status=pa.STATUS_EXERCISED)
    assert exc.value.reason == pa.REASON_ROW_EVIDENCE_REQUIRED


def test_row_exercised_with_limit_id_refuses():
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.row(
            area="a",
            claim="c",
            status=pa.STATUS_EXERCISED,
            evidence={"exercise": "x", "surface": "y"},
            limit_id="nope",
        )
    assert exc.value.reason == pa.REASON_ROW_LIMIT_ID_FORBIDDEN


def test_row_attested_bad_evidence_shape_refuses():
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.row(
            area="a",
            claim="c",
            status=pa.STATUS_ATTESTED,
            evidence={"exercise": "x", "surface": "y"},
        )
    assert exc.value.reason == pa.REASON_ROW_EVIDENCE_SHAPE_INVALID


def test_row_declared_limit_missing_limit_id_refuses():
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.row(
            area="a",
            claim="c",
            status=pa.STATUS_DECLARED_LIMIT,
            closure_path="p",
            ruling=pa.RULING_OWNER_RULED,
        )
    assert exc.value.reason == pa.REASON_ROW_LIMIT_ID_REQUIRED


def test_row_declared_limit_with_evidence_refuses():
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.row(
            area="a",
            claim="c",
            status=pa.STATUS_DECLARED_LIMIT,
            limit_id="lid",
            closure_path="p",
            ruling=pa.RULING_OWNER_RULED,
            evidence={"reason": "x"},
        )
    assert exc.value.reason == pa.REASON_ROW_EVIDENCE_FORBIDDEN


def test_row_declared_limit_invalid_ruling_refuses():
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.row(
            area="a",
            claim="c",
            status=pa.STATUS_DECLARED_LIMIT,
            limit_id="lid",
            closure_path="p",
            ruling="bogus",
        )
    assert exc.value.reason == pa.REASON_ROW_RULING_INVALID


def test_row_prose_residue_with_evidence_refuses():
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.row(
            area="a",
            claim="c",
            status=pa.STATUS_PROSE_RESIDUE,
            evidence={"reason": "x"},
        )
    assert exc.value.reason == pa.REASON_ROW_EVIDENCE_FORBIDDEN


def test_row_prose_residue_empty_claim_refuses():
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.row(area="a", claim="", status=pa.STATUS_PROSE_RESIDUE)
    assert exc.value.reason == pa.REASON_ROW_CLAIM_INVALID


def test_row_invalid_status_refuses():
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.row(area="a", claim="c", status="bogus")
    assert exc.value.reason == pa.REASON_ROW_STATUS_INVALID


# --- resolve ------------------------------------------------------------------

def test_resolve_exercised_right_surface_passes():
    row_data = pa.row(
        area="a",
        claim="c",
        status=pa.STATUS_EXERCISED,
        evidence={"exercise": "wave-headless", "surface": "pilot_reclaim.sweep"},
    )
    report = _report_data(
        exercises=[_exercise("wave-headless", ["pilot_reclaim.sweep", "pilot_wave.wave_phase"])]
    )
    resolved = pa.resolve([row_data], report, _declarations_block())
    assert resolved[0]["status"] == pa.STATUS_EXERCISED


def test_resolve_exercised_wrong_surface_becomes_unexercised():
    row_data = pa.row(
        area="a",
        claim="c",
        status=pa.STATUS_EXERCISED,
        evidence={"exercise": "reclaim-sweep", "surface": "pilot_boundary.is_local_development_origin"},
    )
    report = _report_data(
        exercises=[_exercise("reclaim-sweep", ["pilot_reclaim.sweep"])]
    )
    resolved = pa.resolve([row_data], report, _declarations_block())
    assert resolved[0]["status"] == pa.STATUS_UNEXERCISED
    assert resolved[0]["evidence"]["reason"] == pa.REASON_EVIDENCE_SURFACE_UNBOUND


def test_resolve_exercised_failed_record_becomes_unexercised():
    row_data = pa.row(
        area="a",
        claim="c",
        status=pa.STATUS_EXERCISED,
        evidence={"exercise": "wave-headless", "surface": "pilot_wave.wave_phase"},
    )
    report = _report_data(
        exercises=[_exercise("wave-headless", ["pilot_wave.wave_phase"], result="fail")]
    )
    resolved = pa.resolve([row_data], report, _declarations_block())
    assert resolved[0]["status"] == pa.STATUS_UNEXERCISED
    assert resolved[0]["evidence"]["reason"] == pa.REASON_EVIDENCE_EXERCISE_FAILED


def test_resolve_exercised_missing_exercise_becomes_unexercised():
    row_data = pa.row(
        area="a",
        claim="c",
        status=pa.STATUS_EXERCISED,
        evidence={"exercise": "missing-ex", "surface": "pilot_wave.wave_phase"},
    )
    resolved = pa.resolve([row_data], _report_data(), _declarations_block())
    assert resolved[0]["status"] == pa.STATUS_UNEXERCISED
    assert resolved[0]["evidence"]["reason"] == pa.REASON_EVIDENCE_EXERCISE_ABSENT


def test_resolve_attested_digest_mismatch_becomes_unexercised():
    row_data = pa.row(
        area="a",
        claim="c",
        status=pa.STATUS_ATTESTED,
        evidence={"kind": "session-surface", "slotRef": "slot-a@1", "digest": "wrong"},
    )
    resolved = pa.resolve([row_data], _report_data(), _declarations_block())
    assert resolved[0]["status"] == pa.STATUS_UNEXERCISED
    assert resolved[0]["evidence"]["reason"] == pa.REASON_EVIDENCE_DECLARATION_ABSENT


def test_resolve_attested_not_attested_becomes_unexercised():
    row_data = pa.row(
        area="a",
        claim="c",
        status=pa.STATUS_ATTESTED,
        evidence={"kind": "session-surface", "slotRef": "slot-a@1", "digest": "abc123"},
    )
    declarations = _declarations_block(
        rows=[
            {
                "kind": "session-surface",
                "slotRef": "slot-a@1",
                "status": "absent",
                "declarationDigest": "abc123",
                "reason": None,
            }
        ]
    )
    resolved = pa.resolve([row_data], _report_data(), declarations)
    assert resolved[0]["status"] == pa.STATUS_UNEXERCISED
    assert resolved[0]["evidence"]["reason"] == pa.REASON_EVIDENCE_DECLARATION_NOT_ATTESTED


def test_resolve_never_produces_not_applicable():
    cases = [
        pa.row(
            area="a",
            claim="c",
            status=pa.STATUS_EXERCISED,
            evidence={"exercise": "nope", "surface": "pilot_wave.wave_phase"},
        ),
        pa.row(
            area="a",
            claim="c",
            status=pa.STATUS_ATTESTED,
            evidence={"kind": "session-surface", "slotRef": "slot-a@1", "digest": "nope"},
        ),
    ]
    resolved = pa.resolve(cases, _report_data(), _declarations_block())
    assert all(r["status"] != pa.STATUS_NOT_APPLICABLE for r in resolved)


# --- matrix ok clauses --------------------------------------------------------

def _ok_base_rows():
    return [
        pa.row(area="a", claim="c", status=pa.STATUS_PROSE_RESIDUE),
    ]


def test_matrix_ok_requires_non_empty_rows():
    data = pa.matrix(
        _reference(),
        [],
        _report_data(),
        _declarations_block(),
        generated_at=_GENERATED_AT,
    )
    assert data["ok"] is False


def test_matrix_ok_requires_no_unexercised_rows():
    rows = [
        pa.row(
            area="a",
            claim="c",
            status=pa.STATUS_UNEXERCISED,
            evidence={"reason": "x"},
        )
    ]
    data = pa.matrix(
        _reference(),
        rows,
        _report_data(),
        _declarations_block(),
        generated_at=_GENERATED_AT,
    )
    assert data["ok"] is False


def test_matrix_ok_requires_clean_reference():
    data = pa.matrix(
        _reference(dirty=True),
        _ok_base_rows(),
        _report_data(),
        _declarations_block(),
        generated_at=_GENERATED_AT,
    )
    assert data["ok"] is False


def test_matrix_ok_requires_report_unexercised_empty():
    data = pa.matrix(
        _reference(),
        _ok_base_rows(),
        _report_data(unexercised=["pilot_wave.wave_phase"]),
        _declarations_block(),
        generated_at=_GENERATED_AT,
    )
    assert data["ok"] is False


def test_matrix_ok_requires_report_ok():
    data = pa.matrix(
        _reference(),
        _ok_base_rows(),
        _report_data(ok=False),
        _declarations_block(),
        generated_at=_GENERATED_AT,
    )
    assert data["ok"] is False


def test_matrix_ok_requires_declarations_ok():
    data = pa.matrix(
        _reference(),
        _ok_base_rows(),
        _report_data(),
        _declarations_block(ok=False),
        generated_at=_GENERATED_AT,
    )
    assert data["ok"] is False


def test_matrix_ok_true_when_all_clauses_hold():
    data = pa.matrix(
        _reference(),
        _ok_base_rows(),
        _report_data(),
        _declarations_block(),
        generated_at=_GENERATED_AT,
    )
    assert data["ok"] is True


# --- ownership two-row rule ---------------------------------------------------

def _passing_ownership_report():
    return _report_data(
        exercises=[
            _exercise(
                "ownership-probe",
                ["pilot_policy.ownership_probe_request"],
            )
        ]
    )


def test_ownership_probe_passing_leaves_broad_row_prose_residue():
    rows = pa.framework_rows(_passing_ownership_report(), _declarations_block())
    broad = [r for r in rows if "accumulating data" in r["claim"]]
    probe = [r for r in rows if "ownership probe" in r["claim"].lower()]
    assert len(broad) == 1
    assert len(probe) == 1
    assert broad[0]["status"] == pa.STATUS_PROSE_RESIDUE
    assert probe[0]["status"] == pa.STATUS_EXERCISED


# --- sign-in-cardinality never exercised --------------------------------------

def test_sign_in_cardinality_never_resolves_to_exercised():
    report = _report_data(
        exercises=[
            _exercise("wave-headless", ["pilot_wave.wave_phase"]),
            _exercise("reclaim-sweep", ["pilot_reclaim.sweep"]),
        ]
    )
    rows = pa.framework_rows(report, _declarations_block())
    sign_in = [r for r in rows if r.get("claim", "").startswith("Sign-in cardinality")]
    assert len(sign_in) == 1
    assert sign_in[0]["status"] == pa.STATUS_PROSE_RESIDUE


# --- render_markdown ------------------------------------------------------------

def test_render_markdown_escapes_pipe_in_claim():
    matrix_data = {
        "ok": False,
        "reference": {"project": "p", "commit": _VALID_SHA1, "dirty": False},
        "generatedAt": _GENERATED_AT,
        "rows": [
            pa.row(area="test-area", claim="a | b", status=pa.STATUS_PROSE_RESIDUE),
        ],
    }
    md = pa.render_markdown(matrix_data)
    assert "a \\| b" in md
    assert "**ok:** False" in md


def test_render_markdown_shows_dirty_warning():
    matrix_data = {
        "ok": False,
        "reference": {"project": "p", "commit": _VALID_SHA1, "dirty": True},
        "generatedAt": _GENERATED_AT,
        "rows": [
            pa.row(area="test-area", claim="c", status=pa.STATUS_PROSE_RESIDUE),
        ],
    }
    md = pa.render_markdown(matrix_data)
    assert "dirty" in md.lower()


def test_render_markdown_surfaces_unexercised_reason():
    matrix_data = {
        "ok": False,
        "reference": {"project": "p", "commit": _VALID_SHA1, "dirty": False},
        "generatedAt": _GENERATED_AT,
        "rows": [
            pa.row(
                area="test-area",
                claim="c",
                status=pa.STATUS_UNEXERCISED,
                evidence={"reason": pa.REASON_EVIDENCE_SURFACE_UNBOUND},
            ),
        ],
    }
    md = pa.render_markdown(matrix_data)
    assert "reason: %s" % pa.REASON_EVIDENCE_SURFACE_UNBOUND in md


# --- framework_rows totality --------------------------------------------------

def _empty_report():
    return {
        "ok": True,
        "unexercised": [],
        "warnings": [],
        "surfaces": [],
        "exercises": [],
    }


def _empty_declarations():
    return {
        "schemaVersion": 1,
        "rows": [],
        "attested": 0,
        "absent": 0,
        "notApplicable": 0,
        "ok": True,
    }


def _expected_framework_row_count():
    return (
        len(pa.FRAMEWORK_DECLARED_LIMITS)
        + len(pa.EXTRAPOLATION_POINTS)
        + len(pa.TRIPWIRE_ROWS)
    )


def test_framework_rows_degrades_never_raises_on_empty_inputs():
    """framework_rows is total: empty report and declarations yield every row, never raise."""
    rows = pa.framework_rows(_empty_report(), _empty_declarations())
    assert len(rows) == _expected_framework_row_count()
    for row_data in rows:
        assert row_data["status"] in (
            pa.STATUS_UNEXERCISED,
            pa.STATUS_DECLARED_LIMIT,
            pa.STATUS_PROSE_RESIDUE,
        )
        if row_data["status"] == pa.STATUS_UNEXERCISED:
            assert row_data["evidence"]["reason"]


# --- CLI ----------------------------------------------------------------------

def _write_report(tmpdir, report):
    path = os.path.join(tmpdir, "report.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle)
    return path


def _cli_argv(report_path, **extra):
    argv = [
        sys.executable,
        "-B",
        os.path.join(_LIB, "pilot_acceptance.py"),
        "matrix",
        "--report-path",
        report_path,
        "--project",
        "demo",
        "--commit",
        _VALID_SHA1,
        "--generated-at",
        _GENERATED_AT,
    ]
    for key, value in extra.items():
        if key == "dirty" and value:
            argv.append("--dirty")
        elif key == "format":
            argv.extend(["--format", value])
    return argv


def _minimal_passing_report():
    return {
        "ok": True,
        "unexercised": [],
        "exercises": [
            _exercise("horizon-validity", ["pilot_horizon.account_margin"]),
            _exercise("wave-headless", ["pilot_appctl.assert_unique_endpoints"]),
            _exercise("reclaim-sweep", ["pilot_reclaim.sweep"]),
            _exercise(
                "boundary-refusals",
                ["pilot_boundary.is_local_development_origin"],
            ),
            _exercise(
                "ownership-probe",
                ["pilot_policy.ownership_probe_request"],
            ),
        ],
        "declarations": _declarations_block(),
    }


def test_cli_exit_0_on_ok_matrix():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_report(tmpdir, _minimal_passing_report())
        proc = subprocess.run(
            _cli_argv(path),
            capture_output=True,
            text=True,
            cwd=_LIB,
        )
    assert proc.returncode == 0
    assert proc.stderr == ""
    data = json.loads(proc.stdout)
    assert data["ok"] is True


def test_cli_exit_1_on_not_ok_matrix():
    report = _minimal_passing_report()
    report["ok"] = False
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_report(tmpdir, report)
        proc = subprocess.run(
            _cli_argv(path),
            capture_output=True,
            text=True,
            cwd=_LIB,
        )
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["ok"] is False


def test_cli_exit_2_on_refusal():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_report(tmpdir, {"ok": True, "unexercised": []})
        argv = _cli_argv(path)
        argv[argv.index(_VALID_SHA1)] = "short"
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            cwd=_LIB,
        )
    assert proc.returncode == 2
    assert pa.REASON_REFERENCE_COMMIT_INVALID in proc.stderr
    assert proc.stdout == ""


def test_cli_markdown_format_on_stdout():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_report(tmpdir, _minimal_passing_report())
        proc = subprocess.run(
            _cli_argv(path, format="markdown"),
            capture_output=True,
            text=True,
            cwd=_LIB,
        )
    assert proc.returncode == 0
    assert proc.stdout.startswith("## Acceptance matrix")
    assert proc.stderr == ""
