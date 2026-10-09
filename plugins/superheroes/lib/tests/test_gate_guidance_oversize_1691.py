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
    session_dir = _parked_judgment_session(tmp_path)
    before = _state_bytes(session_dir)
    out = _pending_submit(session_dir, _guided("x" * 2001))
    assert out["ok"] is False
    assert out["reason"].startswith("gate-guidance-oversize: ")
    assert out["reason"] == "gate-guidance-oversize: %s (2001 bytes; cap 2000)" % _TRADEOFF_ID
    assert _state_bytes(session_dir) == before
    assert _journal_rows(session_dir)[-1]["outcome"] == "gate-guidance-oversize"


def test_t2_at_cap_guidance_folds_and_renders_whole(tmp_path):
    session_dir = _parked_judgment_session(tmp_path)
    out = _pending_submit(session_dir, _guided("x" * 2000))
    assert out["ok"] is True, out
    state = _load_state(session_dir)
    assert state["step"] == RD.P_FIXER
    block = _rendered_guidance(session_dir)
    assert "> %s" % ("x" * 2000) in block
    assert "bytes withheld" not in block


def test_t3_multibyte_guidance_is_measured_in_bytes(tmp_path):
    guidance = "é" * 1000 + "x"
    assert len(guidance) == 1001 and len(guidance.encode("utf-8")) == 2001
    session_dir = _parked_judgment_session(tmp_path)
    before = _state_bytes(session_dir)
    out = _pending_submit(session_dir, _guided(guidance))
    assert out["ok"] is False
    assert out["reason"] == "gate-guidance-oversize: %s (2001 bytes; cap 2000)" % _TRADEOFF_ID
    assert _state_bytes(session_dir) == before


def test_t4_whitespace_padding_is_not_counted_on_submit_and_ruling_paths(tmp_path):
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
    entry = {"id": "d.py::big@L1", "title": "big", "file": "d.py", "line": 1,
             "guidance": "x" * 2001}
    if ruling_channel:
        entry["rulingChannel"] = True
    with pytest.raises(ValueError) as excinfo:
        RD._gate_guidance_block([entry])
    assert str(excinfo.value) == "order-render-refused:gate-guidance-oversize"


def test_t7_literals_pinned():
    assert RD.GATE_GUIDANCE_OVERSIZE == "gate-guidance-oversize"
    assert RD.GATE_GUIDANCE_ROW_BYTE_CAP == 2000
