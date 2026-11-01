# plugins/superheroes/lib/tests/test_cloud_parked.py
"""Conformance: the lapsed-pass parked notice, the send-back after renewal, and the `sent` record.
Every repository, ledger, store and account file is built under tmp_path; the `gh api` answers are
a fake `run`; nothing touches the real home directory, clock or network."""
import datetime
import json
import os
import sys
import threading
from types import SimpleNamespace

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder  # noqa: E402
import cloud_check  # noqa: E402
import cloud_parked as CP  # noqa: E402
import cloud_pass  # noqa: E402
import cloud_recover  # noqa: E402
import cloud_ready as CR  # noqa: E402
import cloud_setup as CS  # noqa: E402
import control_plane  # noqa: E402
import launch_ledger as ll  # noqa: E402
import launch_place as LP  # noqa: E402
import launch_report as LR  # noqa: E402
import review_record as RR  # noqa: E402
import store_core  # noqa: E402

from test_cloud_pass import _make_with, _signin  # noqa: E402
from test_launch_ledger import _declare, _init_repo, _ledger_env, _reserved, _started  # noqa: E402

ACCOUNT = "acct-fixture-one"
SECOND_ACCOUNT = "acct-fixture-two"
ENVIRONMENT = "env-fixture-one"
STAMP = "sha256:" + "ab" * 32
TODAY = "2026-10-12"
NOW = datetime.datetime(2026, 10, 12, 12, tzinfo=datetime.timezone.utc).timestamp()
PAST = "2026-10-05"
LAUNCHED = datetime.datetime(2026, 10, 4, 12, tzinfo=datetime.timezone.utc).timestamp()  # before the park comment
RELAUNCHED = datetime.datetime(2026, 10, 10, 12, tzinfo=datetime.timezone.utc).timestamp()
EARLY = datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc).timestamp()  # a record written before any lane here started
RENEWED_AT = datetime.datetime(2026, 10, 8, 12, tzinfo=datetime.timezone.utc).timestamp()  # after LAUNCHED, before RELAUNCHED
FUTURE = "2026-12-01"
REPO = "owner/name"
BATCH = "b-parked"
RENEW_WORDS = ("renew", "fresh pass", "new pass")


class Gh:
    """Fake `gh api`: answers keyed by the endpoint; comments are served 100 a page, by page number."""

    def __init__(self):
        self.comments, self.pulls, self.broken, self.calls = {}, {}, set(), []
        self.comment_reads, self.comments_fail_from = 0, None

    def __call__(self, argv, **_kw):
        self.calls.append(tuple(argv))
        assert "--paginate" not in argv, argv
        path, _, page = argv[-1].partition("?per_page=100&page=")
        if path in self.broken:
            return SimpleNamespace(returncode=1, stdout="")
        if path in self.broken_json:
            return SimpleNamespace(returncode=0, stdout="not json")
        parts = path.split("/")
        number = int(parts[4])
        if parts[3] == "issues":
            assert page.isdigit(), argv
            self.comment_reads += 1
            if self.comments_fail_from is not None and self.comment_reads >= self.comments_fail_from:
                return SimpleNamespace(returncode=1, stdout="")
            rows = self.comments.get(number, [])
            return SimpleNamespace(returncode=0, stdout=json.dumps(rows[(int(page) - 1) * 100:int(page) * 100]))
        return SimpleNamespace(returncode=0, stdout=json.dumps(self.pulls[number]))

    broken_json = frozenset()

    def pull_calls(self):
        return [c for c in self.calls if "/pulls/" in c[-1]]


def _comments_path(pr):
    return "repos/%s/issues/%d/comments" % (REPO, pr)


def _pull_path(pr):
    return "repos/%s/pulls/%d" % (REPO, pr)


def _lapsed_comment(pr, created_at="2026-10-05T10:00:00Z", cid=None):
    comment = {"id": 900 + pr if cid is None else cid, "body": cloud_builder.REVIEW_LAPSED_TEXT}
    if created_at is not None:
        comment["created_at"] = created_at
    return comment


def _record_comment(pr, missing, sha="h1", status=None):
    rec = {"schema": RR.RECORD_SCHEMA, "pr": pr, "missingReviews": missing, "finalCommit": {"sha": sha},
           "parked": any(m["goAhead"] is None for m in missing), **({"status": status} if status is not None else {})}
    return {"id": 500 + pr, "body": RR.MARKER + "\n<details>\n\n```json\n" + json.dumps(rec) + "\n```\n</details>\n"}


def _pull(issue=None, state="open", merged=False):
    body = "Closes #%d\n\nthe work" % issue if issue else "the work"
    return {"state": state, "merged": merged, "body": body, "head": {"sha": "h1"}}


def _account_file(directory, account):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": account}}), encoding="utf-8")


def _written_at(repo, store, account, when):
    """Set the setup record's modification time: the renewal time the send-back reads off it."""
    os.utime(CS.record_path(repo, account, store), (when, when))


def _setup_record(repo, store, account, lapses, written_at=EARLY):
    got = CS.record_check(
        repo, root=store, account=account, environment=ENVIRONMENT, plugin_version="1.2.3",
        picks_up_version=False, calibration_stamp=STAMP, calibration_date="2026-10-01",
        pass_lapses=lapses, checked_at="2026-10-01")
    assert got["action"] == "written", got
    _written_at(repo, store, account, written_at)


@pytest.fixture
def w(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    root = _ledger_env(tmp_path, monkeypatch)
    store = str(tmp_path / "store")
    monkeypatch.setattr(control_plane, "store_root", lambda: store)
    home = tmp_path / "home"
    _account_file(home, ACCOUNT)
    env = {"HOME": str(home), "PATH": os.environ["PATH"], ll.LEDGER_ROOT_ENV: root}
    _setup_record(repo, store, ACCOUNT, PAST)
    gh = Gh()
    assert _declare(repo, BATCH, 4, env=env)["ok"]
    return SimpleNamespace(repo=repo, store=store, env=env, gh=gh, home=home, root=tmp_path)


def _notice(w, pr, today=TODAY):
    return CP.notice(w.repo, REPO, pr, today, env=w.env, run=w.gh)


def _send(w, today=TODAY):
    return CP.send_back(w.repo, today, env=w.env, run=w.gh)


def _park_id(w, pr):
    return next((e.get("parkId") for e in _entries(w) if e["pr"] == pr), None)


def _sent(w, pr, repo=REPO):
    return CP.sent(w.repo, repo, pr, park_id=_park_id(w, pr), env=w.env)


def _park(w, pr, issue=None, **pull):
    w.gh.comments[pr] = [_lapsed_comment(pr)]
    w.gh.pulls[pr] = _pull(issue, **pull)
    out = _notice(w, pr)
    assert out["kind"] == "lapsed-pass", out
    return out


def _renew(w, account=ACCOUNT, date=FUTURE, written_at=EARLY):
    """A renewal the way a cloud session confirms it: through the pass module's own recorder. The record is
    stamped `written_at` (default before every lane here started) so the renewal time is the test's, not the clock's."""
    confirmation = {"schema": cloud_pass.CONFIRMATION_SCHEMA, "reviewerAnswered": True,
                    "passLapses": date, "reason": None}
    got = cloud_pass.record_confirmation(
        w.repo, confirmation, account=account, environment=ENVIRONMENT, now=NOW, root=w.store, env=w.env)
    assert got["action"] == "written", got
    _written_at(w.repo, w.store, account, written_at)


def _lane(w, launch_id, issue, session, surface, finished=False, config_dir=None, ts=LAUNCHED, account_id=None,
          started_ts=None):
    extra = {"ts": ts} if config_dir is None else {"ts": ts, "configDir": config_dir}
    if account_id is not None:
        extra["accountId"] = account_id
    rec = _reserved(launch_id, BATCH, [surface], w.repo, issue=issue, place="cloud",
                    cloudEnvironment=ENVIRONMENT, pluginVersion="1.2.3", **extra)
    assert ll.reserve(w.repo, rec, env=w.env)["ok"]
    if session is not None:
        started = _started(launch_id)
        started["ts"] = ts if started_ts is None else started_ts  # the session starts when the lane was reserved, unless told
        started.update(cloudSessionName=session, cloudSessionId="session_01AbCdEf123")
        assert ll.append_under_lock(w.repo, started, env=w.env)["ok"]
    if finished:
        assert ll.terminalize(w.repo, launch_id, child_ever_spawned=True, outcome="park", evidence="x",
                              env=w.env)["ok"]


def _state_file(w):
    return os.path.join(os.path.dirname(ll.ledger_path(w.repo, w.env)["path"]), CP.STATE_NAME)


def _entries(w):
    with open(_state_file(w), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- the notice


def test_notice_for_a_lapsed_pass_park_names_the_pr_the_reason_and_the_renewal(w):
    _lane(w, "l-42", 101, "session-42", "a")
    w.gh.comments[42] = [{"id": 1, "body": "hello"}, _lapsed_comment(42)]
    w.gh.pulls[42] = _pull(101)
    out = _notice(w, 42)
    assert out == {"ok": True, "kind": "lapsed-pass", "pr": 42, "text": CP.NOTICE_TEXT % 42}
    assert out["text"].startswith("#42 is parked.") and "lapsed" in out["text"] and "Renew the pass" in out["text"]
    assert _entries(w) == [{"repo": REPO, "pr": 42, "parkedOn": "2026-10-05", "outcome": None,
                            "launchId": "l-42", "parkId": 942}]


def test_a_pr_whose_review_did_not_run_for_another_reason_gets_no_renewal_words(w):
    w.gh.comments[43] = [_record_comment(43, [{"name": "codex", "goAhead": None}])]
    out = _notice(w, 43)
    assert out == {"ok": True, "kind": "not-lapsed-pass", "pr": 43, "text": None}
    assert not any(word in json.dumps(out).lower() for word in RENEW_WORDS)
    assert not os.path.exists(_state_file(w))


def test_the_park_day_is_the_newest_lapsed_comments_day_in_utc(w):
    w.gh.comments[10] = [_lapsed_comment(10, "2026-09-30T08:00:00Z"),
                         {"id": 3, "body": "later chatter", "created_at": "2026-10-09T08:00:00Z"},
                         _lapsed_comment(10, "2026-10-06T23:30:00-05:00")]
    w.gh.pulls[10] = _pull()
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert [e["parkedOn"] for e in _entries(w)] == ["2026-10-07"]


def test_noticing_a_recorded_pr_again_keeps_its_first_park_day(w):
    _park(w, 10)
    w.gh.comments[10] = [_lapsed_comment(10, "2026-10-09T10:00:00Z")]
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert _entries(w) == [{"repo": REPO, "pr": 10, "parkedOn": PAST, "outcome": None, "launchId": None, "parkId": 910}]


def test_a_park_comment_without_a_readable_date_refuses_the_notice_and_writes_nothing(w):
    for created_at in (None, "", "yesterday", "2026-10-05", "2026-10-05T10:00:00", 20261005, "2026-13-05T10:00:00Z"):
        w.gh.comments[10] = [_lapsed_comment(10, created_at)]
        assert _notice(w, 10) == {"ok": False, "reason": "park-date-unreadable"}
    assert not os.path.exists(_state_file(w))


# ---------------------------------------------------------------- send-back after a renewal


def test_after_a_confirmed_renewal_the_open_parked_pr_goes_back_with_its_lanes_session(w):
    _lane(w, "l-older", 101, "older-session", "a", finished=True)
    _lane(w, "l-newer", 101, "newer-session", "a2")
    _lane(w, "l-other", 202, "other-session", "b")
    _park(w, 10, issue=101)
    _renew(w)
    out = _send(w)
    assert out == {"ok": True, "skipped": [], "unread": [], "notRenewed": [], "noLane": [], "superseded": [], "uncertain": [],
                   "adopt": [], "adopting": [], "sendBack": [{
        "pr": 10, "repo": REPO, "issue": 101, "launchId": "l-newer", "cloudSessionName": "newer-session",
        "parkId": 910, "configDir": None, "message": CP.SEND_BACK_MESSAGE}]}
    assert _entries(w)[0]["outcome"] is None


def test_a_later_launch_for_the_same_issue_never_receives_the_original_prs_review(w):
    _lane(w, "l-orig", 101, "orig-session", "a")
    _park(w, 10, issue=101)
    assert _entries(w)[0]["launchId"] == "l-orig"
    assert ll.terminalize(w.repo, "l-orig", child_ever_spawned=True, outcome="park", evidence="x", env=w.env)["ok"]
    _lane(w, "l-later", 101, "later-session", "a2")
    _renew(w)
    out = _send(w)
    assert [s["cloudSessionName"] for s in out["sendBack"]] == ["orig-session"]
    assert out["sendBack"][0]["launchId"] == "l-orig"


def test_a_later_park_of_a_sent_back_pr_keeps_its_original_lane_and_a_newer_comment_rearms_it(w):
    _lane(w, "l-orig", 101, "orig-session", "a")
    _park(w, 10, issue=101)
    assert ll.terminalize(w.repo, "l-orig", child_ever_spawned=True, outcome="park", evidence="x", env=w.env)["ok"]
    _lane(w, "l-later", 101, "later-session", "a2", ts=RELAUNCHED)
    _renew(w)
    assert [s["cloudSessionName"] for s in _send(w)["sendBack"]] == ["orig-session"]
    assert _sent(w, 10)["ok"]
    assert _send(w)["sendBack"] == []
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    entry = _entries(w)[0]
    assert entry["outcome"] is None and entry["parkedOn"] == "2026-10-11" and entry["launchId"] == "l-orig"
    out = _send(w)["sendBack"]
    assert [s["cloudSessionName"] for s in out] == ["orig-session"]


def test_a_second_park_on_the_same_day_rearms_a_sent_back_pr_but_rereading_one_comment_does_not(w):
    _lane(w, "l-orig", 101, "orig-session", "a")
    w.gh.comments[10] = [_lapsed_comment(10, created_at="2026-10-05T10:00:00Z", cid=1)]
    w.gh.pulls[10] = _pull(101)
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    _renew(w)
    assert _sent(w, 10)["ok"]
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert _entries(w)[0]["outcome"] == "sent-back"
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-05T14:00:00Z", cid=2))
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    entry = _entries(w)[0]
    assert entry["outcome"] is None and entry["parkId"] == 2 and entry["launchId"] == "l-orig"


# axis: a newer park re-arms whatever the stored outcome, and a resolved park that is not newer gets no renewal text — see bite-proof record c8a_wo4.md
@pytest.mark.parametrize("outcome", [None, "sent-back", CP.UNCERTAIN, "owner-let-through", "closed"])
@pytest.mark.parametrize("newer", [False, True])
def test_the_notice_by_stored_outcome_and_whether_the_park_is_newer(w, outcome, newer):
    _park(w, 10)
    entries = _entries(w)
    entries[0]["outcome"] = outcome
    with open(_state_file(w), "w", encoding="utf-8") as fh:
        json.dump(entries, fh)
    if newer:
        w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    out = _notice(w, 10)
    saved = _entries(w)[0]
    if newer:
        assert out == {"ok": True, "kind": "lapsed-pass", "pr": 10, "text": CP.NOTICE_TEXT % 10}
        assert saved["outcome"] is None and saved["parkId"] == 1010 and saved["parkedOn"] == "2026-10-11"
    elif outcome in ("closed", "owner-let-through"):
        assert out == {"ok": True, "kind": "park-resolved", "pr": 10, "text": None}
        assert saved["outcome"] == outcome and saved["parkId"] == 910
    else:
        assert out == {"ok": True, "kind": "lapsed-pass", "pr": 10, "text": CP.NOTICE_TEXT % 10}
        assert saved["outcome"] == outcome and saved["parkId"] == 910


def test_a_go_ahead_recorded_for_an_earlier_head_does_not_let_the_current_head_through(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    w.gh.comments[10].append(_record_comment(10, [{"name": "codex", "goAhead": {"kind": "owner-words"}}], sha="old"))
    _renew(w)
    out = _send(w)
    assert out["skipped"] == [] and [s["pr"] for s in out["sendBack"]] == [10]
    assert _entries(w)[0]["outcome"] is None


def test_a_first_notice_after_a_later_launch_still_finds_the_original_prs_lane(w):
    _lane(w, "l-orig", 101, "orig-session", "a", finished=True)
    _lane(w, "l-later", 101, "later-session", "a2", ts=RELAUNCHED)
    _park(w, 10, issue=101)
    assert _entries(w)[0]["launchId"] == "l-orig"
    _renew(w)
    assert [s["cloudSessionName"] for s in _send(w)["sendBack"]] == ["orig-session"]


def test_a_first_notice_with_only_a_launch_made_after_the_park_lists_the_pr_under_no_lane(w):
    _lane(w, "l-later", 101, "later-session", "a", ts=RELAUNCHED)
    _park(w, 10, issue=101)
    assert _entries(w)[0]["launchId"] is None
    _renew(w)
    out = _send(w)
    assert out["sendBack"] == [] and out["noLane"] == [{"pr": 10, "issue": 101}]


def test_a_failed_reviewer_check_after_the_renewal_keeps_the_pr_unrenewed(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    marker = cloud_check.failed_check_path(w.repo, ACCOUNT, w.store)
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write("not json")
    out = _send(w)
    assert out["sendBack"] == [] and out["notRenewed"] == [10]


def test_a_parked_pr_whose_original_launch_is_unknown_is_reported_not_given_another_lane(w):
    _park(w, 10, issue=101)
    assert _entries(w)[0]["launchId"] is None
    _lane(w, "l-later", 101, "later-session", "a")
    _renew(w)
    out = _send(w)
    assert out["sendBack"] == [] and out["noLane"] == [{"pr": 10, "issue": 101}]


def test_comments_are_read_page_by_number_so_later_pages_count(w):
    _lane(w, "l-a", 101, "session-a", "a")
    w.gh.comments[10] = [{"id": n, "body": "chatter"} for n in range(1, 101)] + [_lapsed_comment(10)]
    w.gh.pulls[10] = _pull(101)
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    asked = [c[-1] for c in w.gh.calls if "/comments" in c[-1]]
    assert asked[:2] == [_comments_path(10) + "?per_page=100&page=%d" % n for n in (1, 2)]
    assert not any("--paginate" in c for c in w.gh.calls)
    w.gh.comments[11] = [{"id": 1, "body": "chatter"}, {"id": 2, "body": "chatter"}]
    assert _notice(w, 11)["kind"] == "not-lapsed-pass"


# axis: an owner go-ahead past the first comment page; a read that stops at page 1 sends the PR back
def test_an_owner_go_ahead_on_a_later_comment_page_is_still_seen(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    w.gh.comments[10] += [{"id": 1000 + n, "body": "chatter"} for n in range(100)]
    w.gh.comments[10].append(_record_comment(10, [{"name": "codex", "goAhead": {"kind": "owner-words"}}]))
    _renew(w)
    w.gh.calls.clear()
    assert _send(w)["skipped"] == [{"pr": 10, "outcome": "owner-let-through"}]
    assert _comments_path(10) + "?per_page=100&page=2" in [c[-1] for c in w.gh.calls]


def test_a_parked_pr_closed_or_merged_before_the_renewal_is_not_sent_back(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _lane(w, "l-b", 102, "session-b", "b")
    _park(w, 10, issue=101, state="closed")
    _park(w, 11, issue=102, state="open", merged=True)
    _renew(w)
    out = _send(w)
    assert out["sendBack"] == []
    assert out["skipped"] == [{"pr": 10, "outcome": "closed"}, {"pr": 11, "outcome": "closed"}]
    assert [e["outcome"] for e in _entries(w)] == ["closed", "closed"]


def test_a_parked_pr_the_owner_let_through_is_not_sent_back(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _lane(w, "l-b", 102, "session-b", "b")
    _park(w, 10, issue=101)
    w.gh.comments[10].append(_record_comment(10, [{"name": "codex", "goAhead": {"kind": "owner-words"}}]))
    _park(w, 11, issue=102)
    w.gh.comments[11].append(_record_comment(
        11, [{"name": "codex", "goAhead": {"kind": "owner-words"}}, {"name": "claude", "goAhead": None}]))
    _renew(w)
    out = _send(w)
    assert out["skipped"] == [{"pr": 10, "outcome": "owner-let-through"}]
    assert [s["pr"] for s in out["sendBack"]] == [11]
    assert [e["outcome"] for e in _entries(w)] == ["owner-let-through", None]


def test_a_record_reading_awaits_owner_is_let_through_or_sent_back_exactly_as_not_reviewed(w):
    # axis: the let-through check reads no status; an awaits-owner record treated differently from a not-reviewed one
    go = {"name": "codex", "goAhead": {"kind": "owner-words"}}
    for n, (launch, issue, surface) in enumerate([("l-a", 101, "a"), ("l-b", 102, "b"), ("l-c", 103, "c"), ("l-d", 104, "d")]):
        _lane(w, launch, issue, f"session-{surface}", surface)
        _park(w, 10 + n, issue=issue)
    for pr, missing, status in [(10, [go], "awaits-owner"), (11, [go], "not-reviewed"),
                                (12, [go, {"name": "claude", "goAhead": None}], "awaits-owner"),
                                (13, [go, {"name": "claude", "goAhead": None}], "not-reviewed")]:
        w.gh.comments[pr].append(_record_comment(pr, missing, status=status))
    _renew(w)
    out = _send(w)
    assert out["skipped"] == [{"pr": 10, "outcome": "owner-let-through"}, {"pr": 11, "outcome": "owner-let-through"}]
    assert [s["pr"] for s in out["sendBack"]] == [12, 13]
    assert [e["outcome"] for e in _entries(w)] == ["owner-let-through", "owner-let-through", None, None]


def test_a_pr_already_reviewed_on_its_current_head_is_not_sent_back(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    w.gh.comments[10].append(_record_comment(10, []))
    _renew(w)
    out = _send(w)
    assert out["sendBack"] == [] and out["skipped"] == [{"pr": 10, "outcome": "owner-let-through"}]


def test_a_later_park_on_a_new_head_rearms_a_pr_the_owner_let_through(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    w.gh.comments[10].append(_record_comment(10, [{"name": "codex", "goAhead": {"kind": "owner-words"}}]))
    _renew(w)
    assert _send(w)["skipped"] == [{"pr": 10, "outcome": "owner-let-through"}]
    w.gh.pulls[10]["head"]["sha"] = "h2"
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert _entries(w)[0]["outcome"] is None
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]


def test_a_review_record_that_cannot_be_parsed_does_not_count_as_a_let_through(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    w.gh.comments[10].append({"id": 7, "body": RR.MARKER + "\nnot a record"})
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]


def test_a_pass_the_pass_command_made_but_no_cloud_session_confirmed_sends_nothing_back(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    result, copied = _make_with(w.root, _signin(), env=dict(w.env))
    assert result["action"] == "copied" and len(copied) == 1
    assert os.path.isfile(os.path.join(str(w.home), ".codex-cloud", "auth.json"))
    out = _send(w)
    assert out["sendBack"] == [] and out["skipped"] == [] and out["notRenewed"] == [10]
    assert _entries(w)[0]["outcome"] is None


def test_a_renewal_confirmed_before_the_park_was_noticed_still_sends_the_pr_back(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _renew(w)
    _park(w, 10, issue=101)
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]


def test_a_pass_lapsing_no_later_than_the_park_day_is_not_a_renewal(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    assert _send(w, PAST)["notRenewed"] == [10]
    assert [s["pr"] for s in _send(w, PAST)["sendBack"]] == []
    _setup_record(w.repo, w.store, ACCOUNT, "2026-10-06")
    assert [s["pr"] for s in _send(w, PAST)["sendBack"]] == [10]


def test_a_pass_that_already_lapsed_is_not_a_renewal_but_one_lapsing_today_is(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _setup_record(w.repo, w.store, ACCOUNT, "2026-10-11")
    assert _send(w)["notRenewed"] == [10]
    _setup_record(w.repo, w.store, ACCOUNT, TODAY)
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]


def test_a_missing_unreadable_or_unresolvable_setup_record_renews_nothing(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    path = CS.record_path(w.repo, ACCOUNT, w.store)
    saved = open(path, encoding="utf-8").read()
    os.unlink(path)
    assert _send(w)["notRenewed"] == [10]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(saved.replace(FUTURE, "next-tuesday"))
    assert _send(w)["notRenewed"] == [10]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(saved)
    _written_at(w.repo, w.store, ACCOUNT, EARLY)  # the rewrite stamped the clock; keep the renewal before the lane
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]
    os.unlink(str(w.home / ".claude.json"))
    out = _send(w)
    assert out["sendBack"] == [] and out["notRenewed"] == [10]
    assert _entries(w)[0]["outcome"] is None


def test_only_a_renewal_of_the_lanes_own_account_releases_the_pr(w):
    second = w.root / "second-config"
    _account_file(second, SECOND_ACCOUNT)
    _setup_record(w.repo, w.store, SECOND_ACCOUNT, PAST)
    _lane(w, "l-second", 101, "second-session", "a", config_dir=str(second))
    _park(w, 10, issue=101)
    _renew(w, account=ACCOUNT)
    out = _send(w)
    assert out["sendBack"] == [] and out["notRenewed"] == [10]
    _renew(w, account=SECOND_ACCOUNT)
    out = _send(w)
    assert out["notRenewed"] == []
    assert [(s["pr"], s["cloudSessionName"], s["configDir"]) for s in out["sendBack"]] == [
        (10, "second-session", str(second))]


def test_a_renewal_of_the_lanes_account_alone_is_enough_when_the_advisors_pass_is_stale(w):
    second = w.root / "second-config"
    _account_file(second, SECOND_ACCOUNT)
    _setup_record(w.repo, w.store, SECOND_ACCOUNT, PAST)
    _lane(w, "l-second", 101, "second-session", "a", config_dir=str(second))
    _park(w, 10, issue=101)
    _renew(w, account=SECOND_ACCOUNT)
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]


def test_a_lane_with_its_account_id_is_renewed_when_the_advisor_runs_under_an_explicit_default_config_dir(w):
    # axis: the lane's recorded account id decides, not a comparison of config paths — see bite-proof record c8a_wo4.md
    explicit = dict(w.env, CLAUDE_CONFIG_DIR=str(w.home / ".claude"))
    _lane(w, "l-a", 101, "session-a", "a", account_id=ACCOUNT)
    _park(w, 10, issue=101)
    _renew(w)
    out = CP.send_back(w.repo, TODAY, env=explicit, run=w.gh)
    assert out["notRenewed"] == [] and [s["pr"] for s in out["sendBack"]] == [10]


def test_a_legacy_lane_without_an_account_id_keeps_the_config_path_logic(w):
    explicit = dict(w.env, CLAUDE_CONFIG_DIR=str(w.home / ".claude"))
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    assert CP.send_back(w.repo, TODAY, env=explicit, run=w.gh)["notRenewed"] == [10]  # the explicit root reads no account
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]  # the same lane under the plain env is renewed


def test_a_lane_with_an_account_id_is_released_only_by_that_accounts_renewal(w):
    _setup_record(w.repo, w.store, SECOND_ACCOUNT, PAST)
    _lane(w, "l-second", 101, "second-session", "a", account_id=SECOND_ACCOUNT)
    _park(w, 10, issue=101)
    _renew(w, account=ACCOUNT)  # the advisor's own account is renewed; the lane's is not
    out = _send(w)
    assert out["sendBack"] == [] and out["notRenewed"] == [10]
    _renew(w, account=SECOND_ACCOUNT)
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]


@pytest.mark.parametrize("lane_config_dir, lane_account", [(None, ACCOUNT), ("default", None)])
def test_a_default_account_lane_is_decided_by_its_own_record_when_the_advisors_pass_is_stale(
        w, lane_config_dir, lane_account):
    second = w.root / "advisor-config"
    _account_file(second, SECOND_ACCOUNT)
    _setup_record(w.repo, w.store, SECOND_ACCOUNT, PAST)  # the advisor's override account: stale
    advisor = dict(w.env, CLAUDE_CONFIG_DIR=str(second))
    config_dir = str(w.home / ".claude") if lane_config_dir == "default" else None
    _lane(w, "l-a", 101, "session-a", "a", config_dir=config_dir, account_id=lane_account)
    _park(w, 10, issue=101)
    assert CP.send_back(w.repo, TODAY, env=advisor, run=w.gh)["notRenewed"] == [10]
    _renew(w, account=ACCOUNT)  # the lane's own (default) account is renewed
    out = CP.send_back(w.repo, TODAY, env=advisor, run=w.gh)
    assert out["notRenewed"] == [] and [s["pr"] for s in out["sendBack"]] == [10]


def test_a_readable_failed_check_marker_keeps_the_pr_unrenewed(w):
    # axis: a well-formed failed-check marker counts as present, not only a damaged one — see bite-proof record c8a_wo4.md
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    marker = cloud_check.failed_check_path(w.repo, ACCOUNT, w.store)
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, "w", encoding="utf-8") as fh:
        json.dump({"schema": cloud_check.FAILED_CHECK_SCHEMA, "account": ACCOUNT, "environment": ENVIRONMENT,
                   "failedAt": "2026-10-12T09:00:00Z", "failedParts": ["pass"]}, fh)
    assert cloud_check.read_failed_check(w.repo, ACCOUNT, w.store).get("damaged") is None
    assert CP._lapses(w.repo, w.env, None, ENVIRONMENT) is None
    out = _send(w)
    assert out["sendBack"] == [] and out["notRenewed"] == [10]


def test_a_due_pr_with_no_cloud_lane_is_reported_and_stays_undecided(w):
    _lane(w, "l-other", 202, "other-session", "b")
    _park(w, 10, issue=101)
    _park(w, 11, issue=None)
    _renew(w)
    out = _send(w)
    assert out["sendBack"] == []
    assert out["noLane"] == [{"pr": 10, "issue": 101}, {"pr": 11, "issue": None}]
    assert [e["outcome"] for e in _entries(w)] == [None, None]


def test_a_due_pr_whose_lane_has_no_session_is_reported_as_having_no_lane(w):
    _lane(w, "l-unstarted", 101, None, "a")
    _park(w, 10, issue=101)
    _renew(w)
    out = _send(w)
    assert out["sendBack"] == [] and out["noLane"] == [{"pr": 10, "issue": 101}]


def test_a_pr_not_yet_renewed_is_not_judged_a_no_lane_pr(w):
    _park(w, 10, issue=101)
    out = _send(w)
    assert out["noLane"] == [] and out["notRenewed"] == [10]


# ---------------------------------------------------------------- recording a delivery


def test_a_pr_stays_listed_until_it_is_recorded_as_sent_and_never_after(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]
    assert _entries(w)[0]["outcome"] is None
    assert _sent(w, 10) == {"ok": True, "action": "written"}
    assert _entries(w) == [{"repo": REPO, "pr": 10, "parkedOn": PAST, "outcome": "sent-back", "launchId": "l-a", "parkId": 910}]
    calls = len(w.gh.calls)
    again = _send(w)
    assert again["sendBack"] == [] and again["skipped"] == [] and again["notRenewed"] == []
    assert len(w.gh.calls) == calls
    assert _sent(w, 10) == {"ok": True, "action": "unchanged"}
    assert _entries(w)[0]["outcome"] == "sent-back"


def test_recording_a_pr_that_was_never_parked_is_refused(w):
    _park(w, 10)
    assert _sent(w, 99) == {"ok": False, "reason": "not-parked"}
    assert CP.sent(w.repo, "other/repo", 10, env=w.env) == {"ok": False, "reason": "not-parked"}
    assert [e["outcome"] for e in _entries(w)] == [None]


def test_recording_a_pr_already_closed_or_let_through_is_refused(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _lane(w, "l-b", 102, "session-b", "b")
    _park(w, 10, issue=101, state="closed")
    _park(w, 11, issue=102)
    w.gh.comments[11].append(_record_comment(11, [{"name": "codex", "goAhead": {"kind": "owner-words"}}]))
    _renew(w)
    _send(w)
    assert [e["outcome"] for e in _entries(w)] == ["closed", "owner-let-through"]
    assert _sent(w, 10) == {"ok": False, "reason": "already-decided"}
    assert _sent(w, 11) == {"ok": False, "reason": "already-decided"}
    assert [e["outcome"] for e in _entries(w)] == ["closed", "owner-let-through"]


def test_a_closed_pr_is_decided_once_and_not_read_again(w):
    _park(w, 10, issue=101, state="closed")
    _renew(w)
    assert _send(w)["skipped"] == [{"pr": 10, "outcome": "closed"}]
    calls = len(w.gh.calls)
    again = _send(w)
    assert again["sendBack"] == [] and again["skipped"] == [] and again["notRenewed"] == []
    assert len(w.gh.calls) == calls


# ---------------------------------------------------------------- what could not be read


def test_an_unreadable_comments_read_refuses_the_notice(w):
    w.gh.comments[10] = [_lapsed_comment(10)]
    w.gh.broken.add(_comments_path(10))
    assert _notice(w, 10) == {"ok": False, "reason": "pr-read-failed"}
    w.gh.broken.clear()
    w.gh.broken_json = frozenset([_comments_path(10)])
    assert _notice(w, 10) == {"ok": False, "reason": "pr-read-failed"}
    assert not os.path.exists(_state_file(w))


def test_an_unreadable_pr_stays_undecided_and_is_never_sent_back_or_closed(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    w.gh.broken.add(_pull_path(10))
    out = _send(w)
    assert out["unread"] == [{"pr": 10, "reason": "pr-read-failed"}]
    assert out["sendBack"] == [] and out["skipped"] == []
    assert _entries(w)[0]["outcome"] is None
    w.gh.broken.clear()
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]


def test_a_review_record_read_that_fails_leaves_the_pr_unread_and_undecided(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    w.gh.comments_fail_from = w.gh.comment_reads + 1
    out = _send(w)
    assert out["unread"] == [{"pr": 10, "reason": "review-record-read-failed"}]
    assert out["sendBack"] == [] and out["skipped"] == [] and out["noLane"] == []
    assert _entries(w)[0]["outcome"] is None
    w.gh.comments_fail_from = None
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]


def test_an_unreadable_state_file_refuses_every_verb_and_is_never_overwritten(w):
    _park(w, 10, issue=101)
    good = {"repo": REPO, "pr": 10, "parkedOn": PAST, "outcome": None}
    old_shape = {"repo": REPO, "pr": 10, "parkedCommentId": 910, "parkedAt": "2026-10-05T10:00:00Z",
                 "lapseSeen": PAST, "noticedAt": TODAY, "outcome": None}
    for bad in ("{not json", json.dumps({"entries": []}), json.dumps([{"pr": 10}]), json.dumps([old_shape]),
                json.dumps([dict(good, parkedOn="last week")]), json.dumps([dict(good, outcome="done")]),
                json.dumps([dict(good, extra=1)])):
        with open(_state_file(w), "w", encoding="utf-8") as fh:
            fh.write(bad)
        w.gh.comments[11] = [_lapsed_comment(11)]
        assert _notice(w, 11) == {"ok": False, "reason": "parked-state-unreadable"}
        assert _send(w) == {"ok": False, "reason": "parked-state-unreadable"}
        assert CP.sent(w.repo, REPO, 10, env=w.env) == {"ok": False, "reason": "parked-state-unreadable"}
        assert open(_state_file(w), encoding="utf-8").read() == bad


def test_a_state_file_that_cannot_be_written_refuses_and_decides_nothing(w, monkeypatch):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _park(w, 11, issue=102, state="closed")
    _renew(w)
    before = open(_state_file(w), encoding="utf-8").read()

    def broken(path, text):
        raise OSError("disk full")

    monkeypatch.setattr(store_core, "atomic_write", broken)
    w.gh.comments[12] = [_lapsed_comment(12)]
    w.gh.pulls[12] = _pull(101)
    assert _notice(w, 12) == {"ok": False, "reason": "parked-state-unwritable"}
    assert _sent(w, 10) == {"ok": False, "reason": "parked-state-unwritable"}
    assert _send(w) == {"ok": False, "reason": "parked-state-unwritable"}
    assert open(_state_file(w), encoding="utf-8").read() == before


def test_a_malformed_today_pr_or_repo_is_refused(w):
    for today in ("2026-13-01", "20261012", "tomorrow", ""):
        assert _notice(w, 10, today) == {"ok": False, "reason": "today-invalid"}
        assert _send(w, today) == {"ok": False, "reason": "today-invalid"}
    for pr in (0, -3, "abc", "04", True, 1.5, None):
        assert CP.notice(w.repo, REPO, pr, TODAY, env=w.env, run=w.gh) == {"ok": False, "reason": "pr-invalid"}
        assert CP.sent(w.repo, REPO, pr, env=w.env) == {"ok": False, "reason": "pr-invalid"}
    for repo in ("owner", "owner/", "a b/c", "../x", None):
        assert CP.notice(w.repo, repo, 10, TODAY, env=w.env, run=w.gh) == {"ok": False, "reason": "repo-invalid"}
        assert CP.sent(w.repo, repo, 10, env=w.env) == {"ok": False, "reason": "repo-invalid"}
    assert w.gh.calls == []


def test_the_cli_prints_one_json_object_and_exits_one_on_a_refusal(w, capsys):
    assert CP.main(["notice", "--repo-root", w.repo, "--repo", REPO, "--pr", "zero"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "pr-invalid"}
    assert CP.main(["sent", "--repo-root", w.repo, "--repo", REPO, "--pr", "zero"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "pr-invalid"}
    assert CP.main(["sent", "--repo-root", w.repo, "--repo", REPO, "--pr", "10"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "not-parked"}
    assert CP.main(["send-back"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "usage"}
    assert CP.main(["send-back", "--repo-root", w.repo, "--today", TODAY]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "usage"}
    assert CP.main(["notice", "--repo-root", w.repo, "--repo", REPO, "--pr", "10", "--today", TODAY]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "usage"}


# ---------------------------------------------------------------- what the owner hears


def _readiness(reason=None):
    def readiness(cwd, reported=None, root=None, env=None):
        conditions = {name: CR.REASON_FOR[name] != reason for name in CR.CONDITION_ORDER}
        return {"ready": reason is None, "reason": reason, "conditions": conditions, "setting": True,
                "account": ACCOUNT, "environment": ENVIRONMENT, "cloudVersion": "1.2.3",
                "advisorVersion": "1.2.3", "picksUpVersion": False, "checkedAt": None}
    return readiness


def test_with_a_lapsed_pass_the_owner_hears_it_on_the_report_the_still_line_and_the_parked_notice(w):
    def route(readiness_fn):
        return LP.route(w.repo, {}, None, readiness_fn=readiness_fn, needs_fn=lambda cwd, premise, root=None: [],
                        root=w.store, env=w.env)

    lapsed, ready = route(_readiness("pass-lapsed")), route(_readiness())
    assert (lapsed["place"], lapsed["reason"], ready["place"]) == ("local", "pass-lapsed", "cloud")
    report = LR.render_report([{"issue": 1, "title": "Ready one", "placeCall": ready},
                               {"issue": 2, "title": "Lapsed one", "placeCall": lapsed}])
    reserved = _reserved("l-lapsed", BATCH, ["x"], w.repo, issue=2, premise={"placeCall": lapsed})
    assert ll.reserve(w.repo, reserved, env=w.env)["ok"]
    assert ll.append_under_lock(w.repo, _started("l-lapsed"), env=w.env)["ok"]
    still = LR.still_line(w.repo, root=w.store, readiness_fn=_readiness("pass-lapsed"))
    parked = _park(w, 10, issue=2)["text"]
    words = LP.REASONS["pass-lapsed"]["words"]
    assert words in report
    assert still.startswith("Still on your machine") and words in still
    assert parked.startswith("#10 is parked.") and "Renew the pass" in parked


# ---------------------------------------------------------------- review-round fixes


def test_a_pr_whose_closing_line_uses_another_accepted_form_still_finds_its_lane(w):
    _lane(w, "l-a", 101, "session-a", "a")
    for pr, first in ((10, "Fixes: #101"), (11, "Closes %s#101." % REPO)):
        w.gh.comments[pr] = [_lapsed_comment(pr)]
        w.gh.pulls[pr] = {"state": "open", "merged": False, "body": first + "\n\nthe work"}
        assert _notice(w, pr)["kind"] == "lapsed-pass"
    _renew(w)
    out = _send(w)
    assert out["noLane"] == [] and [s["pr"] for s in out["sendBack"]] == [10, 11]


def test_a_pr_whose_first_line_only_says_part_of_an_issue_still_finds_its_cloud_lane(w):
    _lane(w, "l-a", 101, "session-a", "a")
    w.gh.comments[12] = [_lapsed_comment(12)]
    w.gh.pulls[12] = {"state": "open", "merged": False, "body": "Part of #101.\n\nthe work", "head": {"sha": "h1"}}
    assert _notice(w, 12)["kind"] == "lapsed-pass"
    assert _entries(w)[0]["launchId"] == "l-a"
    _renew(w)
    out = _send(w)
    assert out["noLane"] == [] and [s["cloudSessionName"] for s in out["sendBack"]] == ["session-a"]


def test_a_default_account_lane_recording_the_default_root_resolves_the_default_account(w):
    _lane(w, "l-a", 101, "session-a", "a", config_dir=str(w.home / ".claude"))
    _park(w, 10, issue=101)
    _renew(w)
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]


def test_a_renewal_in_another_environment_does_not_release_the_lanes_pr(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    got = CS.record_check(
        w.repo, root=w.store, account=ACCOUNT, environment="other-environment", plugin_version="1.2.3",
        picks_up_version=False, calibration_stamp=STAMP, calibration_date="2026-10-01",
        pass_lapses=FUTURE, checked_at="2026-10-01")
    assert got["action"] == "written", got
    out = _send(w)
    assert out["sendBack"] == [] and out["notRenewed"] == [10]


def test_an_unreadable_launch_ledger_leaves_a_renewed_pr_unread_not_without_a_lane(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    path = ll.ledger_path(w.repo, w.env)["path"]
    with open(path, "ab") as fh:
        fh.write(b"not json\n{\"event\": \"x\"}\n")
    out = _send(w)
    assert out["sendBack"] == [] and out["noLane"] == []
    assert out["unread"] and out["unread"][0]["pr"] == 10
    assert _entries(w)[0]["outcome"] is None


def _uncertain(w, pr):
    return CP.sent(w.repo, REPO, pr, uncertain=True, park_id=_park_id(w, pr), env=w.env)


def test_an_unconfirmed_send_is_never_resent_but_is_listed_every_time_until_a_newer_park_rearms_it(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    assert _uncertain(w, 10) == {"ok": True, "action": "written"}
    assert _entries(w)[0]["outcome"] == "send-uncertain"
    assert _uncertain(w, 10) == {"ok": True, "action": "unchanged"}
    for _ in range(2):
        out = _send(w)
        assert out["sendBack"] == []
        assert out["uncertain"] == [{"pr": 10, "repo": REPO, "launchId": "l-a", "parkId": _park_id(w, 10)}]
    w.gh.comments[10] = [_lapsed_comment(10, created_at="2026-10-08T10:00:00Z", cid=999)]
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert _entries(w)[0]["outcome"] is None
    assert _send(w)["uncertain"] == []


def test_the_cli_sent_uncertain_records_an_unconfirmed_delivery(w, capsys):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    argv = ["sent", "--repo-root", w.repo, "--repo", REPO, "--pr", "10", "--uncertain", "--park-id", str(_park_id(w, 10))]
    assert CP.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "action": "written"}
    assert _entries(w)[0]["outcome"] == "send-uncertain"
    out = _send(w)
    assert out["sendBack"] == [] and [u["pr"] for u in out["uncertain"]] == [10]


def test_a_plain_sent_confirms_an_unconfirmed_send_and_an_unconfirmed_one_never_downgrades_a_confirmed_send(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    assert _uncertain(w, 10)["action"] == "written"
    item = _send(w)["uncertain"][0]
    assert item["parkId"] is not None
    assert CP.sent(w.repo, REPO, 10, park_id=item["parkId"], env=w.env) == {"ok": True, "action": "written"}
    assert _entries(w)[0]["outcome"] == "sent-back"
    assert _uncertain(w, 10) == {"ok": True, "action": "unchanged"}
    assert _entries(w)[0]["outcome"] == "sent-back"
    assert _send(w)["uncertain"] == []


def _paused_run(gh):
    """A `run` that parks its first call (inside a verb's lock, after the state was loaded) until released."""
    inside, release = threading.Event(), threading.Event()
    first = []

    def run(argv, **kw):
        if not first:
            first.append(argv)
            inside.set()
            assert release.wait(10)
        return gh(argv, **kw)
    return run, inside, release


def _in_thread(fn, name=None):
    box = {}
    thread = threading.Thread(target=lambda: box.setdefault("out", fn()), daemon=True, name=name)
    thread.start()
    return thread, box


def _watch_lock(monkeypatch, thread_name):
    """An event set once the thread named `thread_name` calls the state lock's acquire: the proof that a
    worker which is then seen blocked was blocked on the lock, not still starting up."""
    fl = CP._sib("file_lock")
    real_acquire = fl.acquire
    reached_lock = threading.Event()

    def acquire(*args, **kw):
        if threading.current_thread().name == thread_name:
            reached_lock.set()
        return real_acquire(*args, **kw)

    monkeypatch.setattr(fl, "acquire", acquire)
    return reached_lock


# axis: the overlap tests confirm the second worker reached the lock before asserting it is blocked — see bite-proof record c8a_wo4.md
def test_two_notices_overlapping_in_time_cannot_both_read_the_state_and_lose_one_pr(w, monkeypatch):
    reached_lock = _watch_lock(monkeypatch, "notice-b")
    for pr in (10, 11):
        w.gh.comments[pr] = [_lapsed_comment(pr)]
        w.gh.pulls[pr] = _pull()
    run_a, a_inside, release_a = _paused_run(w.gh)
    b_started = threading.Event()

    def run_b(argv, **kw):
        b_started.set()
        return w.gh(argv, **kw)
    first, first_box = _in_thread(lambda: CP.notice(w.repo, REPO, 10, TODAY, env=w.env, run=run_a))
    try:
        assert a_inside.wait(10)
        second, second_box = _in_thread(
            lambda: CP.notice(w.repo, REPO, 11, TODAY, env=w.env, run=run_b), name="notice-b")
        assert reached_lock.wait(10), "the second notice never reached the lock while the first held it"
        assert not b_started.wait(0.5), "the second notice read the state while the first held it"
    finally:
        release_a.set()
    first.join(10)
    second.join(10)
    assert first_box["out"]["kind"] == second_box["out"]["kind"] == "lapsed-pass"
    assert sorted(e["pr"] for e in _entries(w)) == [10, 11]


# axis: the overlap tests confirm the second worker reached the lock before asserting it is blocked — see bite-proof record c8a_wo4.md
def test_a_sent_overlapping_a_state_writing_send_back_keeps_the_sent_back_outcome(w, monkeypatch):
    reached_lock = _watch_lock(monkeypatch, "sent-b")
    _park(w, 10)
    w.gh.comments[12] = [_lapsed_comment(12)]
    w.gh.pulls[12] = _pull()
    assert _notice(w, 12)["kind"] == "lapsed-pass"
    w.gh.pulls[12] = _pull(state="closed")
    run_a, a_inside, release_a = _paused_run(w.gh)
    first, first_box = _in_thread(lambda: CP.send_back(w.repo, TODAY, env=w.env, run=run_a))
    try:
        assert a_inside.wait(10)
        second, second_box = _in_thread(lambda: _sent(w, 10), name="sent-b")
        assert reached_lock.wait(10), "sent never reached the lock while send-back held it"
        second.join(0.5)
        assert second.is_alive(), "sent ran while send-back held the state"
    finally:
        release_a.set()
    first.join(10)
    second.join(10)
    assert second_box["out"] == {"ok": True, "action": "written"}
    assert {e["pr"]: e["outcome"] for e in _entries(w)} == {10: "sent-back", 12: "closed"}


# ---------------------------------------------------------------- a lane a successor replaced


def _recover_file(w):
    return os.path.join(os.path.dirname(ll.ledger_path(w.repo, w.env)["path"]), cloud_recover.STATE_NAME)


def _supersede(w, launch_id):
    mark = {"at": "2026-10-12T10:00:00Z", "branch": "issue-101-work", "sha": "a" * 40}
    with open(_recover_file(w), "w", encoding="utf-8") as fh:
        json.dump({"superseded": {launch_id: mark}}, fh)


def test_t9_a_lane_a_successor_replaced_is_listed_apart_and_never_sent_back(w):
    _lane(w, "l-old", 101, "old-session", "a", finished=True)
    _park(w, 10, issue=101)
    _renew(w)
    _supersede(w, "l-old")
    out = _send(w)
    assert out["sendBack"] == []
    assert out["superseded"] == [{"pr": 10, "launchId": "l-old"}]
    assert out["unread"] == [] and out["noLane"] == []
    assert _entries(w)[0]["outcome"] is None


def test_a_supersession_recorded_during_the_github_reads_still_fences_the_send_back(w):
    _lane(w, "l-old", 101, "old-session", "a", finished=True)
    _park(w, 10, issue=101)
    _renew(w)
    class Racing(Gh):
        def __call__(self, argv, **kw):
            if argv[-1] == _pull_path(10):
                _supersede(w, "l-old")
            return Gh.__call__(self, argv, **kw)
    racing = Racing()
    racing.comments, racing.pulls = w.gh.comments, w.gh.pulls
    out = CP.send_back(w.repo, TODAY, env=w.env, run=racing)
    assert out["sendBack"] == [] and out["superseded"] == [{"pr": 10, "launchId": "l-old"}]


def test_a_first_lane_superseded_during_the_second_prs_read_is_not_sent_back(w):
    _lane(w, "l-a", 101, "session-a", "a", finished=True)
    _lane(w, "l-b", 102, "session-b", "b", finished=True)
    _park(w, 10, issue=101)
    _park(w, 11, issue=102)
    _renew(w)
    class Racing(Gh):
        def __call__(self, argv, **kw):
            if argv[-1] == _pull_path(11):
                _supersede(w, "l-a")
            return Gh.__call__(self, argv, **kw)
    racing = Racing()
    racing.comments, racing.pulls = w.gh.comments, w.gh.pulls
    out = CP.send_back(w.repo, TODAY, env=w.env, run=racing)
    assert [c["pr"] for c in out["sendBack"]] == [11]
    assert out["superseded"] == [{"pr": 10, "launchId": "l-a"}]


def test_a_supersession_recorded_during_the_parked_state_save_still_fences_the_send_back(w, monkeypatch):
    _lane(w, "l-old", 101, "old-session", "a", finished=True)
    _park(w, 10, issue=101)
    _park(w, 11)
    _renew(w)
    w.gh.pulls[11] = _pull(state="closed")
    real_save = CP._save
    def save_then_supersede(path, entries):
        done = real_save(path, entries)
        _supersede(w, "l-old")
        return done
    monkeypatch.setattr(CP, "_save", save_then_supersede)
    out = _send(w)
    assert out["sendBack"] == [] and out["superseded"] == [{"pr": 10, "launchId": "l-old"}]
    assert {e["pr"]: e["outcome"] for e in _entries(w)} == {10: None, 11: "closed"}


def test_a_park_after_the_original_lane_was_superseded_binds_to_the_replacement(w):
    _lane(w, "l-old", 101, "old-session", "a", finished=True)
    _park(w, 10, issue=101)
    _supersede(w, "l-old")
    _lane(w, "l-new", 101, "new-session", "a2", ts=RELAUNCHED)
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert _entries(w)[0]["launchId"] == "l-new"


def test_a_new_park_while_the_recover_state_is_unreadable_is_refused_and_binds_on_retry(w):
    _lane(w, "l-old", 101, "old-session", "a", finished=True)
    _park(w, 10, issue=101)
    _supersede(w, "l-old")
    _lane(w, "l-new", 101, "new-session", "a2", ts=RELAUNCHED)
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    with open(_recover_file(w), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert _notice(w, 10) == {"ok": False, "reason": "recover-state-unreadable"}
    assert _entries(w)[0]["launchId"] == "l-old"
    os.remove(_recover_file(w))
    _supersede(w, "l-old")
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert _entries(w)[0]["launchId"] == "l-new"


def test_a_lane_another_lane_replaced_is_still_sent_back(w):
    _lane(w, "l-keep", 101, "keep-session", "a")
    _park(w, 10, issue=101)
    _renew(w)
    _supersede(w, "l-other")
    out = _send(w)
    assert out["superseded"] == []
    assert [s["launchId"] for s in out["sendBack"]] == ["l-keep"]


def test_a_recover_state_that_cannot_be_read_sends_nothing_back(w):
    _lane(w, "l-1", 101, "session-1", "a")
    _park(w, 10, issue=101)
    _renew(w)
    with open(_recover_file(w), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    out = _send(w)
    assert out["sendBack"] == [] and out["superseded"] == []
    assert out["unread"] == [{"pr": 10, "reason": "recover-state-unreadable"}]
    with open(_recover_file(w), encoding="utf-8") as fh:
        assert fh.read() == "{not json"


def test_a_rebind_stays_on_the_superseded_lanes_own_issue(w):
    _lane(w, "l-old", 101, "old-session", "a", finished=True)
    w.gh.comments[10] = [_lapsed_comment(10)]
    w.gh.pulls[10] = {"state": "open", "merged": False, "body": "Closes #101, closes #102", "head": {"sha": "h1"}}
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    _supersede(w, "l-old")
    _lane(w, "l-new", 101, "new-session", "a2", ts=RELAUNCHED)
    _lane(w, "l-other", 102, "other-session", "b", ts=RELAUNCHED)
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert _entries(w)[0]["launchId"] == "l-new"


def test_an_acknowledgement_for_a_replaced_park_records_nothing(w):
    _lane(w, "l-1", 101, "session-1", "a")
    _park(w, 10, issue=101)
    _renew(w)
    item = _send(w)["sendBack"][0]
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert CP.sent(w.repo, REPO, 10, park_id=item["parkId"], env=w.env) == {"ok": False, "reason": "park-changed"}
    assert _entries(w)[0]["outcome"] is None
    assert CP.sent(w.repo, REPO, 10, park_id="1010", env=w.env)["action"] == "written"


def test_a_legacy_acknowledgement_for_a_replaced_park_records_nothing(w):
    _lane(w, "l-1", 101, "session-1", "a")
    _park(w, 10, issue=101)
    entries = _entries(w)
    del entries[0]["parkId"]
    with open(_state_file(w), "w", encoding="utf-8") as fh:
        json.dump(entries, fh)
    _renew(w)
    item = _send(w)["sendBack"][0]
    assert item["parkId"] is None
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert CP.sent(w.repo, REPO, 10, env=w.env) == {"ok": False, "reason": "park-changed"}
    assert _entries(w)[0]["outcome"] is None


# ---------------------------------------------------------------- a rejected sign-in, and a renewal a running session never sees


FIRST_LINE = "Parked: the review did not run."


def _park_comment(pr, body, created_at="2026-10-05T10:00:00Z", cid=None):
    return {"id": 900 + pr if cid is None else cid, "body": body, "created_at": created_at}


def _rejected_comment(pr, **kw):
    return _park_comment(pr, cloud_builder.REVIEW_REJECTED_TEXT, **kw)


def _park_rejected(w, pr, issue=None):
    w.gh.comments[pr] = [_rejected_comment(pr)]
    w.gh.pulls[pr] = _pull(issue)
    out = _notice(w, pr)
    assert out["kind"] == "lapsed-pass" and out["cause"] == "rejected", out
    return out


def _confirmed_file(w):
    return os.path.join(os.path.dirname(ll.ledger_path(w.repo, w.env)["path"]), CP.CONFIRMED_NAME)


def _adopt_item(pr, issue, launch_id, session, park_id, cause):
    return {"pr": pr, "repo": REPO, "issue": issue, "launchId": launch_id, "parkId": park_id,
            "cloudSessionName": session, "configDir": None, "cause": cause,
            "notice": cloud_builder.superseded_notice_text(launch_id), "message": CP.ADOPT_MESSAGE % launch_id}


def test_t1_a_rejected_sign_in_park_is_classed_apart_recorded_with_its_cause_and_adopted_once_renewed(w):
    _lane(w, "l-a", 101, "session-a", "a")
    w.gh.comments[10] = [{"id": 1, "body": "hello"}, _rejected_comment(10)]
    w.gh.pulls[10] = _pull(101)
    out = _notice(w, 10)
    assert out == {"ok": True, "kind": "lapsed-pass", "pr": 10, "cause": "rejected", "text": CP.REJECTED_NOTICE_TEXT % 10}
    assert "401" in out["text"] and "sign-in was rejected" in out["text"]
    assert _entries(w) == [{"repo": REPO, "pr": 10, "parkedOn": "2026-10-05", "outcome": None,
                            "launchId": "l-a", "parkId": 910, "cause": "rejected"}]
    # the same park written free-form before this change classes the same
    free = FIRST_LINE + "\n\nThe reviewer answered 401 `token_revoked`, so no review happened."
    w.gh.comments[11] = [_park_comment(11, free)]
    w.gh.pulls[11] = _pull()
    assert _notice(w, 11) == {"ok": True, "kind": "lapsed-pass", "pr": 11, "cause": "rejected",
                              "text": CP.REJECTED_NOTICE_TEXT % 11}
    assert _entries(w)[1]["cause"] == "rejected"
    # not yet renewed: the record was written before the lane started
    _renew(w)
    assert _send(w)["adopt"] == [] and _send(w)["notRenewed"] == [10]
    # renewed after the lane started: it is adopted
    _written_at(w.repo, w.store, ACCOUNT, RENEWED_AT)
    got = _send(w)
    assert [a["pr"] for a in got["adopt"]] == [10] and got["adopt"][0]["cause"] == "rejected"
    assert got["sendBack"] == [] and got["notRenewed"] == [] and got["noLane"] == [{"pr": 11, "issue": None}]


def test_t1_e6_only_a_park_line_that_names_a_whole_number_401_is_a_rejected_park(w):
    for n, body in enumerate([FIRST_LINE + "\n\nThe review was stopped for some other reason.",
                              FIRST_LINE + "\n\nThe reviewer answered 4011.",
                              FIRST_LINE + "\n\nRequest id 1401 failed.",
                              "The review did not run (401).",
                              "Note: " + FIRST_LINE + " 401"]):
        w.gh.comments[20 + n] = [_park_comment(20 + n, body)]
        assert _notice(w, 20 + n) == {"ok": True, "kind": "not-lapsed-pass", "pr": 20 + n, "text": None}, body
    assert not os.path.exists(_state_file(w))
    w.gh.comments[30] = [_park_comment(30, FIRST_LINE + "\n\nThe reviewer answered 401.")]
    w.gh.pulls[30] = _pull()
    assert _notice(w, 30)["cause"] == "rejected"


def test_a_newer_park_of_the_other_cause_replaces_the_entry_and_the_newest_park_decides(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    assert "cause" not in _entries(w)[0]
    w.gh.comments[10].append(_rejected_comment(10, created_at="2026-10-08T10:00:00Z", cid=1010))
    assert _notice(w, 10)["cause"] == "rejected"
    assert _entries(w) == [{"repo": REPO, "pr": 10, "parkedOn": "2026-10-08", "outcome": None, "launchId": "l-a",
                            "parkId": 1010, "cause": "rejected"}]
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-09T10:00:00Z", cid=1011))
    assert _notice(w, 10) == {"ok": True, "kind": "lapsed-pass", "pr": 10, "text": CP.NOTICE_TEXT % 10}
    assert "cause" not in _entries(w)[0] and _entries(w)[0]["parkId"] == 1011


def test_a_stored_cause_other_than_rejected_makes_the_state_unreadable(w):
    _park(w, 10)
    good = _entries(w)
    for bad in ("lapsed", None, 1):
        with open(_state_file(w), "w", encoding="utf-8") as fh:
            json.dump([dict(good[0], cause=bad)], fh)
        assert _send(w) == {"ok": False, "reason": "parked-state-unreadable"}


def test_t2_a_lane_started_before_the_renewal_is_adopted_and_one_started_after_is_messaged(w):
    _lane(w, "l-a", 101, "session-a", "a")  # started 10-04
    _lane(w, "l-b", 102, "session-b", "b", started_ts=RELAUNCHED)  # started 10-10
    _park_rejected(w, 10, issue=101)
    _park(w, 11, issue=102)
    _renew(w, written_at=RENEWED_AT)  # renewed 10-08
    out = _send(w)
    assert out["adopt"] == [_adopt_item(10, 101, "l-a", "session-a", 910, "rejected")]
    assert out["adopt"][0]["message"] == CP.ADOPT_MESSAGE % "l-a"
    assert out["sendBack"] == [{"pr": 11, "repo": REPO, "issue": 102, "launchId": "l-b", "parkId": 911,
                                "cloudSessionName": "session-b", "configDir": None, "message": CP.SEND_BACK_MESSAGE}]
    assert [s["pr"] for s in out["sendBack"]] == [11] and 10 not in [s["pr"] for s in out["sendBack"]]
    assert out["notRenewed"] == [] and out["adopting"] == []
    assert [e["outcome"] for e in _entries(w)] == ["adopting", None]


def test_a_lapsed_park_of_a_lane_started_before_the_renewal_is_adopted_with_the_lapsed_cause(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w, written_at=RENEWED_AT)
    out = _send(w)
    assert out["adopt"] == [_adopt_item(10, 101, "l-a", "session-a", 910, "lapsed")] and out["sendBack"] == []


def test_t3_an_adopting_entry_is_listed_once_then_as_adopting_until_a_replacement_started(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park_rejected(w, 10, issue=101)
    _renew(w, written_at=RENEWED_AT)
    item = _adopt_item(10, 101, "l-a", "session-a", 910, "rejected")
    assert _send(w)["adopt"] == [item]
    assert _entries(w)[0]["outcome"] == "adopting"
    second = _send(w)
    assert second["adopt"] == [] and second["adopting"] == [item] and second["sendBack"] == []
    # a notice and a sent on an adopting entry change nothing
    assert _notice(w, 10) == {"ok": True, "kind": "park-resolved", "pr": 10, "text": None}
    assert CP.sent(w.repo, REPO, 10, park_id=910, env=w.env) == {"ok": False, "reason": "already-decided"}
    assert _entries(w)[0]["outcome"] == "adopting"
    # a supersession mark with no launch started behind it leaves the lane adopting
    _supersede(w, "l-a")
    assert _send(w)["adopting"] == [item]
    assert _entries(w)[0]["outcome"] == "adopting"
    # once a later launch for the issue has started, the entry is adopted and listed under neither
    assert ll.terminalize(w.repo, "l-a", child_ever_spawned=True, outcome="park", evidence="x", env=w.env)["ok"]
    _lane(w, "l-new", 101, "new-session", "a2", ts=RELAUNCHED)
    third = _send(w)
    assert third["adopt"] == [] and third["adopting"] == [] and third["sendBack"] == []
    assert third["skipped"] == [{"pr": 10, "outcome": "adopted"}]
    assert _entries(w)[0]["outcome"] == "adopted"
    assert _notice(w, 10)["kind"] == "park-resolved"
    assert CP.sent(w.repo, REPO, 10, park_id=910, env=w.env) == {"ok": False, "reason": "already-decided"}
    calls = len(w.gh.calls)
    again = _send(w)
    assert again["adopt"] == [] and again["adopting"] == [] and again["skipped"] == [] and len(w.gh.calls) == calls


def test_an_adopting_entry_whose_pr_closed_reads_closed(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park_rejected(w, 10, issue=101)
    _renew(w, written_at=RENEWED_AT)
    assert len(_send(w)["adopt"]) == 1
    w.gh.pulls[10] = _pull(101, state="closed")
    out = _send(w)
    assert out["adopting"] == [] and out["skipped"] == [{"pr": 10, "outcome": "closed"}]
    assert _entries(w)[0]["outcome"] == "closed"


def test_an_adopting_entry_whose_pr_cannot_be_read_stays_adopting(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park_rejected(w, 10, issue=101)
    _renew(w, written_at=RENEWED_AT)
    assert len(_send(w)["adopt"]) == 1
    w.gh.broken.add(_pull_path(10))
    out = _send(w)
    assert out["unread"] == [{"pr": 10, "reason": "pr-read-failed"}] and out["adopting"] == []
    assert _entries(w)[0]["outcome"] == "adopting"


def test_a_rejected_park_with_no_lane_is_listed_under_no_lane_before_any_renewal_is_judged(w):
    _lane(w, "l-unstarted", 101, None, "a")
    _park_rejected(w, 10, issue=101)
    _park_rejected(w, 11, issue=None)
    out = _send(w)  # nothing renewed at all
    assert out["noLane"] == [{"pr": 10, "issue": 101}, {"pr": 11, "issue": None}] and out["notRenewed"] == []
    assert out["adopt"] == [] and out["sendBack"] == []


def test_e1_a_rejected_park_is_not_renewed_by_a_record_written_before_the_lane_started(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park_rejected(w, 10, issue=101)
    _renew(w)  # a valid, unexpired lapse date, written before the lane started
    out = _send(w)
    assert out["notRenewed"] == [10] and out["adopt"] == [] and out["sendBack"] == []
    assert _entries(w)[0]["outcome"] is None
    # an old confirmation, from before the lane started, changes nothing
    with open(_confirmed_file(w), "w", encoding="utf-8") as fh:
        json.dump({ACCOUNT: LAUNCHED - 60}, fh)
    assert _send(w)["notRenewed"] == [10]


def test_e2_a_same_date_renewal_confirmed_after_the_lane_started_renews_a_rejected_park(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park_rejected(w, 10, issue=101)
    _renew(w)  # FUTURE lapse date, unchanged by the renewal
    assert _send(w)["notRenewed"] == [10]
    out = CP.send_back(w.repo, TODAY, confirmed=True, env=w.env, run=w.gh, now=RENEWED_AT)
    assert out["notRenewed"] == [] and out["adopt"] == [_adopt_item(10, 101, "l-a", "session-a", 910, "rejected")]
    with open(_confirmed_file(w), encoding="utf-8") as fh:
        assert json.load(fh) == {ACCOUNT: RENEWED_AT}
    assert CS.read(w.repo, ACCOUNT, w.store)["record"]["passLapses"] == FUTURE


def test_a_rejected_park_needs_a_valid_lapse_date_that_is_not_past_even_when_confirmed(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park_rejected(w, 10, issue=101)
    _setup_record(w.repo, w.store, ACCOUNT, "2026-10-11")  # lapsed yesterday
    out = CP.send_back(w.repo, TODAY, confirmed=True, env=w.env, run=w.gh, now=RENEWED_AT)
    assert out["notRenewed"] == [10] and out["adopt"] == []


@pytest.mark.parametrize("started", ["missing", None, "soon", float("nan"), float("inf"), True])
def test_e3_a_lane_without_a_readable_start_adopts_and_is_never_messaged(w, monkeypatch, started):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)  # lapse date moved on, record written before the lane
    real = CP._lane

    def unreadable_start(*args, **kw):
        launch_id, lane, why = real(*args, **kw)
        lane = {k: v for k, v in lane.items() if k != "startedTs"}
        if started != "missing":
            lane["startedTs"] = started
        return launch_id, lane, why
    monkeypatch.setattr(CP, "_lane", unreadable_start)
    out = _send(w)
    assert out["sendBack"] == [] and [a["pr"] for a in out["adopt"]] == [10]
    assert _entries(w)[0]["outcome"] == "adopting"


def test_a_rejected_park_whose_lane_has_no_readable_start_is_not_renewed(w, monkeypatch):
    _lane(w, "l-a", 101, "session-a", "a")
    _park_rejected(w, 10, issue=101)
    _renew(w, written_at=RENEWED_AT)
    real = CP._lane
    monkeypatch.setattr(CP, "_lane", lambda *a, **k: (lambda r: (r[0], {x: y for x, y in r[1].items() if x != "startedTs"}, r[2]))(real(*a, **k)))
    out = _send(w)
    assert out["notRenewed"] == [10] and out["adopt"] == [] and out["sendBack"] == []


@pytest.mark.parametrize("bad", ["{not json", "[]", '{"acct": "soon"}', '{"acct": true}', '{"acct": NaN}', '{"a": [1]}'])
def test_e4_an_unreadable_confirmation_file_refuses_send_back_and_changes_nothing(w, bad):
    _lane(w, "l-a", 101, "session-a", "a")
    _park_rejected(w, 10, issue=101)
    _renew(w, written_at=RENEWED_AT)
    with open(_confirmed_file(w), "w", encoding="utf-8") as fh:
        fh.write(bad)
    before = open(_state_file(w), encoding="utf-8").read()
    for confirmed in (False, True):
        assert CP.send_back(w.repo, TODAY, confirmed=confirmed, env=w.env, run=w.gh, now=RENEWED_AT) == {
            "ok": False, "reason": "pass-confirmed-unreadable"}
    assert open(_confirmed_file(w), encoding="utf-8").read() == bad
    assert open(_state_file(w), encoding="utf-8").read() == before


def test_e5_confirming_with_no_resolvable_account_refuses_and_writes_nothing(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park_rejected(w, 10, issue=101)
    os.unlink(str(w.home / ".claude.json"))
    before = open(_state_file(w), encoding="utf-8").read()
    assert CP.send_back(w.repo, TODAY, confirmed=True, env=w.env, run=w.gh, now=RENEWED_AT) == {
        "ok": False, "reason": "account-unknown"}
    assert not os.path.exists(_confirmed_file(w))
    assert open(_state_file(w), encoding="utf-8").read() == before


def test_a_confirmation_that_cannot_be_written_refuses(w, monkeypatch):
    _lane(w, "l-a", 101, "session-a", "a")
    _park_rejected(w, 10, issue=101)

    def broken(path, text):
        raise OSError("disk full")
    monkeypatch.setattr(store_core, "atomic_write", broken)
    assert CP.send_back(w.repo, TODAY, confirmed=True, env=w.env, run=w.gh, now=RENEWED_AT) == {
        "ok": False, "reason": "pass-confirmed-unwritable"}
    assert not os.path.exists(_confirmed_file(w))


def test_the_confirmation_is_per_account_and_a_later_one_replaces_an_earlier_one(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park_rejected(w, 10, issue=101)
    _renew(w)
    with open(_confirmed_file(w), "w", encoding="utf-8") as fh:
        json.dump({SECOND_ACCOUNT: RENEWED_AT, ACCOUNT: LAUNCHED - 60}, fh)
    assert _send(w)["notRenewed"] == [10]  # another account's confirmation, and an older one of this account's, renew nothing
    CP.send_back(w.repo, TODAY, confirmed=True, env=w.env, run=w.gh, now=RELAUNCHED)
    with open(_confirmed_file(w), encoding="utf-8") as fh:
        assert json.load(fh) == {SECOND_ACCOUNT: RENEWED_AT, ACCOUNT: RELAUNCHED}


def test_the_cli_send_back_takes_confirmed_and_lists_the_new_keys(w, capsys, monkeypatch):
    for k, v in w.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(w.home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert CP.main(["send-back", "--repo-root", w.repo, "--confirmed"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["adopt"] == [] and out["adopting"] == []
    with open(_confirmed_file(w), encoding="utf-8") as fh:
        assert list(json.load(fh)) == [ACCOUNT]
