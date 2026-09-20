"""#1272 WO-2: one chokepoint for every `recorded` journal row."""
import glob
import importlib
import importlib.util
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


RD = _load("round_driver")
RR = _load("round_records")
RC = _load("round_commit")
RCE = _load("round_certification")
TRI = importlib.import_module("test_round_driver_integration")

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
HEAD_SHA = "abc123def4567890abcdef1234567890abcdef12"
SEAT_MAP = {"seats": {dim: {"vendor": "claude", "model": "sonnet-5", "engine": "claude"}
                      for dim in RD.DIMENSIONS}}


class FakeAdapters(object):
    ADAPTER_PHASES = (RD.P_PANEL, RD.P_VERIFIERS, RD.P_SYNTHESIS, RD.P_GAPSWEEP, RD.P_AUDITS,
                      RD.P_SCOPED, RD.P_VERIFY, RD.P_FIXER)

    def __init__(self):
        self.rosters = {RD.P_PANEL: list(RD.DIMENSIONS),
                        RD.P_VERIFIERS: [],
                        RD.P_SYNTHESIS: ["synthesis"],
                        RD.P_FIXER: ["dispatch-fixer"],
                        RD.P_VERIFY: ["verify"]}
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

    def is_orchestrator_fulfilled(self, phase):
        return phase in (RD.P_VERIFY,)

    def orchestrator_payload_fault(self, phase, payload):
        if phase == RD.P_VERIFY:
            return RD.verify_result_fault(payload)
        return "orchestrator-payload-unknown-phase:%s" % phase

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
                seat_key = env.get("seat")
                if env.get("schema") == RR.SEAT_MISSING_SCHEMA:
                    seats[seat_key] = {"findings": [], "missing": True}
                else:
                    seats[seat_key] = env.get("payload") or {"findings": []}
            return {"seats": seats}, None
        if phase == RD.P_VERIFIERS:
            verdicts = []
            for env in (envelopes or []):
                if not isinstance(env, dict):
                    continue
                if env.get("schema") == RR.SEAT_MISSING_SCHEMA:
                    continue
                payload = env.get("payload")
                if not isinstance(payload, dict):
                    continue
                for verdict in payload.get("verdicts") or []:
                    if isinstance(verdict, dict):
                        verdicts.append(dict(verdict))
            return {"verdicts": verdicts}, None
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}, None
        if phase == RD.P_VERIFY:
            for env in (envelopes or []):
                if isinstance(env, dict) and env.get("schema") != RR.SEAT_MISSING_SCHEMA:
                    return dict(env.get("payload") or {"result": "pass"}), None
            return None, "missing-verify"
        return {}, None


@pytest.fixture
def adapters(monkeypatch):
    fake = FakeAdapters()
    monkeypatch.setitem(sys.modules, "round_adapters", fake)
    return fake


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude",
            "seatMap": SEAT_MAP, "headSha": HEAD_SHA}
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


def _journal_bytes(session_dir):
    path = os.path.join(session_dir, RD.JOURNAL_FILE)
    with open(path, "rb") as fh:
        return fh.read()


def _anchor_hashes(session_dir, rnd, phase, attempt, seat, occurrence=0):
    anchor = RD._orders_anchor(_state(session_dir), session_dir, rnd, phase, attempt)
    if anchor is None:
        return RR.NOT_EMITTED, RR.NOT_EMITTED
    skey = RR.storage_key(seat, occurrence)
    return anchor["manifestSha256"], (anchor.get("orders") or {}).get(skey, RR.NOT_EMITTED)


def _execution_evidence(**over):
    evidence = {
        "source": "runner",
        "runnerNonce": "nonce-1",
        "recordDigest": "digest-1",
        "resultKind": "findings",
        "resultDigest": RR.payload_sha256([]),
        "observation": {
            "tokens": None,
            "toolCalls": None,
            "stdoutBytes": 0,
            "wallSeconds": 0.0,
            "source": "none",
            "read": "unknown",
            "telemetry": "none",
        },
    }
    evidence.update(over)
    return evidence


def _result_envelope(session_dir, seat, payload=None, pend=None, occurrence=0, **over):
    pend = pend or _pending(session_dir)
    payload = {"findings": [], "confidence": "high", "seat": seat,
               "verificationReceipt": {"ran": True}} if payload is None else payload
    manifest_sha, order_sha = _anchor_hashes(session_dir, pend["round"], pend["phase"],
                                             pend["attempt"], seat, occurrence=occurrence)
    schema = RR.seat_result_schema_for_state_version(_state(session_dir).get("schemaVersion"))
    if schema is None:
        schema = RR.SEAT_RESULT_SCHEMA
    env = {
        "schema": schema,
        "session": _session_id(session_dir),
        "round": pend["round"],
        "phase": pend["phase"],
        "seat": seat,
        "attempt": pend["attempt"],
        "vendor": "claude",
        "model": "sonnet-5",
        "dispatchRef": manifest_sha,
        "orderSha256": order_sha,
        "manifestSha256": manifest_sha,
        "recordedAt": "2026-08-07T00:00:00",
        "payloadSha256": RR.payload_sha256(payload),
        "payload": payload,
    }
    if schema == RR.SEAT_RESULT_SCHEMA_V2:
        evidence = _execution_evidence()
        env["executionEvidence"] = evidence
        env["provenance"] = RR.PROVENANCE_HAND_LANDED
        env["envelopeSha256"] = RR.envelope_sha256(payload, evidence)
        if HEAD_SHA:
            env["headSha"] = HEAD_SHA
    if occurrence:
        env["occurrence"] = occurrence
    env.update(over)
    if schema == RR.SEAT_RESULT_SCHEMA_V2 and "executionEvidence" in over:
        env["envelopeSha256"] = RR.envelope_sha256(payload, env["executionEvidence"])
    return env


def _land(session_dir, seat, payload=None, pend=None, occurrence=0, **over):
    pend = pend or _pending(session_dir)
    env = _result_envelope(session_dir, seat, payload=payload, pend=pend, occurrence=occurrence,
                           **over)
    path = RR.landing_path(session_dir, pend["round"], pend["phase"], RR.storage_key(seat),
                           pend["attempt"])
    RR.atomic_write_json(path, env)
    return path, env


def _land_and_record(session_dir, seat, payload=None, **over):
    _land(session_dir, seat, payload=payload, **over)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"], out
    return out


def _record_all_panel_seats(session_dir, seats=None):
    for seat in (seats if seats is not None else RD.DIMENSIONS):
        _land_and_record(session_dir, seat)


def _advance(session_dir, tmp_path):
    return RD.cmd_advance(session_dir, git=str(tmp_path / "git"))


def _recorded_rows(session_dir):
    return [e for e in RD.read_journal(session_dir) if e.get("outcome") == "recorded"]


def _assert_revision_identity(row):
    for field in RR.REVISION_IDENTITY_FIELDS:
        assert field in row, "recorded row missing %r: %r" % (field, row)


def _complete_recorded_row(pend, **over):
    row = {
        "phase": pend["phase"],
        "round": pend["round"],
        "attempt": pend["attempt"],
        "seat": "code-reviewer",
        "payloadSha256": "x" * 64,
        "casToken": RR.MISSING_CAS_TOKEN,
        "executionEvidence": _execution_evidence(),
        "provenance": RR.PROVENANCE_HAND_LANDED,
        "envelopeSha256": "y" * 64,
        "executionEvidencePresent": True,
        "citedHead": HEAD_SHA,
    }
    row.update(over)
    return row


@pytest.mark.parametrize("missing_field", RR.REVISION_IDENTITY_FIELDS)
def test_recorded_row_missing_one_identity_field_refused_at_sinks(tmp_path, missing_field):
    """T1 — omitting any one revision-identity field is refused at both sinks; journal unchanged."""
    d = _session(tmp_path)
    pend = _pending(d)
    before = _journal_bytes(d)
    partial = _complete_recorded_row(pend)
    del partial[missing_field]
    with pytest.raises(RD.round_records.IncompleteRevisionIdentity) as excinfo:
        RD._journal_event(d, "record-result", "recorded", **partial)
    assert excinfo.value.missing == (missing_field,)
    assert _journal_bytes(d) == before

    journal = os.path.join(d, RD.JOURNAL_FILE)
    with pytest.raises(RC.CommitRefused) as excinfo:
        RC.begin(d, "test").add_journal_append(
            journal, {"cmd": "record-result", "outcome": "recorded", **partial})
    assert excinfo.value.reason == "recorded-row-incomplete"
    assert excinfo.value.detail == missing_field
    assert _journal_bytes(d) == before


def test_real_record_paths_carry_complete_revision_identity(tmp_path, adapters):
    """T2 — record-result, sweep, record-missing, and advance rows carry every identity key."""
    d = _session(tmp_path)
    pend = _pending(d)
    seat = "code-reviewer"
    evidence = _execution_evidence(runnerNonce="nonce-dispatch")
    _land(d, seat, provenance=RR.PROVENANCE_DISPATCH_OBSERVED, executionEvidence=evidence,
          headSha=HEAD_SHA)
    out = RD.cmd_record_result(d, seat)
    assert out["ok"], out
    rows = [e for e in _recorded_rows(d) if e.get("cmd") == "record-result" and e.get("seat") == seat]
    assert rows
    row = rows[-1]
    _assert_revision_identity(row)
    anchor = RD._orders_anchor(_state(d), d, pend["round"], pend["phase"], pend["attempt"])
    assert row["citedHead"] == anchor.get("headSha") == HEAD_SHA

    missing_seat = "security-reviewer"
    sweep_seat = "test-reviewer"
    for other in RD.DIMENSIONS:
        if other not in (seat, missing_seat, sweep_seat):
            _land_and_record(d, other)
    _land(d, sweep_seat)
    state = _state(d)
    anchor = RD._orders_anchor(state, d, pend["round"], pend["phase"], pend["attempt"])
    schema = RR.seat_result_schema_for_state_version(state.get("schemaVersion"))
    sweep_results = RR.sweep_landing(
        d, pend["round"], pend["phase"], current_attempt=pend["attempt"],
        roster=list(RD.DIMENSIONS), anchor=anchor, seat_result_schema=schema)
    assert any(r.get("ok") and r.get("seatKey") == sweep_seat and r.get("reason") is None
               for r in sweep_results), sweep_results

    missing_out = RD.cmd_record_missing(d, missing_seat, pend["attempt"], "forfeit")
    assert missing_out["ok"], missing_out
    missing_rows = [e for e in _recorded_rows(d)
                    if e.get("cmd") == "record-missing" and e.get("seat") == missing_seat]
    assert missing_rows
    _assert_revision_identity(missing_rows[-1])
    assert missing_rows[-1]["casToken"] == RR.MISSING_CAS_TOKEN
    assert missing_rows[-1]["payloadSha256"] is None

    adv = _advance(d, tmp_path)
    assert adv["ok"], adv
    rows_from_advance = [r for r in _recorded_rows(d) if r.get("cmd") == "advance"]
    assert rows_from_advance
    for row in rows_from_advance:
        _assert_revision_identity(row)


def test_anchor_check_head_sha_edges():
    """T3 — envelope headSha vs anchor head (E6)."""
    skey = RR.storage_key("seat")
    anchor = {"manifestSha256": RR.NOT_EMITTED,
              "orders": {skey: RR.NOT_EMITTED}, "headSha": HEAD_SHA}
    env_match = {"manifestSha256": RR.NOT_EMITTED, "orderSha256": RR.NOT_EMITTED,
                 "headSha": HEAD_SHA}
    assert RR._anchor_check(env_match, "seat", anchor) is None

    env_mismatch = dict(env_match)
    env_mismatch["headSha"] = "f" * 40
    assert RR._anchor_check(env_mismatch, "seat", anchor) == "head-anchor-mismatch"

    anchor_headless = {"manifestSha256": RR.NOT_EMITTED, "orders": {skey: RR.NOT_EMITTED}}
    assert RR._anchor_check(env_match, "seat", anchor_headless) == "head-anchor-unanchored"

    env_no_head = {"manifestSha256": RR.NOT_EMITTED, "orderSha256": RR.NOT_EMITTED}
    assert RR._anchor_check(env_no_head, "seat", anchor_headless) is None


def test_sweep_refuses_when_store_unreadable_before_journal(tmp_path, adapters, monkeypatch):
    """T4 — sweep refuses `recorded-row-store-unreadable` when store read fails before journal."""
    d = _session(tmp_path)
    seat = "code-reviewer"
    _land(d, seat)
    pend = _pending(d)
    spath = RR.store_path(d, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"])
    real_read = RD.round_records.read_json

    def fake_read(path):
        if path == spath and os.path.exists(path):
            return None, "unreadable"
        return real_read(path)

    monkeypatch.setattr(RD.round_records, "read_json", fake_read)
    before_rows = len(_recorded_rows(d))
    out = RD.cmd_record_result(d, sweep=True)
    assert out["ok"] is False
    assert out["reason"] == "recorded-row-store-unreadable"
    assert len(_recorded_rows(d)) == before_rows


def test_reappend_slotless_storage_key_produces_complete_recorded_row(tmp_path, adapters):
    """Slot-less reappend with a readable store produces a complete recorded row; advance proceeds."""
    d = _session(tmp_path)
    ghost_seat = "ghost-reviewer"
    ghost_skey = RR.storage_key(ghost_seat)
    _record_all_panel_seats(d)
    pend = _pending(d)
    env = _result_envelope(d, ghost_seat,
                           payload={"findings": [], "confidence": "high", "seat": ghost_seat})
    spath = RR.store_path(d, pend["round"], pend["phase"], ghost_skey, pend["attempt"])
    os.makedirs(os.path.dirname(spath), exist_ok=True)
    RR.atomic_write_json(spath, env)
    out = _advance(d, tmp_path)
    assert out["ok"], out
    reappended = [e for e in _recorded_rows(d)
                  if e.get("reappended") is True and e.get("seat") is None]
    assert len(reappended) == 1
    _assert_revision_identity(reappended[0])


def test_reappend_slotless_missing_store_refuses(tmp_path, adapters, monkeypatch):
    """Slot-less reappend whose store file is absent refuses recorded-row-store-unreadable."""
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    pend = _pending(d)
    ghost_skey = RR.storage_key("ghost-reviewer")
    real_reconcile = RR.reconcile

    def fake_reconcile(session_dir, rnd, phase, journal_identities):
        result = real_reconcile(session_dir, rnd, phase, journal_identities)
        result = dict(result)
        result["reappend"] = list(result.get("reappend") or []) + [{
            "storageKey": ghost_skey,
            "attempt": pend["attempt"],
            "path": RR.store_path(session_dir, rnd, phase, ghost_skey, pend["attempt"]),
        }]
        return result

    monkeypatch.setattr(RD.round_records, "reconcile", fake_reconcile)
    before_rows = len(_recorded_rows(d))
    out = _advance(d, tmp_path)
    assert out["ok"] is False
    assert out["reason"] == "recorded-row-store-unreadable"
    assert len(_recorded_rows(d)) == before_rows


def _bootstrap_head_before_next(tmp_path, name="pre-head", **cfg_over):
    """Session bootstrap with meta headSha present before the first `next` (production shape)."""
    session_dir = str(tmp_path / name)
    os.makedirs(session_dir, exist_ok=True)
    gitdir = str(tmp_path / (name + "-gitdir"))
    os.makedirs(gitdir, exist_ok=True)
    head_diff_path = str(tmp_path / (name + "-head.diff"))
    with open(head_diff_path, "w", encoding="utf-8") as fh:
        fh.write(TRI.HEAD_DIFF)
    head_sha = TRI._fake_git(gitdir)(session_dir, "rev-parse", "HEAD")
    meta_path = os.path.join(session_dir, RR.META_FILE)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump({"headSha": head_sha}, fh, sort_keys=True)
        fh.write("\n")
    out = RD.cmd_next(session_dir, TRI._cfg(**cfg_over))
    assert out["ok"], out
    return session_dir, gitdir, head_diff_path, head_sha


def test_real_loop_dispatch_observed_row_carries_cited_head_matching_certified_head(tmp_path):
    """Real-loop producer: the pre-next meta head binds `citedHead`; with every seat's evidence engaged the zero-finding loop certifies on that head."""
    seat_map = {
        "seats": {
            dim: {"vendor": "codex", "model": "gpt-5.6-sol", "engine": "codex"}
            for dim in RD.DIMENSIONS
        }
    }
    session_dir, gitdir, head_path, head_sha = _bootstrap_head_before_next(
        tmp_path,
        name="cited-head-producer",
        seatMap=seat_map,
        vendors=["codex"],
        baseGuard=RCE.BASE_GUARD_CHECKED,
    )
    folded = TRI._drive_to_terminal_with_panel_dispatch_evidence(
        session_dir, tmp_path, gitdir, [], head_path, evidence_read="engaged")
    assert RD.P_PANEL in folded
    journal = RD.read_journal(session_dir)
    recorded = [row for row in journal
                if row.get("outcome") == "recorded"
                and row.get("seat") == TRI.FINDING_SEAT
                and row.get("phase") == RD.P_PANEL
                and row.get("provenance") == RR.PROVENANCE_DISPATCH_OBSERVED]
    assert recorded, journal
    ctx, load_refusal = RCE._load_context(session_dir)
    assert load_refusal is None, load_refusal
    certified_head = RCE._certified_head_sha(ctx)
    assert recorded[0]["citedHead"] == certified_head == head_sha
    receipt, refusal = RCE.certify(session_dir)
    assert refusal is None, refusal
    assert isinstance(receipt, dict)
    assert certified_head == head_sha
    assert receipt["terminalState"] == "certified"


def test_real_loop_hand_landed_unknown_read_refuses_execution_evidence_not_engaged(tmp_path):
    """Hand-landed seats with read unknown must not satisfy the read-engagement bar."""
    seat_map = {
        "seats": {
            dim: {"vendor": "codex", "model": "gpt-5.6-sol", "engine": "codex"}
            for dim in RD.DIMENSIONS
        }
    }
    session_dir, gitdir, head_path, head_sha = _bootstrap_head_before_next(
        tmp_path,
        name="cited-head-not-engaged",
        seatMap=seat_map,
        vendors=["codex"],
        baseGuard=RCE.BASE_GUARD_CHECKED,
    )
    TRI._drive_to_terminal_with_panel_dispatch_evidence(
        session_dir, tmp_path, gitdir, [], head_path, evidence_read="unknown")
    receipt, refusal = RCE.certify(session_dir)
    assert receipt is None, receipt
    assert refusal is not None
    assert refusal["bindingFailure"] == "execution-evidence-not-engaged"


def test_journal_revision_helpers_removed_from_lib():
    """T5 — grep DoD: no `_journal_revision_fields` / `_journal_stored_revision` in lib/*.py."""
    paths = glob.glob(os.path.join(_LIB, "*.py"))
    hits = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if "_journal_revision_fields" in line or "_journal_stored_revision" in line:
                    hits.append("%s:%d:%s" % (path, lineno, line.rstrip()))
    assert hits == []
