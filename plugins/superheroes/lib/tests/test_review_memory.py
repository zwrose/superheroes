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


# --- compose-persist / update-round / hash: the record body never rides the courier args ---
# (live 2026-07-02: the haiku courier mangled the oversized inline --record-json payload and every
# native review leg parked cannot-certify: round-memory-write-failed).
import subprocess
import sys


def _cli(*args):
    return subprocess.run([sys.executable, os.path.join(LIB, "review_memory.py"), *args],
                          capture_output=True, text=True)


def _big_findings(dimension, n, evidence_kb=2):
    evidence = ("x" * 1024) * evidence_kb
    return [{"dimension": dimension, "taxonomy": "bug", "title": f"finding {i}",
             "severity": "Critical", "file": "a.py", "line": i, "evidence": evidence}
            for i in range(n)]


def _stage_dim(run_dir, name, round_no, result):
    path = os.path.join(run_dir, f"dim-result-{name}-r{round_no}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    return path


def test_compose_persist_composes_large_record_from_dim_files(tmp_path):
    """A realistic multi-hundred-KB round record persists via file paths + small scalars only."""
    rm = load_memory()
    run_dir = str(tmp_path)
    records_path = os.path.join(run_dir, "round-records.json")
    dims = ["code", "security"]
    for name in dims:
        _stage_dim(run_dir, name, 1, {"dimension": name, "status": "run", "confidence": "high",
                                      "findings": _big_findings(name, 60)})   # ~120KB per dim
    r = _cli("compose-persist", "--path", records_path, "--run-dir", run_dir,
             "--round", "1", "--kind", "baseline", "--dimensions", json.dumps(dims),
             "--changed-subjects-json", "null", "--coverage-decisions-json", "[]",
             "--token-usage-json", json.dumps({"code:r1": {"total": 5}}),
             "--expected-hash", rm.content_hash(""), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    assert "records" not in out, "compose-persist must NOT echo the records (mega stdout)"
    assert out["contentHash"]
    persisted = json.loads(open(records_path, encoding="utf-8").read())
    assert len(persisted) == 1 and persisted[0]["round"] == 1
    assert len(persisted[0]["findings"]) == 120
    assert persisted[0]["runId"] == "run-1"
    assert persisted[0]["tokenUsage"] == {"code:r1": {"total": 5}}
    # fence: the returned hash matches the on-disk text (next round's expected-hash)
    assert out["contentHash"] == rm.content_hash(open(records_path, encoding="utf-8").read())


def test_compose_persist_missing_dim_file_fails_closed(tmp_path):
    rm = load_memory()
    run_dir = str(tmp_path)
    records_path = os.path.join(run_dir, "round-records.json")
    r = _cli("compose-persist", "--path", records_path, "--run-dir", run_dir,
             "--round", "1", "--kind", "baseline", "--dimensions", json.dumps(["code"]),
             "--changed-subjects-json", "null", "--coverage-decisions-json", "[]",
             "--token-usage-json", "{}",
             "--expected-hash", rm.content_hash(""), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert "dim-result" in out.get("reason", "")
    assert not os.path.exists(records_path), "a failed compose must not write the records file"


def test_compose_persist_stale_hash_refused(tmp_path):
    run_dir = str(tmp_path)
    records_path = os.path.join(run_dir, "round-records.json")
    with open(records_path, "w", encoding="utf-8") as fh:
        fh.write("[]\n")
    _stage_dim(run_dir, "code", 1, {"dimension": "code", "status": "run", "findings": []})
    r = _cli("compose-persist", "--path", records_path, "--run-dir", run_dir,
             "--round", "1", "--kind", "baseline", "--dimensions", json.dumps(["code"]),
             "--changed-subjects-json", "null", "--coverage-decisions-json", "[]",
             "--token-usage-json", "{}",
             "--expected-hash", "wrong", "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out == {"ok": False, "reason": "stale"}


def test_update_round_applies_small_delta(tmp_path):
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    base = rm.persist_record(records_path, [], {"schemaVersion": 2, "round": 1, "kind": "baseline",
                                                "findings": _big_findings("code", 40),
                                                "confirmationPending": False},
                             expected_hash=rm.content_hash(""), run_id="run-1")
    assert base["ok"]
    updates = {"confirmationPending": True, "changedSubjects": ["Code"],
               "coverageDecisions": [{"id": "cd-1"}], "fix": {"fixes": ["a.py::bug"], "deferred": []}}
    r = _cli("update-round", "--path", records_path, "--round", "1",
             "--updates-json", json.dumps(updates),
             "--expected-hash", base["contentHash"], "--run-id", "run-2")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    assert "records" not in out
    persisted = json.loads(open(records_path, encoding="utf-8").read())
    assert len(persisted) == 1
    rec = persisted[0]
    assert rec["confirmationPending"] is True
    assert rec["fix"] == updates["fix"]
    assert len(rec["findings"]) == 40, "the delta update must keep the round's findings"
    assert rec["runId"] == "run-2"


def test_update_round_missing_round_fails_closed(tmp_path):
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    with open(records_path, "w", encoding="utf-8") as fh:
        fh.write("[]\n")
    r = _cli("update-round", "--path", records_path, "--round", "3",
             "--updates-json", "{}", "--expected-hash", rm.content_hash("[]\n"), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is False and out["reason"] == "round-missing"


def test_hash_verb_prints_content_hash(tmp_path):
    rm = load_memory()
    p = tmp_path / "f.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    out = json.loads(_cli("hash", "--path", str(p)).stdout)
    assert out == {"ok": True, "contentHash": rm.content_hash('{"a": 1}')}
    out = json.loads(_cli("hash", "--path", str(tmp_path / "absent.json")).stdout)
    assert out == {"ok": True, "contentHash": rm.content_hash("")}
