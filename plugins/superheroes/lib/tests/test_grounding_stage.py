import importlib.util
import io
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GS = _load("grounding_stage")
EA = _load("engine_adapter")

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
    "attest-result-unreadable",
    "attest-token-missing",
    "attest-token-mismatch",
    "attest-claim-unanswered",
    "attest-verdict-out-of-enum",
    "invalid-invocation",
    "stage-unreachable-for-vendor",
})


def _session(tmp_path, mode="pr", body=None, meta_extra=None):
    d = tmp_path / "session"
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


def _invoke(cmd, session_dir, result_path=None):
    argv = ["grounding_stage.py", cmd, "--session-dir", session_dir]
    if result_path is not None:
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


def test_edge_13_attest_result_unreadable(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    rc, body = _invoke("attest", session, str(tmp_path / "missing.json"))
    _assert_refusal(rc, body, "attest-result-unreadable")


def test_edge_14_attest_token_missing(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"verdicts": []}), encoding="utf-8")
    rc, body = _invoke("attest", session, str(result_path))
    _assert_refusal(rc, body, "attest-token-missing")


def test_edge_15_attest_token_mismatch(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({
        "verdicts": [{"id": "stage-token:0000-0000-0000-0000", "verdict": "CONFIRMED"}],
    }), encoding="utf-8")
    rc, body = _invoke("attest", session, str(result_path))
    _assert_refusal(rc, body, "attest-token-mismatch")


def test_edge_16_attest_claim_unanswered(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, staged = _invoke("stage", session)
    assert rc == 0
    token = _manifest_token(session)
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({
        "verdicts": [{"id": "stage-token:%s" % token, "verdict": "CONFIRMED", "reason": "read"}],
    }), encoding="utf-8")
    rc, body = _invoke("attest", session, str(result_path))
    _assert_refusal(rc, body, "attest-claim-unanswered")


def test_edge_17_attest_verdict_out_of_enum_on_claim(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, staged = _invoke("stage", session)
    assert rc == 0
    token = _manifest_token(session)
    claims = staged["claims"]
    repo_claims = [c for c in claims if c["verifiability"] == "repo"]
    verdicts = [{"id": "stage-token:%s" % token, "verdict": "CONFIRMED", "reason": "read"}]
    for claim in repo_claims:
        verdicts.append({"id": claim["claimId"], "verdict": "CONFIRMED", "reason": "ok"})
    verdicts[1]["verdict"] = "MAYBE"
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"verdicts": verdicts}), encoding="utf-8")
    rc, body = _invoke("attest", session, str(result_path))
    _assert_refusal(rc, body, "attest-verdict-out-of-enum")


def test_edge_17b_attest_verdict_out_of_enum_on_token_row(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, staged = _invoke("stage", session)
    assert rc == 0
    token = _manifest_token(session)
    repo_claims = [c for c in staged["claims"] if c["verifiability"] == "repo"]
    verdicts = [{"id": "stage-token:%s" % token, "verdict": "MAYBE", "reason": "read"}]
    for claim in repo_claims:
        verdicts.append({"id": claim["claimId"], "verdict": "CONFIRMED", "reason": "ok"})
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"verdicts": verdicts}), encoding="utf-8")
    rc, body = _invoke("attest", session, str(result_path))
    _assert_refusal(rc, body, "attest-verdict-out-of-enum")


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


def test_token_scrub_round_trip(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    token = _manifest_token(session)
    stdout = json.dumps({
        "verdicts": [{
            "id": "stage-token:%s" % token,
            "verdict": "CONFIRMED",
            "reason": "read token from staged body",
            "note": token,
        }],
    })
    parsed = EA.parse_result("codex", "review", stdout)
    assert parsed["ok"] is True
    row = parsed["verdicts"][0]
    assert row["id"] == "stage-token:%s" % token
    assert row["id"].split(":", 1)[1] == token


def test_token_row_without_reason_unreadable(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, _ = _invoke("stage", session)
    assert rc == 0
    token = _manifest_token(session)
    stdout = json.dumps({
        "verdicts": [{"id": "stage-token:%s" % token, "verdict": "CONFIRMED"}],
    })
    parsed = EA.parse_result("codex", "review", stdout)
    assert parsed["ok"] is False


def test_attest_happy_path(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, staged = _invoke("stage", session)
    assert rc == 0
    token = _manifest_token(session)
    repo_claims = [c for c in staged["claims"] if c["verifiability"] == "repo"]
    verdicts = [{"id": "stage-token:%s" % token, "verdict": "CONFIRMED", "reason": "read"}]
    refuted_id = repo_claims[0]["claimId"]
    plausible_id = None
    for claim in repo_claims:
        if claim["claimId"] == refuted_id:
            verdict = "REFUTED"
        elif plausible_id is None:
            plausible_id = claim["claimId"]
            verdict = "PLAUSIBLE"
        else:
            verdict = "CONFIRMED"
        verdicts.append({"id": claim["claimId"], "verdict": verdict, "reason": "checked"})
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"verdicts": verdicts}), encoding="utf-8")
    rc, body = _invoke("attest", session, str(result_path))
    assert rc == 0
    assert body["ok"] is True
    assert body["attested"] is True
    assert refuted_id in body["refuted"]
    assert plausible_id in body["plausible"]
    assert plausible_id not in body["confirmed"]
    assert refuted_id not in body["confirmed"]


def test_attest_no_substantive_claims_flag(tmp_path):
    body = "## Summary\nNo markers here.\n"
    session = _session(tmp_path, body=body)
    rc, _ = _invoke("stage", session)
    assert rc == 0
    token = _manifest_token(session)
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({
        "verdicts": [{"id": "stage-token:%s" % token, "verdict": "CONFIRMED", "reason": "read"}],
    }), encoding="utf-8")
    rc, body = _invoke("attest", session, str(result_path))
    assert rc == 0
    assert body.get("noSubstantiveClaims") is True
