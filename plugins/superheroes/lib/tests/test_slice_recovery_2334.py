"""A forfeited slice seat that a later unread-part wave re-ran, and read, counts as recovered (#2334).

On a sliced round 1 a slice seat that forfeits folds `missing`; its whole slice is owed by the next wave, whose seats of the same lens
are given it. When every lens obligation of every later wave was handed to that lens's slice seats and read by their own well-formed
lists, the seat is recovered: the panel is no longer incomplete, the record names the recovery, and the seat is no missing review.
A whole-change seat, a forfeit in the last wave, a malformed or empty read list and a wave with no evidence on record never recover.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/i2334_slice_recovery.md
"""
import copy
import os
import sys
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import countable_lines as cl  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_driver as RD  # noqa: E402
import round_phases as RP  # noqa: E402
import slicing  # noqa: E402
from test_review_record_session import EARLIER, Fake, Session, extras, put_envelope  # noqa: E402
from test_sliced_panel_c2 import RISK_AREAS, _core_md, _pin_git, _repo, _state, _three_thousand  # noqa: E402,F401
from test_unread_waves_c2 import FIRST, _slice  # noqa: E402

FORFEIT = {"findings": [], "receiptMissing": True}
S1 = "code-reviewer:s1"
S2 = "code-reviewer:s2"


def _run(state, reads=None, forfeit=(), omit=(), payloads=None):
    """Fold one panel wave over the state's current roster and return the payloads submitted. A slice seat reads its whole slice
    unless ``reads`` names a read list for it; a seat in ``forfeit`` submits a did-not-run payload; one in ``omit`` is left out;
    one in ``payloads`` submits exactly that payload."""
    seats = {}
    for key in RP.panel_roster(state, state["config"]):
        if key in omit:
            continue
        if key in (payloads or {}):
            seats[key] = copy.deepcopy(payloads[key])
            continue
        if key in forfeit:
            seats[key] = dict(FORFEIT)
            continue
        payload = {"findings": []}
        if RP.is_slice_seat(key):
            payload["readParts"] = copy.deepcopy((reads or {}).get(key, _slice(state, key.partition(":")[2])["parts"]))
        seats[key] = payload
    RD._fold(state, state["config"], RD.P_PANEL, {"seats": seats})
    return seats


def _kinds(state):
    return [d["kind"] for d in state["decisions"]]


def _forfeited_then_reread(tmp_path, **second):
    """The DoD-1 session: ``code-reviewer:s2`` forfeits in wave 1, wave 2 re-runs its slice (``second`` are wave 2's own options)."""
    state = _state(_repo(tmp_path), _three_thousand())
    first = _run(state, forfeit=(S2,))
    assert state["step"] == RD.P_PANEL and state["_sliceWave"] == 2
    return state, first, _run(state, **second)


def _not_recovered(state, seat=S2):
    assert state["_incompletePanel"] is True
    assert seat not in [r["seat"] for r in state.get("sliceRecoveries") or []]


# --- DoD 1: the recovery --------------------------------------------------------------------------------------------

def test_a_forfeited_slice_seat_whose_slice_a_later_wave_read_is_recovered_and_the_panel_is_no_longer_incomplete(tmp_path):
    state, _, _ = _forfeited_then_reread(tmp_path)
    assert state["rounds"]["1"]["seatStatus"][S2] == "missing" and state["rounds"]["1"]["missingSeats"] == [S2]
    assert state["_incompletePanel"] is False
    assert state["sliceRecoveries"] == [{"seat": S2, "round": 1, "wave": 1, "recoveredInWave": 2, "recoveredBy": ["code-reviewer:w2u1"]}]
    (decision,) = [d for d in state["decisions"] if d["kind"] == "slice-seat-recovered"]
    assert S2 in decision["detail"] and "code-reviewer:w2u1" in decision["detail"]
    assert state["fullPanelRan"] is False  # the forfeit stays in the history: the session certifies audited-chain
    assert state["rounds"]["1"]["lensCoverage"]["floor"] is True and state["rounds"]["1"]["seatStatus"][S2] == "missing"


def test_a_real_driven_session_whose_wave_one_slice_seat_forfeits_and_is_re_read_converges(tmp_path, monkeypatch):
    import test_round_driver_integration as drive
    forfeiting = "code-reviewer:s1"
    monkeypatch.setattr(cl, "COUNTABLE_LINES_BAR", 20)
    real_repo = drive._fixture_repo

    def repo_with_risk_areas(tmp, name):
        root = real_repo(tmp, name)
        core = os.path.join(root, ".claude", "superheroes", "core.md")
        os.makedirs(os.path.dirname(core), exist_ok=True)
        with open(core, "wb") as fh:
            fh.write(_core_md(RISK_AREAS))
        return root

    monkeypatch.setattr(drive, "_fixture_repo", repo_with_risk_areas)
    session_dir, gitdir, head_path = drive._bootstrap(tmp_path)
    assert drive._state(session_dir)["slicePlan"]["sliced"] is True
    real_payload = drive._payload_for

    def payload_with_reads(sdir, state, pend, seat, panel_findings, head_diff_path):
        body = real_payload(sdir, state, pend, seat, panel_findings, head_diff_path)
        if pend["phase"] == drive.round_driver.P_PANEL and RP.is_slice_seat(seat):
            if seat == forfeiting:
                return dict(FORFEIT)
            body["readParts"] = copy.deepcopy(_slice(state, seat.partition(":")[2])["parts"])
        return body

    with mock.patch.object(drive, "_payload_for", payload_with_reads):
        for _ in range(30):
            state = drive._state(session_dir)
            if state.get("terminal"):
                break
            phase, out = drive._drive_one_phase(session_dir, gitdir, [], head_path)
            assert out["ok"], (phase, out)
        else:
            raise AssertionError("no terminal in 30 phases")
    state = drive._state(session_dir)
    assert state["rounds"]["1"]["seatStatus"][forfeiting] == "missing"
    assert [r["seat"] for r in state["sliceRecoveries"]] == [forfeiting]
    assert state["terminal"] == "converged" and state["terminal"] != "cannot-certify"


# --- DoD 2: what is not a recovery ----------------------------------------------------------------------------------

def test_a_wave_two_seat_that_also_forfeits_with_the_bound_reached_leaves_the_seat_unrecovered(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,))
    _run(state, forfeit=("code-reviewer:w2u1",))
    assert state["step"] == RD.P_PANEL and state["_sliceWave"] == 3
    _run(state, forfeit=("code-reviewer:w3u1",))
    assert state["step"] == RD.P_SEAMS and state["unreadShare"]["parts"]
    _not_recovered(state)
    assert "sliceRecoveries" not in state and "slice-seat-recovered" not in _kinds(state)


def test_a_wave_two_seat_that_read_nothing_twice_over_leaves_the_code_obligations_in_the_residual_and_the_seat_unrecovered(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,))
    _run(state, reads={"code-reviewer:w2u1": []})
    assert state["step"] == RD.P_PANEL and state["_sliceWave"] == 3
    _run(state, reads={"code-reviewer:w3u1": []})
    assert state["unreadShare"]["parts"]
    _not_recovered(state)
    assert "sliceRecoveries" not in state


def test_a_last_wave_seat_that_read_only_part_of_its_slice_leaves_a_residual_of_the_lens_and_the_seat_unrecovered(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,))
    _run(state, reads={"code-reviewer:w2u1": []})
    _run(state, reads={"code-reviewer:w3u1": [{"file": "pkg/f1.py", "lines": [[1, 10]]}]})
    assert state["_sliceReadsChecked"][2] == {"wave": 3, "malformed": [], "empty": []}
    assert [p["file"] for p in state["unreadShare"]["parts"]] == ["pkg/f1.py"]
    _not_recovered(state)
    assert "sliceRecoveries" not in state


def test_a_wave_two_seat_whose_read_list_mixes_a_valid_range_and_an_invalid_one_is_a_malformed_list_and_no_recovery(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,))
    covering = copy.deepcopy(_slice(state, "w2u1")["parts"])
    covering[0]["lines"].append([9, 3])
    _run(state, reads={"code-reviewer:w2u1": covering})
    while state["step"] == RD.P_PANEL:
        _run(state)
    assert state["_sliceReadsChecked"][1] == {"wave": 2, "malformed": ["code-reviewer:w2u1"], "empty": []}
    _not_recovered(state)


def test_a_chain_through_a_wave_whose_seat_read_nothing_is_recovered_by_the_wave_that_read_and_never_names_the_silent_seat(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,))
    _run(state, reads={"code-reviewer:w2u1": []})
    assert state["_sliceReadsChecked"][1] == {"wave": 2, "malformed": [], "empty": ["code-reviewer:w2u1"]}
    _run(state)
    assert state["_incompletePanel"] is False
    assert state["sliceRecoveries"] == [{"seat": S2, "round": 1, "wave": 1, "recoveredInWave": 3, "recoveredBy": ["code-reviewer:w3u1"]}]


@pytest.mark.parametrize("bad", [None, "all of it", {"file": "pkg/f1.py"}, [{"file": "", "lines": []}], [{"file": "pkg/f1.py", "lines": "1-5"}]])
def test_a_read_list_that_is_absent_not_a_list_or_has_one_bad_entry_is_malformed(tmp_path, bad):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,))
    seats = {k: {"findings": [], "readParts": copy.deepcopy(_slice(state, k.partition(":")[2])["parts"])}
             for k in RP.panel_roster(state, state["config"]) if RP.is_slice_seat(k)}
    seats["code-reviewer:w2u1"].pop("readParts")
    if bad is not None:
        seats["code-reviewer:w2u1"]["readParts"] = bad
    RD._fold(state, state["config"], RD.P_PANEL, {"seats": seats})
    while state["step"] == RD.P_PANEL:
        _run(state)
    assert "code-reviewer:w2u1" in state["_sliceReadsChecked"][1]["malformed"]
    _not_recovered(state)


# --- who is named: only the seats handed part of the forfeited slice (V798-1, V798-2) -------------------------------------

def _wave_two_code_seats(state):
    return [k for k in RP.panel_roster(state, state["config"]) if k.startswith("code-reviewer:w2u")]


def _given_part_of(state, parts, seats):
    """The seats among ``seats`` whose slice overlaps ``parts``, by the same predicate the recovery uses."""
    none = slicing.unread_obligations({"o": parts}, {"o": []})
    return [k for k in seats if slicing.unread_obligations({"o": parts}, {"o": _slice(state, k.partition(":")[2])["parts"]}) != none]


def test_a_recovery_names_only_the_wave_two_seat_given_the_forfeited_part_not_the_other_slice_of_the_lens(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    s1_parts, s2_parts = copy.deepcopy(_slice(state, "s1")["parts"]), copy.deepcopy(_slice(state, "s2")["parts"])
    _run(state, reads={S1: []}, forfeit=(S2,))
    assert state["step"] == RD.P_PANEL and state["_sliceWave"] == 2
    code = _wave_two_code_seats(state)
    assert len(code) == 2
    held_s1 = [k for k in code if _slice(state, k.partition(":")[2])["parts"] == s1_parts]
    held_s2 = [k for k in code if _slice(state, k.partition(":")[2])["parts"] == s2_parts]
    assert len(held_s1) == 1 and len(held_s2) == 1 and held_s1 != held_s2
    (other,), (given,) = held_s1, held_s2
    _run(state)
    assert state["_incompletePanel"] is False
    (entry,) = state["sliceRecoveries"]
    assert entry == {"seat": S2, "round": 1, "wave": 1, "recoveredInWave": 2, "recoveredBy": [given]}
    (decision,) = [d for d in state["decisions"] if d["kind"] == "slice-seat-recovered"]
    assert given in decision["detail"] and other not in decision["detail"]
    session = Session(tmp_path / "rec", rounds=state["rounds"], unreadShare=state["unreadShare"], sliceRecoveries=state["sliceRecoveries"])
    account = rs.account_from_session(session.save(), extras(), Fake().readers())
    text = rr.render(rr.build_record(account, Fake().readers()))
    assert ("Recovered by an unread-part wave: code-reviewer:s2 (round 1) forfeited in wave 1; "
            "wave 2 re-ran its slice (%s) on aaaaaaa." % given) in text
    (line,) = [ln for ln in text.splitlines() if "Recovered by an unread-part wave" in ln]
    assert other not in line


def test_a_forfeited_seats_own_complete_read_list_counts_for_nothing_so_its_slice_is_still_handed_on_and_read_by_a_later_seat(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    whole = copy.deepcopy(_slice(state, "s2")["parts"])
    partial = [{"file": FIRST, "lines": [[1, 10]]}]
    _run(state, reads={S1: partial}, payloads={S2: dict(FORFEIT, readParts=copy.deepcopy(whole))})
    assert state["rounds"]["1"]["seatStatus"][S2] == "missing"
    assert state["step"] == RD.P_PANEL and state["_sliceWave"] == 2
    code = _wave_two_code_seats(state)
    handed = [p for k in code for p in _slice(state, k.partition(":")[2])["parts"]]
    assert slicing.unread_obligations({"o": whole}, {"o": handed}) == []
    (given,) = _given_part_of(state, whole, code)
    _run(state)
    assert state["_incompletePanel"] is False
    (entry,) = state["sliceRecoveries"]
    assert entry["seat"] == S2 and entry["recoveredBy"] == [given]


# --- fail-closed edges ----------------------------------------------------------------------------------------------

def test_a_forfeit_in_the_last_wave_is_never_recovered(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, reads={"test-role:s1": []})
    _run(state, reads={"test-role:w2u1": []})
    assert state["_sliceWave"] == 3
    _run(state, forfeit=("code-reviewer:w3u1",))
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer:w3u1"] == "missing"
    _not_recovered(state, "code-reviewer:w3u1")
    assert "sliceRecoveries" not in state


def test_a_whole_change_seat_that_is_missing_keeps_the_panel_incomplete_though_the_slice_seats_recovery_is_recorded(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,), omit=("architecture-reviewer",))
    assert not RP.is_slice_seat("architecture-reviewer") and not RP.is_slice_seat("premortem-reviewer:w2")
    _run(state)
    assert state["rounds"]["1"]["seatStatus"]["architecture-reviewer"] == "missing"
    assert [r["seat"] for r in state["sliceRecoveries"]] == [S2]
    assert state["_incompletePanel"] is True and state["fullPanelRan"] is False


def test_a_session_saved_between_waves_by_code_that_kept_no_read_evidence_gives_no_recovery(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,))
    _run(state, reads={"code-reviewer:w2u1": []})
    state["_sliceReadsChecked"] = [c for c in state["_sliceReadsChecked"] if c["wave"] != 2]
    _run(state)
    assert [c["wave"] for c in state["_sliceReadsChecked"]] == [1, 3]
    _not_recovered(state)


@pytest.mark.parametrize("held", [None, "wave 1", [None], [["wave", 2]]])
def test_a_read_evidence_list_that_is_absent_or_malformed_between_waves_gives_no_recovery(tmp_path, held):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,))
    _run(state, reads={"code-reviewer:w2u1": []})
    if held is None:
        state.pop("_sliceReadsChecked")
    else:
        state["_sliceReadsChecked"] = held
    _run(state)
    _not_recovered(state)


def test_a_later_wave_whose_slices_were_not_given_the_forfeited_parts_gives_no_recovery(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,))
    _slice(state, "w2u1")["parts"] = [{"file": "pkg/f0.py", "lines": [[1, 10]]}]
    _run(state)
    assert state["unreadShare"]["parts"] == []
    _not_recovered(state)


def test_a_later_wave_with_no_record_of_what_it_owed_gives_no_recovery(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,))
    state["_sliceWaves"] = []
    _run(state)
    _not_recovered(state)


def test_a_seat_whose_slice_the_plan_does_not_hold_gives_no_recovery(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state, forfeit=(S2,))
    state["slicePlan"]["slices"] = [s for s in state["slicePlan"]["slices"] if s["id"] != "s2"]
    _run(state)
    _not_recovered(state)


def test_a_round_two_or_an_unsliced_session_records_no_recovery(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _run(state)
    RD._fold(state, state["config"], RD.P_SEAMS, {"findings": []})
    state["round"] = 2
    state["step"] = RD.P_PANEL
    dims = RP.panel_roster(state, state["config"])
    RD._fold(state, state["config"], RD.P_PANEL, {"seats": {d: dict(FORFEIT) if d == dims[0] else {"findings": []} for d in dims}})
    assert "sliceRecoveries" not in state and "_sliceReadsChecked" in state and len(state["_sliceReadsChecked"]) == 1
    assert "slice-seat-recovered" not in _kinds(state)


# --- the record -----------------------------------------------------------------------------------------------------

def _recovered_session(tmp_path, journaled):
    state, first, second = _forfeited_then_reread(tmp_path)
    kept = dict(rounds=state["rounds"], unreadShare=state["unreadShare"], sliceRecoveries=state["sliceRecoveries"])
    session = Session(tmp_path, **kept)
    if not journaled:
        return session.save(), state
    for attempt, seats in ((0, first), (1, second)):
        for key in seats:
            session.seat(key, attempt=attempt)
    path = session.save()
    for attempt, seats in ((0, first), (1, second)):
        for key, payload in seats.items():
            put_envelope(path, key, {"vendor": "codex", "model": "m", "payload": payload}, attempt=attempt)
    return path, state


@pytest.mark.parametrize("journaled", [True, False], ids=["journaled", "hand-submit"])
def test_the_account_carries_the_recovery_lists_no_missing_review_for_the_recovered_seat_and_the_record_shows_the_line(tmp_path, journaled):
    path, state = _recovered_session(tmp_path, journaled)
    account = rs.account_from_session(path, extras(), Fake().readers())
    assert account["sliceRecoveries"] == [dict(state["sliceRecoveries"][0], commit=EARLIER)]
    names = {r["name"]: r for r in account["reviewers"]}
    assert (S2 + " (round 1)") not in names
    assert not [r for r in account["reviewers"] if not r["ran"] and r["name"].startswith("code-reviewer")]
    assert "code-reviewer:w2u1 (round 1)" in names and names["code-reviewer:s1 (round 1)"]["ran"] is True
    record = rr.build_record(account, Fake().readers())
    assert record["sliceRecoveries"] == account["sliceRecoveries"]
    text = rr.render(record)
    assert ("Recovered by an unread-part wave: code-reviewer:s2 (round 1) forfeited in wave 1; "
            "wave 2 re-ran its slice (code-reviewer:w2u1) on aaaaaaa.") in text
    assert S2 not in [m for m in record.get("missingReviews", [])]


def test_a_recovery_with_no_recorded_head_reads_an_unrecorded_commit_and_the_part_is_absent_when_the_state_has_none(tmp_path):
    line = rr._recovery_line([{"seat": S2, "round": 1, "wave": 1, "recoveredInWave": 3, "recoveredBy": ["a", "b"], "commit": None},
                              {"seat": "test-role:s1", "round": 1, "wave": 1, "recoveredInWave": 2, "recoveredBy": ["c"], "commit": "b" * 40}])
    assert line == ("Recovered by an unread-part wave: code-reviewer:s2 (round 1) forfeited in wave 1; wave 3 re-ran its slice (a, b) on "
                    "an unrecorded commit; Recovered by an unread-part wave: test-role:s1 (round 1) forfeited in wave 1; "
                    "wave 2 re-ran its slice (c) on bbbbbbb.")
    assert rr._recovery_line(None) is None
    session = Session(tmp_path, rounds={"1": {"seatStatus": {"code-reviewer": "run"}}}).save()
    assert "sliceRecoveries" not in rs.account_from_session(session, extras(), Fake().readers())


@pytest.mark.parametrize("bad", [
    [{"seat": S2, "round": 1, "wave": 2, "recoveredInWave": 2, "recoveredBy": ["code-reviewer:w2u1"]}],
    [{"seat": S2, "round": 1, "wave": 1, "recoveredInWave": 2, "recoveredBy": []}],
    [{"seat": "architecture-reviewer", "round": 1, "wave": 1, "recoveredInWave": 2, "recoveredBy": ["x"]}],
    [{"seat": S2, "round": 0, "wave": 1, "recoveredInWave": 2, "recoveredBy": ["x"]}],
    [{"seat": S2, "round": 1, "wave": 1, "recoveredInWave": 2, "recoveredBy": [" "]}],
    [{"seat": S2, "round": 1, "wave": 1, "recoveredInWave": 2, "recoveredBy": ["x"], "extra": 1}],
    [], "recovered", {"seat": S2}, [None]], ids=["not-later", "nobody", "whole-change", "round-zero", "blank-reader", "extra-key",
                                                  "empty-list", "string", "dict", "none-item"])
def test_a_malformed_slice_recovery_part_is_refused_by_the_records_account_check(tmp_path, bad):
    path, state = _recovered_session(tmp_path, journaled=False)
    session = Session(tmp_path / "bad", rounds=state["rounds"], sliceRecoveries=bad).save()
    account = rs.account_from_session(session, extras(), Fake().readers())
    with pytest.raises(rr.Refusal) as err:
        rr.build_record(account, Fake().readers())
    assert err.value.args[0] == "review-account-invalid" and err.value.args[1].startswith("sliceRecoveries")
