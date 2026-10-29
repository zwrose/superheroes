"""C1-L4b: the two owner-choice fixes of the gate removal, each with a test of its own.

  - a held owner-choice finding that was merged into a representative whose ledger row carries a
    current `fixed` disposition is settled by that disposition, so the session converges;
  - a blocking tradeoff finding the owner already ruled on with guidance is not held again.

Drives the round driver's own functions on built states: `_terminal_converged` for the first,
`_hold_owner_choice` after the real `rule` verb (`cmd_rule` on a session directory) for the second.

Bite-proof record: c1l4b_wo_c
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import session_contract as SC  # noqa: E402
import test_outcome_settle_c7 as TOC  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # the same load of the driver the other driver tests run on

_MEMBER_KEY = "f.py::widen the api@L2"
_REP_KEY = "f.py::widen the api surface@L2"
_CHOICE = {"title": "widen the API", "severity": "Important", "consequence": TRD._CONSEQUENCE,
           "consequenceKind": "real", "file": "f.py", "line": 2, "tradeoff": True}


def _kinds(state):
    return [d["kind"] for d in state["decisions"]]


# --- the merged-member branch of _owner_choice_settled -----------------------------------------

def _merged_held_state(disposition_seq):
    """A held owner choice (the member) merged into a representative the ledger reads `fixed`.

    The member was raised at seq 3 and the representative at seq 2, so the representative's
    disposition is current against its own raise for any `disposition_seq` above 2, and current
    against the member's raise only above 3."""
    state = RD.new_state(TRD._cfg_cert())
    state["ownerChoiceHeld"] = [_MEMBER_KEY]
    state[SC.DISPOSITION_LEDGER_OWNER_FIELD] = SC.DISPOSITION_LEDGER_OWNER_VALUE
    member = {SC.FINDING_KEY_FIELD: _MEMBER_KEY, "title": "widen the API", "file": "f.py",
              "line": 2, "severity": "Important", "tradeoff": True,
              SC.MERGED_INTO_FIELD: _REP_KEY, SC.RAISED_SEQ_FIELD: 3}
    representative = {SC.FINDING_KEY_FIELD: _REP_KEY, "title": "widen the API surface",
                      "file": "f.py", "line": 2, "severity": "Important",
                      "disposition": "fixed", "dispositionRound": 2,
                      SC.DISPOSITION_SEQ_FIELD: disposition_seq, SC.RAISED_SEQ_FIELD: 2}
    state["findings"] = [dict(member)]
    state[SC.DISPOSITION_LEDGER_KEY] = [dict(member), representative]
    return state


def test_a_merged_owner_choice_is_settled_by_its_fixed_representative_and_the_session_converges():
    # axis: a merged member settled by its fixed representative converges — see bite-proof record c1l4b_wo_c
    state = _merged_held_state(disposition_seq=4)  # above the member's raise (3) and its own (2)
    assert RD._unsettled_owner_choices(state) == []
    RD._terminal_converged(state, state["config"], full_panel=False)
    assert state["terminal"] == "converged"
    assert state["terminal"] != "handed-back"
    assert "owner-choice-open" not in _kinds(state)
    assert _kinds(state)[-1] == "converged"


def test_a_merged_owner_choice_whose_representative_was_fixed_before_the_member_was_raised_is_handed_back():
    # axis: A/B for the test above — a representative disposition not above the member's raise settles nothing
    state = _merged_held_state(disposition_seq=3)  # current against its own raise (2), not the member's (3)
    representative = state[SC.DISPOSITION_LEDGER_KEY][1]
    assert RD._disposition_is_current(representative)  # only the member's later raise is in the way
    RD._terminal_converged(state, state["config"], full_panel=False)
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == "owner-choice-open"
    assert state["certification"]["shape"] is None
    assert "owner-choice-held" not in _kinds(state)


# --- _decided_to_fix in _hold_owner_choice -----------------------------------------------------

def _session_with_choice(tmp_path, ruling):
    """A saved session holding one blocking tradeoff finding; `ruling` is applied through `rule`."""
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    state = TOC._staged_state([dict(_CHOICE)])
    RD.save_state(session_dir, state)
    key = RD._finding_identity_key(state["findings"][0])
    if ruling is not None:
        path = TOC._write_rulings(tmp_path / "rulings.json", [dict(ruling, id=key)])
        out = RD.cmd_rule(session_dir, path, "owner")
        assert out.get("ok"), out
    ok, state = RD.load_state(session_dir)
    assert ok
    finding = next(f for f in state["findings"] if RD._finding_identity_key(f) == key)
    assert finding.get("tradeoff") is True
    return state, finding, key


_GUIDANCE = {"ruling": "guidance", "reason": "owner call", "guidance": "keep the retry loop"}


def test_a_tradeoff_the_owner_ruled_guidance_on_is_not_held_again_in_a_later_round(tmp_path):
    # axis: a tradeoff the owner already ruled on is not held again — see bite-proof record c1l4b_wo_c
    state, finding, key = _session_with_choice(tmp_path, _GUIDANCE)
    effective = RD._live_ruling_by_key(state)[key]
    assert effective["ruling"] == "guidance"  # the ruling went in through the real `rule` path
    batch = RD._hold_owner_choice(state, [finding])
    assert batch == [finding]
    assert key not in (state.get("ownerChoiceHeld") or [])
    assert "owner-choice-held" not in _kinds(state)


def test_the_same_tradeoff_with_no_ruling_is_held_out_of_the_batch(tmp_path):
    # axis: A/B for the test above — without the owner's ruling the finding is held and journaled
    state, finding, key = _session_with_choice(tmp_path, None)
    assert key not in RD._live_ruling_by_key(state)
    batch = RD._hold_owner_choice(state, [finding])
    assert batch == []
    assert state["ownerChoiceHeld"] == [key]
    assert _kinds(state).count("owner-choice-held") == 1
