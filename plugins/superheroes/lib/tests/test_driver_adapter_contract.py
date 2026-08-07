#!/usr/bin/env python3
"""Boundary contract between `round_driver` producers and `round_adapters` / `round_records`
consumers.

Each disagreement in this build was internally consistent on ONE side — unit tests on either
module alone stayed green while the seam shipped broken. This module drives the REAL driver helpers
that build boundary values, feeds them to the REAL consumers, and fails on SHAPE refusals only.
"""
import importlib.util
import inspect
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_adapters  # noqa: E402
import round_driver  # noqa: E402
import round_records  # noqa: E402

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
SEAT_MAP = {"seats": {dim: {"vendor": "claude", "model": "sonnet-5", "engine": "claude"}
                      for dim in round_driver.DIMENSIONS}}


def _load_advance_module():
    path = os.path.join(_HERE, "test_round_driver_advance.py")
    spec = importlib.util.spec_from_file_location("test_round_driver_advance_contract", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_ADV = _load_advance_module()


# Shape refusals at the seam — domain refusals (unknown seat, incomplete roster, etc.) are fine.
_ADAPTER_SHAPE_PREFIXES = (
    "envelopes-not-a-list:",
    "envelope-not-an-object:",
    "envelope-has-no-seat:",
    "envelope-bad-occurrence:",
    "canary-not-a-list:",
    "canary-entry-not-an-object:",
    "canary-entry-has-no-engine:",
    "dispatch-manifest-not-a-dict:",
)


def _adapter_shape_refusal(reason):
    if reason is None:
        return False
    return any(reason.startswith(prefix) for prefix in _ADAPTER_SHAPE_PREFIXES)


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude",
            "seatMap": SEAT_MAP}
    base.update(over)
    return base


def _session(tmp_path, name="contract"):
    d = str(tmp_path / name)
    os.makedirs(d, exist_ok=True)
    out = round_driver.cmd_next(d, _cfg())
    assert out["ok"], out
    return d


def _state(session_dir):
    ok, state = round_driver.load_state(session_dir)
    assert ok, state
    return state


def _pending(session_dir):
    return _state(session_dir)["pending"]


def _record_all_panel_seats(session_dir):
    for seat in round_driver.DIMENSIONS:
        _ADV._land_and_record(session_dir, seat)


def _write_canary_probes(session_dir, rnd, attempt, vendors):
    probes = []
    for vendor in vendors:
        probe = {"engine": vendor, "engaged": True, "evidence": {"probe": "seat_canary"}}
        path = round_records.canary_path(session_dir, rnd, vendor, attempt)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        round_records.atomic_write_json(path, probe)
        probes.append(probe)
    return probes


@pytest.fixture
def panel_ready(tmp_path):
    d = _session(tmp_path)
    _write_canary_probes(d, 1, 0, ["codex"])
    _record_all_panel_seats(d)
    return d


def _driver_boundary_values(session_dir):
    """Values the driver builds the way `_advance_locked` does, using real driver helpers."""
    state = _state(session_dir)
    pend = state["pending"]
    phase, rnd, attempt = pend["phase"], pend["round"], pend["attempt"]
    roster, reason = round_adapters.roster_for(phase, state, state.get("config") or {})
    assert reason is None, reason
    anchor = round_driver._orders_anchor(state, rnd, phase, attempt)
    slots = round_driver._seat_slot_records(session_dir, rnd, phase, attempt, roster)
    envelopes = [env for _seat, _occurrence, env in slots]
    manifest, _merr = round_records.read_json(
        round_records.dispatch_manifest_path(session_dir, rnd, phase, attempt))
    canary = round_driver._canary_landings(session_dir, state, rnd, attempt)
    return {
        "phase": phase,
        "envelopes": envelopes,
        "state": state,
        "config": state.get("config") or {},
        "dispatch_manifest": manifest if _merr is None else None,
        "canary": canary,
        "roster": roster,
        "anchor": anchor,
        "rnd": rnd,
        "attempt": attempt,
    }


def test_driver_adapter_assemble_boundary_is_shape_clean(panel_ready):
    vals = _driver_boundary_values(panel_ready)
    artifact, reason = round_adapters.assemble(
        vals["phase"], vals["envelopes"], vals["state"], vals["config"],
        dispatch_manifest=vals["dispatch_manifest"], canary=vals["canary"])
    assert not _adapter_shape_refusal(reason), reason
    assert isinstance(artifact, dict), reason


def test_driver_adapter_roster_and_policy_boundaries(panel_ready):
    vals = _driver_boundary_values(panel_ready)
    roster, reason = round_adapters.roster_for(vals["phase"], vals["state"], vals["config"])
    assert reason is None
    assert isinstance(roster, (list, tuple))
    policy = round_adapters.missing_policy(vals["phase"])
    assert isinstance(policy, str)


def test_driver_adapter_payload_fault_accepts_landed_payloads(panel_ready):
    vals = _driver_boundary_values(panel_ready)
    for env in vals["envelopes"]:
        if env.get("schema") != round_records.SEAT_RESULT_SCHEMA:
            continue
        fault = round_adapters.payload_fault(
            vals["phase"], env.get("payload"), env.get("seat"), record_boundary=True)
        assert fault is None, fault


def test_driver_records_ingest_boundary_accepts_driver_landings(panel_ready):
    vals = _driver_boundary_values(panel_ready)
    for env in vals["envelopes"]:
        seat = env.get("seat")
        occurrence = env.get("occurrence", 0)
        out = round_records.ingest_landing(
            panel_ready, vals["rnd"], vals["phase"], seat, vals["attempt"],
            current_attempt=vals["attempt"], roster=vals["roster"], anchor=vals["anchor"],
            occurrence=occurrence)
        assert out.get("ok") or out.get("reason") == "store-exists", out


def test_driver_canary_landings_matches_adapter_probe_list(panel_ready):
    vals = _driver_boundary_values(panel_ready)
    canary = vals["canary"]
    assert canary is None or isinstance(canary, list), type(canary)
    if isinstance(canary, list):
        assert all(isinstance(probe, dict) and probe.get("engine") for probe in canary)
    probes, fault = round_adapters._normalize_canary(canary)
    assert fault is None, fault


def test_driver_envelopes_are_a_list_not_a_seat_map(panel_ready):
    vals = _driver_boundary_values(panel_ready)
    assert isinstance(vals["envelopes"], list)
    indexed, fault = round_adapters._index_envelopes(
        vals["phase"], vals["envelopes"], vals["roster"])
    assert fault is None, fault
    assert isinstance(indexed, dict)


def test_driver_call_sites_cover_adapter_entry_points():
    """The driver reaches assemble/roster_for/payload_fault; missing_policy is assemble-internal."""
    driver_source = inspect.getsource(round_driver)
    for name in ("assemble", "roster_for", "payload_fault"):
        assert name in driver_source
        assert hasattr(round_adapters, name)
    assert hasattr(round_adapters, "missing_policy")
    assert "missing_policy" in inspect.getsource(round_adapters._assemble)


def test_driver_call_sites_cover_records_entry_points():
    driver_source = inspect.getsource(round_driver)
    for name in ("ingest_landing", "sweep_landing", "reconcile", "landing_path", "store_path"):
        assert name in driver_source
        assert hasattr(round_records, name)
