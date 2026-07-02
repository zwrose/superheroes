import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)


def load():
    spec = importlib.util.spec_from_file_location("review_telemetry", os.path.join(LIB, "review_telemetry.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RT = load()


def test_complete_usage_is_benchmark_valid(tmp_path):
    record = RT.build_record(
        rounds=[{"round": 1, "dimensions": {"code-reviewer": {"status": "run", "tier": "reviewer-deep"}}}],
        expected_leaves=["code-reviewer:r1", "synthesis:r1"],
        usage={"code-reviewer:r1": {"input": 3, "output": 4, "total": 7}, "synthesis:r1": {"input": 1, "output": 2, "total": 3}},
        benchmark=True,
    )
    assert record["tokenUsage"]["complete"] is True
    assert record["benchmarkValid"] is True
    assert record["tokenUsage"]["total"] == 10


def test_partial_usage_is_not_benchmark_valid(tmp_path):
    record = RT.build_record(
        rounds=[{"round": 1, "dimensions": {}}],
        expected_leaves=["code-reviewer:r1", "synthesis:r1"],
        usage={"code-reviewer:r1": {"total": 7}},
        benchmark=True,
    )
    assert record["tokenUsage"]["complete"] is False
    assert record["benchmarkValid"] is False
    assert record["tokenUsage"]["missing"] == ["synthesis:r1"]


def test_dimension_counts_record_run_skip_and_tiers():
    record = RT.build_record(
        rounds=[{"round": 1, "dimensions": {"test-reviewer": {"status": "run", "tier": "reviewer-deep"}, "security-reviewer": {"status": "skipped", "tier": "reviewer-deep", "escalated": True}}}],
        expected_leaves=["test-reviewer:r1"],
        usage={"test-reviewer:r1": {"total": 7}},
        benchmark=False,
    )
    assert record["dimensionCounts"]["test-reviewer"]["run"] == 1
    assert record["dimensionCounts"]["security-reviewer"]["skipped"] == 1
    assert record["dimensionCounts"]["test-reviewer"]["deep"] == 1
    assert record["dimensionCounts"]["security-reviewer"]["escalated"] == 1


def test_write_failure_does_not_change_terminal(tmp_path, monkeypatch):
    path = tmp_path / "review-telemetry.json"
    record = RT.build_record(rounds=[], expected_leaves=[], usage={}, benchmark=False, terminal="clean")
    monkeypatch.setattr(RT, "_atomic_write", lambda _path, _text: {"ok": False, "reason": "write-failed"})
    result = RT.write_record(str(path), record, expected_hash=RT.content_hash(""), run_id="run-1")
    assert result["ok"] is False
    assert record["terminal"] == "clean"


def test_stale_telemetry_write_refuses_to_overwrite(tmp_path):
    path = tmp_path / "review-telemetry.json"
    path.write_text('{"schemaVersion":1}\n', encoding="utf-8")
    record = RT.build_record(rounds=[], expected_leaves=[], usage={}, benchmark=False, terminal="clean")
    result = RT.write_record(str(path), record, expected_hash="wrong", run_id="run-2")
    assert result == {"ok": False, "reason": "stale"}
    assert path.read_text(encoding="utf-8") == '{"schemaVersion":1}\n'


# --- write-from-records: rounds come from round-records.json ON DISK, never inline ---
# (live 2026-07-02: the inline --payload-json with all rounds embedded was courier-mangled).
import subprocess
import sys


def _cli(*args):
    return subprocess.run([sys.executable, os.path.join(LIB, "review_telemetry.py"), *args],
                          capture_output=True, text=True)


def test_write_from_records_reads_rounds_from_disk_and_prints_summary(tmp_path):
    records_path = tmp_path / "round-records.json"
    rounds = [{"schemaVersion": 2, "round": 1,
               "dimensions": {"code": {"status": "run", "tier": "reviewer-deep"}},
               "findings": [{"title": "big", "evidence": "x" * 200000, "severity": "Critical"}]}]
    records_path.write_text(json.dumps(rounds), encoding="utf-8")
    path = tmp_path / "review-telemetry.json"
    r = _cli("write-from-records", "--path", str(path), "--records-path", str(records_path),
             "--expected-leaves-json", json.dumps(["code:r1"]),
             "--usage-json", json.dumps({"code:r1": {"input": 1, "output": 2, "total": 3}}),
             "--terminal", "clean",
             "--expected-hash", RT.content_hash(""), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    # stdout is the SMALL summary — never the rounds themselves
    assert "rounds" not in out, "write-from-records must not echo the rounds"
    assert out["roundCount"] == 1
    assert out["tokenUsage"]["complete"] is True and out["tokenUsage"]["total"] == 3
    assert out["dimensionCounts"]["code"]["run"] == 1
    assert out["benchmarkValid"] is True
    # D3: the on-disk telemetry record is the same small summary — no rounds embed (the round
    # history's durable home is round-records.json; nothing ever read telemetry rounds back)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["terminal"] == "clean"
    assert "rounds" not in persisted, "telemetry must not duplicate the round records on disk"
    assert persisted["roundCount"] == 1
    assert persisted["runId"] == "run-1"


def test_write_from_records_stale_refused(tmp_path):
    records_path = tmp_path / "round-records.json"
    records_path.write_text("[]", encoding="utf-8")
    path = tmp_path / "review-telemetry.json"
    path.write_text('{"schemaVersion":1}\n', encoding="utf-8")
    r = _cli("write-from-records", "--path", str(path), "--records-path", str(records_path),
             "--expected-leaves-json", "[]", "--usage-json", "{}", "--terminal", "clean",
             "--expected-hash", "wrong", "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is False and out["reason"] == "stale"
    assert path.read_text(encoding="utf-8") == '{"schemaVersion":1}\n'


def test_write_from_records_corrupt_records_fail_closed(tmp_path):
    # A CORRUPT records file fails closed (no telemetry write); a MISSING one is fine (empty
    # rounds — early terminals can finalize before any round was persisted).
    path = tmp_path / "review-telemetry.json"
    (tmp_path / "corrupt.json").write_text("{nope", encoding="utf-8")
    r = _cli("write-from-records", "--path", str(path), "--records-path", str(tmp_path / "corrupt.json"),
             "--expected-leaves-json", "[]", "--usage-json", "{}", "--terminal", "clean",
             "--expected-hash", RT.content_hash(""), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert not path.exists()


def test_write_from_records_missing_records_writes_zero_round_summary(tmp_path):
    path = tmp_path / "review-telemetry.json"
    r = _cli("write-from-records", "--path", str(path), "--records-path", str(tmp_path / "absent.json"),
             "--expected-leaves-json", "[]", "--usage-json", "{}", "--terminal", "halted",
             "--expected-hash", RT.content_hash(""), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    assert out["roundCount"] == 0
    assert json.loads(path.read_text(encoding="utf-8"))["roundCount"] == 0
