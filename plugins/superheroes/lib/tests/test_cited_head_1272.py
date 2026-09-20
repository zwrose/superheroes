"""#1272 layer 1c: runner-observed cited head and citedHeadSource."""
import importlib.util
import json
import os
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import engine_dispatch  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import session_contract  # noqa: E402

from test_recorded_row_chokepoint_1272 import (  # noqa: E402
    HEAD_SHA,
    FakeAdapters,
    _advance,
    _land,
    _pending,
    _record_all_panel_seats,
    _result_envelope,
    _session,
    _state,
)

_TDI_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_TDI_SPEC)
_TDI_SPEC.loader.exec_module(_TDI)

_TSP_SPEC = importlib.util.spec_from_file_location(
    "test_seat_provenance_1272",
    os.path.join(_HERE, "test_seat_provenance_1272.py"))
_TSP = importlib.util.module_from_spec(_TSP_SPEC)
_TSP_SPEC.loader.exec_module(_TSP)

ANCHOR_HEAD = HEAD_SHA
PANEL_FINDING = [{"dimension": "d", "taxonomy": "t", "title": "x"}]
PANEL_PAYLOAD = {"findings": PANEL_FINDING}


@pytest.fixture
def adapters(monkeypatch):
    fake = FakeAdapters()
    monkeypatch.setitem(sys.modules, "round_adapters", fake)
    return fake


def _observation():
    return {
        "tokens": None,
        "toolCalls": 1,
        "stdoutBytes": 10,
        "wallSeconds": 0.1,
        "source": "codex-events",
        "read": "engaged",
        "telemetry": "tool-calls",
    }


def _panel_envelope(order_sha=None):
    order_sha = order_sha or ("a" * 64)
    return {
        "phase": RD.P_PANEL,
        "orderSha256": order_sha,
        "payload": PANEL_PAYLOAD,
    }


def _runner_record(**over):
    digest = RR.payload_sha256(PANEL_FINDING)
    base = {
        "orderPromptSha256": "a" * 64,
        "source": "codex",
        "runnerNonce": "nonce-cited-head",
        "recordDigest": "d" * 64,
        "observation": _observation(),
        "resultDigest": digest,
        "resultKind": "findings",
        "runKind": engine_dispatch.RUN_KIND_REVIEW,
        "viewHeadSha": ANCHOR_HEAD,
    }
    base.update(over)
    return base


def _assemble_with_record(tmp_path, envelope, record, anchor_head=ANCHOR_HEAD):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir, exist_ok=True)
    real = engine_dispatch.run_execution_record

    def _patched(_run_dir):
        return record, None

    engine_dispatch.run_execution_record = _patched
    try:
        return RD._assemble_dispatch_evidence(session_dir, envelope, "fake-run", anchor_head)
    finally:
        engine_dispatch.run_execution_record = real


def _recorded_count(session_dir):
    return sum(1 for row in RD.read_journal(session_dir) if row.get("outcome") == "recorded")


def _store_exists(session_dir, seat):
    pend = _pending(session_dir)
    spath = RR.store_path(session_dir, pend["round"], pend["phase"],
                          RR.storage_key(seat), pend["attempt"])
    return os.path.exists(spath)


def test_assemble_refuses_when_run_kind_absent(tmp_path):
    record = _runner_record(viewHeadSha=ANCHOR_HEAD)
    del record["runKind"]
    assembled, refusal, extra, source = _assemble_with_record(
        tmp_path, _panel_envelope(), record)
    assert assembled is None
    assert source is None
    assert refusal == "view-head-underivable"
    assert extra == {"runKind": None}


def test_assemble_refuses_when_run_kind_null(tmp_path):
    record = _runner_record(runKind=None, viewHeadSha=ANCHOR_HEAD)
    assembled, refusal, extra, source = _assemble_with_record(
        tmp_path, _panel_envelope(), record)
    assert assembled is None
    assert source is None
    assert refusal == "view-head-underivable"
    assert extra == {"runKind": None}


def test_assemble_refuses_when_run_kind_boolean(tmp_path):
    record = _runner_record(runKind=True, viewHeadSha=ANCHOR_HEAD)
    assembled, refusal, extra, source = _assemble_with_record(
        tmp_path, _panel_envelope(), record)
    assert assembled is None
    assert source is None
    assert refusal == "view-head-underivable"
    assert extra == {"runKind": True}


def test_assemble_refuses_when_run_kind_unknown_string(tmp_path):
    record = _runner_record(runKind="probe", viewHeadSha=ANCHOR_HEAD)
    assembled, refusal, extra, source = _assemble_with_record(
        tmp_path, _panel_envelope(), record)
    assert assembled is None
    assert source is None
    assert refusal == "view-head-underivable"
    assert extra == {"runKind": "probe"}


def test_assemble_refuses_review_when_view_head_missing(tmp_path):
    record = _runner_record(viewHeadSha=None)
    assembled, refusal, extra, source = _assemble_with_record(
        tmp_path, _panel_envelope(), record)
    assert assembled is None
    assert source is None
    assert refusal == "view-head-underivable"
    assert extra == {"runKind": engine_dispatch.RUN_KIND_REVIEW}


def test_assemble_refuses_review_when_view_head_empty(tmp_path):
    record = _runner_record(viewHeadSha="")
    assembled, refusal, extra, source = _assemble_with_record(
        tmp_path, _panel_envelope(), record)
    assert assembled is None
    assert source is None
    assert refusal == "view-head-underivable"
    assert extra == {"runKind": engine_dispatch.RUN_KIND_REVIEW}


@pytest.mark.parametrize("anchor_head", [None, ""])
def test_assemble_refuses_review_when_anchor_cited_head_missing(tmp_path, anchor_head):
    record = _runner_record()
    assembled, refusal, extra, source = _assemble_with_record(
        tmp_path, _panel_envelope(), record, anchor_head=anchor_head)
    assert assembled is None
    assert source is None
    assert refusal == "view-head-underivable"
    assert extra == {"runKind": engine_dispatch.RUN_KIND_REVIEW, "anchorCitedHead": anchor_head}


def test_assemble_refuses_when_landed_envelope_head_sha_disagrees_with_view(tmp_path):
    record = _runner_record()
    envelope = _panel_envelope()
    envelope["headSha"] = "f" * 40
    assembled, refusal, extra, source = _assemble_with_record(
        tmp_path, envelope, record)
    assert assembled is None
    assert source is None
    assert refusal == "head-anchor-mismatch"
    assert extra == {"envelopeHeadSha": "f" * 40, "viewHeadSha": ANCHOR_HEAD}


def test_assemble_refuses_review_when_view_head_differs_from_anchor(tmp_path):
    record = _runner_record(viewHeadSha="f" * 40)
    assembled, refusal, extra, source = _assemble_with_record(
        tmp_path, _panel_envelope(), record)
    assert assembled is None
    assert source is None
    assert refusal == "view-head-anchor-mismatch"
    assert extra == {"viewHeadSha": "f" * 40, "anchorCitedHead": ANCHOR_HEAD}


def test_assemble_write_run_declares_order_anchor_without_view_head(tmp_path):
    fixes = [{"file": "a.py", "description": "x"}]
    record = _runner_record(
        runKind=engine_dispatch.RUN_KIND_WRITE,
        viewHeadSha=None,
        resultKind=session_contract.WRITE_RESULT_KIND,
        resultDigest=RR.payload_sha256(fixes),
    )
    envelope = {
        "orderSha256": "a" * 64,
        "payload": {"fixes": fixes},
    }
    assembled, refusal, extra, source = _assemble_with_record(
        tmp_path, envelope, record, anchor_head=ANCHOR_HEAD)
    assert refusal is None, extra
    assert assembled is not None
    assert source == RR.CITED_HEAD_SOURCE_ORDER_ANCHOR
    assert "headSha" not in assembled


def test_recorded_row_fields_rejects_missing_or_unknown_cited_head_source():
    envelope = {"schema": RR.SEAT_RESULT_SCHEMA_V2, "payload": {"findings": []},
                "payloadSha256": "x" * 64}
    with pytest.raises(RR.IncompleteRevisionIdentity) as excinfo:
        RR.recorded_row_fields(envelope, ANCHOR_HEAD, None)
    assert excinfo.value.missing == ("citedHeadSource",)
    with pytest.raises(RR.IncompleteRevisionIdentity) as excinfo:
        RR.recorded_row_fields(envelope, ANCHOR_HEAD, "hand-typed")
    assert excinfo.value.missing == ("citedHeadSource",)


def _run_dir_with_opened_view_meta(tmp_path, view_meta, base_sha=None):
    order_path = str(tmp_path / "order.txt")
    with open(order_path, "w", encoding="utf-8") as fh:
        fh.write("Review.\n")
    run_dir = _TDI._execution_run_dir(tmp_path, order_path, PANEL_FINDING, view_head_sha=ANCHOR_HEAD)
    journal_path = engine_dispatch._journal_path(os.path.realpath(run_dir))
    records, _ = engine_dispatch._journal_read(run_dir)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for rec in records:
            if rec.get("kind") == "run-opened":
                if view_meta is not None:
                    rec["viewMeta"] = view_meta
                else:
                    rec.pop("viewMeta", None)
                if base_sha is not None:
                    rec["baseSha"] = base_sha
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    return run_dir


def test_run_execution_record_view_head_from_view_meta_dict(tmp_path):
    run_dir = _run_dir_with_opened_view_meta(tmp_path, {"headSha": "meta-head-sha"})
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    assert record["viewHeadSha"] == "meta-head-sha"


def test_run_execution_record_view_head_falls_back_to_base_sha(tmp_path):
    run_dir = _run_dir_with_opened_view_meta(tmp_path, "not-a-dict", base_sha="base-head-sha")
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    assert record["viewHeadSha"] == "base-head-sha"


def test_run_execution_record_view_head_none_when_view_meta_not_dict_and_no_base_sha(tmp_path):
    run_dir = _run_dir_with_opened_view_meta(tmp_path, [], base_sha=None)
    records, _ = engine_dispatch._journal_read(run_dir)
    journal_path = engine_dispatch._journal_path(os.path.realpath(run_dir))
    with open(journal_path, "w", encoding="utf-8") as fh:
        for rec in records:
            if rec.get("kind") == "run-opened":
                rec["viewMeta"] = []
                rec.pop("baseSha", None)
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    assert record["viewHeadSha"] is None


def test_run_execution_record_view_head_none_when_head_sha_not_string(tmp_path):
    run_dir = _run_dir_with_opened_view_meta(tmp_path, {"headSha": 7}, base_sha="")
    records, _ = engine_dispatch._journal_read(run_dir)
    journal_path = engine_dispatch._journal_path(os.path.realpath(run_dir))
    with open(journal_path, "w", encoding="utf-8") as fh:
        for rec in records:
            if rec.get("kind") == "run-opened":
                rec["viewMeta"] = {"headSha": 7}
                rec["baseSha"] = ""
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    assert record["viewHeadSha"] is None


def test_record_result_refuses_view_head_anchor_mismatch_without_side_effects(tmp_path):
    session_dir, gitdir, _head_path = _TSP._drive_to_audits(tmp_path, name="cited-head-mismatch")
    seat = _TSP._audit_roster(session_dir)[0]
    pend = _pending(session_dir)
    order_path = RR.order_prompt_path(
        session_dir, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"])
    anchor_head = RD._anchor_cited_head(_state(session_dir), session_dir, pend["round"],
                                        pend["phase"], pend["attempt"])
    mismatch_head = "f" * 40
    assert mismatch_head != anchor_head
    run_dir = _TSP._audit_execution_run_dir(
        tmp_path, order_path, seat, view_head_sha=mismatch_head)
    ruling_payload = {
        "id": seat,
        "ruling": "discharged",
        "reason": "re-read the hunk; the defect is gone",
        "auditorVendor": "codex",
    }
    state = _state(session_dir)
    _TDI._dispatch_observed_land(session_dir, state, pend, seat, ruling_payload)
    recorded_before = _recorded_count(session_dir)
    store_dir = os.path.dirname(RR.store_path(
        session_dir, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"]))
    listing_before = sorted(os.listdir(store_dir)) if os.path.isdir(store_dir) else []
    assert not _store_exists(session_dir, seat)
    out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
    assert out["ok"] is False
    assert out["reason"] == "view-head-anchor-mismatch"
    assert not _store_exists(session_dir, seat)
    listing_after = sorted(os.listdir(store_dir)) if os.path.isdir(store_dir) else []
    assert listing_after == listing_before
    assert _recorded_count(session_dir) == recorded_before


def test_record_result_review_run_carries_runner_view_cited_head(tmp_path):
    session_dir, gitdir, _head_path = _TSP._drive_to_audits(tmp_path, name="cited-head-success")
    seat = _TSP._audit_roster(session_dir)[0]
    pend = _pending(session_dir)
    order_path = RR.order_prompt_path(
        session_dir, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"])
    anchor_head = RD._anchor_cited_head(_state(session_dir), session_dir, pend["round"],
                                        pend["phase"], pend["attempt"])
    run_dir = _TSP._audit_execution_run_dir(
        tmp_path, order_path, seat, view_head_sha=anchor_head)
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    runner_view_head = record["viewHeadSha"]
    assert runner_view_head == anchor_head
    ruling_payload = {
        "id": seat,
        "ruling": "discharged",
        "reason": "re-read the hunk; the defect is gone",
        "auditorVendor": "codex",
    }
    state = _state(session_dir)
    _TDI._dispatch_observed_land(session_dir, state, pend, seat, ruling_payload)
    out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
    assert out["ok"] is True, out
    stored, read_err = RR.read_json(out["storePath"])
    assert read_err is None
    assert stored["headSha"] == runner_view_head
    row = [r for r in RD.read_journal(session_dir)
           if r.get("outcome") == "recorded" and r.get("seat") == seat][-1]
    assert row["citedHead"] == runner_view_head
    assert row["citedHeadSource"] == RR.CITED_HEAD_SOURCE_RUNNER_VIEW
    assert stored["citedHeadSource"] == RR.CITED_HEAD_SOURCE_RUNNER_VIEW


def test_record_missing_declares_order_anchor_cited_head_source(tmp_path, adapters):
    d = _session(tmp_path)
    pend = _pending(d)
    seat = "security-reviewer"
    out = RD.cmd_record_missing(d, seat, pend["attempt"], "forfeit")
    assert out["ok"], out
    row = [r for r in RD.read_journal(d)
           if r.get("outcome") == "recorded" and r.get("cmd") == "record-missing"
           and r.get("seat") == seat][-1]
    assert row["citedHeadSource"] == RR.CITED_HEAD_SOURCE_ORDER_ANCHOR


def test_advance_reappend_row_declares_order_anchor_cited_head_source(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    pend = _pending(d)
    ghost_seat = "ghost-reviewer"
    ghost_skey = RR.storage_key(ghost_seat)
    env = _result_envelope(d, ghost_seat,
                           payload={"findings": [], "confidence": "high", "seat": ghost_seat},
                           headSha=None)
    spath = RR.store_path(d, pend["round"], pend["phase"], ghost_skey, pend["attempt"])
    os.makedirs(os.path.dirname(spath), exist_ok=True)
    RR.atomic_write_json(spath, env)
    out = _advance(d, tmp_path)
    assert out["ok"], out
    reappended = [e for e in RD.read_journal(d)
                  if e.get("outcome") == "recorded" and e.get("cmd") == "advance"
                  and e.get("reappended") is True]
    assert len(reappended) == 1
    assert reappended[0]["citedHeadSource"] == RR.CITED_HEAD_SOURCE_ORDER_ANCHOR


def _fixer_session(tmp_path, adapters, name="cited-head-fixer"):
    d = _session(tmp_path, name=name)
    state = _state(d)
    state["step"] = RD.P_FIXER
    state["pending"] = {"action": RD.P_FIXER, "round": 1, "phase": RD.P_FIXER, "attempt": 0,
                        "payload": {}}
    RD.save_state(d, state)
    return d


def test_fixer_head_diff_row_declares_order_anchor_cited_head_source(tmp_path, adapters):
    d = _fixer_session(tmp_path, adapters)
    head_path = str(tmp_path / "head.diff")
    with open(head_path, "w", encoding="utf-8") as fh:
        fh.write("diff --git a/f.py b/f.py\n+fixed\n")
    _land(d, "dispatch-fixer", payload={"fixes": [], "headDiffPath": head_path}, headSha=None)
    out = RD.cmd_record_result(d, "dispatch-fixer")
    assert out["ok"], out
    rows = [r for r in RD.read_journal(d)
            if r.get("outcome") == "recorded" and r.get("phase") == RD.P_FIXER
            and r.get("seat") == "dispatch-fixer"]
    assert rows
    assert rows[-1]["citedHeadSource"] == RR.CITED_HEAD_SOURCE_ORDER_ANCHOR


def test_reappend_preserves_runner_view_cited_head_source(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    pend = _pending(d)
    ghost_seat = "ghost-reviewer"
    ghost_skey = RR.storage_key(ghost_seat)
    env = _result_envelope(d, ghost_seat,
                           payload={"findings": [], "confidence": "high", "seat": ghost_seat})
    env = RR.envelope_bind_cited_head_source(env, RR.CITED_HEAD_SOURCE_RUNNER_VIEW)
    spath = RR.store_path(d, pend["round"], pend["phase"], ghost_skey, pend["attempt"])
    os.makedirs(os.path.dirname(spath), exist_ok=True)
    RR.atomic_write_json(spath, env)
    out = _advance(d, tmp_path)
    assert out["ok"], out
    reappended = [e for e in RD.read_journal(d) if e.get("reappended") is True]
    assert len(reappended) == 1
    assert reappended[0]["citedHeadSource"] == RR.CITED_HEAD_SOURCE_RUNNER_VIEW
