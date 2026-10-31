"""#1858 (review C5 L5) WO-A — the three L4 folds.

v0: a session saved by the generation before the per-seat verdict binding is never continued.
v4: `run_loop` authenticates a seams-check / scoped result against the selection captured before the
    callback ran, not the preference as it stands afterwards.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_a_1858_l4_folds.md
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import round_driver as RD  # noqa: E402
import test_round_driver as TRD  # noqa: E402
from test_session_pickup_and_upgrade_1721 import (  # noqa: E402
    MARKER, TOKEN, _assert_refusal, _light_folder, _marker_path, _read_state_file,
)

PRE_BINDING_GENERATION = 3  # the literal integer the pre-binding driver stamped, not derived


# --- v0: a generation-3 unfinished session restarts ---------------------------------------------

def test_v0_next_on_a_generation_three_unfinished_session_refuses_and_writes_the_marker(tmp_path):
    # axis: a generation-3 unfinished session is refused at `next` with the restart marker (P-v0)
    session_dir = _light_folder(tmp_path, generation=PRE_BINDING_GENERATION)
    assert _read_state_file(session_dir)["sessionGeneration"] == 3
    assert not os.path.exists(_marker_path(session_dir))
    out = RD.cmd_next(session_dir)
    _assert_refusal(out, already_restarted=False)
    assert out["reason"] == "session-from-earlier-version" == TOKEN
    assert MARKER == "restarted-on-upgrade.json"
    assert os.path.exists(os.path.join(session_dir, MARKER))


def test_v0_submit_on_a_generation_three_unfinished_session_refuses(tmp_path):
    # axis: a second command (`submit`) on a generation-3 unfinished session is refused too (P-v0)
    session_dir = _light_folder(tmp_path, generation=PRE_BINDING_GENERATION)
    out = RD.cmd_submit(session_dir, RD.P_PANEL, 1, "x", {})
    _assert_refusal(out, already_restarted=False)
    assert os.path.exists(os.path.join(session_dir, MARKER))


def test_v0_e2_a_current_generation_unfinished_session_is_not_refused(tmp_path):
    # positive control (e2): the current generation passes the gate
    session_dir = _light_folder(tmp_path, generation=RD.SESSION_GENERATION)
    out = RD.cmd_next(session_dir)
    assert out.get("reason") != "session-from-earlier-version", out
    assert not os.path.exists(_marker_path(session_dir))


# --- v4: the finder is judged against the selection captured before the callback ------------------

def _flip_engine(monkeypatch, to_vendor):
    """Make `_reviewer_engine_vendor` answer `to_vendor` from now on (a preference edit mid-callback)."""
    # `run_loop` runs on test_round_driver's own load of the module (`TRD.RD`), not this file's import
    for module in (RD, TRD.RD):
        monkeypatch.setattr(module, "_reviewer_engine_vendor",
                            lambda repo_root: (to_vendor, RD.VENDOR_SOURCE_CONFIGURED))


VENDORS = ["claude", "codex", "cursor"]  # cursor is live, so the edit below really moves the selection


def _seams_run(monkeypatch, reported_vendor, edit_to="cursor"):
    """run_loop over a sliced change so a seams check runs; the callback edits the preference, then reports."""
    seen = {"seams": 0}
    _flip_engine(monkeypatch, "codex")  # the engine as it stands before the callback: selection is codex
    monkeypatch.setattr(TRD.RD, "_round_is_sliced", lambda state: True)

    def reviewer(dim, tier, rnd, ctx):
        if dim == "seams-check":
            seen["seams"] += 1
            if seen["seams"] == 1:
                _flip_engine(monkeypatch, edit_to)
            return dict(findings=[], vendor=reported_vendor)
        return []

    seams = TRD._seams(vendors=VENDORS)
    seams["reviewer"] = reviewer
    _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert(diff=TRD._big_diff(25), vendors=VENDORS))
    return state, seen


def _scoped_run(monkeypatch, reported_vendor, edit_to="cursor"):
    seen = {"scoped": 0}
    _flip_engine(monkeypatch, "codex")

    def reviewer(dim, tier, rnd, ctx):
        if dim == "scoped-finder":
            seen["scoped"] += 1
            if seen["scoped"] == 1:
                _flip_engine(monkeypatch, edit_to)
            return dict(findings=[], vendor=reported_vendor)
        if rnd == 1 and dim == "code-reviewer":
            return dict(findings=[dict(title="bug", severity="Important", file="f.py", line=1,
                                       consequence="a reviewer-found defect stays in the change")])
        return []

    def fix_step(batch, rnd, payload):
        return dict(fixes=[], headDiff=TRD.HEAD_NEW_SURFACE, changedSubjects=["Code"])

    _result, state = TRD._run_loop_capturing_state(
        TRD._seams(reviewer=reviewer, fix_step=fix_step, vendors=VENDORS), TRD._cfg_cert(vendors=VENDORS))
    return state, seen


def _parked_unauthenticated(state, phase):
    reason = str((state.get("certification") or {}).get("reason"))
    return (state.get("terminal") == "cannot-certify"
            and reason.startswith("nonpanel-finder-unauthenticated:%s" % phase)), reason


RUNS = [pytest.param(_seams_run, RD.P_SEAMS, "seams", id="seams-check"),
        pytest.param(_scoped_run, RD.P_SCOPED, "scoped", id="scoped")]


@pytest.mark.parametrize("run,phase,key", RUNS)
def test_v4_a_preference_edit_while_the_callback_runs_does_not_re_judge_the_result(
        monkeypatch, run, phase, key):
    # axis: the finder is authenticated against the selection captured before the callback (P-v4)
    # the pre-callback selection is codex; the edit made while the callback ran makes it cursor
    # (a live re-read would judge the codex report against cursor and park)
    state, seen = run(monkeypatch, "codex")
    parked, reason = _parked_unauthenticated(state, phase)
    assert seen[key] >= 1
    assert not parked, reason


@pytest.mark.parametrize("run,phase,key", RUNS)
def test_v4_a_vendor_other_than_the_captured_selection_still_parks(monkeypatch, run, phase, key):
    # the pair: reporting the post-edit selection (not the captured one) is still unauthenticated
    state, seen = run(monkeypatch, "cursor")
    parked, reason = _parked_unauthenticated(state, phase)
    assert parked, (state.get("terminal"), reason)
    assert "expected=codex:reported=cursor" in reason, reason
    assert seen[key] == 1


# fail-closed edges of the helper itself, with the selection passed in (a live read would differ)

def _state(makers=()):
    seat_map = {"hostFamily": "anthropic", **TRD._nonpanel_cell_proof(["claude", "codex", "cursor"])}
    if makers:
        seat_map["makerFamilies"] = list(makers)
    return RD.new_state({"repoRoot": "/nonexistent-review-project", "vendors": ["claude", "codex", "cursor"],
                         "fixerVendor": "claude", "seatMap": seat_map})


def test_v4_e4_a_captured_selection_of_none_is_unauthenticated():
    state = _state()
    assert RD._nonpanel_selection(state, None, RD.P_SEAMS)[0] == "codex"  # the live read would authenticate
    assert RD._library_finder_unauthenticated(state, "codex", RD.P_SEAMS, selected=None, replaced=False) is True


def test_v4_e5_no_report_with_the_captured_selection_replaced_is_unauthenticated():
    state = _state()
    assert RD._library_finder_unauthenticated(state, None, RD.P_SEAMS, selected="claude", replaced=True) is True


def test_v4_e6_no_report_with_the_captured_selection_being_the_engine_is_authenticated():
    state = _state()
    assert RD._nonpanel_replaced(state, "codex")  # the live read would say replaced
    assert RD._library_finder_unauthenticated(state, None, RD.P_SEAMS, selected="codex", replaced=False) is False


def test_v4_e7_a_reported_vendor_equal_to_the_captured_selection_but_barred_is_unauthenticated():
    state = _state(makers=["openai"])
    assert RD._library_finder_unauthenticated(state, "codex", RD.P_SEAMS, selected="codex", replaced=True) is True
