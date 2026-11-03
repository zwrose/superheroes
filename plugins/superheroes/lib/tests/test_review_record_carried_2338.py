"""A carried finding this session's verifier graded shown wrong reads fixed when a fixed check proves it, and the
`Test lens:` line counts only this round's findings, saying how many were carried over from an earlier review.

Edges: E-a no earlier record · E-b an earlier record whose `findings` is not a list · E-c a same-session rewrite looks
past its own record · E-d a shown-wrong finding with no grade of its own (a repeat) stays · E-e a grade whose verdict is
not wrong stays.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import review_record as rr  # noqa: E402

from test_review_record_carried_recheck import FIX, PRIOR, X, X_KEY, account, entry, readers  # noqa: E402
from test_review_record_session import CODEX, HEAD, THIRD  # noqa: E402

PROOF = "plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md"
OLD = "the verifier showed the cited line does not exist"
GRADE = {"verdict": "wrong", "reason": OLD}
W = dict(X, outcome="shown-wrong", reason=OLD, grade=GRADE)
U = dict(X, outcome=None, reason="still open")
OVERRULED = "; this session's verifier graded it shown wrong, and the fixed check overrules that grade"


def record(session, finding):
    """An earlier record of ``session`` that lists ``finding`` under its stored key."""
    return {"sessionId": session, "findings": [dict(finding, findingKey=rr._key(finding))]}


def build_w(checks, prior=PRIOR, history=(), finding=W, **kw):
    return rr.build_record(account(checks, [finding]), readers(**kw), prior=prior, history=history)


def the_one(rec):
    (f,) = rec["findings"]
    return f


# --- the carried check reaches a shown-wrong finding ---

@pytest.mark.parametrize("prior", [
    pytest.param(PRIOR, id="carried-left-for-owner"),
    pytest.param(record("s-0", U), id="carried-undecided"),
])
def test_t1_a_fixed_check_moves_a_finding_the_verifier_graded_wrong_to_fixed(prior):
    # axis: a shown-wrong finding with its own wrong grade enters the carried chain and a fixed check at the head overrules the grade
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
    assert rr._key(W) == X_KEY
    calls = []
    rec = build_w([entry()], prior=prior, calls=calls)
    f = the_one(rec)
    assert f["outcome"] == "fixed"
    assert f["reason"] == (f"fixed after its review at {FIX[:7]}: ran the test; it passes "
                           f"(checked against the final commit {HEAD[:7]} when this record was written)"
                           f"{OVERRULED}; earlier: {OLD}")
    (row,) = rec["carriedRechecks"]
    assert row == {"finding": "f-1", "settled": "fixed", "result": "fixed", "why": "fixed", "commit": FIX,
                   "checkedHead": HEAD, "evidence": "ran the test; it passes"}
    assert calls == [(None, FIX, HEAD)]


@pytest.mark.parametrize("checks, prior, kw, why, opening", [
    pytest.param([entry()], PRIOR, {"ancestor": False}, f"its fix commit {FIX[:7]} is not in the final commit's history",
                 "a check against the final commit", id="fix-commit-not-in-history"),
    pytest.param([entry()], PRIOR, {"ancestor": None}, "its fix commit's place in the history could not be read",
                 "a check against the final commit", id="history-unreadable"),
    pytest.param([entry()], {"findings": []}, {}, "not carried from an earlier record",
                 "a check against the final commit", id="not-carried"),
    pytest.param([entry()], None, {}, "not carried from an earlier record",
                 "a check against the final commit", id="no-earlier-record"),
    pytest.param([entry()], {"sessionId": "s-0", "findings": "none"}, {}, "not carried from an earlier record",
                 "a check against the final commit", id="earlier-findings-not-a-list"),
    pytest.param([entry(checkedHead=THIRD)], PRIOR, {}, f"checked on {THIRD[:7]}, not the final commit {HEAD[:7]}",
                 "a check", id="checked-on-another-head"),
    pytest.param([entry(settled="applies")], PRIOR, {}, "the check found it still applies: ran the test; it passes",
                 "a check against the final commit", id="applies"),
    pytest.param([entry(settled="unsettled")], PRIOR, {}, "the check could not settle it: ran the test; it passes",
                 "a check against the final commit", id="unsettled"),
])
def test_t2_every_weaker_case_keeps_the_finding_shown_wrong(checks, prior, kw, why, opening):
    # axis: fail closed, a shown-wrong finding stays shown-wrong unless every condition of the chain holds; it is never removed
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
    rec = build_w(checks, prior, **kw)
    f = the_one(rec)
    assert f["outcome"] == "shown-wrong"
    assert f["reason"] == f"{OLD}; {opening} kept it shown wrong: {why}"
    assert "for the owner" not in f["reason"] and "overrules" not in f["reason"]
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["why"]) == ("kept", why)


def test_t3_a_finding_the_earlier_record_of_another_session_lists_shown_wrong_is_not_moved():
    # axis: the earlier record of another session already lists the finding shown-wrong, so a fixed check does not move it
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
    rec = build_w([entry()], prior=record("s-0", W))
    f = the_one(rec)
    assert f["outcome"] == "shown-wrong" and f["reason"] == OLD
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["why"]) == ("unchanged", "shown wrong in the earlier record")


def test_t4_a_same_session_rewrite_looks_past_its_own_record_to_the_other_sessions():
    # axis: the earlier record is the latest of ANOTHER session, so a rewrite whose prior is this session's own record reads the older one
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
    own = record("s-1", W)
    older = record("s-0", U)
    rec = build_w([entry()], prior=own, history=[older])
    f = the_one(rec)
    assert f["outcome"] == "fixed" and f["reason"].endswith(f"{OVERRULED}; earlier: {OLD}")
    assert [r["result"] for r in rec["carriedRechecks"]] == ["fixed"]
    # and the other session's shown-wrong still holds when the rewrite reads it past its own record
    held = build_w([entry()], prior=own, history=[record("s-0", W)])
    assert the_one(held)["outcome"] == "shown-wrong"
    assert [(r["result"], r["why"]) for r in held["carriedRechecks"]] == [("unchanged", "shown wrong in the earlier record")]


@pytest.mark.parametrize("finding", [
    pytest.param({**{k: v for k, v in W.items() if k != "grade"},
                  "repeatOf": {"findingKey": X_KEY, "id": "f-0", "fixHolds": True}}, id="repeat-with-no-grade"),
    pytest.param(dict(W, grade={"verdict": "plausible", "reason": "could not show it"}), id="grade-not-wrong"),
    pytest.param(dict(W, grade={"verdict": "confirmed", "reason": "it holds"}), id="grade-confirmed"),
])
def test_t5_a_shown_wrong_finding_without_its_own_wrong_grade_is_not_moved(finding):
    # axis: a shown-wrong finding moves only with this session's own verifier wrong grade, never one inherited by repeat or graded otherwise
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
    rec = build_w([entry()], prior=PRIOR, finding=finding)
    f = the_one(rec)
    assert f["outcome"] == "shown-wrong" and f["reason"] == OLD
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["why"]) == ("unchanged", "shown wrong without this session's verifier grade")


def test_t6_left_for_owner_and_undecided_still_move_to_fixed_without_the_overruled_clause():
    # axis: the shown-wrong branch leaves the left-for-owner and undecided paths as they were
    f = the_one(rr.build_record(account([entry()]), readers(), prior=PRIOR))
    assert f["outcome"] == "fixed"
    assert f["reason"] == (f"fixed after its review at {FIX[:7]}: ran the test; it passes "
                           f"(checked against the final commit {HEAD[:7]} when this record was written); earlier: waits for the owner")
    u = the_one(build_w([entry()], prior=record("s-0", U), finding=U))
    assert u["outcome"] == "fixed" and "overrules" not in u["reason"] and u["reason"].endswith("; earlier: still open")
    kept = the_one(build_w([entry(settled="applies")], prior=record("s-0", U), finding=U))
    assert kept["outcome"] is None and "kept it open: " in kept["reason"]


# --- the test-lens line counts this round's findings only ---

TEST_ROW = {"name": "test-role", "vendor": "codex", "model": CODEX, "planned": True, "ran": True, "runDir": None}
CARRIED_CLAUSE = "carried over from an earlier review"


def lens_finding(n, reviewer="test-role"):
    return {"id": f"t-{n}", "title": f"Test gap {n}", "severity": "Minor", "file": f"t{n}.py", "line": n, "body": "b",
            "consequence": "c", "outcome": "fixed", "reason": "fixed in 1a2b3c4", "reviewer": reviewer}


def lens_build(findings, prior=None, history=(), row=TEST_ROW, extra_rows=()):
    acct = account([], findings)
    # the full lane credits a session-reported row without an engine record
    acct.update(lane="full", laneReason="big", makers=[{"family": "anthropic"}])
    acct["reviewers"] = [*acct["reviewers"], *([row] if row else []), *extra_rows]
    return rr.build_record(acct, readers(), prior=prior, history=history)


def lens_line(rec):
    (line,) = [l for l in rr.render(rec).split("\n") if l.startswith("Test lens:")]
    return line


def earlier(session, *findings):
    return {"sessionId": session, "findings": [dict(f, findingKey=rr._key(f)) for f in findings]}


def test_t7_a_round_that_raised_nothing_reads_zero_and_the_carried_ones_are_counted_apart():
    # axis: the own count leaves out every carried finding, and the ran line says both counts in words that cannot be added
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
    found = [lens_finding(1), lens_finding(2)]
    rec = lens_build(found, prior=earlier("s-0", *found))
    part = rec["testLens"]
    assert part["findings"] == 0 and part["carriedFindings"] == 2
    assert lens_line(rec).endswith("; 0 findings raised in this round, 2 findings carried over from an earlier review.")


def test_t8_new_and_carried_findings_are_two_counts_and_never_a_sum():
    # axis: one new and two carried findings read 1 and 2, and no number in the line is their sum
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
    found = [lens_finding(1), lens_finding(2), lens_finding(3)]
    rec = lens_build(found, prior=earlier("s-0", found[1], found[2]))
    assert (rec["testLens"]["findings"], rec["testLens"]["carriedFindings"]) == (1, 2)
    line = lens_line(rec)
    assert line.endswith("; 1 finding raised in this round, 2 findings carried over from an earlier review.")
    assert "3" not in line


def test_t9_no_carried_finding_leaves_the_part_and_the_line_as_they_were():
    # axis: with nothing carried the part has no carriedFindings key and the line is the earlier form, so older records render unchanged
    found = [lens_finding(1)]
    for prior in (None, earlier("s-0", lens_finding(9))):
        rec = lens_build(found, prior=prior)
        assert "carriedFindings" not in rec["testLens"] and rec["testLens"]["findings"] == 1
        line = lens_line(rec)
        assert line.endswith("; calibration read: not shown (no engine record); 1 finding raised.")
        assert CARRIED_CLAUSE not in line and "in this round" not in line
    old = {"testLens": {"listed": True, "ran": True, "ranFrom": "engine-record", "row": "test-role", "commit": HEAD,
                        "coversFinalCommit": True, "calibrationRead": None, "findings": 2},
           "reviewers": []}
    assert rr._test_lens_line(old).endswith("; 2 findings raised.")


def test_t10_a_carried_count_rides_the_not_listed_and_the_did_not_run_lines():
    # axis: with no test-role reviewer listed, or one that did not run, the carried count still shows and reads as carried
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
    found = [lens_finding(1), lens_finding(2)]
    rec = lens_build(found, prior=earlier("s-0", *found), row=None)
    assert rec["testLens"] == {"listed": False, "carriedFindings": 2}
    assert lens_line(rec) == "Test lens: no test-role reviewer was listed; 2 findings carried over from an earlier review."
    rec = lens_build(found[:1], prior=earlier("s-0", found[0]), row=dict(TEST_ROW, ran=False))
    assert rec["testLens"]["ran"] is False and rec["testLens"]["findings"] == 0 and rec["testLens"]["carriedFindings"] == 1
    assert lens_line(rec) == "Test lens: did not run; 1 finding carried over from an earlier review."
    # nothing carried: both lines read as they did
    assert lens_build(found, row=None)["testLens"] == {"listed": False}
    assert lens_line(lens_build(found, row=None)) == "Test lens: no test-role reviewer was listed."
    assert lens_line(lens_build([], row=dict(TEST_ROW, ran=False))) == "Test lens: did not run."


def test_t11_a_carried_finding_raised_in_another_round_still_counts_as_a_carried_test_lens_finding():
    # axis: a finding is a test-lens finding by its own reviewer identity, not only by the current rows' names
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
    other_round = lens_finding(1, reviewer="test-role (round 2)")
    rec = lens_build([other_round], prior=earlier("s-0", other_round), row=dict(TEST_ROW, name="test-role (round 1)"))
    assert (rec["testLens"]["findings"], rec["testLens"]["carriedFindings"]) == (0, 1)
    labelled = lens_finding(2, reviewer="Code, Test")
    rec = lens_build([labelled], prior=earlier("s-0", labelled))
    assert (rec["testLens"]["findings"], rec["testLens"]["carriedFindings"]) == (0, 1)
    not_test = lens_finding(3, reviewer="Testing")
    rec = lens_build([not_test], prior=earlier("s-0", not_test))
    assert rec["testLens"]["findings"] == 0 and "carriedFindings" not in rec["testLens"]


def test_t12_a_same_session_rewrite_counts_its_own_findings_as_raised_not_carried():
    # axis: the earlier record is another session's, so a finding held by this session's own prior record is raised in this round
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2338_carried_record.md
    found = [lens_finding(1)]
    rec = lens_build(found, prior=earlier("s-1", *found))
    assert rec["testLens"]["findings"] == 1 and "carriedFindings" not in rec["testLens"]
    assert lens_line(rec).endswith("; 1 finding raised.")
    # past its own record, the other session's record is what counts as carried
    rec = lens_build(found, prior=earlier("s-1", *found), history=[earlier("s-0", *found)])
    assert (rec["testLens"]["findings"], rec["testLens"]["carriedFindings"]) == (0, 1)


def test_t13_the_carried_clause_and_a_carried_row_read_as_two_facts_on_one_line():
    # axis: "carried from the earlier review of <sha>" is a whole carried row; "carried over from an earlier review" is findings
    part = {"listed": True, "ran": True, "ranFrom": "engine-record", "row": "test-role", "commit": HEAD,
            "coversFinalCommit": True, "calibrationRead": None, "findings": 0, "carriedFindings": 2,
            "carried": {"commit": THIRD}}
    row = {"name": "test-role", "ran": "engine-record", "commit": THIRD, "coversFinalCommit": True}
    line = rr._test_lens_line({"testLens": part, "reviewers": [row]})
    assert line.startswith(f"Test lens: carried from the earlier review of {THIRD[:7]}")
    assert line.endswith("; 0 findings raised in this round, 2 findings carried over from an earlier review.")


def test_t14_a_nonpositive_or_odd_carried_count_adds_no_clause():
    # axis: only a positive int is a carried count; zero, a bool or a string leaves the line as it was
    part = {"listed": False}
    for odd in (0, True, "2", None, -1):
        assert rr._test_lens_line({"testLens": dict(part, carriedFindings=odd), "reviewers": []}) == \
            "Test lens: no test-role reviewer was listed."
