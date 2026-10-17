"""A cloud launch runs the cloud command only when the launching checkout is on the base.

The cloud command takes no revision and the platform starts the session from the checkout's
commit, so the launcher refuses unless the checkout sits on a named branch whose local HEAD and
whose tip on `origin` are both the premise's base. It only reads the checkout; every state it
cannot read refuses. The platform command is never run here: the spawn function is injected.
"""
import os
import subprocess

import pytest

import launch_ledger as ll

from test_launcher import (  # noqa: E402
    L,
    _head_sha,
    _valid_premise,
)
from test_launcher_cloud import (  # noqa: E402
    _assert_refused_cloud_lane,
    _cloud_repo,
    _fake_spawn,
    _git,
    _lanes,
    _launch,
    _local_remote_has,
)

OFF_BASE = "launch-cloud-checkout-off-base"
UNREADABLE = "launch-cloud-checkout-unreadable"
NOT_ON_REMOTE = "launch-cloud-checkout-branch-not-on-remote"
REMOTE_UNCHECKED = "launch-cloud-checkout-remote-unchecked"
IDENT = ("-c", "user.email=t@t.local", "-c", "user.name=t")


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger-root"))
    # The instance-pin gate applies only on a Claude-hosted seat; these tests are not one.
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setattr(L, "_pause_between_appends", lambda: None)
    # The base is kept on a local bare remote and asked of it, not of GitHub.
    monkeypatch.setattr(L, "_base_on_remote_fn", _local_remote_has)
    # The fixture repositories must not depend on the developer's git config, such as signing.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _branch(repo):
    return _git(repo, "symbolic-ref", "--short", "HEAD").strip()


def _commit(repo, name):
    """A new commit on the checkout's current branch; its sha."""
    with open(os.path.join(repo, name), "w") as fh:
        fh.write("%s\n" % name)
    _git(repo, "add", name)
    _git(repo, *IDENT, "commit", "-q", "-m", name)
    return _head_sha(repo)


def _proc(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


# --- the field shape: the checkout is on another branch at another commit ---------------------


def test_row1_a_checkout_on_another_branch_at_another_commit_refuses_and_is_left_untouched(
    tmp_path,
):
    # axis: HEAD that is not the base refuses, and the launcher never writes the checkout
    repo = _cloud_repo(tmp_path)
    base = _head_sha(repo)
    _git(repo, "checkout", "-q", "-b", "elsewhere")
    elsewhere = _commit(repo, "tracked.txt")
    assert elsewhere != base
    with open(os.path.join(repo, "file.txt"), "w") as fh:
        fh.write("staged\n")
    _git(repo, "add", "file.txt")
    with open(os.path.join(repo, "tracked.txt"), "w") as fh:
        fh.write("unstaged\n")
    with open(os.path.join(repo, "untracked.txt"), "w") as fh:
        fh.write("untracked\n")

    def snapshot():
        return {
            "symbolic": _git(repo, "symbolic-ref", "HEAD"),
            "head": _head_sha(repo),
            "status": _git(repo, "status", "--porcelain"),
            "cached": _git(repo, "diff", "--cached"),
            "diff": _git(repo, "diff"),
            "files": {
                name: open(os.path.join(repo, name), "rb").read()
                for name in ("file.txt", "tracked.txt", "untracked.txt")
            },
        }

    before = snapshot()
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls),
                     premise=_valid_premise(repo, baseCommit=base))
    _assert_refused_cloud_lane(repo, result, OFF_BASE, "cloud-base")
    assert calls == []
    assert result["checkout"] == repo
    assert result["checkoutBranch"] == "elsewhere"
    assert result["checkoutHead"] == elsewhere
    assert result["baseCommit"] == base
    assert snapshot() == before


# --- the healthy case ------------------------------------------------------------------------


def test_row2_a_checkout_on_the_base_with_the_branch_tip_on_the_base_launches(tmp_path):
    # axis: a checkout and a remote tip that both sit on the base launch
    repo = _cloud_repo(tmp_path)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    assert result["ok"] is True, result
    assert len(calls) == 1


# --- fail closed: the checkout cannot be read ----------------------------------------------


def test_row3_a_detached_head_at_the_base_refuses_as_unreadable(tmp_path):
    # axis: a branch or HEAD that could not be read refuses
    repo = _cloud_repo(tmp_path)
    base = _head_sha(repo)
    _git(repo, "checkout", "-q", "--detach")
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    _assert_refused_cloud_lane(repo, result, UNREADABLE, "cloud-base")
    assert calls == []
    assert result["checkoutBranch"] is None
    assert result["checkoutHead"] == base


@pytest.mark.parametrize("unread", [
    {"symbolic-ref": None},
    {"symbolic-ref": _proc(128)},
    {"symbolic-ref": _proc(0, "HEAD\n")},
    {"symbolic-ref": _proc(0, "refs/heads/\n")},
    {"rev-parse": None},
    {"rev-parse": _proc(128)},
    {"rev-parse": _proc(0, "not-a-sha\n")},
    {"symbolic-ref": None, "rev-parse": None},
], ids=[
    "symbolic-ref-none", "symbolic-ref-128", "symbolic-ref-not-a-branch",
    "symbolic-ref-empty-name", "rev-parse-none", "rev-parse-128", "rev-parse-garbage",
    "neither-readable",
])
def test_row4_a_checkout_git_cannot_read_refuses_as_unreadable_and_the_remote_is_not_asked(
    monkeypatch, unread,
):
    # axis: local facts git cannot read refuse before any remote call
    base = "a" * 40
    asked = []
    monkeypatch.setattr(L, "_remote_branch_head_fn", lambda *a, **k: asked.append(a))

    def scrubbed(repo_root, *args, env=None, timeout=None):
        if args[0] in unread:
            return unread[args[0]]
        if args[0] == "symbolic-ref":
            return _proc(0, "refs/heads/main\n")
        return _proc(0, base + "\n")

    monkeypatch.setattr(L, "_git_scrubbed", scrubbed)
    reason, detail = L._cloud_checkout_refusal("/repo", base, None)
    assert reason == UNREADABLE
    assert detail["checkout"] == "/repo" and detail["baseCommit"] == base
    assert "checkoutBranch" in detail and "checkoutHead" in detail
    assert asked == []


# --- fail closed: the remote's branch tip -----------------------------------------------------


def test_row5_a_remote_branch_tip_that_moved_past_the_base_refuses_as_off_base(tmp_path):
    # axis: a remote branch tip that is not the base refuses
    repo = _cloud_repo(tmp_path)
    base = _head_sha(repo)
    branch = _branch(repo)
    later = _commit(repo, "later.txt")
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/%s" % branch)
    _git(repo, "reset", "-q", "--hard", base)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls),
                     premise=_valid_premise(repo, baseCommit=base))
    _assert_refused_cloud_lane(repo, result, OFF_BASE, "cloud-base")
    assert calls == []
    assert result["checkoutHead"] == base
    assert result["remoteBranchHead"] == later


def test_row6_a_branch_never_pushed_refuses_as_not_on_the_remote(tmp_path):
    # axis: a branch the remote lacks refuses
    repo = _cloud_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "never-pushed")
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    _assert_refused_cloud_lane(repo, result, NOT_ON_REMOTE, "cloud-base")
    assert calls == []
    assert result["checkoutBranch"] == "never-pushed"
    assert result["remoteBranchHead"] is None


def test_row7_a_remote_that_could_not_be_asked_for_the_branch_tip_refuses(tmp_path, monkeypatch):
    # axis: a remote branch tip that could not be read refuses
    repo = _cloud_repo(tmp_path)
    monkeypatch.setattr(L, "_remote_branch_head_fn", lambda *a, **k: (None, "unchecked"))
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    _assert_refused_cloud_lane(repo, result, REMOTE_UNCHECKED, "cloud-base")
    assert calls == []


# --- the remote round-trip's parsing ---------------------------------------------------------


def _ls_remote_answer(monkeypatch, answer):
    seen = []

    def scrubbed(repo_root, *args, env=None, timeout=None):
        seen.append({"repo": repo_root, "args": args, "env": env, "timeout": timeout})
        return answer

    monkeypatch.setattr(L, "_git_scrubbed", scrubbed)
    return seen


SHA = "1234567890abcdef1234567890abcdef12345678"


@pytest.mark.parametrize("answer,expected", [
    (_proc(0, "%s\trefs/heads/main\n" % SHA), (SHA, None)),
    (_proc(2), (None, "absent")),
    (_proc(128), (None, "unchecked")),
    (_proc(1), (None, "unchecked")),
    (_proc(0, ""), (None, "unchecked")),
    (_proc(0, "%s\trefs/heads/main\n%s\trefs/heads/main\n" % (SHA, SHA)), (None, "unchecked")),
    (_proc(0, "%s\trefs/heads/other\n" % SHA), (None, "unchecked")),
    (_proc(0, "%s\trefs/heads/main-2\n" % SHA), (None, "unchecked")),
    (_proc(0, "%s\trefs/heads/main\n" % ("z" * 40)), (None, "unchecked")),
    (_proc(0, "%s refs/heads/main\n" % SHA), (None, "unchecked")),
    (None, (None, "unchecked")),
], ids=[
    "one-good-line", "exit-2-absent", "exit-128", "exit-1", "empty-stdout", "two-lines",
    "another-ref", "a-longer-ref", "non-hex-sha", "no-tab", "git-did-not-run",
])
def test_row8_remote_branch_head_maps_what_git_said(monkeypatch, answer, expected):
    # axis: the ls-remote answer parses exactly: one matching ref line is a tip, anything else is absent or unchecked
    seen = _ls_remote_answer(monkeypatch, answer)
    assert L._remote_branch_head("/repo", "main", {"KEEP": "1"}) == expected
    assert len(seen) == 1
    assert seen[0]["args"] == ("ls-remote", "--exit-code", "origin", "refs/heads/main")
    assert seen[0]["timeout"] == L._WORKTREE_GIT_TIMEOUT


def test_row8_remote_branch_head_never_prompts_and_does_not_touch_the_callers_env(monkeypatch):
    # axis: the tip lookup never prompts and never mutates the caller's env
    seen = _ls_remote_answer(monkeypatch, _proc(2))
    caller = {"KEEP": "1"}
    L._remote_branch_head("/repo", "main", caller)
    assert seen[0]["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert seen[0]["env"]["KEEP"] == "1"
    assert caller == {"KEEP": "1"}


# --- the re-check right before the command ----------------------------------------------------


def test_row9_a_checkout_that_moves_while_reserving_terminalizes_the_unstarted_lane(
    tmp_path, monkeypatch,
):
    # axis: the checkout is re-checked right before the command; reservation can wait on the lock
    repo = _cloud_repo(tmp_path)
    real_reserve = ll.reserve

    def reserve_then_move_the_checkout(*args, **kwargs):
        result = real_reserve(*args, **kwargs)
        _git(repo, "checkout", "-q", "-b", "moved")
        _commit(repo, "moved.txt")
        return result

    monkeypatch.setattr(ll, "reserve", reserve_then_move_the_checkout)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    assert result["ok"] is False
    assert result["reason"] == OFF_BASE
    assert result["checkoutBranch"] == "moved"
    assert calls == []
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is True
    assert lane["started"] is False


# --- the checkout is read again after the remote answered -------------------------------------


@pytest.mark.parametrize("again,reason,branch,head", [
    ({"symbolic-ref": _proc(128)}, UNREADABLE, None, "a" * 40),
    ({"rev-parse": _proc(128)}, UNREADABLE, "main", None),
    ({"symbolic-ref": _proc(0, "refs/heads/other\n")}, OFF_BASE, "other", "a" * 40),
    ({"rev-parse": _proc(0, "b" * 40 + "\n")}, OFF_BASE, "main", "b" * 40),
], ids=[
    "branch-unreadable", "head-unreadable", "another-branch-at-the-base",
    "same-branch-at-another-commit",
])
def test_the_checkout_read_again_after_the_remote_answered_must_still_be_on_the_base(
    monkeypatch, again, reason, branch, head,
):
    # axis: a checkout that cannot be read or has moved once the remote answered refuses, with the re-read facts
    base = "a" * 40
    reads = {"symbolic-ref": 0, "rev-parse": 0}
    calls = []

    def scrubbed(repo_root, *args, env=None, timeout=None):
        name = args[0]
        reads[name] += 1
        # each _read_checkout pass makes three git calls, so the second pass is calls 4 to 6
        second_pass = len(calls) >= 3
        calls.append(name)
        if second_pass and name in again:
            return again[name]
        if name == "symbolic-ref":
            return _proc(0, "refs/heads/main\n")
        return _proc(0, base + "\n")

    monkeypatch.setattr(L, "_git_scrubbed", scrubbed)
    monkeypatch.setattr(L, "_remote_branch_head_fn", lambda *a, **k: (base, None))
    result = L._cloud_checkout_refusal("/repo", base, None)
    assert result is not None
    got_reason, detail = result
    assert got_reason == reason
    assert detail["checkoutBranch"] == branch
    assert detail["checkoutHead"] == head
    assert detail["remoteBranchHead"] == base
    assert reads == {"symbolic-ref": 4, "rev-parse": 2}


# --- one checkout read describes one state of the checkout ------------------------------------


@pytest.mark.parametrize("second_branch", [
    _proc(0, "refs/heads/other\n"),
    _proc(128),
], ids=["another-branch-after-head", "branch-unreadable-after-head"])
def test_one_checkout_read_never_mixes_two_branches(monkeypatch, second_branch):
    # axis: a branch that changed or became unreadable across the HEAD read makes the read unreadable
    base = "a" * 40
    branch_reads = []

    def scrubbed(repo_root, *args, env=None, timeout=None):
        if args[0] == "rev-parse":
            return _proc(0, base + "\n")
        branch_reads.append(True)
        if len(branch_reads) == 1:
            return _proc(0, "refs/heads/main\n")
        return second_branch

    monkeypatch.setattr(L, "_git_scrubbed", scrubbed)
    assert L._read_checkout("/repo", None) == (None, base)
    assert len(branch_reads) == 2


# --- the existing base refusals keep their precedence -----------------------------------------


def test_a_base_the_remote_lacks_is_refused_with_its_own_token_before_the_checkout_is_read(
    tmp_path,
):
    # axis: the base-on-remote refusal keeps its precedence and the checkout is not read
    repo = _cloud_repo(tmp_path)
    later = _commit(repo, "later.txt")
    _git(repo, "checkout", "-q", "-b", "elsewhere")
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls),
                     premise=_valid_premise(repo, baseCommit=later))
    assert result["reason"] == "launch-cloud-base-not-on-remote"
    assert "checkout" not in result
    assert calls == []


def test_start_refusal_hands_back_a_base_refusal_as_a_bare_reason_with_no_extra(monkeypatch):
    # axis: a base refusal comes back as a bare reason with no extra
    monkeypatch.setattr(L, "_base_on_remote_fn", lambda *a, **k: None)
    monkeypatch.setattr(
        L, "_cloud_checkout_refusal", lambda *a, **k: pytest.fail("the checkout was read"),
    )
    assert L._cloud_start_refusal("/repo", {"baseCommit": SHA}, None) == (
        "launch-cloud-base-remote-unchecked", {},
    )
