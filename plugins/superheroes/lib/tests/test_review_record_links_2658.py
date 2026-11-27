"""The review record reads a PR's issues only from what GitHub records, and never treats an unreadable earlier record as absent (issue 2658).

I1: an issue counts as linked only when GitHub records the link and the link's repository is the record's repository;
the description alone never links; a link read that fails, is refused or cannot be read is disclosed as unreadable.
I2: an earlier review record that cannot be read is never treated as absent by a history consumer.

Edges: E1 an issue read fails · E2 a timeline page fails · E3 a malformed timeline row · E4 a target that is a PR ·
E5 another repository's PR with the same number · E6 another PR of this repository · E7 a description that closes #N
with no cross-reference · E8 `owner/other#N` in the description · E9 local closing list naming another repository's
issue · E10 local entry with no repository · E11 unreadable links, a full marker on the branch, a light session lane
over the cap · E12 unreadable links, no marker · E13 read_history over three kinds of unreadable record · E14 read_history
when listing fails · E15 a same-session rewrite whose intervening record is unreadable · E16 _earlier_session_record
stops · E17 a hand write with an unattributed finding and an unreadable older record.
"""
import json
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import build_lane  # noqa: E402
import gh_pages  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402

from test_review_record import EARLIER, GOOD_RUN, HEAD, Fake, account, finding, put, reviewer  # noqa: E402

REPO = "o/r"
MARKER = {"schema": build_lane.BUILD_LANE_SCHEMA, "lane": "full", "branch": "b", "currentBranch": "b", "issue": 9}
UNREADABLE_SENTENCE = ("The PR's linked issues could not be read, so no issue's lane call or build lane marker "
                       "was matched to them.")


def cross_ref(number=7, repo=REPO, **issue):
    return {"event": "cross-referenced",
            "source": {"issue": {"number": number, "pull_request": {}, "repository": {"full_name": repo}, **issue}}}


def issue_obj(n, **extra):
    return {"number": n, **extra}


class GH:
    """A stand-in for `rr._run` serving the REST reads of the cloud reader: the PR, each issue, each issue's timeline
    (a list of pages, a page of None failing)."""

    def __init__(self, body, issues=None, timelines=None, head=HEAD):
        self.body, self.issues, self.timelines, self.head = body, issues or {}, timelines or {}, head
        self.seen = []

    def __call__(self, argv, cwd=None):
        endpoint = argv[2]
        self.seen.append(endpoint)
        if endpoint == f"repos/{REPO}/pulls/7":
            return json.dumps({"head": {"sha": self.head}, "body": self.body})
        m = re.fullmatch(rf"repos/{REPO}/issues/(\d+)", endpoint)
        if m:
            answer = self.issues.get(int(m.group(1)))
            return None if answer is None else json.dumps(answer)
        m = re.fullmatch(rf"repos/{REPO}/issues/(\d+)/timeline\?per_page=100&page=(\d+)", endpoint)
        if m:
            pages = self.timelines.get(int(m.group(1)))
            at = int(m.group(2)) - 1
            page = pages[at] if pages is not None and at < len(pages) else []
            return None if page is None else json.dumps(page)
        return None


def cloud_meta(monkeypatch, gh):
    monkeypatch.setattr(rr, "_run", gh)
    return rr._pr_meta_rest(7, REPO)


UNREADABLE_META = {"head": HEAD, "body": "", "issues": [], "laneIssues": [], "issueLinks": "unreadable"}


def links(candidates, issues, timelines, repo=REPO, pr=7):
    return rr.recorded_links(candidates, repo, pr, lambda n: issues.get(n), lambda n: timelines.get(n))


# --- the shared helper, positive ------------------------------------------------------------------------------------

def test_a_cross_reference_from_this_pr_links_the_candidate_in_order_without_duplicates_and_ignores_other_rows():
    issues = {9: issue_obj(9), 4: issue_obj(4), 5: issue_obj(5)}
    timelines = {9: [{"event": "labeled"}, cross_ref(7, "O/R")], 4: [cross_ref(7)], 5: [{"event": "commented"}]}
    assert links([9, 5, 4, 9], issues, timelines) == [9, 4]
    assert links([], issues, timelines) == []


@pytest.mark.parametrize("repo,pr", [(None, 7), ("", 7), ("no-slash", 7), ("a/b/c", 7), (REPO, "7"), (REPO, True), (REPO, None)])
def test_a_repository_or_pr_that_cannot_be_matched_leaves_the_whole_answer_unreadable(repo, pr):
    assert links([9], {9: issue_obj(9)}, {9: [cross_ref(7)]}, repo=repo, pr=pr) is None


def test_the_issue_links_unreadable_sentence_is_the_one_the_record_renders():
    assert rr.ISSUE_LINKS_UNREADABLE_LINE == " " + UNREADABLE_SENTENCE


# --- I1: the links ----------------------------------------------------------------------------------------------------

def test_e1_an_issue_read_that_fails_is_unreadable_never_no_link(monkeypatch):
    # axis: E1; an issue GitHub could not be asked about read as "not linked"
    assert links([9], {}, {9: [cross_ref(7)]}) is None
    for answer in ("text", ["x"], issue_obj(10), {"number": True}, {"title": "no number"}):
        assert links([9], {9: answer}, {9: [cross_ref(7)]}) is None
    meta = cloud_meta(monkeypatch, GH("Closes #9.", issues={}, timelines={9: [[cross_ref(7)]]}))
    assert meta == UNREADABLE_META | {"body": "Closes #9."}


def test_e2_a_timeline_page_that_fails_is_unreadable_never_a_partial_read(monkeypatch):
    # axis: E2; a timeline read that stopped at a failed page read as the rows before it, or as none
    assert links([9], {9: issue_obj(9)}, {}) is None
    full_page = [{"event": "labeled"}] * (gh_pages.PAGE_ROWS - 1) + [cross_ref(7)]
    gh = GH("Closes #9.", issues={9: issue_obj(9)}, timelines={9: [full_page, None]})
    assert cloud_meta(monkeypatch, gh) == UNREADABLE_META | {"body": "Closes #9."}
    # the first page failing is as unreadable as a later one
    gh = GH("Closes #9.", issues={9: issue_obj(9)}, timelines={9: [None]})
    assert cloud_meta(monkeypatch, gh) == UNREADABLE_META | {"body": "Closes #9."}


@pytest.mark.parametrize("row", [
    pytest.param("not a dict", id="a-row-that-is-not-an-object"),
    pytest.param({"event": "cross-referenced"}, id="no-source"),
    pytest.param({"event": "cross-referenced", "source": {"issue": "x"}}, id="source-issue-not-an-object"),
    pytest.param({"event": "cross-referenced", "source": {}}, id="source-without-an-issue"),
    pytest.param(cross_ref(None), id="pr-row-without-a-number"),
    pytest.param(cross_ref(True), id="pr-row-with-a-bool-number"),
    pytest.param(cross_ref("7"), id="pr-row-with-a-string-number"),
    pytest.param({"event": "cross-referenced", "source": {"issue": {"number": 7, "pull_request": {}}}},
                 id="pr-row-without-a-repository"),
    pytest.param(cross_ref(7, None), id="pr-row-with-a-repository-name-that-is-not-a-string"),
])
def test_e3_a_malformed_timeline_row_is_unreadable_never_skipped(row):
    # axis: E3; a row the reader cannot make sense of skipped, so a link it may have held reads as no link
    assert links([9], {9: issue_obj(9)}, {9: [cross_ref(7), row]}) is None
    assert links([9], {9: issue_obj(9)}, {9: [row]}) is None


def test_e4_a_target_that_is_a_pull_request_is_not_linked_and_its_timeline_is_not_read():
    # axis: E4; a pull request named as a closed issue counted as linked, or its timeline asked for
    asked = []

    def timeline(n):
        asked.append(n)
        return [cross_ref(7)]
    got = rr.recorded_links([9, 4], REPO, 7, lambda n: {"number": n, **({"pull_request": {}} if n == 9 else {})}, timeline)
    assert got == [4] and asked == [4]


def test_e5_a_cross_reference_from_another_repositorys_pr_with_the_same_number_is_not_linked():
    # axis: E5; the repository of the cross-referencing PR not compared
    assert links([9], {9: issue_obj(9)}, {9: [cross_ref(7, "x/y")]}) == []
    assert links([9], {9: issue_obj(9)}, {9: [cross_ref(7, "x/y"), cross_ref(7, "O/r")]}) == [9]


def test_e6_a_cross_reference_from_another_pr_of_this_repository_is_not_linked():
    # axis: E6; the number of the cross-referencing PR not compared
    assert links([9], {9: issue_obj(9)}, {9: [cross_ref(8)]}) == []


def test_e7_a_description_that_closes_an_issue_with_no_cross_reference_does_not_link_it(monkeypatch):
    # axis: E7 (the DoD no-link test); the description's closing keyword read as GitHub's link
    gh = GH("Closes #9.\nmore", issues={9: issue_obj(9, body="**Lane call:** micro. one line")},
            timelines={9: [[{"event": "labeled"}, cross_ref(8)]]})
    meta = cloud_meta(monkeypatch, gh)
    assert meta == {"head": HEAD, "body": "Closes #9.\nmore", "issues": [], "laneIssues": []}
    fake = Fake(meta=meta, issue_bodies={9: "**Lane call:** micro. one line"},
                marker=MARKER)
    rec = rr.build_record(account(), fake.readers())
    # neither the issue's lane call nor the build lane marker bound to that issue reaches the record
    assert rec["lane"] == {"value": "full", "source": rr.SESSION, "reason": "big"}


def test_e7_a_cross_reference_from_this_pr_links_the_description_named_issue(monkeypatch):
    # the control of E7: the same description, with GitHub's own cross-reference, links the issue and its lane call counts
    gh = GH("Closes #9.\nmore", issues={9: issue_obj(9)}, timelines={9: [[cross_ref(7)]]})
    meta = cloud_meta(monkeypatch, gh)
    assert meta == {"head": HEAD, "body": "Closes #9.\nmore", "issues": [9], "laneIssues": [9]}
    fake = Fake(meta=meta, issue_bodies={9: "**Lane call:** micro. one line"})
    assert rr.build_record(account(), fake.readers())["lane"]["source"] == "issue lane call"


def test_e8_another_repositorys_issue_in_the_description_is_never_a_candidate(monkeypatch):
    # axis: E8; `owner/other#N` read as this repository's issue N, so its timeline is asked for
    gh = GH("Closes x/y#9.\nCloses other/repo#10\nCloses O/R#11", issues={11: issue_obj(11)},
            timelines={11: [[cross_ref(7)]]})
    meta = cloud_meta(monkeypatch, gh)
    assert meta["issues"] == [11] and "issueLinks" not in meta
    assert not [e for e in gh.seen if re.search(r"issues/(9|10)\b", e)], gh.seen


def _local_gh(monkeypatch, refs, repo=REPO):
    monkeypatch.setattr(rr, "_gh_json", lambda *a: {"headRefOid": HEAD, "body": "x", "closingIssuesReferences": refs})
    return rr._pr_meta(7, repo)


def _ref(number, owner="o", name="r"):
    return {"number": number, "repository": {"name": name, "owner": {"login": owner}}}


def test_e9_a_local_closing_reference_in_another_repository_is_not_this_repositorys_issue(monkeypatch):
    # axis: E9; the repository of a closingIssuesReferences entry dropped, so another repository's #N counts here
    meta = _local_gh(monkeypatch, [_ref(3, "x", "y"), _ref(5), _ref(6, "O", "R")])
    assert meta == {"head": HEAD, "body": "x", "issues": [5, 6]}
    assert _local_gh(monkeypatch, [_ref(3, "x", "y")])["issues"] == []


@pytest.mark.parametrize("refs,repo", [
    pytest.param([{"number": 3}], REPO, id="an-entry-with-no-repository"),
    pytest.param([_ref(5), {"number": 3, "repository": {"name": "r"}}], REPO, id="an-entry-with-no-owner"),
    pytest.param(None, REPO, id="no-list-at-all"),
    pytest.param([_ref(5)], None, id="no-repository-to-compare-with"),
])
def test_e10_a_local_entry_that_cannot_be_read_leaves_the_links_unreadable(monkeypatch, refs, repo):
    # axis: E10; an entry the reader cannot place in a repository counted, or dropped as "no link"
    assert _local_gh(monkeypatch, refs, repo) == {"head": HEAD, "body": "x", "issues": [], "issueLinks": "unreadable"}


def test_a_failed_local_head_read_is_still_no_meta(monkeypatch):
    monkeypatch.setattr(rr, "_gh_json", lambda *a: None)
    assert rr._pr_meta(7, REPO) is None
    monkeypatch.setattr(rr, "_gh_json", lambda *a: {"body": "x", "closingIssuesReferences": []})
    assert rr._pr_meta(7, REPO) is None


def test_the_cloud_reader_with_no_repository_reads_the_links_as_unreadable(monkeypatch):
    monkeypatch.setattr(rr, "_run", GH("Closes #9."))
    monkeypatch.setattr(rr, "_gh_json", lambda *a: {"head": {"sha": HEAD}, "body": "Closes #9."})
    assert rr._pr_meta_rest(7, None) == UNREADABLE_META | {"body": "Closes #9."}


# --- I1: the record discloses an unreadable read -------------------------------------------------------------------

def test_e11_unreadable_links_never_let_a_full_marker_promote_the_sessions_lane(tmp_path):
    # axis: E11; a full build lane marker the PR could not be matched to promoting a light review past its round cap
    over_cap = {"count": 5, "cap": 4, "stoppedAtCap": False}
    fake = Fake(meta=dict(UNREADABLE_META), marker=MARKER, issue_bodies={9: "**Lane call:** full. spans contracts"})
    with pytest.raises(rr.Refusal) as e:
        rr.build_record(account(lane="light", rounds=over_cap), fake.readers())
    assert e.value.reason == "review-record-round-cap-exceeded"
    # under the cap the session's own lane stands, disclosed, with the marker deciding nothing
    out = rr.write(put(tmp_path, account(lane="light")), str(tmp_path), fake.readers())
    assert out["ok"] and out["action"] == "created", out
    body = fake.marked()[-1]["body"]
    rec = rr._parse_body(body)
    assert rec["lane"]["value"] == "light" and rec["lane"]["source"] == rr.SESSION
    assert rec["lane"]["issueLinks"] == "unreadable"
    assert "Lane: light (" in body and UNREADABLE_SENTENCE in body
    # the same marker with readable links naming its issue does decide the full lane
    readable = Fake(meta={"head": HEAD, "body": "", "issues": [9], "laneIssues": [9]}, marker=MARKER)
    assert rr.build_record(account(lane="light"), readable.readers())["lane"]["value"] == "full"


def test_e12_unreadable_links_with_no_marker_keep_the_session_or_pr_lane_and_disclose_it(tmp_path):
    # axis: E12; an unreadable link read left unsaid on the record, or an issue's lane call read from an unconfirmed link
    fake = Fake(meta=dict(UNREADABLE_META), issue_bodies={9: "**Lane call:** micro. one line"})
    out = rr.write(put(tmp_path, account(lane="light")), str(tmp_path), fake.readers())
    assert out["ok"], out
    body = fake.marked()[-1]["body"]
    rec = rr._parse_body(body)
    assert rec["lane"] == {"value": "light", "source": rr.SESSION, "reason": "big", "issueLinks": "unreadable"}
    assert UNREADABLE_SENTENCE in body
    pr_call = Fake(meta=dict(UNREADABLE_META, body="x\n**Lane call:** light. small\n"))
    lane = rr.build_record(account(), pr_call.readers())["lane"]
    assert (lane["value"], lane["source"], lane["issueLinks"]) == ("light", "PR lane call", "unreadable")


def test_readable_links_leave_the_lane_and_the_line_exactly_as_they_were(tmp_path):
    fake = Fake(meta={"head": HEAD, "body": "", "issues": [9]}, marker=MARKER, issue_bodies={9: "no call"})
    rec = rr.build_record(account(), fake.readers())
    assert rec["lane"] == {"value": "full", "source": "build lane marker", "reason": "big",
                           "reasonSource": rr.SESSION}
    assert UNREADABLE_SENTENCE not in rr.render(rec)


# --- I2: the history --------------------------------------------------------------------------------------------------

def _record_comment(fake, sid, n, **over):
    rec = rr.build_record(account(sessionId=sid, **over), Fake().readers())
    return {"id": n, "author": "bot", "body": rr.render(rec), "url": f"http://c/{n}"}


def _junk(n, text="not a record"):
    return {"id": n, "author": "bot", "body": f"{rr.MARKER}\n{text}", "url": f"http://c/{n}"}


def test_e13_read_history_keeps_each_unreadable_earlier_record_as_an_unreadable_entry(monkeypatch):
    # axis: E13; an earlier record that does not parse, raises or lists malformed findings dropped from the history
    fake = Fake()
    fake.comments = [_record_comment(fake, "s-0", 1), _junk(2), _junk(3, "RAISE"), _junk(4, "MALFORMED"),
                     _record_comment(fake, "s-1", 5), _record_comment(fake, "s-2", 6)]
    real = rr._parse_body

    def parse(body, by_id=None):
        if "RAISE" in body:
            raise ValueError("boom")
        if "MALFORMED" in body:
            return {"schema": rr.RECORD_SCHEMA, "findings": "x"}
        return real(body, by_id)
    monkeypatch.setattr(rr, "_parse_body", parse)
    history = rr.read_history(7, REPO, fake.readers())
    assert len(history) == 5 and [rr._is_unreadable_entry(h) for h in history] == [False, True, True, True, False]
    assert history[0]["sessionId"] == "s-0" and history[4]["sessionId"] == "s-1"
    for entry, n in zip(history[1:4], (2, 3, 4)):
        got = entry[rr.UNREADABLE_RECORD]
        assert got["url"] == f"http://c/{n}" and isinstance(got["detail"], str) and got["detail"]
    assert rr._unreadable_entry("u", "d") == {rr.UNREADABLE_RECORD: {"url": "u", "detail": "d"}}


def test_a_pr_with_zero_or_one_record_has_no_history():
    fake = Fake()
    assert rr.read_history(7, REPO, fake.readers()) == []
    fake.comments = [_record_comment(fake, "s-1", 1)]
    assert rr.read_history(7, REPO, fake.readers()) == []


def test_e14_read_history_when_the_comments_cannot_be_listed_is_one_unreadable_entry_never_empty():
    # axis: E14; a failed listing read as a PR with no earlier record
    detail = "the review record comments could not be listed"
    failed = dict(Fake().readers(), list_comments=lambda pr, repo: None)
    assert rr.read_history(7, REPO, failed) == [rr._unreadable_entry(None, detail)]

    def boom(pr, repo):
        raise RuntimeError("down")
    assert rr.read_history(7, REPO, dict(Fake().readers(), list_comments=boom)) == [rr._unreadable_entry(None, detail)]


CARRY_BASE = "c" * 40
ALLOWED = lambda *a, **k: {"read": "changed", "changedFiles": [], "why": []}  # noqa: E731


def _carried_session(tmp_path):
    """R1 (session s-1) reviewed EARLIER; R3 (session s-2) carried from it at HEAD; an unreadable record R2 sits between."""
    fake = Fake(meta={"head": EARLIER, "body": "", "issues": []})
    fake.runs["/run/code-reviewer"] = (dict(GOOD_RUN, viewHeadSha=EARLIER), None)
    readers = dict(fake.readers(), returning_decide=ALLOWED)
    first = rr.write(put(tmp_path, account(sessionId="s-1", finalCommit=EARLIER), "first.json"), str(tmp_path), readers)
    assert first["ok"], first
    fake.meta = {"head": HEAD, "body": "", "issues": []}
    carried = carried_account()
    second = rr.write(put(tmp_path, carried, "second.json"), str(tmp_path), readers)
    assert second["ok"], second
    assert rr._parse_body(fake.comments[-1]["body"])["reviewers"][0]["carried"] == {"commit": EARLIER}
    fake.comments[-1]["id"] = 3
    fake.comments.append(_junk(2))
    return fake, readers


def carried_account():
    row = reviewer(runDir=None, commit=EARLIER, carriedFrom=EARLIER)
    return account(sessionId="s-2", finalCommit=HEAD, reviewers=[row], carryBase=CARRY_BASE,
                   carriedReview={"lastReviewed": EARLIER, "why": "carried"})


def test_e15_a_same_session_rewrite_whose_intervening_record_is_unreadable_refuses_the_carry_naming_it(tmp_path):
    # axis: E15 through the record writer; the carry walk looking past an unreadable record to the older one it carried from
    fake, readers = _carried_session(tmp_path)
    out = rr.write(put(tmp_path, carried_account(), "third.json"), str(tmp_path), readers)
    assert out["ok"], out
    row = rr._parse_body(fake.comments[-1]["body"])["reviewers"][0]
    assert row["ran"] == "not-run" and "carried" not in row
    assert row["runNote"].startswith("an earlier review record could not be read (")
    assert "http://c/2" in row["runNote"] and row["runNote"].endswith("so the record this session carried from cannot be checked")


def test_e15_the_session_carry_path_refuses_with_the_reason_naming_the_unreadable_record(tmp_path):
    # axis: E15 through review_record_session; review_record_session's carry reading past an unreadable record
    fake, readers = _carried_session(tmp_path)
    acct = {"pr": 7, "sessionId": "s-2", "carryBase": CARRY_BASE, "finalCommit": HEAD}
    with pytest.raises(rs.Refusal) as e:
        rs._carry_review(acct, EARLIER, {"repo": REPO}, str(tmp_path), readers)
    assert e.value.reason == rs.UNSUPPORTED
    assert e.value.detail.startswith("an earlier review record could not be read (http://c/2")
    assert e.value.detail.endswith("so the record this session carried from cannot be checked")
    assert "carriedReview" not in acct


def test_carry_source_walks_past_a_readable_record_but_stops_at_an_unreadable_one():
    own = {"sessionId": "s-2", "finalCommit": {"sha": HEAD}, "findings": [], "reviewers": [{"carried": {"commit": EARLIER}}]}
    old = {"sessionId": "s-1", "finalCommit": {"sha": EARLIER}}
    # a same-session record whose findings list is malformed is never walked through
    assert rr.carry_source(dict(own, findings="x"), EARLIER, "s-2", [old])["sessionId"] == "s-2"
    mid = {"sessionId": "s-3", "finalCommit": {"sha": "d" * 40}}
    entry = rr._unreadable_entry("http://c/2", "gone")
    assert rr.carry_source(own, EARLIER, "s-2", [old, mid]) is old
    assert rr.carry_source(own, EARLIER, "s-2", [old, entry]) is entry
    assert rr.carry_source(own, EARLIER, "s-2", [entry, old]) is old
    assert rr.carry_refusal(entry, EARLIER, None, None, HEAD, []) == (
        "an earlier review record could not be read (gone), so the record this session carried from cannot be checked")


def test_e16_the_earlier_session_record_walk_stops_at_an_unreadable_entry():
    # axis: E16; a record older than an unreadable one taken as the earlier record of another session
    own = {"sessionId": "s-2"}
    older = {"sessionId": "s-0"}
    entry = rr._unreadable_entry("http://c/2", "gone")
    assert rr._earlier_session_record(own, [older], "s-2") is older
    assert rr._earlier_session_record(own, [older, entry], "s-2") is entry
    assert rr._earlier_session_record(entry, [older], "s-2") is entry
    assert rr._earlier_session_record(own, [entry, older], "s-2") is older


def test_an_unreadable_earlier_record_is_named_by_the_carried_recheck():
    # axis: the carried re-check reading an unreadable earlier record as one that never listed the finding
    entry = rr._unreadable_entry("http://c/2", "gone")
    f = {"id": "f-1", "outcome": rr._LEFT_FOR_OWNER, "file": "a.py", "line": 1, "title": "t"}
    check = {"key": "f-1", "settled": "fixed", "commit": EARLIER, "checkedHead": HEAD, "evidence": "fixed it"}
    found, rows = rr._recheck_carried([f], [check], HEAD, lambda c, h: True, entry)
    assert found[0]["outcome"] == rr._LEFT_FOR_OWNER
    assert "an earlier review record could not be read (gone)" in json.dumps(rows)


def test_an_unreadable_latest_record_stops_the_writers_carried_recheck(tmp_path):
    # axis: an unreadable latest record left out of the writer's history, so an older record settles a carried fix
    fake = Fake()
    older = rr.write(put(tmp_path, account(sessionId="s-1", findings=[finding("f-1", outcome=rr._LEFT_FOR_OWNER)]),
                         "a.json"), str(tmp_path), fake.readers())
    assert older["ok"], older
    fake.comments.append(_junk(99))
    check = {"key": "f-1", "settled": "fixed", "commit": EARLIER, "checkedHead": HEAD, "evidence": "fixed it"}
    out = rr.write(put(tmp_path, account(sessionId="s-2", findings=[finding("f-1", outcome=rr._LEFT_FOR_OWNER)],
                                         carriedChecks=[check]), "b.json"), str(tmp_path), fake.readers())
    assert out["ok"], out
    rec = rr._parse_body(fake.comments[-1]["body"])
    assert rec["findings"][0]["outcome"] == rr._LEFT_FOR_OWNER
    assert "an earlier review record could not be read (" in json.dumps(rec["carriedRechecks"])


@pytest.mark.parametrize("damage", [
    pytest.param({"sentHashMatches": False}, id="sent-hash"),
    pytest.param({"recordedChars": 10, "foundChars": 10, "hashMatches": False}, id="parts-hash"),
    pytest.param({"recordedChars": 10, "foundChars": 9, "hashMatches": True}, id="parts-length"),
])
def test_a_record_whose_hash_failed_is_never_carried_from(damage):
    # axis: a record whose posted text fails its recorded hash credited as carry authority
    own = {"sessionId": "s-2", "finalCommit": {"sha": HEAD}, "findings": [],
           "reviewers": [{"carried": {"commit": EARLIER}}]}
    damaged = {"sessionId": "s-1", "finalCommit": {"sha": EARLIER}, "findings": [], "transitDamage": damage}
    assert rr.carry_source(own, EARLIER, "s-2", [damaged]) is damaged
    assert rr.carry_refusal(damaged, EARLIER, None, None, HEAD, []) == (
        "the earlier record's posted text does not match the hash it recorded, so its reviewers are not carried")
    assert rr.carry_source(dict(own, transitDamage=damage), EARLIER, "s-2", [{"finalCommit": {"sha": EARLIER}}])["sessionId"] == "s-2"
    assert rr.carry_refusal(dict(damaged, transitDamage={"redactedFields": ["x"]}), EARLIER, None, None, HEAD, []) != (
        "the earlier record's posted text does not match the hash it recorded, so its reviewers are not carried")


def test_e17_a_hand_write_with_an_unattributed_finding_and_an_unreadable_older_record_is_written(tmp_path):
    # axis: E17; an unreadable entry in the history reaching the raiser derivation and raising inside the writer
    fake = Fake()
    fake.comments = [_junk(1)]
    first = rr.write(put(tmp_path, account(findings=[finding("f-0", raisedBy="code-reviewer")]), "a.json"),
                     str(tmp_path), fake.readers())
    assert first["ok"], first
    out = rr.write(put(tmp_path, account(findings=[finding("f-0", raisedBy="code-reviewer"), finding("f-1", line=9)]), "b.json"),
                   str(tmp_path), fake.readers())
    assert out["ok"], out
    rec = rr._parse_body(fake.comments[-1]["body"])
    # the unreadable record stops the derivation: the unattributed finding is not credited to the one reviewer that ran
    assert {f["id"]: f.get("raisedBy") for f in rec["findings"]} == {"f-0": "code-reviewer", "f-1": None}
    assert [n["why"] for n in rec["earlierRecordsNotChecked"]] == ["unreadable"]
