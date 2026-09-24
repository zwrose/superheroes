"""#1272 layer 4b: control probe is recorded, never a gate."""
import copy
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_adapters as RA
import round_phases as RP
import receipt_disclosures as RD_DISCLOSURES

from test_round_driver import (
    _cfg,
    _cfg_cert,
    _load,
    _seat_map_vendors,
)

RD = _load("round_driver")


def _cross_vendor_artifact(canary_result):
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    art = {"seats": seats, "seatMap": seat_map}
    if canary_result is not None:
        art["canaryResult"] = canary_result
    return art


def _fold_twice(canary_result):
    cfg = _cfg(leg="panel", vendors=["claude", "codex"])
    state = RD.new_state(cfg)
    art = _cross_vendor_artifact(canary_result)
    RD._fold_panel(state, cfg, art)
    state["round"] = 2
    RD._fold_panel(state, cfg, art)
    return state


def _verdict_snapshot(state):
    r2 = state["rounds"]["2"]
    RD._terminal_converged(state, state["config"], full_panel=True)
    receipt = RD.build_receipt(state)
    return {
        "seatStatus": copy.deepcopy(r2["seatStatus"]),
        "fullPanelRan": state["fullPanelRan"],
        "_incompletePanel": state["_incompletePanel"],
        "confirmations": state.get("confirmations"),
        "lensCoverage": copy.deepcopy(r2.get("lensCoverage")),
        "terminal": state["terminal"],
        "certification_shape": (state.get("certification") or {}).get("shape"),
        "degraded_prose": RD_DISCLOSURES.build_degraded_prose(state, RD.RECEIPT_FORM_CERTIFIED),
        "controlProbe": copy.deepcopy(r2.get("controlProbe")),
        "legacy_canary_keys": {
            k: copy.deepcopy(r2[k])
            for k in (
                "canaryUnverified", "canaryFailed", "canaryOutcomeFailed",
                "canaryPlantUndetected", "canaryVerified",
            )
            if k in r2
        },
    }


PROBE_CASES = [
    pytest.param(None, id="absent"),
    pytest.param({
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 1}, "detectedPlant": True, "detail": "live",
    }, id="engaged-ok"),
    pytest.param({
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {}, "detectedPlant": False, "detail": "missed plant",
    }, id="plant-undetected"),
    pytest.param({
        "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
        "evidence": {}, "detectedPlant": False, "detail": "not engaged",
    }, id="not-engaged"),
    pytest.param({
        "engine": "codex", "model": "gpt", "outcome": "forfeited", "engaged": True,
        "evidence": {}, "detectedPlant": False, "detail": "dispatch fail",
    }, id="forfeited"),
    pytest.param([None, {"engaged": True}], id="malformed-list"),
]


@pytest.mark.parametrize("canary_result", PROBE_CASES)
def test_probe_states_do_not_change_verdict_surface(canary_result):
    baseline = _verdict_snapshot(_fold_twice(None))
    probe = _verdict_snapshot(_fold_twice(canary_result))
    for key in (
        "seatStatus", "fullPanelRan", "_incompletePanel", "confirmations",
        "lensCoverage", "terminal", "certification_shape", "degraded_prose",
    ):
        assert probe[key] == baseline[key], key
    if canary_result is not None:
        assert probe["controlProbe"] != baseline["controlProbe"]


def test_control_probe_shapes_per_state():
    absent = _fold_twice(None)
    assert absent["rounds"]["2"]["controlProbe"] == {"submitted": False, "vendors": {}}

    ok_art = _cross_vendor_artifact({
        "engine": "codex", "outcome": "ok", "engaged": True,
        "detectedPlant": True, "evidence": {}, "detail": "",
    })
    st = RD.new_state(_cfg(leg="panel"))
    RD._fold_panel(st, st["config"], ok_art)
    assert st["rounds"]["1"]["controlProbe"] == {
        "submitted": True, "vendors": {"codex": "ok"},
    }

    st2 = RD.new_state(_cfg(leg="panel"))
    RD._fold_panel(st2, st2["config"], _cross_vendor_artifact([
        {
            "engine": "codex", "outcome": "forfeited", "engaged": True,
            "detectedPlant": False, "evidence": {}, "detail": "",
        },
        {
            "engine": "codex", "outcome": "vacuous", "engaged": False,
            "detectedPlant": False, "evidence": {}, "detail": "",
        },
    ]))
    assert st2["rounds"]["1"]["controlProbe"]["vendors"]["codex"] == "forfeited"

    st3 = RD.new_state(_cfg(leg="panel"))
    RD._fold_panel(st3, st3["config"], _cross_vendor_artifact([]))
    assert st3["rounds"]["1"]["controlProbe"] == {"submitted": True, "vendors": {}}

    art = _cross_vendor_artifact([
        {
            "engine": "codex", "outcome": "ok", "engaged": True,
            "detectedPlant": True, "evidence": {}, "detail": "",
        },
        {
            "engine": "cursor", "outcome": "ok", "engaged": True,
            "detectedPlant": True, "evidence": {}, "detail": "",
        },
    ])
    st4 = RD.new_state(_cfg(leg="panel"))
    RD._fold_panel(st4, st4["config"], art)
    first = st4["rounds"]["1"]["controlProbe"]
    art["canaryResult"] = list(reversed(art["canaryResult"]))
    st5 = RD.new_state(_cfg(leg="panel"))
    RD._fold_panel(st5, st5["config"], art)
    assert st5["rounds"]["1"]["controlProbe"] == first


def test_malformed_canary_assemble_not_refused(tmp_path):
    _d, _n, state = (
        str(tmp_path),
        None,
        RD.new_state(_cfg(leg="panel")),
    )
    envelopes = [
        {"seat": dim, "schema": "seat-result/2", "payload": {"findings": []}}
        for dim in RD.DIMENSIONS
    ]
    artifact, reason = RA.assemble(
        RP.P_PANEL, envelopes, state, state["config"],
        canary=[{"engine": "codex", "engaged": True}, {"engaged": True}],
    )
    assert reason is None and artifact is not None


def test_dry_run_a_not_engaged_probe_certifies_on_panel_complete():
    state = RD.new_state(_cfg_cert(leg="panel"))
    canary = {
        "engine": "codex", "outcome": "vacuous", "engaged": False,
        "detectedPlant": False, "evidence": {}, "detail": "not engaged",
    }
    RD._fold_panel(state, state["config"], _cross_vendor_artifact(canary))
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["terminal"] == "converged"
    assert state["certification"]["shape"].startswith("full-panel-confirmed")
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["controlProbe"]["vendors"]["codex"] == "vacuous"
    assert "canaryFailed" in receipt["rounds"][0]


def test_dry_run_b_plant_undetected_certifies_no_canary_degraded_line():
    state = RD.new_state(_cfg_cert(leg="panel"))
    canary = {
        "engine": "codex", "outcome": "ok", "engaged": True,
        "detectedPlant": False, "evidence": {}, "detail": "missed",
    }
    RD._fold_panel(state, state["config"], _cross_vendor_artifact(canary))
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["terminal"] == "converged"
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["controlProbe"]["vendors"]["codex"] == "plant-undetected"
    assert not any("canary-" in line for line in receipt["degraded"])


def test_resume_restores_control_probe(tmp_path):
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([{
        "schemaVersion": 2, "round": 1, "kind": "baseline",
        "dimensions": {"test-reviewer": {"status": "run", "findings": []}},
        "findings": [], "coverageDecisions": [],
        "disclosures": {"controlProbe": {"submitted": True, "vendors": {"codex": "ok"}}},
    }]))
    state = RD.new_state(_cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert state["rounds"]["1"]["controlProbe"] == {
        "submitted": True, "vendors": {"codex": "ok"},
    }
