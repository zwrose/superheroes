"""Tests for the four by-release review-loop measures (#2498): owner cards per merged PR, review sessions per PR,
first-session certification, and sessions voided by a silent reviewer, each counted by plugin release."""
import datetime
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import review_measures as RM  # noqa: E402

D = datetime.date.fromisoformat
FROM, UNTIL = D("2026-10-28"), D("2026-11-11")
U = RM.UNMEASURED
SEC = "security-reviewer (round 1)"
CODE = "code-reviewer (round 1)"
RELEASES = [{"version": "0.49.0", "since": "2026-10-20"}, {"version": "0.50.0", "since": "2026-11-05T12:00:00Z"}]


def _row(name, ran="engine-record"):
    return {"name": name, "ran": ran, "commit": "c1"}


def _rec(pr, session="s1", at="2026-11-01T10:00:00Z", status="reviewed", rows=None, findings=(), ends=None):
    rec = {"pr": pr, "sessionId": session, "writtenAt": at, "status": status, "rounds": {"count": 1},
           "reviewers": rows if rows is not None else [_row(SEC)], "findings": list(findings)}
    if ends is not None:
        rec["silenceWatchdogEnds"] = ends
    return rec


def _card(key, outcome="left-for-owner", reason="why"):
    return {"id": key, "findingKey": key, "outcome": outcome, "reason": reason, "raisedBy": "security-reviewer"}


def _end(seat):
    return {"seat": seat, "attempt": 1, "silentSeconds": 400}


def _m(records, **over):
    inp = {"records": records, "releases": RELEASES, "mergedPrs": [1, 2, 3, 4]}
    inp.update(over)
    row = RM.compute(inp, FROM, UNTIL)
    assert RM.problems(row) == []
    return row["measures"], {u["measure"]: u["reason"] for u in row["unmeasured"]}


def test_a_session_runs_on_the_release_adopted_last_before_it_even_the_same_day():
    m, _ = _m([_rec(1, at="2026-11-05T11:59:00Z"), _rec(2, at="2026-11-05T12:00:00Z")])
    by = m["sessionsPerPrByRelease"]["byRelease"]
    assert by == {"0.49.0": {"median": 1, "p90": 1}, "0.50.0": {"median": 1, "p90": 1}}


def test_a_pr_counts_under_the_release_its_first_in_window_session_ran_on():
    m, _ = _m([_rec(1, "s1", at="2026-11-01T10:00:00Z"), _rec(1, "s2", at="2026-11-07T10:00:00Z"),
               _rec(1, "s3", at="2026-11-08T10:00:00Z")])
    assert m["sessionsPerPrByRelease"] == {"byRelease": {"0.49.0": {"median": 3, "p90": 3}}, "unplaced": 0}


def test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only():
    merged_member = _card("k3", reason="same defect (merged into k1)")
    m, _ = _m([_rec(1, "s1", findings=[_card("k1"), _card("k2", outcome="fixed")]),
               _rec(1, "s2", at="2026-11-02T10:00:00Z", findings=[_card("k1"), _card("k4"), merged_member]),
               _rec(5, findings=[_card("k9")])], mergedPrs=[1])
    assert m["ownerCardsPerMergedPr"] == {"byRelease": {"0.49.0": {"median": 2, "p90": 2, "total": 2}}, "unplaced": 0}


def test_owner_cards_without_the_merged_list_read_unmeasured_never_zero():
    m, why = _m([_rec(1)], mergedPrs=None)
    assert m["ownerCardsPerMergedPr"] == U and why["ownerCardsPerMergedPr"] == "no-merged-input"
    m, why = _m([_rec(1)], mergedPrs=[True])
    assert m["ownerCardsPerMergedPr"] == U and why["ownerCardsPerMergedPr"] == "incomplete-evidence"


def test_first_session_certification_reads_the_prs_first_session_even_before_the_window():
    early = _rec(1, "s0", at="2026-10-21T10:00:00Z", status="not-reviewed")
    m, _ = _m([early, _rec(1, "s1", at="2026-11-01T10:00:00Z"), _rec(2, "s2", at="2026-11-06T10:00:00Z")])
    assert m["firstSessionCertification"]["byRelease"] == {
        "0.49.0": {"certified": 0, "prs": 1, "share": 0.0}, "0.50.0": {"certified": 1, "prs": 1, "share": 1.0}}


def test_a_session_is_voided_by_a_silent_reviewer_only_when_it_did_not_certify_and_the_silent_seat_never_answered():
    at = "2026-11-06T10:00:00Z"
    m, _ = _m([_rec(1, "s1", at=at, status="not-reviewed", rows=[_row(SEC, "not-run"), _row(CODE)], ends=[_end(SEC)]),
               _rec(2, "s2", at=at, status="reviewed", rows=[_row(SEC, "not-run"), _row(CODE)], ends=[_end(SEC)]),
               _rec(3, "s3", at=at, status="not-reviewed", rows=[_row(SEC), _row(CODE)], ends=[_end(SEC)]),
               _rec(4, "s4", at=at, status="not-reviewed", rows=[_row(SEC, "not-run")])])
    assert m["silentReviewerVoids"] == {"byRelease": {"0.50.0": {"voided": 1, "sessions": 4}}, "unplaced": 0}


def test_a_release_before_watchdog_ends_were_recorded_reads_unmeasured():
    m, why = _m([_rec(1, at="2026-11-01T10:00:00Z")], releases=[{"version": "0.47.0", "since": "2026-10-01"}])
    assert m["silentReviewerVoids"]["byRelease"] == {"0.47.0": U}
    assert why["silentReviewerVoids.byRelease.0.47.0"] == "watchdog-ends-not-recorded"


def test_malformed_watchdog_ends_read_unmeasured_for_that_release():
    m, why = _m([_rec(1, at="2026-11-06T10:00:00Z", ends=[{"attempt": 1}])])
    assert m["silentReviewerVoids"]["byRelease"] == {"0.50.0": U}
    assert why["silentReviewerVoids.byRelease.0.50.0"] == "incomplete-evidence"


def test_missing_or_malformed_releases_leave_all_four_unmeasured():
    for releases, reason in ((None, "no-releases-input"), ([{"version": "0.50", "since": "2026-10-01"}], "incomplete-evidence"),
                             ([{"version": "0.50.0", "since": "soon"}], "incomplete-evidence")):
        m, why = _m([_rec(1)], releases=releases)
        assert all(m[k] == U and why[k] == reason for k in RM.BY_RELEASE)


def test_a_session_before_every_release_is_unplaced_never_counted_under_one():
    m, _ = _m([_rec(1, at="2026-10-29T10:00:00Z")], releases=[{"version": "0.50.0", "since": "2026-11-05"}])
    assert all(m[k] == {"byRelease": {}, "unplaced": 1} for k in RM.BY_RELEASE)


def test_a_row_written_before_the_by_release_measures_still_has_the_fixed_shape():
    row = RM.compute({}, FROM, UNTIL)
    old = dict(row, schema="review-loop-measures/1", measures={k: row["measures"][k] for k in RM.MEASURES_V1})
    assert RM.problems(old) == []
    assert RM.problems(dict(old, measures=row["measures"]))  # a /1 row carrying the /2 measures is off its shape
    assert "No review-loop measures row yet." not in RM.render([old])


def test_a_by_release_measure_off_its_shape_is_named():
    m_row = RM.compute({"records": [_rec(1)], "releases": RELEASES, "mergedPrs": [1]}, FROM, UNTIL)
    m_row["measures"]["sessionsPerPrByRelease"]["byRelease"]["0.49.0"] = 3
    assert RM.problems(m_row)
