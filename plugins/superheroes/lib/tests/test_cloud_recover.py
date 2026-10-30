# plugins/superheroes/lib/tests/test_cloud_recover.py
"""Conformance: the advisor's recovery of a stopped cloud builder. The git remote is a real bare
repository under tmp_path, pushed to from a second clone so the advisor's clone lacks the pushed
objects and must fetch them; only `gh` is faked, through the `run=` injection. The launch ledger lives
under tmp_path; nothing touches the real home directory, clock source or network."""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder  # noqa: E402
import cloud_recover as CR  # noqa: E402
import heartbeat  # noqa: E402
import launch_ledger as ll  # noqa: E402
import launch_place  # noqa: E402
import launcher as L  # noqa: E402
import cloud_ready  # noqa: E402

REPO = "owner/repo"
BATCH = "b-recover"
WINDOW = heartbeat.LIVENESS_QUIET_WINDOW_SECONDS
HEADER = cloud_builder.HANDOVER_HEADER
UTC = datetime.timezone.utc
BRANCH = "issue-17-work"


def _handover_body(sha):
    return cloud_builder.handover_text(sha)


def _run_handover(sha):
    proc = subprocess.run([sys.executable, "-B", cloud_builder.__file__, "handover", "--head", sha],
                          capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def _clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra)
    return env


def _git(cwd, *args, env=None):
    proc = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.email=t@test.local", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True, env=env or _clean_env())
    return proc.stdout.strip()


def _has_object(cwd, sha):
    return subprocess.run(["git", "-C", str(cwd), "cat-file", "-e", sha + "^{commit}"],
                          capture_output=True, env=_clean_env()).returncode == 0


def _iso_ago(age):
    return datetime.datetime.fromtimestamp(time.time() - age, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _at(hour, minute, second=0):
    return datetime.datetime(2026, 10, 12, hour, minute, second, tzinfo=UTC).timestamp()


def _stamp(hour, minute):
    return "2026-10-12T%02d:%02d:00Z" % (hour, minute)


class Gh:
    """Fake `gh api` (and a passthrough for git): comments and push activity are set by the test."""

    def __init__(self):
        self.comments, self.comments_fail, self.activity, self.calls = [], False, {}, []
        self.pulls = []

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        if argv[0] == "git":
            return subprocess.run(argv, **kw)
        endpoint = argv[-1]
        if "/activity?" in endpoint:
            ref = parse_qs(urlparse(endpoint).query)["ref"][0]
            events = self.activity.get(ref[len("refs/heads/"):])
            if events is None:
                return subprocess.CompletedProcess(argv, 1, "", "boom")
            return subprocess.CompletedProcess(argv, 0, events if isinstance(events, str) else json.dumps(events), "")
        if "/pulls?" in endpoint:
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.pulls), "")
        if "/comments?" in endpoint:
            if self.comments_fail:
                return subprocess.CompletedProcess(argv, 1, "", "boom")
            since = parse_qs(urlparse(endpoint).query)["since"][0]  # like GitHub: only comments updated after `since`, not created
            return subprocess.CompletedProcess(argv, 0, json.dumps(
                [c for c in self.comments if c.get("updated_at", c["created_at"]) > since]), "")
        return subprocess.CompletedProcess(argv, 1, "", "unrouted")


def _event(branch, sha, timestamp):
    return {"ref": "refs/heads/" + branch, "after": sha, "before": "0" * 40, "timestamp": timestamp,
            "activity_type": "push", "id": 1}


def _comment(body, age=600, cid=1):
    return {"id": cid, "html_url": "https://github.com/%s/issues/17#issuecomment-%d" % (REPO, cid),
            "body": body, "created_at": _iso_ago(age), "updated_at": _iso_ago(age)}


@pytest.fixture
def w(tmp_path, monkeypatch):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True, env=_clean_env())
    _git(bare, "symbolic-ref", "HEAD", "refs/heads/main")
    advisor = tmp_path / "advisor"
    advisor.mkdir()
    _git(advisor, "init", "-q")
    _git(advisor, "symbolic-ref", "HEAD", "refs/heads/main")
    (advisor / "file.txt").write_text("x\n")
    _git(advisor, "add", ".")
    _git(advisor, "commit", "-q", "-m", "init")
    _git(advisor, "remote", "add", "origin", str(bare))
    _git(advisor, "push", "-q", "origin", "main")
    builder = tmp_path / "builder"
    subprocess.run(["git", "clone", "-q", str(bare), str(builder)], check=True, env=_clean_env())
    root = str(advisor)
    store = str(tmp_path / "ledger-root")
    os.makedirs(store, mode=0o700, exist_ok=True)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, store)
    os.makedirs(os.path.join(store, ll.repo_identity(root)), mode=0o700, exist_ok=True)
    assert ll.declare_batch(root, BATCH, 8)["ok"]
    return SimpleNamespace(root=root, builder=str(builder), bare=str(bare), tmp=tmp_path, gh=Gh(),
                           base=_git(advisor, "rev-parse", "HEAD"))


def _push(w, branch, name, when=None):
    """Commit on `branch` in the builder's clone and push it; the advisor's clone never sees the object."""
    env = _clean_env(**({"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when} if when else {}))
    exists = subprocess.run(["git", "-C", w.builder, "rev-parse", "--verify", "-q", "refs/heads/" + branch],
                            capture_output=True, env=_clean_env()).returncode == 0
    _git(w.builder, "checkout", "-q", branch) if exists else _git(w.builder, "checkout", "-q", "-b", branch, w.base)
    with open(os.path.join(w.builder, name + ".txt"), "w") as fh:
        fh.write(name)
    _git(w.builder, "add", ".")
    _git(w.builder, "commit", "-q", "-m", name, env=env)
    _git(w.builder, "push", "-q", "origin", branch)
    return _git(w.builder, "rev-parse", "HEAD")


def _premise(w, issue):
    """A reserved premise the launcher accepts (once its own stamps are gone), with the stamps it adds."""
    return {"issue": issue, "surfaces": ["plugins/x"], "batchId": BATCH, "baseCommit": w.base, "stack": 2,
            "layerPosition": 2, "maxRunMinutes": 240, "bashMaxTimeoutMs": 900000,
            "grantScope": {"applicable": False, "reason": "no grant in this lane"},
            "ownerCapability": {"applicable": False, "reason": "no owner capability in this lane"},
            "placeCall": {"place": "cloud", "pointedAtCloud": True}, "standingExclusions": {"merge": True},
            "standDown": 1}


def _lane(w, launch_id, issue=17, *, premise=None, start_age=7200):
    assert ll.append(w.root, {
        "event": "reserved", "launchId": launch_id, "ts": time.time() - start_age - 60, "schema": ll.SCHEMA,
        "batchId": BATCH, "repoId": ll.repo_identity(w.root), "issue": issue, "surfaces": ["plugins/x-%s" % launch_id],
        "premise": _premise(w, issue) if premise is None else premise, "preflight": {}, "argv": [],
        "doctrineDigest": "abc123", "model": "test-model", "place": ll.PLACE_CLOUD, "cloudEnvironment": "env-1",
        "pluginVersion": "1.2.3", "configDir": "/cfg/acct"})
    assert ll.append(w.root, {
        "event": "started", "launchId": launch_id, "ts": time.time() - start_age, "schema": ll.SCHEMA, "attempt": 1,
        "pid": 999999999, "logPath": "/tmp/log", "errPath": "/tmp/err", "cloudSessionName": "cloud-%s" % launch_id,
        "cloudSessionId": "session_%s" % launch_id, "cloudSessionUrl": "https://claude.ai/code/session_x"})


def _local_lane(w, launch_id):
    assert ll.append(w.root, {
        "event": "reserved", "launchId": launch_id, "ts": time.time(), "schema": ll.SCHEMA, "batchId": BATCH,
        "repoId": ll.repo_identity(w.root), "issue": 18, "surfaces": ["plugins/local"], "premise": {}, "preflight": {},
        "argv": [], "doctrineDigest": "abc123", "model": "test-model"})
    assert ll.append(w.root, {
        "event": "started", "launchId": launch_id, "ts": time.time(), "schema": ll.SCHEMA, "attempt": 1,
        "pid": 999999999, "logPath": "/tmp/log", "errPath": "/tmp/err"})


def _died(w, launch_id, outcome="died"):
    assert ll.record_outcome(w.root, launch_id, outcome, "ended")["ok"]


def _assess(w, launch_id="l1", state="failed", age=None, **kw):
    return CR.assess(w.root, launch_id, session_state=state, activity_age_seconds=age, repo=REPO, run=w.gh, **kw)


def _successor(w, launch_id="l1", **kw):
    return CR.successor(w.root, launch_id, repo=REPO, run=w.gh, **kw)


def _state_file(w):
    return os.path.join(os.path.dirname(ll.ledger_path(w.root)["path"]), CR.STATE_NAME)


def _state(w):
    with open(_state_file(w), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- what the lane pushed


def test_p1_a_branch_matches_only_when_it_carries_the_issue_as_a_whole_number(w):
    wanted = _push(w, BRANCH, "a")
    _push(w, "issue-170-other", "b")
    _push(w, "feature/1700", "c")
    got = CR.pushed(w.root, 17, repo=REPO, run=w.gh)
    assert got["ok"] is True
    assert [b["branch"] for b in got["branches"]] == [BRANCH]
    assert got["newest"]["branch"] == BRANCH and got["newest"]["sha"] == wanted and got["ambiguous"] is False
    assert [b["branch"] for b in CR.pushed(w.root, 170, repo=REPO, run=w.gh)["branches"]] == ["issue-170-other"]


def test_pushed_work_is_fetched_and_timed_from_the_push_event(w):
    sha = _push(w, BRANCH, "a", when="2026-10-12T08:00:00+0000")
    assert not _has_object(w.root, sha)
    w.gh.activity[BRANCH] = [_event(BRANCH, "f" * 40, _stamp(9, 59)), _event(BRANCH, sha, _stamp(9, 55))]
    got = CR.pushed(w.root, 17, repo=REPO, run=w.gh)
    assert _has_object(w.root, sha)
    assert got["newest"] == {"branch": BRANCH, "sha": sha, "committedAt": _at(8, 0), "pushedAt": _at(9, 55),
                             "pushTimeSource": "push"}
    asked_for = [c[-1] for c in w.gh.calls if c[0] == "gh"]
    assert asked_for == ["repos/%s/activity?ref=refs/heads/%s&activity_type=push&per_page=30" % (REPO, BRANCH)]


@pytest.mark.parametrize("events", [None, "not json", [], [{"ref": "refs/heads/x", "after": "e" * 40, "timestamp": "2026-10-12T09:55:00Z"}]],
                         ids=["call-fails", "unparseable", "empty", "no-match"])
def test_an_activity_read_that_gives_no_push_time_falls_back_to_the_commit_time(w, events):
    _push(w, BRANCH, "a", when="2026-10-12T08:00:00+0000")
    if events is not None:
        w.gh.activity[BRANCH] = events
    entry = CR.pushed(w.root, 17, repo=REPO, run=w.gh)["newest"]
    assert entry["pushTimeSource"] == "commit" and entry["pushedAt"] == entry["committedAt"] == _at(8, 0)


def test_a_remote_that_cannot_be_listed_is_refused(w):
    _git(w.root, "remote", "set-url", "origin", str(w.tmp / "nowhere.git"))
    assert CR.pushed(w.root, 17, repo=REPO, run=w.gh) == {"ok": False, "reason": "remote-unreadable"}


def test_a_branch_that_moved_between_listing_and_fetch_is_excluded_and_named(w):
    _push(w, BRANCH, "a")

    def run(argv, **kw):
        got = w.gh(argv, **kw)
        if "ls-remote" in argv:
            _push(w, BRANCH, "b")  # the builder pushes again after the listing
        return got

    got = CR.pushed(w.root, 17, repo=REPO, run=run)
    assert got["newest"] is None and got["ambiguous"] is False
    assert [(b["branch"], b["reason"]) for b in got["branches"]] == [(BRANCH, "branch-moved-during-read")]


def test_pushed_checks_its_arguments(w):
    assert CR.pushed(w.root, 17, repo="not a repo", run=w.gh)["reason"] == "repo-invalid"
    assert CR.pushed(w.root, 0, repo=REPO, run=w.gh)["reason"] == "issue-invalid"
    assert CR.pushed(w.root, True, repo=REPO, run=w.gh)["reason"] == "issue-invalid"


# ---------------------------------------------------------------- the lane and the ledger


def test_an_unknown_lane_a_local_lane_and_an_unreadable_ledger_are_refused(w, monkeypatch):
    assert _assess(w, "nope")["reason"] == "lane-unknown"
    _local_lane(w, "local-1")
    for call in (lambda: _assess(w, "local-1"), lambda: CR.ask(w.root, "local-1"),
                 lambda: CR.asked(w.root, "local-1"), lambda: _successor(w, "local-1")):
        assert call() == {"ok": False, "reason": "lane-not-cloud"}
    with monkeypatch.context() as scoped:
        scoped.setattr(ll, "fold", lambda records: {"ok": False, "reason": "fold-x", "launches": {}})
        assert _assess(w, "local-1") == {"ok": False, "reason": "launch-ledger-unreadable"}
    with open(ll.ledger_path(w.root)["path"], "ab") as fh:
        fh.write(b"not json\n")
    assert _assess(w, "local-1") == {"ok": False, "reason": "launch-ledger-unreadable"}
    assert _successor(w, "local-1") == {"ok": False, "reason": "launch-ledger-unreadable"}


# ---------------------------------------------------------------- may the lane be recovered now


def test_p2_positive_stop_evidence_recovers_at_once_whatever_the_activity_age(w):
    _lane(w, "l1")
    out = _assess(w, state="failed", age=30)
    assert out["verdict"] == "stopped" and out["evidence"] == "session-failed"


VERDICTS = [
    ("failed", 30, "stopped", "session-failed"),
    ("archived", None, "stopped", "session-archived"),
    ("absent", 5, "stopped", "session-absent"),
    ("working", 60, "working", None),
    ("blocked", 0, "working", None),
    ("working", WINDOW, "working", None),
    ("working", WINDOW + 1, "ask-to-push", None),
    ("blocked", WINDOW + 1, "ask-to-push", None),
    ("working", -5, "ask-to-push", None),
    ("working", None, "unresolved", "activity-unknown"),
    ("blocked", None, "unresolved", "activity-unknown"),
    ("unread", None, "unresolved", "session-unread"),
    ("unread", 60, "unresolved", "session-unread"),
    ("idle", None, "ask-to-push", None),
    ("idle", 60, "ask-to-push", None),
    ("completed", WINDOW + 1, "ask-to-push", None),
    ("review-ready", None, "ask-to-push", None),
]


@pytest.mark.parametrize("state,age,verdict,evidence", VERDICTS)
def test_the_verdict_for_each_session_state_and_activity_age(w, state, age, verdict, evidence):
    _lane(w, "l1")
    out = _assess(w, state=state, age=age)
    assert (out["verdict"], out["evidence"]) == (verdict, evidence)
    assert out["handover"] is None and out["handoverRead"] == "ok" and out["issue"] == 17
    assert (out["cloudSessionName"], out["cloudSessionId"], out["configDir"]) == ("cloud-l1", "session_l1", "/cfg/acct")
    assert os.path.exists(_state_file(w)) is (verdict == "stopped")


def test_t3_a_working_lane_with_recent_activity_is_refused_not_recovered(w):
    _lane(w, "l1")
    out = _assess(w, state="working", age=60)
    assert out["verdict"] == "working" and out["stoppedAt"] is None


def test_p5_a_lane_the_ledger_still_holds_live_never_gets_a_successor(w):
    _push(w, BRANCH, "a")
    _lane(w, "l1")
    assert _assess(w, state="failed")["verdict"] == "stopped"
    assert _successor(w) == {"ok": False, "reason": "lane-not-ended"}  # assessed stopped, but not recorded died
    assert _state(w)["superseded"] == {}
    _died(w, "l1")
    assert _successor(w)["ok"] is True


def test_p6_a_lane_ended_without_an_assess_that_returned_stopped_never_gets_a_successor(w):
    _push(w, BRANCH, "a")
    _lane(w, "l1")
    _died(w, "l1")
    assert _successor(w) == {"ok": False, "reason": "lane-not-assessed-stopped"}
    _lane(w, "l2", 18)
    assert _assess(w, "l2", state="working", age=60)["verdict"] == "working"  # a refusal verdict records nothing
    _died(w, "l2")
    assert _successor(w, "l2") == {"ok": False, "reason": "lane-not-assessed-stopped"}


def test_a_lane_already_handed_back_in_the_ledger_assesses_as_ended_and_records_nothing(w):
    _lane(w, "l1")
    _died(w, "l1", "handback")
    out = _assess(w, state="failed")
    assert out["ok"] is True and out["verdict"] == "ended"
    assert not os.path.exists(_state_file(w))


def test_a_parked_lane_whose_session_failed_is_assessed_stopped_until_a_successor_is_composed(w):
    _push(w, BRANCH, "a")
    _lane(w, "l1")
    _died(w, "l1", "park")
    assert _assess(w, state="archived")["verdict"] == "stopped"
    assert _successor(w)["ok"] is True
    assert _assess(w, state="archived")["verdict"] == "stopped"  # no replacement has started: the recovery is still owed
    _lane(w, "l2")
    assert _assess(w, state="archived")["verdict"] == "ended"


def test_assess_checks_its_arguments(w):
    _lane(w, "l1")
    assert _assess(w, state="sleeping") == {"ok": False, "reason": "session-state-invalid"}
    assert _assess(w, state=None) == {"ok": False, "reason": "session-state-invalid"}
    assert _assess(w, state="idle", age="soon")["reason"] == "activity-age-invalid"
    assert _assess(w, state="idle", age=True)["reason"] == "activity-age-invalid"
    assert CR.assess(w.root, "l1", session_state="idle", repo="nope", run=w.gh)["reason"] == "repo-invalid"


def test_a_stopped_verdict_without_a_handover_records_no_stop_time(w):
    _lane(w, "l1")
    now = _at(10, 0, 30)
    out = _assess(w, state="archived", age=30, now=now)
    assert out["stoppedAt"] is None  # GitHub activity age is not when the session stopped
    assert _state(w)["assessed"] == {"l1": {"verdict": "stopped", "evidence": "session-archived",
                                            "at": "2026-10-12T10:00:30Z", "stoppedAt": None, "handoverSha": None}}


def test_a_state_that_cannot_be_written_refuses_the_stopped_verdict(w, monkeypatch):
    _lane(w, "l1")
    monkeypatch.setattr(CR, "_save", lambda path, data: False)
    assert _assess(w, state="failed") == {"ok": False, "reason": "recover-state-unwritable"}


# ---------------------------------------------------------------- the handover comment


def test_a_handover_comment_after_the_start_stops_the_lane_and_names_its_head(w):
    _lane(w, "l1")
    sha = "a" * 40
    w.gh.comments = [_comment("an unrelated note", 900, 1), _comment(_handover_body("b" * 40), 700, 2),
                     _comment(_handover_body(sha), 500, 3)]
    out = _assess(w, state="idle")
    assert out["verdict"] == "stopped" and out["evidence"] == "handover"
    assert out["handover"]["sha"] == sha and out["handover"]["commentId"] == 3
    assert out["handover"]["url"].endswith("issuecomment-3")
    assert out["stoppedAt"] == pytest.approx(time.time() - 500, abs=5)
    assert _state(w)["assessed"]["l1"]["handoverSha"] == sha


def test_a_footered_handover_comment_stops_the_lane(w):
    _lane(w, "l1")
    sha = "c" * 40
    w.gh.comments = [_comment(cloud_builder.handover_text(sha) + "\n\n" + cloud_builder.HANDOVER_FOOTER, 500, 3)]
    out = _assess(w, state="idle")
    assert out["verdict"] == "stopped" and out["evidence"] == "handover"
    assert out["handover"]["sha"] == sha
    assert _state(w)["assessed"]["l1"]["handoverSha"] == sha


def test_e16_a_handover_comment_older_than_the_lane_is_ignored(w):
    _lane(w, "l1", start_age=7200)
    w.gh.comments = [_comment(_handover_body("a" * 40), 9000)]
    out = _assess(w, state="idle")
    assert out["verdict"] == "ask-to-push" and out["handover"] is None


@pytest.mark.parametrize("body", ["Builder handover (cloud build). I pushed.", "see " + _handover_body("a" * 40),
                                  HEADER + "\n\nMy pushed head is " + "a" * 39 + ".",
                                  _handover_body("a" * 40).replace("stopped working", "am still working"),
                                  _handover_body("a" * 40) + "\n\n" + HEADER])
def test_a_comment_that_is_not_a_whole_handover_does_not_count(w, body):
    _lane(w, "l1")
    w.gh.comments = [_comment(body)]
    assert _assess(w, state="idle")["verdict"] == "ask-to-push"


def test_e8_a_comment_read_that_fails_never_stops_the_lane_by_handover(w):
    _lane(w, "l1")
    w.gh.comments_fail = True
    out = _assess(w, state="idle")
    assert out["verdict"] == "ask-to-push" and out["handover"] is None and out["handoverRead"] == "failed"
    assert _assess(w, state="failed")["verdict"] == "stopped"  # positive stop evidence needs no comment


# ---------------------------------------------------------------- the ask to push


def test_the_push_ask_is_the_agreed_words():
    assert CR.PUSH_ASK == (
        "Another builder is about to take this issue over. Push every commit you have now, then post the "
        "handover comment on this issue: run python3 -B <plugin root>/lib/cloud_builder.py handover --head "
        "<your pushed head sha> and post the comment field of its output, as it is. Then stop working on this issue and end your turn.")


def test_p4_a_second_ask_after_the_first_was_delivered_is_refused(w):
    _lane(w, "l1")
    assert CR.ask(w.root, "l1")["ok"] is True
    assert CR.asked(w.root, "l1")["ok"] is True
    assert CR.ask(w.root, "l1") == {"ok": False, "reason": "already-asked"}


def test_ask_composes_again_until_the_delivery_is_recorded(w):
    _lane(w, "l1")
    first = CR.ask(w.root, "l1")
    assert first == {"ok": True, "launchId": "l1", "cloudSessionName": "cloud-l1", "configDir": "/cfg/acct",
                     "text": CR.PUSH_ASK}
    assert CR.ask(w.root, "l1") == first  # nothing is recorded by composing it
    assert not os.path.exists(_state_file(w))


def test_an_unconfirmed_ask_is_not_asked_again_and_a_later_confirmation_upgrades_it(w):
    _lane(w, "l1")
    assert CR.asked(w.root, "l1", uncertain=True) == {"ok": True, "unchanged": False, "outcome": "uncertain"}
    assert CR.ask(w.root, "l1")["reason"] == "already-asked"
    assert _assess(w, state="idle")["verdict"] == "awaiting-handover"
    assert CR.asked(w.root, "l1", uncertain=True) == {"ok": True, "unchanged": True}
    assert CR.asked(w.root, "l1") == {"ok": True, "unchanged": False, "outcome": "delivered"}
    assert _state(w)["asks"]["l1"]["outcome"] == "delivered"
    assert CR.asked(w.root, "l1") == {"ok": True, "unchanged": True}
    assert CR.asked(w.root, "l1", uncertain=True) == {"ok": True, "unchanged": True}
    assert _state(w)["asks"]["l1"]["outcome"] == "delivered"


def test_t4_a_stalled_builder_that_answers_is_recovered_from_the_head_it_handed_over(w):
    first = _push(w, BRANCH, "a")
    _lane(w, "l1")
    assert _assess(w, state="idle")["verdict"] == "ask-to-push"
    ask = CR.ask(w.root, "l1")
    assert ask["text"] == CR.PUSH_ASK
    assert CR.asked(w.root, "l1")["ok"] is True
    assert CR.ask(w.root, "l1")["reason"] == "already-asked"
    assert _assess(w, state="idle")["verdict"] == "awaiting-handover"
    newer = _push(w, BRANCH, "b")  # the builder answers the ask: pushes, then posts the handover
    cb_out = _run_handover(newer)  # what the ask tells the builder to run, and its comment field is what it posts
    w.gh.comments = [_comment(cb_out["comment"])]
    out = _assess(w, state="idle")
    assert (out["verdict"], out["evidence"], out["handover"]["sha"]) == ("stopped", "handover", newer)
    _died(w, "l1")
    got = _successor(w)
    assert got["ok"] is True and got["premise"]["adoptsHead"] == newer != first
    assert got["premise"]["adoptsBranch"] == BRANCH and got["premise"]["baseCommit"] == w.base


def test_a_handover_head_that_is_not_pushed_gives_no_successor(w):
    _push(w, BRANCH, "a")
    _lane(w, "l1")
    w.gh.comments = [_comment(_handover_body("c" * 40))]
    assert _assess(w, state="idle")["verdict"] == "stopped"
    _died(w, "l1")
    assert _successor(w) == {"ok": False, "reason": "handover-head-not-pushed"}


# ---------------------------------------------------------------- the successor


def _cli_launch(w, tmp_path, monkeypatch, premise, placement):
    (tmp_path / "premise.json").write_text(json.dumps(premise))
    (tmp_path / "checks.json").write_text("{}")
    seen = {}

    def launch_build(repo_root, issue, premise, checks, log_dir, **kwargs):
        seen.update(premise=premise, kwargs=kwargs)
        return {"ok": True, "launchId": "l-new"}

    monkeypatch.setattr(L.launch_place, "route", lambda cwd, premise, word=None, **kw: placement)
    monkeypatch.setattr(L, "launch_build", launch_build)
    args = argparse.Namespace(
        repo_root=w.root, issue=17, premise=str(tmp_path / "premise.json"), checks=str(tmp_path / "checks.json"),
        log_dir=str(tmp_path / "logs"), model=None, effort=None, slot=None, generation=None, boundary=None,
        allow_foreign_instance=False, place=None, cloud_environment=None, batch=None)
    return L._cli_launch(args), seen


def _placement(place, **over):
    base = {"place": place, "pointedAtCloud": True, "by": "setting", "reason": None, "need": None,
            "cloudVersion": "1.2.3", "advisorVersion": "1.2.3", "environment": "env-1" if place == "cloud" else None,
            "reported": None, "failedCheck": None}
    base.update(over)
    return base


def _stopped_lane_with_work(w):
    sha = _push(w, BRANCH, "a")
    w.gh.activity[BRANCH] = [_event(BRANCH, sha, _stamp(9, 55))]
    _lane(w, "l1")
    assert _assess(w, state="failed", age=30)["verdict"] == "stopped"
    _died(w, "l1")
    return sha


def test_t1_the_successor_premise_adopts_the_pushed_branch_and_passes_the_launch_boundary(w, tmp_path, monkeypatch):
    sha = _push(w, BRANCH, "a")
    w.gh.activity[BRANCH] = [_event(BRANCH, sha, _stamp(9, 55))]
    _lane(w, "l1")
    assert _assess(w, state="failed", age=30)["verdict"] == "stopped"
    _died(w, "l1")
    got = _successor(w)
    assert got["ok"] is True and got["neverPushed"] is False and got["branch"] == BRANCH and got["sha"] == sha
    assert (got["pushedAt"], got["pushTimeSource"]) == (_at(9, 55), "push")
    premise = got["premise"]
    assert premise["baseCommit"] == w.base != sha  # the lane's own base is kept; the pushed work rides beside it
    assert premise["adoptsBranch"] == BRANCH and premise["adoptsHead"] == sha
    assert "placeCall" not in premise and "standingExclusions" not in premise
    original = _premise(w, 17)
    for key in set(original) - set(CR._LAUNCHER_STAMPED):
        assert premise[key] == original[key]
    assert _has_object(w.root, sha)  # the pushed head was fetched into this clone
    accepted = L.validate_premise(premise, w.root)  # the real launcher check, not a stand-in
    assert accepted["ok"] is True and accepted["resolvedBaseCommit"] == w.base
    assert L.validate_premise(dict(premise, adoptsHead="abc"), w.root)["reason"] == "premise-adopts-head-invalid"
    stamp = _placement("cloud")
    result, seen = _cli_launch(w, tmp_path, monkeypatch, premise, stamp)
    assert result.get("reason") != "premise-place-call-caller-set" and result["ok"] is True
    assert seen["premise"]["adoptsBranch"] == BRANCH and seen["premise"]["adoptsHead"] == sha
    assert seen["premise"]["baseCommit"] == w.base
    assert seen["premise"]["placeCall"] == stamp and seen["kwargs"]["place"] == "cloud"
    assert _state(w)["superseded"]["l1"]["branch"] == BRANCH and _state(w)["superseded"]["l1"]["sha"] == sha


def _membership(monkeypatch, got):
    monkeypatch.setattr(CR._sib("stack_check"), "read_membership", lambda **k: got)


def test_a_pull_request_not_linked_into_the_stack_is_not_adopted_and_an_unreadable_stack_refuses(w, monkeypatch):
    _push(w, BRANCH, "a")
    _lane(w, "l1")
    assert _assess(w, state="failed")["verdict"] == "stopped"
    _died(w, "l1")
    w.gh.pulls = [{"number": 99}]
    _membership(monkeypatch, {"ok": False, "reason": "boom"})
    assert _successor(w) == {"ok": False, "reason": "stack-membership-unreadable"}
    _membership(monkeypatch, {"ok": False, "reason": CR._sib("stack_check").REASON_NOT_LINKED})
    assert "adopts" not in _successor(w)["premise"]


def test_a_stack_layer_that_opened_its_pull_request_is_relaunched_through_the_real_stack_gate(w, monkeypatch):
    sha = _push(w, BRANCH, "a")  # the original layer-2 premise has no adopts: its pull request did not exist yet
    _lane(w, "l1")
    assert _assess(w, state="failed")["verdict"] == "stopped"
    _died(w, "l1")
    w.gh.pulls = [{"number": 99}]
    member = {"position": 2, "number": 99, "baseRefName": "layer-1", "headRefName": BRANCH, "headRefOid": sha}
    below = {"position": 1, "headRefName": "layer-1", "headRefOid": w.base}
    _membership(monkeypatch, {"ok": True, "queried": below, "members": [member]})
    premise = _successor(w)["premise"]
    assert premise["adopts"] == 99
    gate = L._apply_stack_gate(
        dict(premise, **{"stack": 2}), w.base, w.root, {},
        lambda *a, **k: {"ok": True, "pr": 5, "repo": REPO},
        lambda **k: {"ok": True, "queried": below, "members": [member]})
    assert gate["ok"] is True and gate["stackGate"]["adopts"] == 99


def test_the_launch_boundary_does_refuse_a_premise_that_still_carries_the_launchers_stamp(w, tmp_path, monkeypatch):
    sha = _push(w, BRANCH, "a")
    premise = dict(_premise(w, 17), baseCommit=sha, adoptsBranch=BRANCH)
    result, seen = _cli_launch(w, tmp_path, monkeypatch, premise, _placement("cloud"))
    assert result == {"ok": False, "reason": "premise-place-call-caller-set"} and seen == {}


def test_t2_when_the_cloud_is_not_ready_the_same_premise_reaches_the_local_path(w, tmp_path, monkeypatch):
    sha = _stopped_lane_with_work(w)
    premise = _successor(w)["premise"]
    stamp = _placement("local", reason="version")
    result, seen = _cli_launch(w, tmp_path, monkeypatch, premise, stamp)
    assert result["ok"] is True and result["placeCall"] == stamp
    assert seen["premise"]["adoptsBranch"] == BRANCH and seen["premise"]["adoptsHead"] == sha
    assert seen["premise"]["baseCommit"] == w.base
    assert "place" not in seen["kwargs"] and seen["kwargs"]["slot"] is None


def test_t6_a_lane_that_never_pushed_is_relaunched_from_its_original_base(w):
    _push(w, "issue-18-work", "other")
    stale = dict(_premise(w, 17), adoptsBranch="stale-branch", adoptsHead="f" * 40)
    _lane(w, "l1", premise=stale)
    assert _assess(w, state="absent")["verdict"] == "stopped"
    _died(w, "l1")
    assert _successor(w)["reason"] == "pushed-work-unknown"  # no matching branch is not proof of no pushed work
    assert _successor(w, never_pushed_evidence=" ") == {"ok": False, "reason": "never-pushed-evidence-invalid"}
    got = _successor(w, never_pushed_evidence="remote branches and PRs for #17")
    assert got["ok"] is True and got["neverPushed"] is True
    assert (got["branch"], got["sha"], got["pushedAt"]) == (None, None, None)
    assert got["premise"]["baseCommit"] == w.base
    assert "adoptsBranch" not in got["premise"] and "adoptsHead" not in got["premise"]
    assert "placeCall" not in got["premise"] and "standingExclusions" not in got["premise"]
    assert _state(w)["superseded"]["l1"]["branch"] is None
    assert _state(w)["superseded"]["l1"]["neverPushedEvidence"] == "remote branches and PRs for #17"
    assert CR.message(17, place="cloud", stopped_at=_at(10, 0), never_pushed=True, tz=UTC)["text"] == (
        "The cloud builder on #17 stopped at 10:00. It never pushed, so I relaunched the build from the beginning "
        "in a new cloud session.")


def test_e4_two_qualifying_branches_give_no_successor_and_there_is_no_way_to_name_one(w, capsys):
    _push(w, "issue-17-a", "a")
    _push(w, "issue-17-b", "b")
    _lane(w, "l1")
    got = CR.pushed(w.root, 17, repo=REPO, run=w.gh)
    assert got["ambiguous"] is True and got["newest"] is None and len(got["branches"]) == 2
    assert _assess(w, state="failed")["verdict"] == "stopped"
    _died(w, "l1")
    assert _successor(w) == {"ok": False, "reason": "pushed-branch-ambiguous"}
    with pytest.raises(TypeError):
        _successor(w, branch="issue-17-b")
    assert CR.main(["successor", "--repo-root", w.root, "--launch-id", "l1", "--repo", REPO,
                    "--branch", "issue-17-b"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "usage"}
    assert "l1" not in _state(w)["superseded"]


def test_a_recorded_handover_head_picks_the_one_pushed_branch_that_carries_it(w):
    _push(w, "issue-17-a", "a")
    named = _push(w, "issue-17-b", "b")
    _lane(w, "l1")
    w.gh.comments = [_comment(_handover_body(named))]
    assert _assess(w, state="idle")["verdict"] == "stopped"
    _died(w, "l1")
    chosen = _successor(w)
    assert chosen["ok"] is True and chosen["branch"] == "issue-17-b" and chosen["sha"] == named
    assert chosen["premise"]["adoptsBranch"] == "issue-17-b" and chosen["premise"]["adoptsHead"] == named
    assert chosen["premise"]["baseCommit"] == w.base


def test_an_adopted_branch_without_the_issue_number_is_found(w):
    head = _push(w, "feature/login", "a")
    _lane(w, "l1", premise=dict(_premise(w, 17), adoptsBranch="feature/login"))
    w.gh.comments = [_comment(_handover_body(head))]
    assert _assess(w, state="idle")["verdict"] == "stopped"
    _died(w, "l1")
    assert _successor(w)["branch"] == "feature/login"


def test_a_working_session_is_not_stopped_by_an_earlier_handover(w):
    _lane(w, "l1")
    w.gh.comments = [_comment(_handover_body("a" * 40))]
    assert _assess(w, state="working", age=60)["verdict"] == "working"


def test_a_later_working_reading_withdraws_the_stop_authorization(w):
    _push(w, BRANCH, "a")
    _lane(w, "l1")
    assert _assess(w, state="failed")["verdict"] == "stopped"
    _died(w, "l1")
    assert _assess(w, state="working", age=60)["verdict"] == "working"
    assert _successor(w) == {"ok": False, "reason": "lane-not-assessed-stopped"}


def test_a_working_reading_during_successors_remote_reads_withdraws_the_stop_authorization(w):
    _push(w, BRANCH, "a")
    _lane(w, "l1")
    assert _assess(w, state="failed")["verdict"] == "stopped"
    _died(w, "l1")

    def run(argv, **kw):
        if "ls-remote" in argv:
            assert _assess(w, state="working", age=60)["verdict"] == "working"
        return w.gh(argv, **kw)
    assert CR.successor(w.root, "l1", repo=REPO, run=run) == {"ok": False, "reason": "lane-not-assessed-stopped"}
    assert _state(w)["superseded"] == {}


def test_a_parked_lane_that_later_handed_back_is_ended_not_stopped(w):
    _lane(w, "l1")
    _died(w, "l1", "park")
    assert ll.record_outcome(w.root, "l1", "handback", "done")["ok"]
    assert _assess(w, state="archived")["verdict"] == "ended"


def test_an_ended_assessment_withdraws_an_earlier_stop(w):
    _lane(w, "l1")
    _died(w, "l1", "park")
    assert _assess(w, state="archived")["verdict"] == "stopped"
    assert ll.record_outcome(w.root, "l1", "handback", "done")["ok"]
    assert _assess(w, state="archived")["verdict"] == "ended"
    assert _state(w)["assessed"] == {}


def test_a_handback_recorded_during_the_successors_remote_reads_refuses_it(w):
    _push(w, BRANCH, "a")
    _lane(w, "l1")
    _died(w, "l1", "park")
    assert _assess(w, state="archived")["verdict"] == "stopped"

    def run(argv, **kw):
        if "ls-remote" in argv:
            assert ll.record_outcome(w.root, "l1", "handback", "done")["ok"]
        return w.gh(argv, **kw)
    assert CR.successor(w.root, "l1", repo=REPO, run=run) == {"ok": False, "reason": "lane-not-assessed-stopped"}
    assert _state(w)["superseded"] == {}


def test_a_handover_head_carried_by_two_pushed_branches_is_ambiguous(w):
    head = _push(w, "issue-17-a", "a")
    _git(w.builder, "push", "-q", "origin", "issue-17-a:refs/heads/issue-17-b")
    _lane(w, "l1")
    w.gh.comments = [_comment(_handover_body(head))]
    assert _assess(w, state="idle")["verdict"] == "stopped"
    _died(w, "l1")
    assert _successor(w) == {"ok": False, "reason": "pushed-branch-ambiguous"}


def test_a_branch_that_could_not_be_read_cleanly_is_never_taken_for_no_work(w, monkeypatch):
    _lane(w, "l1")
    assert _assess(w, state="failed")["verdict"] == "stopped"
    _died(w, "l1")
    moved = {"branch": BRANCH, "sha": "a" * 40, "reason": "branch-moved-during-read"}
    monkeypatch.setattr(CR, "pushed", lambda *a, **k: {"ok": True, "issue": 17, "branches": [moved],
                                                       "newest": None, "ambiguous": False})
    assert _successor(w) == {"ok": False, "reason": "pushed-branch-unreadable"}


def test_a_remote_that_cannot_be_read_refuses_the_successor(w):
    _lane(w, "l1")
    assert _assess(w, state="failed")["verdict"] == "stopped"
    _died(w, "l1")
    _git(w.root, "remote", "set-url", "origin", str(w.tmp / "nowhere.git"))
    assert _successor(w) == {"ok": False, "reason": "remote-unreadable"}
    assert "l1" not in _state(w)["superseded"]


# ---------------------------------------------------------------- the state file


def test_e13_a_state_file_that_cannot_be_read_refuses_and_is_never_overwritten(w):
    _lane(w, "l1")
    _died(w, "l1")
    for junk in ("{not json", "[]", '{"asks": []}', '{"mystery": {}}', '{"asks": {"l1": {"outcome": "maybe"}}}'):
        with open(_state_file(w), "w", encoding="utf-8") as fh:
            fh.write(junk)
        for refused in (CR.ask(w.root, "l1"), CR.asked(w.root, "l1"), _successor(w)):
            assert refused == {"ok": False, "reason": "recover-state-unreadable"}
        assert CR.superseded_ids(w.root) == (set(), False)
        with open(_state_file(w), encoding="utf-8") as fh:
            assert fh.read() == junk


def test_a_corrupt_state_stops_an_assess_that_needs_it_and_leaves_it_alone(w):
    _lane(w, "l1")
    with open(_state_file(w), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert _assess(w, state="idle") == {"ok": False, "reason": "recover-state-unreadable"}
    assert _assess(w, state="failed") == {"ok": False, "reason": "recover-state-unreadable"}
    assert _assess(w, state="working", age=60)["verdict"] == "working"  # needs no state
    with open(_state_file(w), encoding="utf-8") as fh:
        assert fh.read() == "{not json"


def test_superseded_ids_reads_the_lanes_a_successor_was_composed_for(w):
    assert CR.superseded_ids(w.root) == (set(), True)
    _push(w, BRANCH, "a")
    _lane(w, "l1")
    assert _assess(w, state="failed")["verdict"] == "stopped"
    _died(w, "l1")
    assert _successor(w)["ok"] is True
    assert CR.superseded_ids(w.root) == ({"l1"}, True)


# ---------------------------------------------------------------- the board's words


def test_the_board_sentence_is_the_boards_own_words():
    out = CR.message(412, place="cloud", stopped_at=_at(14, 2), pushed_at=_at(14, 2) - 360, tz=UTC)
    assert out == {"ok": True, "text": (
        "The cloud builder on #412 stopped at 14:02. I recovered the lane from its pushed work in a new cloud "
        "session. About 6 minutes of work since its last push is being redone.")}


def test_t5_the_minutes_redone_are_counted_from_the_last_push(w):
    def text(seconds, **kw):
        return CR.message(17, place="cloud", stopped_at=_at(10, 0), pushed_at=_at(10, 0) - seconds, tz=UTC, **kw)["text"]

    assert "About 6 minutes of work" in text(370)
    assert "About 1 minute of work" in text(60) and "1 minutes" not in text(60)
    assert text(0).endswith("No work since its last push is lost.")
    assert text(-300).endswith("No work since its last push is lost.")
    assert text(0.5).endswith("Less than a minute of work since its last push is being redone.")
    assert text(1).endswith("Less than a minute of work since its last push is being redone.")
    assert text(30).endswith("Less than a minute of work since its last push is being redone.")
    assert text(59).endswith("Less than a minute of work since its last push is being redone.")
    assert text(30, push_time_source="commit").endswith(
        "Less than a minute of work since its last pushed commit is being redone.")
    assert text(60).endswith("About 1 minute of work since its last push is being redone.")
    assert text(119 * 60).endswith("About 119 minutes of work since its last push is being redone.")
    assert text(120 * 60).endswith("About 2 hours of work since its last push is being redone.")
    assert text(4320 * 60).endswith("About 72 hours of work since its last push is being redone.")
    assert text(1800, push_time_source="commit").endswith("About 30 minutes of work since its last pushed commit is being redone.")
    assert CR.message(17, place="local", stopped_at=_at(10, 0), pushed_at=_at(9, 54), tz=UTC)["text"] == (
        "The cloud builder on #17 stopped at 10:00. I recovered the lane from its pushed work on your machine. "
        "About 6 minutes of work since its last push is being redone.")


def test_t5_a_delayed_push_is_counted_from_the_push_not_the_commit(w):
    _push(w, BRANCH, "a", when="2026-10-12T08:00:00+0000")
    w.gh.activity[BRANCH] = [_event(BRANCH, _git(w.builder, "rev-parse", "HEAD"), _stamp(9, 55))]
    _lane(w, "l1")
    stopped = _at(10, 0)
    entry = CR.pushed(w.root, 17, repo=REPO, run=w.gh)["newest"]
    assert entry["pushTimeSource"] == "push" and entry["committedAt"] == _at(8, 0)
    assert "About 5 minutes of work since its last push" in CR.message(
        17, place="cloud", stopped_at=stopped, pushed_at=entry["pushedAt"], tz=UTC)["text"]
    w.gh.activity.clear()  # the activity read fails: the commit time stands in, and the words say so
    entry = CR.pushed(w.root, 17, repo=REPO, run=w.gh)["newest"]
    assert entry["pushTimeSource"] == "commit"
    assert "About 2 hours of work since its last pushed commit" in CR.message(
        17, place="cloud", stopped_at=stopped, pushed_at=entry["pushedAt"], push_time_source="commit", tz=UTC)["text"]


def test_a_stop_time_that_is_not_known_leaves_the_time_out(w):
    assert CR.message(17, place="cloud", stopped_at=None, pushed_at=_at(9, 0))["text"] == (
        "The cloud builder on #17 stopped. I recovered the lane from its pushed work in a new cloud session.")
    assert CR.message(17, place="local", stopped_at=None, never_pushed=True)["text"] == (
        "The cloud builder on #17 stopped. It never pushed, so I relaunched the build from the beginning on your machine.")


def test_message_checks_its_arguments():
    assert CR.message(17, place="mars", stopped_at=None)["reason"] == "place-invalid"
    assert CR.message(0, place="cloud", stopped_at=None)["reason"] == "issue-invalid"
    assert CR.message(17, place="cloud", stopped_at=None, push_time_source="clock")["reason"] == "push-time-source-invalid"
    assert CR.message(17, place="cloud", stopped_at="noon")["reason"] == "time-invalid"


# ---------------------------------------------------------------- relaunch after a version-mismatch refusal


MISMATCH = cloud_builder._refusal_comment("plugin-version-mismatch", running="1.2.2", launched="1.2.3")
UNSTACKED = {k: v for k, v in _premise(SimpleNamespace(base="0" * 40), 17).items() if k not in ("stack", "layerPosition")}


def _relaunch(w, launch_id="l1"):
    return CR.relaunch_refusal(w.root, launch_id, repo=REPO, run=w.gh)


def _refused_lane(w, *bodies):
    _lane(w, "l1", premise=dict(UNSTACKED, baseCommit=w.base))
    _died(w, "l1", outcome="refusal")
    w.gh.comments = [_comment(b, age=600 - i, cid=i + 1) for i, b in enumerate(bodies)]


def test_t_r1_a_version_mismatch_refusal_relaunches_on_the_owners_machine_naming_both_versions(w):
    _refused_lane(w, MISMATCH)
    got = _relaunch(w)
    assert got["ok"] is True and (got["cloudVersion"], got["advisorVersion"], got["issue"]) == ("1.2.2", "1.2.3", 17)
    premise = got["premise"]
    assert premise["reportedCloud"] == {"pluginVersion": "1.2.2"}
    assert "placeCall" not in premise and "standingExclusions" not in premise
    assert L.validate_premise(premise, w.root)["ok"] is True  # the real launcher check
    assert not os.path.exists(_state_file(w))  # nothing is recorded

    def readiness(cwd, **kw):
        # A stub shaped as `cloud_ready._result` shapes a version mismatch: the real `readiness` needs a cloud
        # setup record, a calibration stamp and a project setting, none of which this fixture has, and without
        # them it reports no cloud version at all.
        conditions = {name: name != "version" for name in cloud_ready.CONDITION_ORDER}
        return cloud_ready._result(conditions, setting=False, cloud_version=kw["reported"]["pluginVersion"],
                                   advisor_version="1.2.3")

    # The real routing step; `needs_fn` is also stubbed (to no needs) because the fixture repository keeps no Canon or
    # specs in-repo, which the real `machine_needs` reads as a need of the owner's machine and would answer "needs".
    # The cloud setting is off here: the launch word is what points the build at the cloud, so the report names both.
    placement = launch_place.route(w.root, premise, launch_place.CLOUD_WORD, readiness_fn=readiness,
                                   needs_fn=lambda *a, **k: [])
    assert placement["place"] == "local" and placement["reason"] == "version"
    assert "1.2.2" in launch_place.reason_text(placement) and "1.2.3" in launch_place.reason_text(placement)

    # Without the word, and with the setting off, nothing points at the cloud: the report names neither version.
    # That is why the doctrine's relaunch passes the word.
    wordless = launch_place.route(w.root, premise, readiness_fn=readiness, needs_fn=lambda *a, **k: [])
    assert launch_place.reason_text(wordless) is None


def test_the_relaunch_doctrine_passes_the_cloud_word():
    doctrine = os.path.join(os.path.dirname(__file__), "..", "..", "skills", "showrunner", "reference",
                            "orchestration.md")
    with open(doctrine, encoding="utf-8") as f:
        paragraphs = re.split(r"\n\s*\n", f.read())
    [relaunch] = [p for p in paragraphs if "relaunch-refusal" in p]
    assert "launcher.py launch --place cloud" in " ".join(relaunch.split())


def test_t_r1b_a_second_relaunch_cannot_make_two_builders(w):
    _lane(w, "l1")  # one live cloud launch for issue 17
    again = {"event": "reserved", "launchId": "l2", "ts": time.time(), "schema": ll.SCHEMA, "batchId": BATCH,
             "repoId": ll.repo_identity(w.root), "issue": 17, "surfaces": ["plugins/y"], "premise": {}, "preflight": {},
             "argv": [], "doctrineDigest": "abc123", "model": "test-model", "place": ll.PLACE_CLOUD,
             "cloudEnvironment": "env-1", "pluginVersion": "1.2.3", "configDir": "/cfg/acct"}
    got = ll.reserve(w.root, again)
    assert got["ok"] is False and got["reason"].startswith("surface-overlap:")


def test_a_relaunch_is_refused_for_a_live_lane_and_for_a_lane_that_did_not_end_in_refusal(w):
    _lane(w, "l1", premise=dict(UNSTACKED, baseCommit=w.base))
    w.gh.comments = [_comment(MISMATCH)]
    assert _relaunch(w) == {"ok": False, "reason": "lane-not-ended"}
    _died(w, "l1")
    assert _relaunch(w) == {"ok": False, "reason": "lane-not-refusal"}


def test_a_relaunch_checks_its_arguments_and_the_lane(w):
    assert CR.relaunch_refusal(w.root, "", repo=REPO, run=w.gh) == {"ok": False, "reason": "launch-id-invalid"}
    assert _relaunch(w, "l-none") == {"ok": False, "reason": "lane-unknown"}


def test_a_relaunch_is_refused_when_the_comments_cannot_be_read(w):
    _refused_lane(w, MISMATCH)
    w.gh.comments_fail = True
    assert _relaunch(w) == {"ok": False, "reason": "comments-unreadable"}


@pytest.mark.parametrize("bodies", [
    [], ["Looks fine."], ["> " + MISMATCH], ["I saw this:\n\n" + MISMATCH], [MISMATCH + " Please retry."],
    [cloud_builder._refusal_comment("cloud-environment-mismatch", actual="env-a", expected="env-b")],
    [cloud_builder._refusal_comment("plugin-version-mismatch")],
], ids=["none", "unrelated", "quoted", "after-another-line", "edited", "other-refusal", "unreadable-version"])
def test_a_relaunch_needs_a_whole_version_mismatch_refusal_comment(w, bodies):
    _refused_lane(w, *bodies)
    assert _relaunch(w) == {"ok": False, "reason": "refusal-comment-missing"}


def test_a_refusal_comment_older_than_the_lane_is_ignored(w):
    _refused_lane(w)
    w.gh.comments = [_comment(MISMATCH, age=7200 + 3600)]
    assert _relaunch(w) == {"ok": False, "reason": "refusal-comment-missing"}


def test_an_old_refusal_comment_edited_after_the_reservation_is_ignored(w):
    _refused_lane(w)
    w.gh.comments = [dict(_comment(MISMATCH, age=7200 + 3600), updated_at=_iso_ago(60))]  # made an hour before the reservation, edited a minute ago
    assert _relaunch(w) == {"ok": False, "reason": "refusal-comment-missing"}


def test_a_refusal_posted_after_the_reservation_but_before_the_start_receipt_counts(w):
    _refused_lane(w)  # reserved 7260 seconds ago, started 7200
    w.gh.comments = [_comment(MISMATCH, age=7230)]
    assert _relaunch(w)["ok"] is True


def test_a_refusal_in_the_same_second_as_the_reservation_counts(w):
    _refused_lane(w)
    reserved = ll.fold(ll.read(w.root)["records"])["launches"]["l1"]["reservedTs"]
    at = datetime.datetime.fromtimestamp(int(reserved), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    w.gh.comments = [dict(_comment(MISMATCH), created_at=at, updated_at=at)]
    assert _relaunch(w)["ok"] is True


def test_a_refusal_lane_with_a_later_started_launch_is_refused_as_replaced(w):
    _refused_lane(w, MISMATCH)
    assert _relaunch(w)["ok"] is True
    _lane(w, "l2", start_age=60)  # a later launch for issue 17, started
    assert _relaunch(w) == {"ok": False, "reason": "lane-replaced"}


def test_with_two_refusal_comments_the_newest_wins(w):
    newer = cloud_builder._refusal_comment("plugin-version-mismatch", running="1.2.4", launched="1.2.3")
    _refused_lane(w, MISMATCH, newer)
    got = _relaunch(w)
    assert got["cloudVersion"] == "1.2.4" and got["premise"]["reportedCloud"] == {"pluginVersion": "1.2.4"}


def test_a_relaunch_with_a_lane_that_has_no_premise_is_refused(w):
    _lane(w, "l1", premise="gone")
    _died(w, "l1", outcome="refusal")
    w.gh.comments = [_comment(MISMATCH)]
    assert _relaunch(w) == {"ok": False, "reason": "lane-premise-unreadable"}


def test_refusal_versions_reads_only_a_whole_version_mismatch_comment():
    rv = cloud_builder.refusal_versions
    assert rv(MISMATCH) == ("1.2.2", "1.2.3") and rv("\n" + MISMATCH + "\n") == ("1.2.2", "1.2.3")
    assert rv(cloud_builder._refusal_comment("cloud-environment-mismatch", actual="a", expected="b")) is None
    assert rv(MISMATCH + " One more sentence.") is None
    assert rv("> " + MISMATCH) is None
    assert rv(None) is None and rv(12) is None


# ---------------------------------------------------------------- the resume table's cloud rows


def test_t_r2_a_cloud_lane_answers_working_and_stopped_for_the_resume_rows(w):
    _lane(w, "l1")
    assert _assess(w, state="working", age=60)["verdict"] == "working"
    assert _assess(w, state="archived")["verdict"] == "stopped"
    skill = os.path.join(os.path.dirname(__file__), "..", "..", "skills", "showrunner-resume", "SKILL.md")
    with open(skill, encoding="utf-8") as fh:
        text = fh.read()
    paragraph = next(p for p in text.split("\n\n") if p.startswith("**A cloud lane**"))
    assert "`cloud_recover.py assess`" in paragraph
    assert "`working` satisfies row 2" in paragraph and "`stopped` satisfies row 4" in paragraph
    assert "orchestration.md` § Adoption mechanics" in paragraph
    assert "`ask-to-push`" in paragraph and "(`ask`, then `asked`)" in paragraph and "`awaiting-handover`" in paragraph
    assert "still needs the pull-request read" in paragraph and "the park-record read" in paragraph
    assert "satisfies no row" in paragraph
    assert "`activityAgeSeconds`" in paragraph and "`relaunch-refusal`" in paragraph
    assert paragraph.index("`relaunch-refusal`") < paragraph.index("generic `ended` rule")


# ---------------------------------------------------------------- the one input check


def test_inputs_judges_only_the_arguments_it_is_handed_and_in_a_fixed_order():
    assert CR._inputs() is None
    assert CR._inputs(repo=REPO, issue=17, launch_id="l1", session_state="idle", activity_age_seconds=None,
                      place="local", stopped_at=None, pushed_at=1.5, push_time_source="commit") is None
    assert CR._inputs(place="mars") == "place-invalid"  # nothing else handed over, nothing else judged
    assert CR._inputs(issue=0, repo="nope") == "repo-invalid"  # the order is fixed, not the call's keyword order
    assert CR._inputs(push_time_source="clock", session_state="sleeping") == "session-state-invalid"


_BAD_INPUTS = [
    ("repo-shape", lambda w: CR.pushed(w.root, 17, repo="not a repo", run=w.gh), "repo-invalid"),
    ("repo-type", lambda w: CR.successor(w.root, "l1", repo=None, run=w.gh), "repo-invalid"),
    ("issue-zero", lambda w: CR.pushed(w.root, 0, repo=REPO, run=w.gh), "issue-invalid"),
    ("issue-bool", lambda w: CR.message(True, place="cloud", stopped_at=None), "issue-invalid"),
    ("launch-id-empty", lambda w: CR.ask(w.root, ""), "launch-id-invalid"),
    ("launch-id-type", lambda w: CR.asked(w.root, 7), "launch-id-invalid"),
    ("launch-id-assess", lambda w: _assess(w, launch_id=""), "launch-id-invalid"),
    ("launch-id-successor", lambda w: _successor(w, launch_id=None), "launch-id-invalid"),
    ("session-state", lambda w: _assess(w, state="sleeping"), "session-state-invalid"),
    ("activity-age-text", lambda w: _assess(w, state="idle", age="soon"), "activity-age-invalid"),
    ("activity-age-nan", lambda w: _assess(w, state="idle", age=float("nan")), "activity-age-invalid"),
    ("place", lambda w: CR.message(17, place="mars", stopped_at=None), "place-invalid"),
    ("time-stopped", lambda w: CR.message(17, place="cloud", stopped_at="noon"), "time-invalid"),
    ("time-pushed", lambda w: CR.message(17, place="cloud", stopped_at=None, pushed_at=float("inf")), "time-invalid"),
    ("push-time-source", lambda w: CR.message(17, place="cloud", stopped_at=None, push_time_source="clock"),
     "push-time-source-invalid"),
]


@pytest.mark.parametrize("call,token", [c[1:] for c in _BAD_INPUTS], ids=[c[0] for c in _BAD_INPUTS])
def test_e8_every_verb_refuses_an_input_the_shared_check_rejects(w, call, token):
    _lane(w, "l1")  # a real lane, so only the input check can be what refuses
    assert call(w) == {"ok": False, "reason": token}


# ---------------------------------------------------------------- the command line


_CENSUS = {
    "pushed": ["--repo-root", "{root}", "--repo", REPO, "--issue", "17"],
    "assess": ["--repo-root", "{root}", "--launch-id", "l-none", "--repo", REPO, "--session-state", "idle"],
    "ask": ["--repo-root", "{root}", "--launch-id", "l-none"],
    "asked": ["--repo-root", "{root}", "--launch-id", "l-none", "--uncertain"],
    "successor": ["--repo-root", "{root}", "--launch-id", "l-none", "--repo", REPO],
    "relaunch-refusal": ["--repo-root", "{root}", "--launch-id", "l-none", "--repo", REPO],
    "helper-read": ["--repo", REPO, "--issue", "17", "--session-id", "session_abc"],
    "message": ["--issue", "17", "--place", "cloud", "--stopped-at", "1760000000", "--pushed-at", "1759999000"],
}


def test_t10_the_census_covers_every_verb_the_module_lists():
    listed = set(re.findall(r"^  cloud_recover\.py (\S+)", CR.__doc__, re.M))
    parsed = set(CR._build_parser()._subparsers._group_actions[0].choices)
    assert listed == parsed == set(_CENSUS)


@pytest.mark.parametrize("verb", sorted(_CENSUS))
def test_t10_every_verb_prints_exactly_one_json_object_with_ok(w, verb, capsys):
    argv = [verb] + [a.replace("{root}", w.root) for a in _CENSUS[verb]]
    code = CR.main(argv)
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert isinstance(out, dict) and isinstance(out.get("ok"), bool)
    assert code == (0 if out["ok"] else 1)
    if out["ok"] is False:
        assert isinstance(out.get("reason"), str)


def test_t10_a_malformed_command_line_prints_one_refusal(capsys):
    assert CR.main(["pushed", "--repo-root"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "usage"}
