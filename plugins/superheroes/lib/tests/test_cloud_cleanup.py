# plugins/superheroes/lib/tests/test_cloud_cleanup.py
"""Conformance: the cleanup after a cloud lane ends -- the archive request to its builder and the PR's
branch. Every repository, ledger and state file is built under tmp_path. The `gh api` answers are a fake
`run`; the lease delete goes to a real local bare git repository named as the remote; nothing touches the
real home directory, clock or network."""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_cleanup as CC  # noqa: E402
import launch_ledger as ll  # noqa: E402

from test_launch_ledger import _declare, _init_repo, _ledger_env, _reserved, _started  # noqa: E402

REPO = "owner/name"
BATCH = "b-cleanup"
PR = 412
BRANCH = "feature"
IDENT = ["-c", "user.name=t", "-c", "user.email=t@t"]


def _git(path, *args):
    return subprocess.run(["git", "-C", str(path)] + list(args), check=True, capture_output=True, text=True).stdout.strip()


class Gh:
    """Fake `gh api` answering reads from dicts, with the branch reads taken live from the bare remote;
    a `git` argv runs for real."""

    def __init__(self, bare):
        self.bare = str(bare)
        self.pulls, self.open_prs, self.default = {}, [], "main"
        self.broken, self.ref_override, self.calls = set(), {}, []
        self.push_url = "git@github.com:%s.git" % REPO

    def _live(self, branch):
        got = subprocess.run(["git", "--git-dir", self.bare, "rev-parse", "--verify", "-q", "refs/heads/" + branch],
                             capture_output=True, text=True)
        return got.stdout.strip() or None

    def __call__(self, argv, **kw):
        if argv[0] == "git" and argv[3:6] == ["remote", "get-url", "--push"]:
            return SimpleNamespace(returncode=0, stdout=self.push_url + "\n", stderr="")
        if argv[0] == "git":
            return subprocess.run(argv, **kw)
        self.calls.append(tuple(argv))
        path = argv[-1]
        if path in self.broken:
            return SimpleNamespace(returncode=1, stdout="", stderr="gh: Server Error (HTTP 500)")
        base = "repos/%s" % REPO
        if path.startswith(base + "/pulls/"):
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.pulls[int(path.rsplit("/", 1)[1])]), stderr="")
        if path == base:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"default_branch": self.default}), stderr="")
        if path == base + "/pulls?state=open&per_page=100":
            assert "--paginate" in argv
            return SimpleNamespace(returncode=0, stdout="\n".join(json.dumps([p]) for p in self.open_prs) or "[]", stderr="")
        if path == base + "/branches?per_page=100":
            assert "--paginate" in argv
            names = _git(self.bare, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()
            return SimpleNamespace(returncode=0, stdout="\n".join(json.dumps([{"name": n}]) for n in names), stderr="")
        assert path.startswith(base + "/git/ref/heads/"), path
        branch = path[len(base + "/git/ref/heads/"):]
        sha = self.ref_override.get(branch) or self._live(branch)
        if sha is None:
            return SimpleNamespace(returncode=1, stdout='{"message":"Not Found","status":"404"}',
                                   stderr="gh: Not Found (HTTP 404)")
        return SimpleNamespace(returncode=0, stdout=json.dumps({"object": {"sha": sha}}), stderr="")


def _pull(issues=(101,), state="closed", merged=True, head_sha=None, head_repo=REPO, ref=BRANCH,
          created_at="2100-01-01T00:00:00Z"):
    body = "Closes " + ", closes ".join("#%d" % i for i in issues) + "\n\nthe work" if issues else "the work"
    head = {"ref": ref, "sha": head_sha, "repo": {"full_name": head_repo} if head_repo else None}
    return {"state": state, "merged": merged, "merged_at": "2026-10-12T10:00:00Z" if merged else None, "created_at": created_at,
            "body": body,
            "head": head, "base": {"ref": "main", "repo": {"full_name": REPO}}}


def _open_pr(head_ref="other", base_ref="main", head_repo=REPO):
    return {"head": {"ref": head_ref, "repo": {"full_name": head_repo}}, "base": {"ref": base_ref, "repo": {"full_name": REPO}}}


@pytest.fixture
def w(tmp_path, monkeypatch):
    # the fixture repositories read no git configuration of the machine they run on (no signing, no hooks)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = _init_repo(tmp_path / "repo")
    root = _ledger_env(tmp_path, monkeypatch)
    env = {"HOME": str(tmp_path / "home"), "PATH": os.environ["PATH"], ll.LEDGER_ROOT_ENV: root}
    assert _declare(repo, BATCH, 4, env=env)["ok"]
    bare, work = tmp_path / "remote.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    (work / "f").write_text("1\n")
    _git(work, "add", ".")
    _git(work, *IDENT, "commit", "-q", "-m", "one")
    _git(work, "branch", "-M", "main")
    _git(work, "branch", BRANCH)
    _git(work, "push", "-q", str(bare), "main", BRANCH)
    head = _git(work, "rev-parse", "HEAD")
    gh = Gh(bare)
    gh.pulls[PR] = _pull(head_sha=head)
    return SimpleNamespace(repo=repo, env=env, gh=gh, bare=bare, work=work, head=head, remote=str(bare))


def _lane(w, launch_id, issue, session="session-a", place="cloud", outcome=None, ts=None):
    extra = {"place": "cloud", "cloudEnvironment": "env-fixture-one", "pluginVersion": "1.2.3"} if place == "cloud" else {}
    if ts is not None:
        extra["ts"] = ts
    got = ll.reserve(w.repo, _reserved(launch_id, BATCH, [launch_id], w.repo, issue=issue, **extra), env=w.env)
    assert got["ok"], got
    if session is not None:
        started = _started(launch_id)
        started.update(cloudSessionName=session, cloudSessionId="session_01AbCdEf123")
        assert ll.append_under_lock(w.repo, started, env=w.env)["ok"]
    if outcome:
        assert ll.terminalize(w.repo, launch_id, child_ever_spawned=True, outcome=outcome, evidence="x", env=w.env)["ok"]


def _plan(w, **kw):
    return CC.plan(w.repo, REPO, PR, env=w.env, run=w.gh, **kw)


def _branch(w):
    return CC.branch(w.repo, REPO, PR, remote=w.remote, env=w.env, run=w.gh)


def _record(w, msg_id, outcome):
    return CC.record(w.repo, REPO, PR, msg_id, outcome, env=w.env, run=w.gh)


def _state_file(w):
    return os.path.join(os.path.dirname(ll.ledger_path(w.repo, w.env)["path"]), CC.STATE_NAME)


def _remote_branches(w):
    return _git(w.bare, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()


def _advance_remote(w):
    (w.work / "f").write_text("2\n")
    _git(w.work, *IDENT, "commit", "-q", "-am", "two")
    _git(w.work, "push", "-q", str(w.bare), "HEAD:refs/heads/" + BRANCH)
    return _git(w.work, "rev-parse", "HEAD")


# ---------------------------------------------------------------- an open PR gets nothing


@pytest.mark.parametrize("ended", ["handback", "park"])
def test_an_open_pr_after_a_handback_or_a_park_gets_no_message_no_deletion_and_no_receipt(w, ended):
    _lane(w, "l-1", 101, outcome=ended)
    w.gh.pulls[PR] = _pull(state="open", merged=False, head_sha=w.head)
    none = {"ok": True, "action": "none", "reason": "pr-open"}
    assert _plan(w) == none
    assert _branch(w) == none
    assert _record(w, "m-1", "delivered") == {"ok": False, "reason": "pr-open"}
    assert _remote_branches(w) == ["feature", "main"]
    assert not os.path.exists(_state_file(w))
    assert {c[-1] for c in w.gh.calls} == {"repos/%s/pulls/%d" % (REPO, PR)}


# ---------------------------------------------------------------- the branch


def test_a_merged_pr_whose_branch_the_repository_kept_is_deleted_and_the_listing_lacks_it(w):
    _lane(w, "l-1", 101)
    assert BRANCH in _remote_branches(w)
    out = _branch(w)
    assert out == {"ok": True, "action": "cleanup", "branch": BRANCH, "deleted": True, "already": None,
                   "listing": ["main"]}
    assert _remote_branches(w) == ["main"]


def test_a_branch_the_repository_already_deleted_is_a_success_that_deletes_nothing(w):
    _lane(w, "l-1", 101)
    _git(w.bare, "branch", "-D", BRANCH)
    assert _branch(w) == {"ok": True, "action": "cleanup", "branch": BRANCH, "deleted": False, "already": "absent",
                          "listing": ["main"]}


def test_a_pr_closed_without_merging_gets_the_closed_words_and_its_branch_deleted(w):
    _lane(w, "l-1", 101)
    w.gh.pulls[PR] = _pull(merged=False, head_sha=w.head)
    got = _plan(w)
    assert got["outcome"] == "closed" and got["archiveText"] == CC.ARCHIVE_TEXT_CLOSED % PR
    assert "is closed without merging" in got["archiveText"] and "is merged" not in got["archiveText"]
    assert _branch(w)["deleted"] is True
    assert _remote_branches(w) == ["main"]


def test_a_branch_that_moved_past_the_prs_head_is_never_deleted(w):
    _lane(w, "l-1", 101)
    moved = _advance_remote(w)
    assert moved != w.head
    assert _branch(w) == {"ok": False, "reason": "branch-moved"}
    assert BRANCH in _remote_branches(w)


def test_the_lease_rejects_a_delete_when_a_push_lands_after_the_read(w):
    _lane(w, "l-1", 101)
    moved = _advance_remote(w)
    w.gh.ref_override[BRANCH] = w.head  # the read still reports the PR's head: the push landed after it
    out = _branch(w)
    assert out["ok"] is False and out["reason"] == "delete-refused" and out["detail"]
    assert _git(w.bare, "rev-parse", "refs/heads/" + BRANCH) == moved


def test_a_branch_an_open_pr_uses_as_its_base_is_kept(w):
    _lane(w, "l-1", 101)
    w.gh.open_prs = [_open_pr(head_ref="upper", base_ref=BRANCH)]
    assert _branch(w) == {"ok": False, "reason": "branch-in-use"}
    assert BRANCH in _remote_branches(w)


def test_a_branch_another_open_pr_in_this_repository_uses_as_its_head_is_kept_but_a_forks_is_not_a_use(w):
    _lane(w, "l-1", 101)
    w.gh.open_prs = [_open_pr(head_ref=BRANCH)]
    assert _branch(w) == {"ok": False, "reason": "branch-in-use"}
    w.gh.open_prs = [_open_pr(head_ref=BRANCH, head_repo="fork/name")]
    assert _branch(w)["deleted"] is True


def test_the_default_branch_and_a_foreign_head_repository_are_refused(w):
    _lane(w, "l-1", 101)
    w.gh.default = BRANCH
    assert _branch(w) == {"ok": False, "reason": "default-branch"}
    w.gh.default = "main"
    for head_repo in ("fork/name", None):
        w.gh.pulls[PR] = _pull(head_sha=w.head, head_repo=head_repo)
        assert _branch(w) == {"ok": False, "reason": "head-repo-foreign"}
    assert BRANCH in _remote_branches(w)


def test_an_unreadable_read_refuses_and_never_reads_as_absent_or_open(w):
    _lane(w, "l-1", 101)
    base = "repos/%s" % REPO
    for broken, reason in ((base, "default-branch-unreadable"),
                           (base + "/pulls?state=open&per_page=100", "open-prs-unreadable"),
                           (base + "/git/ref/heads/" + BRANCH, "branch-unreadable")):
        w.gh.broken = {broken}
        assert _branch(w) == {"ok": False, "reason": reason}
        assert BRANCH in _remote_branches(w)
    w.gh.broken = {"%s/pulls/%d" % (base, PR)}
    assert _branch(w) == {"ok": False, "reason": "pr-unreadable"}
    assert _plan(w) == {"ok": False, "reason": "pr-unreadable"}
    w.gh.broken = {base + "/branches?per_page=100"}
    assert _branch(w) == {"ok": False, "reason": "branches-unreadable"}


def test_a_delete_the_read_back_does_not_confirm_is_refused(w):
    _lane(w, "l-1", 101)
    w.gh.ref_override[BRANCH] = w.head  # the read keeps reporting the branch after the push
    out = _branch(w)
    assert out["ok"] is False and out["reason"] == "delete-unconfirmed"


# ---------------------------------------------------------------- binding the PR to its lane


def test_a_pr_that_links_no_issue_is_unlinked(w):
    _lane(w, "l-1", 101)
    w.gh.pulls[PR] = _pull(issues=(), head_sha=w.head)
    assert _plan(w) == {"ok": False, "reason": "pr-unlinked"}
    assert _branch(w) == {"ok": False, "reason": "pr-unlinked"}


def test_a_local_lane_is_no_cloud_lane(w):
    _lane(w, "l-local", 101, session=None, place="local")
    assert _plan(w) == {"ok": False, "reason": "no-cloud-lane"}
    assert _branch(w) == {"ok": False, "reason": "no-cloud-lane"}
    assert BRANCH in _remote_branches(w)


def test_two_linked_issues_with_cloud_lanes_are_ambiguous_without_a_launch_id(w):
    _lane(w, "l-1", 101, session="session-a")
    _lane(w, "l-2", 202, session="session-b")
    w.gh.pulls[PR] = _pull(issues=(101, 202), head_sha=w.head)
    assert _plan(w) == {"ok": False, "reason": "lane-ambiguous"}
    assert _branch(w) == {"ok": False, "reason": "lane-ambiguous"}
    got = _plan(w, launch_id="l-2")
    assert got["ok"] and got["session"] == "session-b" and got["launchId"] == "l-2" and got["issue"] == 202
    assert _plan(w, launch_id="l-unknown") == {"ok": False, "reason": "no-cloud-lane"}


def test_a_launch_id_of_another_issues_lane_is_not_this_prs_lane(w):
    _lane(w, "l-1", 101)
    _lane(w, "l-9", 909, session="session-z")
    assert _plan(w, launch_id="l-9") == {"ok": False, "reason": "lane-mismatch"}


def test_a_lane_without_a_session_name_is_unknown_and_the_plan_carries_the_lane_facts(w):
    _lane(w, "l-1", 101, session=None)
    assert _plan(w) == {"ok": False, "reason": "lane-session-unknown"}


def test_the_plan_carries_the_lanes_facts_and_the_newest_cloud_lane_of_the_issue(w):
    _lane(w, "l-1", 101, session="session-one", outcome="handback", ts=_T1)
    _lane(w, "l-2", 101, session="session-two", ts=_T2)
    w.gh.pulls[PR] = _pull(head_sha=w.head, created_at="2023-11-17T00:00:00Z")  # opened after both lanes
    got = _plan(w)
    assert got == {"ok": True, "action": "cleanup", "outcome": "merged", "repo": REPO, "pr": PR, "issue": 101,
                   "launchId": "l-2", "session": "session-two", "sessionId": "session_01AbCdEf123", "configDir": None,
                   "archiveText": CC.ARCHIVE_TEXT_MERGED % PR, "request": {"state": "none"}, "branch": BRANCH,
                   "headSha": w.head}


_T1, _T2, _OPENED = 1_700_000_000, 1_700_100_000, "2023-11-15T00:00:00Z"  # _OPENED is between them


def test_an_older_pr_is_not_bound_to_a_lane_reserved_after_it_was_opened(w):
    _lane(w, "l-1", 101, session="session-one", outcome="handback", ts=_T1)
    _lane(w, "l-2", 101, session="session-two", ts=_T2)
    w.gh.pulls[PR] = _pull(head_sha=w.head, created_at=_OPENED)
    got = _plan(w)
    assert got["ok"] and got["session"] == "session-one" and got["launchId"] == "l-1"
    assert got.get("session") != "session-two"
    recorded = _record(w, "m-1", "delivered")
    assert recorded["ok"] and recorded["request"]["session"] == "session-one"


def test_a_pr_opened_before_every_lane_of_its_issue_has_no_cloud_lane(w):
    _lane(w, "l-2", 101, session="session-two", ts=_T2)
    w.gh.pulls[PR] = _pull(head_sha=w.head, created_at=_OPENED)
    assert _plan(w) == {"ok": False, "reason": "no-cloud-lane"}


def test_an_explicit_launch_id_wins_over_the_pr_open_time(w):
    _lane(w, "l-1", 101, session="session-one", outcome="handback", ts=_T1)
    _lane(w, "l-2", 101, session="session-two", ts=_T2)
    w.gh.pulls[PR] = _pull(head_sha=w.head, created_at=_OPENED)
    got = _plan(w, launch_id="l-2")
    assert got["ok"] and got["session"] == "session-two"


def test_a_pr_without_a_readable_open_time_is_unreadable(w):
    _lane(w, "l-1", 101)
    for bad in (None, "yesterday", 5):
        w.gh.pulls[PR] = _pull(head_sha=w.head, created_at=bad)
        assert _plan(w) == {"ok": False, "reason": "pr-unreadable"}


def test_an_argument_that_is_not_a_repository_or_a_pull_request_is_refused(w):
    assert CC.plan(w.repo, "not-a-repo", PR, env=w.env, run=w.gh) == {"ok": False, "reason": "repo-invalid"}
    for pr in (0, -3, "x", True, None):
        assert CC.plan(w.repo, REPO, pr, env=w.env, run=w.gh) == {"ok": False, "reason": "pr-invalid"}


# ---------------------------------------------------------------- the receipt


def test_a_delivered_request_gives_the_owner_the_boards_words_and_is_never_overwritten(w):
    _lane(w, "l-1", 101)
    first = _record(w, "m-1", "delivered")
    assert first["ok"] and first["ownerMessage"] == CC.OWNER_MESSAGE_MERGED % PR
    assert set(first["request"]) == set(CC._RECEIPT_KEYS)
    assert (first["request"]["session"], first["request"]["msgId"], first["request"]["outcome"]) == ("session-a", "m-1", "delivered")
    second = _record(w, "m-2", "delivered")
    assert second["ok"] and second["already"] is True and second["request"]["msgId"] == "m-1"
    with open(_state_file(w), encoding="utf-8") as fh:
        assert [r["msgId"] for r in json.load(fh)] == ["m-1"]
    assert _plan(w)["request"] == first["request"]


def test_an_uncertain_request_is_never_resent_on_its_own_and_has_no_owner_message(w):
    _lane(w, "l-1", 101)
    got = _record(w, "m-1", "uncertain")
    assert got["ok"] and got["ownerMessage"] is None and got["request"]["outcome"] == "uncertain"
    assert _record(w, "m-2", "delivered") == {"ok": False, "reason": "request-uncertain"}
    with open(_state_file(w), encoding="utf-8") as fh:
        assert [(r["msgId"], r["outcome"]) for r in json.load(fh)] == [("m-1", "uncertain")]


def test_a_failed_request_may_be_overwritten_by_a_delivered_one(w):
    _lane(w, "l-1", 101)
    got = _record(w, "m-1", "failed")
    assert got["ok"] and got["ownerMessage"] is None
    done = _record(w, "m-2", "delivered")
    assert done["ok"] and "already" not in done and done["request"]["msgId"] == "m-2" and done["ownerMessage"]
    with open(_state_file(w), encoding="utf-8") as fh:
        assert [(r["msgId"], r["outcome"]) for r in json.load(fh)] == [("m-2", "delivered")]


def test_a_closed_pr_gets_the_closed_owner_message(w):
    _lane(w, "l-1", 101)
    w.gh.pulls[PR] = _pull(merged=False, head_sha=w.head)
    got = _record(w, "m-1", "delivered")
    assert got["ownerMessage"] == CC.OWNER_MESSAGE_CLOSED % PR


def test_record_refuses_bad_arguments_and_an_unreadable_state_file_is_never_reset(w):
    _lane(w, "l-1", 101)
    assert _record(w, "", "delivered") == {"ok": False, "reason": "msg-id-invalid"}
    assert _record(w, "m-1", "sent") == {"ok": False, "reason": "outcome-invalid"}
    assert not os.path.exists(_state_file(w))
    os.makedirs(os.path.dirname(_state_file(w)), exist_ok=True)
    with open(_state_file(w), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert _record(w, "m-1", "delivered") == {"ok": False, "reason": "cleanup-state-unreadable"}
    assert _plan(w) == {"ok": False, "reason": "cleanup-state-unreadable"}
    with open(_state_file(w), encoding="utf-8") as fh:
        assert fh.read() == "{not json"


def test_the_cli_prints_one_json_object_and_exits_1_on_a_refusal(w, capsys, monkeypatch):
    for key, value in w.env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(CC, "subprocess", SimpleNamespace(run=w.gh))
    _lane(w, "l-1", 101)
    base = ["--repo-root", w.repo, "--repo", REPO, "--pr", str(PR)]
    assert CC.main(["plan"] + base) == 0
    assert json.loads(capsys.readouterr().out)["archiveText"] == CC.ARCHIVE_TEXT_MERGED % PR
    assert CC.main(["record"] + base + ["--msg-id", "m-1", "--outcome", "delivered"]) == 0
    assert json.loads(capsys.readouterr().out)["ownerMessage"]
    assert CC.main(["branch"] + base + ["--remote", w.remote]) == 0
    assert json.loads(capsys.readouterr().out)["deleted"] is True
    assert CC.main(["branch"] + base[:-2] + ["--pr", "0"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "pr-invalid"}


def test_the_owner_message_is_the_boards_words_byte_for_byte():
    # the board's owner-approved text is an external contract, so it is the one literal pinned here
    assert CC.OWNER_MESSAGE_MERGED % 412 == ("#412 is merged. I've asked its cloud builder to archive itself. "
                                             "You'll get one prompt for it: tap Allow once.")


# ---------------------------------------------------------------- review round 1


def test_a_delivered_request_is_not_asked_for_again(w):
    _lane(w, "l-1", 101)
    assert _record(w, "m-1", "delivered")["ok"]
    got = _plan(w)
    assert got["action"] == "cleanup" and got["archiveText"] is None and got["alreadyDelivered"] is True


def test_record_and_branch_keep_the_explicit_launch_selection(w):
    w.gh.pulls[PR] = _pull(issues=(101, 202), head_sha=w.head)
    _lane(w, "l-1", 101, session="session-a")
    _lane(w, "l-2", 202, session="session-b")
    assert _record(w, "m-1", "delivered") == {"ok": False, "reason": "lane-ambiguous"}
    got = CC.record(w.repo, REPO, PR, "m-1", "delivered", launch_id="l-2", env=w.env, run=w.gh)
    assert got["ok"] and got["request"]["session"] == "session-b"
    out = CC.branch(w.repo, REPO, PR, remote=w.remote, launch_id="l-2", env=w.env, run=w.gh)
    assert out.get("deleted") is True, out


def test_an_open_pr_head_in_a_differently_cased_repository_spelling_keeps_the_branch(w):
    _lane(w, "l-1", 101)
    w.gh.open_prs = [_open_pr(head_ref=BRANCH, base_ref="release", head_repo="Owner/Name")]
    assert _branch(w) == {"ok": False, "reason": "branch-in-use"}
    assert BRANCH in _remote_branches(w)


def test_a_push_destination_other_than_the_checked_repository_is_refused_before_any_delete(w):
    _lane(w, "l-1", 101)
    w.gh.push_url = "git@github.com:owner/mirror.git"
    assert _branch(w) == {"ok": False, "reason": "push-destination-mismatch"}
    assert BRANCH in _remote_branches(w)
    w.gh.push_url = "https://github.com/Owner/Name"
    assert _branch(w)["deleted"] is True


def test_a_pending_request_is_written_before_the_send_and_replaced_by_the_outcome_of_the_same_message(w):
    _lane(w, "l-1", 101)
    pending = _record(w, "m-1", "pending")
    assert pending["ok"] and pending["ownerMessage"] is None and pending["request"]["outcome"] == "pending"
    assert _plan(w)["request"] == pending["request"]
    done = _record(w, "m-1", "delivered")
    assert done["ok"] and done["ownerMessage"] == CC.OWNER_MESSAGE_MERGED % PR
    with open(_state_file(w), encoding="utf-8") as fh:
        assert [(r["msgId"], r["outcome"]) for r in json.load(fh)] == [("m-1", "delivered")]


def test_a_pending_request_found_on_resume_is_never_replaced_by_another_message(w):
    _lane(w, "l-1", 101)
    assert _record(w, "m-1", "pending")["ok"]
    assert _record(w, "m-2", "pending") == {"ok": False, "reason": "request-uncertain"}
    assert _record(w, "m-2", "delivered") == {"ok": False, "reason": "request-uncertain"}
    settled = _record(w, "m-1", "uncertain")
    assert settled["ok"] and settled["request"]["outcome"] == "uncertain"
    with open(_state_file(w), encoding="utf-8") as fh:
        assert [(r["msgId"], r["outcome"]) for r in json.load(fh)] == [("m-1", "uncertain")]
