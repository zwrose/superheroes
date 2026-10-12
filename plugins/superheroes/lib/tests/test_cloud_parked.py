# plugins/superheroes/lib/tests/test_cloud_parked.py
"""Conformance: the lapsed-pass parked notice and the send-back after renewal (cloud C7 WO-C).
Every repository, ledger, store and account file is built under tmp_path; the `gh api` answers are
a fake `run`; nothing touches the real home directory, clock or network."""
import datetime
import json
import os
import sys
from types import SimpleNamespace

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder  # noqa: E402
import cloud_parked as CP  # noqa: E402
import cloud_ready as CR  # noqa: E402
import cloud_setup as CS  # noqa: E402
import control_plane  # noqa: E402
import launch_ledger as ll  # noqa: E402
import launch_place as LP  # noqa: E402
import launch_report as LR  # noqa: E402
import review_record as RR  # noqa: E402

from test_launch_ledger import _declare, _init_repo, _ledger_env, _reserved, _started  # noqa: E402

ACCOUNT = "acct-fixture-one"
ENVIRONMENT = "env-fixture-one"
STAMP = "sha256:" + "ab" * 32
TODAY = "2026-10-12"
PAST = "2026-10-05"
FUTURE = "2026-12-01"
REPO = "owner/name"
BATCH = "b-parked"
RENEW_WORDS = ("renew", "fresh pass", "new pass")


class Gh:
    """Fake `gh api`: answers keyed by the endpoint, comments as concatenated pages like --paginate."""

    def __init__(self):
        self.comments, self.pulls, self.broken, self.calls = {}, {}, set(), []

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
            pages = [json.dumps([c]) for c in self.comments.get(number, [])]
            return SimpleNamespace(returncode=0, stdout="\n".join(pages) if pages else "[]")
        return SimpleNamespace(returncode=0, stdout=json.dumps(self.pulls[number]))

    broken_json = frozenset()

    def pull_calls(self):
        return [c for c in self.calls if "/pulls/" in c[-1]]


def _comments_path(pr):
    return "repos/%s/issues/%d/comments" % (REPO, pr)


def _pull_path(pr):
    return "repos/%s/pulls/%d" % (REPO, pr)


def _lapsed_comment(pr):
    return {"id": 900 + pr, "body": cloud_builder.REVIEW_LAPSED_TEXT, "created_at": "2026-10-05T10:00:00Z"}


def _record_comment(pr, missing):
    rec = {"schema": RR.RECORD_SCHEMA, "pr": pr, "missingReviews": missing}
    return {"id": 500 + pr, "body": RR.MARKER + "\n<details>\n\n```json\n" + json.dumps(rec) + "\n```\n</details>\n"}


def _pull(issue=None, state="open", merged=False):
    body = "Closes #%d\n\nthe work" % issue if issue else "the work"
    return {"state": state, "merged": merged, "body": body}


@pytest.fixture
def w(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    root = _ledger_env(tmp_path, monkeypatch)
    store = str(tmp_path / "store")
    monkeypatch.setattr(control_plane, "store_root", lambda: store)
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": ACCOUNT}}), encoding="utf-8")
    env = {"HOME": str(home), "PATH": os.environ["PATH"], ll.LEDGER_ROOT_ENV: root}
    got = CS.record_check(
        repo, root=store, account=ACCOUNT, environment=ENVIRONMENT, plugin_version="1.2.3",
        picks_up_version=False, calibration_stamp=STAMP, calibration_date="2026-10-01",
        pass_lapses=PAST, checked_at="2026-10-01")
    assert got["action"] == "written", got
    gh = Gh()
    assert _declare(repo, BATCH, 4, env=env)["ok"]
    return SimpleNamespace(repo=repo, store=store, env=env, gh=gh, home=home)


def _notice(w, pr, today=TODAY):
    return CP.notice(w.repo, REPO, pr, today, env=w.env, run=w.gh)


def _send(w, today=TODAY):
    return CP.send_back(w.repo, today, env=w.env, run=w.gh)


def _park(w, pr, issue=None, **pull):
    w.gh.comments[pr] = [_lapsed_comment(pr)]
    w.gh.pulls[pr] = _pull(issue, **pull)
    out = _notice(w, pr)
    assert out["kind"] == "lapsed-pass", out
    return out


def _renew(w, date=FUTURE):
    assert CS.confirm_pass(w.repo, ACCOUNT, date, root=w.store)["action"] == "written"


def _lane(w, launch_id, issue, session, surface, finished=False):
    rec = _reserved(launch_id, BATCH, [surface], w.repo, issue=issue, place="cloud",
                    cloudEnvironment=ENVIRONMENT, pluginVersion="1.2.3")
    assert ll.reserve(w.repo, rec, env=w.env)["ok"]
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


def test_notice_for_a_lapsed_pass_park_names_the_pr_the_reason_and_the_renewal(w):
    w.gh.comments[42] = [{"id": 1, "body": "hello"}, _lapsed_comment(42)]
    out = _notice(w, 42)
    assert out == {"ok": True, "kind": "lapsed-pass", "pr": 42, "text": (
        "#42 is parked. The reviewer pass lapsed mid-build, so its review didn't run. "
        "Renew the pass and I'll send it back for review.")}
    entry = _entries(w)[0]
    assert (entry["repo"], entry["pr"], entry["parkedCommentId"], entry["lapseSeen"]) == (REPO, 42, 942, PAST)
    assert entry["outcome"] is None


def test_a_pr_whose_review_did_not_run_for_another_reason_gets_no_renewal_words(w):
    w.gh.comments[43] = [_record_comment(43, [{"name": "codex", "goAhead": None}])]
    out = _notice(w, 43)
    assert out == {"ok": True, "kind": "not-lapsed-pass", "pr": 43, "text": None}
    assert not any(word in json.dumps(out).lower() for word in RENEW_WORDS)
    assert not os.path.exists(_state_file(w))


def test_after_a_confirmed_renewal_the_open_parked_pr_goes_back_with_its_lanes_session(w):
    _lane(w, "l-older", 101, "older-session", "a", finished=True)
    _lane(w, "l-newer", 101, "newer-session", "a2")
    _lane(w, "l-other", 202, "other-session", "b")
    _park(w, 10, issue=101)
    _renew(w)
    out = _send(w)
    assert out["ok"] is True and out["lapses"] == FUTURE and out["notRenewed"] == []
    assert out["sendBack"] == [{
        "pr": 10, "issue": 101, "launchId": "l-newer", "cloudSessionName": "newer-session",
        "configDir": None, "message": CP.SEND_BACK_MESSAGE}]
    assert CP.SEND_BACK_MESSAGE == ("The reviewer pass is renewed. Run this pull request's review now, as "
                                    "your review step says, then hand back as usual.")
    assert _entries(w)[0]["outcome"] == "sent-back"


def test_a_parked_pr_with_no_cloud_lane_goes_back_with_the_lane_fields_null(w):
    _park(w, 10, issue=None)
    _renew(w)
    sent = _send(w)["sendBack"][0]
    assert (sent["issue"], sent["launchId"], sent["cloudSessionName"], sent["configDir"]) == (None,) * 4


def test_a_parked_pr_closed_before_the_renewal_is_not_sent_back(w):
    _park(w, 10, issue=101, state="closed")
    _park(w, 11, issue=102, state="open", merged=True)
    _renew(w)
    out = _send(w)
    assert out["sendBack"] == []
    assert out["skipped"] == [{"pr": 10, "outcome": "closed"}, {"pr": 11, "outcome": "closed"}]
    assert [e["outcome"] for e in _entries(w)] == ["closed", "closed"]


def test_a_parked_pr_the_owner_let_through_is_not_sent_back(w):
    _park(w, 10, issue=101)
    w.gh.comments[10].append(_record_comment(10, [{"name": "codex", "goAhead": {"kind": "owner-words"}}]))
    _park(w, 11, issue=102)
    w.gh.comments[11].append(_record_comment(
        11, [{"name": "codex", "goAhead": {"kind": "owner-words"}}, {"name": "claude", "goAhead": None}]))
    _renew(w)
    out = _send(w)
    assert out["skipped"] == [{"pr": 10, "outcome": "owner-let-through"}]
    assert [s["pr"] for s in out["sendBack"]] == [11]


def test_a_pass_made_but_not_confirmed_by_a_cloud_session_sends_nothing_back(w):
    _park(w, 10, issue=101)
    out = _send(w)
    assert out["sendBack"] == [] and out["skipped"] == [] and out["notRenewed"] == [10]
    assert out["lapses"] == PAST
    assert w.gh.pull_calls() == []
    assert _entries(w)[0]["outcome"] is None


def test_a_decided_entry_is_not_sent_back_twice(w):
    _park(w, 10, issue=101)
    _renew(w)
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]
    calls = len(w.gh.calls)
    again = _send(w)
    assert again["sendBack"] == [] and again["skipped"] == [] and again["notRenewed"] == []
    assert len(w.gh.calls) == calls


def test_renoticing_a_recorded_pr_keeps_its_first_lapse_seen(w):
    _park(w, 10)
    _renew(w)
    assert _notice(w, 10)["kind"] == "lapsed-pass"
    assert [e["lapseSeen"] for e in _entries(w)] == [PAST]


def test_E1_an_unreadable_comments_read_refuses_the_notice(w):
    w.gh.comments[10] = [_lapsed_comment(10)]
    w.gh.broken.add(_comments_path(10))
    assert _notice(w, 10) == {"ok": False, "reason": "pr-read-failed"}
    w.gh.broken.clear()
    w.gh.broken_json = frozenset([_comments_path(10)])
    assert _notice(w, 10) == {"ok": False, "reason": "pr-read-failed"}
    assert not os.path.exists(_state_file(w))


def test_E1_an_unreadable_pr_stays_undecided_and_is_never_sent_back_or_closed(w):
    _park(w, 10, issue=101)
    _renew(w)
    w.gh.broken.add(_pull_path(10))
    out = _send(w)
    assert out["unread"] == [{"pr": 10, "reason": "pr-read-failed"}]
    assert out["sendBack"] == [] and out["skipped"] == []
    assert _entries(w)[0]["outcome"] is None
    w.gh.broken.clear()
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]


def test_E2_a_missing_or_unreadable_setup_record_renews_nothing(w):
    _park(w, 10, issue=101)
    _renew(w)
    path = CS.record_path(w.repo, ACCOUNT, w.store)
    saved = open(path, encoding="utf-8").read()
    os.unlink(path)
    out = _send(w)
    assert out["sendBack"] == [] and out["notRenewed"] == [10] and out["lapses"] is None
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(saved.replace(FUTURE, "next-tuesday"))
    out = _send(w)
    assert out["sendBack"] == [] and out["notRenewed"] == [10] and out["lapses"] is None
    assert _entries(w)[0]["outcome"] is None


def test_E3_a_pr_parked_when_there_was_no_pass_is_renewed_by_any_valid_date_not_before_today(w):
    path = CS.record_path(w.repo, ACCOUNT, w.store)
    saved = open(path, encoding="utf-8").read()
    os.unlink(path)
    _park(w, 10, issue=101)
    assert _entries(w)[0]["lapseSeen"] is None
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(saved.replace(PAST, TODAY))
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]
    _park(w, 11, issue=102)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(saved.replace(PAST, "2026-10-11"))
    assert _send(w)["notRenewed"] == [11]


def test_E4_a_review_record_that_cannot_be_read_does_not_count_as_a_let_through(w):
    _park(w, 10, issue=101)
    _renew(w)
    w.gh.comments[10].append({"id": 7, "body": RR.MARKER + "\nnot a record"})
    assert [s["pr"] for s in _send(w)["sendBack"]] == [10]


def test_E5_an_unreadable_state_file_refuses_both_verbs_and_is_never_overwritten(w):
    _park(w, 10, issue=101)
    for bad in ("{not json", json.dumps({"entries": []}), json.dumps([{"pr": 10}])):
        with open(_state_file(w), "w", encoding="utf-8") as fh:
            fh.write(bad)
        w.gh.comments[11] = [_lapsed_comment(11)]
        assert _notice(w, 11) == {"ok": False, "reason": "parked-state-unreadable"}
        assert _send(w) == {"ok": False, "reason": "parked-state-unreadable"}
        assert open(_state_file(w), encoding="utf-8").read() == bad


def test_E6_a_malformed_today_pr_or_repo_is_refused(w):
    for today in ("2026-13-01", "20261012", "tomorrow", ""):
        assert _notice(w, 10, today) == {"ok": False, "reason": "today-invalid"}
        assert _send(w, today) == {"ok": False, "reason": "today-invalid"}
    for pr in (0, -3, "abc", "04", True, 1.5):
        assert CP.notice(w.repo, REPO, pr, TODAY, env=w.env, run=w.gh) == {"ok": False, "reason": "pr-invalid"}
    for repo in ("owner", "owner/", "a b/c", "../x"):
        assert CP.notice(w.repo, repo, 10, TODAY, env=w.env, run=w.gh) == {"ok": False, "reason": "repo-invalid"}
    assert w.gh.calls == []


def test_the_cli_prints_one_json_object_and_exits_one_on_a_refusal(w, capsys):
    assert CP.main(["notice", "--repo-root", w.repo, "--repo", REPO, "--pr", "zero"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "pr-invalid"}
    assert CP.main(["send-back"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "usage"}


def _readiness(reason=None):
    def readiness(cwd, reported=None, root=None, env=None):
        conditions = {name: CR.REASON_FOR[name] != reason for name in CR.CONDITION_ORDER}
        return {"ready": reason is None, "reason": reason, "conditions": conditions, "setting": True,
                "account": ACCOUNT, "environment": ENVIRONMENT, "cloudVersion": "1.2.3",
                "advisorVersion": "1.2.3", "picksUpVersion": False, "checkedAt": None}
    return readiness


def test_FR35_the_owner_hears_the_lapsed_pass_on_the_report_the_still_line_and_the_parked_notice(w):
    def route(readiness_fn):
        return LP.route(w.repo, {}, None, readiness_fn=readiness_fn, needs_fn=lambda cwd, premise, root=None: [],
                        root=w.store, env=w.env)

    lapsed, ready = route(_readiness("pass-lapsed")), route(_readiness())
    assert (lapsed["place"], lapsed["reason"], ready["place"]) == ("local", "pass-lapsed", "cloud")
    report = LR.render_report([{"issue": 1, "title": "Ready one", "placeCall": ready},
                               {"issue": 2, "title": "Lapsed one", "placeCall": lapsed}])
    day = datetime.date.fromisoformat(TODAY)
    assert LR.record_still(w.repo, [lapsed], root=w.store, today=day)["action"] == "written"
    still = LR.still_line(w.repo, root=w.store, today=day, readiness_fn=_readiness("pass-lapsed"))
    parked = _park(w, 10, issue=2)["text"]
    assert LP.REASONS["pass-lapsed"]["words"] in report
    assert still.startswith("Still on your machine")
    assert parked.startswith("#10 is parked.") and "Renew the pass" in parked
