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
    "stage-unwritable",
    "stage-readback-mismatch",
    "stage-manifest-missing",
    "stage-manifest-invalid",
    "staged-file-unreadable",
    "staged-file-hash-mismatch",
    "invalid-invocation",
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


def _invoke(cmd, session_dir):
    argv = ["grounding_stage.py", cmd, "--session-dir", session_dir]
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

    monkeypatch.setattr(GS.store_core, "atomic_write", boom)
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
    assert "Defer later|deferred|#609 reason" not in repo_texts


def test_dod_table_without_separator_mints_all_rows(tmp_path):
    body = (
        "<!-- superheroes:dod-table -->\n"
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
    assert texts == {
        "Ship the thing|done|tests/test_a.py",
        "Second thing|done|tests/b.py",
    }
    assert manifest.get("noSubstantiveClaims") is not True
    assert body_out.get("noSubstantiveClaims") is not True


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
    assert body_out.get("noSubstantiveClaims") is True
    manifest = _manifest(session)
    assert manifest.get("noSubstantiveClaims") is True
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

    def case_stage_unwritable():
        session = _session(tmp_path, body=_happy_body(), name="case-stage-unwritable")

        def boom(path, text, tmp_prefix=".grounding-stage-"):
            raise OSError("permission denied")

        with patch.object(GS.store_core, "atomic_write", boom):
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


def test_refuse_call_sites_use_registered_string_literals():
    """Detect unregistered or dynamically computed refusal tokens at _refuse call sites.

    Does not prove reachability — a _refuse call behind an impossible condition would
    still satisfy this detector. Reachability is test_every_registered_refusal_reason_is_observably_emitted."""
    module_path = os.path.join(_LIB, "grounding_stage.py")
    with open(module_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=module_path)

    non_literal = []
    unregistered = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Name) or func.id != "_refuse":
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
