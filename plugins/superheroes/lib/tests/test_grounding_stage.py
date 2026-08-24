import ast
import importlib.util
import io
import json
import os
import sys
from unittest.mock import patch

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GS = _load("grounding_stage")

EXPECTED_REFUSAL_REASONS = frozenset({
    "meta-unreadable",
    "meta-mode-unknown",
    "pr-json-unreadable",
    "pr-json-unparseable",
    "pr-body-absent",
    "pr-body-empty",
    "pr-body-too-large",
    "pr-body-claim-count-exceeded",
    "session-dir-not-absolute",
    "stage-unwritable",
    "stage-readback-mismatch",
    "stage-manifest-missing",
    "stage-manifest-invalid",
    "staged-file-unreadable",
    "staged-file-hash-mismatch",
    "staged-stage-token-mismatch",
    "manifest-flag-mismatch",
    "source-body-stale",
    "staged-body-source-mismatch",
    "stage-unreachable-for-vendor",
    "attest-result-outside-session",
    "attest-result-unreadable",
    "attest-token-missing",
    "attest-token-mismatch",
    "attest-claim-unanswered",
    "attest-verdict-out-of-enum",
    "region-marker-duplicated",
    "dod-table-rows-unadmitted",
    "body-context-unterminated",
    "attest-duplicate-claim-verdict",
    "attest-verdict-reason-missing",
    "invalid-invocation",
    "internal-error",
})


def _session(tmp_path, mode="pr", body=None, meta_extra=None, name="session"):
    d = tmp_path / name
    d.mkdir()
    meta = {"mode": mode}
    if meta_extra:
        meta.update(meta_extra)
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if body is not None:
        (d / "pr.json").write_text(json.dumps({"body": body}), encoding="utf-8")
    return str(d)


def _happy_body():
    return (
        "## Summary\n"
        "Ship grounding stage.\n\n"
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| tests pass | done | `plugins/superheroes/lib/tests/test_grounding_stage.py` |\n"
        "| defer item | deferred | #609 reason |\n\n"
        "<!-- superheroes:build-record -->\n"
        "<details><summary>Build record</summary></details>\n\n"
        "<!-- superheroes:degradations -->\n"
        "### Disclosed degradations\n"
        "- promised full suite, delivered scoped tests only\n"
        "- promised advisor vet, delivered inline check\n\n"
        "Seam STUB(#123): unwired grounding dispatch\n"
    )


def _invoke(cmd, session_dir, vendor_path="engine", result_path=None):
    argv = ["grounding_stage.py", cmd, "--session-dir", session_dir]
    if cmd in ("check", "attest"):
        argv.extend(["--vendor-path", vendor_path])
    if cmd == "attest":
        if result_path is None:
            raise ValueError("attest requires result_path")
        argv.extend(["--result-path", result_path])
    out = io.StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        rc = GS.main(argv)
    finally:
        sys.stdout = old
    lines = [ln for ln in out.getvalue().strip().splitlines() if ln.strip()]
    body = json.loads(lines[-1]) if lines else {}
    return rc, body


def _manifest(session):
    manifest_path = os.path.join(session, "grounding", "stage.json")
    with open(manifest_path, encoding="utf-8") as fh:
        return json.load(fh)


def _manifest_token(session):
    return _manifest(session)["stageToken"]


def _projected_claims(manifest):
    return GS._project_claims(manifest["claims"])


def _staged_body_text(session):
    path = os.path.join(session, "grounding", "pr-body.md")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _assert_refusal(rc, body, reason):
    assert rc == 1
    assert body == {
        "ok": False,
        "signal": "cannot-certify",
        "reason": reason,
        "detail": body.get("detail"),
    }


def test_refusal_reason_census():
    # bite-axis: refusal vocabulary — every registered token must appear in the census set.
    assert GS.REFUSAL_REASONS == EXPECTED_REFUSAL_REASONS


def test_refuse_unregistered_reason_raises():
    with pytest.raises(ValueError, match="unregistered refusal reason"):
        GS._refuse("not-a-real-reason")


def test_refuse_dict_shape():
    result = GS._refuse("pr-body-empty", "detail text")
    assert result == {
        "ok": False,
        "signal": "cannot-certify",
        "reason": "pr-body-empty",
        "detail": "detail text",
    }


def test_invalid_invocation_bad_subcommand(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    argv = ["grounding_stage.py", "nope", "--session-dir", session]
    out = io.StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        rc = GS.main(argv)
    finally:
        sys.stdout = old
    body = json.loads(out.getvalue().strip().splitlines()[-1])
    _assert_refusal(rc, body, "invalid-invocation")


def test_edge_01_meta_unreadable(tmp_path):
    rc, body = _invoke("stage", str(tmp_path / "missing"))
    _assert_refusal(rc, body, "meta-unreadable")


def test_edge_02_meta_mode_unknown_missing_mode(tmp_path):
    d = tmp_path / "session"
    d.mkdir()
    (d / "meta.json").write_text("{}", encoding="utf-8")
    rc, body = _invoke("stage", str(d))
    _assert_refusal(rc, body, "meta-mode-unknown")


def test_edge_03_pr_json_unreadable(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    os.unlink(os.path.join(session, "pr.json"))
    rc, body = _invoke("stage", session)
    _assert_refusal(rc, body, "pr-json-unreadable")


def test_edge_04_pr_json_unparseable(tmp_path):
    d = tmp_path / "session"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"mode": "pr"}), encoding="utf-8")
    (d / "pr.json").write_text("{not json", encoding="utf-8")
    rc, body = _invoke("stage", str(d))
    _assert_refusal(rc, body, "pr-json-unparseable")


def test_edge_05_pr_body_absent(tmp_path):
    d = tmp_path / "session"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"mode": "pr"}), encoding="utf-8")
    (d / "pr.json").write_text(json.dumps({"title": "x"}), encoding="utf-8")
    rc, body = _invoke("stage", str(d))
    _assert_refusal(rc, body, "pr-body-absent")


def test_edge_06_pr_body_empty(tmp_path):
    session = _session(tmp_path, body="   \n\t")
    rc, body = _invoke("stage", session)
    _assert_refusal(rc, body, "pr-body-empty")


def test_edge_07_stage_unwritable(tmp_path, monkeypatch):
    session = _session(tmp_path, body=_happy_body())

    def boom(path, text, tmp_prefix=".grounding-stage-"):
        raise OSError("permission denied")

    monkeypatch.setattr(GS, "_atomic_write_text", boom)
    rc, body = _invoke("stage", session)
    _assert_refusal(rc, body, "stage-unwritable")


def test_edge_08_stage_readback_mismatch(tmp_path, monkeypatch):
    session = _session(tmp_path, body=_happy_body())
    real_atomic = GS._atomic_write_text

    def drift_write(path, text, tmp_prefix=".grounding-stage-"):
        if path.endswith("pr-body.md"):
            real_atomic(path, text + "\n<!-- drift -->\n", tmp_prefix=tmp_prefix)
        else:
            real_atomic(path, text, tmp_prefix=tmp_prefix)

    monkeypatch.setattr(GS, "_atomic_write_text", drift_write)
    rc, body = _invoke("stage", session)
    _assert_refusal(rc, body, "stage-readback-mismatch")


def test_edge_08b_manifest_readback_mismatch(tmp_path, monkeypatch):
    session = _session(tmp_path, body=_happy_body())
    real_atomic = GS._atomic_write_text

    def drift_write(path, text, tmp_prefix=".grounding-stage-"):
        if path.endswith("stage.json"):
            real_atomic(path, text + "\n<!-- drift -->\n", tmp_prefix=tmp_prefix)
        else:
            real_atomic(path, text, tmp_prefix=tmp_prefix)

    monkeypatch.setattr(GS, "_atomic_write_text", drift_write)
    rc, body = _invoke("stage", session)
    _assert_refusal(rc, body, "stage-readback-mismatch")


def test_edge_07b_manifest_unwritable(tmp_path, monkeypatch):
    session = _session(tmp_path, body=_happy_body())
    real_atomic = GS._atomic_write_text

    def boom_manifest(path, text, tmp_prefix=".grounding-stage-"):
        if path.endswith("stage.json"):
            raise OSError("permission denied")
        real_atomic(path, text, tmp_prefix=tmp_prefix)

    monkeypatch.setattr(GS, "_atomic_write_text", boom_manifest)
    rc, body = _invoke("stage", session)
    _assert_refusal(rc, body, "stage-unwritable")


def test_edge_09_stage_manifest_missing(tmp_path):
    session = _session(tmp_path, mode="pr")
    rc, body = _invoke("check", session)
    _assert_refusal(rc, body, "stage-manifest-missing")


def test_edge_10_stage_manifest_invalid(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest = tmp_path / "session" / "grounding" / "stage.json"
    manifest.write_text('{"schema":"wrong/0"}', encoding="utf-8")
    rc, body = _invoke("check", session)
    _assert_refusal(rc, body, "stage-manifest-invalid")


def test_manifest_empty_files_rejected(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest_path = tmp_path / "session" / "grounding" / "stage.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    rc, body = _invoke("check", session)
    _assert_refusal(rc, body, "stage-manifest-invalid")


def test_edge_11_staged_file_unreadable(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    os.chmod(os.path.join(session, "grounding", "pr-body.md"), 0)
    try:
        rc, body = _invoke("check", session)
        _assert_refusal(rc, body, "staged-file-unreadable")
    finally:
        os.chmod(os.path.join(session, "grounding", "pr-body.md"), 0o644)


def test_edge_12_staged_file_hash_mismatch(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    pr_body = tmp_path / "session" / "grounding" / "pr-body.md"
    pr_body.write_text(pr_body.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    rc, body = _invoke("check", session)
    _assert_refusal(rc, body, "staged-file-hash-mismatch")


def _dod_claims(manifest):
    return [c for c in manifest["claims"] if c["kind"] == "dod-row"]


def _degradation_claims(manifest):
    return [c for c in manifest["claims"] if c["kind"] == "degradation"]


def test_dod_rows_exact_set_and_verifiability(tmp_path):
    body = (
        "## Summary\n"
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| Ship the thing | done | tests/test_a.py |\n"
        "| Defer later | deferred | #609 reason |\n"
        "| Remove deferred fallback | done | tests/test_x.py |\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    dod = _dod_claims(manifest)
    assert len(dod) == 3
    by_text = {c["text"]: c["verifiability"] for c in dod}
    assert "DoD|Status|Evidence" not in by_text
    assert by_text["Ship the thing|done|tests/test_a.py"] == "repo"
    assert by_text["Defer later|deferred|#609 reason"] == "external"
    assert by_text["Remove deferred fallback|done|tests/test_x.py"] == "repo"
    repo_dod = [c for c in body_out["claims"] if c["kind"] == "dod-row"]
    repo_texts = {c["text"] for c in repo_dod}
    assert "Remove deferred fallback|done|tests/test_x.py" in repo_texts
    assert "Defer later|deferred|#609 reason" in repo_texts
    assert "Ship the thing|done|tests/test_a.py" in repo_texts


def test_dod_table_without_separator_refuses_unadmitted(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
        "| Ship the thing | done | tests/test_a.py |\n"
        "| Second thing | done | tests/b.py |"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    _assert_refusal(rc, body_out, "dod-table-rows-unadmitted")


def test_dod_table_with_separator_excludes_header_only(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| Ship the thing | done | tests/test_a.py |\n"
        "| Second thing | done | tests/b.py |"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    dod = _dod_claims(manifest)
    assert len(dod) == 2
    texts = {c["text"] for c in dod}
    assert "DoD|Status|Evidence" not in texts
    assert texts == {
        "Ship the thing|done|tests/test_a.py",
        "Second thing|done|tests/b.py",
    }


def test_degradation_marker_without_heading_bounded_by_first_heading(tmp_path):
    body = (
        "<!-- superheroes:degradations -->\n"
        "- real degradation one\n\n"
        "### Dispatch provenance\n"
        "- WO-A by cursor\n\n"
        "### Follow-ups\n"
        "- unrelated follow-up\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    deg = _degradation_claims(manifest)
    assert [c["text"] for c in deg] == ["real degradation one"]


def test_degradation_region_bounded_by_headings(tmp_path):
    body = (
        "## Summary\n"
        "<!-- superheroes:degradations -->\n"
        "### Disclosed degradations\n"
        "- real degradation one\n\n"
        "### Dispatch provenance\n"
        "- WO-A implemented by cursor\n"
        "- WO-B implemented by cursor\n\n"
        "### Follow-up\n"
        "- unrelated follow-up item\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    deg = _degradation_claims(manifest)
    assert len(deg) == 1
    assert deg[0]["text"] == "real degradation one"
    repo_deg = [c for c in body_out["claims"] if c["kind"] == "degradation"]
    assert len(repo_deg) == 1
    assert repo_deg[0]["text"] == "real degradation one"


def test_dod_table_separator_does_not_drop_final_row(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| Only data row | done | tests/final.py |"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    dod = _dod_claims(manifest)
    assert len(dod) == 1
    assert dod[0]["text"] == "Only data row|done|tests/final.py"


def test_happy_path_stage(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, body = _invoke("stage", session)
    assert rc == 0
    assert body["ok"] is True
    assert body["applicable"] is True
    assert "stageToken" not in body
    manifest = _manifest(session)
    assert manifest["schema"] == GS.STAGE_SCHEMA
    regions = {r["name"]: r for r in manifest["regions"]}
    assert regions["dod-table"]["present"] is True
    assert regions["build-record"]["present"] is True
    assert regions["degradations"]["present"] is True
    assert regions["advisor-vet"]["present"] is False
    claim_ids_first = [c["claimId"] for c in manifest["claims"]]
    token_first = manifest["stageToken"]
    rc2, body2 = _invoke("stage", session)
    assert rc2 == 0
    manifest2 = _manifest(session)
    claim_ids_second = [c["claimId"] for c in manifest2["claims"]]
    token_second = manifest2["stageToken"]
    assert claim_ids_first == claim_ids_second
    assert token_first != token_second
    kinds = {c["kind"] for c in manifest["claims"]}
    assert "region-present" in kinds
    assert "dod-row" in kinds
    assert "degradation" in kinds
    assert "stub-marker" in kinds
    staged = _staged_body_text(session)
    assert "BEGIN UNTRUSTED PR BODY" in staged
    assert "END UNTRUSTED PR BODY" in staged
    assert "Echo this token" not in staged


def test_stub_marker_claim_text_emitted_unchanged(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, body = _invoke("stage", session)
    assert rc == 0 and body["ok"]
    manifest = _manifest(session)
    stub_claims = [c for c in manifest["claims"] if c["kind"] == "stub-marker"]
    assert len(stub_claims) == 1
    assert stub_claims[0]["text"] == "STUB(#123): unwired grounding dispatch"


def test_absent_regions_still_stage(tmp_path):
    body = "## Summary\nNo markers here.\n"
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    assert body_out.get("noSubstantiveClaims") is not True
    manifest = _manifest(session)
    assert manifest.get("noSubstantiveClaims") is not True
    regions = {r["name"]: r for r in manifest["regions"]}
    assert regions["dod-table"]["present"] is False
    assert regions["degradations"]["present"] is False
    region_claims = [c for c in manifest["claims"] if c["kind"] == "region-present"]
    names = {c["text"] for c in region_claims}
    assert any("dod-table" in t and "present=False" in t for t in names)
    assert any("degradations" in t and "present=False" in t for t in names)
    assert all(c["verifiability"] == "stager" for c in region_claims)


def test_branch_mode_writes_nothing(tmp_path):
    session = _session(tmp_path, mode="branch", body=_happy_body())
    rc, body = _invoke("stage", session)
    assert rc == 0
    assert body == {"ok": True, "applicable": False, "reason": "branch-mode-has-no-pr-body"}
    assert not os.path.isdir(os.path.join(session, "grounding"))


def test_check_branch_mode_applicable_false(tmp_path):
    session = _session(tmp_path, mode="branch", body=_happy_body())
    rc, body = _invoke("check", session)
    assert rc == 0
    assert body == {"ok": True, "applicable": False, "reason": "branch-mode-has-no-pr-body"}


def test_every_registered_refusal_reason_is_observably_emitted(tmp_path):
    # bite-axis: refusal reachability — every registered token must be observable in a live refusal.
    cases = {}

    def case_meta_unreadable():
        return _invoke("stage", str(tmp_path / "case-meta-unreadable-missing"))

    cases["meta-unreadable"] = case_meta_unreadable

    def case_meta_mode_unknown():
        d = tmp_path / "case-meta-mode-unknown"
        d.mkdir()
        (d / "meta.json").write_text("{}", encoding="utf-8")
        return _invoke("stage", str(d))

    cases["meta-mode-unknown"] = case_meta_mode_unknown

    def case_pr_json_unreadable():
        session = _session(tmp_path, body=_happy_body(), name="case-pr-json-unreadable")
        os.unlink(os.path.join(session, "pr.json"))
        return _invoke("stage", session)

    cases["pr-json-unreadable"] = case_pr_json_unreadable

    def case_pr_json_unparseable():
        d = tmp_path / "case-pr-json-unparseable"
        d.mkdir()
        (d / "meta.json").write_text(json.dumps({"mode": "pr"}), encoding="utf-8")
        (d / "pr.json").write_text("{not json", encoding="utf-8")
        return _invoke("stage", str(d))

    cases["pr-json-unparseable"] = case_pr_json_unparseable

    def case_pr_body_absent():
        d = tmp_path / "case-pr-body-absent"
        d.mkdir()
        (d / "meta.json").write_text(json.dumps({"mode": "pr"}), encoding="utf-8")
        (d / "pr.json").write_text(json.dumps({"title": "x"}), encoding="utf-8")
        return _invoke("stage", str(d))

    cases["pr-body-absent"] = case_pr_body_absent

    def case_pr_body_empty():
        session = _session(tmp_path, body="   \n\t", name="case-pr-body-empty")
        return _invoke("stage", session)

    cases["pr-body-empty"] = case_pr_body_empty

    def case_pr_body_too_large():
        pad = "x" * (GS.PR_BODY_MAX_BYTES + 1)
        session = _session(tmp_path, body=pad, name="case-pr-body-too-large")
        return _invoke("stage", session)

    cases["pr-body-too-large"] = case_pr_body_too_large

    def case_pr_body_claim_count_exceeded():
        over = GS.CLAIM_COUNT_MAX - 4 + 1
        session = _session(
            tmp_path, body=_dod_table_body(over), name="case-pr-body-claim-count-exceeded",
        )
        return _invoke("stage", session)

    cases["pr-body-claim-count-exceeded"] = case_pr_body_claim_count_exceeded

    def case_session_dir_not_absolute():
        session = _session(tmp_path, body=_happy_body(), name="case-session-dir-not-absolute")
        rel = os.path.relpath(session)
        return _invoke("stage", rel)

    cases["session-dir-not-absolute"] = case_session_dir_not_absolute

    def case_stage_unwritable():
        session = _session(tmp_path, body=_happy_body(), name="case-stage-unwritable")

        def boom(path, text, tmp_prefix=".grounding-stage-"):
            raise OSError("permission denied")

        with patch.object(GS, "_atomic_write_text", boom):
            return _invoke("stage", session)

    cases["stage-unwritable"] = case_stage_unwritable

    def case_stage_readback_mismatch():
        session = _session(tmp_path, body=_happy_body(), name="case-stage-readback-mismatch")
        real_atomic = GS._atomic_write_text

        def drift_write(path, text, tmp_prefix=".grounding-stage-"):
            if path.endswith("pr-body.md"):
                real_atomic(path, text + "\n<!-- drift -->\n", tmp_prefix=tmp_prefix)
            else:
                real_atomic(path, text, tmp_prefix=tmp_prefix)

        with patch.object(GS, "_atomic_write_text", drift_write):
            return _invoke("stage", session)

    cases["stage-readback-mismatch"] = case_stage_readback_mismatch

    def case_stage_manifest_missing():
        session = _session(tmp_path, mode="pr", name="case-stage-manifest-missing")
        return _invoke("check", session)

    cases["stage-manifest-missing"] = case_stage_manifest_missing

    def case_stage_manifest_invalid():
        session = _session(tmp_path, body=_happy_body(), name="case-stage-manifest-invalid")
        rc, _ = _invoke("stage", session)
        assert rc == 0
        manifest = tmp_path / "case-stage-manifest-invalid" / "grounding" / "stage.json"
        manifest.write_text('{"schema":"wrong/0"}', encoding="utf-8")
        return _invoke("check", session)

    cases["stage-manifest-invalid"] = case_stage_manifest_invalid

    def case_staged_file_unreadable():
        session = _session(tmp_path, body=_happy_body(), name="case-staged-file-unreadable")
        rc, _ = _invoke("stage", session)
        assert rc == 0
        pr_body = os.path.join(session, "grounding", "pr-body.md")
        os.chmod(pr_body, 0)
        try:
            return _invoke("check", session)
        finally:
            os.chmod(pr_body, 0o644)

    cases["staged-file-unreadable"] = case_staged_file_unreadable

    def case_staged_file_hash_mismatch():
        session = _session(tmp_path, body=_happy_body(), name="case-staged-file-hash-mismatch")
        rc, _ = _invoke("stage", session)
        assert rc == 0
        pr_body = tmp_path / "case-staged-file-hash-mismatch" / "grounding" / "pr-body.md"
        pr_body.write_text(pr_body.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        return _invoke("check", session)

    cases["staged-file-hash-mismatch"] = case_staged_file_hash_mismatch

    def case_staged_stage_token_mismatch():
        session = _session(tmp_path, body=_happy_body(), name="case-staged-stage-token-mismatch")
        rc, _ = _invoke("stage", session)
        assert rc == 0
        manifest_path = tmp_path / "case-staged-stage-token-mismatch" / "grounding" / "stage.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["stageToken"] = "9999-9999-9999-9999"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return _invoke("check", session)

    cases["staged-stage-token-mismatch"] = case_staged_stage_token_mismatch

    def case_manifest_flag_mismatch():
        session = _session(tmp_path, body=_happy_body(), name="case-manifest-flag-mismatch")
        rc, _ = _invoke("stage", session)
        assert rc == 0
        manifest_path = tmp_path / "case-manifest-flag-mismatch" / "grounding" / "stage.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["noSubstantiveClaims"] = True
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return _invoke("check", session)

    cases["manifest-flag-mismatch"] = case_manifest_flag_mismatch

    def case_source_body_stale():
        session = _session(tmp_path, body=_happy_body(), name="case-source-body-stale")
        rc, _ = _invoke("stage", session)
        assert rc == 0
        pr_path = tmp_path / "case-source-body-stale" / "pr.json"
        pr_data = json.loads(pr_path.read_text(encoding="utf-8"))
        pr_data["body"] = pr_data["body"] + "\nEdited after staging."
        pr_path.write_text(json.dumps(pr_data), encoding="utf-8")
        return _invoke("check", session)

    cases["source-body-stale"] = case_source_body_stale

    def case_staged_body_source_mismatch():
        session = _session(
            tmp_path, body=_happy_body(), name="case-staged-body-source-mismatch",
        )
        rc, _ = _invoke("stage", session)
        assert rc == 0
        _tamper_staged_body_preserve_source_sha(
            session,
            lambda body: body.replace(
                "Ship grounding stage.", "Ship grounding stage!", 1,
            ),
        )
        return _invoke("check", session)

    cases["staged-body-source-mismatch"] = case_staged_body_source_mismatch

    def case_stage_unreachable_for_vendor():
        session = _session(
            tmp_path, body=_happy_body(), name="case-stage-unreachable-for-vendor",
        )
        rc, _ = _invoke("stage", session)
        assert rc == 0
        result = GS.check(session, "bogus")
        rc_out = 1 if not result.get("ok") else 0
        return rc_out, result

    cases["stage-unreachable-for-vendor"] = case_stage_unreachable_for_vendor

    def _staged_for_attest(name):
        session = _session(tmp_path, body=_happy_body(), name=name)
        rc, _ = _invoke("stage", session)
        assert rc == 0
        return session, _manifest(session)

    def _attest_verdicts(manifest, mutate=None):
        rows = [{
            "id": "stage-token:%s" % manifest["stageToken"],
            "verdict": "CONFIRMED",
            "reason": "read stage token from staged body",
        }]
        for claim in manifest["claims"]:
            if claim.get("verifiability") == GS.VERIFIABILITY_REPO:
                rows.append({
                    "id": claim["claimId"],
                    "verdict": "CONFIRMED",
                    "reason": "verified in repository",
                })
        if mutate:
            mutate(rows)
        return rows

    def _write_attest_result(session, manifest, mutate=None):
        path = os.path.join(session, "grounding", "attest-result.json")
        payload = {"verdicts": _attest_verdicts(manifest, mutate=mutate)}
        open(path, "w", encoding="utf-8").write(json.dumps(payload))
        return path

    def case_attest_result_outside_session():
        session, manifest = _staged_for_attest("case-attest-result-outside-session")
        outside = tmp_path / "outside-result.json"
        outside.write_text(json.dumps({"verdicts": []}), encoding="utf-8")
        return _invoke("attest", session, result_path=str(outside))

    cases["attest-result-outside-session"] = case_attest_result_outside_session

    def case_attest_result_unreadable():
        session, manifest = _staged_for_attest("case-attest-result-unreadable")
        path = os.path.join(session, "grounding", "attest-result.json")
        open(path, "w", encoding="utf-8").write("{not json")
        return _invoke("attest", session, result_path=path)

    cases["attest-result-unreadable"] = case_attest_result_unreadable

    def case_attest_token_missing():
        session, manifest = _staged_for_attest("case-attest-token-missing")
        path = _write_attest_result(session, manifest, mutate=lambda rows: rows.clear())
        return _invoke("attest", session, result_path=path)

    cases["attest-token-missing"] = case_attest_token_missing

    def case_attest_token_mismatch():
        session, manifest = _staged_for_attest("case-attest-token-mismatch")

        def mutate(rows):
            for row in rows:
                if row["id"].startswith("stage-token:"):
                    row["id"] = "stage-token:0000-0000-0000-0000"

        path = _write_attest_result(session, manifest, mutate=mutate)
        return _invoke("attest", session, result_path=path)

    cases["attest-token-mismatch"] = case_attest_token_mismatch

    def case_attest_claim_unanswered():
        session, manifest = _staged_for_attest("case-attest-claim-unanswered")

        def mutate(rows):
            rows[:] = [
                {
                    "id": "stage-token:%s" % manifest["stageToken"],
                    "verdict": "CONFIRMED",
                    "reason": "read stage token from staged body",
                },
            ]

        path = _write_attest_result(session, manifest, mutate=mutate)
        return _invoke("attest", session, result_path=path)

    cases["attest-claim-unanswered"] = case_attest_claim_unanswered

    def case_attest_verdict_out_of_enum():
        session, manifest = _staged_for_attest("case-attest-verdict-out-of-enum")

        def mutate(rows):
            for row in rows:
                if not row["id"].startswith("stage-token:"):
                    row["verdict"] = "BOGUS"

        path = _write_attest_result(session, manifest, mutate=mutate)
        return _invoke("attest", session, result_path=path)

    cases["attest-verdict-out-of-enum"] = case_attest_verdict_out_of_enum

    def case_region_marker_duplicated():
        marker = GS.REGION_MARKERS["dod-table"]
        session = _session(
            tmp_path, body=_duplicate_marker_body(marker), name="case-region-marker-duplicated",
        )
        return _invoke("stage", session)

    cases["region-marker-duplicated"] = case_region_marker_duplicated

    def case_dod_table_rows_unadmitted():
        body = (
            "<!-- superheroes:dod-table -->\n"
            "| lone row | done | tests/a.py |\n"
        )
        session = _session(tmp_path, body=body, name="case-dod-table-rows-unadmitted")
        return _invoke("stage", session)

    cases["dod-table-rows-unadmitted"] = case_dod_table_rows_unadmitted

    def case_body_context_unterminated():
        body = (
            "# PR\n\n"
            "<pre>\n"
            "example never closed\n\n"
            "<!-- superheroes:dod-table -->\n"
            "| DoD | Status | Evidence |\n"
            "|---|---|---|\n"
            "| Ship it | done | tests pass |\n"
        )
        session = _session(tmp_path, body=body, name="case-body-context-unterminated")
        return _invoke("stage", session)

    cases["body-context-unterminated"] = case_body_context_unterminated

    def case_attest_duplicate_claim_verdict():
        session, manifest = _staged_for_attest("case-attest-duplicate-claim-verdict")
        repo_claim = next(
            c for c in manifest["claims"] if c.get("verifiability") == GS.VERIFIABILITY_REPO
        )

        def mutate(rows):
            rows.append({
                "id": repo_claim["claimId"],
                "verdict": "REFUTED",
                "reason": "duplicate probe",
            })

        path = _write_attest_result(session, manifest, mutate=mutate)
        return _invoke("attest", session, result_path=path)

    cases["attest-duplicate-claim-verdict"] = case_attest_duplicate_claim_verdict

    def case_attest_verdict_reason_missing():
        session, manifest = _staged_for_attest("case-attest-verdict-reason-missing")

        def mutate(rows):
            for row in rows:
                if not row["id"].startswith("stage-token:"):
                    row.pop("reason", None)

        path = _write_attest_result(session, manifest, mutate=mutate)
        return _invoke("attest", session, result_path=path)

    cases["attest-verdict-reason-missing"] = case_attest_verdict_reason_missing

    def case_invalid_invocation():
        session = _session(tmp_path, body=_happy_body(), name="case-invalid-invocation")
        argv = ["grounding_stage.py", "nope", "--session-dir", session]
        out = io.StringIO()
        old = sys.stdout
        sys.stdout = out
        try:
            rc = GS.main(argv)
        finally:
            sys.stdout = old
        lines = [ln for ln in out.getvalue().strip().splitlines() if ln.strip()]
        body = json.loads(lines[-1]) if lines else {}
        return rc, body

    cases["invalid-invocation"] = case_invalid_invocation

    def case_internal_error():
        session = _session(tmp_path, body=_happy_body(), name="case-internal-error")

        def boom(*_args, **_kwargs):
            raise RuntimeError("probe")

        with patch.object(GS, "_detect_regions", boom):
            return _invoke("stage", session)

    cases["internal-error"] = case_internal_error

    missing_cases = GS.REFUSAL_REASONS - set(cases)
    extra_cases = set(cases) - GS.REFUSAL_REASONS
    assert not missing_cases, "registered tokens with no case: %s" % sorted(missing_cases)
    assert not extra_cases, "cases for unregistered tokens: %s" % sorted(extra_cases)

    for token, run_case in cases.items():
        rc, body = run_case()
        assert rc == 1, "token %r: expected exit 1, got %r" % (token, rc)
        assert body.get("ok") is False, "token %r: ok not false" % token
        assert body.get("signal") == "cannot-certify", "token %r: signal mismatch" % token
        assert body.get("reason") == token, "token %r: reason was %r" % (token, body.get("reason"))


def _stage_then_mutate_manifest(tmp_path, mutate):
    session = _session(tmp_path, body=_happy_body(), name="mutate-session")
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest_path = os.path.join(session, "grounding", "stage.json")
    manifest = json.loads(open(manifest_path, encoding="utf-8").read())
    mutate(manifest)
    open(manifest_path, "w", encoding="utf-8").write(json.dumps(manifest))
    return session


def _manifest_shape_mutations():
    """Every manifest field / nested member shape that must refuse check."""
    cases = []

    def add(case_id, mutate, reason="stage-manifest-invalid"):
        cases.append(pytest.param(case_id, mutate, reason, id=case_id))

    add("schema-wrong", lambda m: m.update({"schema": "wrong/0"}))
    add("schema-missing", lambda m: m.pop("schema", None))
    add("stageToken-missing", lambda m: m.pop("stageToken", None))
    add("stageToken-empty", lambda m: m.update({"stageToken": "   "}))
    add("stageToken-non-string", lambda m: m.update({"stageToken": 123}))
    add("files-empty", lambda m: m.update({"files": []}))
    add("files-two-entries", lambda m: m.update({"files": m["files"] * 2}))
    add("files-non-list", lambda m: m.update({"files": {}}))
    add("files-entry-non-object", lambda m: m.update({"files": ["x"]}))
    add("files-name-wrong", lambda m: m["files"][0].update({"name": "other.md"}))
    add("files-sha256-missing", lambda m: m["files"][0].pop("sha256", None))
    add("files-sha256-empty", lambda m: m["files"][0].update({"sha256": ""}))
    add("files-bytes-non-int", lambda m: m["files"][0].update({"bytes": "1"}))
    add("files-bytes-bool", lambda m: m["files"][0].update({"bytes": True}))
    add("files-path-missing", lambda m: m["files"][0].pop("path", None))
    add("files-path-outside-grounding", lambda m: m["files"][0].update(
        {"path": "/tmp/outside-pr-body.md"}))
    add("regions-non-list", lambda m: m.update({"regions": {}}))
    add("regions-count-wrong", lambda m: m.update({"regions": m["regions"][:2]}))
    add("regions-extra", lambda m: m.update({
        "regions": m["regions"] + [{"name": "extra", "present": False, "lines": None}],
    }))
    add("region-name-unknown", lambda m: m["regions"][0].update({"name": "not-a-region"}))
    add("region-name-missing", lambda m: m["regions"][0].pop("name", None))
    add("region-present-non-bool", lambda m: m["regions"][0].update({"present": "yes"}))
    add("region-present-missing", lambda m: m["regions"][0].pop("present", None))
    add("region-member-non-object", lambda m: m.update({"regions": ["x"] + m["regions"][1:]}))
    add("claims-empty", lambda m: m.update({"claims": []}))
    add("claims-non-list", lambda m: m.update({"claims": {}}))
    add("claim-non-object", lambda m: m.update({"claims": [{"verifiability": "repo"}]}))
    add("claim-missing-claimId", lambda m: m["claims"].append({"kind": "dod-row", "text": "x", "verifiability": "repo"}))
    add("claim-empty-claimId", lambda m: m["claims"].append(
        {"claimId": "  ", "kind": "dod-row", "text": "x", "verifiability": "repo"}))
    add("claim-missing-kind", lambda m: m["claims"].append(
        {"claimId": "x-abc", "text": "x", "verifiability": "repo"}))
    add("claim-unknown-kind", lambda m: m["claims"].append(
        {"claimId": "x-abc", "kind": "bogus", "text": "x", "verifiability": "repo"}))
    add("claim-missing-text", lambda m: m["claims"].append(
        {"claimId": "x-abc", "kind": "dod-row", "verifiability": "repo"}))
    add("claim-text-non-string", lambda m: m["claims"].append(
        {"claimId": "x-abc", "kind": "dod-row", "text": 1, "verifiability": "repo"}))
    add("claim-missing-verifiability", lambda m: m["claims"].append(
        {"claimId": "x-abc", "kind": "dod-row", "text": "x"}))
    add("claim-unknown-verifiability", lambda m: m["claims"].append(
        {"claimId": "x-abc", "kind": "dod-row", "text": "x", "verifiability": "bogus"}))
    add("sourceBodySha256-missing", lambda m: m.pop("sourceBodySha256", None))
    add("sourceBodySha256-empty", lambda m: m.update({"sourceBodySha256": ""}))

    def defect_b1_minimal_claim():
        m = {"claims": [{"verifiability": "repo"}]}
        return m

    add("defect-B1-minimal-claim", lambda m: m.update(defect_b1_minimal_claim()))

    def defect_b2_stage_token_mismatch(session):
        manifest_path = os.path.join(session, "grounding", "stage.json")
        manifest = json.loads(open(manifest_path, encoding="utf-8").read())
        manifest["stageToken"] = "9999-9999-9999-9999"
        open(manifest_path, "w", encoding="utf-8").write(json.dumps(manifest))

    def defect_b4_flag_mismatch(session):
        manifest_path = os.path.join(session, "grounding", "stage.json")
        manifest = json.loads(open(manifest_path, encoding="utf-8").read())
        manifest["noSubstantiveClaims"] = True
        open(manifest_path, "w", encoding="utf-8").write(json.dumps(manifest))

    cases.append(pytest.param(
        "defect-B2-stage-token-mismatch",
        None,
        "staged-stage-token-mismatch",
        id="defect-B2-stage-token-mismatch",
        marks=pytest.mark.special_b2,
    ))
    cases.append(pytest.param(
        "defect-B4-flag-mismatch",
        None,
        "manifest-flag-mismatch",
        id="defect-B4-flag-mismatch",
        marks=pytest.mark.special_b4,
    ))
    return cases, defect_b2_stage_token_mismatch, defect_b4_flag_mismatch


_MANIFEST_MUTATIONS, _DEFECT_B2, _DEFECT_B4 = _manifest_shape_mutations()


@pytest.mark.parametrize("case_id,mutate,reason", _MANIFEST_MUTATIONS)
def test_manifest_shape_mutations_refuse(tmp_path, case_id, mutate, reason, request):
    if request.node.get_closest_marker("special_b2"):
        session = _session(tmp_path, body=_happy_body(), name="b2-session")
        rc, _ = _invoke("stage", session)
        assert rc == 0
        _DEFECT_B2(session)
    elif request.node.get_closest_marker("special_b4"):
        session = _session(tmp_path, body=_happy_body(), name="b4-session")
        rc, _ = _invoke("stage", session)
        assert rc == 0
        _DEFECT_B4(session)
    else:
        session = _stage_then_mutate_manifest(tmp_path, mutate)
    rc, body = _invoke("check", session)
    _assert_refusal(rc, body, reason)


def test_malformed_claim_member_refuses_not_filtered(tmp_path):
    session = _stage_then_mutate_manifest(
        tmp_path,
        lambda m: m.update({"claims": m["claims"] + [{"verifiability": "repo"}]}),
    )
    rc, body = _invoke("check", session)
    _assert_refusal(rc, body, "stage-manifest-invalid")
    assert body.get("claims") is None


def test_stage_check_round_trip_full_envelope(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, stage_body = _invoke("stage", session)
    assert rc == 0
    manifest = _manifest(session)
    rc2, check_body = _invoke("check", session)
    assert rc2 == 0
    assert check_body["ok"] is True
    assert check_body["applicable"] is True
    assert check_body["claims"] == _projected_claims(manifest)
    assert all("text" not in c for c in check_body["claims"])
    assert check_body["files"] == manifest["files"]
    assert check_body.get("noSubstantiveClaims") is not True
    assert len(manifest["claims"]) >= 1


def test_stage_check_round_trip_no_substantive_claims(tmp_path):
    body = (
        "## Summary\n"
        "<!-- superheroes:dod-table -->\n"
        "No DoD rows in this region.\n\n"
        "<!-- superheroes:build-record -->\n"
        "<details><summary>Build record</summary></details>\n\n"
        "<!-- superheroes:degradations -->\n"
        "### Disclosed degradations\n\n"
        "<!-- superheroes:advisor-vet -->\n"
    )
    session = _session(tmp_path, body=body)
    rc, stage_body = _invoke("stage", session)
    assert rc == 0
    assert stage_body.get("noSubstantiveClaims") is True
    rc2, check_body = _invoke("check", session)
    assert rc2 == 0
    assert check_body.get("noSubstantiveClaims") is True
    assert not any(
        c.get("kind") in ("dod-row", "degradation", "stub-marker")
        for c in check_body["claims"]
    )


def _dod_table_body(row_count):
    header = (
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
    )
    rows = "\n".join(
        "| row %d | done | tests/test_%d.py |" % (i, i) for i in range(row_count)
    )
    return header + rows + "\n"


def test_c1_claim_count_exceeded_refuses(tmp_path):
    over = GS.CLAIM_COUNT_MAX - 4 + 1
    session = _session(tmp_path, body=_dod_table_body(over))
    rc, body = _invoke("stage", session)
    _assert_refusal(rc, body, "pr-body-claim-count-exceeded")


def test_c1_claim_count_at_limit_accepted(tmp_path):
    rows = GS.CLAIM_COUNT_MAX - 4
    session = _session(tmp_path, body=_dod_table_body(rows))
    rc, body = _invoke("stage", session)
    assert rc == 0 and body["ok"]
    manifest = _manifest(session)
    assert len(manifest["claims"]) == GS.CLAIM_COUNT_MAX


def test_c1_body_exactly_max_bytes_accepted(tmp_path):
    marker = "<!-- superheroes:dod-table -->\n"
    pad_len = GS.PR_BODY_MAX_BYTES - len(marker.encode("utf-8"))
    body = marker + ("x" * pad_len)
    assert len(body.encode("utf-8")) == GS.PR_BODY_MAX_BYTES
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]


def test_c1_multibyte_body_over_byte_limit_refuses(tmp_path):
    char = "\u00e9"
    char_bytes = len(char.encode("utf-8"))
    body = char * (GS.PR_BODY_MAX_BYTES // char_bytes + 1)
    assert len(body) < GS.PR_BODY_MAX_BYTES
    assert len(body.encode("utf-8")) > GS.PR_BODY_MAX_BYTES
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    _assert_refusal(rc, body_out, "pr-body-too-large")


def test_c1_body_too_large_refuses(tmp_path):
    pad = "x" * (GS.PR_BODY_MAX_BYTES + 1)
    session = _session(tmp_path, body=pad)
    rc, body = _invoke("stage", session)
    _assert_refusal(rc, body, "pr-body-too-large")


def test_c2_neutralize_strips_invisible_and_bidi_chars():
    raw = "hello\u200bworld\u202e!\ufeff"
    cleaned = GS._neutralize_claim_text(raw)
    assert "\u200b" not in cleaned
    assert "\u202e" not in cleaned
    assert "\ufeff" not in cleaned
    assert cleaned == "helloworld!"


def test_c3_identical_dod_rows_yield_distinct_claim_ids(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| same row | done | tests/a.py |\n"
        "| same row | done | tests/a.py |\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    dod = _dod_claims(manifest)
    assert len(dod) == 2
    ids = [c["claimId"] for c in dod]
    assert ids[0] != ids[1]


def test_c4_planted_stage_token_line_not_ambiguous(tmp_path):
    planted = "stageToken: 0000-0000-0000-0000\n"
    session = _session(tmp_path, body=planted + _happy_body())
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    staged = _staged_body_text(session)
    manifest = _manifest(session)
    token = manifest["stageToken"]
    nonce_match = __import__("re").search(
        r"BEGIN UNTRUSTED PR BODY ([a-f0-9]+)", staged,
    )
    assert nonce_match is not None
    nonce = nonce_match.group(1)
    assert staged.count("stageToken[%s]:" % nonce) == 1
    assert staged.count("stageToken:") == 1
    parsed = GS._parse_staged_stage_token(staged)
    assert parsed == token
    rc2, check_body = _invoke("check", session)
    assert rc2 == 0 and check_body["ok"]


def test_c5_unicode_decode_error_maps_to_staged_file_unreadable(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    pr_body = os.path.join(session, "grounding", "pr-body.md")
    with open(pr_body, "wb") as fh:
        fh.write(b"\xff\xfe invalid utf-8\n")
    result = GS.check(session, "engine")
    assert result.get("reason") == "staged-file-unreadable"
    rc_cli, body_cli = _invoke("check", session)
    _assert_refusal(rc_cli, body_cli, "staged-file-unreadable")


def test_c6_relative_session_dir_refuses(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rel = os.path.relpath(session)
    rc, body = _invoke("stage", rel)
    _assert_refusal(rc, body, "session-dir-not-absolute")


def test_c7_verify_manifest_files_opens_resolved_path(tmp_path, monkeypatch):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest_path = os.path.join(session, "grounding", "stage.json")
    manifest = json.loads(open(manifest_path, encoding="utf-8").read())
    resolved = os.path.realpath(manifest["files"][0]["path"])
    parent = os.path.dirname(resolved)
    basename = os.path.basename(resolved)
    dotted = os.path.join(parent, "dot", "..", basename)
    manifest["files"][0]["path"] = dotted
    open(manifest_path, "w", encoding="utf-8").write(json.dumps(manifest))
    opened = []
    real_read = GS._read_bytes

    def track_read(path):
        opened.append(path)
        return real_read(path)

    monkeypatch.setattr(GS, "_read_bytes", track_read)
    rc, body = _invoke("check", session)
    assert rc == 0 and body["ok"]
    pr_body_reads = [p for p in opened if p.endswith("pr-body.md")]
    assert pr_body_reads
    assert pr_body_reads[0] == resolved


def test_refuse_call_sites_use_registered_string_literals():
    """Detect unregistered or dynamically computed refusal tokens at _refuse call sites.

    Does not prove reachability — a _refuse call behind an impossible condition would
    still satisfy this detector. Reachability is test_every_registered_refusal_reason_is_observably_emitted."""
    # bite-axis: refusal literal census — _refuse first args must be registered string literals.
    module_path = os.path.join(_LIB, "grounding_stage.py")
    with open(module_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=module_path)

    func_index = _function_index(tree)
    exempt = set()
    convert_fn = func_index.get("_convert_body_refusal")
    if convert_fn is not None:
        for node in ast.walk(convert_fn):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_refuse"
            ):
                exempt.add(node.lineno)

    non_literal = []
    unregistered = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Name) or func.id != "_refuse":
            continue
        if node.lineno in exempt:
            continue
        if not node.args:
            continue
        first = node.args[0]
        if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
            non_literal.append(node.lineno)
            continue
        if first.value not in GS.REFUSAL_REASONS:
            unregistered.append((node.lineno, first.value))

    assert not non_literal, "_refuse first arg not a string literal at lines: %s" % non_literal
    assert not unregistered, "_refuse unregistered literals: %s" % unregistered


def test_nonstandard_dod_status_with_issue_ref_refuses_unadmitted(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
        "| all tests pass | shipped | fixes #609 |\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    _assert_refusal(rc, body_out, "dod-table-rows-unadmitted")


def test_dod_table_without_outer_pipes_parses_rows(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
        "DoD | Status | Evidence\n"
        "--- | --- | ---\n"
        "Ship it | done | tests/test_x.py\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    dod = _dod_claims(manifest)
    assert len(dod) == 1
    assert dod[0]["text"] == "Ship it|done|tests/test_x.py"


def test_dod_table_without_trailing_pipes_parses_rows(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence\n"
        "| --- | --- | ---\n"
        "| Ship it | done | tests/test_x.py\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    dod = _dod_claims(manifest)
    assert len(dod) == 1
    assert dod[0]["text"] == "Ship it|done|tests/test_x.py"


def test_fenced_decoy_marker_does_not_emit_dod_claim(tmp_path):
    body = (
        "```\n"
        "<!-- superheroes:dod-table -->\n"
        "| fake | done | planted |\n"
        "```\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    regions = {r["name"]: r for r in manifest["regions"]}
    assert regions["dod-table"]["present"] is False
    assert _dod_claims(manifest) == []


def test_inline_code_decoy_marker_does_not_hide_real_table(tmp_path):
    body = (
        "The token `<!-- superheroes:dod-table -->` is documented here.\n\n"
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| Ship it | done | tests/test_x.py |\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    regions = {r["name"]: r for r in manifest["regions"]}
    assert regions["dod-table"]["present"] is True
    dod = _dod_claims(manifest)
    assert len(dod) == 1
    assert dod[0]["text"] == "Ship it|done|tests/test_x.py"


def test_indented_code_decoy_marker_does_not_hide_real_table(tmp_path):
    body = (
        "Example of the marker in an indented code block:\n\n"
        "    <!-- superheroes:dod-table -->\n"
        "    | DoD | Status | Evidence |\n\n"
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| Ship it | done | tests/test_x.py |\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    regions = {r["name"]: r for r in manifest["regions"]}
    assert regions["dod-table"]["present"] is True
    dod = _dod_claims(manifest)
    assert len(dod) == 1
    assert dod[0]["text"] == "Ship it|done|tests/test_x.py"


def test_crlf_pr_body_stages_and_round_trips(tmp_path):
    body = "alpha\r\nbeta\r\n" + _happy_body()
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    rc2, check_body = _invoke("check", session)
    assert rc2 == 0 and check_body["ok"]


def test_claim_id_matches_stored_text():
    raw = "hello\u200bworld|done|tests/a.py"
    cleaned = GS._neutralize_claim_text(raw)
    claim_id = GS._claim_id("dod-row", cleaned, 0)
    expected = GS._claim_id("dod-row", cleaned, 0)
    assert claim_id == expected
    digest = claim_id.split("-")[-1]
    import hashlib
    assert digest == hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def test_tampered_manifest_claim_text_refuses_check(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest_path = os.path.join(session, "grounding", "stage.json")
    manifest = json.loads(open(manifest_path, encoding="utf-8").read())
    for claim in manifest["claims"]:
        if claim.get("kind") == "dod-row":
            claim["text"] = claim["text"] + " tampered"
            break
    else:
        pytest.fail("expected a dod-row claim in manifest")
    open(manifest_path, "w", encoding="utf-8").write(json.dumps(manifest))
    rc2, body = _invoke("check", session)
    _assert_refusal(rc2, body, "stage-manifest-invalid")


def test_tampered_manifest_claim_refuses_check(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest_path = os.path.join(session, "grounding", "stage.json")
    manifest = json.loads(open(manifest_path, encoding="utf-8").read())
    for claim in manifest["claims"]:
        if claim.get("kind") == "dod-row" and claim.get("verifiability") == "external":
            claim["verifiability"] = "repo"
            break
    else:
        pytest.fail("expected a deferred dod-row claim in manifest")
    open(manifest_path, "w", encoding="utf-8").write(json.dumps(manifest))
    rc2, body = _invoke("check", session)
    _assert_refusal(rc2, body, "stage-manifest-invalid")


def _marker_body(case_id, marker):
    """Build a PR body placing ``marker`` in the census context named by ``case_id``."""
    if case_id == "column_0":
        return marker + "\n"
    if case_id == "indent_1":
        return " " + marker + "\n"
    if case_id == "indent_2":
        return "  " + marker + "\n"
    if case_id == "indent_3":
        return "   " + marker + "\n"
    if case_id == "indent_4":
        return "    " + marker + "\n"
    if case_id == "inside_fence":
        return "```\n" + marker + "\n```\n"
    if case_id == "inside_pre":
        return "<pre>\n" + marker + "\n</pre>\n"
    if case_id == "inside_details":
        return "<details>\n" + marker + "\n</details>\n"
    if case_id == "blockquote":
        return "> " + marker + "\n"
    if case_id == "list_item":
        return "- " + marker + "\n"
    if case_id == "trailing_whitespace":
        return marker + "   \n"
    if case_id == "other_text_on_line":
        return marker + " extra\n"
    raise ValueError("unknown marker census case: %r" % case_id)


_MARKER_CENSUS_CASES = [
    pytest.param("column_0", True, id="column_0"),
    pytest.param("indent_1", False, id="indent_1"),
    pytest.param("indent_2", False, id="indent_2"),
    pytest.param("indent_3", False, id="indent_3"),
    pytest.param("indent_4", False, id="indent_4"),
    pytest.param("inside_fence", False, id="inside_fence"),
    pytest.param("inside_pre", False, id="inside_pre"),
    pytest.param("inside_details", True, id="inside_details"),
    pytest.param("blockquote", False, id="blockquote"),
    pytest.param("list_item", False, id="list_item"),
    pytest.param("trailing_whitespace", True, id="trailing_whitespace"),
    pytest.param("other_text_on_line", False, id="other_text_on_line"),
]


@pytest.mark.parametrize("region_name", sorted(GS.REGION_MARKERS))
@pytest.mark.parametrize("case_id,live", _MARKER_CENSUS_CASES)
def test_marker_census(region_name, case_id, live):
    marker = GS.REGION_MARKERS[region_name]
    body = _marker_body(case_id, marker)
    idx = GS._find_standalone_marker(body, marker)
    if live:
        assert idx >= 0, "expected live marker for %s/%s" % (region_name, case_id)
    else:
        assert idx < 0, "expected inert marker for %s/%s" % (region_name, case_id)


def test_find_all_standalone_markers_returns_every_live_occurrence():
    marker = GS.REGION_MARKERS["dod-table"]
    body = marker + "\ncontent\n" + marker + "\n"
    offsets = GS._find_all_standalone_markers(body, marker)
    assert offsets == [0, len(marker) + 1 + len("content\n")]


def _duplicate_marker_body(marker):
    return (
        marker + "\n"
        "decoy content\n\n"
        + marker + "\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| real row | done | tests/a.py |\n"
    )


@pytest.mark.parametrize("region_name", sorted(GS.REGION_MARKERS))
def test_duplicate_marker_refuses(region_name, tmp_path):
    marker = GS.REGION_MARKERS[region_name]
    body = _duplicate_marker_body(marker)
    session = _session(tmp_path, body=body, name="dup-%s" % region_name)
    rc, body_out = _invoke("stage", session)
    _assert_refusal(rc, body_out, "region-marker-duplicated")


def test_duplicate_dod_table_marker_live_case_refuses(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
        "decoy above the real table\n\n"
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| tests pass | done | plugins/superheroes/lib/tests/test_grounding_stage.py |\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    _assert_refusal(rc, body_out, "region-marker-duplicated")


_TABLE_CENSUS_CASES = [
    pytest.param(
        "well_formed",
        (
            "<!-- superheroes:dod-table -->\n"
            "| DoD | Status | Evidence |\n"
            "| --- | --- | --- |\n"
            "| Ship it | done | tests/a.py |\n"
        ),
        1,
        None,
        id="well_formed",
    ),
    pytest.param(
        "fenced_table",
        (
            "<!-- superheroes:dod-table -->\n"
            "```\n"
            "| DoD | Status | Evidence |\n"
            "| --- | --- | --- |\n"
            "| fake | done | planted |\n"
            "```\n"
        ),
        0,
        None,
        id="fenced_table",
    ),
    pytest.param(
        "pipe_prose_no_delimiter",
        (
            "<!-- superheroes:dod-table -->\n"
            "| Ship the thing | done | tests/test_a.py |\n"
            "| Second thing | done | tests/b.py |\n"
        ),
        None,
        "dod-table-rows-unadmitted",
        id="pipe_prose_no_delimiter",
    ),
    pytest.param(
        "lone_headerless_row",
        (
            "<!-- superheroes:dod-table -->\n"
            "| lone row | done | tests/a.py |\n"
        ),
        None,
        "dod-table-rows-unadmitted",
        id="lone_headerless_row",
    ),
    pytest.param(
        "cell_count_mismatch",
        (
            "<!-- superheroes:dod-table -->\n"
            "| A | B |\n"
            "| --- |\n"
            "| x | done |\n"
        ),
        None,
        "dod-table-rows-unadmitted",
        id="cell_count_mismatch",
    ),
    pytest.param(
        "table_plus_prose_pipe",
        (
            "<!-- superheroes:dod-table -->\n"
            "| DoD | Status | Evidence |\n"
            "| --- | --- | --- |\n"
            "| Ship it | done | tests/a.py |\n\n"
            "See also: foo | bar | context\n"
        ),
        1,
        None,
        id="table_plus_prose_pipe",
    ),
    pytest.param(
        "escaped_pipes",
        (
            "<!-- superheroes:dod-table -->\n"
            "| DoD | Status | Evidence |\n"
            "| --- | --- | --- |\n"
            "| path \\| pipe | done | tests/a.py |\n"
        ),
        1,
        None,
        id="escaped_pipes",
    ),
]


@pytest.mark.parametrize(
    "case_id,body,expected_rows,refusal_reason",
    _TABLE_CENSUS_CASES,
)
def test_table_census(case_id, body, expected_rows, refusal_reason, tmp_path):
    session = _session(tmp_path, body=body, name="table-%s" % case_id)
    rc, body_out = _invoke("stage", session)
    if refusal_reason:
        _assert_refusal(rc, body_out, refusal_reason)
        return
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    dod = _dod_claims(manifest)
    assert len(dod) == expected_rows


def test_region_boundary_fenced_heading_does_not_truncate(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
        "```\n"
        "## sample\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| fake | done | planted |\n"
        "```\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| real row | done | tests/a.py |\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    dod = _dod_claims(manifest)
    assert len(dod) == 1
    assert dod[0]["text"] == "real row|done|tests/a.py"


def test_region_boundary_live_heading_truncates(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| first row | done | tests/a.py |\n"
        "## Next\n"
        "| later | done | tests/b.py |\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    dod = _dod_claims(manifest)
    assert len(dod) == 1
    assert dod[0]["text"] == "first row|done|tests/a.py"


def test_fenced_bullet_not_minted_as_degradation(tmp_path):
    body = (
        "<!-- superheroes:degradations -->\n"
        "### Disclosed degradations\n"
        "- real degradation\n"
        "```\n"
        "- fenced fake degradation\n"
        "```\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    deg = _degradation_claims(manifest)
    assert [c["text"] for c in deg] == ["real degradation"]


def test_body_refusal_surfaces_own_token_not_internal_error(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    with patch.object(
        GS,
        "_parse_dod_rows",
        side_effect=GS._BodyRefusal("dod-table-rows-unadmitted", "probe"),
    ):
        rc, body_out = _invoke("stage", session)
    _assert_refusal(rc, body_out, "dod-table-rows-unadmitted")
    assert body_out.get("reason") != "internal-error"


def _grounding_stage_ast():
    module_path = os.path.join(_LIB, "grounding_stage.py")
    with open(module_path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=module_path)


def _function_index(tree):
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def _calls_function(node, name):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Name) and func.id == name:
                return True
    return False


def _callable_names(node):
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Name):
                names.add(func.id)
    return names


def _callers_of(tree, target):
    func_index = _function_index(tree)
    callers = set()
    for name, node in func_index.items():
        if target in _callable_names(node):
            callers.add(name)
    return callers


def _discover_staging_access(tree):
    manifest_ops = {
        "_load_manifest",
        "_verify_manifest_files",
        "_validate_manifest_shape",
        "_bind_three_way_source",
    }
    func_index = _function_index(tree)
    access = set(manifest_ops)
    exempt = {"check", "attest", "main", "stage", "_trust_boundary"}
    changed = True
    while changed:
        changed = False
        for name, node in func_index.items():
            if name in access or name in exempt:
                continue
            if _callable_names(node) & access:
                access.add(name)
                changed = True
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and sub.id in ("STAGE_MANIFEST", "PR_BODY_STAGED"):
                    access.add(name)
                    changed = True
                    break
    return access


def _refresh_manifest_file_entry(session):
    import hashlib
    pr_body_path = os.path.join(session, "grounding", "pr-body.md")
    manifest_path = os.path.join(session, "grounding", "stage.json")
    on_disk = open(pr_body_path, "rb").read()
    manifest = json.loads(open(manifest_path, encoding="utf-8").read())
    manifest["files"][0]["sha256"] = hashlib.sha256(on_disk).hexdigest()
    manifest["files"][0]["bytes"] = len(on_disk)
    open(manifest_path, "w", encoding="utf-8").write(json.dumps(manifest))


def _tamper_staged_body_preserve_source_sha(session, tamper):
    import hashlib
    pr_body_path = os.path.join(session, "grounding", "pr-body.md")
    manifest_path = os.path.join(session, "grounding", "stage.json")
    manifest = json.loads(open(manifest_path, encoding="utf-8").read())
    original_sha = manifest["sourceBodySha256"]
    staged = open(pr_body_path, encoding="utf-8").read()
    raw = GS._extract_untrusted_pr_body(staged)
    canonical = GS._canonical_staged_body_for_sha(raw)
    tampered = tamper(canonical)
    nonce = GS._parse_fence_nonce(staged)
    token = GS._parse_staged_stage_token(staged)
    open(pr_body_path, "w", encoding="utf-8").write(
        GS._staged_pr_body(token, tampered, nonce),
    )
    scan = GS._context_scan(tampered)
    regions = GS._detect_regions(tampered, scan)
    region_map = {r["name"]: r for r in regions}
    claims = GS._enumerate_claims(tampered, region_map, scan)
    on_disk = open(pr_body_path, "rb").read()
    manifest["files"][0]["sha256"] = hashlib.sha256(on_disk).hexdigest()
    manifest["files"][0]["bytes"] = len(on_disk)
    manifest["regions"] = regions
    manifest["claims"] = claims
    manifest["sourceBodySha256"] = original_sha
    open(manifest_path, "w", encoding="utf-8").write(
        json.dumps(manifest, sort_keys=True) + "\n",
    )


def _reachable_functions(tree, root):
    func_index = _function_index(tree)
    seen = set()
    stack = [root]
    while stack:
        fn = stack.pop()
        if fn in seen or fn not in func_index:
            continue
        seen.add(fn)
        for callee in _callable_names(func_index[fn]):
            if callee in func_index:
                stack.append(callee)
    return seen


def test_trust_boundary_chokepoint_census():
    # bite-axis: chokepoint census — manifest load/validate must be reachable only from _trust_boundary.
    tree = _grounding_stage_ast()
    access = _discover_staging_access(tree)
    assert access, "staging-access set must not be empty"
    trusted = _reachable_functions(tree, "_trust_boundary")
    orphan_access = sorted(access - trusted)
    assert orphan_access == [], "staging-access outside _trust_boundary reachability: %s" % orphan_access
    violations = {}
    for fn in sorted(access):
        callers = _callers_of(tree, fn) - {fn}
        bad = sorted(callers - trusted)
        if bad:
            violations[fn] = bad
    assert violations == {}, "staging-access with callers outside _trust_boundary: %s" % violations

    validated_sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "_Validated":
                validated_sites.append(node.lineno)
    assert len(validated_sites) == 1, "_Validated must be constructed at exactly one site: %s" % validated_sites


def test_check_and_attest_require_validated_instance(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest = _manifest(session)
    result_path = os.path.join(session, "grounding", "attest-result.json")
    rows = [{
        "id": "stage-token:%s" % manifest["stageToken"],
        "verdict": "CONFIRMED",
        "reason": "read stage token from staged body",
    }]
    for claim in manifest["claims"]:
        if claim.get("verifiability") == GS.VERIFIABILITY_REPO:
            rows.append({
                "id": claim["claimId"],
                "verdict": "CONFIRMED",
                "reason": "verified in repository",
            })
    open(result_path, "w", encoding="utf-8").write(json.dumps({"verdicts": rows}))

    with patch.object(GS, "_trust_boundary", return_value={"ok": True, "applicable": True}):
        check_out = GS.check(session, "engine")
        assert check_out.get("reason") == "internal-error"
        attest_out = GS.attest(session, result_path, "engine")
        assert attest_out.get("reason") == "internal-error"


def test_attest_happy_path(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest = _manifest(session)
    result_path = os.path.join(session, "grounding", "attest-result.json")
    rows = [{
        "id": "stage-token:%s" % manifest["stageToken"],
        "verdict": "CONFIRMED",
        "reason": "read stage token from staged body",
    }]
    repo_ids = []
    for claim in manifest["claims"]:
        if claim.get("verifiability") == GS.VERIFIABILITY_REPO:
            rows.append({
                "id": claim["claimId"],
                "verdict": "CONFIRMED",
                "reason": "verified in repository",
            })
            repo_ids.append(claim["claimId"])
    open(result_path, "w", encoding="utf-8").write(json.dumps({"verdicts": rows}))
    rc2, body = _invoke("attest", session, result_path=result_path)
    assert rc2 == 0
    assert body["ok"] is True
    assert body["attested"] is True
    assert body["confirmed"] == sorted(repo_ids)


def test_attest_duplicate_row_id_refuses(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest = _manifest(session)
    repo_claim = next(
        c for c in manifest["claims"] if c.get("verifiability") == GS.VERIFIABILITY_REPO
    )
    result_path = os.path.join(session, "grounding", "attest-result.json")
    rows = [
        {
            "id": "stage-token:%s" % manifest["stageToken"],
            "verdict": "CONFIRMED",
            "reason": "read stage token from staged body",
        },
        {
            "id": repo_claim["claimId"],
            "verdict": "REFUTED",
            "reason": "first verdict",
        },
        {
            "id": repo_claim["claimId"],
            "verdict": "CONFIRMED",
            "reason": "conflicting second verdict",
        },
    ]
    for claim in manifest["claims"]:
        if claim.get("verifiability") == GS.VERIFIABILITY_REPO and claim is not repo_claim:
            rows.append({
                "id": claim["claimId"],
                "verdict": "CONFIRMED",
                "reason": "verified in repository",
            })
    open(result_path, "w", encoding="utf-8").write(json.dumps({"verdicts": rows}))
    rc2, body = _invoke("attest", session, result_path=result_path)
    _assert_refusal(rc2, body, "attest-duplicate-claim-verdict")


def test_attest_verdict_reason_missing_refuses(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest = _manifest(session)
    result_path = os.path.join(session, "grounding", "attest-result.json")
    rows = [{
        "id": "stage-token:%s" % manifest["stageToken"],
        "verdict": "CONFIRMED",
        "reason": "read stage token from staged body",
    }]
    for claim in manifest["claims"]:
        if claim.get("verifiability") == GS.VERIFIABILITY_REPO:
            rows.append({"id": claim["claimId"], "verdict": "CONFIRMED"})
    open(result_path, "w", encoding="utf-8").write(json.dumps({"verdicts": rows}))
    rc2, body = _invoke("attest", session, result_path=result_path)
    _assert_refusal(rc2, body, "attest-verdict-reason-missing")


def test_body_context_unterminated_html_refuses(tmp_path):
    body = (
        "# PR\n\n"
        "<pre>\n"
        "example never closed\n\n"
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "|---|---|---|\n"
        "| Ship it | done | tests pass |\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    _assert_refusal(rc, body_out, "body-context-unterminated")


def test_body_context_unterminated_fence_refuses(tmp_path):
    body = (
        "# PR\n\n"
        "```\n"
        "unclosed fence\n\n"
        "<!-- superheroes:dod-table -->\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| Ship it | done | tests pass |\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    _assert_refusal(rc, body_out, "body-context-unterminated")


def test_convert_body_refusal_unregistered_raises():
    with pytest.raises(ValueError, match="unregistered refusal reason"):
        GS._convert_body_refusal(GS._BodyRefusal("not-a-real-reason", "probe"))


def test_dod_empty_table_accepted(tmp_path):
    body = (
        "# PR\n"
        "<!-- superheroes:dod-table -->\n\n"
        "| DoD | Status | Evidence |\n"
        "|---|---|---|\n\n"
        "<!-- superheroes:build-record -->\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    assert _dod_claims(manifest) == []


def test_region_start_line_aligns_with_region_text(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
        "\n"
        "\n"
        "```\n"
        "| fake | done | planted |\n"
        "```\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| real row | done | tests/a.py |\n"
    )
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest = _manifest(session)
    dod = _dod_claims(manifest)
    assert len(dod) == 1
    assert dod[0]["text"] == "real row|done|tests/a.py"
    scan = GS._context_scan(body)
    region_text, _, region_start_line = GS._extract_region(
        body, GS.REGION_MARKERS["dod-table"], scan, "dod-table",
    )
    _, bare = GS._bare_lines_from_body(body)
    region_lines = region_text.splitlines()
    for i, line in enumerate(region_lines):
        assert bare[region_start_line + i] == line


def test_attest_opens_resolved_result_path(tmp_path, monkeypatch):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest = _manifest(session)
    result_path = os.path.join(session, "grounding", "attest-result.json")
    rows = [{
        "id": "stage-token:%s" % manifest["stageToken"],
        "verdict": "CONFIRMED",
        "reason": "read stage token from staged body",
    }]
    for claim in manifest["claims"]:
        if claim.get("verifiability") == GS.VERIFIABILITY_REPO:
            rows.append({
                "id": claim["claimId"],
                "verdict": "CONFIRMED",
                "reason": "verified in repository",
            })
    open(result_path, "w", encoding="utf-8").write(json.dumps({"verdicts": rows}))
    resolved = os.path.realpath(result_path)
    parent = os.path.dirname(resolved)
    basename = os.path.basename(resolved)
    dotted = os.path.join(parent, "dot", "..", basename)
    opened = []
    real_read_json = GS._read_json

    def track_read_json(path):
        opened.append(path)
        return real_read_json(path)

    monkeypatch.setattr(GS, "_read_json", track_read_json)
    rc2, body = _invoke("attest", session, result_path=dotted)
    assert rc2 == 0 and body["ok"]
    result_reads = [p for p in opened if p.endswith("attest-result.json")]
    assert result_reads
    assert result_reads[0] == resolved


def test_biteproof_staged_body_source_mismatch_guard(tmp_path):
    session = _session(tmp_path, body=_happy_body(), name="bite-staged-body")
    rc, _ = _invoke("stage", session)
    assert rc == 0
    _tamper_staged_body_preserve_source_sha(
        session,
        lambda body: body.replace("Ship grounding stage.", "Ship grounding stage!", 1),
    )
    rc2, body = _invoke("check", session)
    _assert_refusal(rc2, body, "staged-body-source-mismatch")


def test_biteproof_attest_pr_json_leg_guard(tmp_path):
    session = _session(tmp_path, body=_happy_body(), name="bite-pr-json-leg")
    rc, _ = _invoke("stage", session)
    assert rc == 0
    manifest = _manifest(session)
    pr_path = os.path.join(session, "pr.json")
    pr_data = json.loads(open(pr_path, encoding="utf-8").read())
    pr_data["body"] = pr_data["body"] + "\nEdited after staging."
    open(pr_path, "w", encoding="utf-8").write(json.dumps(pr_data))
    result_path = os.path.join(session, "grounding", "attest-result.json")
    rows = [{
        "id": "stage-token:%s" % manifest["stageToken"],
        "verdict": "CONFIRMED",
        "reason": "read stage token from staged body",
    }]
    for claim in manifest["claims"]:
        if claim.get("verifiability") == GS.VERIFIABILITY_REPO:
            rows.append({
                "id": claim["claimId"],
                "verdict": "CONFIRMED",
                "reason": "verified in repository",
            })
    open(result_path, "w", encoding="utf-8").write(json.dumps({"verdicts": rows}))
    rc2, body = _invoke("attest", session, result_path=result_path)
    _assert_refusal(rc2, body, "source-body-stale")


def test_biteproof_vendor_path_gate_guard(tmp_path):
    session = _session(tmp_path, body=_happy_body(), name="bite-vendor-path")
    rc, _ = _invoke("stage", session)
    assert rc == 0
    result = GS.check(session, "not-a-vendor")
    assert result.get("reason") == "stage-unreachable-for-vendor"


def test_biteproof_result_path_confinement_guard(tmp_path):
    session = _session(tmp_path, body=_happy_body(), name="bite-result-path")
    rc, _ = _invoke("stage", session)
    assert rc == 0
    outside = tmp_path / "outside-attest.json"
    outside.write_text('{"verdicts": []}', encoding="utf-8")
    rc2, body = _invoke("attest", session, result_path=str(outside))
    _assert_refusal(rc2, body, "attest-result-outside-session")


def test_biteproof_chokepoint_census_detects_bypass():
    # bite-axis: chokepoint census mutation proof — a direct manifest reader must fail the census.
    tree = _grounding_stage_ast()
    bypass = ast.FunctionDef(
        name="_biteproof_direct_manifest_reader",
        args=ast.arguments(
            posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[],
        ),
        body=[
            ast.Return(
                value=ast.Call(
                    func=ast.Name(id="_load_manifest", ctx=ast.Load()),
                    args=[ast.Constant(value="/tmp/session")],
                    keywords=[],
                ),
            ),
        ],
        decorator_list=[],
        returns=None,
        type_comment=None,
    )
    tree.body.append(bypass)
    access = _discover_staging_access(tree)
    reachable = _reachable_functions(tree, "_trust_boundary")
    assert "_biteproof_direct_manifest_reader" in access
    assert "_biteproof_direct_manifest_reader" not in reachable
