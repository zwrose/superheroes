"""#1272 layer 2e: followUp shape — one home (`session_contract.follow_up_shape_fault`).

The owner-gate submit paths that used to apply it (judgment skip, stall accept-risk) are retired; the
shape check stays for the `rule` verb's out-of-scope rulings."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import session_contract as SC

from test_round_driver import RD  # noqa: E402  (the helpers below are shared by other test files)

_TRADEOFF = {"title": "widen the API", "severity": "Important",
             "file": "f.py", "line": 1, "tradeoff": True}
_TRADEOFF_ID = "f.py::widen the api@L1"
_WELL_FORMED = {
    "item": "defer auth redesign",
    "revisitTrigger": "when #1300 lands",
    "classClosure": "tracked separately",
}


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, RD.STATE_FILE), "rb") as fh:
        return fh.read()


def _load_state(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok, state
    return state


def _ledger_by_key(state):
    return {SC.finding_identity_key(e): e
            for e in (state.get("dispositionLedger") or []) if isinstance(e, dict)}


# --- helper unit tests (rules 1–6) -----------------------------------------------

def test_rule_1_not_dict():
    # axis: rule 1 — non-dict followUp
    fault = SC.follow_up_shape_fault(None)
    assert fault == (None, "out-of-scope disposition lacks named follow-up item")


def test_rule_2_item_absent_refused_when_required():
    # axis: rule 2 — missing item refused when require_item=True (default)
    fault = SC.follow_up_shape_fault({"revisitTrigger": "later", "classClosure": "none"})
    assert fault == ("missing-follow-up-item", "out-of-scope follow-up lacks named item")


def test_rule_2_legacy_item_absent_passes():
    # axis: rule 2 legacy — item optional when require_item=False
    fault = SC.follow_up_shape_fault(
        {"revisitTrigger": "later", "classClosure": "none"}, require_item=False)
    assert fault is None


def test_rule_2b_present_empty_item_refused():
    # axis: rule 2b — present-but-empty item refused
    fault = SC.follow_up_shape_fault({
        "item": "",
        "revisitTrigger": "later",
        "classClosure": "none",
    })
    assert fault == ("missing-follow-up-item", "out-of-scope follow-up lacks named item")


def test_rule_3_missing_revisit_trigger():
    # axis: rule 3 — revisitTrigger required
    fault = SC.follow_up_shape_fault({"item": "defer", "classClosure": "none"})
    assert fault == ("missing-revisit-trigger", "out-of-scope follow-up lacks revisit trigger")


def test_rule_4_documented_trigger():
    # axis: rule 4 — documented token forbidden
    fault = SC.follow_up_shape_fault({
        "item": "defer",
        "revisitTrigger": "documented in the PR",
        "classClosure": "none",
    })
    assert fault == (None, "revisit trigger must not be the word documented")


def test_rule_5_missing_class_closure():
    # axis: rule 5 — classClosure required
    fault = SC.follow_up_shape_fault({"item": "defer", "revisitTrigger": "2026-12-01"})
    assert fault == ("missing-class-closure", "out-of-scope follow-up lacks class-closure line")


def test_rule_6_well_formed_returns_none():
    # axis: rule 6 — fully shaped followUp accepted
    assert SC.follow_up_shape_fault(dict(_WELL_FORMED)) is None
