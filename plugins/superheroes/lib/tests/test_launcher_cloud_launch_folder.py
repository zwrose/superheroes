"""A cloud launch runs from a launcher-owned folder, never from the primary checkout (#2353).

A cloud start reads its working folder's current branch and the platform clones that branch's
remote tip, so the folder the command runs in must sit on a named branch whose local head and
whose tip on `origin` are both the launch's target commit. The launcher keeps its own clone for
that, repairs it non-destructively, and only reads the primary checkout. These tests drive the
real folder path (the conftest stand-in is put back), over throwaway repositories with a bare
remote; the platform command is never run, the spawn function is injected and records the
folder's branch and head at the moment it is called.

Bite-proof record: i2353_cloud_launch_folder.
"""
import fcntl
import json
import os
import subprocess
import sys

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
    _launch,
    _local_remote_has,
)

OFF_BASE = "launch-cloud-checkout-off-base"
UNREADABLE = "launch-cloud-checkout-unreadable"
IDENT = ("-c", "user.email=t@t.local", "-c", "user.name=t")
MARKER = "superheroes-cloud-launch-folder"


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
    # The launcher's own folders live under this root, inside the test's tmp dir.
    monkeypatch.setenv("SUPERHEROES_WORKTREES_ROOT", str(tmp_path / "wt-root"))
    # Put the real folder path back: conftest stands the fixture repo in as the folder.
    monkeypatch.setattr(L, "_cloud_launch_folder_fn", L._prepare_cloud_launch_folder)
    monkeypatch.setattr(L, "_cloud_launch_folder_path_fn", L.cloud_launch_folder_path)
    # No test here has an earlier lane, so no round-trip to GitHub is ever made; belt and braces.
    monkeypatch.setattr(L, "_adopted_branch_first_pr_fn", lambda root, branch, env: None)


# --- fixtures and helpers ---------------------------------------------------------------------


def _symbolic(path):
    got = subprocess.run(
        ["git", "-C", path, "symbolic-ref", "--short", "HEAD"], capture_output=True, text=True,
    )
    return got.stdout.strip() if got.returncode == 0 else None


def _commit(repo, name, text=None):
    """A new commit on the checkout's current branch; its sha."""
    with open(os.path.join(repo, name), "w") as fh:
        fh.write(text if text is not None else "%s\n" % name)
    _git(repo, "add", name)
    _git(repo, *IDENT, "commit", "-q", "-m", name)
    return _head_sha(repo)


def _remote_commit(tmp_path, repo, branches, name, start, text=None):
    """A new commit on top of `start`, pushed (forced) to each of `branches` on origin through a
    scratch clone, so neither the primary checkout nor the launcher's folder sees it. Its sha."""
    remote = _git(repo, "remote", "get-url", "origin").strip()
    scratch = str(tmp_path / ("scratch-%s" % name.replace(".", "-")))
    subprocess.run(["git", "clone", "-q", remote, scratch], check=True, capture_output=True)
    _git(scratch, "checkout", "-q", "--detach", start)
    sha = _commit(scratch, name, text)
    for branch in branches:
        _git(scratch, "push", "-q", "-f", "origin", "%s:refs/heads/%s" % (sha, branch))
    # The launch's premise must resolve its base in the primary checkout's object store, so the
    # commit is fetched there by name (an object-only read: no ref and no working file moves).
    _git(repo, "fetch", "-q", "origin", sha)
    return sha


def _snap(path):
    """The primary checkout's (or the folder's) branch, head and status."""
    named = subprocess.run(
        ["git", "-C", path, "symbolic-ref", "HEAD"], capture_output=True, text=True)
    return {
        "symbolic": named.stdout if named.returncode == 0 else None,
        "head": _head_sha(path),
        "status": _git(path, "status", "--porcelain"),
    }


def _world(tmp_path):
    """A primary checkout with its bare remote, and the launcher's folder made by the setup verb."""
    repo = _cloud_repo(tmp_path)
    ensured = L.ensure_cloud_launch_folder(repo)
    assert ensured["ok"] is True and ensured["created"] is True, ensured
    return repo, ensured["folder"]


def _spy(calls, during=None):
    """A spawn that records the cwd and, at call time, the folder's branch and head."""
    inner = _fake_spawn(calls=[])

    def spawn(argv, cwd, log_path, child_env, timeout):
        calls.append({"cwd": cwd, "branch": _symbolic(cwd), "head": _head_sha(cwd)})
        if during is not None:
            during()
        return inner(argv, cwd, log_path, child_env, timeout)

    return spawn


def _refused(repo, result, reason, repair, folder, calls, primary_before):
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
    assert calls == []
    assert result["launchFolder"] == folder
    assert result.get("folderRepair") == repair
    assert _snap(repo) == primary_before


# --- row 1: a base that is the tip of an unmerged branch --------------------------------------


def test_row1_a_base_that_is_an_unmerged_branch_tip_launches_from_the_folder_on_that_branch(
    tmp_path,
):
    # axis: the command runs in the launcher's folder, which is moved to the branch at the base, while the primary checkout stays where it was — see bite-proof record i2353_cloud_launch_folder
    repo, folder = _world(tmp_path)
    main = _head_sha(repo)
    pr = _remote_commit(tmp_path, repo, ["pr"], "pr.txt", start=main)
    assert pr != main
    before = _snap(repo)
    calls = []
    result = _launch(repo, tmp_path, _spy(calls), premise=_valid_premise(repo, baseCommit=pr))
    assert result["ok"] is True, result
    assert len(calls) == 1
    assert calls[0]["cwd"] == folder
    assert calls[0]["branch"] == "pr"
    assert calls[0]["head"] == pr
    assert _snap(repo) == before


# --- row 2: the folder is repaired forward ----------------------------------------------------


def test_row2_a_folder_at_an_old_tip_is_moved_forward_to_the_new_tip(tmp_path):
    # axis: a folder behind the remote's tip is fast-forwarded to the target before the command runs, and the primary is not touched
    repo, folder = _world(tmp_path)
    main = _head_sha(repo)
    branch = _symbolic(folder)
    assert _head_sha(folder) == main
    newer = _remote_commit(tmp_path, repo, [branch], "newer.txt", start=main)
    before = _snap(repo)
    calls = []
    result = _launch(repo, tmp_path, _spy(calls), premise=_valid_premise(repo, baseCommit=newer))
    assert result["ok"] is True, result
    assert len(calls) == 1
    assert calls[0]["cwd"] == folder
    assert calls[0]["branch"] == branch
    assert calls[0]["head"] == newer
    assert _snap(repo) == before


# --- row 3: uncommitted changes ---------------------------------------------------------------


def test_row3_a_folder_with_uncommitted_changes_refuses_and_is_left_as_it_was(tmp_path):
    # axis: a folder with uncommitted changes refuses and nothing in it is moved or discarded — see bite-proof record i2353_cloud_launch_folder
    repo, folder = _world(tmp_path)
    with open(os.path.join(folder, "scratch.txt"), "w") as fh:
        fh.write("mine\n")
    primary_before = _snap(repo)
    folder_before = _snap(folder)
    calls = []
    result = _launch(repo, tmp_path, _spy(calls))
    _refused(repo, result, OFF_BASE, "uncommitted-changes", folder, calls, primary_before)
    assert _snap(folder) == folder_before
    with open(os.path.join(folder, "scratch.txt")) as fh:
        assert fh.read() == "mine\n"


# --- row 4: no branch sits at the base --------------------------------------------------------


def test_row4_a_base_no_remote_branch_tip_equals_refuses_and_the_folder_is_unchanged(tmp_path):
    # axis: a base the remote holds but no branch tip equals refuses, because a cloud start reads a branch's tip — see bite-proof record i2353_cloud_launch_folder
    repo, folder = _world(tmp_path)
    base = _head_sha(repo)
    branch = _symbolic(folder)
    _remote_commit(tmp_path, repo, [branch, "main"], "beyond.txt", start=base)
    primary_before = _snap(repo)
    folder_before = _snap(folder)
    calls = []
    result = _launch(repo, tmp_path, _spy(calls), premise=_valid_premise(repo, baseCommit=base))
    _refused(repo, result, OFF_BASE, "no-branch-at-base", folder, calls, primary_before)
    assert _snap(folder) == folder_before


# --- row 5: a base the remote does not hold ---------------------------------------------------


def test_row5_a_base_the_remote_does_not_hold_refuses_on_the_existing_path(tmp_path):
    # axis: a base the remote lacks keeps its refusal, ahead of any folder work
    repo, folder = _world(tmp_path)
    later = _commit(repo, "later.txt")
    primary_before = _snap(repo)
    folder_before = _snap(folder)
    calls = []
    result = _launch(repo, tmp_path, _spy(calls), premise=_valid_premise(repo, baseCommit=later))
    assert result["ok"] is False
    assert result["reason"] == "launch-cloud-base-not-on-remote"
    assert calls == []
    assert _snap(folder) == folder_before
    assert _snap(repo) == primary_before


# --- row 6: local commits in the folder -------------------------------------------------------


def test_row6_local_commits_on_the_folders_branch_refuse_and_the_branch_is_not_reset(tmp_path):
    # axis: a local branch holding commits the target lacks refuses, so the repair is only ever a fast-forward — see bite-proof record i2353_cloud_launch_folder
    repo, folder = _world(tmp_path)
    mine = _commit(folder, "local-work.txt")
    primary_before = _snap(repo)
    folder_before = _snap(folder)
    calls = []
    result = _launch(repo, tmp_path, _spy(calls))
    _refused(repo, result, OFF_BASE, "local-commits", folder, calls, primary_before)
    assert _snap(folder) == folder_before
    assert _head_sha(folder) == mine


# --- row 7: an ignored file the target tracks -------------------------------------------------


def test_row7_an_ignored_file_the_target_tracks_refuses_the_switch_and_keeps_its_bytes(tmp_path):
    # axis: --no-overwrite-ignore makes an ignored local file that the target tracks refuse the switch instead of being overwritten — see bite-proof record i2353_cloud_launch_folder
    repo, folder = _world(tmp_path)
    base = _head_sha(repo)
    tracked = _remote_commit(
        tmp_path, repo, ["other"], "gen.txt", start=base, text="tracked\n")
    # Ignored through the folder's own exclude file: an untracked .gitignore would itself make
    # the tree dirty and this row would read as uncommitted changes.
    with open(os.path.join(folder, ".git", "info", "exclude"), "a") as fh:
        fh.write("gen.txt\n")
    with open(os.path.join(folder, "gen.txt"), "w") as fh:
        fh.write("localbytes\n")
    assert _git(folder, "status", "--porcelain", "--untracked-files=all") == ""
    primary_before = _snap(repo)
    folder_before = _snap(folder)
    calls = []
    result = _launch(
        repo, tmp_path, _spy(calls), premise=_valid_premise(repo, baseCommit=tracked))
    _refused(repo, result, OFF_BASE, "checkout-failed", folder, calls, primary_before)
    assert _snap(folder) == folder_before
    with open(os.path.join(folder, "gen.txt")) as fh:
        assert fh.read() == "localbytes\n"


# --- row 8: the folder is missing -------------------------------------------------------------


def test_row8_a_missing_folder_refuses_and_is_never_created(tmp_path):
    # axis: a folder the setup verb has not made refuses, and a launch never creates it — see bite-proof record i2353_cloud_launch_folder
    repo = _cloud_repo(tmp_path)
    folder = L.cloud_launch_folder_path(repo)
    assert folder is not None and not os.path.lexists(folder)
    primary_before = _snap(repo)
    calls = []
    result = _launch(repo, tmp_path, _spy(calls))
    _assert_refused_cloud_lane(repo, result, "launch-cloud-folder-missing", "cloud-base")
    assert calls == []
    assert result["launchFolder"] == folder
    assert "folderRepair" not in result
    assert "checkout" not in result
    assert not os.path.lexists(folder)
    assert not os.path.lexists(folder + ".lock")
    assert _snap(repo) == primary_before
    # The refusal's detail names exactly the folder and the base, nothing else.
    got_folder, targets, refusal = L._prepare_cloud_launch_folder(
        repo, {"baseCommit": _head_sha(repo)}, dict(os.environ))
    assert got_folder == folder and targets is None
    reason, detail = refusal
    assert reason == "launch-cloud-folder-missing"
    assert set(detail) == {"launchFolder", "baseCommit"}


# --- row 9: a path that is not the launcher's own clone ---------------------------------------


def test_row9_a_symlink_to_the_primary_checkout_is_not_the_folder(tmp_path):
    # axis: a folder path that is a symlink to the primary checkout is refused as not launcher-owned and the primary is not touched
    repo = _cloud_repo(tmp_path)
    folder = L.cloud_launch_folder_path(repo)
    os.makedirs(os.path.dirname(folder))
    os.symlink(repo, folder)
    primary_before = _snap(repo)
    calls = []
    result = _launch(repo, tmp_path, _spy(calls))
    _refused(repo, result, UNREADABLE, "not-launcher-owned", folder, calls, primary_before)
    assert os.path.islink(folder)


def test_row9_a_symlink_to_a_genuine_launcher_clone_is_not_the_folder(tmp_path):
    # axis: a folder path that is a symlink is not the launcher's own folder even when what it points at passes every other check — see bite-proof record i2353_cloud_launch_folder
    repo, folder = _world(tmp_path)
    real = folder + "-real"
    os.rename(folder, real)
    os.symlink(real, folder)
    primary_before = _snap(repo)
    real_before = _snap(real)
    calls = []
    result = _launch(repo, tmp_path, _spy(calls))
    _refused(repo, result, UNREADABLE, "not-launcher-owned", folder, calls, primary_before)
    assert _snap(real) == real_before
    assert os.path.islink(folder)


def test_row9_a_linked_worktree_with_a_valid_marker_is_not_the_folder(tmp_path):
    # axis: a folder that shares the primary's git dir is not independent of it, whatever marker and origin it carries — see bite-proof record i2353_cloud_launch_folder
    repo = _cloud_repo(tmp_path)
    folder = L.cloud_launch_folder_path(repo)
    os.makedirs(os.path.dirname(folder))
    _git(repo, "worktree", "add", "--detach", folder)
    gitdir = _git(folder, "rev-parse", "--absolute-git-dir").strip()
    with open(os.path.join(gitdir, MARKER), "w") as fh:
        json.dump({"schema": 1, "repoId": ll.repo_identity(repo)}, fh)
    assert _git(folder, "remote", "get-url", "origin") == _git(repo, "remote", "get-url", "origin")
    primary_before = _snap(repo)
    folder_before = _snap(folder)
    calls = []
    result = _launch(repo, tmp_path, _spy(calls))
    _refused(repo, result, UNREADABLE, "not-launcher-owned", folder, calls, primary_before)
    assert _snap(folder) == folder_before


# --- row 10: the folder path is the same from every checkout of one repository ----------------


def test_row10_every_checkout_of_one_repository_names_the_same_folder(tmp_path):
    # axis: the folder path comes from the git common dir and the repository identity, not from the checkout's own name — see bite-proof record i2353_cloud_launch_folder
    repo = _cloud_repo(tmp_path)
    linked = str(tmp_path / "linked")
    _git(repo, "worktree", "add", "--detach", linked)
    alias = str(tmp_path / "alias")
    os.symlink(repo, alias)
    paths = [L.cloud_launch_folder_path(path) for path in (repo, linked, alias)]
    assert paths[0] is not None
    assert paths[0] == paths[1] == paths[2]
    assert paths[0].startswith(str(tmp_path / "wt-root") + os.sep)
    assert os.path.basename(paths[0]) == "cloud-launch-" + ll.repo_identity(repo)[:12]


# --- row 11: the folder is locked by another launch ---------------------------------------------


def test_row11_a_folder_another_launch_holds_refuses_busy_after_the_wait(tmp_path, monkeypatch):
    # axis: a folder lock another launch holds refuses after the wait and the command does not run — see bite-proof record i2353_cloud_launch_folder
    repo, folder = _world(tmp_path)
    monkeypatch.setattr(L, "_CLOUD_FOLDER_LOCK_WAIT_SECONDS", 0.3)
    primary_before = _snap(repo)
    folder_before = _snap(folder)
    fd = os.open(folder + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls))
    finally:
        os.close(fd)
    _assert_refused_cloud_lane(repo, result, "launch-cloud-folder-busy", "cloud-base")
    assert calls == []
    assert result["launchFolder"] == folder
    assert _snap(repo) == primary_before
    assert _snap(folder) == folder_before


# --- row 12: two launches with different bases ---------------------------------------------------


def test_row12_a_second_launch_during_a_running_one_is_refused_and_the_folder_stays(
    tmp_path, monkeypatch,
):
    # axis: the folder lock is held through the whole command, so a launch with another base cannot move the folder under the platform's read — see bite-proof record i2353_cloud_launch_folder
    repo, folder = _world(tmp_path)
    main = _head_sha(repo)
    pr = _remote_commit(tmp_path, repo, ["pr"], "pr.txt", start=main)
    monkeypatch.setattr(L, "_CLOUD_FOLDER_LOCK_WAIT_SECONDS", 0.3)
    seen = {}

    def during():
        seen["b"] = L._cloud_start_refusal(repo, {"baseCommit": pr}, dict(os.environ))
        seen["folder"] = (_symbolic(folder), _head_sha(folder))

    before = _snap(repo)
    calls = []
    result = _launch(
        repo, tmp_path, _spy(calls, during), premise=_valid_premise(repo, baseCommit=main))
    assert result["ok"] is True, result
    assert calls[0]["head"] == main
    reason, detail = seen["b"]
    assert reason == "launch-cloud-folder-busy"
    assert detail["launchFolder"] == folder
    assert seen["folder"] == (calls[0]["branch"], main)
    # The lock is released once the launch returned: the other base now passes and the folder moves.
    assert L._cloud_start_refusal(repo, {"baseCommit": pr}, dict(os.environ)) is None
    assert (_symbolic(folder), _head_sha(folder)) == ("pr", pr)
    assert _snap(repo) == before


# --- row 13: the setup verb ---------------------------------------------------------------------


def test_row13_the_setup_verb_makes_the_folder_once_and_never_overwrites_a_stranger(tmp_path):
    # axis: the setup verb makes a marked clone with the primary's origin once, and an existing path that is not the launcher's own is refused with nothing written
    repo = _cloud_repo(tmp_path)
    folder = L.cloud_launch_folder_path(repo)
    primary_before = _snap(repo)
    first = L.ensure_cloud_launch_folder(repo)
    assert first == {"ok": True, "folder": folder, "created": True, "reason": None}
    with open(os.path.join(folder, ".git", MARKER)) as fh:
        assert json.load(fh) == {"schema": 1, "repoId": ll.repo_identity(repo)}
    assert _git(folder, "remote", "get-url", "origin") == _git(repo, "remote", "get-url", "origin")
    assert _symbolic(folder) == _symbolic(repo)
    assert _snap(repo) == primary_before
    second = L.ensure_cloud_launch_folder(repo)
    assert second == {"ok": True, "folder": folder, "created": False, "reason": None}

    other = _cloud_repo(tmp_path / "other")
    stranger = L.cloud_launch_folder_path(other)
    os.makedirs(stranger)
    with open(os.path.join(stranger, "keep.txt"), "w") as fh:
        fh.write("keep\n")
    refused = L.ensure_cloud_launch_folder(other)
    assert refused == {
        "ok": False, "reason": "launch-cloud-folder-not-launcher-owned", "folder": stranger,
    }
    assert sorted(os.listdir(stranger)) == ["keep.txt"]
    with open(os.path.join(stranger, "keep.txt")) as fh:
        assert fh.read() == "keep\n"


def _run_verb(repo):
    got = subprocess.run(
        [sys.executable, "-B", L.__file__, "cloud-launch-folder", "--repo-root", repo],
        capture_output=True, text=True, env=dict(os.environ),
    )
    lines = [line for line in got.stdout.splitlines() if line.strip()]
    return got.returncode, json.loads(lines[-1])


def test_row13_the_cli_verb_prints_the_result_and_exits_by_it(tmp_path):
    # axis: the CLI verb prints the ensure result as one JSON line and exits 0 when ok and 1 when not
    repo = _cloud_repo(tmp_path)
    folder = L.cloud_launch_folder_path(repo)
    code, printed = _run_verb(repo)
    assert code == 0
    assert printed == {"ok": True, "folder": folder, "created": True, "reason": None}
    assert os.path.isdir(os.path.join(folder, ".git"))

    other = _cloud_repo(tmp_path / "other")
    stranger = L.cloud_launch_folder_path(other)
    os.makedirs(stranger)
    code, printed = _run_verb(other)
    assert code == 1
    assert printed == {
        "ok": False, "reason": "launch-cloud-folder-not-launcher-owned", "folder": stranger,
    }
    assert os.listdir(stranger) == []


# --- row 14: an adoption -------------------------------------------------------------------------


def test_row14_an_adoption_launches_from_the_folder_on_the_adopted_branch_at_its_head(tmp_path):
    # axis: an adoption whose adopted branch's remote tip is its adopted head targets that branch and head, not the base
    repo = _cloud_repo(tmp_path)
    base = _head_sha(repo)
    head = _commit(repo, "adopted.txt")
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/feature")
    _git(repo, "reset", "-q", "--hard", base)
    ensured = L.ensure_cloud_launch_folder(repo)
    assert ensured["ok"] is True, ensured
    folder = ensured["folder"]
    before = _snap(repo)
    calls = []
    result = _launch(
        repo, tmp_path, _spy(calls),
        premise=_valid_premise(repo, baseCommit=base, adoptsBranch="feature", adoptsHead=head),
    )
    assert result["ok"] is True, result
    assert len(calls) == 1
    assert calls[0]["cwd"] == folder
    assert calls[0]["branch"] == "feature"
    assert calls[0]["head"] == head
    assert _snap(repo) == before


# --- the branch choice, read directly ------------------------------------------------------------


def test_the_branch_choice_prefers_the_default_branch_then_the_lexically_first(tmp_path):
    # axis: among branches whose tip is the base, the remote's default branch wins, else the lexically first
    repo, folder = _world(tmp_path)
    base = _head_sha(repo)
    default = _symbolic(folder)
    env = dict(os.environ)
    assert default != "main"
    assert L._choose_cloud_launch_branch(folder, {"baseCommit": base}, env) == (
        default, base, None)
    _remote_commit(tmp_path, repo, [default], "ahead.txt", start=base)
    assert L._choose_cloud_launch_branch(folder, {"baseCommit": base}, env) == (
        "main", base, None)
    assert L._choose_cloud_launch_branch(folder, {"baseCommit": "0" * 40}, env) == (
        None, None, "no-branch-at-base")
