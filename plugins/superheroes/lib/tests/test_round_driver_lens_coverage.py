"""Output-level lensCoverage receipt tests for #960 (WO-3)."""
import copy
import importlib.util
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


def _cfg(**over):
    base = {"leg": "panel", "vendors": ["claude", "codex"], "diff": "diff"}
    base.update(over)
    return base


def _seat_map_vendors(vendors):
    return {"seats": {d: {"vendor": v} for d, v in vendors.items()}}


def _all_seats_empty():
    return {d: {"findings": []} for d in RD.DIMENSIONS}


def _fold_and_receipt(seats, **artifact_kw):
    state = RD.new_state(_cfg())
    artifact = {"seats": seats, **artifact_kw}
    RD._fold_panel(state, state["config"], artifact)
    return state, RD.build_receipt(state)


def _converged_receipt_from_state(state):
    state = copy.deepcopy(state)
    state["terminal"] = "converged"
    state["certification"] = {
        "shape": "full-panel-confirmed" if state.get("fullPanelRan") else "audited-chain",
        "fullPanel": bool(state.get("fullPanelRan")),
        "independence": "independent",
    }
    return RD.build_receipt(state)


def test_complete_panel_lens_coverage_may_ground_converged():
    seats = _all_seats_empty()
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    state, receipt = _fold_and_receipt(seats, seatMap=seat_map)
    lc = receipt["rounds"][0]["lensCoverage"]
    assert lc == {"ran": len(RD.DIMENSIONS), "expected": len(RD.DIMENSIONS), "floor": False}
    assert state["fullPanelRan"] is True
    converged = _converged_receipt_from_state(state)
    ok, reason = RD.validate_receipt(converged)
    assert ok is True, reason
    assert converged["certification"]["fullPanel"] is True


def test_missing_lens_floor_cannot_ground_converged():
    seats = {d: {"findings": []} for d in RD.DIMENSIONS if d != "premortem-reviewer"}
    state, receipt = _fold_and_receipt(seats)
    lc = receipt["rounds"][0]["lensCoverage"]
    assert lc["floor"] is True
    assert lc["ran"] < lc["expected"]
    assert state["fullPanelRan"] is False
    bad = _converged_receipt_from_state(state)
    bad["certification"]["fullPanel"] = True
    bad["certification"]["shape"] = "full-panel-confirmed"
    bad["certificationShape"] = "full-panel-confirmed"
    ok, reason = RD.validate_receipt(bad)
    assert ok is False
    assert "floor-marked" in reason


def test_canary_unverified_all_run_still_floor():
    seats = _all_seats_empty()
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    state, receipt = _fold_and_receipt(seats, seatMap=seat_map)
    r0 = receipt["rounds"][0]
    assert r0["seatStatus"]["code-reviewer"] == "run"
    lc = r0["lensCoverage"]
    assert lc["floor"] is True
    assert lc["ran"] == lc["expected"]
    assert state["fullPanelRan"] is False
    bad = _converged_receipt_from_state(state)
    bad["certification"]["fullPanel"] = True
    bad["certification"]["shape"] = "full-panel-confirmed"
    bad["certificationShape"] = "full-panel-confirmed"
    ok, reason = RD.validate_receipt(bad)
    assert ok is False
    assert "floor-marked" in reason


def test_validate_receipt_refuses_false_floor_with_partial_ran():
    seats = _all_seats_empty()
    state, receipt = _fold_and_receipt(seats)
    mutated = copy.deepcopy(receipt)
    mutated["rounds"][0]["lensCoverage"]["floor"] = False
    mutated["rounds"][0]["lensCoverage"]["ran"] = 1
    mutated["terminal"] = "converged"
    mutated["verdict"] = "converged"
    mutated["certification"] = {"shape": "audited-chain", "fullPanel": False}
    mutated["certificationShape"] = "audited-chain"
    ok, reason = RD.validate_receipt(mutated)
    assert ok is False
    assert "floor:false" in reason


def test_non_panel_round_omits_lens_coverage():
    state = RD.new_state(_cfg())
    RD._record_round(state, "roundKind", "delta")
    RD._record_round(state, "blockingCount", 0)
    receipt = RD.build_receipt(state)
    assert "lensCoverage" not in receipt["rounds"][0]


def test_legacy_receipt_without_lens_coverage_still_validates():
    state = RD.new_state(_cfg())
    state["terminal"] = "converged"
    state["certification"] = {"shape": "audited-chain", "fullPanel": False}
    receipt = RD.build_receipt(state)
    assert all("lensCoverage" not in rd for rd in receipt["rounds"])
    ok, reason = RD.validate_receipt(receipt)
    assert ok is True, reason


def test_validate_receipt_refuses_ran_above_expected():
    seats = _all_seats_empty()
    _, receipt = _fold_and_receipt(seats)
    mutated = copy.deepcopy(receipt)
    mutated["rounds"][0]["lensCoverage"]["ran"] = mutated["rounds"][0]["lensCoverage"]["expected"] + 1
    mutated["terminal"] = "halted"
    mutated["verdict"] = "halted"
    mutated["certification"] = {"shape": None}
    mutated["certificationShape"] = None
    ok, reason = RD.validate_receipt(mutated)
    assert ok is False
    assert "ran" in reason
