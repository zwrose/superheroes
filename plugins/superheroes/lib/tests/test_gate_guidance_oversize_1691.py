"""#1691: oversized owner-gate guidance refuses loudly — a fixer order never carries guidance
shorter than what the owner wrote."""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import test_layer2e_follow_up_1272 as L2E
from test_round_driver import _cfg_cert, _run_loop_with_loop_receipt, _seams

RD = L2E.RD
_TRADEOFF = L2E._TRADEOFF
_TRADEOFF_ID = L2E._TRADEOFF_ID
_state_bytes = L2E._state_bytes
_load_state = L2E._load_state
_parked_judgment_session = L2E._parked_judgment_session
_pending_submit = L2E._pending_submit


def _guided(guidance):
    return {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "fix-with-guidance", "guidance": guidance}]}


def _journal_rows(session_dir):
    with open(os.path.join(session_dir, RD.JOURNAL_FILE), encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _rendered_guidance(session_dir):
    state = _load_state(session_dir)
    return RD._gate_guidance_block(RD._gate_guidance_entries(state, state["round"]))


def test_t1_submit_refuses_over_cap_guidance(tmp_path):
    """axis: submit refusal — oversized guidance refuses before fold, state unchanged"""
    session_dir = _parked_judgment_session(tmp_path)
    before = _state_bytes(session_dir)
    out = _pending_submit(session_dir, _guided("x" * 2001))
    assert out["ok"] is False
    assert out["reason"].startswith("gate-guidance-oversize: ")
    assert out["reason"] == "gate-guidance-oversize: %s (2001 bytes; cap 2000)" % _TRADEOFF_ID
    assert _state_bytes(session_dir) == before
    assert _journal_rows(session_dir)[-1]["outcome"] == "gate-guidance-oversize"


def test_t2_at_cap_guidance_folds_and_renders_whole(tmp_path):
    """axis: boundary acceptance at exactly the cap"""
    session_dir = _parked_judgment_session(tmp_path)
    out = _pending_submit(session_dir, _guided("x" * 2000))
    assert out["ok"] is True, out
    state = _load_state(session_dir)
    assert state["step"] == RD.P_FIXER
    block = _rendered_guidance(session_dir)
    assert "> %s" % ("x" * 2000) in block
    assert "bytes withheld" not in block


def test_t3_multibyte_guidance_is_measured_in_bytes(tmp_path):
    """axis: the measure is UTF-8 bytes, not characters"""
    guidance = "é" * 1000 + "x"
    assert len(guidance) == 1001 and len(guidance.encode("utf-8")) == 2001
    session_dir = _parked_judgment_session(tmp_path)
    before = _state_bytes(session_dir)
    out = _pending_submit(session_dir, _guided(guidance))
    assert out["ok"] is False
    assert out["reason"] == "gate-guidance-oversize: %s (2001 bytes; cap 2000)" % _TRADEOFF_ID
    assert _state_bytes(session_dir) == before


def test_t4_whitespace_padding_is_not_counted_on_submit_and_ruling_paths(tmp_path):
    """axis: one stripped measure on both the gate and ruling paths"""
    padded = "  \n" + "x" * 2000 + "\n\t  "
    assert len(padded.encode("utf-8")) > 2000
    session_dir = _parked_judgment_session(tmp_path)
    out = _pending_submit(session_dir, _guided(padded))
    assert out["ok"] is True, out
    assert "> %s" % ("x" * 2000) in _rendered_guidance(session_dir)

    def validate(guidance):
        doc = {"_provenance": {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z",
                               "records": ["rulings.json"]},
               "rulings": [{"id": "a.py::t@L1", "ruling": "guidance",
                            "reason": "r", "guidance": guidance}]}
        return RD._validate_ruling_entries(doc)

    parsed, _prov, err = validate(padded)
    assert err is None, err
    assert parsed[0]["guidance"] == "x" * 2000
    _parsed, _prov, err = validate("x" * 2001)
    assert err == RD.RULING_GUIDANCE_OVERSIZE


def test_t5_library_run_loop_parks_cannot_certify_without_fixing():
    """axis: the library run_loop door parks before any fixer runs"""
    fixes = []

    def fix_step(batch, rnd, payload):
        fixes.append(rnd)
        return {"fixes": [], "headDiff": "x", "changedSubjects": ["Code"]}

    def judgment_gate(payload):
        return {"dispositions": [{"id": f["id"], "disposition": "fix-with-guidance",
                                  "guidance": "x" * 2001} for f in payload["findings"]]}

    refusal, receipt = _run_loop_with_loop_receipt(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [dict(_TRADEOFF)]} if rnd == 1 and dim == "code-reviewer" else []),
        fix_step=fix_step, io={"judgment_gate": judgment_gate}), _cfg_cert())
    assert refusal["loopTerminal"] == "cannot-certify"
    reason = (receipt["certification"] or {}).get("reason") or ""
    assert "gate-guidance-oversize: %s (2001 bytes; cap 2000)" % _TRADEOFF_ID in reason
    assert fixes == []


@pytest.mark.parametrize("ruling_channel", [False, True])
def test_t6_render_backstop_refuses_over_cap_entry(ruling_channel):
    """axis: render backstop on both channels"""
    entry = {"id": "d.py::big@L1", "title": "big", "file": "d.py", "line": 1,
             "guidance": "x" * 2001}
    if ruling_channel:
        entry["rulingChannel"] = True
    with pytest.raises(ValueError) as excinfo:
        RD._gate_guidance_block([entry])
    assert str(excinfo.value) == "order-render-refused:gate-guidance-oversize"


def test_t7_literals_pinned():
    """axis: external-contract literals pinned"""
    assert RD.GATE_GUIDANCE_OVERSIZE == "gate-guidance-oversize"
    assert RD.GATE_GUIDANCE_ROW_BYTE_CAP == 2000
    assert RD.GATE_GUIDANCE_AGGREGATE_OVERSIZE == "gate-guidance-aggregate-oversize"
    assert RD.GATE_GUIDANCE_AGGREGATE_BYTE_CAP == 8000


def test_t8_render_backstop_checks_entries_past_the_aggregate_cap():
    """axis: render backstop checks every entry, including those past the aggregate cap"""
    sizes = [2000, 2000, 2000, 2000, 2001]
    entries = [{"id": "e%d.py::t%d@L%d" % (i, i, i), "title": "t%d" % i, "file": "e%d.py" % i,
                "line": i, "guidance": "x" * size}
               for i, size in enumerate(sizes, start=1)]
    with pytest.raises(ValueError) as excinfo:
        RD._gate_guidance_block(entries)
    assert str(excinfo.value) == "order-render-refused:gate-guidance-oversize"


_AGGREGATE_REASON = ("gate-guidance-aggregate-oversize: %d guided finding(s) exceed the "
                     "8000-byte order cap")


def _tradeoff_findings(n):
    return [{"title": "widen the API %d" % i, "severity": "Important", "file": "f%d.py" % i,
             "line": i, "tradeoff": True} for i in range(1, n + 1)]


def _session_with_findings(tmp_path, n, name="judgment"):
    session_dir = _parked_judgment_session(tmp_path, name=name)
    state = _load_state(session_dir)
    state["_judgmentFindings"] = _tradeoff_findings(n)
    RD.save_state(session_dir, state)
    return session_dir


def _guided_all(session_dir, size):
    rows = _load_state(session_dir)["_judgmentFindings"]
    return {"dispositions": [
        {"id": fid, "disposition": "fix-with-guidance", "guidance": "x" * size}
        for fid in RD._judgment_row_ids(rows)]}


def test_t9_submit_refuses_aggregate_over_cap(tmp_path):
    """axis: submit refusal — a whole batch's guidance over the aggregate cap refuses, state unchanged"""
    session_dir = _session_with_findings(tmp_path, 5)
    before = _state_bytes(session_dir)
    out = _pending_submit(session_dir, _guided_all(session_dir, 1900))
    assert out["ok"] is False
    assert out["reason"] == _AGGREGATE_REASON % 5
    assert _state_bytes(session_dir) == before
    assert _journal_rows(session_dir)[-1]["outcome"] == "gate-guidance-aggregate-oversize"


def test_t10_aggregate_boundary_acceptance(tmp_path):
    """axis: boundary acceptance — three 1900-byte guidances fit one order and render whole"""
    session_dir = _session_with_findings(tmp_path, 3)
    out = _pending_submit(session_dir, _guided_all(session_dir, 1900))
    assert out["ok"] is True, out
    assert _load_state(session_dir)["step"] == RD.P_FIXER
    assert _rendered_guidance(session_dir).count("> " + "x" * 1900) == 3


def test_t11_library_run_loop_parks_aggregate_without_fixing():
    """axis: the library run_loop door parks on aggregate overflow before any fixer runs"""
    fixes = []
    diff = "".join(
        "diff --git a/f%d.py b/f%d.py\nindex 1..2 100644\n--- a/f%d.py\n+++ b/f%d.py\n"
        "@@ -1 +1,6 @@\n-old\n+n1\n+n2\n+n3\n+n4\n+n5\n" % (i, i, i, i) for i in range(1, 6))

    def fix_step(batch, rnd, payload):
        fixes.append(rnd)
        return {"fixes": [], "headDiff": "x", "changedSubjects": ["Code"]}

    def judgment_gate(payload):
        return {"dispositions": [{"id": f["id"], "disposition": "fix-with-guidance",
                                  "guidance": "x" * 1900} for f in payload["findings"]]}

    refusal, receipt = _run_loop_with_loop_receipt(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": _tradeoff_findings(5)} if rnd == 1 and dim == "code-reviewer" else []),
        fix_step=fix_step, io={"judgment_gate": judgment_gate}), _cfg_cert(diff=diff))
    assert refusal["loopTerminal"] == "cannot-certify"
    reason = (receipt["certification"] or {}).get("reason") or ""
    assert _AGGREGATE_REASON % 5 in reason
    assert fixes == []


def test_t12_render_backstop_refuses_aggregate_overflow():
    """axis: render backstop — the render raises rather than omit when the aggregate overflows"""
    entries = [{"id": "e%d.py::t%d@L%d" % (i, i, i), "title": "t%d" % i, "file": "e%d.py" % i,
                "line": i, "guidance": "x" * 1900} for i in range(1, 6)]
    with pytest.raises(ValueError) as excinfo:
        RD._gate_guidance_block(entries)
    assert str(excinfo.value) == "order-render-refused:gate-guidance-aggregate-oversize"


def _carried_session(tmp_path, name):
    """Round 2 holding tradeoff row D, with mechanical rows A, B, C whose 1900-byte guidance was
    ruled in round 1 and carried in the batch."""
    session_dir = _parked_judgment_session(tmp_path, name=name)
    state = _load_state(session_dir)
    mechanical = [{"title": "mech %d" % i, "severity": "Important", "file": "m%d.py" % i,
                   "line": i} for i in range(1, 4)]
    records = []
    for row in mechanical:
        key = RD._fix_batch_row_key(row)
        records.append({"id": key, RD.session_contract.FINDING_KEY_FIELD: key,
                        "title": row["title"], "file": row["file"], "line": row["line"],
                        "disposition": "fix-with-guidance",
                        RD.GATE_GUIDANCE_RECORD_KEY: "g%d" % row["line"] + "x" * 1898})
    state["round"] = 2
    state["pending"]["round"] = 2
    state["rounds"]["1"] = {"judgmentDispositions": records}
    state["_judgmentMechanical"] = mechanical
    state["_judgmentFindings"] = [dict(_TRADEOFF)]
    RD.save_state(session_dir, state)
    return session_dir, records


def test_t13_carried_guidance_counts_at_submit(tmp_path):
    """axis: carried guidance — earlier-round guidance in the batch counts toward the aggregate cap"""
    control_dir, records = _carried_session(tmp_path, "control")
    out = _pending_submit(control_dir, {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "fix-as-suggested"}]})
    assert out["ok"] is True, out
    assert _load_state(control_dir)["step"] == RD.P_FIXER
    block = _rendered_guidance(control_dir)
    for rec in records:
        assert "> " + rec[RD.GATE_GUIDANCE_RECORD_KEY] in block

    session_dir, _records = _carried_session(tmp_path, "refuse")
    before = _state_bytes(session_dir)
    out = _pending_submit(session_dir, _guided("x" * 1900))
    assert out["ok"] is False
    assert out["reason"] == _AGGREGATE_REASON % 4
    assert _state_bytes(session_dir) == before
