"""C1-L4b: a review already running under the earlier version (generation 6) finishes.

A generation-6 session finishes under the rules it started with. It keeps the round cap it stored at
its start (often 7), has no ceiling above it and no owner gate. One waiting at an owner gate this
version no longer has (the judgment gate, the stall menu) is handed back with every finding given an
outcome. Generation 5 and older, and any generation that is not exactly the integer 6, are refused as
before; so is a generation-6 state at an earlier schema version. A loaded generation-6 state is never
re-stamped.

The fixtures under `fixtures/gen6_sessions/` are real generation-6 sessions, minted by the
generation-6 driver itself (see the README there). A test copies one to `tmp_path` before driving it;
a fixture is never driven in place.

Bite-proof record: c1l4b_wo_b
"""
import copy
import json
import os
import shutil
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record as RR  # noqa: E402
import review_record_session as RS  # noqa: E402
import round_phases as RP  # noqa: E402
import session_checkout  # noqa: E402
import session_contract as SC  # noqa: E402
import test_review_record_session as TRRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # the driver on test_round_driver's own load of the module

FIXTURES = os.path.join(_HERE, "fixtures", "gen6_sessions")
JUDGMENT = "waiting-at-judgment"
STALL_MENU = "waiting-at-stall-menu"
BOUNDARY = "near-its-boundary"
STORED_CAP = 7
OWNER_CHOICE_OPEN = "owner-choice-open"
FIX_KEEPS_FAILING = "fix-keeps-failing"


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


def _fixture_state(name):
    """The fixture's saved state, read and never written."""
    with open(os.path.join(FIXTURES, name, RD.STATE_FILE), encoding="utf-8") as fh:
        return json.load(fh)


def _disk_generation(session_dir):
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        return json.load(fh)["sessionGeneration"]


def _accepted_rows(session_dir):
    return [row for row in RD.read_journal(session_dir) if row.get("outcome") == "accepted"]


def _ledger(state):
    return {SC.finding_identity_key(row): row for row in state.get(SC.DISPOSITION_LEDGER_KEY) or []}


def _assert_every_finding_has_an_outcome(state):
    ledger = _ledger(state)
    assert ledger, state.get(SC.DISPOSITION_LEDGER_KEY)
    for key, row in ledger.items():
        assert row.get("disposition") in SC.DISPOSITIONS, (key, row)
    for finding in state.get("findings") or []:
        if isinstance(finding, dict) and not finding.get("summaryEntry"):
            assert SC.finding_identity_key(finding) in ledger, finding


def _account(session_dir):
    account = RS.account_from_session(session_dir, TRRS.extras())
    RR._validate(account)
    return account


def _drive_to_terminal(session_dir, respond):
    """next/submit with scripted artifacts to the terminal; returns every `next` answer."""
    answers = []
    for _ in range(200):
        n = RD.cmd_next(session_dir)
        assert n["ok"], n
        answers.append(n)
        if n["action"] == RD.P_TERMINAL:
            return answers
        art = TRD._claim_reviewer(session_dir, n["phase"], respond(n["phase"], n["payload"], n["round"]))
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    raise AssertionError("the loop did not reach a terminal")


# --- G1 / G2: a session waiting at a gate this version no longer has is handed back -------------

def test_g1_a_session_waiting_at_the_retired_judgment_gate_is_handed_back(tmp_path):
    # axis: a step outside ALL_PHASES hands the session back before any command acts on it — see bite-proof record c1l4b_wo_b
    session_dir = _bootstrap(tmp_path, JUDGMENT)
    before = _state(session_dir)
    assert before["step"] not in RP.ALL_PHASES and before["pending"]["phase"] not in RP.ALL_PHASES
    held = [RD._finding_key_of(f) for f in before["_judgmentFindings"]]
    assert held
    n = RD.cmd_next(session_dir)
    assert n["ok"] and n["action"] == RD.P_TERMINAL, n
    assert n["payload"]["verdict"] == "handed-back", n
    state = _state(session_dir)
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == OWNER_CHOICE_OPEN
    assert state["pending"]["phase"] == RD.P_TERMINAL
    assert state["ownerChoiceHeld"] == held
    _assert_every_finding_has_an_outcome(state)
    assert _disk_generation(session_dir) == 6
    account = _account(session_dir)
    assert account["rounds"]["cap"] == state["config"]["maxRounds"] == STORED_CAP
    assert account["rounds"]["stoppedAtCap"] is False
    assert account["findings"] and all(f.get("outcome") for f in account["findings"]), account["findings"]


def test_g2_a_session_waiting_at_the_retired_stall_gate_is_handed_back(tmp_path):
    # axis: the judgment gate and the stall menu hand back under different decision kinds — see bite-proof record c1l4b_wo_b
    session_dir = _bootstrap(tmp_path, STALL_MENU)
    before = _state(session_dir)
    assert before["step"] not in RP.ALL_PHASES and before["pending"]["phase"] not in RP.ALL_PHASES
    assert not before.get("_judgmentFindings") and before["_stallChoices"] and before["_stallTargets"]
    n = RD.cmd_next(session_dir)
    assert n["ok"] and n["action"] == RD.P_TERMINAL, n
    assert n["payload"]["verdict"] == "handed-back", n
    state = _state(session_dir)
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == FIX_KEEPS_FAILING
    assert not state.get("ownerChoiceHeld")
    _assert_every_finding_has_an_outcome(state)
    assert _disk_generation(session_dir) == 6
    account = _account(session_dir)
    assert account["rounds"]["cap"] == state["config"]["maxRounds"] == STORED_CAP
    assert account["rounds"]["stoppedAtCap"] is False
    assert account["findings"] and all(f.get("outcome") for f in account["findings"]), account["findings"]


def test_a_retired_step_that_cannot_be_classified_is_handed_back_as_a_failing_fix():
    state = _fixture_state(STALL_MENU)
    for name in RD.RETIRED_STALL_FIELDS:
        state.pop(name)
    assert RD._finish_retired_gate_step(state) is True
    assert state["terminal"] == "handed-back" and state["pending"] is None
    last = state["decisions"][-1]
    assert last["kind"] == FIX_KEEPS_FAILING and "could not be classified" in last["detail"], last


def test_a_state_that_is_not_an_unfinished_continuable_generation_is_left_as_it_is():
    current = RD.new_state(TRD._cfg())
    current["step"] = "a-step-nothing-emits"
    finished = _fixture_state(JUDGMENT)
    finished["terminal"] = "handed-back"
    for state in (current, finished):
        before = copy.deepcopy(state)
        assert RD._finish_retired_gate_step(state) is False
        assert state == before


# --- G3: a session in its stored last round finishes it and begins no round after it ------------

def test_g3_a_generation_six_session_runs_its_stored_cap_round_and_begins_no_round_after_it(tmp_path):
    # axis: an unfinished state of a continuable earlier generation at the current schema is not refused — see bite-proof record c1l4b_wo_b
    session_dir = _bootstrap(tmp_path, BOUNDARY)
    before = _state(session_dir)
    assert before["round"] == STORED_CAP == before["config"]["maxRounds"] and not before.get("terminal")
    assert any(f.get("severity") in ("Critical", "Important") for f in before["findings"])
    seq = {"n": 100}
    base = TRD._responder(round1_findings=[], vendors=TRD._cfg()["vendors"])

    def respond(phase, payload, rnd):
        if phase == RD.P_FIXER:
            seq["n"] += 1
            return {"fixes": [], "headDiff": TRD._headf_ns(seq["n"]), "changedSubjects": ["Code"]}
        return base(phase, payload, rnd)

    answers = _drive_to_terminal(session_dir, respond)
    assert answers[0]["round"] == STORED_CAP
    for n in answers:
        assert n["action"] in RP.ALL_PHASES and n["phase"] in RP.ALL_PHASES, n
    assert max(n["round"] for n in answers) == STORED_CAP
    state = _state(session_dir)
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == "round-cap"
    assert "8" not in state["rounds"] and state["round"] == STORED_CAP
    assert state["config"]["maxRounds"] == STORED_CAP
    assert _disk_generation(session_dir) == 6
    account = _account(session_dir)
    assert account["rounds"]["cap"] == STORED_CAP and account["rounds"]["stoppedAtCap"] is True
    assert account["rounds"]["count"] == STORED_CAP


# --- G4: a retired gate's artifact is never folded ------------------------------------------------

@pytest.mark.parametrize("name,kind", [(JUDGMENT, OWNER_CHOICE_OPEN), (STALL_MENU, FIX_KEEPS_FAILING)])
@pytest.mark.parametrize("entry", ["advance", "submit"])
def test_g4_a_retired_gate_is_never_folded_through_advance_or_submit(entry, name, kind, tmp_path):
    session_dir = _bootstrap(tmp_path, name)
    before = _state(session_dir)
    stale_phase, stale_attempt = before["pending"]["phase"], before["pending"]["attempt"]
    stale_hash = RD.state_hash(before)
    accepted = _accepted_rows(session_dir)
    if entry == "advance":
        out = RD.cmd_advance(session_dir)
        assert out["ok"] is True and out["terminal"] == "handed-back" and out["idempotent"] is True, out
    else:
        out = RD.cmd_submit(session_dir, stale_phase, stale_attempt, stale_hash, {"choices": []})
        assert out["ok"] is False and "no pending step" in out["reason"], out
    after = _state(session_dir)
    assert after["terminal"] == "handed-back" and after["step"] == RD.P_TERMINAL
    assert after["decisions"][-1]["kind"] == kind
    assert len(after["decisions"]) == len(before["decisions"]) + 1  # the hand-back, and nothing folded
    assert _accepted_rows(session_dir) == accepted
    assert _disk_generation(session_dir) == 6


# --- G5: every other generation, and an older schema, is still refused ----------------------------

def _light_folder(tmp_path, generation, version=None):
    session_dir = str(tmp_path / "light")
    os.makedirs(session_dir)
    state = RD.new_state(TRD._cfg())
    state["terminal"] = None
    state["sessionGeneration"] = generation
    if version is not None:
        state["schemaVersion"] = version
    with open(os.path.join(session_dir, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)
    return session_dir


@pytest.mark.parametrize("generation", [5, True, 6.0, "6", 8],
                         ids=["five", "true", "float-six", "string-six", "eight"])
def test_g5_a_generation_that_is_not_exactly_the_integer_six_is_still_refused(generation, tmp_path):
    # axis: a generation stamped true, 6.0 or "6" is not generation 6 and stays refused — see bite-proof record c1l4b_wo_b
    session_dir = _light_folder(tmp_path, generation)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is False and out["reason"] == RD.SESSION_FROM_EARLIER_VERSION, out


def test_g5_a_generation_six_state_at_an_older_schema_version_is_still_refused(tmp_path):
    older = 4
    assert older in RD.SUPPORTED_STATE_VERSIONS and older < RD.STATE_SCHEMA_VERSION
    session_dir = _light_folder(tmp_path, 6, version=older)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is False and out["reason"] == RD.SESSION_FROM_EARLIER_VERSION, out


# --- G6: a finished generation-6 session replays its terminal ------------------------------------

def test_g6_a_finished_generation_six_session_replays_its_terminal(tmp_path):
    session_dir = _bootstrap(tmp_path, JUDGMENT)
    first = RD.cmd_next(session_dir)
    assert first["ok"] and first["action"] == RD.P_TERMINAL, first
    on_disk = _state(session_dir)
    again = RD.cmd_next(session_dir)
    assert again["ok"] and again["action"] == RD.P_TERMINAL, again
    assert again["payload"] == first["payload"]
    assert _state(session_dir)["decisions"] == on_disk["decisions"]
    rows = [row for row in RD.read_journal(session_dir) if row.get("outcome") == "retired-gate-hand-back"]
    assert len(rows) == 1, rows
    assert _disk_generation(session_dir) == 6
    assert not os.path.exists(os.path.join(session_dir, RD.UPGRADE_RESTART_MARKER_FILE))
