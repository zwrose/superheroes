"""#1272 WO-3: terminal-receipt faults carry a typed class minted at the raise site."""
import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from test_round_driver import _certification_refusal_session


def test_receipt_write_fault_with_certification_in_path_is_a_write_fault(tmp_path, monkeypatch):
    session_dir = _certification_refusal_session(tmp_path / "certification-run")
    ok, state = RD.load_state(session_dir)
    assert ok, state
    RD._journal_append(session_dir, {"cmd": "submit", "phase": RD.P_PANEL, "round": 1,
                                     "attempt": 0})
    real_atomic_write_bytes = RD.round_commit.atomic_write_bytes

    def _fail_receipt_write(path, data):
        if os.path.basename(path) == RD.RECEIPT_FILE:
            raise OSError("[Errno 28] No space left on device: %r" % path)
        return real_atomic_write_bytes(path, data)

    monkeypatch.setattr(RD.round_commit, "atomic_write_bytes", _fail_receipt_write)
    fault = RD._terminal_receipt_gate(session_dir, state)
    assert isinstance(fault, RD.ReceiptFault)
    assert fault.kind == RD.RECEIPT_FAULT_WRITE
    assert "certification" in fault
    ok, state_after = RD.load_state(session_dir)
    assert ok, state_after
    assert state_after.get("_receiptFinalized") is True
    assert state_after.get("_receiptFaultClass") == RD.RECEIPT_FAULT_WRITE


def test_certification_artifact_fault_is_not_finalized(tmp_path):
    session_dir = _certification_refusal_session(tmp_path)
    os.makedirs(os.path.join(session_dir, RD.CERTIFICATION_REFUSAL_FILE))
    ok, state = RD.load_state(session_dir)
    assert ok, state
    RD._journal_append(session_dir, {"cmd": "submit", "phase": RD.P_PANEL, "round": 1,
                                     "attempt": 0})
    fault = RD._terminal_receipt_gate(session_dir, state)
    assert isinstance(fault, RD.ReceiptFault)
    assert fault.kind == RD.RECEIPT_FAULT_CERTIFICATION
    ok, state_after = RD.load_state(session_dir)
    assert ok, state_after
    assert not state_after.get("_receiptFinalized")
    assert state_after.get("_receiptFaultClass") == RD.RECEIPT_FAULT_CERTIFICATION


def test_verify_fault_kind(tmp_path):
    session_dir = _certification_refusal_session(tmp_path)
    fault = RD._verify_terminal_receipt(session_dir)
    assert isinstance(fault, RD.ReceiptFault)
    assert fault.kind == RD.RECEIPT_FAULT_VERIFY


def test_gate_refuses_untyped_fault(tmp_path, monkeypatch):
    session_dir = _certification_refusal_session(tmp_path)
    ok, state = RD.load_state(session_dir)
    assert ok, state
    RD._journal_append(session_dir, {"cmd": "submit", "phase": RD.P_PANEL, "round": 1,
                                     "attempt": 0})

    def _bare_str_fault(_session_dir, _state):
        return "terminal receipt write failed (simulated) — cannot certify; treat as park"

    monkeypatch.setattr(RD, "_finalize_receipt", _bare_str_fault)
    with pytest.raises(TypeError, match="terminal receipt fault without a class"):
        RD._terminal_receipt_gate(session_dir, state)


def test_receipt_fault_kinds_are_the_declared_set():
    assert RD.RECEIPT_FAULT_KINDS == (
        "receipt-write",
        "certification-artifact",
        "receipt-verify",
    )
