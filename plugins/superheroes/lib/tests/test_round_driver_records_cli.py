"""#1196 WO-B: CLI-path round-records producer, submit-accept atomicity, corrupt-resume park."""
import importlib.util
import json
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RM = _load("review_memory")
RC = RD.round_commit

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
HEAD = "abc123def4567890abcdef1234567890abcdef12"
_A_FINDING = {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude"}
    base.update(over)
    return base


def _responder(round1_findings=None):
    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            dims = payload.get("dimensions") or list(RD.DIMENSIONS)
            seats = {d: {"findings": []} for d in dims}
            if rnd == 1 and round1_findings:
                seats[dims[0]] = {"findings": list(round1_findings)}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [
                {"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_GAPSWEEP:
            return {"findings": []}
        if phase == RD.P_AUDITS:
            return {"results": [
                {"id": t["id"], "ruling": "discharged", "reason": "r", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor")} for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            return {"findings": []}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiff": HEAD, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        return {}

    return respond


def _stop_at_kind(monkeypatch, kind, stop_at, n=0):
    real = RC.begin
    counts = {}

    def wrapper(session_dir, commit_kind, **kw):
        idx = counts.get(commit_kind, 0)
        if commit_kind == kind and idx == n:
            kw["stop_at"] = stop_at
        counts[commit_kind] = idx + 1
        return real(session_dir, commit_kind, **kw)

    monkeypatch.setattr(RD.round_commit, "begin", wrapper)


def _records_panel_submit_setup(tmp_path):
    records = tmp_path / "round-records.json"
    before_bytes = RM.records_bytes([])
    records.write_bytes(before_bytes)
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir, exist_ok=True)
    cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
    respond = _responder(round1_findings=[_A_FINDING])
    n = RD.cmd_next(session_dir, cfg)
    assert n["ok"], n
    assert n["phase"] == RD.P_PANEL, n
    return session_dir, records, before_bytes, cfg, respond, n


def test_cmd_next_corrupt_non_mapping_member_parks_cannot_certify(tmp_path):
  records = tmp_path / "records.json"
  records.write_text("[null]")
  session_dir = str(tmp_path)
  cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
  out = RD.cmd_next(session_dir, cfg)
  assert out["ok"], out
  assert out["phase"] == RD.P_TERMINAL
  assert out["payload"]["verdict"] == "cannot-certify"
  assert out["payload"]["certification"]["shape"] is None
  journal = RD.read_journal(session_dir)
  assert any(e.get("outcome") == "resume-corrupt-park" for e in journal)


def test_cmd_next_corrupt_malformed_json_parks_cannot_certify(tmp_path):
  records = tmp_path / "records.json"
  records.write_text("{not valid json")
  session_dir = str(tmp_path)
  cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
  out = RD.cmd_next(session_dir, cfg)
  assert out["ok"], out
  assert out["phase"] == RD.P_TERMINAL
  assert out["payload"]["verdict"] == "cannot-certify"
  journal = RD.read_journal(session_dir)
  assert any(e.get("outcome") == "resume-corrupt-park" for e in journal)


def test_submit_records_staged_crash_leaves_file_byte_identical(tmp_path, monkeypatch):
  session_dir, records, before_bytes, cfg, respond, n = _records_panel_submit_setup(tmp_path)
  _stop_at_kind(monkeypatch, "submit-accept", "staged")
  with pytest.raises(RC.StopPoint):
    RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                  respond(n["phase"], n["payload"], n["round"]))
  assert records.read_bytes() == before_bytes


def test_submit_records_sealed_crash_recovers_bytes_and_state(tmp_path, monkeypatch):
  session_dir, records, before_bytes, cfg, respond, n = _records_panel_submit_setup(tmp_path)
  art = respond(n["phase"], n["payload"], n["round"])
  before_state = open(os.path.join(session_dir, RD.STATE_FILE), "rb").read()
  _stop_at_kind(monkeypatch, "submit-accept", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
  assert records.read_bytes() == before_bytes
  assert open(os.path.join(session_dir, RD.STATE_FILE), "rb").read() == before_state
  out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
  assert out["ok"], out
  assert records.read_bytes() != before_bytes
  assert open(os.path.join(session_dir, RD.STATE_FILE), "rb").read() != before_state


def test_submit_hash_mismatch_leaves_records_file_byte_identical(tmp_path):
  session_dir, records, before_bytes, cfg, respond, n = _records_panel_submit_setup(tmp_path)
  out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], "deadbeef", respond(n["phase"],
                                                                                  n["payload"],
                                                                                  n["round"]))
  assert out["ok"] is False
  assert "hash" in out["reason"]
  assert records.read_bytes() == before_bytes


def test_cli_and_run_loop_records_files_are_byte_identical(tmp_path):
  """DoD row 4 (narrowed): the CLI sidecar and library ``_persist_round_records`` land the same
  bytes when the post-fold state feeding ``_round_records_payload`` is equivalent."""
  finding = dict(_A_FINDING)
  records_cli = tmp_path / "cli-records.json"
  records_loop = tmp_path / "loop-records.json"
  empty_bytes = RM.records_bytes([])
  records_cli.write_bytes(empty_bytes)
  records_loop.write_bytes(empty_bytes)
  cfg_cli = _cfg(dimensions=["test-reviewer"], recordsPath=str(records_cli))
  cfg_loop = _cfg(dimensions=["test-reviewer"], recordsPath=str(records_loop))
  respond = _responder(round1_findings=[finding])
  session_dir = str(tmp_path / "cli-session")
  os.makedirs(session_dir, exist_ok=True)
  n = RD.cmd_next(session_dir, cfg_cli)
  assert n["ok"], n
  RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                respond(n["phase"], n["payload"], n["round"]))
  ok, state_cli = RD.load_state(session_dir)
  assert ok and state_cli is not None
  state_loop = RD.new_state(dict(cfg_loop))
  state_loop["_records"] = json.loads(json.dumps(state_cli["_records"]))
  state_loop["rounds"] = json.loads(json.dumps(state_cli["rounds"]))
  RD._persist_round_records(state_loop, state_loop["config"])
  assert records_cli.read_bytes() == records_loop.read_bytes()
