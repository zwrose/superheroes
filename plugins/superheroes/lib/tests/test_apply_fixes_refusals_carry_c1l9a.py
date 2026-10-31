"""WO-9 (C1-L9a, #2213): an apply-fixes continuation keeps the refusals an earlier slice's record holds.

An older session can resume between fix-batch slices with `rounds[N].fix.refusals` already stored (written
by the retired fixer before the upgrade). The continuation merges the earlier `fixes`, `unfixed` and
`commits` and carries every other key of the earlier record unchanged, so `review_record_session` still
reads those refusals. A first slice carries nothing from any earlier record.

E1 an earlier `fix` that is no dict (missing, None, a list) carries nothing and raises nothing.
E2 an earlier `refusals` at slice index 0 is not carried.
E3 an earlier `fix` with no `refusals` leaves the new record without that key.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record_session as rs  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD

REFUSAL = {"command": "rm -rf build", "reason": "denied"}
_MISSING = object()


def _state(index, earlier=_MISSING):
    """A hand-built state in round 1 at slice `index`; `earlier` is the stored `rounds["1"]["fix"]`."""
    state = RD.new_state(TRD._cfg())
    state["round"] = 1
    state["_fixBatchIndex"] = index
    if earlier is not _MISSING:
        state["rounds"]["1"] = {"fix": earlier}
    return state


def _fold(state, artifact=None, fix_commits=None):
    RD._fold_apply_fixes(state, {}, artifact if artifact is not None else {"fixes": []},
                         changed_subjects_seam=lambda *args: [], session_dir=None, fix_commits=fix_commits)


def _earlier(**over):
    out = {"fixes": ["an earlier note"], "commits": [], "refusals": [dict(REFUSAL)]}
    out.update(over)
    return out


def test_a_continuation_keeps_the_earlier_refusals():
    state = _state(1, _earlier())
    _fold(state)
    assert state["rounds"]["1"]["fix"]["refusals"] == [REFUSAL]
    assert rs._command_refusals(state["rounds"]) == [dict(REFUSAL, round=1)]


def test_a_continuation_keeps_the_refusals_in_order():
    other = {"command": "git clean -fdx", "reason": "denied"}
    state = _state(1, _earlier(refusals=[dict(REFUSAL), dict(other)]))
    _fold(state)
    assert state["rounds"]["1"]["fix"]["refusals"] == [REFUSAL, other]


def test_a_first_slice_carries_nothing():  # E2
    state = _state(0, _earlier())
    _fold(state)
    assert "refusals" not in state["rounds"]["1"]["fix"]


def test_a_continuation_with_no_earlier_refusals_adds_none():  # E3
    earlier = _earlier()
    del earlier["refusals"]
    state = _state(1, earlier)
    _fold(state)
    assert "refusals" not in state["rounds"]["1"]["fix"]


@pytest.mark.parametrize("earlier", [_MISSING, None, [], [REFUSAL], "x"])
def test_an_earlier_fix_that_is_no_dict_carries_nothing(earlier):  # E1
    state = _state(1, earlier)
    _fold(state, {"fixes": ["a note"]}, fix_commits=["c1"])
    assert state["rounds"]["1"]["fix"] == {"fixes": ["a note"], "commits": ["c1"]}


def test_a_continuation_still_merges_fixes_commits_and_unfixed():
    unfixed_old = {"finding": "A", "reason": "old"}
    unfixed_new = {"finding": "B", "reason": "new"}
    state = _state(1, _earlier(fixes=["old note"], commits=["c1"], unfixed=[unfixed_old]))
    _fold(state, {"fixes": ["new note"], "unfixed": [unfixed_new]}, fix_commits=["c2"])
    fix = state["rounds"]["1"]["fix"]
    assert fix["fixes"] == ["old note", "new note"]
    assert fix["commits"] == ["c1", "c2"]
    assert fix["unfixed"] == [unfixed_old, unfixed_new]
    assert fix["refusals"] == [REFUSAL]
