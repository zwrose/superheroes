#!/usr/bin/env python3
"""#1720 — the review loop reads, records and discloses nothing about a planted-defect probe.

`canaryResult` survives only as a tolerated envelope key (an older-shaped panel artifact that
still carries it is accepted and the key is ignored), and a round record written by an older
version that still carries a removed probe channel builds a receipt without raising.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_EVAL = os.path.join(os.path.dirname(_LIB), "eval")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver  # noqa: E402

_PROBE_CHANNELS = (
    "canaryUnverified", "canaryFailed", "canaryOutcomeFailed", "canaryPlantUndetected",
    "canaryVerified", "controlProbe",
)

_SHIPPED_SOURCES = (
    os.path.join(_LIB, "round_driver.py"),
    os.path.join(_LIB, "round_adapters.py"),
    os.path.join(_LIB, "round_records.py"),
    os.path.join(_LIB, "receipt_disclosures.py"),
    os.path.join(_LIB, "decision_kinds.py"),
    os.path.join(_LIB, "seat_map_receipts.py"),
    os.path.join(_EVAL, "review_loop_runner.py"),
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _minimal_state(round_entry):
    state = round_driver.new_state({"leg": "code", "vendors": ["claude"]})
    state["schemaVersion"] = 3
    state["terminal"] = "converged"
    state["certification"] = {"shape": "audited-chain"}
    state["rounds"] = {"1": round_entry}
    return state


def test_panel_fold_records_no_probe_channel():
    """A well-formed probe list on the artifact is ignored: nothing is recorded, nothing decided."""
    cfg = {"leg": "panel", "vendors": ["claude", "codex"], "fixerVendor": "claude"}
    state = round_driver.new_state(cfg)
    seats = {d: {"findings": []} for d in round_driver.DIMENSIONS}
    seat_map = {"seats": {d: {"vendor": "claude"} for d in round_driver.DIMENSIONS}}
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    probe = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 1}, "detectedPlant": True, "detail": "live",
    }
    round_driver._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": [probe],
    })
    r1 = state["rounds"]["1"]
    assert r1["seatStatus"]["code-reviewer"] == "run"
    assert not [k for k in _PROBE_CHANNELS if k in r1], sorted(r1)
    kinds = [d["kind"] for d in (state.get("decisions") or [])]
    assert not [k for k in kinds if k.startswith("canary-")], kinds


def test_older_shaped_artifact_with_canary_result_key_is_not_refused():
    assert round_driver.panel_seat_key_fault(
        ["code-reviewer"],
        {"code-reviewer": {"findings": []}, "canaryResult": {"engine": "codex"}}) is None


def test_old_round_record_probe_keys_are_dropped_from_the_receipt():
    """Edge E1: a round record from an older version carries removed channels; none is emitted."""
    entry = {
        "controlProbe": {"submitted": False, "vendors": {}},
        "canaryVerified": {},
        "canaryUnverified": ["premortem-reviewer"],
    }
    receipt = round_driver.build_receipt(_minimal_state(entry))
    rounds = receipt.get("rounds") or []
    assert len(rounds) == 1
    assert not [k for k in entry if k in rounds[0]], sorted(rounds[0])


def test_no_shipped_module_reads_a_probe_result():
    for path in _SHIPPED_SOURCES:
        text = _read(path).lower()
        assert "controlprobe" not in text and "control_probe" not in text, path
        if os.path.basename(path) == "round_driver.py":
            # Only the tolerated envelope-key declaration (and its comment) may name the key.
            text = "\n".join(
                line for line in text.splitlines()
                if not (line.lstrip().startswith("#")
                        or line.startswith("_panel_envelope_keys")))
        assert "canary" not in text, path
    assert "canaryResult" in round_driver._PANEL_ENVELOPE_KEYS


def _complete_round_two_panel(**extra):
    cfg = {"leg": "panel", "vendors": ["claude", "codex"], "fixerVendor": "claude"}
    state = round_driver.new_state(cfg)
    state["round"] = 2
    seats = {d: {"findings": []} for d in round_driver.DIMENSIONS}
    artifact = {"seats": seats}
    artifact.update(extra)
    round_driver._fold_panel(state, state["config"], artifact)
    return state


def test_complete_panel_certifies_with_or_without_legacy_canary_result():
    """A complete panel is unaffected by a legacy canaryResult: ignored, not read."""
    for extra in ({}, {"canaryResult": [{"engine": "codex", "outcome": "ok"}]}):
        state = _complete_round_two_panel(**extra)
        assert state["fullPanelRan"] is True, extra
        assert state["_incompletePanel"] is False, extra
        assert "confirmations" not in state, extra
        assert state["rounds"]["2"]["lensCoverage"]["floor"] is False, extra
