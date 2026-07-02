import importlib.util
import json
import os

LIB = os.path.join(os.path.dirname(__file__), "..")


def load_memory():
    spec = importlib.util.spec_from_file_location("review_memory", os.path.join(LIB, "review_memory.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_corrupt_round_records_report_corrupt(tmp_path):
    rm = load_memory()
    path = tmp_path / "round-records.json"
    path.write_text("{corrupt", encoding="utf-8")
    state = rm.load_records_state(str(path), ["test-reviewer"])
    assert state["ok"] is False
    assert state["state"] == "corrupt"


def test_stale_round_record_write_leaves_file_unchanged(tmp_path):
    rm = load_memory()
    path = tmp_path / "round-records.json"
    path.write_text("[]\n", encoding="utf-8")
    result = rm.persist_record(str(path), [], {"round": 1, "schemaVersion": 2}, expected_hash="wrong", run_id="run-new")
    assert result == {"ok": False, "reason": "stale"}
    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_carried_findings_do_not_recur():
    rm = load_memory()
    records = [
        {"round": 1, "findings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important"}]},
        {"round": 2, "findings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important", "carried": True}]},
    ]
    assert rm.recurrent_classes(records) == []
