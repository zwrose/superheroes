"""#1272 layer 4a: how a seat proves it ran, and the audit cluster.

Item 1 — no step is handed out under an unrecognized disposition-ledger owner.
"""
import ast
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD  # noqa: E402
import session_contract as SC  # noqa: E402

_OWNER_CAUSE = "disposition-ledger-owner-unrecognized"


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, SC.STATE_FILE), "rb") as fh:
        return fh.read()


def _plant_owner(session_dir, value):
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    state[SC.DISPOSITION_LEDGER_OWNER_FIELD] = value
    RD.save_state(session_dir, state)


# --- item 1: the refusal at the one hand-out builder -----------------------------------------

def test_l4a_1_next_refuses_a_pending_dispatch_under_an_unrecognized_owner(tmp_path):
    # axis: an unrecognized owner refuses the re-emitted dispatch before anyone spends on it
    session_dir = str(tmp_path)
    first = RD.cmd_next(session_dir, _cfg())
    assert first["ok"] and first["phase"] == RD.P_PANEL, first
    _plant_owner(session_dir, "ledger-v2")
    before = _state_bytes(session_dir)
    out = RD.cmd_next(session_dir)
    assert out == {"ok": False, "reason": _OWNER_CAUSE}
    assert "expectedStateHash" not in out
    assert _state_bytes(session_dir) == before
    last = RD.read_journal(session_dir)[-1]
    assert last["cmd"] == "next"
    assert last["outcome"] == _OWNER_CAUSE
    assert last["phase"] == RD.P_PANEL


def test_l4a_1_null_owner_is_unrecognized_and_refuses_too(tmp_path):
    session_dir = str(tmp_path)
    assert RD.cmd_next(session_dir, _cfg())["ok"]
    _plant_owner(session_dir, None)
    assert RD.cmd_next(session_dir) == {"ok": False, "reason": _OWNER_CAUSE}


def test_l4a_1_recognized_and_absent_owners_still_hand_the_step_out(tmp_path):
    session_dir = str(tmp_path)
    first = RD.cmd_next(session_dir, _cfg())
    assert first["ok"]
    again = RD.cmd_next(session_dir)
    assert again["ok"] and again["expectedStateHash"] == first["expectedStateHash"]
    _plant_owner(session_dir, SC.DISPOSITION_LEDGER_OWNER_VALUE)
    assert RD.cmd_next(session_dir)["ok"]


def test_l4a_1_builder_refuses_for_every_caller_and_names_the_caller(tmp_path):
    session_dir = str(tmp_path)
    state = RD.new_state(_cfg())
    state[SC.DISPOSITION_LEDGER_OWNER_FIELD] = "ledger-v2"
    pending = {"action": RD.P_AUDITS, "round": 2, "phase": RD.P_AUDITS, "attempt": 0,
               "payload": {"targets": []}}
    out = RD._next_response(session_dir, RD.RE_EMIT_CMD, state, pending)
    assert out == {"ok": False, "reason": _OWNER_CAUSE}
    last = RD.read_journal(session_dir)[-1]
    assert (last["cmd"], last["phase"], last["round"], last["attempt"], last["outcome"]) == (
        RD.RE_EMIT_CMD, RD.P_AUDITS, 2, 0, _OWNER_CAUSE)


def test_l4a_1_a_terminal_step_still_answers_under_an_unrecognized_owner(tmp_path):
    # axis: a terminal hands nothing out — certification refuses it on its own path
    session_dir = str(tmp_path)
    state = RD.new_state(_cfg())
    state[SC.DISPOSITION_LEDGER_OWNER_FIELD] = "ledger-v2"
    pending = {"action": RD.P_TERMINAL, "round": 1, "phase": RD.P_TERMINAL, "attempt": 0,
               "payload": {"verdict": "cannot-certify"}}
    out = RD._next_response(session_dir, "next", state, pending)
    assert out["ok"] is True
    assert out["expectedStateHash"] == RD.state_hash(state)


def _driver_tree():
    with open(os.path.join(_LIB, "round_driver.py"), encoding="utf-8") as fh:
        return ast.parse(fh.read())


def test_l4a_1_census_the_step_echo_has_one_builder():
    """Every hand-out carries `expectedStateHash`; the key is built in exactly one function, so a
    new hand-out path that skips the refusal cannot exist without failing here."""
    tree = _driver_tree()
    owners = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and key.value == "expectedStateHash":
                        owners.append(fn.name)
            if (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
                    and node.slice.value == "expectedStateHash"
                    and isinstance(node.ctx, ast.Store)):
                owners.append(fn.name)
    assert owners == ["_next_response"], owners
