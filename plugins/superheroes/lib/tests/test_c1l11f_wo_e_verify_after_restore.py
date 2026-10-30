"""The verify gate after a restore, and the same-anchor merge's `testCorrection` carry (vet 734, issue #2279).

E1: when the retry of a pending verify re-run ran at another head after a restore, the review record still holds
both runs (decision `head-moved`, with the two heads) before the gate halts. E2: a pass whose head is unknown on
both sides never advances after a restore. E3: a same-anchor merge that an ordinary finding wins keeps the
carrier's `testCorrection`.

Edges: (E1) the retry at the restored head with HEAD moved during it records `head-moved` and halts on the
existing path; the retry at another head with `moved` false records `head-moved` and halts on the restore gate;
a first failure at a non-restored head halts on the first run with no rerun entry; `_verifyRerun` is popped
exactly once, so a halt leaves none. (E2) an unknown head with a `fail` result goes the rerun path first and
halts on the second fail; an unknown head with a skip result and no verify command keeps today's advance (the
finding is about a pass); a known head equal to the restored head advances.

Bite-proof record: c1l11f_wo_e_verify_after_restore
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import test_round_driver_advance as TA  # noqa: E402
from test_verify_rerun_ufr3 import H1, H2, _artifact, _entries, _kinds, _state  # noqa: E402

RD = TA.RD
H3 = "3" * 40


def _fold(state, artifact, fold_head=None):
    """`run_loop`'s in-process leg forwards no head: an artifact with no run head and an errored resolution."""
    resolution = (fold_head, None) if fold_head else (None, "error")
    RD._fold_verify(state, state["config"], artifact, resolution=resolution)
    return state


def _restored_state(restored=H1, **cfg_over):
    state = _state(**cfg_over)
    state["_restoredHead"] = restored
    return state


# =============================================================================================
# E1: a head-moved retry after a restore records both runs before the halt
# =============================================================================================

def test_e1_a_retry_at_another_head_after_a_restore_records_both_runs_then_halts():
    # axis: the rerun entry with both runs is recorded before the restore gate's halt — see bite-proof record c1l11f_wo_e_verify_after_restore
    state = _restored_state()
    _fold(state, _artifact("fail", head=H1))
    assert "_verifyRerun" in state and not state.get("terminal")
    _fold(state, _artifact("pass", head=H2))

    assert state["terminal"] == "halted" and state["step"] == RD.P_TERMINAL
    assert _kinds(state)[-1] == "verify-unresolved"
    (entry,) = _entries(state)
    assert entry["check"] == "verify" and entry["decision"] == "head-moved"
    assert entry["heads"] == [H1, H2]
    first, second = entry["runs"]
    assert first["head"] == H1 and second["head"] == H2
    assert first["exitCode"] == 1 and second["exitCode"] == 0
    assert "_verifyRerun" not in state


def test_e1_a_retry_that_moved_head_while_running_records_where_it_started_and_ended():
    state = _restored_state()
    _fold(state, _artifact("fail", head=H1))
    _fold(state, _artifact("pass", head=H2, after=H3))

    assert state["terminal"] == "halted"
    (entry,) = _entries(state)
    assert entry["decision"] == "head-moved" and entry["heads"] == [H2, H3]
    assert "_verifyRerun" not in state


def test_e1_a_retry_at_the_restored_head_that_moved_during_the_run_halts_on_the_rerun_path():
    state = _restored_state()
    _fold(state, _artifact("fail", head=H1))
    _fold(state, _artifact("pass", head=H1, after=H2))

    assert state["terminal"] == "halted" and "_verifyRerun" not in state
    assert _kinds(state)[-1] == "verify-rerun-head-moved"
    (entry,) = _entries(state)
    assert entry["decision"] == "head-moved" and entry["heads"] == [H1, H2]


def test_e1_a_first_failure_at_another_head_halts_on_the_first_run_with_no_rerun_entry():
    state = _restored_state()
    _fold(state, _artifact("fail", head=H2))

    assert state["terminal"] == "halted" and state["step"] == RD.P_TERMINAL
    assert _kinds(state)[-1] == "verify-unresolved"
    assert "_verifyRerun" not in state and _entries(state) == []


def test_e1_a_retry_at_the_restored_head_that_passes_still_advances_and_records_went_on():
    state = _restored_state()
    _fold(state, _artifact("fail", head=H1))
    _fold(state, _artifact("pass", head=H1))

    assert not state.get("terminal") and "_restoredHead" not in state and "_verifyRerun" not in state
    (entry,) = _entries(state)
    assert entry["decision"] == "went-on"


# =============================================================================================
# E2: a pass whose head is unknown on both sides halts after a restore
# =============================================================================================

def test_e2_a_pass_with_no_known_head_after_a_restore_halts_and_does_not_advance():
    # axis: the gate after a restore halts on a pass whose head is unknown on both sides — see bite-proof record c1l11f_wo_e_verify_after_restore
    state = _restored_state()
    _fold(state, _artifact("pass", head=None))

    assert state["terminal"] == "halted" and state["step"] == RD.P_TERMINAL
    assert state["certification"]["shape"] is None and "unknown" in state["certification"]["reason"]
    decision = state["decisions"][-1]
    assert decision["kind"] == "verify-unresolved" and "unknown" in decision["detail"]
    assert "verifyVia" not in state["rounds"]["1"]


def test_e2_a_pass_at_a_known_matching_head_after_a_restore_still_advances():
    state = _restored_state()
    _fold(state, _artifact("pass", head=H1))

    assert not state.get("terminal") and "_restoredHead" not in state


def test_e2_a_pass_whose_head_is_known_only_at_the_fold_and_matches_still_advances():
    state = _restored_state()
    _fold(state, _artifact("pass", head=None), fold_head=H1)

    assert not state.get("terminal") and "_restoredHead" not in state


def test_e2_without_a_restore_a_pass_with_no_known_head_behaves_as_today():
    state = _state()
    _fold(state, _artifact("pass", head=None))

    assert not state.get("terminal")


def test_e2_a_fail_with_no_known_head_after_a_restore_goes_the_rerun_path_and_halts_on_the_second_fail():
    state = _restored_state()
    _fold(state, _artifact("fail", head=None))
    assert "_verifyRerun" in state and not state.get("terminal")
    _fold(state, _artifact("fail", head=None))

    assert state["terminal"] == "halted" and _kinds(state)[-1] == "verify-fail"
    assert "_verifyRerun" not in state


def test_e2_a_retry_pass_with_no_known_head_after_a_restore_records_both_runs_then_halts():
    state = _restored_state()
    _fold(state, _artifact("fail", head=None))
    _fold(state, _artifact("pass", head=None))

    assert state["terminal"] == "halted" and _kinds(state)[-1] == "verify-unresolved"
    assert "_verifyRerun" not in state
    (entry,) = _entries(state)
    assert len(entry["runs"]) == 2
    # axis: the rejected retry is recorded as non-advancing, so the record never calls it a re-run on unchanged code — see bite-proof record c1l11f_wo_e_verify_after_restore
    assert entry["decision"] == "failed"


def test_e2_a_skip_with_no_verify_command_and_no_known_head_after_a_restore_keeps_todays_advance():
    state = _restored_state(verifyCommand=None)
    _fold(state, {"result": "skipped"})

    assert not state.get("terminal") and "_restoredHead" not in state


# =============================================================================================
# the in-process verify seam may report its head
# =============================================================================================

def _seam_artifact(returned):
    state = _state()
    seams = {"verify_runner": lambda command, rnd: returned}
    return RD._run_seam(seams, RD.P_VERIFY, {"command": "make test"}, state, state["config"])


def test_seam_a_dict_return_gives_its_result_and_a_non_empty_string_head():
    # axis: the in-process verify seam may report the head the run ran at, a non-empty string only — see bite-proof record c1l11f_wo_e_verify_after_restore
    assert _seam_artifact({"result": "pass", "headSha": H1, "extra": "x"}) == {"result": "pass", "headSha": H1}


def test_seam_a_bare_string_return_stays_result_only():
    assert _seam_artifact("pass") == {"result": "pass"}


def test_seam_a_head_that_is_not_a_non_empty_string_is_ignored():
    for bad in ("", None, 7, ["a"]):
        assert _seam_artifact({"result": "pass", "headSha": bad}) == {"result": "pass"}


def test_seam_a_dict_with_no_result_has_no_result_and_fails_closed_as_unresolved():
    artifact = _seam_artifact({"headSha": H1})
    assert artifact.get("result") is None
    state = _state()
    _fold(state, artifact)
    assert state["terminal"] == "halted" and _kinds(state)[-1] == "verify-unresolved"


# =============================================================================================
# E3: a same-anchor merge carries `testCorrection`
# =============================================================================================

def test_e3_a_same_anchor_merge_an_ordinary_finding_wins_keeps_the_carriers_test_correction():
    # axis: an attached test, its stamp and its runs survive a same-anchor merge the other finding wins — see bite-proof record c1l11f_wo_e_verify_after_restore
    correction = {"round": 2, "used": True, "outcome": "corrected"}
    carrier = {"file": "f.py", "line": 1, "title": "t", "severity": "Nit", "taxonomy": "break-it-test",
               RD.break_it.RUN_FIELD: {"outcome": "failed"}, RD.TEST_CORRECTION_FIELD: correction}
    plain = {"file": "f.py", "line": 1, "title": "t", "severity": "Critical"}
    for existing, incoming in ((carrier, plain), (plain, carrier)):
        merged = RD._merge_same_finding(existing, incoming)
        assert merged["severity"] == "Critical"
        assert merged[RD.TEST_CORRECTION_FIELD] == correction
