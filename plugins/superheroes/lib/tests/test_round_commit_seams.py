"""Crash-window suite for round_commit seams in the round driver (#918).

Each driver seam that commits multiple artifacts in one ``round_commit`` transaction is exercised
at ``staged``, ``sealed``, ``applied``, and ``done`` stop points; recovery must leave the seam's
artifacts mutually consistent (or unchanged when the commit is discarded).
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RR = _load("round_records")
RC = RD.round_commit

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")

SEAT_MAP = {"seats": {dim: {"vendor": "claude", "model": "sonnet-5", "engine": "claude"}
                      for dim in RD.DIMENSIONS}}


class FakeAdapters(object):
  ADAPTER_PHASES = (RD.P_PANEL, RD.P_VERIFIERS, RD.P_SYNTHESIS, RD.P_GAPSWEEP, RD.P_AUDITS,
                    RD.P_SCOPED, RD.P_VERIFY, RD.P_FIXER)

  def __init__(self):
    self.rosters = {RD.P_PANEL: list(RD.DIMENSIONS),
                    RD.P_VERIFIERS: [],
                    RD.P_SYNTHESIS: ["synthesis"],
                    RD.P_FIXER: ["dispatch-fixer"]}
    self.roster_reasons = {}
    self.faults = {}
    self.assemble_reason = None
    self.assembled = []
    self.policies = {}

  def roster_for(self, phase, state, config):
    if phase in self.roster_reasons:
      return [], self.roster_reasons[phase]
    return list(self.rosters.get(phase, [])), None

  def payload_fault(self, phase, payload, seat_key, record_boundary=False):
    return self.faults.get(seat_key)

  def missing_policy(self, phase):
    return self.policies.get(phase, "seat-status")

  def assemble(self, phase, envelopes, state, config, dispatch_manifest=None, canary=None,
               session_dir=None):
    self.assembled.append({"phase": phase, "envelopes": envelopes,
                           "dispatch_manifest": dispatch_manifest, "canary": canary,
                           "session_dir": session_dir})
    if self.assemble_reason is not None:
      return None, self.assemble_reason
    if phase == RD.P_PANEL:
      seats = {}
      for env in (envelopes or []):
        if not isinstance(env, dict):
          continue
        seat = env.get("seat")
        if env.get("schema") == RR.SEAT_MISSING_SCHEMA:
          seats[seat] = {"findings": [], "missing": True}
        else:
          seats[seat] = env.get("payload") or {"findings": []}
      return {"seats": seats}, None
    if phase == RD.P_VERIFIERS:
      return {"verdicts": []}, None
    if phase == RD.P_SYNTHESIS:
      return {"grouping": None}, None
    return {}, None


@pytest.fixture
def adapters(monkeypatch):
  fake = FakeAdapters()
  monkeypatch.setitem(sys.modules, "round_adapters", fake)
  return fake


def _cfg(**over):
  base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude",
          "seatMap": SEAT_MAP}
  base.update(over)
  return base


def _session(tmp_path, name="s", **cfg_over):
  d = str(tmp_path / name)
  os.makedirs(d, exist_ok=True)
  out = RD.cmd_next(d, _cfg(**cfg_over))
  assert out["ok"], out
  return d


def _state(session_dir):
  ok, state = RD.load_state(session_dir)
  assert ok, state
  return state


def _pending(session_dir):
  return _state(session_dir)["pending"]


def _session_id(session_dir):
  with open(os.path.join(session_dir, RR.META_FILE), encoding="utf-8") as fh:
    return json.load(fh)["sessionId"]


def _anchor_hashes(session_dir, rnd, phase, attempt):
  anchor = RD._orders_anchor(_state(session_dir), session_dir, rnd, phase, attempt)
  if anchor is None:
    return RR.NOT_EMITTED, RR.NOT_EMITTED
  return anchor["manifestSha256"], anchor["orders"].get("*", RR.NOT_EMITTED)


def _result_envelope(session_dir, seat, payload=None, pend=None, **over):
  pend = pend or _pending(session_dir)
  payload = {"findings": [], "confidence": "high", "seat": seat,
             "verificationReceipt": {"ran": True}} if payload is None else payload
  manifest_sha, _order = _anchor_hashes(session_dir, pend["round"], pend["phase"],
                                        pend["attempt"])
  env = {
    "schema": RR.SEAT_RESULT_SCHEMA,
    "session": _session_id(session_dir),
    "round": pend["round"],
    "phase": pend["phase"],
    "seat": seat,
    "attempt": pend["attempt"],
    "vendor": "claude",
    "model": "sonnet-5",
    "dispatchRef": "dispatch-1",
    "orderSha256": RR.NOT_EMITTED,
    "manifestSha256": manifest_sha,
    "recordedAt": "2026-08-07T00:00:00",
    "payloadSha256": RR.payload_sha256(payload),
    "payload": payload,
  }
  env.update(over)
  return env


def _land(session_dir, seat, payload=None, pend=None, **over):
  pend = pend or _pending(session_dir)
  env = _result_envelope(session_dir, seat, payload=payload, pend=pend, **over)
  path = RR.landing_path(session_dir, pend["round"], pend["phase"], RR.storage_key(seat),
                         pend["attempt"])
  RR.atomic_write_json(path, env)
  return path, env


def _land_and_record(session_dir, seat, payload=None):
  _land(session_dir, seat, payload=payload)
  out = RD.cmd_record_result(session_dir, seat)
  assert out["ok"], out
  return out


def _record_all_panel_seats(session_dir, seats=None):
  for seat in (seats if seats is not None else RD.DIMENSIONS):
    _land_and_record(session_dir, seat)


def _fixer_session(tmp_path, adapters, name="fx"):
  d = _session(tmp_path, name=name)
  state = _state(d)
  state["step"] = RD.P_FIXER
  state["pending"] = {"action": RD.P_FIXER, "round": 1, "phase": RD.P_FIXER, "attempt": 0,
                      "payload": {}}
  RD.save_state(d, state)
  return d


def _gitdir(base, name="_gitdir"):
  path = os.path.join(base, name)
  os.makedirs(path, exist_ok=True)
  return path


def _fake_git(gitdir, head="a" * 40, base_sha="b" * 40, remote="github.com/o/r"):
  def run(cwd, *args):
    if args[:2] == ("rev-parse", "--absolute-git-dir"):
      return gitdir
    if args == ("rev-parse", "HEAD"):
      return head
    if args[:3] == ("rev-parse", "--abbrev-ref", "HEAD"):
      return "feature/x"
    if args[0] == "rev-parse" and "--verify" in args:
      return base_sha
    if args[:2] == ("remote", "get-url"):
      return remote
    return None
  return run


def _journal(session_dir):
  return RD.read_journal(session_dir)


def _outcomes(session_dir, outcome):
  return [e for e in _journal(session_dir) if e.get("outcome") == outcome]


def _advance(session_dir, tmp_path, **kw):
  return RD.cmd_advance(session_dir, git=_fake_git(_gitdir(str(tmp_path))), **kw)


def _recover(session_dir, git=None):
  sidecar_target = RD._sidecar_target_for_recover(session_dir, git=git)
  return RC.recover(session_dir, sidecar_target=sidecar_target)


def _commits_empty(session_dir):
  root = RC.commits_root(session_dir)
  return not os.path.exists(root) or os.listdir(root) == []


def _read_bytes(path):
  if not os.path.exists(path):
    return None
  with open(path, "rb") as fh:
    return fh.read()


def _stop_at_kind(monkeypatch, kind, stop_at, n=0):
  real = RD.round_commit.begin
  counts = {}

  def wrapper(session_dir, commit_kind, **kw):
    idx = counts.get(commit_kind, 0)
    if commit_kind == kind and idx == n:
      kw["stop_at"] = stop_at
    counts[commit_kind] = idx + 1
    return real(session_dir, commit_kind, **kw)

  monkeypatch.setattr(RD.round_commit, "begin", wrapper)


def _noop_recover(monkeypatch):
  def noop(session_dir, **kw):
    return {"ok": True, "replayed": [], "discarded": [], "cleaned": []}

  monkeypatch.setattr(RD.round_commit, "recover", noop)


def _noop_driver_recover(monkeypatch):
  monkeypatch.setattr(RD, "_commit_recover_or_refuse", lambda *a, **kw: None)


def _panel_artifact(session_dir):
  dims = RD._panel_dimensions(_state(session_dir)["config"])
  return {"seats": {dim: {"findings": []} for dim in dims}}


def _record_ingest_setup(tmp_path, adapters, head_text="diff --git a/f.py b/f.py\n+fixed\n"):
  d = _fixer_session(tmp_path, adapters)
  head_path = str(tmp_path / "head.diff")
  with open(head_path, "w", encoding="utf-8") as fh:
    fh.write(head_text)
  _land(d, "dispatch-fixer", payload={"fixes": [], "headDiffPath": head_path})
  return d, head_path, head_text


def _assert_record_ingest_agree(session_dir, head_text):
  recorded = [e for e in _outcomes(session_dir, "recorded")
              if e.get("phase") == RD.P_FIXER and e.get("seat") == "dispatch-fixer"]
  assert recorded, "expected a recorded journal row"
  row = recorded[-1]
  pend = _pending(session_dir)
  spath = RR.store_path(session_dir, pend["round"], pend["phase"],
                         RR.storage_key("dispatch-fixer"), pend["attempt"])
  stored, err = RR.read_json(spath)
  assert err is None
  blob_path = stored["payload"]["headDiffStorePath"]
  assert os.path.exists(blob_path)
  with open(blob_path, encoding="utf-8") as fh:
    assert fh.read() == head_text
  assert row["payloadSha256"] == stored["payloadSha256"]


def _snapshot_record_ingest(session_dir):
  pend = _pending(session_dir)
  spath = RR.store_path(session_dir, pend["round"], pend["phase"],
                        RR.storage_key("dispatch-fixer"), pend["attempt"])
  recorded = [e for e in _outcomes(session_dir, "recorded")
              if e.get("phase") == RD.P_FIXER]
  blob_path = None
  if os.path.exists(spath):
    stored, _ = RR.read_json(spath)
    blob_path = (stored.get("payload") or {}).get("headDiffStorePath")
  return {
    "store": _read_bytes(spath),
    "blob": _read_bytes(blob_path) if blob_path else None,
    "journal": json.dumps(recorded, sort_keys=True),
  }


def _orders_setup_fresh(tmp_path):
  d = str(tmp_path / "orders-fresh")
  os.makedirs(d, exist_ok=True)
  return d


def _snapshot_orders(session_dir, rnd, phase, attempt):
  manifest_path = RD._orders_manifest_path(session_dir, rnd, phase, attempt)
  state_path = os.path.join(session_dir, RD.STATE_FILE)
  emitted = [e for e in _outcomes(session_dir, "orders-emitted")
               if e.get("phase") == phase and e.get("round") == rnd
               and e.get("attempt") == attempt]
  return {
    "manifest": _read_bytes(manifest_path),
    "state": _read_bytes(state_path),
    "journal": json.dumps(emitted, sort_keys=True),
  }


def _assert_orders_agree(session_dir, rnd, phase, attempt):
  manifest_path = RD._orders_manifest_path(session_dir, rnd, phase, attempt)
  manifest_sha = hashlib.sha256(_read_bytes(manifest_path)).hexdigest()
  anchor = RD._orders_anchor(_state(session_dir), session_dir, rnd, phase, attempt)
  assert anchor is not None
  assert anchor["manifestSha256"] == manifest_sha
  assert anchor["path"] == manifest_path
  emitted = [e for e in _outcomes(session_dir, "orders-emitted")
             if e.get("phase") == phase and e.get("round") == rnd
             and e.get("attempt") == attempt]
  assert len(emitted) == 1
  assert emitted[0]["manifestSha256"] == manifest_sha


def _fold_setup(tmp_path, adapters):
  d = _session(tmp_path, name="fold")
  _record_all_panel_seats(d)
  return d


def _snapshot_fold(session_dir):
  state_path = os.path.join(session_dir, RD.STATE_FILE)
  accepted = [e for e in _outcomes(session_dir, "accepted")]
  return {"state": _read_bytes(state_path), "journal": json.dumps(accepted, sort_keys=True)}


def _assert_fold_agree(session_dir, phase, rnd, attempt):
  accepted = [e for e in _outcomes(session_dir, "accepted")
              if e.get("phase") == phase and e.get("round") == rnd
              and e.get("attempt") == attempt]
  assert len(accepted) == 1
  state = _state(session_dir)
  la = state.get("lastAccepted")
  assert la and la["phase"] == phase and la["attempt"] == attempt and la["round"] == rnd
  assert isinstance(la.get("artifactHash"), str) and len(la["artifactHash"]) == 64
  assert state["step"] != RD.P_PANEL


def _orphan_failure(tmp_path, adapters, name="att"):
  d = _session(tmp_path, name=name)
  _record_all_panel_seats(d)
  pend = _pending(d)
  os.remove(RR.store_path(d, pend["round"], pend["phase"], RR.storage_key("security-reviewer"),
                          pend["attempt"]))
  os.remove(RR.landing_path(d, pend["round"], pend["phase"],
                            RR.storage_key("security-reviewer"), pend["attempt"]))
  out = RD.cmd_advance(d, git=_fake_git(_gitdir(tmp_path, "_gd-" + name)))
  assert out["reason"] == "journal-orphan"
  seq = None
  for index, event in enumerate(_journal(d), start=1):
    if event.get("reason") == "journal-orphan":
      seq = index
      break
  assert seq is not None
  return d, seq


def _snapshot_attest(session_dir, gitdir):
  receipt_path = os.path.join(session_dir, RD.RECEIPT_FILE)
  state_path = os.path.join(session_dir, RD.STATE_FILE)
  sidecar_path = os.path.join(gitdir, "superheroes", "review-receipt.json")
  rows = _journal(session_dir)
  return {
    "receipt": _read_bytes(receipt_path),
    "state": _read_bytes(state_path),
    "sidecar": _read_bytes(sidecar_path),
    "journal": json.dumps(rows, sort_keys=True),
  }


def _assert_attest_agree(session_dir, gitdir):
  receipt_path = os.path.join(session_dir, RD.RECEIPT_FILE)
  receipt_bytes = _read_bytes(receipt_path)
  assert receipt_bytes is not None
  sidecar_path = os.path.join(gitdir, "superheroes", "review-receipt.json")
  assert os.path.exists(sidecar_path)
  sidecar, err = RR.read_json(sidecar_path)
  assert err is None
  stale, _why = RR.sidecar_stale(sidecar, head_sha="a" * 40, receipt_bytes=receipt_bytes,
                                 session_dir=session_dir)
  assert stale is False
  state = _state(session_dir)
  assert state["terminal"] == RD.ATTESTED_VERDICT
  attested = [e for e in _outcomes(session_dir, "attested")]
  assert len(attested) == 1
  repair_begin = [e for e in _outcomes(session_dir, "sidecar-repair-begin")]
  repair_done = [e for e in _outcomes(session_dir, "sidecar-repaired")]
  assert len(repair_begin) == 1 and len(repair_done) == 1


def _sweep_repair_setup(tmp_path, adapters):
  d = _fixer_session(tmp_path, adapters, name="sweep")
  head_path = str(tmp_path / "sweep-head.diff")
  with open(head_path, "w", encoding="utf-8") as fh:
    fh.write("diff --git a/f.py b/f.py\n+sweep-fixed\n")
  _land(d, "dispatch-fixer", payload={"fixes": [], "headDiffPath": head_path})
  out = RD.cmd_record_result(d, "dispatch-fixer")
  assert out["ok"], out
  spath = out["storePath"]
  blob = out["headDiffStorePath"]
  stored, _ = RR.read_json(spath)
  del stored["payload"]["headDiffStorePath"]
  RR.atomic_write_json(spath, stored)
  os.remove(blob)
  return d, head_path, "diff --git a/f.py b/f.py\n+sweep-fixed\n"


def _snapshot_sweep_repair(session_dir):
  pend = _pending(session_dir)
  spath = RR.store_path(session_dir, pend["round"], pend["phase"],
                        RR.storage_key("dispatch-fixer"), pend["attempt"])
  stored, _ = RR.read_json(spath)
  blob_path = (stored.get("payload") or {}).get("headDiffStorePath")
  return {"store": _read_bytes(spath), "blob": _read_bytes(blob_path) if blob_path else None}


def _assert_sweep_repair_agree(session_dir, head_text):
  pend = _pending(session_dir)
  spath = RR.store_path(session_dir, pend["round"], pend["phase"],
                         RR.storage_key("dispatch-fixer"), pend["attempt"])
  stored, err = RR.read_json(spath)
  assert err is None
  blob_path = stored["payload"]["headDiffStorePath"]
  assert os.path.exists(blob_path)
  with open(blob_path, encoding="utf-8") as fh:
    assert fh.read() == head_text
  assert stored["payloadSha256"] == RR.payload_sha256(stored["payload"])


# --- Group A: record ingest -------------------------------------------------------------------

@pytest.mark.parametrize("stop_at", ["staged", "sealed", "applied", "done"])
def test_seam_a_record_ingest_crash_matrix(tmp_path, adapters, monkeypatch, stop_at):
  d, _head_path, head_text = _record_ingest_setup(tmp_path, adapters)
  before = _snapshot_record_ingest(d)
  _stop_at_kind(monkeypatch, "record-ingest", stop_at)
  with pytest.raises(RC.StopPoint):
    RD.cmd_record_result(d, "dispatch-fixer")
  RC.recover(d)
  if stop_at == "staged":
    after = _snapshot_record_ingest(d)
    assert after == before
  else:
    _assert_record_ingest_agree(d, head_text)
  assert _commits_empty(d)


def test_seam_a_supersede_staged_preserves_old_record(tmp_path, adapters, monkeypatch):
  d = _fixer_session(tmp_path, adapters, name="sup-staged")
  head_path = str(tmp_path / "head1.diff")
  with open(head_path, "w", encoding="utf-8") as fh:
    fh.write("first-revision\n")
  _land(d, "dispatch-fixer", payload={"fixes": [], "headDiffPath": head_path})
  first = RD.cmd_record_result(d, "dispatch-fixer")
  assert first["ok"], first
  before_store = _read_bytes(first["storePath"])
  before_blob = _read_bytes(first["headDiffStorePath"])
  _land(d, "dispatch-fixer", payload={"fixes": ["x"], "headDiffPath": head_path})
  _stop_at_kind(monkeypatch, "record-ingest", "staged")
  with pytest.raises(RC.StopPoint):
    RD.cmd_record_result(d, "dispatch-fixer", supersede=True,
                           expect_sha256=first["payloadSha256"])
  RC.recover(d)
  assert _read_bytes(first["storePath"]) == before_store
  assert _read_bytes(first["headDiffStorePath"]) == before_blob
  assert _commits_empty(d)


def test_seam_a_supersede_applied_agrees_on_new_revision(tmp_path, adapters, monkeypatch):
  d = _fixer_session(tmp_path, adapters, name="sup-applied")
  head_path = str(tmp_path / "head2.diff")
  with open(head_path, "w", encoding="utf-8") as fh:
    fh.write("second-revision\n")
  _land(d, "dispatch-fixer", payload={"fixes": [], "headDiffPath": head_path})
  first = RD.cmd_record_result(d, "dispatch-fixer")
  assert first["ok"], first
  replacement = {"fixes": ["replaced"], "headDiffPath": head_path}
  _land(d, "dispatch-fixer", payload=replacement)
  _stop_at_kind(monkeypatch, "record-ingest", "applied")
  with pytest.raises(RC.StopPoint):
    RD.cmd_record_result(d, "dispatch-fixer", supersede=True,
                           expect_sha256=first["payloadSha256"])
  RC.recover(d)
  stored, _ = RR.read_json(first["storePath"])
  recorded = [e for e in _outcomes(d, "recorded")
              if e.get("phase") == RD.P_FIXER and e.get("seat") == "dispatch-fixer"]
  assert recorded[-1]["payloadSha256"] == stored["payloadSha256"]
  assert stored["payloadSha256"] != first["payloadSha256"]
  assert _commits_empty(d)


def test_seam_a_record_ingest_recovers_via_driver_command(tmp_path, adapters, monkeypatch):
  d, _head_path, head_text = _record_ingest_setup(tmp_path, adapters)
  _stop_at_kind(monkeypatch, "record-ingest", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_record_result(d, "dispatch-fixer")
  RD.cmd_record_result(d, "dispatch-fixer")
  _assert_record_ingest_agree(d, head_text)
  assert _commits_empty(d)


# --- Group B: orders manifest -----------------------------------------------------------------

@pytest.mark.parametrize("stop_at", ["staged", "sealed", "applied", "done"])
def test_seam_b_orders_manifest_crash_matrix(tmp_path, adapters, monkeypatch, stop_at):
  d = _orders_setup_fresh(tmp_path)
  rnd, phase, attempt = 1, RD.P_PANEL, 0
  before = _snapshot_orders(d, rnd, phase, attempt)
  _stop_at_kind(monkeypatch, "orders-emit", stop_at, n=0)
  with pytest.raises(RC.StopPoint):
    RD.cmd_next(d, _cfg())
  RC.recover(d)
  if stop_at == "staged":
    after = _snapshot_orders(d, rnd, phase, attempt)
    assert after == before
  else:
    _assert_orders_agree(d, rnd, phase, attempt)
  assert _commits_empty(d)


def test_seam_b_orders_manifest_recovers_via_driver_command(tmp_path, adapters, monkeypatch):
  d = _orders_setup_fresh(tmp_path)
  rnd, phase, attempt = 1, RD.P_PANEL, 0
  _stop_at_kind(monkeypatch, "orders-emit", "sealed", n=0)
  with pytest.raises(RC.StopPoint):
    RD.cmd_next(d, _cfg())
  out = RD.cmd_next(d, _cfg())
  assert out["ok"], out
  _assert_orders_agree(d, rnd, phase, attempt)
  assert _commits_empty(d)


# --- Group C: fold (submit-accept) ------------------------------------------------------------

@pytest.mark.parametrize("stop_at", ["staged", "sealed", "applied", "done"])
def test_seam_c_fold_crash_matrix(tmp_path, adapters, monkeypatch, stop_at):
  d = _fold_setup(tmp_path, adapters)
  pend = _pending(d)
  before = _snapshot_fold(d)
  art = _panel_artifact(d)
  _stop_at_kind(monkeypatch, "submit-accept", stop_at)
  with pytest.raises(RC.StopPoint):
    RD.cmd_submit(d, pend["phase"], pend["attempt"], RD.state_hash(_state(d)), art)
  RC.recover(d)
  if stop_at == "staged":
    after = _snapshot_fold(d)
    assert after == before
  else:
    _assert_fold_agree(d, pend["phase"], pend["round"], pend["attempt"])
  assert _commits_empty(d)


def test_seam_c_fold_recovers_via_driver_command(tmp_path, adapters, monkeypatch):
  d = _fold_setup(tmp_path, adapters)
  pend = _pending(d)
  art = _panel_artifact(d)
  _stop_at_kind(monkeypatch, "submit-accept", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_submit(d, pend["phase"], pend["attempt"], RD.state_hash(_state(d)), art)
  out = RD.cmd_submit(d, pend["phase"], pend["attempt"], RD.state_hash(_state(d)), art)
  assert out["ok"], out
  _assert_fold_agree(d, pend["phase"], pend["round"], pend["attempt"])
  assert _commits_empty(d)


# --- Group D: attestation ---------------------------------------------------------------------

@pytest.mark.parametrize("stop_at", ["staged", "sealed", "applied", "done"])
def test_seam_d_attestation_crash_matrix(tmp_path, adapters, monkeypatch, stop_at):
  gitdir = _gitdir(str(tmp_path), "attest-crash")
  d, seq = _orphan_failure(tmp_path, adapters, name="att-crash")
  before = _snapshot_attest(d, gitdir)
  _stop_at_kind(monkeypatch, "attest-finalize", stop_at)
  with pytest.raises(RC.StopPoint):
    RD.cmd_attest(d, str(seq), "orphaned record; handing back uncertified",
                  git=_fake_git(gitdir))
  _recover(d, git=_fake_git(gitdir))
  if stop_at == "staged":
    after = _snapshot_attest(d, gitdir)
    assert after == before
  else:
    _assert_attest_agree(d, gitdir)
  assert _commits_empty(d)


def test_seam_d_attestation_recovers_via_driver_command(tmp_path, adapters, monkeypatch):
  gitdir = _gitdir(str(tmp_path), "attest-driver")
  d, seq = _orphan_failure(tmp_path, adapters, name="att-driver")
  _stop_at_kind(monkeypatch, "attest-finalize", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_attest(d, str(seq), "orphaned record; handing back uncertified",
                  git=_fake_git(gitdir))
  out = RD.cmd_advance(d, git=_fake_git(gitdir))
  assert out["ok"], out
  _assert_attest_agree(d, gitdir)
  assert _commits_empty(d)


# --- Group E: sweep repair --------------------------------------------------------------------

@pytest.mark.parametrize("stop_at", ["staged", "sealed", "applied", "done"])
def test_seam_e_sweep_repair_crash_matrix(tmp_path, adapters, monkeypatch, stop_at):
  d, _head_path, head_text = _sweep_repair_setup(tmp_path, adapters)
  before = _snapshot_sweep_repair(d)
  _stop_at_kind(monkeypatch, "head-diff-bind", stop_at)
  with pytest.raises(RC.StopPoint):
    RD.cmd_record_result(d, sweep=True)
  RC.recover(d)
  if stop_at == "staged":
    after = _snapshot_sweep_repair(d)
    assert after == before
  else:
    _assert_sweep_repair_agree(d, head_text)
  assert _commits_empty(d)


def test_seam_e_sweep_repair_recovers_via_driver_command(tmp_path, adapters, monkeypatch):
  d, _head_path, head_text = _sweep_repair_setup(tmp_path, adapters)
  _stop_at_kind(monkeypatch, "head-diff-bind", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_record_result(d, sweep=True)
  out = RD.cmd_record_result(d, sweep=True)
  assert out["ok"], out
  _assert_sweep_repair_agree(d, head_text)
  assert _commits_empty(d)


# --- Group F: forfeited seam order obligations ------------------------------------------------

def test_recovery_failure_does_not_fall_open(tmp_path, adapters, monkeypatch):
  d_rec = _session(tmp_path, name="rec-fail-record")
  _land(d_rec, "code-reviewer")
  d_miss = _session(tmp_path, name="rec-fail-miss")
  d_sub = _fold_setup(tmp_path, adapters)
  d_next = str(tmp_path / "rec-fail-next")
  os.makedirs(d_next, exist_ok=True)
  d_att, seq = _orphan_failure(tmp_path, adapters, name="rec-fail-att")
  gitdir = _gitdir(str(tmp_path), "rec-fail-att-git")
  d_adv = _session(tmp_path, name="rec-fail-adv")
  _record_all_panel_seats(d_adv)

  def boom(session_dir, **kw):
    raise RC.CommitRefused("intent-unreadable", "synthetic")

  monkeypatch.setattr(RD.round_commit, "recover", boom)

  before_state = _read_bytes(os.path.join(d_rec, RD.STATE_FILE))
  out = RD.cmd_record_result(d_rec, "code-reviewer")
  assert out["ok"] is False and out["reason"] == "commit-recovery-failed"
  assert _read_bytes(os.path.join(d_rec, RD.STATE_FILE)) == before_state

  before_state = _read_bytes(os.path.join(d_miss, RD.STATE_FILE))
  out = RD.cmd_record_missing(d_miss, "code-reviewer", 0, "forfeit")
  assert out["ok"] is False and out["reason"] == "commit-recovery-failed"
  assert _read_bytes(os.path.join(d_miss, RD.STATE_FILE)) == before_state

  pend = _pending(d_sub)
  before_state = _read_bytes(os.path.join(d_sub, RD.STATE_FILE))
  out = RD.cmd_submit(d_sub, pend["phase"], pend["attempt"], RD.state_hash(_state(d_sub)),
                      _panel_artifact(d_sub))
  assert out["ok"] is False and out["reason"] == "commit-recovery-failed"
  assert _read_bytes(os.path.join(d_sub, RD.STATE_FILE)) == before_state

  before_exists = os.path.exists(os.path.join(d_next, RD.STATE_FILE))
  out = RD.cmd_next(d_next, _cfg())
  assert out["ok"] is False and out["reason"] == "commit-recovery-failed"
  assert os.path.exists(os.path.join(d_next, RD.STATE_FILE)) == before_exists

  before_receipt = _read_bytes(os.path.join(d_att, RD.RECEIPT_FILE))
  out = RD.cmd_attest(d_att, str(seq), "note", git=_fake_git(gitdir))
  assert out["ok"] is False and out["reason"] == "commit-recovery-failed"
  assert _read_bytes(os.path.join(d_att, RD.RECEIPT_FILE)) == before_receipt

  before_state = _read_bytes(os.path.join(d_adv, RD.STATE_FILE))
  out = _advance(d_adv, tmp_path)
  assert out["ok"] is False and out["reason"] == "commit-recovery-failed"
  assert _read_bytes(os.path.join(d_adv, RD.STATE_FILE)) == before_state


@pytest.mark.parametrize("cmd_name,runner", [
    ("record-result", lambda d: RD.cmd_record_result(d, "code-reviewer")),
    ("record-missing", lambda d: RD.cmd_record_missing(d, "code-reviewer", 0, "forfeit")),
    ("submit", lambda d: RD.cmd_submit(
        d, _pending(d)["phase"], _pending(d)["attempt"],
        RD.state_hash(_state(d)), _panel_artifact(d))),
    ("next", lambda d: RD.cmd_next(d)),
    ("attest", lambda d, tp: RD.cmd_attest(
        d, str(_seq_of(d, "journal-orphan")), "note",
        git=_fake_git(_gitdir(tp, "lock-att-git")))),
    ("advance", lambda d, tp: _advance(d, tp)),
])
def test_serialization_foreign_lock_refuses(tmp_path, adapters, cmd_name, runner):
  if cmd_name == "submit":
    d = _fold_setup(tmp_path, adapters)
  elif cmd_name == "attest":
    d, _ = _orphan_failure(tmp_path, adapters, name="lock-att")
  elif cmd_name == "advance":
    d = _session(tmp_path, name="lock-adv")
    _record_all_panel_seats(d)
  elif cmd_name == "next":
    d = _session(tmp_path, name="lock-next")
  else:
    d = _session(tmp_path, name="lock-" + cmd_name)
    if cmd_name == "record-result":
      _land(d, "code-reviewer")
  RR.atomic_write_json(RR.session_lock_path(d),
                       {"pid": 424242, "createdAt": "2026-08-07T00:00:00"})
  out = runner(d, str(tmp_path)) if cmd_name in ("attest", "advance") else runner(d)
  assert out["ok"] is False
  expected = "advance-locked" if cmd_name == "advance" else "%s-locked" % cmd_name
  assert out["reason"] == expected
  assert out["holder"] == {"pid": 424242, "createdAt": "2026-08-07T00:00:00"}


def _seq_of(session_dir, reason):
  for index, event in enumerate(_journal(session_dir), start=1):
    if event.get("reason") == reason:
      return index
  raise AssertionError("no journal event with reason %r" % reason)


def test_byte_shape_preservation_save_state_and_receipt(tmp_path, adapters):
  d = _session(tmp_path, name="bytes")
  state = _state(d)
  state["_byteShapeMarker"] = 1
  RD.save_state(d, state)
  state_path = os.path.join(d, RD.STATE_FILE)
  assert open(state_path, "rb").read() == RD._canonical(state).encode("utf-8")

  d_att, seq = _orphan_failure(tmp_path, adapters, name="bytes-att")
  gitdir = _gitdir(str(tmp_path), "bytes-git")
  out = RD.cmd_attest(d_att, str(seq), "orphaned record", git=_fake_git(gitdir))
  assert out["ok"], out
  receipt_path = os.path.join(d_att, RD.RECEIPT_FILE)
  receipt_bytes = open(receipt_path, "rb").read()
  parsed = json.loads(receipt_bytes.decode("utf-8"))
  assert receipt_bytes == (
      json.dumps(parsed, indent=2, sort_keys=True) + "\n").encode("utf-8")


def test_no_raw_os_replace_in_round_driver_source():
  source = open(os.path.join(_LIB, "round_driver.py"), encoding="utf-8").read()
  assert "os.replace" not in source


def test_ordering_argument_removed_from_round_driver_source():
  source = open(os.path.join(_LIB, "round_driver.py"), encoding="utf-8").read()
  assert "published durably FIRST" not in source


# --- Group G: bite-proofs ---------------------------------------------------------------------

def test_biteproof_record_ingest_recovery_neutralized(tmp_path, adapters, monkeypatch):
  d, _head_path, head_text = _record_ingest_setup(tmp_path, adapters)
  _noop_recover(monkeypatch)
  _stop_at_kind(monkeypatch, "record-ingest", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_record_result(d, "dispatch-fixer")
  RD.round_commit.recover(d)
  with pytest.raises(AssertionError):
    _assert_record_ingest_agree(d, head_text)


def test_biteproof_orders_manifest_recovery_neutralized(tmp_path, adapters, monkeypatch):
  d = _orders_setup_fresh(tmp_path)
  _noop_recover(monkeypatch)
  _stop_at_kind(monkeypatch, "orders-emit", "sealed", n=0)
  with pytest.raises(RC.StopPoint):
    RD.cmd_next(d, _cfg())
  RD.round_commit.recover(d)
  manifest_path = RD._orders_manifest_path(d, 1, RD.P_PANEL, 0)
  assert not os.path.exists(manifest_path)


def test_biteproof_fold_recovery_neutralized(tmp_path, adapters, monkeypatch):
  d = _fold_setup(tmp_path, adapters)
  pend = _pending(d)
  _noop_recover(monkeypatch)
  _stop_at_kind(monkeypatch, "submit-accept", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_submit(d, pend["phase"], pend["attempt"], RD.state_hash(_state(d)),
                  _panel_artifact(d))
  RD.round_commit.recover(d)
  with pytest.raises(AssertionError):
    _assert_fold_agree(d, pend["phase"], pend["round"], pend["attempt"])


def test_biteproof_attestation_recovery_neutralized(tmp_path, adapters, monkeypatch):
  gitdir = _gitdir(str(tmp_path), "bite-att")
  d, seq = _orphan_failure(tmp_path, adapters, name="bite-att")
  _noop_recover(monkeypatch)
  _stop_at_kind(monkeypatch, "attest-finalize", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_attest(d, str(seq), "orphaned record", git=_fake_git(gitdir))
  RD.round_commit.recover(d)
  with pytest.raises(AssertionError):
    _assert_attest_agree(d, gitdir)


def test_biteproof_sweep_repair_recovery_neutralized(tmp_path, adapters, monkeypatch):
  d, _head_path, head_text = _sweep_repair_setup(tmp_path, adapters)
  _noop_recover(monkeypatch)
  _stop_at_kind(monkeypatch, "head-diff-bind", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_record_result(d, sweep=True)
  RD.round_commit.recover(d)
  pend = _pending(d)
  spath = RR.store_path(d, pend["round"], pend["phase"],
                        RR.storage_key("dispatch-fixer"), pend["attempt"])
  stored, err = RR.read_json(spath)
  assert err is None
  assert "headDiffStorePath" not in (stored.get("payload") or {})


# --- Group H: driver-path recovery bite-proofs ----------------------------------------------

def test_biteproof_seam_a_driver_recovery_not_wired(tmp_path, adapters, monkeypatch):
  d, _head_path, head_text = _record_ingest_setup(tmp_path, adapters)
  _stop_at_kind(monkeypatch, "record-ingest", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_record_result(d, "dispatch-fixer")
  _noop_driver_recover(monkeypatch)
  RD.cmd_record_result(d, "dispatch-fixer")
  assert not _commits_empty(d)


def test_biteproof_seam_b_driver_recovery_not_wired(tmp_path, adapters, monkeypatch):
  d = _orders_setup_fresh(tmp_path)
  _stop_at_kind(monkeypatch, "orders-emit", "sealed", n=0)
  with pytest.raises(RC.StopPoint):
    RD.cmd_next(d, _cfg())
  _noop_driver_recover(monkeypatch)
  RD.cmd_next(d, _cfg())
  assert not _commits_empty(d)


def test_biteproof_seam_c_driver_recovery_not_wired(tmp_path, adapters, monkeypatch):
  d = _fold_setup(tmp_path, adapters)
  pend = _pending(d)
  art = _panel_artifact(d)
  _stop_at_kind(monkeypatch, "submit-accept", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_submit(d, pend["phase"], pend["attempt"], RD.state_hash(_state(d)), art)
  _noop_driver_recover(monkeypatch)
  RD.cmd_submit(d, pend["phase"], pend["attempt"], RD.state_hash(_state(d)), art)
  assert not _commits_empty(d)


def test_biteproof_seam_d_driver_recovery_not_wired(tmp_path, adapters, monkeypatch):
  gitdir = _gitdir(str(tmp_path), "bite-att-driver")
  d, seq = _orphan_failure(tmp_path, adapters, name="bite-att-driver")
  _stop_at_kind(monkeypatch, "attest-finalize", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_attest(d, str(seq), "orphaned record", git=_fake_git(gitdir))
  _noop_driver_recover(monkeypatch)
  RD.cmd_advance(d, git=_fake_git(gitdir))
  with pytest.raises(AssertionError):
    _assert_attest_agree(d, gitdir)


def test_biteproof_seam_e_driver_recovery_not_wired(tmp_path, adapters, monkeypatch):
  d, _head_path, head_text = _sweep_repair_setup(tmp_path, adapters)
  _stop_at_kind(monkeypatch, "head-diff-bind", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_record_result(d, sweep=True)
  _noop_driver_recover(monkeypatch)
  RD.cmd_record_result(d, sweep=True)
  assert not _commits_empty(d)


# --- FIX-3 review round 1 (#918) -------------------------------------------------------------

def _sealed_attest_commit(tmp_path, adapters, monkeypatch, name="r5"):
  gitdir = _gitdir(str(tmp_path), name + "-git")
  d, seq = _orphan_failure(tmp_path, adapters, name=name)
  _stop_at_kind(monkeypatch, "attest-finalize", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_attest(d, str(seq), "orphaned record", git=_fake_git(gitdir))
  assert not _commits_empty(d)
  return d, seq, gitdir


def _sidecar_path(gitdir):
  return os.path.join(gitdir, "superheroes", "review-receipt.json")


def test_r3_attest_replays_orders_emit_before_state_use(tmp_path, adapters, monkeypatch):
  d = _orders_setup_fresh(tmp_path)
  _stop_at_kind(monkeypatch, "orders-emit", "sealed", n=0)
  with pytest.raises(RC.StopPoint):
    RD.cmd_next(d, _cfg())
  manifest_path = RD._orders_manifest_path(d, 1, RD.P_PANEL, 0)
  assert not os.path.exists(manifest_path)
  assert not _commits_empty(d)
  RD.cmd_attest(d, "1", "note")
  assert os.path.exists(manifest_path)
  anchor = RD._orders_anchor(_state(d), d, 1, RD.P_PANEL, 0)
  assert anchor is not None
  assert anchor["manifestSha256"] == hashlib.sha256(_read_bytes(manifest_path)).hexdigest()
  assert _commits_empty(d)


def test_r3_attest_terminal_check_sees_recovery_replay(tmp_path, adapters, monkeypatch):
  gitdir = _gitdir(str(tmp_path), "r3-term-git")
  d, seq = _orphan_failure(tmp_path, adapters, name="r3-term")
  _stop_at_kind(monkeypatch, "attest-finalize", "applied")
  with pytest.raises(RC.StopPoint):
    RD.cmd_attest(d, str(seq), "first note", git=_fake_git(gitdir))
  os.remove(os.path.join(d, RD.RECEIPT_FILE))
  state = _state(d)
  state.pop("terminal", None)
  RD.save_state(d, state)
  out = RD.cmd_attest(d, str(seq), "second note", git=_fake_git(gitdir))
  assert out["ok"] is False
  assert out["reason"] == "terminal-receipt-exists"


def test_r4_sweep_record_refuses_on_head_diff_commit_refused(tmp_path, adapters, monkeypatch):
  d, _head_path, head_text = _sweep_repair_setup(tmp_path, adapters)
  out = RD.cmd_record_result(d, sweep=True)
  assert out["ok"] is True

  d2 = _fixer_session(tmp_path, adapters, name="r4-refuse")
  head_path2 = str(tmp_path / "r4-head.diff")
  with open(head_path2, "w", encoding="utf-8") as fh:
    fh.write("diff --git a/f.py b/f.py\n+sweep-fixed\n")
  _land(d2, "dispatch-fixer", payload={"fixes": [], "headDiffPath": head_path2})
  out_rec = RD.cmd_record_result(d2, "dispatch-fixer")
  assert out_rec["ok"], out_rec
  spath = out_rec["storePath"]
  blob = out_rec["headDiffStorePath"]
  stored, _ = RR.read_json(spath)
  del stored["payload"]["headDiffStorePath"]
  RR.atomic_write_json(spath, stored)
  os.remove(blob)

  def _refuse(*_a, **_k):
    raise RC.CommitRefused("commit-id-collision", "synthetic")

  monkeypatch.setattr(RD, "_store_head_diff", _refuse)
  out2 = RD.cmd_record_result(d2, sweep=True)
  assert out2["ok"] is False
  assert out2["reason"] == "commit-id-collision"


@pytest.mark.parametrize("cmd_name,runner", [
    ("next", lambda d, gitdir: RD.cmd_next(d)),
    ("submit", lambda d, gitdir: RD.cmd_submit(
        d, _pending(d)["phase"], _pending(d)["attempt"],
        RD.state_hash(_state(d)), _panel_artifact(d))),
    ("record-result", lambda d, gitdir: RD.cmd_record_result(d, "code-reviewer")),
    ("record-missing", lambda d, gitdir: RD.cmd_record_missing(
        d, "security-reviewer", _pending(d)["attempt"], "forfeit")),
])
def test_r5_commands_replay_attest_sidecar_commit(tmp_path, adapters, monkeypatch,
                                                  cmd_name, runner):
  d, seq, gitdir = _sealed_attest_commit(tmp_path, adapters, monkeypatch, name="r5-" + cmd_name)
  monkeypatch.setattr(RD.store_core, "get_worktree_gitdir",
                      lambda repo_root, run=None: gitdir)
  monkeypatch.setattr(RD.store_core, "run_git", _fake_git(gitdir))
  sidecar = _sidecar_path(gitdir)
  assert not os.path.exists(sidecar)
  runner(d, gitdir)
  assert _commits_empty(d)
  assert os.path.exists(sidecar)
