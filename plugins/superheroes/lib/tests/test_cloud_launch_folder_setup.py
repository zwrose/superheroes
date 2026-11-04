"""The launcher's cloud launch folder (#2353, layer 1): make it, validate it, never write a path
that is not the launcher's own.

Direct tests of ``cloud_launch_folder_path``, ``_validate_cloud_launch_folder`` and
``ensure_cloud_launch_folder``; no launch uses the folder at this layer.
"""
import json
import os
import subprocess
import sys

import pytest

import launch_ledger as ll

from test_launcher import L, _head_sha, _init_repo  # noqa: F401
from test_launcher_cloud import _cloud_repo

_LAUNCHER = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "launcher.py"))
_IDENT = ["-c", "user.email=test@test.local", "-c", "user.name=test"]


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger-root"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "wt-root"))


def _git(path, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=check,
    )


def _snapshot(primary):
    """What the primary checkout shows: its branch (or detached), head, status and local branches."""
    head_ref = _git(primary, "symbolic-ref", "-q", "HEAD", check=False)
    return {
        "head-ref": (head_ref.returncode, head_ref.stdout),
        "head": _git(primary, "rev-parse", "HEAD").stdout,
        "status": _git(primary, "status", "--porcelain").stdout,
        "branches": _git(primary, "for-each-ref", "refs/heads").stdout,
    }


def _marker(folder):
    gitdir = _git(folder, "rev-parse", "--absolute-git-dir").stdout.strip()
    return os.path.join(gitdir, L._CLOUD_FOLDER_MARKER)


def _made(tmp_path):
    """A primary and the launcher's folder made for it."""
    primary = _cloud_repo(tmp_path)
    got = L.ensure_cloud_launch_folder(primary)
    assert got["ok"] is True and got["created"] is True, got
    return primary, got["folder"]


def test_one_path_for_the_primary_a_linked_worktree_and_a_symlink_alias(tmp_path):
    primary = _cloud_repo(tmp_path)
    linked = str(tmp_path / "linked")
    _git(primary, "worktree", "add", "--detach", linked)
    alias = str(tmp_path / "alias")
    os.symlink(primary, alias)
    before = _snapshot(primary)

    # axis: the path comes from the common dir and the repository identity, not from the checkout's own basename
    here = L.cloud_launch_folder_path(primary)
    assert here is not None
    assert L.cloud_launch_folder_path(linked) == here
    assert L.cloud_launch_folder_path(alias) == here
    assert os.path.basename(here) == "cloud-launch-" + ll.repo_identity(primary)[:12]
    assert here.endswith("cloud-launch-" + ll.repo_identity(primary)[:12])
    assert _snapshot(primary) == before


def test_ensure_makes_an_independent_marked_clone_and_a_second_call_changes_nothing(tmp_path):
    primary = _cloud_repo(tmp_path)
    before = _snapshot(primary)

    got = L.ensure_cloud_launch_folder(primary)

    assert got["ok"] is True and got["created"] is True and got["reason"] is None, got
    folder = got["folder"]
    assert folder == L.cloud_launch_folder_path(primary)
    assert os.path.isdir(os.path.join(folder, ".git"))
    assert _git(folder, "remote", "get-url", "origin").stdout == _git(primary, "remote", "get-url", "origin").stdout
    with open(_marker(folder), encoding="utf-8") as fh:
        said = json.load(fh)
    assert said["schema"] == 1
    assert said["repoId"] == ll.repo_identity(primary)
    assert L._validate_cloud_launch_folder(primary, folder, None) is None

    head = _git(folder, "rev-parse", "HEAD").stdout
    status = _git(folder, "status", "--porcelain").stdout
    again = L.ensure_cloud_launch_folder(primary)
    assert again["ok"] is True and again["created"] is False and again["folder"] == folder, again
    assert _git(folder, "rev-parse", "HEAD").stdout == head
    assert _git(folder, "status", "--porcelain").stdout == status
    assert _snapshot(primary) == before


def test_the_new_clone_is_detached_with_no_local_branch_though_the_primary_has_unpushed_commits(tmp_path):
    primary = _cloud_repo(tmp_path)
    _git(primary, *_IDENT, "commit", "-q", "--allow-empty", "-m", "unpushed")
    before = _snapshot(primary)
    assert before["head-ref"][0] == 0

    got = L.ensure_cloud_launch_folder(primary)

    assert got["ok"] is True and got["created"] is True, got
    folder = got["folder"]
    # axis: the clone copies the primary's checked-out branch, so it is detached and every local branch is dropped
    assert _git(folder, "symbolic-ref", "-q", "HEAD", check=False).returncode != 0
    assert _git(folder, "for-each-ref", "refs/heads/").stdout == ""
    assert _git(folder, "rev-parse", "HEAD").stdout == before["head"]
    assert _snapshot(primary) == before


def test_a_non_owned_directory_at_the_path_is_refused_and_left_untouched(tmp_path):
    primary = _cloud_repo(tmp_path)
    path = L.cloud_launch_folder_path(primary)
    os.makedirs(path)
    with open(os.path.join(path, "keep.txt"), "w", encoding="utf-8") as fh:
        fh.write("mine\n")
    before = _snapshot(primary)

    got = L.ensure_cloud_launch_folder(primary)

    assert got["ok"] is False
    assert got["reason"] == "launch-cloud-folder-not-launcher-owned"
    assert got["folder"] == path
    assert os.listdir(path) == ["keep.txt"]
    with open(os.path.join(path, "keep.txt"), encoding="utf-8") as fh:
        assert fh.read() == "mine\n"
    assert _snapshot(primary) == before


def test_validator_says_missing_for_an_absent_path(tmp_path):
    primary = _cloud_repo(tmp_path)
    path = L.cloud_launch_folder_path(primary)
    assert not os.path.lexists(path)
    assert L._validate_cloud_launch_folder(primary, path, None) == "missing"


def test_validator_refuses_a_symlink_to_a_genuine_launcher_clone(tmp_path):
    primary, folder = _made(tmp_path)
    aside = folder + "-aside"
    os.rename(folder, aside)
    os.symlink(aside, folder)
    before = _snapshot(primary)

    # axis: a symlink at the path is not the launcher's own folder, whatever it points at
    assert L._validate_cloud_launch_folder(primary, folder, None) == "not-launcher-owned"
    assert _snapshot(primary) == before


def test_validator_refuses_a_symlink_to_the_primary(tmp_path):
    primary = _cloud_repo(tmp_path)
    path = L.cloud_launch_folder_path(primary)
    os.makedirs(os.path.dirname(path))
    os.symlink(primary, path)
    before = _snapshot(primary)

    assert L._validate_cloud_launch_folder(primary, path, None) == "not-launcher-owned"
    assert _snapshot(primary) == before


def test_validator_refuses_a_linked_worktree_even_with_a_valid_marker(tmp_path):
    primary = _cloud_repo(tmp_path)
    path = L.cloud_launch_folder_path(primary)
    os.makedirs(os.path.dirname(path))
    _git(primary, "worktree", "add", "--detach", path)
    with open(_marker(path), "w", encoding="utf-8") as fh:
        json.dump({"schema": 1, "repoId": ll.repo_identity(primary)}, fh)
    assert os.path.isfile(_marker(path))
    before = _snapshot(primary)

    # axis: the folder keeps its own object store and git dir, independent of the primary's
    assert L._validate_cloud_launch_folder(primary, path, None) == "not-launcher-owned"
    assert _snapshot(primary) == before


def test_validator_refuses_a_clone_whose_marker_was_removed(tmp_path):
    primary, folder = _made(tmp_path)
    assert L._validate_cloud_launch_folder(primary, folder, None) is None
    os.remove(_marker(folder))
    before = _snapshot(primary)

    # axis: only a folder carrying the launcher's marker is its own
    assert L._validate_cloud_launch_folder(primary, folder, None) == "not-launcher-owned"
    assert _snapshot(primary) == before


def test_validator_refuses_a_clone_whose_marker_is_a_symlink_to_a_valid_marker(tmp_path):
    primary, folder = _made(tmp_path)
    marker = _marker(folder)
    real = str(tmp_path / "real-marker")
    os.rename(marker, real)
    os.symlink(real, marker)
    assert json.load(open(marker, encoding="utf-8"))["repoId"] == ll.repo_identity(primary)
    before = _snapshot(primary)

    # axis: only a folder carrying the launcher's own marker file (not a link to one) is its own
    assert L._validate_cloud_launch_folder(primary, folder, None) == "not-launcher-owned"
    assert _snapshot(primary) == before


def test_validator_refuses_a_clone_whose_marker_names_another_repository(tmp_path):
    primary, folder = _made(tmp_path)
    with open(_marker(folder), "w", encoding="utf-8") as fh:
        json.dump({"schema": 1, "repoId": "0" * 40}, fh)
    before = _snapshot(primary)

    assert L._validate_cloud_launch_folder(primary, folder, None) == "not-launcher-owned"
    assert _snapshot(primary) == before


def test_validator_refuses_a_clone_whose_origin_is_another_url(tmp_path):
    primary, folder = _made(tmp_path)
    _git(folder, "remote", "set-url", "origin", str(tmp_path / "elsewhere.git"))
    before = _snapshot(primary)

    assert L._validate_cloud_launch_folder(primary, folder, None) == "not-launcher-owned"
    assert _snapshot(primary) == before


def test_a_failure_after_the_clone_began_leaves_no_folder_behind(tmp_path, monkeypatch):
    primary = _cloud_repo(tmp_path)
    path = L.cloud_launch_folder_path(primary)
    before = _snapshot(primary)
    # The clone step succeeds; the step that writes the marker cannot find where to write it.
    monkeypatch.setattr(L, "_cloud_folder_marker_path", lambda folder, env: None)

    got = L.ensure_cloud_launch_folder(primary)

    # axis: a failure after the clone began removes the path this call created
    assert got["ok"] is False
    assert got["reason"] == "launch-cloud-folder-create-failed"
    assert got["folder"] == path
    assert not os.path.lexists(path)
    assert _snapshot(primary) == before


def _run_cli(primary, tmp_path):
    env = dict(os.environ)
    got = subprocess.run(
        [sys.executable, "-B", _LAUNCHER, "cloud-launch-folder", "--repo-root", primary],
        capture_output=True, text=True, env=env,
    )
    lines = got.stdout.strip().splitlines()
    assert len(lines) == 1, got
    return got.returncode, json.loads(lines[0])


def test_the_cli_prints_one_json_line_and_exits_zero_on_ok(tmp_path):
    primary = _cloud_repo(tmp_path)
    before = _snapshot(primary)

    code, said = _run_cli(primary, tmp_path)

    assert code == 0
    assert said["ok"] is True and said["created"] is True
    assert said["folder"] == L.cloud_launch_folder_path(primary)
    assert L._validate_cloud_launch_folder(primary, said["folder"], None) is None
    assert _snapshot(primary) == before


def test_the_cli_exits_one_when_the_path_is_not_the_launchers_own(tmp_path):
    primary = _cloud_repo(tmp_path)
    path = L.cloud_launch_folder_path(primary)
    os.makedirs(path)
    before = _snapshot(primary)

    code, said = _run_cli(primary, tmp_path)

    assert code == 1
    assert said["ok"] is False
    assert said["reason"] == "launch-cloud-folder-not-launcher-owned"
    assert os.listdir(path) == []
    assert _snapshot(primary) == before
