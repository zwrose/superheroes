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
