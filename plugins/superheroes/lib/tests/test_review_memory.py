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


# --- persist-skeleton / update-round / hash: the round record's DURABLE form is the bounded
# skeleton (D3) — evidence bodies never touch round-records.json, and the inline transport
# self-verifies via --record-hash (a courier that mangles the JSON cannot recompute its sha256).
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


def _skeleton_cli(records_path, record, expected_hash, run_id="run-1", record_hash=None):
    rm = load_memory()
    record_json = json.dumps(record)
    return _cli("persist-skeleton", "--path", records_path,
                "--record-json", record_json,
                "--record-hash", record_hash or rm.content_hash(record_json),
                "--expected-hash", expected_hash, "--run-id", run_id)


def test_persist_skeleton_strips_bodies_python_side(tmp_path):
    """Even a full-bodied record shipped by a drifted JS twin lands as skeletons on disk —
    the on-disk contract (no evidence, no receipts) is enforced here, not in the caller."""
    rm = load_memory()
    records_path = str(tmp_path / "run" / "round-records.json")  # run dir doesn't exist yet
    record = {"schemaVersion": 2, "round": 1, "kind": "baseline",
              "confirmationPending": False, "changedSubjects": ["Code"],
              "coverageDecisions": [{"id": "cd-1"}],
              "tokenUsage": {"code:r1": {"total": 5}},
              "findings": _big_findings("code", 40), "carriedFindings": [],
              "dimensions": {"code": {"dimension": "code", "status": "run", "confidence": "high",
                                      "round": 1, "subjects": ["Code"],
                                      "findings": _big_findings("code", 40),
                                      "verificationReceipt": {"chain": ["y" * 5000]}}}}
    r = _skeleton_cli(records_path, record, rm.content_hash(""))
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    assert "records" not in out, "persist-skeleton must NOT echo the records (mega stdout)"
    text = open(records_path, encoding="utf-8").read()
    assert "evidence" not in text, "finding bodies must never land in round-records.json"
    assert "verificationReceipt" not in text, "receipts must never land in round-records.json"
    persisted = json.loads(text)
    assert len(persisted) == 1 and persisted[0]["round"] == 1
    assert len(persisted[0]["findings"]) == 40
    assert persisted[0]["findings"][0]["severity"] == "Critical"
    assert persisted[0]["dimensions"]["code"]["blockingCount"] == 40
    assert persisted[0]["runId"] == "run-1"
    assert persisted[0]["tokenUsage"] == {"code:r1": {"total": 5}}
    # fence: the returned hash matches the on-disk text (next round's expected-hash)
    assert out["contentHash"] == rm.content_hash(text)


def test_persist_skeleton_record_hash_mismatch_fails_closed(tmp_path):
    """The transport self-check: a courier-mangled --record-json no longer matches the
    shipped sha256, so nothing is written (retry-or-park upstream, never silent corruption)."""
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    r = _skeleton_cli(records_path, {"schemaVersion": 2, "round": 1, "kind": "baseline"},
                      rm.content_hash(""), record_hash="0" * 64)
    out = json.loads(r.stdout)
    assert out == {"ok": False, "reason": "record-corrupt"}
    assert not os.path.exists(records_path)


def test_persist_skeleton_record_path_variant(tmp_path):
    """A many-finding skeleton that outgrows a safe inline arg rides a staged file; the same
    --record-hash self-check covers the staged text."""
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    staged = tmp_path / "round-skeleton-r1.json"
    record_json = json.dumps({"schemaVersion": 2, "round": 1, "kind": "baseline",
                              "findings": [{"file": "a.py", "title": f"f{i}", "severity": "Minor"}
                                           for i in range(200)]})
    staged.write_text(record_json, encoding="utf-8")
    r = _cli("persist-skeleton", "--path", records_path, "--record-path", str(staged),
             "--record-hash", rm.content_hash(record_json),
             "--expected-hash", rm.content_hash(""), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    assert len(json.loads(open(records_path, encoding="utf-8").read())[0]["findings"]) == 200
    # a corrupted staged file fails the same self-check
    staged.write_text(record_json + " ", encoding="utf-8")
    r = _cli("persist-skeleton", "--path", records_path, "--record-path", str(staged),
             "--record-hash", rm.content_hash(record_json),
             "--expected-hash", out["contentHash"], "--run-id", "run-2")
    assert json.loads(r.stdout) == {"ok": False, "reason": "record-corrupt"}


def test_update_round_slims_deferred_bodies(tmp_path):
    """A deferred entry embedding its full finding body must land slimmed — bodies can't
    smuggle back into round-records.json through the post-fix delta (their durable home is
    the best-effort round-bodies dump)."""
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    base = rm.persist_record(records_path, [], {"schemaVersion": 2, "round": 1, "kind": "baseline"},
                             expected_hash=rm.content_hash(""), run_id="run-1")
    updates = {"fix": {"fixes": [], "deferred": [
        {"identity": "a.py::x", "severity": "Critical", "reason": "R" * 600,
         "finding": {"file": "a.py", "title": "x", "severity": "Critical",
                     "evidence": "E" * 5000}}]}}
    r = _cli("update-round", "--path", records_path, "--round", "1",
             "--updates-json", json.dumps(updates),
             "--expected-hash", base["contentHash"], "--run-id", "run-2")
    assert json.loads(r.stdout)["ok"] is True, r.stderr
    text = open(records_path, encoding="utf-8").read()
    assert "E" * 100 not in text, "deferred finding bodies must never land in round-records.json"
    entry = json.loads(text)[0]["fix"]["deferred"][0]
    assert entry["identity"] == "a.py::x" and len(entry["reason"]) == 500
    assert entry["finding"] == {"file": "a.py", "title": "x", "severity": "Critical"}


def test_persist_skeleton_stale_hash_refused(tmp_path):
    records_path = str(tmp_path / "round-records.json")
    with open(records_path, "w", encoding="utf-8") as fh:
        fh.write("[]\n")
    r = _skeleton_cli(records_path, {"schemaVersion": 2, "round": 1, "kind": "baseline"}, "wrong")
    out = json.loads(r.stdout)
    assert out == {"ok": False, "reason": "stale"}
    assert json.loads(open(records_path, encoding="utf-8").read()) == []


def test_load_summary_extras_path_folds_the_entry_reads(tmp_path):
    records_path = str(tmp_path / "round-records.json")
    extras_path = str(tmp_path / "last-extras.json")
    with open(extras_path, "w", encoding="utf-8") as fh:
        json.dump({"changedSubjects": ["Code"], "needsConfirmation": True}, fh)
    r = _cli("load-summary", "--path", records_path, "--dimensions", '["code"]',
             "--extras-path", extras_path)
    out = json.loads(r.stdout)
    assert out["ok"] is True and out["records"] == []
    assert out["extras"] == {"changedSubjects": ["Code"], "needsConfirmation": True}
    # missing or corrupt extras answer as null (the loop's readJson-default parity)
    r = _cli("load-summary", "--path", records_path, "--dimensions", '["code"]',
             "--extras-path", str(tmp_path / "absent.json"))
    assert json.loads(r.stdout)["extras"] is None


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


def test_load_summary_bounds_large_records(tmp_path):
    """The resume read mirrors the write-side fix: a large on-disk records file loads as a
    BOUNDED summary — findings keep only their small identity/class/severity skeleton (the
    breaker, recurrence, and fix-context inputs); the unbounded evidence bodies and receipts
    never ride the courier stdout."""
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    recs = []
    for rnd in (1, 2):
        findings = _big_findings("code", 50)   # ~100KB of evidence per round
        recs.append({"schemaVersion": 2, "round": rnd, "kind": "baseline",
                     "confirmationPending": rnd == 2, "changedSubjects": ["Code"],
                     "coverageDecisions": [{"id": "cd-%d" % rnd, "classKey": "k"}],
                     "tokenUsage": {"code:r%d" % rnd: {"total": 3}},
                     "findings": findings, "carriedFindings": [],
                     "dimensions": {"code": {"dimension": "code", "status": "run",
                                             "confidence": "high", "round": rnd,
                                             "findings": findings, "subjects": ["Code"],
                                             "verificationReceipt": {"chain": ["y" * 5000]}}}})
    with open(records_path, "w", encoding="utf-8") as fh:
        json.dump(recs, fh)
    on_disk = os.path.getsize(records_path)
    r = _cli("load-summary", "--path", records_path, "--dimensions", '["code"]')
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    assert len(r.stdout) < on_disk / 5, (
        "the resume summary must be a small fraction of the on-disk file "
        "(%d vs %d on disk)" % (len(r.stdout), on_disk))
    assert "evidence" not in r.stdout, "findings bodies must never ride the load stdout"
    assert "verificationReceipt" not in r.stdout, "reviewer receipts must never ride the load stdout"
    assert out["contentHash"] == rm.content_hash(open(records_path, encoding="utf-8").read())
    s1, s2 = out["records"]
    # everything the loop needs in memory to seed a resume survives:
    assert s1["round"] == 1 and s1["kind"] == "baseline"
    assert s2["confirmationPending"] is True
    assert s2["changedSubjects"] == ["Code"]
    assert s2["coverageDecisions"][0]["id"] == "cd-2"
    f = s1["findings"][0]
    assert f["severity"] == "Critical" and f["file"] == "a.py" and f["title"]
    assert f["classKey"] if "classKey" in f else True
    dim = s1["dimensions"]["code"]
    assert dim["status"] == "run" and dim["confidence"] == "high"
    assert dim["hasFindings"] is True and dim["blockingCount"] == 50
    assert dim["subjects"] == ["Code"]


def test_load_summary_corrupt_reports_corrupt(tmp_path):
    p = tmp_path / "round-records.json"
    p.write_text("{corrupt", encoding="utf-8")
    r = _cli("load-summary", "--path", str(p), "--dimensions", '["code"]')
    out = json.loads(r.stdout)
    assert out["ok"] is False and out["state"] == "corrupt"


def test_hash_verb_prints_content_hash(tmp_path):
    rm = load_memory()
    p = tmp_path / "f.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    out = json.loads(_cli("hash", "--path", str(p)).stdout)
    assert out == {"ok": True, "contentHash": rm.content_hash('{"a": 1}')}
    out = json.loads(_cli("hash", "--path", str(tmp_path / "absent.json")).stdout)
    assert out == {"ok": True, "contentHash": rm.content_hash("")}
