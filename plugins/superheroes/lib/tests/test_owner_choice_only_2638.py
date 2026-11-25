"""The owner-choice hand-back says whether nothing but the owner's choices stands between the session and a converge.

`_terminal_converged` hands a session back `handed-back` / `owner-choice-open` while a finding held for the
owner's choice is unsettled. That hand-back is stamped `certification.ownerChoiceOnly = True` exactly when no
owner fix or guidance ruling is still unsent to a fixer, no incomplete panel is outstanding, and the break-it
kept check (run after the hand-back's settle, recording nothing) finds nothing to park on. Otherwise the
hand-back is what it always was and `certification.ownerChoiceGap` names the one reason.

Pieces are driven directly on prepared states (no git, no loop) except the plain round-1 case, which runs the loop.

Bite-proof record: i2638_owner_choice_only
"""
import copy
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import session_contract as SC  # noqa: E402
import test_c1l4_gates_retired as G  # noqa: E402
import test_kept_head_resolver_2393 as KH  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD

_LOST_KEY = "g.py::lost test@L3"
_OPEN_DETAIL = "1 finding(s) need the owner's choice and are still open: widen the API"


def _choice_row(**over):
    row = {SC.FINDING_KEY_FIELD: G._CHOICE_KEY, "title": "widen the API", "file": "f.py", "line": 2,
           "severity": "Important", "consequence": TRD._CONSEQUENCE, "tradeoff": True,
           SC.RAISED_SEQ_FIELD: 1}
    row.update(over)
    return row


def _lost_row():
    """A carried finding that stands fixed whose break-it test the earlier record lost: the kept check parks on it."""
    return {SC.FINDING_KEY_FIELD: _LOST_KEY, "title": "lost test", "file": "g.py", "line": 3,
            "severity": "Important", "disposition": "fixed", "dispositionRound": 1,
            SC.DISPOSITION_SEQ_FIELD: 2, SC.RAISED_SEQ_FIELD: 1, RD.CARRIED_TEST_LOST_FIELD: True}


def _state(*extra_rows):
    """A session whose only open item is the held owner choice (a ledger row with no disposition yet)."""
    state = G._held_state()
    state[SC.DISPOSITION_LEDGER_KEY] = [_choice_row()] + list(extra_rows)
    return state


def _converge(state):
    RD._terminal_converged(state, state["config"], full_panel=True)
    return state


def _kinds(state):
    return [d["kind"] for d in state["decisions"]]


def _still_the_plain_hand_back(state):
    assert state["terminal"] == "handed-back"
    assert _kinds(state)[-1] == "owner-choice-open", _kinds(state)
    assert state["certification"]["shape"] is None
    assert state["certification"]["reason"] == _OPEN_DETAIL


def test_e1_a_pending_owner_ruling_leaves_the_gap_and_no_stamp():
    """axis: E1 — an owner ruling recorded but never sent to a fixer withholds the stamp, naming the ruling — see bite-proof record i2638_owner_choice_only"""
    control = _converge(_state())
    assert control["certification"]["ownerChoiceOnly"] is True, control["certification"]  # same state, no ruling: stamped
    state = _state()
    state["rulingsLog"] = [{"findingKey": G._CHOICE_KEY, "ruling": "guidance", "seq": 1,
                            "reason": "the owner wants it handled this way",
                            "guidance": "keep the public signature as it is"}]
    assert RD._pending_owner_rulings(state) == ["1 (guidance)"]
    _converge(state)
    _still_the_plain_hand_back(state)
    cert = state["certification"]
    assert "ownerChoiceOnly" not in cert, cert
    assert cert["ownerChoiceGap"].startswith("owner ruling(s) recorded but never sent"), cert
    assert cert["ownerChoiceGap"] == "owner ruling(s) recorded but never sent to a fixer: 1 (guidance)"


def test_e2_an_outstanding_incomplete_panel_leaves_the_gap_and_no_stamp():
    """axis: E2 — a configured lens that never ran, with no complete panel since, withholds the stamp, naming the panel — see bite-proof record i2638_owner_choice_only"""
    assert _converge(_state())["certification"]["ownerChoiceOnly"] is True  # same state, panel complete: stamped
    state = _state()
    state["_incompletePanel"] = True
    _converge(state)
    _still_the_plain_hand_back(state)
    cert = state["certification"]
    assert "ownerChoiceOnly" not in cert, cert
    assert cert["ownerChoiceGap"].startswith("panel incomplete"), cert
    assert "never ran" in cert["ownerChoiceGap"]


def test_e3_a_fixed_finding_whose_test_is_not_kept_leaves_the_gap_and_the_hand_back_alone():
    """axis: E3 — the post-settle kept check parks nothing and records nothing from the hand-back path; its detail becomes the gap — see bite-proof record i2638_owner_choice_only"""
    state = _state(_lost_row())
    rounds_before = copy.deepcopy(state.get("rounds"))
    _converge(state)
    _still_the_plain_hand_back(state)  # the terminal stays handed-back / owner-choice-open, never cannot-certify
    cert = state["certification"]
    assert "ownerChoiceOnly" not in cert, cert
    assert cert["ownerChoiceGap"] == ("break-it test not kept: the earlier session's test for %s was lost "
                                      "and no reviewer attached it again" % _LOST_KEY), cert
    assert "break-it-kept" not in _kinds(state) and "cannot-certify" not in _kinds(state), _kinds(state)
    assert state.get("rounds") == rounds_before, state.get("rounds")
    assert all("breakItKept" not in rec for rec in (state.get("rounds") or {}).values())


def test_e4_a_held_owner_choice_with_an_attached_break_it_test_and_nothing_else_open_is_stamped():
    """axis: E4 — the kept check runs after the settle, so the held choice's attached test reads not-required, not no-disposition — see bite-proof record i2638_owner_choice_only"""
    state = _state()
    state["rounds"] = {"1": {"breakItRuns": [{"findingKey": G._CHOICE_KEY, "path": "tests/test_widen.py",
                                              "outcome": "failed", "kind": "attached"}]}}
    before_settle = RD._break_it_kept_gap(copy.deepcopy(state), state["config"], record=False)
    assert before_settle is not None and "no-disposition" in before_settle, before_settle  # what an unsettled read would say
    rounds_before = copy.deepcopy(state["rounds"])
    _converge(state)
    _still_the_plain_hand_back(state)
    cert = state["certification"]
    assert cert["ownerChoiceOnly"] is True and "ownerChoiceGap" not in cert, cert
    held = {SC.finding_identity_key(e): e for e in state[SC.DISPOSITION_LEDGER_KEY]}[G._CHOICE_KEY]
    assert held["disposition"] == "left-for-owner", held
    assert state["rounds"] == rounds_before  # the hand-back path recorded no breakItKept row
    assert "break-it-kept" not in _kinds(state)


def test_e5_a_round_one_with_only_an_owner_choice_blocker_is_stamped_and_ends_on_owner_choice_open():
    """axis: E5 — the plain case through the real loop: stamped ownerChoiceOnly, and no decision follows the hand-back's — see bite-proof record i2638_owner_choice_only"""
    _result, state = TRD._run_loop_capturing_state(
        TRD._seams(reviewer=G._reviewer([G._CHOICE])), TRD._cfg_cert())
    assert state["terminal"] == "handed-back"
    assert _kinds(state)[-1] == "owner-choice-open", _kinds(state)
    assert state["certification"]["ownerChoiceOnly"] is True, state["certification"]
    assert "ownerChoiceGap" not in state["certification"]
    assert state["certification"]["shape"] is None
    assert "widen the API" in state["certification"]["reason"]
    assert sorted(state["rounds"]) == ["1"] and "breakItKept" not in state["rounds"]["1"]


# --- the kept check at the final commit, through a real repository (test_kept_head_resolver_2393's World) ---

def _world_with_a_held_choice(tmp_path):
    """A fixed break-it finding whose test the kept check runs at the session head, beside an unsettled held
    owner choice: the hand-back path reaches `check_kept` itself, past every early return."""
    world = KH.World(tmp_path)
    world.fixed_finding()
    world.state["ownerChoiceHeld"] = [G._CHOICE_KEY]
    world.state[SC.DISPOSITION_LEDGER_KEY].append(_choice_row())
    return world


def _hand_back_at(world):
    rounds_before = copy.deepcopy(world.state["rounds"])
    RD._terminal_converged(world.state, world.state["config"], full_panel=True, session_dir=world.session_dir)
    assert world.state["terminal"] == "handed-back"
    assert _kinds(world.state)[-1] == "owner-choice-open", _kinds(world.state)
    assert "break-it-kept" not in _kinds(world.state), _kinds(world.state)
    assert world.state["rounds"] == rounds_before  # the hand-back path recorded no breakItKept row
    return world.state["certification"]


def test_k1_a_kept_test_at_the_final_commit_is_checked_and_still_stamps(tmp_path):
    """axis: K-run — a fixed finding's test that passes at the final commit leaves the stamp, and the check writes nothing: the run record never stands in for the write flag — see bite-proof record i2638_owner_choice_only"""
    world = _world_with_a_held_choice(tmp_path)
    world.write_meta(headSha=world.fix())
    cert = _hand_back_at(world)
    assert cert["ownerChoiceOnly"] is True and "ownerChoiceGap" not in cert, cert


def test_k2_a_test_missing_at_the_final_commit_leaves_the_gap(tmp_path):
    """axis: K-head — a fixed finding's test absent from the final commit is found by the kept check on the hand-back path, so the gap names it and no stamp is set — see bite-proof record i2638_owner_choice_only"""
    world = _world_with_a_held_choice(tmp_path)
    world.fix()  # the fix exists, but the session head stays the setup head, which holds no test
    cert = _hand_back_at(world)
    assert "ownerChoiceOnly" not in cert, cert
    assert KH.TEST_PATH in cert["ownerChoiceGap"] and "not-in-head" in cert["ownerChoiceGap"], cert
