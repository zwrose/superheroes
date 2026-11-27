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

import git_routing  # noqa: E402
import pilot_acceptance as pa  # noqa: E402
import pilot_conformance as pc  # noqa: E402
import pilot_conformance_declarations as pcd  # noqa: E402

_VALID_SHA1 = "a" * 40
_VALID_SHA256 = "b" * 64
_GENERATED_AT = "2026-08-08T12:00:00Z"


def _reference(**overrides):
    base = {"project": "example", "commit": _VALID_SHA1, "dirty": False}
    base.update(overrides)
    return base


def _bound(project="example", commit=_VALID_SHA1):
    return {"project": project, "commit": commit}


def _report_data(**overrides):
    base = {
        "schemaVersion": pc.SCHEMA,
        "reference": _bound(),
        "ok": True,
        "unexercised": [],
        "exercises": [],
    }
    base.update(overrides)
    return base


def _declarations_block(**overrides):
    base = {
        "schemaVersion": pcd.SCHEMA,
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
        "attested": 1,
        "absent": 0,
        "notApplicable": 0,
    }
    base.update(overrides)
    return base


def _empty_report():
    return {
        "schemaVersion": pc.SCHEMA,
        "reference": _bound(),
        "ok": True,
        "unexercised": [],
        "warnings": [],
        "surfaces": [],
        "exercises": [],
    }


def _empty_declarations():
    return {
        "schemaVersion": pcd.SCHEMA,
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


def test_resolve_exercised_refused_record_becomes_unexercised():
    row_data = pa.row(
        area="a",
        claim="c",
        status=pa.STATUS_EXERCISED,
        evidence={"exercise": "wave-headless", "surface": "pilot_wave.wave_phase"},
    )
    report = _report_data(
        exercises=[_exercise("wave-headless", ["pilot_wave.wave_phase"], result=pc.RESULT_REFUSED)]
    )
    resolved = pa.resolve([row_data], report, _declarations_block())
    assert resolved[0]["status"] == pa.STATUS_UNEXERCISED
    assert resolved[0]["evidence"]["reason"] == pa.REASON_EVIDENCE_EXERCISE_REFUSED


def test_resolve_exercised_skipped_record_becomes_unexercised():
    row_data = pa.row(
        area="a",
        claim="c",
        status=pa.STATUS_EXERCISED,
        evidence={"exercise": "wave-headless", "surface": "pilot_wave.wave_phase"},
    )
    report = _report_data(
        exercises=[_exercise("wave-headless", ["pilot_wave.wave_phase"], result=pc.RESULT_SKIPPED)]
    )
    resolved = pa.resolve([row_data], report, _declarations_block())
    assert resolved[0]["status"] == pa.STATUS_UNEXERCISED
    assert resolved[0]["evidence"]["reason"] == pa.REASON_EVIDENCE_EXERCISE_SKIPPED


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
    assert data["okClauses"]["rows_non_empty"] is True
    assert data["okClauses"]["declarations_ok"] is True


# --- report binding -----------------------------------------------------------

_OTHER_SHA1 = "c" * 40


def test_matrix_refuses_report_from_another_commit():
    report = _report_data(reference=_bound(commit=_OTHER_SHA1))
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.matrix(
            _reference(),
            _ok_base_rows(),
            report,
            _declarations_block(),
            generated_at=_GENERATED_AT,
        )
    assert exc.value.reason == pa.REASON_REPORT_COMMIT_MISMATCH
    assert _OTHER_SHA1 in exc.value.detail
    assert _VALID_SHA1 in exc.value.detail


def test_matrix_refuses_report_from_another_project():
    report = _report_data(reference=_bound(project="other-project"))
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.matrix(
            _reference(),
            _ok_base_rows(),
            report,
            _declarations_block(),
            generated_at=_GENERATED_AT,
        )
    assert exc.value.reason == pa.REASON_REPORT_PROJECT_MISMATCH
    assert "other-project" in exc.value.detail
    assert "example" in exc.value.detail


def test_matrix_refuses_report_differing_in_both_names_both():
    report = _report_data(reference=_bound(project="other-project", commit=_OTHER_SHA1))
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.bind_report(_reference(), report)
    assert exc.value.reason == pa.REASON_REPORT_COMMIT_MISMATCH
    assert _OTHER_SHA1 in exc.value.detail
    assert "other-project" in exc.value.detail


@pytest.mark.parametrize(
    "bound",
    [
        None,
        "example",
        {},
        {"project": "example"},
        {"commit": _VALID_SHA1},
        {"project": "", "commit": _VALID_SHA1},
        {"project": "example", "commit": None},
    ],
)
def test_matrix_refuses_unbound_report(bound):
    report = _report_data()
    if bound is None:
        del report["reference"]
    else:
        report["reference"] = bound
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa.matrix(
            _reference(),
            _ok_base_rows(),
            report,
            _declarations_block(),
            generated_at=_GENERATED_AT,
        )
    assert exc.value.reason == pa.REASON_REPORT_UNBOUND


def test_matrix_matching_report_still_backs_exercised_row():
    rows = [
        pa.row(
            area="a",
            claim="c",
            status=pa.STATUS_EXERCISED,
            evidence={"exercise": "reclaim-sweep", "surface": "pilot_reclaim.sweep"},
        )
    ]
    report = _report_data(exercises=[_exercise("reclaim-sweep", ["pilot_reclaim.sweep"])])
    data = pa.matrix(
        _reference(),
        rows,
        report,
        _declarations_block(),
        generated_at=_GENERATED_AT,
    )
    assert data["rows"][0]["status"] == pa.STATUS_EXERCISED
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


def test_render_markdown_shows_ok_clauses():
    report = _report_data(ok=False, unexercised=["pilot_wave.wave_phase"])
    declarations = _declarations_block(ok=False)
    matrix_data = pa.matrix(
        _reference(),
        [pa.row(area="test-area", claim="c", status=pa.STATUS_PROSE_RESIDUE)],
        report,
        declarations,
        generated_at=_GENERATED_AT,
    )
    md = pa.render_markdown(matrix_data, report_data=report, declarations_block=declarations)
    assert "**ok clauses:**" in md
    assert "conformance run left no unexercised surfaces: fail" in md
    assert "declarations envelope ok: fail" in md


def test_render_markdown_shows_declared_limit_ruling():
    matrix_data = {
        "ok": True,
        "reference": {"project": "p", "commit": _VALID_SHA1, "dirty": False},
        "generatedAt": _GENERATED_AT,
        "rows": [
            pa.row(
                area="declared-limit",
                claim="limit claim",
                status=pa.STATUS_DECLARED_LIMIT,
                limit_id="lid",
                closure_path="closure path",
                ruling=pa.RULING_PENDING_OWNER_RULING,
            ),
        ],
    }
    md = pa.render_markdown(matrix_data)
    assert "ruling: pending-owner-ruling" in md
    assert "closure: closure path" in md


def test_matrix_accepts_null_declarations():
    report = _empty_report()
    report["declarations"] = None
    rows = pa.framework_rows(report, pa._coerce_declarations_block(report))
    assert len(rows) == _expected_framework_row_count()
    matrix_data = pa.matrix(
        _reference(),
        rows,
        report,
        pa._coerce_declarations_block(report),
        generated_at=_GENERATED_AT,
    )
    assert "## Acceptance matrix" not in str(matrix_data)
    assert matrix_data["ok"] is False
    assert matrix_data["okClauses"]["declarations_ok"] is False


def test_coerce_declarations_absent_key_degrades():
    block = pa._coerce_declarations_block({})
    assert block["source"] == pa.REASON_CLI_DECLARATIONS_ABSENT
    assert block["ok"] is False


def test_coerce_declarations_explicit_null_degrades():
    block = pa._coerce_declarations_block({"declarations": None})
    assert block["source"] == pa.REASON_CLI_DECLARATIONS_NULL
    assert block["ok"] is False


def test_coerce_declarations_malformed_envelope_refuses():
    with pytest.raises(pa.PilotAcceptanceError) as exc:
        pa._coerce_declarations_block({"declarations": {"schemaVersion": pcd.SCHEMA}})
    assert exc.value.reason == pa.REASON_CLI_DECLARATIONS_MALFORMED


def test_cli_matrix_with_malformed_declarations_report():
    report = {
        "schemaVersion": pc.SCHEMA,
        "reference": _bound("demo"),
        "ok": False,
        "unexercised": list(pc.REQUIRED_SURFACES),
        "exercises": [],
        "declarations": {"schemaVersion": pcd.SCHEMA},
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_report(tmpdir, report)
        proc = subprocess.run(
            _cli_argv(path, format="markdown"),
            capture_output=True,
            text=True,
            cwd=_LIB,
        )
    assert proc.returncode == 2
    assert proc.stderr.strip() == pa.REASON_CLI_DECLARATIONS_MALFORMED


def test_cli_matrix_with_null_declarations_report():
    report = {
        "schemaVersion": pc.SCHEMA,
        "reference": _bound("demo"),
        "ok": False,
        "unexercised": list(pc.REQUIRED_SURFACES),
        "exercises": [],
        "declarations": None,
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_report(tmpdir, report)
        proc = subprocess.run(
            _cli_argv(path, format="markdown"),
            capture_output=True,
            text=True,
            cwd=_LIB,
        )
    assert proc.returncode == 1
    assert proc.stderr == ""
    assert proc.stdout.startswith("## Acceptance matrix")


def _pinned_git_env():
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _fixture_git_env():
    """The fixture's own git calls: pinned config, and no inherited routing variable, so a test
    that sets GIT_DIR for the run under test never redirects the fixture's commits."""
    env = _pinned_git_env()
    for key in git_routing.GIT_ROUTING_VARS:
        if key not in ("GIT_CONFIG_GLOBAL",):
            env.pop(key, None)
    return env


def _git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path)] + list(args),
        capture_output=True,
        text=True,
        check=True,
        env=_fixture_git_env(),
    )


def _commit_checkout(path):
    """Make `path` a git checkout with one commit; return that commit's full id."""
    _git(path, "init", "-q")
    _git(path, "add", "-A")
    _git(
        path,
        "-c",
        "user.name=Pilot Fixture",
        "-c",
        "user.email=pilot-fixture@example.test",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "fixture",
    )
    return _git(path, "rev-parse", "HEAD").stdout.strip()


def _conformance_fixture(tmp_path):
    from test_pilot_conformance import _write_calibration_layer  # noqa: E402

    reach_root = tmp_path / "reach"
    reach_root.mkdir()
    _write_calibration_layer(reach_root, include_mint=True)
    policy_root = tmp_path / "policy"
    policy_root.mkdir()
    policy = {
        "declaration": "example-project-pilot-policy",
        "slots": {
            "slot-a": {
                "origin": "http://127.0.0.1:5173",
                "permittedRedirects": ["http://127.0.0.1:5173"],
                "expectedIdentities": {"owner": "pilot-owner@example.test"},
                "mintableAccounts": ["pilot-owner"],
                "accountClasses": {"owner": "dev"},
            }
        },
    }
    with open(
        policy_root / "example-project-pilot-policy.json",
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(policy, handle)
    return reach_root, policy_root


def _run_conformance(reach_root, policy_root, *extra):
    argv = [
        sys.executable,
        "-B",
        os.path.join(_LIB, "pilot_conformance.py"),
        "run",
        "--cwd",
        str(reach_root),
        "--policy-root",
        str(policy_root),
        "--reach-root",
        str(reach_root),
        "--now",
        _GENERATED_AT,
    ] + list(extra)
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        cwd=_LIB,
        env=_pinned_git_env(),
    )


def _run_matrix_cli(report_path, project, commit):
    argv = [
        sys.executable,
        "-B",
        os.path.join(_LIB, "pilot_acceptance.py"),
        "matrix",
        "--report-path",
        str(report_path),
        "--project",
        project,
        "--commit",
        commit,
        "--generated-at",
        _GENERATED_AT,
        "--clean",
        "--format",
        "markdown",
    ]
    return subprocess.run(argv, capture_output=True, text=True, cwd=_LIB)


def test_conformance_run_with_project_stamps_reference(tmp_path):
    reach_root, policy_root = _conformance_fixture(tmp_path)
    commit = _commit_checkout(reach_root)
    proc = _run_conformance(reach_root, policy_root, "--project", "demo")
    assert proc.returncode in (0, 1)
    assert proc.stderr == ""
    report = json.loads(proc.stdout)
    assert report["reference"] == {"project": "demo", "commit": commit}
    assert len(commit) == 40


def test_conformance_run_with_project_refuses_unreadable_commit(tmp_path):
    reach_root, policy_root = _conformance_fixture(tmp_path)
    proc = _run_conformance(reach_root, policy_root, "--project", "demo")
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.strip() == pc.REASON_CLI_COMMIT_UNREADABLE


def test_conformance_run_refuses_invalid_project(tmp_path):
    reach_root, policy_root = _conformance_fixture(tmp_path)
    _commit_checkout(reach_root)
    proc = _run_conformance(reach_root, policy_root, "--project", "")
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.strip() == pc.REASON_CLI_PROJECT_INVALID


def test_conformance_run_unreadable_commit_ignores_inherited_git_dir(tmp_path, monkeypatch):
    """A --cwd that is no checkout still refuses when an inherited GIT_DIR names a real one."""
    reach_root, policy_root = _conformance_fixture(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "marker.txt").write_text("elsewhere\n", encoding="utf-8")
    _commit_checkout(elsewhere)
    monkeypatch.setenv("GIT_DIR", str(elsewhere / ".git"))
    proc = _run_conformance(reach_root, policy_root, "--project", "demo")
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.strip() == pc.REASON_CLI_COMMIT_UNREADABLE


def _refusal_probe(monkeypatch):
    """Swap in one registered exercise that records each call, so a test sees whether any ran."""
    ran = []

    @pc.register("refusal-probe", surfaces=["pilot_reclaim.sweep"])
    def probe(inputs, now):
        ran.append("probe")
        return pc.exercise_record(
            exercise="refusal-probe",
            surfaces=["pilot_reclaim.sweep"],
            result=pc.RESULT_PASS,
            reason=None,
            evidence="probe ran",
            exercised_at=now,
        )

    monkeypatch.setattr(pc, "default_exercises", lambda: [probe])
    return ran


@pytest.mark.parametrize(
    "project, make_checkout, reason",
    [
        ("demo", False, pc.REASON_CLI_COMMIT_UNREADABLE),
        ("", True, pc.REASON_CLI_PROJECT_INVALID),
    ],
)
def test_conformance_reference_refusal_runs_no_exercise(
    tmp_path, monkeypatch, capsys, project, make_checkout, reason
):
    """bite-axis: preflight order — a refused stamp stops the run before any exercise runs."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "marker.txt").write_text("checkout\n", encoding="utf-8")
    if make_checkout:
        _commit_checkout(checkout)
    ran = _refusal_probe(monkeypatch)
    exit_code = pc.main([
        "pilot_conformance.py",
        "run",
        "--cwd",
        str(checkout),
        "--now",
        _GENERATED_AT,
        "--allow-live-effects",
        "--project",
        project,
    ])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.strip() == reason
    assert ran == []


def test_conformance_run_without_project_stamps_no_reference(tmp_path):
    reach_root, policy_root = _conformance_fixture(tmp_path)
    proc = _run_conformance(reach_root, policy_root)
    assert proc.returncode in (0, 1)
    assert "reference" not in json.loads(proc.stdout)


def test_e2e_conformance_run_then_matrix_cli(tmp_path):
    """The documented pipeline, end to end: a stamped report backs a matrix for its own pair."""
    reach_root, policy_root = _conformance_fixture(tmp_path)
    commit = _commit_checkout(reach_root)
    conformance_proc = _run_conformance(reach_root, policy_root, "--project", "demo")
    assert conformance_proc.stderr == ""
    # conformance may exit 1 when surfaces unexercised
    report_path = tmp_path / "report.json"
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(conformance_proc.stdout)
    matrix_proc = _run_matrix_cli(report_path, "demo", commit)
    assert matrix_proc.returncode in (0, 1)
    assert matrix_proc.stderr == ""
    assert matrix_proc.stdout.startswith("## Acceptance matrix")

    other_commit = _run_matrix_cli(report_path, "demo", "c" * 40)
    assert other_commit.returncode == 2
    assert other_commit.stderr.splitlines()[0] == pa.REASON_REPORT_COMMIT_MISMATCH
    assert commit in other_commit.stderr

    other_project = _run_matrix_cli(report_path, "elsewhere", commit)
    assert other_project.returncode == 2
    assert other_project.stderr.splitlines()[0] == pa.REASON_REPORT_PROJECT_MISMATCH


def test_e2e_unstamped_report_refuses_as_unbound(tmp_path):
    reach_root, policy_root = _conformance_fixture(tmp_path)
    commit = _commit_checkout(reach_root)
    conformance_proc = _run_conformance(reach_root, policy_root)
    report_path = tmp_path / "report.json"
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(conformance_proc.stdout)
    matrix_proc = _run_matrix_cli(report_path, "demo", commit)
    assert matrix_proc.returncode == 2
    assert matrix_proc.stdout == ""
    assert matrix_proc.stderr.splitlines()[0] == pa.REASON_REPORT_UNBOUND


# --- framework_rows totality --------------------------------------------------

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
        "--clean",
    ]
    for key, value in extra.items():
        if key == "dirty" and value:
            if "--clean" in argv:
                argv.remove("--clean")
            argv.append("--dirty")
        elif key == "format":
            argv.extend(["--format", value])
    return argv


def _minimal_passing_report():
    return {
        "schemaVersion": pc.SCHEMA,
        "reference": _bound("demo"),
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


def test_cli_derives_dirty_from_git_status(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "dirty-marker.txt").write_text("dirty", encoding="utf-8")
    report = {
        "schemaVersion": pc.SCHEMA,
        "reference": _bound("demo"),
        "ok": False,
        "unexercised": list(pc.REQUIRED_SURFACES),
        "exercises": [],
        "declarations": None,
    }
    path = _write_report(tmpdir=str(tmp_path), report=report)
    argv = [
        sys.executable,
        "-B",
        os.path.join(_LIB, "pilot_acceptance.py"),
        "matrix",
        "--report-path",
        path,
        "--project",
        "demo",
        "--commit",
        _VALID_SHA1,
        "--generated-at",
        _GENERATED_AT,
        "--format",
        "json",
    ]
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=tmp_path)
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["reference"]["dirty"] is True


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
        path = _write_report(
            tmpdir,
            {"schemaVersion": pc.SCHEMA, "ok": True, "unexercised": [], "declarations": None},
        )
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


@pytest.mark.parametrize(
    "bound, reason, named",
    [
        ({"project": "demo", "commit": "c" * 40}, pa.REASON_REPORT_COMMIT_MISMATCH, "c" * 40),
        ({"project": "elsewhere", "commit": _VALID_SHA1}, pa.REASON_REPORT_PROJECT_MISMATCH, "elsewhere"),
        (None, pa.REASON_REPORT_UNBOUND, "project or commit"),
    ],
)
def test_cli_refuses_report_not_bound_to_reference(bound, reason, named):
    report = _minimal_passing_report()
    if bound is None:
        del report["reference"]
    else:
        report["reference"] = bound
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_report(tmpdir, report)
        proc = subprocess.run(
            _cli_argv(path),
            capture_output=True,
            text=True,
            cwd=_LIB,
        )
    assert proc.returncode == 2
    assert proc.stdout == ""
    lines = proc.stderr.splitlines()
    assert lines[0] == reason
    assert named in proc.stderr


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
