"""#2343: a finding counts as carried, for every outcome a carried check can move (left-for-owner, undecided,
shown-wrong), only when the earlier record of another session lists it; never on this session's own earlier record.

Edges: E-a no earlier record · E-b the earlier record is this session's own and nothing else is listed · E-c the
other-session record's `findings` is not a list · E-d the other-session record lists a different key only · E-e an
earlier record with no `sessionId` is another session's · E-f the latest record is unreadable and an older readable
record of another session lists it.
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import review_record as rr  # noqa: E402

from test_review_record_carried_recheck import FIX, X, X_KEY, account, entry, readers  # noqa: E402
from test_review_record_session import HEAD, Fake  # noqa: E402

PROOF = "plugins/superheroes/lib/tests/bite_proofs/i2343_never_carried.md"
KEPT = "not carried from an earlier record"
L = dict(X)
U = dict(X, outcome=None, reason="still open")
UNRELATED = dict(X, id="f-9", title="Another finding", line=3)
CASES = [pytest.param(L, id="left-for-owner"), pytest.param(U, id="undecided")]


def record(session, finding):
    """An earlier record of ``session`` that lists ``finding`` under its stored key."""
    return {"sessionId": session, "findings": [dict(finding, findingKey=rr._key(finding))]}


def build_f(finding, prior, history=(), calls=None):
    return rr.build_record(account([entry()], [finding]), readers(calls=calls), prior=prior, history=history)


def the_one(rec):
    (f,) = rec["findings"]
    return f


def assert_kept(rec, finding, calls):
    f = the_one(rec)
    assert f["outcome"] == finding["outcome"]
    assert KEPT in f["reason"] and "fixed after" not in f["reason"]
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["why"]) == ("kept", KEPT)
    assert calls == []
    if finding["outcome"] == "left-for-owner":
        assert rec["leftForOwner"] == [finding["id"]]


def assert_moved(rec):
    f = the_one(rec)
    assert f["outcome"] == "fixed"
    assert [r["result"] for r in rec["carriedRechecks"]] == ["fixed"]


# --- unit: the membership test in _recheck_carried ---

@pytest.mark.parametrize("finding", CASES)
def test_t1_a_same_session_rewrite_with_nothing_carried_keeps_the_finding(finding):
    # axis: a finding only this session's own earlier record lists is not carried, for left-for-owner and undecided
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2343_never_carried.md
    calls = []
    rec = build_f(finding, record("s-1", finding), history=[], calls=calls)
    assert_kept(rec, finding, calls)


@pytest.mark.parametrize("finding", CASES)
def test_t2_a_same_session_rewrite_whose_other_session_record_omits_the_finding_keeps_it(finding):
    # axis: the other session's record lists a different key only, so a finding only this session's own record lists is not carried
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2343_never_carried.md
    assert rr._key(UNRELATED) != X_KEY
    calls = []
    rec = build_f(finding, record("s-1", finding), history=[record("s-0", UNRELATED)], calls=calls)
    assert_kept(rec, finding, calls)


@pytest.mark.parametrize("finding", CASES)
def test_t3_a_same_session_rewrite_with_no_readable_other_record_keeps_the_finding(finding):
    # axis: an other-session record whose findings are not a list carries nothing
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2343_never_carried.md
    calls = []
    rec = build_f(finding, record("s-1", finding), history=[{"sessionId": "s-0", "findings": "none"}], calls=calls)
    assert_kept(rec, finding, calls)


@pytest.mark.parametrize("finding", CASES)
def test_e_a_no_earlier_record_at_all_keeps_the_finding(finding):
    # axis: with no earlier record nothing is carried
    calls = []
    rec = build_f(finding, None, history=[], calls=calls)
    assert_kept(rec, finding, calls)


@pytest.mark.parametrize("finding", CASES)
@pytest.mark.parametrize("prior", [
    pytest.param("s-0", id="another-session"),
    pytest.param(None, id="no-session-id"),
])
def test_t4_a_first_write_over_another_sessions_record_moves_the_finding(finding, prior):
    # axis: a finding the earlier record of another session lists is still carried, so a fixed check moves it
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2343_never_carried.md
    earlier = record(prior, finding) if prior else {"findings": [dict(finding, findingKey=rr._key(finding))]}
    calls = []
    rec = build_f(finding, earlier, calls=calls)
    assert_moved(rec)
    assert calls == [(None, FIX, HEAD)]


@pytest.mark.parametrize("finding", CASES)
def test_t5_a_same_session_rewrite_whose_other_session_record_lists_it_moves_the_finding(finding):
    # axis: a finding the earlier record of another session lists is carried even when this session also rewrites its own record
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2343_never_carried.md
    rec = build_f(finding, record("s-1", finding), history=[record("s-0", finding)])
    assert_moved(rec)


# --- through the writer: the history of readable records survives an unreadable latest one ---

def _wired(fake, calls=None):
    rd = readers(calls=calls)
    shared = fake.readers()
    rd["list_comments"], rd["create_comment"] = shared["list_comments"], shared["create_comment"]
    return rd


def _write(tmp_path, rd, acct):
    path = tmp_path / "account.json"
    path.write_text(json.dumps(acct))
    return rr.write(str(path), str(tmp_path), rd)


@pytest.mark.parametrize("finding", CASES)
def test_t6_an_unreadable_latest_record_leaves_the_older_other_session_record_to_carry_the_finding(tmp_path, finding):
    # axis: the latest record unreadable, the newest readable record of another session carries the finding and the unreadable one is listed
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2343_never_carried.md
    fake, calls = Fake(), []
    rd = _wired(fake, calls)
    assert _write(tmp_path, rd, account([], [finding], session="s-0"))["ok"]
    bad = len(fake.comments) + 1
    fake.comments.append({"id": bad, "author": "a", "body": rr.MARKER + "\nhand edited", "url": "u-bad"})
    assert _write(tmp_path, rd, account([entry()], [finding], session="s-1"))["ok"]
    rec = rr.read(7, readers=rd)
    assert the_one(rec)["outcome"] == "fixed" and [r["result"] for r in rec["carriedRechecks"]] == ["fixed"]
    assert rec["earlierRecordsNotChecked"] == [{"id": bad, "url": "u-bad", "why": "unreadable"}]
    assert calls == [(str(tmp_path), FIX, HEAD)]


def test_t7_two_writes_by_one_session_never_move_the_finding_the_first_listed(tmp_path):
    # axis: the original direct-write sequence, both writes by the same session, ends with the finding kept for the owner
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2343_never_carried.md
    fake, calls = Fake(), []
    rd = _wired(fake, calls)
    assert _write(tmp_path, rd, account([]))["ok"]
    assert rr.read(7, readers=rd)["findings"][0]["outcome"] == "left-for-owner"
    assert _write(tmp_path, rd, account([entry()]))["ok"]
    rec = rr.read(7, readers=rd)
    assert the_one(rec)["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"]
    assert [(r["result"], r["why"]) for r in rec["carriedRechecks"]] == [("kept", KEPT)]
    assert calls == []
