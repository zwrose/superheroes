"""#1272 layer 4a: unrecognized disposition-ledger owner refused before hand-out."""
import importlib.util
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
SC = _load("session_contract")


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}


def _unrecognized_owner_state():
    return {
        "schemaVersion": 5,
        "dispositionLedgerOwner": "ledger-v2",
        "dispositionLedger": [],
        "findings": [],
    }


def test_next_refuses_unrecognized_owner_on_stored_pending(tmp_path):
    """T1: idempotent re-emit of a stored non-terminal pending refuses before hand-out."""
    session_dir = str(tmp_path)
    n = RD.cmd_next(session_dir, _cfg())
    assert n["ok"], n
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    state["dispositionLedgerOwner"] = "ledger-v2"
    RD.save_state(session_dir, state)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is False
    assert out["reason"] == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE
    journal = RD.read_journal(session_dir)
    refused = [e for e in journal
               if e.get("outcome") == "refused"
               and e.get("reason") == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE]
    assert refused


def test_next_refuses_unrecognized_owner_on_fresh_advance(tmp_path):
    """T2: fresh advance with no stored pending refuses before hand-out."""
    session_dir = str(tmp_path)
    n = RD.cmd_next(session_dir, _cfg())
    assert n["ok"], n
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    state["dispositionLedgerOwner"] = "ledger-v2"
    state["pending"] = None
    RD.save_state(session_dir, state)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is False
    assert out["reason"] == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE


def test_disposition_ledger_owner_refusal_terminal_pending_not_refused(tmp_path):
    """T3: terminal pending with unrecognized owner is not refused at the ledger gate."""
    session_dir = str(tmp_path / "sess")
    os.makedirs(session_dir, exist_ok=True)
    with open(os.path.join(session_dir, RD.JOURNAL_FILE), "w", encoding="utf-8") as fh:
        fh.write("")
    state = _unrecognized_owner_state()
    state["round"] = 1
    pending = {
        "action": RD.P_TERMINAL,
        "round": 1,
        "phase": RD.P_TERMINAL,
        "attempt": 0,
        "payload": {"verdict": "converged"},
    }
    refusal = RD._disposition_ledger_owner_refusal(session_dir, state, pending, "next")
    assert refusal is None


def test_re_emit_refuses_unrecognized_disposition_ledger_owner(tmp_path):
    """A2: re-emit refuses before superseding when dispositionLedgerOwner is unrecognized."""
    session_dir = str(tmp_path)
    n = RD.cmd_next(session_dir, _cfg())
    assert n["ok"], n
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    old_attempt = state["pending"]["attempt"]
    state["dispositionLedgerOwner"] = "ledger-v2"
    RD.save_state(session_dir, state)
    out = RD.cmd_re_emit(session_dir, "tester")
    assert out["ok"] is False
    assert out["reason"] == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE
    ok, state = RD.load_state(session_dir)
    assert state["pending"]["attempt"] == old_attempt


def test_next_response_call_sites_pass_state():
    """T4: every _next_response call site passes state (four-argument form)."""
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    assert src.count("def _next_response(") == 1
    calls = re.findall(r"_next_response\([^)]+\)", src)
    assert calls, "expected at least one _next_response call site"
    for call in calls:
        assert "state" in call, "call site missing state argument: %s" % call
