import json
import os
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)


def load():
    spec = importlib.util.spec_from_file_location("coverage_decisions", os.path.join(LIB, "coverage_decisions.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CD = load()


def test_doc_decision_appends_bounded_section_atomically(tmp_path):
    doc = tmp_path / "plan.md"
    doc.write_text("# Plan\n\nBody\n", encoding="utf-8")
    before = CD.content_hash(doc.read_text(encoding="utf-8"))
    decision = {"id": "RCD-1-test", "kind": "principle", "classKey": "Test::coverage::missing", "text": "Acceptance tests cover every FR.", "sourceRound": 2}
    result = CD.record_doc_decision(str(doc), decision, expected_hash=before, run_id="run-1")
    assert result["ok"] is True
    text = doc.read_text(encoding="utf-8")
    assert "## Review coverage decisions" in text
    assert "RCD-1-test" in text
    assert "Acceptance tests cover every FR." in text


def test_stale_doc_hash_refuses_write(tmp_path):
    doc = tmp_path / "tasks.md"
    doc.write_text("# Tasks\n", encoding="utf-8")
    result = CD.record_doc_decision(str(doc), {"id": "RCD-1", "text": "x"}, expected_hash="wrong", run_id="run-1")
    assert result == {"ok": False, "reason": "stale"}
    assert doc.read_text(encoding="utf-8") == "# Tasks\n"


def test_failed_replace_leaves_old_doc_readable(tmp_path, monkeypatch):
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\n", encoding="utf-8")
    before = CD.content_hash(doc.read_text(encoding="utf-8"))
    monkeypatch.setattr(CD.os, "replace", lambda _src, _dst: (_ for _ in ()).throw(OSError("disk full")))
    result = CD.record_doc_decision(str(doc), {"id": "RCD-1", "text": "x"}, expected_hash=before, run_id="run-1")
    assert result["ok"] is False
    assert result["reason"] == "replace-failed"
    assert doc.read_text(encoding="utf-8") == "# Spec\n"


def test_code_decision_record_is_json_array(tmp_path):
    path = tmp_path / "review-coverage-decisions.json"
    result = CD.record_code_decision(str(path), {"id": "RCD-code", "text": "x"}, expected_hash=CD.content_hash(""), run_id="run-1")
    assert result["ok"] is True
    assert json.loads(path.read_text(encoding="utf-8"))[0]["id"] == "RCD-code"


def test_stale_code_decision_hash_refuses_write(tmp_path):
    path = tmp_path / "review-coverage-decisions.json"
    path.write_text("[]\n", encoding="utf-8")
    result = CD.record_code_decision(str(path), {"id": "RCD-stale", "text": "x"}, expected_hash="wrong", run_id="run-2")
    assert result == {"ok": False, "reason": "stale"}
    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_missing_run_id_refuses_write(tmp_path):
    path = tmp_path / "review-coverage-decisions.json"
    result = CD.record_code_decision(str(path), {"id": "RCD-missing", "text": "x"}, expected_hash=CD.content_hash(""))
    assert result == {"ok": False, "reason": "missing-run-id"}


def test_second_doc_decision_stays_inside_coverage_section(tmp_path):
    doc = tmp_path / "plan.md"
    doc.write_text("# Plan\n\n## Review coverage decisions\n\n- **RCD-1** (coverage; round 1; class `Test::a`): first\n\n## Gates\n\npending\n", encoding="utf-8")
    before = CD.content_hash(doc.read_text(encoding="utf-8"))
    result = CD.record_doc_decision(str(doc), {"id": "RCD-2", "text": "second", "classKey": "Test::b", "sourceRound": 2}, expected_hash=before, run_id="run-1")
    assert result["ok"] is True
    text = doc.read_text(encoding="utf-8")
    gates_idx = text.index("## Gates")
    rcd2_idx = text.index("RCD-2")
    assert rcd2_idx < gates_idx


# --- load: the loop's coverage read, computed entirely Python-side (courier prose must never
# enter the fence hash or the parsed decisions; live 2026-07-02, 4 parked runs) ---


def test_load_code_mode_reads_decisions_and_hash(tmp_path):
    path = tmp_path / "review-coverage-decisions.json"
    text = json.dumps([{"id": "RCD-1", "classKey": "Test::a"}])
    path.write_text(text, encoding="utf-8")
    out = CD.load_decisions(str(path), "code")
    assert out["ok"] is True
    assert out["decisions"][0]["id"] == "RCD-1"
    assert out["contentHash"] == CD.content_hash(text)


def test_load_missing_file_is_expected_empty(tmp_path):
    out = CD.load_decisions(str(tmp_path / "absent.json"), "code")
    assert out == {"ok": True, "decisions": [], "contentHash": CD.content_hash("")}


def test_load_corrupt_code_file_fails_closed(tmp_path):
    path = tmp_path / "review-coverage-decisions.json"
    path.write_text("{bad json", encoding="utf-8")
    out = CD.load_decisions(str(path), "code")
    assert out["ok"] is False and out["state"] == "corrupt"


def test_load_doc_mode_parses_the_recorded_section(tmp_path):
    """The doc parser round-trips record_doc_decision's own append format — both the JSON
    trailer line and the bare markdown line shape."""
    doc = tmp_path / "plan.md"
    doc.write_text("# Plan\n\n## Review coverage decisions\n\n"
                   "- **RCD-line** (coverage; round 1; class `Test::a`): bare line\n",
                   encoding="utf-8")
    before = CD.content_hash(doc.read_text(encoding="utf-8"))
    assert CD.record_doc_decision(str(doc), {"id": "RCD-json", "text": "with trailer",
                                             "classKey": "Test::b", "sourceRound": 2},
                                  expected_hash=before, run_id="run-1")["ok"] is True
    out = CD.load_decisions(str(doc), "doc")
    assert out["ok"] is True
    ids = [d.get("id") for d in out["decisions"]]
    assert "RCD-line" in ids and "RCD-json" in ids
    # a recorded entry parses twice (markdown line + JSON trailer), matching the retired JS
    # parser exactly; the trailer variant carries the full payload
    json_entry = next(d for d in out["decisions"] if d.get("id") == "RCD-json" and "runId" in d)
    assert json_entry["classKey"] == "Test::b" and json_entry["runId"] == "run-1"
    assert out["contentHash"] == CD.content_hash(doc.read_text(encoding="utf-8"))
    # lines outside the section never parse as decisions
    doc2 = tmp_path / "other.md"
    doc2.write_text("# Plan\n\n## Other\n\n- **RCD-outside** (coverage; round 1; class `X::y`): nope\n",
                    encoding="utf-8")
    assert CD.load_decisions(str(doc2), "doc")["decisions"] == []
