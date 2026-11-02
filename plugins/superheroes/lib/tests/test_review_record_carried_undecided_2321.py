"""#2321: a carried finding left undecided by an abandoned review is settled by the same carriedChecks chain as a
left-for-owner one, and by nothing weaker."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402

from test_review_record_abandoned_2137 import LIVE_FINDING, REASON  # noqa: E402
from test_review_record_carried_recheck import FIX, PRIOR, X, X_KEY, account, entry, readers  # noqa: E402
from test_review_record_session import HEAD, THIRD, Fake, Session, _by_key, _reviewed_second_session, extras, put_extras  # noqa: E402

PROOF = "plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md"
OLD = "still open when the review loop ended (carried from the earlier review record)"
U = dict(X, outcome=None, reason=OLD)
PRIOR_U = {"findings": [dict(U, findingKey=X_KEY)]}
SECOND = {"findingKey": "b.py::u@L8", "id": "f-2", "title": "u", "severity": "Important", "file": "b.py", "line": 8,
          "detail": "d2", "dimension": "code-reviewer"}
HAS_NO_OUTCOME = "has no outcome"


def build_u(checks, prior=PRIOR_U, finding=U, **kw):
    return rr.build_record(account(checks, [finding]), readers(**kw), prior=prior)


def the_one(rec):
    (f,) = rec["findings"]
    return f


# --- unit: the chain in _recheck_carried ---

@pytest.mark.parametrize("finding", [
    pytest.param(U, id="outcome-null"),
    pytest.param({k: v for k, v in U.items() if k != "outcome"}, id="outcome-absent"),
])
def test_t1_a_fixed_check_at_the_final_head_settles_an_undecided_carried_finding(finding):
    # axis: an undecided carried finding moves to fixed through the same chain as a left-for-owner one
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md
    calls = []
    rec = build_u([entry()], finding=finding, calls=calls)
    f = the_one(rec)
    assert f["outcome"] == "fixed"
    assert f["reason"] == (f"fixed after its review at {FIX[:7]}: ran the test; it passes "
                           f"(checked against the final commit {HEAD[:7]} when this record was written); earlier: {OLD}")
    (row,) = rec["carriedRechecks"]
    assert row == {"finding": "f-1", "settled": "fixed", "result": "fixed", "why": "fixed", "commit": FIX,
                   "checkedHead": HEAD, "evidence": "ran the test; it passes"}
    assert calls == [(None, FIX, HEAD)]


@pytest.mark.parametrize("checks, prior, kw, why, opening", [
    pytest.param([entry(checkedHead=THIRD)], PRIOR_U, {}, f"checked on {THIRD[:7]}, not the final commit {HEAD[:7]}",
                 "a check", id="head-moved-after-the-check"),
    pytest.param([entry()], PRIOR_U, {"ancestor": False}, f"its fix commit {FIX[:7]} is not in the final commit's history",
                 "a check against the final commit", id="fix-commit-not-in-history"),
    pytest.param([entry()], PRIOR_U, {"ancestor": None}, "its fix commit's place in the history could not be read",
                 "a check against the final commit", id="history-unreadable"),
    pytest.param([entry()], PRIOR_U, {"ancestor": 1}, "its fix commit's place in the history could not be read",
                 "a check against the final commit", id="ancestor-truthy-not-true"),
    pytest.param([entry()], {"findings": []}, {}, "not carried from an earlier record",
                 "a check against the final commit", id="not-carried"),
    pytest.param([entry()], None, {}, "not carried from an earlier record",
                 "a check against the final commit", id="no-earlier-record"),
    pytest.param([entry(settled="applies")], PRIOR_U, {}, "the check found it still applies: ran the test; it passes",
                 "a check against the final commit", id="applies"),
    pytest.param([entry(settled="unsettled")], PRIOR_U, {}, "the check could not settle it: ran the test; it passes",
                 "a check against the final commit", id="unsettled"),
])
def test_t3_every_other_case_keeps_an_undecided_finding_open(checks, prior, kw, why, opening):
    # axis: fail closed, an undecided finding stays undecided unless every condition of the chain holds
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md
    rec = build_u(checks, prior, **kw)
    f = the_one(rec)
    assert f["outcome"] is None
    assert f["reason"] == f"{OLD}; {opening} kept it open: {why}"
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["why"]) == ("kept", why)


def test_t3_no_entry_leaves_an_undecided_finding_as_it_was():
    # axis: with no carriedChecks entry an undecided finding is untouched and no row is written
    rec = build_u([])
    f = the_one(rec)
    assert f["outcome"] is None and f["reason"] == OLD and rec["carriedRechecks"] == []


def test_t7_an_undecided_finding_not_carried_from_an_earlier_record_stays_undecided():
    # axis: a not-carried undecided finding never settles, even on a fixed entry at the final head
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md
    rec = build_u([entry()], {"findings": []})
    f = the_one(rec)
    assert f["outcome"] is None
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["why"]) == ("kept", "not carried from an earlier record")


@pytest.mark.parametrize("settled, said", [("applies", "the check found it still applies: "),
                                           ("unsettled", "the check could not settle it: ")])
def test_t5_a_left_for_owner_finding_is_unchanged_in_outcome_reason_and_row(settled, said):
    # axis: left-for-owner reasons and rows stay byte-identical, "kept it for the owner"
    rec = rr.build_record(account([entry(settled=settled)]), readers(), prior=PRIOR)
    f = the_one(rec)
    assert f["outcome"] == "left-for-owner"
    assert f["reason"] == f"waits for the owner; a check against the final commit kept it for the owner: {said}ran the test; it passes"
    assert "kept it open" not in f["reason"]
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["why"]) == ("kept", said + "ran the test; it passes")


def test_t5_a_fixed_check_still_settles_a_left_for_owner_finding_with_the_existing_reason():
    # axis: the left-for-owner fixed path is unchanged
    f = the_one(rr.build_record(account([entry()]), readers(), prior=PRIOR))
    assert f["outcome"] == "fixed"
    assert f["reason"] == (f"fixed after its review at {FIX[:7]}: ran the test; it passes "
                           f"(checked against the final commit {HEAD[:7]} when this record was written); earlier: waits for the owner")


@pytest.mark.parametrize("outcome", ["fixed", "craft"])
def test_t5_a_finding_with_another_outcome_is_still_unchanged(outcome):
    # axis: every outcome other than left-for-owner and undecided stays result unchanged, not left for the owner
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md
    rec = rr.build_record(account([entry()], [dict(X, outcome=outcome, reason="done")]), readers(), prior=PRIOR)
    assert the_one(rec)["outcome"] == outcome and the_one(rec)["reason"] == "done"
    assert [(r["result"], r["why"]) for r in rec["carriedRechecks"]] == [("unchanged", "not left for the owner")]


# --- end to end: an abandoned review's undecided finding, carried into a later reviewed session ---

def _abandoned_first(tmp_path, fake, findings):
    session = Session(tmp_path, terminal=None, findings=findings).seat("code-reviewer").save()
    out = rs.write_from_session(session, put_extras(tmp_path, extras()), str(tmp_path), fake.readers(), abandoned=REASON)
    assert out["ok"] and out["status"] == "not-reviewed", out
    return [f for f in _by_key(fake) if f["outcome"] is None]


def _later(tmp_path, fake, session, body, checks):
    rd = {**fake.readers(), "is_ancestor": lambda root, commit, to: True}
    out = rs.write_from_session(session, put_extras(tmp_path, {**extras(**body), "carriedChecks": checks}), str(tmp_path), rd)
    return out, rd


def _setup(tmp_path, findings):
    """The control (the later session with no earlier record reads reviewed), then the abandoned first record."""
    session, runs, body = _reviewed_second_session(tmp_path)
    control = Fake(runs=runs)
    control_out = rs.write_from_session(session, put_extras(tmp_path, extras(**body)), str(tmp_path), control.readers())
    assert control_out["ok"] and control_out["status"] == "reviewed" and control_out["whatIsMissing"] == [], control_out
    fake = Fake(runs=runs)
    return fake, session, body, _abandoned_first(tmp_path, fake, findings)


def _check(held, **over):
    return {"key": held["findingKey"], "settled": "fixed", "commit": FIX, "checkedHead": HEAD, "evidence": "ran the test; it passes", **over}


def test_t2_a_fixed_check_settles_the_finding_an_abandoned_review_left_open_and_the_record_reads_reviewed(tmp_path):
    # axis: end to end, the carried undecided finding moves to fixed on a driver check and the record reads reviewed
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md
    fake, body, (held,) = _setup(tmp_path, [LIVE_FINDING])
    assert held["outcome"] is None
    out, rd = _later(tmp_path, fake, body, [_check(held)])
    assert out["ok"], out
    assert out["status"] == "reviewed", out
    assert out["whatIsMissing"] == []
    rec = rr.read(7, readers=rd)
    (carried,) = rec["findings"]
    assert carried["outcome"] == "fixed" and [r["result"] for r in rec["carriedRechecks"]] == ["fixed"]


def test_t4_a_check_on_an_older_head_leaves_the_finding_undecided_and_the_record_not_reviewed(tmp_path):
    # axis: end to end, a check not made on the final commit settles nothing and the record names the undecided finding
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md
    fake, body, (held,) = _setup(tmp_path, [LIVE_FINDING])
    out, rd = _later(tmp_path, fake, body, [_check(held, checkedHead=THIRD)])
    assert out["ok"], out
    assert out["status"] == "not-reviewed", out
    (line,) = out["whatIsMissing"]
    assert HAS_NO_OUTCOME in line, line
    (carried,) = rr.read(7, readers=rd)["findings"]
    assert carried["outcome"] is None


def test_t6_settling_one_of_two_undecided_findings_leaves_the_other_open(tmp_path):
    # axis: end to end, a check settles only the finding it names; the other keeps the record not reviewed
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2321_undecided_carried.md
    fake, body, held = _setup(tmp_path, [LIVE_FINDING, SECOND])
    first = next(h for h in held if h["id"] == "f-1")
    out, rd = _later(tmp_path, fake, body, [_check(first)])
    assert out["ok"], out
    assert out["status"] == "not-reviewed", out
    by_id = {f["id"]: f for f in rr.read(7, readers=rd)["findings"]}
    assert by_id["f-1"]["outcome"] == "fixed" and by_id["f-2"]["outcome"] is None
    (line,) = out["whatIsMissing"]
    assert HAS_NO_OUTCOME in line and ("f-2" in line or "u" in line), line
    assert "f-1" not in line
