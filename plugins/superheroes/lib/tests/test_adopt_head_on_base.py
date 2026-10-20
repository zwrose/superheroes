"""Tests for the launcher's refusal of an adoption whose head is not on its base (issue #2002).

A premise that carries `adoptsHead` reaches no reservation, worktree, cloud command or spawn unless
the adopted head descends from the resolved `baseCommit` in the launching checkout. Everything else
refuses `premise-adopts-head-not-on-base` before anything is spent. Nothing here touches the
network: the repositories are throwaway, with a bare remote under tmp_path for the cloud path.
"""
import os
import subprocess
import types

import pytest

from test_launcher import (
    L,
    _all_checks,
    _head_sha,
    _init_repo,
    _make_spawn_fn,
    _valid_premise,
)
from test_launcher_cloud import (  # noqa: F401  (_isolated is an autouse fixture)
    ENV_ID,
    _assert_refused_cloud_lane,
    _cloud_repo,
    _fake_spawn,
    _git,
    _isolated,
    _launch,
)

TOKEN = "premise-adopts-head-not-on-base"
BRANCH = "feature/adopted-2002"
_UNDECIDABLE_PREFIX = (
    "Ancestry could not be decided in the launching checkout: fetch the adopted branch so its "
    "head is present, then launch again. If it still does not descend from baseCommit: "
)
_BOTTOM_REMEDY = (
    "Bring the adopted branch current with its base first: merge the base into it and push, then "
    "launch again with the same baseCommit. Or set baseCommit to the adopted head and launch with "
    "--repo-root set to a worktree on the adopted branch at that head."
)
_STACKED_REMEDY = (
    "Bring the adopted branch current with the layer below first: merge the layer below's head "
    "into it and push, then launch again with the same baseCommit. A layer above the bottom keeps "
    "the layer below's head as its base."
)


def _commit_on(repo, parent):
    """A new commit whose only parent is `parent` and whose tree is the parent's; its sha."""
    return _git(
        repo, "-c", "user.email=t@t.local", "-c", "user.name=t",
        "commit-tree", parent + "^{tree}", "-p", parent, "-m", "adopted",
    ).strip()


def _fork_and_main(tmp_path, cloud):
    """A repository whose main head is the base, with an older commit before it.

    Returns `(repo, base, older)`; `cloud` makes the base reachable on a bare remote.
    """
    repo = _cloud_repo(tmp_path) if cloud else _init_repo(tmp_path / "repo")
    older = _head_sha(repo)
    (tmp_path / "repo" / "second.txt").write_text("second\n")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-q", "-m", "second")
    base = _head_sha(repo)
    if cloud:
        branch = _git(repo, "symbolic-ref", "--short", "HEAD").strip()
        _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
        _git(repo, "push", "-q", "-f", "origin", "HEAD:refs/heads/%s" % branch)
        _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo, base, older


def _env():
    return dict(os.environ)


# --- the launch path ----------------------------------------------------------------------


def test_cloud_launch_with_a_not_descendant_head_refuses_before_spend(tmp_path):
    # axis: an adopted head that does not descend from the base refuses before the cloud command
    repo, base, older = _fork_and_main(tmp_path, cloud=True)
    head = _commit_on(repo, older)
    calls = []
    premise = _valid_premise(repo, baseCommit=base, adoptsBranch=BRANCH, adoptsHead=head)
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), premise=premise)
    _assert_refused_cloud_lane(repo, result, TOKEN, "premise")
    assert result["ancestry"] == "not-descendant"
    assert result["adoptsHead"] == head
    assert result["baseCommit"] == base
    assert result["remedy"] == _BOTTOM_REMEDY
    assert calls == []


def test_local_launch_with_a_not_descendant_head_refuses_and_spawns_nothing(tmp_path):
    # axis: the refusal holds for a local launch too — no child is spawned
    repo, base, older = _fork_and_main(tmp_path, cloud=False)
    head = _commit_on(repo, older)
    spawned = []
    delegate = _make_spawn_fn("sleep")

    def recording_spawn(*args, **kwargs):
        spawned.append(args)
        return delegate(*args, **kwargs)

    premise = _valid_premise(repo, baseCommit=base, adoptsBranch=BRANCH, adoptsHead=head)
    result = L.launch_build(
        repo, 656, premise, _all_checks(), str(tmp_path / "logs"),
        spawn_fn=recording_spawn, settle_seconds=0.2,
    )
    assert result["ok"] is False
    assert result["reason"] == TOKEN
    assert result["ancestry"] == "not-descendant"
    assert spawned == []


def test_cloud_launch_with_a_head_that_descends_from_its_base_passes(tmp_path):
    # axis: a child commit of the base is a descendant and the launch goes ahead
    repo, base, _older = _fork_and_main(tmp_path, cloud=True)
    head = _commit_on(repo, base)
    calls = []
    premise = _valid_premise(repo, baseCommit=base, adoptsBranch=BRANCH, adoptsHead=head)
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), premise=premise)
    assert result["ok"] is True, result
    assert len(calls) == 1


def test_cloud_launch_with_the_head_as_its_own_base_passes(tmp_path):
    # axis: the adopted head equal to the base is its own ancestor and passes
    repo = _cloud_repo(tmp_path)
    branch = _git(repo, "symbolic-ref", "--short", "HEAD").strip()
    head = _head_sha(repo)
    calls = []
    premise = _valid_premise(repo, baseCommit=head, adoptsBranch=branch, adoptsHead=head)
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), premise=premise)
    assert result["ok"] is True, result
    assert len(calls) == 1


def test_cloud_launch_with_a_head_missing_locally_refuses_undecidable(tmp_path):
    # axis: an adopted head that is not a commit here cannot be decided and refuses
    repo, base, _older = _fork_and_main(tmp_path, cloud=True)
    calls = []
    premise = _valid_premise(repo, baseCommit=base, adoptsBranch=BRANCH, adoptsHead="e" * 40)
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), premise=premise)
    _assert_refused_cloud_lane(repo, result, TOKEN, "premise")
    assert result["ancestry"] == "undecidable"
    assert result["remedy"] == _UNDECIDABLE_PREFIX + _BOTTOM_REMEDY
    assert result["remedy"].startswith(_UNDECIDABLE_PREFIX)
    assert calls == []


# --- the helper, called directly ----------------------------------------------------------


def _stamped(base, head, **more):
    stamped = {"baseCommit": base, "adoptsBranch": BRANCH, "adoptsHead": head}
    stamped.update(more)
    return stamped


def _done(code):
    return types.SimpleNamespace(returncode=code, stdout="", stderr="")


@pytest.mark.parametrize("case", ["rev-parse-cannot-run", "merge-base-cannot-run"])
def test_git_that_cannot_run_refuses_undecidable(tmp_path, monkeypatch, case):
    # axis: a git read that could not run (timeout, no git) refuses undecidable, never passes
    repo, base, older = _fork_and_main(tmp_path, cloud=False)
    head = _commit_on(repo, base)
    real = L._git_scrubbed
    asked = []

    def flaky(repo_root, *args, **kwargs):
        asked.append(args[0])
        if case == "rev-parse-cannot-run" and args[0] == "rev-parse":
            return None
        if case == "merge-base-cannot-run" and args[0] == "merge-base":
            return None
        return real(repo_root, *args, **kwargs)

    monkeypatch.setattr(L, "_git_scrubbed", flaky)
    got = L._adopted_head_refusal(repo, _stamped(base, head), _env())
    assert got is not None
    reason, detail = got
    assert reason == TOKEN
    assert detail["ancestry"] == "undecidable"
    assert asked[0] == "rev-parse"
    assert ("merge-base" in asked) == (case == "merge-base-cannot-run")


@pytest.mark.parametrize("code", [128, 2])
def test_a_merge_base_exit_other_than_zero_or_one_refuses_undecidable(
    tmp_path, monkeypatch, code,
):
    # axis: only exit 1 is a verdict of not-descendant; any other non-zero exit is undecidable
    repo, base, _older = _fork_and_main(tmp_path, cloud=False)
    head = _commit_on(repo, base)
    real = L._git_scrubbed

    def fake(repo_root, *args, **kwargs):
        if args[0] == "merge-base":
            return _done(code)
        return real(repo_root, *args, **kwargs)

    monkeypatch.setattr(L, "_git_scrubbed", fake)
    reason, detail = L._adopted_head_refusal(repo, _stamped(base, head), _env())
    assert reason == TOKEN
    assert detail["ancestry"] == "undecidable"
    assert detail["remedy"].startswith(_UNDECIDABLE_PREFIX)


def test_a_rev_parse_failure_refuses_undecidable_without_asking_merge_base(
    tmp_path, monkeypatch,
):
    # axis: the ancestry question is asked only of a head that resolved to a commit
    repo, base, _older = _fork_and_main(tmp_path, cloud=False)
    asked = []

    def fake(repo_root, *args, **kwargs):
        asked.append(args[0])
        return _done(1)

    monkeypatch.setattr(L, "_git_scrubbed", fake)
    reason, detail = L._adopted_head_refusal(repo, _stamped(base, "d" * 40), _env())
    assert (reason, detail["ancestry"]) == (TOKEN, "undecidable")
    assert asked == ["rev-parse"]


def test_a_stamped_premise_without_adopts_head_passes_without_running_git(monkeypatch):
    # axis: a premise that adopts nothing is none of this check's business
    def boom(*args, **kwargs):
        raise AssertionError("git must not run")

    monkeypatch.setattr(L, "_git_scrubbed", boom)
    assert L._adopted_head_refusal(".", {"baseCommit": "a" * 40}, _env()) is None


@pytest.mark.parametrize("base", [None, "", "main", "a" * 39, "a" * 41, 7])
def test_a_base_that_is_not_a_resolved_sha_refuses_undecidable_without_running_git(
    monkeypatch, base,
):
    # axis: an absent or unresolved base refuses undecidable and git is not asked
    def boom(*args, **kwargs):
        raise AssertionError("git must not run")

    monkeypatch.setattr(L, "_git_scrubbed", boom)
    stamped = {"adoptsBranch": BRANCH, "adoptsHead": "b" * 40}
    if base is not None:
        stamped["baseCommit"] = base
    reason, detail = L._adopted_head_refusal(".", stamped, _env())
    assert reason == TOKEN
    assert detail["ancestry"] == "undecidable"
    assert set(detail) == {"adoptsHead", "baseCommit", "ancestry", "remedy"}


def test_a_stacked_layer_above_the_bottom_gets_the_stacked_remedy(tmp_path):
    # axis: a layer above the bottom is told to bring the branch current with the layer below
    repo, base, older = _fork_and_main(tmp_path, cloud=False)
    head = _commit_on(repo, older)
    stamped = _stamped(base, head, stack=7, layerPosition=2)
    reason, detail = L._adopted_head_refusal(repo, stamped, _env())
    assert reason == TOKEN
    assert detail["ancestry"] == "not-descendant"
    assert detail["remedy"] == _STACKED_REMEDY
    assert set(detail) == {"adoptsHead", "baseCommit", "ancestry", "remedy"}
    bottom = dict(stamped, layerPosition=1)
    assert L._adopted_head_refusal(repo, bottom, _env())[1]["remedy"] == _BOTTOM_REMEDY
    boolean = dict(stamped, layerPosition=True)
    assert L._adopted_head_refusal(repo, boolean, _env())[1]["remedy"] == _BOTTOM_REMEDY
