"""A saved session left at the retired fixer step is moved to `apply-fixes` before any command acts on it.

The fixtures under `fixtures/gen6_sessions/` are real generation-6 sessions, minted by the generation-6 driver;
`near-its-boundary` stands at its fixer step, `waiting-at-judgment` at an owner gate this version no longer has.
A test copies one to `tmp_path` before driving it; a fixture is never driven in place.

E12 a generation-6 state at the fixer step is migrated, not handed back; a state at a truly retired gate still is;
    a state of the current generation at the fixer step is migrated the same way.
"""
import json
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import session_checkout  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD

FIXTURES = os.path.join(_HERE, "fixtures", "gen6_sessions")
AT_FIXER = "near-its-boundary"
AT_RETIRED_GATE = "waiting-at-judgment"
RETIRED_FIXER = "dispatch-fixer"
MIGRATED = "fix-step-migrated"
HANDED_BACK = "retired-gate-hand-back"


def _bootstrap(tmp_path, name):
    """Copy the fixture session to `tmp_path`, give it a real checkout and point its meta at it."""
    session_dir = str(tmp_path / "session")
    shutil.copytree(os.path.join(FIXTURES, name), session_dir)
    checkout = os.path.join(session_dir, "checkout")
    session_checkout.enter_checkout(checkout)
    session_checkout.seed_session_meta(session_dir, checkout)
    return session_dir


def _state(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok and isinstance(state, dict), state
    return state


def _rows(session_dir, outcome):
    return [row for row in RD.read_journal(session_dir) if row.get("outcome") == outcome]


def _migrated_session(tmp_path, generation=None):
    session_dir = _bootstrap(tmp_path, AT_FIXER)
    state = _state(session_dir)
    assert state["step"] == RETIRED_FIXER and state["pending"]["phase"] == RETIRED_FIXER
    anchor = state["_ordersAnchors"]["%d:%s:%d" % (state["round"], RETIRED_FIXER, state["pending"]["attempt"])]
    if generation is not None:
        state["sessionGeneration"] = generation
        RD.save_state(session_dir, state)
    return session_dir, state, anchor


def test_e12_a_generation_6_session_at_the_fixer_step_is_migrated_not_handed_back(tmp_path):
    # axis: the migration runs before the retired-gate hand-back, so a generation-6 fixer step is moved on — see bite-proof record c1l9a_wo3_apply_fixes
    session_dir, before, anchor = _migrated_session(tmp_path)
    assert before["sessionGeneration"] == 6
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True and out["action"] == out["phase"] == RD.P_APPLY_FIXES, out
    assert out["round"] == before["round"]
    assert out["payload"]["startHead"] == anchor["headSha"]
    state = _state(session_dir)
    assert state["terminal"] is None and state["step"] == RD.P_APPLY_FIXES
    assert state["sessionGeneration"] == 6 and state["config"]["maxRounds"] == before["config"]["maxRounds"]
    assert "_escalatedRung" not in state and state["_fixStepHead"] == anchor["headSha"]
    (row,) = _rows(session_dir, MIGRATED)
    assert (row["phase"], row["round"], row["attempt"]) == (RETIRED_FIXER, before["round"],
                                                            before["pending"]["attempt"])
    assert _rows(session_dir, HANDED_BACK) == []
    assert not os.path.exists(os.path.join(session_dir, "round-%d" % before["round"], "orders",
                                           RD.P_APPLY_FIXES))


def test_e12_a_state_at_a_truly_retired_gate_is_still_handed_back(tmp_path):
    session_dir = _bootstrap(tmp_path, AT_RETIRED_GATE)
    assert _state(session_dir)["step"] not in (RETIRED_FIXER, RD.P_APPLY_FIXES)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True and out["action"] == RD.P_TERMINAL, out
    assert _state(session_dir)["terminal"] == "handed-back"
    assert len(_rows(session_dir, HANDED_BACK)) == 1 and _rows(session_dir, MIGRATED) == []


def test_e12_a_current_generation_state_at_the_fixer_step_is_migrated_the_same_way(tmp_path):
    session_dir, before, anchor = _migrated_session(tmp_path, generation=RD.SESSION_GENERATION)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True and out["action"] == RD.P_APPLY_FIXES, out
    assert out["payload"]["startHead"] == anchor["headSha"]
    assert len(_rows(session_dir, MIGRATED)) == 1 and _rows(session_dir, HANDED_BACK) == []
    # the step then folds as any apply-fixes report does
    state = _state(session_dir)
    assert state["pending"]["phase"] == RD.P_APPLY_FIXES and state["_fixStepHead"] == anchor["headSha"]


def test_e12_the_build_session_becomes_the_fix_maker_when_the_old_fixer_differs_from_the_host(tmp_path):
    session_dir, before, _anchor = _migrated_session(tmp_path)
    state = _state(session_dir)
    state["config"]["fixerVendor"] = "claude"
    state["config"]["seatMap"] = {"hostFamily": "openai"}
    state["seatMapReceipts"] = []
    state.pop("seatMap", None)
    host_vendor = RD._build_session_vendor({"hostFamily": "openai"})
    assert host_vendor not in (None, "claude")
    RD.save_state(session_dir, state)
    RD.cmd_next(session_dir)
    assert len(_rows(session_dir, MIGRATED)) == 1
    assert _state(session_dir)["config"]["fixerVendor"] == host_vendor


def test_e12_a_second_command_migrates_nothing_again(tmp_path):
    session_dir, _before, _anchor = _migrated_session(tmp_path)
    first = RD.cmd_next(session_dir)
    again = RD.cmd_next(session_dir)
    assert (again["phase"], again["attempt"], again["expectedStateHash"]) == (
        first["phase"], first["attempt"], first["expectedStateHash"])
    assert len(_rows(session_dir, MIGRATED)) == 1
