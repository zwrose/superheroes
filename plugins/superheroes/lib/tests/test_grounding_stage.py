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
    real_verify = GS._verify_written_file

    def bad_verify(path, expected_text):
        if path.endswith("pr-body.md"):
            return GS._refuse("stage-readback-mismatch", "injected mismatch")
        return real_verify(path, expected_text)

    monkeypatch.setattr(GS, "_verify_written_file", bad_verify)
    rc, body = _invoke("stage", session)
    _assert_refusal(rc, body, "stage-readback-mismatch")


def test_edge_09_stage_manifest_missing(tmp_path):
    session = _session(tmp_path, mode="pr")
    (tmp_path / "session" / "meta.json").write_text(json.dumps({"mode": "pr"}), encoding="utf-8")
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


def test_edge_11_staged_file_unreadable(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, staged = _invoke("stage", session)
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
    rc, staged = _invoke("stage", session)
    assert rc == 0
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"verdicts": []}), encoding="utf-8")
    rc, body = _invoke("attest", session, str(result_path))
    _assert_refusal(rc, body, "attest-token-missing")


def test_edge_15_attest_token_mismatch(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, staged = _invoke("stage", session)
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
    token = staged["stageToken"]
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({
        "verdicts": [{"id": "stage-token:%s" % token, "verdict": "CONFIRMED"}],
    }), encoding="utf-8")
    rc, body = _invoke("attest", session, str(result_path))
    _assert_refusal(rc, body, "attest-claim-unanswered")


def test_edge_17_attest_verdict_out_of_enum(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, staged = _invoke("stage", session)
    assert rc == 0
    token = staged["stageToken"]
    claims = staged["claims"]
    repo_claims = [c for c in claims if c["verifiability"] == "repo"]
    verdicts = [{"id": "stage-token:%s" % token, "verdict": "CONFIRMED"}]
    for claim in repo_claims:
        verdicts.append({"id": claim["claimId"], "verdict": "CONFIRMED"})
    verdicts[1]["verdict"] = "MAYBE"
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
    manifest_path = os.path.join(session, "grounding", "stage.json")
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["schema"] == GS.STAGE_SCHEMA
    regions = {r["name"]: r for r in manifest["regions"]}
    assert regions["dod-table"]["present"] is True
    assert regions["build-record"]["present"] is True
    assert regions["degradations"]["present"] is True
    assert regions["advisor-vet"]["present"] is False
    claim_ids_first = [c["claimId"] for c in manifest["claims"]]
    rc2, body2 = _invoke("stage", session)
    assert rc2 == 0
    with open(manifest_path, encoding="utf-8") as fh:
        manifest2 = json.load(fh)
    claim_ids_second = [c["claimId"] for c in manifest2["claims"]]
    assert claim_ids_first == claim_ids_second
    kinds = {c["kind"] for c in manifest["claims"]}
    assert "region-present" in kinds
    assert "dod-row" in kinds
    assert "degradation" in kinds
    assert "stub-marker" in kinds


def test_stub_marker_claim_text_emitted_unchanged(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, body = _invoke("stage", session)
    assert rc == 0 and body["ok"]
    manifest_path = os.path.join(session, "grounding", "stage.json")
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    stub_claims = [c for c in manifest["claims"] if c["kind"] == "stub-marker"]
    assert len(stub_claims) == 1
    assert stub_claims[0]["text"] == "STUB(#123): unwired grounding dispatch"


def test_absent_regions_still_stage(tmp_path):
    body = "## Summary\nNo markers here.\n"
    session = _session(tmp_path, body=body)
    rc, body_out = _invoke("stage", session)
    assert rc == 0 and body_out["ok"]
    manifest_path = os.path.join(session, "grounding", "stage.json")
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    regions = {r["name"]: r for r in manifest["regions"]}
    assert regions["dod-table"]["present"] is False
    assert regions["degradations"]["present"] is False
    region_claims = [c for c in manifest["claims"] if c["kind"] == "region-present"]
    names = {c["text"] for c in region_claims}
    assert any("dod-table" in t and "present=False" in t for t in names)
    assert any("degradations" in t and "present=False" in t for t in names)


def test_branch_mode_writes_nothing(tmp_path):
    session = _session(tmp_path, mode="branch", body=_happy_body())
    rc, body = _invoke("stage", session)
    assert rc == 0
    assert body == {"ok": True, "applicable": False, "reason": "branch-mode-has-no-pr-body"}
    assert not os.path.isdir(os.path.join(session, "grounding"))


def test_token_scrub_round_trip(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, staged = _invoke("stage", session)
    assert rc == 0
    token = staged["stageToken"]
    row = {"id": "stage-token:%s" % token, "verdict": "CONFIRMED", "note": token}
    scrubbed = EA._scrub_verdicts([row])
    assert scrubbed[0]["id"] == "stage-token:%s" % token
    assert scrubbed[0]["id"].split(":", 1)[1] == token


def test_attest_happy_path(tmp_path):
    session = _session(tmp_path, body=_happy_body())
    rc, staged = _invoke("stage", session)
    assert rc == 0
    token = staged["stageToken"]
    repo_claims = [c for c in staged["claims"] if c["verifiability"] == "repo"]
    verdicts = [{"id": "stage-token:%s" % token, "verdict": "CONFIRMED"}]
    refuted_id = repo_claims[0]["claimId"]
    for claim in repo_claims:
        verdict = "REFUTED" if claim["claimId"] == refuted_id else "CONFIRMED"
        verdicts.append({"id": claim["claimId"], "verdict": verdict})
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"verdicts": verdicts}), encoding="utf-8")
    rc, body = _invoke("attest", session, str(result_path))
    assert rc == 0
    assert body["ok"] is True
    assert body["attested"] is True
    assert refuted_id in body["refuted"]
    assert all(cid in body["confirmed"] or cid in body["refuted"] for cid in [
        c["claimId"] for c in repo_claims
    ])
