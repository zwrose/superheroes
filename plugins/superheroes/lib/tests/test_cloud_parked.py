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
FUTURE = "2026-12-01"
REPO = "owner/name"
BATCH = "b-parked"
RENEW_WORDS = ("renew", "fresh pass", "new pass")


class Gh:
    """Fake `gh api`: answers keyed by the endpoint, comments as concatenated pages like --paginate."""

    def __init__(self):
        self.comments, self.pulls, self.broken, self.calls = {}, {}, set(), []
        self.comment_reads, self.comments_fail_from = 0, None

    def __call__(self, argv, **_kw):
        self.calls.append(tuple(argv))
        path = argv[-1]
        if path in self.broken:
            return SimpleNamespace(returncode=1, stdout="")
        if path in self.broken_json:
            return SimpleNamespace(returncode=0, stdout="not json")
        parts = path.split("/")
        number = int(parts[4])
        if parts[3] == "issues":
            self.comment_reads += 1
            if self.comments_fail_from is not None and self.comment_reads >= self.comments_fail_from:
                return SimpleNamespace(returncode=1, stdout="")
            pages = [json.dumps([c]) for c in self.comments.get(number, [])]
            if "--paginate" not in argv:
                pages = pages[:1]
            return SimpleNamespace(returncode=0, stdout="\n".join(pages) if pages else "[]")
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


def _record_comment(pr, missing, sha="h1"):
    rec = {"schema": RR.RECORD_SCHEMA, "pr": pr, "missingReviews": missing, "finalCommit": {"sha": sha},
           "parked": any(m["goAhead"] is None for m in missing)}
    return {"id": 500 + pr, "body": RR.MARKER + "\n<details>\n\n```json\n" + json.dumps(rec) + "\n```\n</details>\n"}


def _pull(issue=None, state="open", merged=False):
    body = "Closes #%d\n\nthe work" % issue if issue else "the work"
    return {"state": state, "merged": merged, "body": body, "head": {"sha": "h1"}}


def _account_file(directory, account):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": account}}), encoding="utf-8")


def _setup_record(repo, store, account, lapses):
    got = CS.record_check(
        repo, root=store, account=account, environment=ENVIRONMENT, plugin_version="1.2.3",
        picks_up_version=False, calibration_stamp=STAMP, calibration_date="2026-10-01",
        pass_lapses=lapses, checked_at="2026-10-01")
    assert got["action"] == "written", got


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


def _sent(w, pr, repo=REPO):
    return CP.sent(w.repo, repo, pr, env=w.env)


def _park(w, pr, issue=None, **pull):
    w.gh.comments[pr] = [_lapsed_comment(pr)]
    w.gh.pulls[pr] = _pull(issue, **pull)
    out = _notice(w, pr)
    assert out["kind"] == "lapsed-pass", out
    return out


def _renew(w, account=ACCOUNT, date=FUTURE):
    """A renewal the way a cloud session confirms it: through the pass module's own recorder."""
    confirmation = {"schema": cloud_pass.CONFIRMATION_SCHEMA, "reviewerAnswered": True,
                    "passLapses": date, "reason": None}
    got = cloud_pass.record_confirmation(
        w.repo, confirmation, account=account, environment=ENVIRONMENT, now=NOW, root=w.store, env=w.env)
    assert got["action"] == "written", got


def _lane(w, launch_id, issue, session, surface, finished=False, config_dir=None, ts=LAUNCHED):
    extra = {"ts": ts} if config_dir is None else {"ts": ts, "configDir": config_dir}
    rec = _reserved(launch_id, BATCH, [surface], w.repo, issue=issue, place="cloud",
                    cloudEnvironment=ENVIRONMENT, pluginVersion="1.2.3", **extra)
    assert ll.reserve(w.repo, rec, env=w.env)["ok"]
    if session is not None:
        started = _started(launch_id)
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
    assert out == {"ok": True, "skipped": [], "unread": [], "notRenewed": [], "noLane": [], "superseded": [], "uncertain": [], "sendBack": [{
        "pr": 10, "repo": REPO, "issue": 101, "launchId": "l-newer", "cloudSessionName": "newer-session",
        "configDir": None, "message": CP.SEND_BACK_MESSAGE}]}
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


def test_comments_are_read_with_the_paginate_flag_so_later_pages_count(w):
    _lane(w, "l-a", 101, "session-a", "a")
    w.gh.comments[10] = [{"id": 1, "body": "chatter"}, _lapsed_comment(10)]
    w.gh.pulls[10] = _pull(101)
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert any("--paginate" in c for c in w.gh.calls if "/comments" in c[-1])
    w.gh.comments[11] = [{"id": 1, "body": "chatter"}, {"id": 2, "body": "chatter"}]
    assert _notice(w, 11)["kind"] == "not-lapsed-pass"


def test_an_owner_go_ahead_on_a_later_comment_page_is_still_seen(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    w.gh.comments[10] += [{"id": 8, "body": "chatter"},
                          _record_comment(10, [{"name": "codex", "goAhead": {"kind": "owner-words"}}])]
    _renew(w)
    assert _send(w)["skipped"] == [{"pr": 10, "outcome": "owner-let-through"}]


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
        assert _sent(w, 10) == {"ok": False, "reason": "parked-state-unreadable"}
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
    return CP.sent(w.repo, REPO, pr, uncertain=True, env=w.env)


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
        assert out["uncertain"] == [{"pr": 10, "repo": REPO, "launchId": "l-a"}]
    w.gh.comments[10] = [_lapsed_comment(10, created_at="2026-10-08T10:00:00Z", cid=999)]
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert _entries(w)[0]["outcome"] is None
    assert _send(w)["uncertain"] == []


def test_the_cli_sent_uncertain_records_an_unconfirmed_delivery(w, capsys):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    _renew(w)
    argv = ["sent", "--repo-root", w.repo, "--repo", REPO, "--pr", "10", "--uncertain"]
    assert CP.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "action": "written"}
    assert _entries(w)[0]["outcome"] == "send-uncertain"
    out = _send(w)
    assert out["sendBack"] == [] and [u["pr"] for u in out["uncertain"]] == [10]


def test_a_plain_sent_confirms_an_unconfirmed_send_and_an_unconfirmed_one_never_downgrades_a_confirmed_send(w):
    _lane(w, "l-a", 101, "session-a", "a")
    _park(w, 10, issue=101)
    assert _uncertain(w, 10)["action"] == "written"
    assert _sent(w, 10) == {"ok": True, "action": "written"}
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


def _in_thread(fn):
    box = {}
    thread = threading.Thread(target=lambda: box.setdefault("out", fn()), daemon=True)
    thread.start()
    return thread, box


def test_two_notices_overlapping_in_time_cannot_both_read_the_state_and_lose_one_pr(w):
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
        second, second_box = _in_thread(lambda: CP.notice(w.repo, REPO, 11, TODAY, env=w.env, run=run_b))
        assert not b_started.wait(0.5), "the second notice read the state while the first held it"
    finally:
        release_a.set()
    first.join(10)
    second.join(10)
    assert first_box["out"]["kind"] == second_box["out"]["kind"] == "lapsed-pass"
    assert sorted(e["pr"] for e in _entries(w)) == [10, 11]


def test_a_sent_overlapping_a_state_writing_send_back_keeps_the_sent_back_outcome(w):
    _park(w, 10)
    w.gh.comments[12] = [_lapsed_comment(12)]
    w.gh.pulls[12] = _pull()
    assert _notice(w, 12)["kind"] == "lapsed-pass"
    w.gh.pulls[12] = _pull(state="closed")
    run_a, a_inside, release_a = _paused_run(w.gh)
    first, first_box = _in_thread(lambda: CP.send_back(w.repo, TODAY, env=w.env, run=run_a))
    try:
        assert a_inside.wait(10)
        second, second_box = _in_thread(lambda: _sent(w, 10))
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
