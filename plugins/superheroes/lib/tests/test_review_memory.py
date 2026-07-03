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
    # keep the inline arg under Linux's 128KiB per-arg cap (MAX_ARG_STRLEN) — the point here
    # is the Python-side stripping, not the transport size (the staged variant covers large)
    record = {"schemaVersion": 2, "round": 1, "kind": "baseline",
              "confirmationPending": False, "changedSubjects": ["Code"],
              "coverageDecisions": [{"id": "cd-1"}],
              "tokenUsage": {"code:r1": {"total": 5}},
              "findings": _big_findings("code", 20, evidence_kb=1), "carriedFindings": [],
              "dimensions": {"code": {"dimension": "code", "status": "run", "confidence": "high",
                                      "round": 1, "subjects": ["Code"],
                                      "findings": _big_findings("code", 20, evidence_kb=1),
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
    assert len(persisted[0]["findings"]) == 20
    assert persisted[0]["findings"][0]["severity"] == "Critical"
    assert persisted[0]["dimensions"]["code"]["blockingCount"] == 20
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
    --record-hash self-check covers the staged text, and the consumed stage is unlinked."""
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
    assert not staged.exists(), "the staged skeleton file is consumed (unlinked) on success"
    # a corrupted staged file fails the same self-check
    staged.write_text(record_json + " ", encoding="utf-8")
    r = _cli("persist-skeleton", "--path", records_path, "--record-path", str(staged),
             "--record-hash", rm.content_hash(record_json),
             "--expected-hash", out["contentHash"], "--run-id", "run-2")
    assert json.loads(r.stdout) == {"ok": False, "reason": "record-corrupt"}


def test_persist_skeleton_staged_tolerates_heredoc_newline(tmp_path):
    """The bundle's leaf-bash writeFile is a heredoc: it puts body+'\\n' on disk, one byte the
    sender's hash never covered. The STAGED check tolerates exactly that one newline (a second
    one still fails); the INLINE check stays exact."""
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    staged = tmp_path / "round-skeleton-r1.json"
    record_json = json.dumps({"schemaVersion": 2, "round": 1, "kind": "baseline"})
    staged.write_text(record_json + "\n", encoding="utf-8")
    r = _cli("persist-skeleton", "--path", records_path, "--record-path", str(staged),
             "--record-hash", rm.content_hash(record_json),
             "--expected-hash", rm.content_hash(""), "--run-id", "run-1")
    assert json.loads(r.stdout)["ok"] is True, r.stdout + r.stderr
    staged.write_text(record_json + "\n\n", encoding="utf-8")
    r = _cli("persist-skeleton", "--path", records_path, "--record-path", str(staged),
             "--record-hash", rm.content_hash(record_json),
             "--expected-hash", "whatever", "--run-id", "run-2")
    assert json.loads(r.stdout) == {"ok": False, "reason": "record-corrupt"}


def test_persist_skeleton_round_cross_check(tmp_path):
    """--round binds the invocation to the intended round: a replayed earlier (record-json,
    record-hash) pair passes the hash but fails this freshness check."""
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    record_json = json.dumps({"schemaVersion": 2, "round": 1, "kind": "baseline"})
    r = _cli("persist-skeleton", "--path", records_path,
             "--record-json", record_json, "--record-hash", rm.content_hash(record_json),
             "--round", "2", "--expected-hash", rm.content_hash(""), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is False and out["reason"] == "record-corrupt"
    assert not os.path.exists(records_path)


def test_persist_skeleton_stale_probe_answers_idempotently(tmp_path):
    """When a prior attempt PERSISTED and only its stdout answer was lost in transport, the
    retry (same args, now-stale expected-hash) answers ok idempotently instead of 'stale' —
    a transport blip on the answer path must not kill the run as write-failed."""
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    record_json = json.dumps({"schemaVersion": 2, "round": 1, "kind": "baseline"})
    args = ("persist-skeleton", "--path", records_path,
            "--record-json", record_json, "--record-hash", rm.content_hash(record_json),
            "--round", "1", "--expected-hash", rm.content_hash(""), "--run-id", "run-1")
    first = json.loads(_cli(*args).stdout)
    assert first["ok"] is True
    replay = json.loads(_cli(*args).stdout)   # identical retry with the now-stale hash
    assert replay["ok"] is True and replay.get("idempotent") is True
    assert replay["contentHash"] == first["contentHash"]
    # a DIFFERENT record for the same round with a stale hash still refuses
    other = json.dumps({"schemaVersion": 2, "round": 1, "kind": "targeted"})
    r = _cli("persist-skeleton", "--path", records_path,
             "--record-json", other, "--record-hash", rm.content_hash(other),
             "--round", "1", "--expected-hash", rm.content_hash(""), "--run-id", "run-1")
    assert json.loads(r.stdout) == {"ok": False, "reason": "stale"}


def test_update_round_hash_and_idempotent_replay(tmp_path):
    """update-round self-verifies its delta when --updates-hash is present (pre-D3 bundles
    omit it), answers updates-corrupt (not a traceback) on mangled JSON, and answers ok
    idempotently when the delta was already applied and only the answer was lost."""
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    base = rm.persist_record(records_path, [], {"schemaVersion": 2, "round": 1, "kind": "baseline"},
                             expected_hash=rm.content_hash(""), run_id="run-1")
    updates_json = json.dumps({"confirmationPending": True, "changedSubjects": ["Code"]})
    r = _cli("update-round", "--path", records_path, "--round", "1",
             "--updates-json", updates_json, "--updates-hash", "0" * 64,
             "--expected-hash", base["contentHash"], "--run-id", "run-2")
    assert json.loads(r.stdout) == {"ok": False, "reason": "updates-corrupt"}
    r = _cli("update-round", "--path", records_path, "--round", "1",
             "--updates-json", "{not json", "--updates-hash", rm.content_hash("{not json"),
             "--expected-hash", base["contentHash"], "--run-id", "run-2")
    out = json.loads(r.stdout)
    assert out["ok"] is False and out["reason"] == "updates-corrupt"
    args = ("update-round", "--path", records_path, "--round", "1",
            "--updates-json", updates_json, "--updates-hash", rm.content_hash(updates_json),
            "--expected-hash", base["contentHash"], "--run-id", "run-2")
    first = json.loads(_cli(*args).stdout)
    assert first["ok"] is True
    replay = json.loads(_cli(*args).stdout)   # identical retry with the now-stale hash
    assert replay["ok"] is True and replay.get("idempotent") is True
    assert replay["contentHash"] == first["contentHash"]


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


def test_update_round_bounds_oversized_coverage_decisions(tmp_path):
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    base = rm.persist_record(records_path, [], {"schemaVersion": 2, "round": 1, "kind": "baseline",
                                                "findings": [], "confirmationPending": False},
                             expected_hash=rm.content_hash(""), run_id="run-1")
    assert base["ok"]
    big_text = "x" * 8000
    small_text = "short coverage rationale"
    updates = {"coverageDecisions": [
        {"id": "cd-big", "classKey": "k::big", "text": big_text},
        {"id": "cd-small", "classKey": "k::small", "text": small_text},
    ]}
    r = _cli("update-round", "--path", records_path, "--round", "1",
             "--updates-json", json.dumps(updates),
             "--expected-hash", base["contentHash"], "--run-id", "run-2")
    assert json.loads(r.stdout)["ok"] is True, r.stderr
    rec = json.loads(open(records_path, encoding="utf-8").read())[0]
    by_id = {d["id"]: d for d in rec["coverageDecisions"]}
    assert len(by_id["cd-big"]["text"]) == 500
    assert by_id["cd-big"]["text"] == big_text[:500]
    assert by_id["cd-small"]["text"] == small_text


def test_persist_skeleton_bounds_coverage_decisions_on_disk(tmp_path):
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    big_text = "y" * 9000
    record = {"schemaVersion": 2, "round": 1, "kind": "baseline", "findings": [],
              "coverageDecisions": [{"id": "cd-1", "classKey": "k", "text": big_text}]}
    r = _skeleton_cli(records_path, record, rm.content_hash(""))
    assert json.loads(r.stdout)["ok"] is True, r.stderr
    persisted = json.loads(open(records_path, encoding="utf-8").read())[0]
    assert len(persisted["coverageDecisions"][0]["text"]) == 500


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


def _round_record(round_no, fixes, deferred, coverage, findings_n=40):
    return {"schemaVersion": 2, "round": round_no, "kind": "baseline",
            "confirmationPending": False, "changedSubjects": ["Code"],
            "coverageDecisions": coverage, "tokenUsage": {"code:r%d" % round_no: {"total": 3}},
            "findings": _big_findings("code", findings_n), "carriedFindings": [],
            "fix": {"fixes": fixes, "deferred": deferred},
            "dimensions": {"code": {"dimension": "code", "status": "run", "round": round_no}}}


def _telemetry_file(tmp_path):
    path = tmp_path / "review-telemetry.json"
    path.write_text(json.dumps({"schemaVersion": 1, "terminal": "clean", "roundCount": 2,
                                "tokenUsage": {"complete": True, "total": 42, "missing": []},
                                "dimensionCounts": {"code": {"run": 2}},
                                "benchmarkValid": True, "runId": "telem-run", "lease": "L"}),
                    encoding="utf-8")
    return str(path)


def test_compose_terminal_builds_the_readout_record_from_disk(tmp_path):
    """The terminal record is composed PYTHON-SIDE from state already on disk: the unbounded
    fixes/deferred/coverageDecisions ride round-records.json (not the courier), telemetry rides
    review-telemetry.json, and only small verdict scalars ride inline. The evidence-bodied
    `findings` (which no terminal-record consumer reads) never lands in the record."""
    rm = load_memory()
    records_path = str(tmp_path / "round-records.json")
    with open(records_path, "w", encoding="utf-8") as fh:
        json.dump([
            _round_record(1, ["a.py::f0"],
                          [{"identity": "a.py::f0", "severity": "Critical", "reason": "out of scope"}],
                          [{"id": "cd-1", "classKey": "k1"}]),
            _round_record(2, ["b.py::f1"], [], [{"id": "cd-1", "classKey": "k1"}, {"id": "cd-2", "classKey": "k2"}]),
        ], fh)
    telemetry_path = _telemetry_file(tmp_path)
    target = str(tmp_path / "terminal-record.json")
    verdict = {"schemaVersion": 1, "terminal": "clean", "reason": "all good", "round": 2,
               "gate": "clean", "drops": [{"id": "c.py::f9", "title": "spurious", "reason": "unsubstantiated"}],
               "findings": _big_findings("code", 40)}
    verdict_json = json.dumps(verdict)
    r = _cli("compose-terminal", "--path", target, "--records-path", records_path,
             "--telemetry-path", telemetry_path, "--verdict-json", verdict_json,
             "--verdict-hash", rm.content_hash(verdict_json), "--run-id", "run-x", "--lease", "L2")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    text = open(target, encoding="utf-8").read()
    assert out["contentHash"] == rm.content_hash(text)
    assert "records" not in out, "compose-terminal must answer only {ok, contentHash} (no mega echo)"
    rec = json.loads(text)
    # small verdict scalars survive
    assert rec["terminal"] == "clean" and rec["reason"] == "all good" and rec["round"] == 2
    assert rec["gate"] == "clean"
    assert rec["drops"][0]["title"] == "spurious"
    # the unbounded evidence bodies never land in the terminal record
    assert "findings" not in rec, "the terminal record must not carry the evidence-bodied findings"
    assert "evidence" not in text, "no evidence body may ride into the terminal record"
    # fixes/deferred/coverageDecisions are composed from the durable round records
    assert rec["fixes"] == ["a.py::f0", "b.py::f1"], "fixes are the union across rounds, from disk"
    assert [d["identity"] for d in rec["deferred"]] == ["a.py::f0"]
    assert [c["id"] for c in rec["coverageDecisions"]] == ["cd-1", "cd-2"], "coverage deduped by id"
    # telemetry is the on-disk summary (not the courier-transported blob)
    assert rec["telemetry"]["roundCount"] == 2 and rec["telemetry"]["tokenUsage"]["total"] == 42
    assert rec["runId"] == "run-x" and rec["lease"] == "L2"


def test_compose_terminal_verdict_hash_mismatch_fails_closed(tmp_path):
    """A courier that mangles the inline verdict scalars must fail closed here (it cannot also
    recompute the sha256) — never persist silently altered content."""
    rm = load_memory()
    target = str(tmp_path / "terminal-record.json")
    verdict_json = json.dumps({"schemaVersion": 1, "terminal": "clean", "round": 1})
    r = _cli("compose-terminal", "--path", target,
             "--verdict-json", verdict_json, "--verdict-hash", rm.content_hash("something-else"),
             "--run-id", "run-x")
    out = json.loads(r.stdout)
    assert out["ok"] is False and out["reason"] == "verdict-corrupt"
    assert not os.path.exists(target), "a corrupt verdict must not be written"


def test_compose_terminal_overwrites_stale_prior_run(tmp_path):
    """Finalize composes the record fresh and unconditionally replaces a stale prior-run
    terminal-record.json — the file is durable for crash-resume, not append-only."""
    rm = load_memory()
    target = tmp_path / "terminal-record.json"
    target.write_text(json.dumps({"terminal": "halted", "reason": "STALE prior run"}), encoding="utf-8")
    verdict_json = json.dumps({"schemaVersion": 1, "terminal": "clean", "reason": "fresh", "round": 1})
    r = _cli("compose-terminal", "--path", str(target),
             "--verdict-json", verdict_json, "--verdict-hash", rm.content_hash(verdict_json),
             "--run-id", "run-fresh")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    rec = json.loads(target.read_text(encoding="utf-8"))
    assert rec["terminal"] == "clean" and rec["reason"] == "fresh"
    assert "STALE prior run" not in target.read_text(encoding="utf-8")


def test_compose_terminal_missing_records_still_writes(tmp_path):
    """Absent round-records.json (an early terminal before any round persisted) degrades to an
    empty fixes/deferred list — the record still writes so the readout + gate can proceed."""
    rm = load_memory()
    target = str(tmp_path / "terminal-record.json")
    verdict_json = json.dumps({"schemaVersion": 1, "terminal": "cannot-certify", "round": 1})
    r = _cli("compose-terminal", "--path", target, "--records-path", str(tmp_path / "absent.json"),
             "--telemetry-path", str(tmp_path / "absent-telem.json"),
             "--verdict-json", verdict_json, "--verdict-hash", rm.content_hash(verdict_json),
             "--run-id", "run-x")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    rec = json.loads(open(target, encoding="utf-8").read())
    assert rec["terminal"] == "cannot-certify"
    assert rec["fixes"] == [] and rec["deferred"] == [] and rec["coverageDecisions"] == []


def test_compose_terminal_preserves_existing_clean_from_later_failure(tmp_path):
    rm = load_memory()
    path = tmp_path / "terminal-record.json"
    clean = {"terminal": "clean", "round": 5, "runId": "old-clean"}
    path.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failure = {"terminal": "cannot-certify", "reason": "round-memory-unreadable", "round": 1}
    failure_json = json.dumps(failure)
    out = rm.compose_terminal_record(str(path), failure_json,
                                     verdict_hash=rm.content_hash(failure_json),
                                     run_id="flaked-entry")
    assert out["ok"] is True
    assert out.get("preserved") is True
    assert json.loads(path.read_text(encoding="utf-8")) == clean


def test_compose_terminal_preserves_clean_for_transport_class_failures_only(tmp_path):
    rm = load_memory()
    path = tmp_path / "terminal-record.json"
    clean = {"terminal": "clean", "round": 5, "runId": "old-clean"}
    path.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    transport = {"terminal": "cannot-certify", "reason": "coverage-decisions-unreadable", "round": 6}
    transport_json = json.dumps(transport)
    out = rm.compose_terminal_record(str(path), transport_json,
                                     verdict_hash=rm.content_hash(transport_json),
                                     run_id="flaked-entry")
    assert out["ok"] is True and out.get("preserved") is True
    assert json.loads(path.read_text(encoding="utf-8")) == clean

    legitimate = {"terminal": "halted", "reason": "fix failed", "round": 6}
    legitimate_json = json.dumps(legitimate)
    out = rm.compose_terminal_record(str(path), legitimate_json,
                                     verdict_hash=rm.content_hash(legitimate_json),
                                     run_id="later-real-failure")
    assert out["ok"] is True and out.get("preserved") is not True
    assert json.loads(path.read_text(encoding="utf-8"))["terminal"] == "halted"


def test_load_summary_sweeps_stale_staging_but_keeps_durable_state(tmp_path):
    """Run dirs are shared across runs of the same work-item+phase: loop entry sweeps a dead
    run's TRANSIENT staging artifacts while preserving the durable loop state crash-resume
    depends on. round-state.json is a WRITE-ONLY per-run diagnostic (never read back for
    resume), so a dead run's copy must be swept too — it leaked across runs live (2026-07-02,
    run 7's copy survived into run 8), the same cross-run contamination class as the staging
    files."""
    records_path = tmp_path / "round-records.json"
    records_path.write_text("[]\n", encoding="utf-8")
    transient = ["dim-result-code-r1.json", "round-skeleton-r2.json",
                 "round-updates-r2.json", "terminal-record.json.payload",
                 "round-state.json"]
    durable = ["deferred-set.json", "round-bodies-r1.json", "last-extras.json",
               "terminal-record.json"]
    for name in transient + durable:
        (tmp_path / name).write_text("{}", encoding="utf-8")
    r = _cli("load-summary", "--path", str(records_path), "--dimensions", '["code"]',
             "--sweep-stale-staging")
    assert json.loads(r.stdout)["ok"] is True, r.stderr
    for name in transient:
        assert not (tmp_path / name).exists(), f"transient staging {name} must be swept"
    for name in durable + ["round-records.json"]:
        assert (tmp_path / name).exists(), f"durable state {name} must be preserved"
