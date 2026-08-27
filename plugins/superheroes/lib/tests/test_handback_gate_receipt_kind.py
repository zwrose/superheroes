"""Handback gate classifies receipt shape through receipt_kind (#1107 WO-1107-b3)."""
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
HG = _load("handback_gate")


def _certified_receipt(verdict="converged"):
    return {
        "schema": RD.RECEIPT_CERTIFIED_SCHEMA % 3,
        "schemaVersion": 3,
        "verdict": verdict,
        "certificationShape": "audited-chain",
        "certification": {"shape": "audited-chain"},
        "scriptRan": {"byPhase": {}},
        "seatMap": {},
        "rounds": [],
        "findings": [],
        "decisions": [],
        "degraded": [],
        "skippedBlockers": [],
    }


def test_receipt_bindings_ok_classifies_interim_via_receipt_kind(monkeypatch):
    # axis: interim refusal follows receipt_kind, not raw schema byte-equality.
    receipt = {
        "schema": "receipt-interim/2",
        "verdict": "converged",
        "scriptRan": {"byPhase": {}},
        "seatMap": {},
        "rounds": [],
        "findings": [],
        "decisions": [],
        "degraded": [],
        "skippedBlockers": [],
    }
    monkeypatch.setattr(
        HG.RD,
        "receipt_kind",
        lambda r: RD.RECEIPT_INTERIM_SCHEMA if isinstance(r, dict) else None,
    )
    sidecar = {"verdict": "converged"}
    ok, why = HG._receipt_bindings_ok(sidecar, receipt)
    assert ok is False
    assert why == "receipt-interim-not-handback-evidence"


def test_receipt_bindings_ok_rejects_genuine_interim_receipt():
    interim = RD.build_interim_receipt(RD.new_state({"leg": "code"}), None, "tripwire")
    sidecar = {"verdict": "converged"}
    ok, why = HG._receipt_bindings_ok(sidecar, interim)
    assert ok is False
    assert why == "receipt-interim-not-handback-evidence"


def test_receipt_bindings_ok_accepts_valid_certified_receipt():
    receipt = _certified_receipt()
    sidecar = {"verdict": "converged"}
    ok, why = HG._receipt_bindings_ok(sidecar, receipt)
    assert ok is True
    assert why is None
