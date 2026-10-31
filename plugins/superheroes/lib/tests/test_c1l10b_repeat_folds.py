"""The vet-728 fold of C1-L10b: pins for the repeat chain closure, the repeat mark a newer disposition clears, a second
synthesis wave's marks, and the decision table's unknown change.

Edges: E1 `repeat_marks.decide` with `changed` None, a callable returning None, False and True · E2 a round whose
synthesis marks nothing writes no `repeatMarks` key · E3 `_wrong_ungraded` over a ring of repeats, a link to a key no
finding holds, and a finding that names its own key.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c1l10b_wo1_repeat_folds.md
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import repeat_marks  # noqa: E402
import test_repeat_marks_c1l8 as TRM  # noqa: E402
from test_review_record import Fake, closed, finding, wrong  # noqa: E402
from test_review_record_repeats_c1l8 import mark, write  # noqa: E402

RD = TRM.RD


def chained(fid, title, earlier):
    """A kept shown-wrong repeat of `earlier`: no wrong grade of its own."""
    return finding(fid, title=title, outcome="shown-wrong", reason="repeat; keeps its earlier outcome (shown-wrong)",
                   repeatOf=mark(rr._key(earlier), id=earlier["id"]))


def chain():
    a = wrong("a-1", title="one", reason="not a bug")
    b = chained("a-2", "two", a)
    c = chained("a-3", "three", b)
    return a, b, c


# --- item 2: the chain closure of `_wrong_ungraded` ----------------------------------------------------------------------

def test_2a_a_chain_of_kept_repeats_passes_link_by_link_to_a_verifier_closed_root():
    a, b, c = chain()
    assert rr._wrong_ungraded([a, b, c], None, closed(a)) == []


def test_2a_reverse_a_chain_listed_child_first_still_passes_link_by_link_to_the_root():
    # axis: the chain closure repeats until nothing changes — a single forward pass admits only the links listed after their parent
    a, b, c = chain()
    assert rr._wrong_ungraded([c, b, a], None, closed(a)) == []


def test_2b_a_ring_of_kept_repeats_gains_no_root_and_is_refused():
    a = wrong("a-1", title="one", reason="not a bug")
    b = finding("a-2", title="two", outcome="shown-wrong", reason="r")
    c = finding("a-3", title="three", outcome="shown-wrong", reason="r")
    b, c = dict(b, repeatOf=mark(rr._key(c))), dict(c, repeatOf=mark(rr._key(b)))
    assert rr._wrong_ungraded([a, b, c], None, closed(a)) == [1, 2]


def test_2c_a_link_to_a_key_no_finding_holds_is_refused_and_so_is_every_repeat_behind_it():
    a, b, _ = chain()
    dangling = finding("a-3", title="three", outcome="shown-wrong", reason="r", repeatOf=mark("rr1:" + "0" * 32))
    assert rr._wrong_ungraded([a, b, dangling], None, closed(a)) == [2]
    behind = chained("a-4", "four", dangling)
    assert rr._wrong_ungraded([a, b, dangling, behind], None, closed(a)) == [2, 3]
    # the earlier record does not list the key either: it is not carried
    prior = {"findings": [dict(a, outcome="shown-wrong")]}
    assert rr._wrong_ungraded([b, dangling], prior, frozenset()) == [1]


def test_3e_a_repeat_naming_its_own_key_stays_refused():
    a = wrong("a-1", title="one", reason="not a bug")
    own = finding("a-2", title="two", outcome="shown-wrong", reason="r")
    own = dict(own, repeatOf=mark(rr._key(own)))
    assert rr._wrong_ungraded([a, own], None, closed(a)) == [1]


def test_2d_the_writer_takes_the_whole_chain_of_kept_repeats(tmp_path):
    a, b, c = chain()
    fake = Fake()
    out = write(tmp_path, fake, [a, b, c], verifier_closed=closed(a))
    assert out["ok"], out
    rows = {f["id"]: f for f in rr.read(7, readers=fake.readers())["findings"]}
    assert [rows[i]["outcome"] for i in ("a-1", "a-2", "a-3")] == ["shown-wrong"] * 3
    assert rows["a-3"]["repeatOf"]["findingKey"] == rr._key(b)


def test_2d_reverse_the_writer_takes_the_whole_chain_listed_child_first(tmp_path):
    a, b, c = chain()
    fake = Fake()
    out = write(tmp_path, fake, [c, b, a], verifier_closed=closed(a))
    assert out["ok"], out
    rows = {f["id"]: f for f in rr.read(7, readers=fake.readers())["findings"]}
    assert [rows[i]["outcome"] for i in ("a-1", "a-2", "a-3")] == ["shown-wrong"] * 3
    assert rows["a-3"]["repeatOf"]["findingKey"] == rr._key(b)


# --- item 3: a newer disposition clears `repeatKept` ---------------------------------------------------------------------

def _rule_out_of_scope(tmp_path, state, key):
    """Rule `key` out of scope with the owner's attribution, through the driver's `rule` verb on a saved session."""
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    RD.save_state(session_dir, state)
    path = str(tmp_path / "rulings.json")
    entry = {"id": key, "ruling": "out-of-scope", "reason": "belongs to the next milestone",
             "followUp": {"item": "backlog item", "revisitTrigger": "next milestone", "classClosure": "owner backlog"}}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"_provenance": {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z", "records": ["rulings.json"]},
                   "rulings": [entry]}, fh)
    out = RD.cmd_rule(session_dir, path, "owner")
    assert out.get("ok"), out
    ok, loaded = RD.load_state(session_dir)
    assert ok, loaded
    return loaded


def _kept_left_for_owner_through_the_fold():
    state = TRM._state()
    owner = TRM._raw("owner call", line=2, tradeoff=True)
    TRM._earlier(state, owner, "left-for-owner", settledReason="only the owner can settle this")
    state["round"] = 2
    fresh = TRM._raw("fresh plain", line=4)  # a fresh finding keeps the session open, so the rule verb takes the ruling
    TRM._verify(state, [owner, fresh], {"owner call": "CONFIRMED", "fresh plain": "CONFIRMED"})
    TRM._synth(state, None)
    row = TRM._row(state, owner)
    assert row["repeatKept"]["outcome"] == "left-for-owner" and not RD._live_finding_by_key(state, TRM._key(owner))
    return state, owner


def _kept_left_for_owner_on_a_live_finding():
    state = TRM._state()
    owner = TRM._raw("owner call", line=2, tradeoff=True)
    RD._stage_findings(state, TRM._compile([owner]))
    RD._set_findings(state, state["_toVerify"])
    key = TRM._key(owner)
    kept = {"outcome": "left-for-owner", "reason": "repeat of f-1; keeps its earlier outcome (left-for-owner)"}
    entry = {"outcome": "left-for-owner"}
    RD._record_kept_disposition(state, key, entry, kept["reason"], None, False)
    RD._record_repeat(state, key, {"findingKey": key, "id": None, "fixHolds": None}, kept)
    assert RD._live_finding_by_key(state, key)["repeatKept"] == kept, "premise: the live finding carries the mark"
    assert TRM._row(state, owner)["repeatKept"] == kept, "premise: the ledger row carries the mark"
    return state, owner


BUILDS = pytest.mark.parametrize("build", [_kept_left_for_owner_through_the_fold, _kept_left_for_owner_on_a_live_finding],
                                 ids=["ledger-row-only", "ledger-row-and-live-finding"])


def _ruled(tmp_path, build):
    state, owner = build()
    key = TRM._key(owner)
    loaded = _rule_out_of_scope(tmp_path, state, key)
    row = TRM._row(loaded, owner)
    assert row["disposition"] == "out-of-scope", "premise: the ruling is the newer disposition"
    return loaded, row, RD._live_finding_by_key(loaded, key)


@BUILDS
def test_3a_an_owner_ruling_after_a_kept_repeat_leaves_no_mark_on_the_row_or_the_live_finding(tmp_path, build):
    _, row, live = _ruled(tmp_path, build)
    assert "repeatKept" not in row and (live is None or "repeatKept" not in live), (row, live)


@BUILDS
def test_3b_the_record_reads_the_attributed_ruling_not_the_outcome_the_repeat_kept(tmp_path, build):
    loaded, row, _ = _ruled(tmp_path, build)
    # the reader matches a row by identity against the map `decision_inputs` builds, so read the map's own row
    inputs = rs.decision_inputs(loaded)
    own_row = inputs[0][TRM.SC.finding_identity_key(row)]
    outcome, _rep = rs.row_decision(own_row, inputs)
    assert outcome == "ruling", outcome


# --- item 4: a second synthesis wave appends to the round's repeat marks --------------------------------------------------

def test_4_a_second_synthesis_wave_of_one_round_keeps_the_first_waves_marks():
    state = TRM._state()
    first, second = TRM._raw("craft a", line=1), TRM._raw("ruled b", line=2)
    TRM._earlier(state, first, "craft", settledReason="cq")
    TRM._earlier(state, second, "ruling", settledReason="decided")
    state["round"] = 2
    TRM._verify(state, [first], {"craft a": "CONFIRMED"})
    TRM._synth(state, None)  # the panel's wave
    assert [m["repeatOf"]["findingKey"] for m in state["rounds"]["2"]["repeatMarks"]] == [TRM._key(first)]
    TRM._verify(state, [second], {"ruled b": "CONFIRMED"})
    TRM._synth(state, None)  # the gap sweep's wave
    marks = state["rounds"]["2"]["repeatMarks"]
    assert [m["repeatOf"]["findingKey"] for m in marks] == [TRM._key(first), TRM._key(second)], marks
    assert [m["kept"] for m in marks] == [True, True]


def test_4_edge2_a_round_whose_synthesis_marks_nothing_writes_no_repeat_marks_key():
    state = TRM._state()
    state["round"] = 1
    TRM._verify(state, [TRM._raw("fresh one")], {"fresh one": "CONFIRMED"})
    TRM._synth(state, None)
    assert "repeatMarks" not in state["rounds"]["1"]


# --- item 6: `decide` reads an unknown change as a change -----------------------------------------------------------------

@pytest.mark.parametrize("changed", [None, lambda: None], ids=["unknown", "callable-unknown"])
def test_6_an_unknown_change_keeps_a_shown_wrong_repeat_only_on_a_wrong_grade(changed):
    assert repeat_marks.decide("shown-wrong", "confirmed", changed) == (False, None)
    assert repeat_marks.decide("shown-wrong", "plausible", changed) == (False, None)
    assert repeat_marks.decide("shown-wrong", None, changed) == (False, None)
    assert repeat_marks.decide("shown-wrong", "wrong", changed) == (True, None)


@pytest.mark.parametrize("changed,grade,expected", [
    (False, "confirmed", (True, None)), (lambda: False, "confirmed", (True, None)),
    (True, "confirmed", (False, None)), (lambda: True, "confirmed", (False, None)),
    (True, "wrong", (True, None)), (False, "wrong", (True, None)),
])
def test_6_edge1_a_known_change_decides_as_before(changed, grade, expected):
    assert repeat_marks.decide("shown-wrong", grade, changed) == expected
