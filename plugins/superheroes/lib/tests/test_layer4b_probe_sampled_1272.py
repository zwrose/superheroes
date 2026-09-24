"""#1272 layer 4b: control probe is recorded, never a gate."""
import ast
import copy
import importlib.util
import inspect
import json
import os
import sys

import pytest
import session_contract as SC

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_adapters as RA
import round_certification as RC
import round_phases as RP
import receipt_disclosures as RD_DISCLOSURES

from round_certification_fixtures import DEFAULT_PANEL_PAYLOAD_SHA
from test_layer4a_uncertified_seats_1272 import (
    HEAD,
    _dispatch_observed_no_telemetry_row,
    _manifest_seat_entry,
    _qualifying_dispatch_row,
    _session_with_manifest,
)
from test_round_certification import (
    _dispatch_journal_with_binding,
    _orders_emitted_journal_row,
    _write_orders_manifest,
    write_certifiable_session,
)
from test_round_driver import (
    _cfg,
    _cfg_cert,
    _load,
    _seat_map_vendors,
)

RD = _load("round_driver")

_L4B_PANEL_VENDORS = {
    "code-reviewer": "codex",
    "security-reviewer": "cursor",
    "architecture-reviewer": "codex",
    "test-reviewer": "cursor",
    "premortem-reviewer": "codex",
}


def _panel_vendor_channel(vendor):
    return SC.CHANNEL_STDOUT if vendor != "claude" else SC.CHANNEL_FILE


def _cross_vendor_artifact(canary_result):
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors(_L4B_PANEL_VENDORS)
    art = {"seats": seats, "seatMap": seat_map}
    if canary_result is not None:
        art["canaryResult"] = canary_result
    return art


def _fold_twice(canary_result):
    cfg = _cfg(leg="panel", vendors=["claude", "codex", "cursor"])
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


def _assert_absolute_invariant_anchor(baseline):
    for dim in RD.DIMENSIONS:
        assert baseline["seatStatus"].get(dim) == "run", dim
    assert baseline["fullPanelRan"] is True
    assert baseline["_incompletePanel"] is False
    assert baseline["confirmations"] == 1
    assert baseline["lensCoverage"]["floor"] is False
    assert baseline["terminal"] == "converged"
    assert baseline["certification_shape"].startswith("full-panel-confirmed")
    assert not any("canary-" in line for line in baseline["degraded_prose"])


def _driver_panel_state_with_probe(canary):
    state = RD.new_state(_cfg_cert(leg="panel", vendors=["claude", "codex", "cursor"]))
    RD._fold_panel(state, state["config"], _cross_vendor_artifact(canary))
    RD._terminal_converged(state, state["config"], full_panel=True)
    return state


def _cert_writer_session_for_probe(tmp_path, canary):
    """Certification-writer session: full panel telemetry + round record from driver fold."""
    fold_state = _driver_panel_state_with_probe(canary)
    seat_map = _seat_map_vendors(_L4B_PANEL_VENDORS)
    journal = []
    manifest_seats = {}
    envelopes = []
    for dim in RD.DIMENSIONS:
        vendor = _L4B_PANEL_VENDORS[dim]
        channel = _panel_vendor_channel(vendor)
        if channel == SC.CHANNEL_STDOUT:
            row = _qualifying_dispatch_row(dim, RP.P_PANEL)
        else:
            row = _dispatch_journal_with_binding(seat=dim)
            row["phase"] = RP.P_PANEL
            row["seat"] = dim
            row["recordIdentity"]["phase"] = RP.P_PANEL
            row["recordIdentity"]["seat"] = dim
        journal.append(row)
        skey, entry = _manifest_seat_entry(dim, channel, vendor)
        manifest_seats[skey] = entry
        envelopes.append({"seat": dim, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA})
    manifest = {
        "schema": "orders-manifest/1",
        "session": "test-session-001",
        "round": 1,
        "phase": RP.P_PANEL,
        "attempt": 0,
        "orders": "not-emitted",
        "seats": manifest_seats,
    }
    manifest_sha = SC.sha256_text(SC.canonical(manifest))
    journal.append(_orders_emitted_journal_row(manifest_sha))
    cert_state = {
        "terminal": fold_state["terminal"],
        "certification": fold_state["certification"],
        "rounds": fold_state["rounds"],
        "fullPanelRan": fold_state.get("fullPanelRan"),
        "config": {
            "fixerVendor": "claude",
            "baseGuard": RC.BASE_GUARD_CHECKED,
            "headSha": HEAD,
        },
        "seatMapReceipts": [{"round": "1", "map": seat_map}],
    }
    session_dir = write_certifiable_session(
        tmp_path,
        journal_lines=journal,
        envelopes=envelopes,
        state=cert_state,
    )
    _write_orders_manifest(session_dir, manifest)
    return session_dir


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
    _assert_absolute_invariant_anchor(baseline)
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


def test_dry_run_a_not_engaged_probe_certifies_via_writer_with_telemetry(tmp_path):
    canary = {
        "engine": "codex", "outcome": "vacuous", "engaged": False,
        "detectedPlant": False, "evidence": {}, "detail": "not engaged",
    }
    session_dir = _cert_writer_session_for_probe(tmp_path, canary)
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None and receipt is not None
    assert receipt["terminalState"] == "certified"
    r0 = receipt["rounds"][0]
    assert r0["controlProbe"]["vendors"]["codex"] == "vacuous"
    assert "canaryFailed" in r0


def test_dry_run_b_plant_undetected_certifies_via_writer_no_canary_degraded_line(tmp_path):
    canary = {
        "engine": "codex", "outcome": "ok", "engaged": True,
        "detectedPlant": False, "evidence": {}, "detail": "missed",
    }
    session_dir = _cert_writer_session_for_probe(tmp_path, canary)
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None and receipt is not None
    assert receipt["terminalState"] == "certified"
    r0 = receipt["rounds"][0]
    assert r0["controlProbe"]["vendors"]["codex"] == "plant-undetected"
    assert not any("canary-" in line for line in receipt["degraded"])


def test_l4b_cross_vendor_zero_finding_no_telemetry_no_probe_refuses_unrun_review(tmp_path):
    """Fail-closed edge 5(b): probe gate removal must not certify without runner telemetry."""
    seat = "code-reviewer"
    row = _dispatch_observed_no_telemetry_row(seat, RP.P_PANEL)
    session_dir, _ = _session_with_manifest(
        tmp_path,
        seat=seat,
        phase=RP.P_PANEL,
        channel=SC.CHANNEL_STDOUT,
        vendor="codex",
        journal_lines=[row],
        envelopes=[{"seat": seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == seat


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


def _literal_get_keys_in_build_degraded_prose():
    source = inspect.getsource(RD_DISCLOSURES.build_degraded_prose)
    tree = ast.parse(source)
    fn_node = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "build_degraded_prose")
    keys = []
    for node in ast.walk(fn_node):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "get":
            continue
        if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant):
            continue
        if isinstance(node.args[0].value, str):
            keys.append(node.args[0].value)
    return keys


def test_record_only_channels_never_read_in_build_degraded_prose():
    """Record-only disclosure channels must not be read into degraded prose."""
    record_only = set(RD.RECORD_ONLY_DISCLOSURE_CHANNELS)
    literal_gets = _literal_get_keys_in_build_degraded_prose()
    assert len(literal_gets) >= 5, (
        "build_degraded_prose census must find literal .get() reads (e.g. vacuousSeats)")
    assert "vacuousSeats" in literal_gets
    offenders = [k for k in literal_gets if k in record_only]
    assert not offenders, (
        "record-only channels must not be read in build_degraded_prose: %s" % offenders)
