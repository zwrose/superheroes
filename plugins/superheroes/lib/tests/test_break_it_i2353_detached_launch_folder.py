"""Destroying-work regression: repair must retain detached local commits."""

import pytest

from test_launcher_cloud_launch_folder import (
    _commit,
    _git,
    _head_sha,
    _isolated,  # noqa: F401 - pytest discovers this imported isolation fixture.
    _launch,
    _snap,
    _spy,
    _symbolic,
    _world,
)

pytestmark = pytest.mark.usefixtures("_isolated")


def test_launch_retains_work_committed_on_the_setup_folders_detached_head(tmp_path):
    # axis: repair must retain a newly committed detached HEAD, either in place or under a ref; switching to the remote target without preservation must fail this check.
    repo, folder = _world(tmp_path)
    assert _symbolic(folder) is None
    mine = _commit(folder, "detached-owner-work.txt", "keep this work\n")
    assert _git(folder, "status", "--porcelain", "--untracked-files=all") == ""
    assert not _git(
        folder, "for-each-ref", "--contains=" + mine, "--format=%(refname)"
    ).strip()
    primary_before = _snap(repo)
    calls = []

    result = _launch(repo, tmp_path, _spy(calls))

    assert result["ok"] or result.get("folderRepair") == "local-commits", result
    if result["ok"]:
        assert len(calls) == 1
    else:
        assert calls == []
    assert _snap(repo) == primary_before
    retained = _git(
        folder, "for-each-ref", "--contains=" + mine, "--format=%(refname)"
    ).strip()
    assert _head_sha(folder) == mine or retained, (
        "cloud folder repair abandoned a detached local commit without retaining a ref"
    )
