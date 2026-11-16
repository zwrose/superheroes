"""A hand-written account names its finding's raiser (issue 2515).

On a record written by `review_record.write` for a hand account, a finding the account gives no non-blank `raisedBy`
takes the name of the one reviewer row that ran, only when exactly one ran and no earlier record of the PR holds the
finding; a finding an earlier readable record holds takes that record's raiser, or stays without one; an unreadable
earlier record stops the derivation. The session writer's records are never touched.

Edges: E1 two or more reviewers ran · E2 none ran · E3 an earlier record holds the finding with no raiser ·
E4 an earlier record is unreadable · E5 the session writer's write.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import review_record as rr  # noqa: E402

import review_record_session as rs  # noqa: E402

from test_review_record import Fake, account, finding, put, reviewer  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)
from test_review_record_session import Fake as SessionFake, Session, extras, put_extras  # noqa: E402

SEC = "security-reviewer"
CODE = "code-reviewer"


def hand(tmp_path, fake, sid="s1", **over):
    out = rr.write(put(tmp_path, account(sessionId=sid, **over), name=f"{sid}-{len(fake.comments)}.json"),
                   str(tmp_path), fake.readers())
    assert out["ok"], out
    return out


def raisers(fake):
    rec = rr.read(7, readers=fake.readers())
    assert rec["ok"], rec
    return {f["id"]: f.get("raisedBy") for f in rec["findings"]}


def test_one_reviewer_ran_so_a_new_finding_without_a_raiser_names_it(tmp_path):
    # axis: a hand account's new finding with no raisedBy is credited to the one reviewer that ran
    fake = Fake()
    hand(tmp_path, fake, findings=[finding("f-1")])
    assert raisers(fake) == {"f-1": CODE}


def test_two_reviewers_ran_so_the_raiser_stays_unstated(tmp_path):
    # axis: E1, no guess between two reviewers that ran
    fake = Fake()
    hand(tmp_path, fake, reviewers=[reviewer(CODE), reviewer(SEC)], findings=[finding("f-1")])
    assert raisers(fake) == {"f-1": None}


def test_a_row_that_did_not_run_is_not_counted_and_none_ran_is_unstated(tmp_path):
    # axis: E2 and the not-run exclusion, a row that did not run neither makes two nor is the one
    # the writer demotes a row whose run record it cannot read to not-run, whatever the account says
    fake = Fake()
    fake.runs["/run/" + SEC] = (None, "no run record")
    hand(tmp_path, fake, reviewers=[reviewer(SEC), reviewer(CODE)], findings=[finding("f-1")])
    assert [v["ran"] for v in rr.read(7, readers=fake.readers())["reviewers"]] == ["not-run", "engine-record"]
    assert raisers(fake) == {"f-1": CODE}
    other = Fake()
    other.runs["/run/" + SEC] = other.runs["/run/" + CODE] = (None, "no run record")
    hand(tmp_path, other, reviewers=[reviewer(SEC), reviewer(CODE)], findings=[finding("f-1")])
    assert raisers(other) == {"f-1": None}


def test_an_account_that_names_its_raiser_keeps_it(tmp_path):
    # axis: an account's own non-blank raisedBy is kept as given
    fake = Fake()
    hand(tmp_path, fake, findings=[finding("f-1", raisedBy="premortem-reviewer")])
    assert raisers(fake) == {"f-1": "premortem-reviewer"}


def test_a_relist_keeps_the_earlier_raiser_and_never_credits_the_relister(tmp_path):
    # axis: a finding an earlier record holds takes that record's raiser, or none, never the reviewer that relisted it
    fake = Fake()
    hand(tmp_path, fake, sid="s1", reviewers=[reviewer(SEC)], findings=[finding("f-1", raisedBy=SEC)])
    hand(tmp_path, fake, sid="s2", reviewers=[reviewer(CODE)], findings=[finding("f-1")])
    assert raisers(fake) == {"f-1": SEC}
    other = Fake()  # E3: the earlier finding names no raiser (two reviewers ran in the first write)
    hand(tmp_path, other, sid="s1", reviewers=[reviewer(CODE), reviewer(SEC)], findings=[finding("f-1")])
    assert raisers(other) == {"f-1": None}
    hand(tmp_path, other, sid="s2", reviewers=[reviewer(CODE)], findings=[finding("f-1")])
    assert raisers(other) == {"f-1": None}


def test_one_write_with_a_relisted_and_a_new_finding_credits_each_its_own(tmp_path):
    # axis: the relisted finding keeps its earlier raiser while the new one in the same write takes the sole reviewer
    fake = Fake()
    hand(tmp_path, fake, sid="s1", reviewers=[reviewer(SEC)], findings=[finding("f-1", raisedBy=SEC)])
    hand(tmp_path, fake, sid="s2", reviewers=[reviewer(CODE)], findings=[finding("f-1"), finding("f-2", line=9)])
    assert raisers(fake) == {"f-1": SEC, "f-2": CODE}


def test_an_unreadable_earlier_record_stops_the_derivation_but_not_the_copy(tmp_path):
    # axis: E4, an unreadable earlier record might hold the finding, so a new finding gets no raiser
    fake = Fake()
    hand(tmp_path, fake, sid="s1", reviewers=[reviewer(SEC)], findings=[finding("f-1", raisedBy=SEC)])
    fake.comments.append({"id": len(fake.comments) + 1, "author": "a", "body": rr.MARKER + "\nhand edited", "url": "u-broken"})
    hand(tmp_path, fake, sid="s2", reviewers=[reviewer(CODE)], findings=[finding("f-1"), finding("f-2", line=9)])
    rec = rr.read(7, readers=fake.readers())
    assert rec["earlierRecordsNotChecked"][0]["why"] == "unreadable"
    assert raisers(fake) == {"f-1": SEC, "f-2": None}


def test_the_session_writers_write_derives_nothing(tmp_path):
    # axis: E5, the full-lane session writer's records are never touched, so absence stays absence
    fake = Fake()
    path = put(tmp_path, account(findings=[finding("f-1")]))
    assert rr.write(path, str(tmp_path), fake.readers(), from_session=True)["ok"]
    assert raisers(fake) == {"f-1": None}


def test_the_session_writer_hands_the_writer_the_session_flag(tmp_path, monkeypatch):
    # axis: E5 at the caller, `write_from_session` marks its write as the session's so no raiser is derived
    seen = {}
    real = rr.write

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)
    monkeypatch.setattr(rr, "write", spy)
    session = Session(tmp_path, terminal=None).save()
    out = rs.write_from_session(session, put_extras(tmp_path, extras(ci="green")), str(tmp_path),
                                SessionFake().readers(), abandoned="stopped before any seat ran")
    assert out["ok"], out
    assert seen.get("from_session") is True
