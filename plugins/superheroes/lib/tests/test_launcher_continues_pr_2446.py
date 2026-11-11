"""Tests for the launcher's refusal of a leg that continues an existing pull request's branch
without the adoption pair (issue #2446).

A workhorse premise that carries `adopts`, or whose `surfaces` name an open pull request's head
branch by explicit wording, reaches no reservation, worktree, cloud command or spawn unless it also
carries `adoptsBranch` and `adoptsHead`. Nothing here touches the network: the repositories are
throwaway, the origin is a URL string only, and the read of the open pull requests is replaced.
"""
import json
import os
import signal
import subprocess
import types

import pytest

from test_launcher import (
    L,
    _adoption_members,
    _all_checks,
    _head_sha,
    _init_repo,
    _make_spawn_fn,
    _membership_ok,
    _pr_lookup_ok,
    _stack_premise,
    _valid_premise,
)
from test_launcher_cloud import (  # noqa: F401  (_isolated is an autouse fixture)
    _assert_refused_cloud_lane,
    _cloud_repo,
    _fake_spawn,
    _git,
    _isolated,
    _launch,
)

WITHOUT = "premise-continues-pr-without-adoption"
UNREAD = "premise-continues-pr-unread"
URL = "https://github.com/o/r.git"
BRANCH = "build/2434-span-tie"
NUMBER = 2435
PR_HEAD = "b" * 40


def _env():
    return dict(os.environ)


def _set_origin(repo, url):
    verb = "set-url" if "origin" in _git(repo, "remote").split() else "add"
    _git(repo, "remote", verb, "origin", url)


def _pull(number=NUMBER, branch=BRANCH, head=PR_HEAD, full_name="o/r"):
    """A row of GitHub's open-pulls answer."""
    return {
        "number": number,
        "head": {"ref": branch, "sha": head, "repo": {"full_name": full_name}},
    }


def _answer(rows, code=0):
    return types.SimpleNamespace(returncode=code, stdout=json.dumps(rows), stderr="")


def _replace_read(monkeypatch, rows=None, failed=None):
    """Replace the whole read of the open pull requests with a recorder; the list of its calls."""
    calls = []

    def read(repo_root, owner, repo, env, deadline=None):
        calls.append((owner, repo))
        return (list(rows or []), failed)

    monkeypatch.setattr(L, "_open_pulls_fn", read)
    return calls


def _replace_pages(monkeypatch, pages):
    """Replace the page read: `pages` is a function of the page number; the list of page numbers."""
    asked = []

    def page_read(owner, repo, page, env, timeout):
        asked.append(page)
        return pages(page)

    monkeypatch.setattr(L, "_gh_open_pulls_page", page_read)
    return asked


def _github_repo(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _set_origin(repo, URL)
    return repo


def _commit_on(repo, parent):
    """A new commit whose only parent is `parent` and whose tree is the parent's; its sha."""
    return _git(
        repo, "-c", "user.email=t@t.local", "-c", "user.name=t",
        "commit-tree", parent + "^{tree}", "-p", parent, "-m", "adopted",
    ).strip()


def _local_launch(repo, tmp_path, premise):
    """A local launch with a recording spawn; `(result, spawned)`. A child it started is stopped."""
    spawned = []
    delegate = _make_spawn_fn("sleep")

    def recording_spawn(*args, **kwargs):
        spawned.append(args)
        return delegate(*args, **kwargs)

    result = L.launch_build(
        repo, 656, premise, _all_checks(), str(tmp_path / "logs"),
        spawn_fn=recording_spawn, settle_seconds=0.2,
    )
    if result.get("ok"):
        try:
            os.kill(result["pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass
    return result, spawned


def _assert_without_adoption(result, surface, number=NUMBER, branch=BRANCH, head=PR_HEAD):
    assert result["ok"] is False
    assert result["reason"] == WITHOUT
    assert result["continuedPulls"] == [
        {"number": number, "branch": branch, "head": head, "matchedIn": surface}
    ]
    assert result["remedy"] == L._CONTINUES_PR_REMEDY_WITHOUT_ADOPTION


# --- the launch path: each wording refuses before spend ----------------------------------------


@pytest.mark.parametrize("lane", ["local", "cloud"])
def test_an_origin_branch_token_refuses_before_spend(tmp_path, monkeypatch, lane):
    # axis: an origin/<branch> token names the open pull request, local and cloud alike (E2, E9)
    surface = "origin/" + BRANCH
    _replace_read(monkeypatch, [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}])
    if lane == "cloud":
        repo = _cloud_repo(tmp_path)
        _set_origin(repo, URL)
        calls = []
        premise = _valid_premise(repo, surfaces=[surface])
        result = _launch(repo, tmp_path, _fake_spawn(calls=calls), premise=premise)
        _assert_refused_cloud_lane(repo, result, WITHOUT, "premise")
        assert calls == []
    else:
        repo = _github_repo(tmp_path)
        result, spawned = _local_launch(repo, tmp_path, _valid_premise(repo, surfaces=[surface]))
        assert spawned == []
    _assert_without_adoption(result, surface)


def test_a_branch_colon_token_refuses(tmp_path, monkeypatch):
    # axis: a branch:<branch> token names the open pull request (E2)
    surface = "branch:" + BRANCH
    _replace_read(monkeypatch, [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}])
    repo = _github_repo(tmp_path)
    result, spawned = _local_launch(repo, tmp_path, _valid_premise(repo, surfaces=[surface]))
    assert spawned == []
    _assert_without_adoption(result, surface)


def test_the_word_branch_beside_the_name_refuses(tmp_path, monkeypatch):
    # axis: the word branch plus a token equal to the branch's name names the pull request (E3)
    surface = "PR 2435 branch " + BRANCH
    _replace_read(monkeypatch, [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}])
    repo = _github_repo(tmp_path)
    result, spawned = _local_launch(repo, tmp_path, _valid_premise(repo, surfaces=[surface]))
    assert spawned == []
    _assert_without_adoption(result, surface)


@pytest.mark.parametrize("surface", [
    "continue #2435's branch", "continue #2435’s branch", "the #2435 branch",
])
def test_a_number_s_branch_phrase_refuses(tmp_path, monkeypatch, surface):
    # axis: a #N's branch phrase names the open pull request by number (E4)
    _replace_read(monkeypatch, [{"number": NUMBER, "branch": "feature/other", "head": PR_HEAD}])
    repo = _github_repo(tmp_path)
    result, spawned = _local_launch(repo, tmp_path, _valid_premise(repo, surfaces=[surface]))
    assert spawned == []
    _assert_without_adoption(result, surface, branch="feature/other")


@pytest.mark.parametrize("surface", ["branch of PR #2435", "the branch of #2435"])
def test_a_branch_of_pr_phrase_refuses(tmp_path, monkeypatch, surface):
    # axis: a branch of PR #N phrase names the open pull request by number (E5)
    _replace_read(monkeypatch, [{"number": NUMBER, "branch": "feature/other", "head": PR_HEAD}])
    repo = _github_repo(tmp_path)
    result, spawned = _local_launch(repo, tmp_path, _valid_premise(repo, surfaces=[surface]))
    assert spawned == []
    _assert_without_adoption(result, surface, branch="feature/other")


def test_adopts_without_the_pair_refuses_with_no_read(tmp_path, monkeypatch):
    # axis: adopts without the pair refuses with matchedIn adopts and makes no read (E1)
    calls = _replace_read(monkeypatch, [])
    repo = _init_repo(tmp_path / "repo")
    head = _head_sha(repo)
    spawned = []
    delegate = _make_spawn_fn("sleep")

    def recording_spawn(*args, **kwargs):
        spawned.append(args)
        return delegate(*args, **kwargs)

    members = _adoption_members(head, occupant_head=head)
    result = L.launch_build(
        repo, 656, _stack_premise(repo, stack=7, layerPosition=2, adopts=4242),
        _all_checks(), str(tmp_path / "logs"),
        spawn_fn=recording_spawn, settle_seconds=0.2,
        pr_lookup=lambda *a, **k: _pr_lookup_ok(),
        membership_reader=lambda **kw: _membership_ok(1, head, members=members),
    )
    assert result["ok"] is False
    assert result["reason"] == WITHOUT
    assert result["continuedPulls"] == [{"number": 4242, "matchedIn": "adopts"}]
    assert result["remedy"] == L._CONTINUES_PR_REMEDY_ADOPTS
    assert calls == []
    assert spawned == []


@pytest.mark.parametrize("url", [None, "git@gitlab.example:o/r.git", URL])
def test_adopts_without_the_pair_refuses_whatever_the_origin(tmp_path, monkeypatch, url):
    # axis: the origin exemptions bite on the surface path only; adopts refuses on any origin (E1)
    calls = _replace_read(monkeypatch, [])
    repo = _init_repo(tmp_path / "repo")
    if url:
        _set_origin(repo, url)
    stamped = {"surfaces": ["lib"], "adopts": 4242, "adoptsBranch": "b2"}
    reason, detail = L._continues_pr_refusal(repo, stamped, _env())
    assert reason == WITHOUT
    assert detail == {
        "continuedPulls": [{"number": 4242, "matchedIn": "adopts"}],
        "remedy": L._CONTINUES_PR_REMEDY_ADOPTS,
    }
    assert calls == []


def test_a_surface_naming_a_dependency_pull_request_branch_still_refuses(tmp_path, monkeypatch):
    # axis: a premise that names a dependency still refuses when a surface names an open branch (E2)
    _replace_read(monkeypatch, [{"number": 77, "branch": "dep/branch", "head": PR_HEAD}])
    repo = _github_repo(tmp_path)
    stamped = {"surfaces": ["origin/dep/branch"], "dependency": 77, "baseCommit": "a" * 40}
    reason, detail = L._continues_pr_refusal(repo, stamped, _env())
    assert reason == WITHOUT
    assert [row["number"] for row in detail["continuedPulls"]] == [77]


def test_each_pull_request_is_named_once_by_its_first_surface(tmp_path, monkeypatch):
    # axis: continuedPulls lists each open pull request once, in pull order, with its first surface
    pulls = [
        {"number": 5, "branch": "a/one", "head": "1" * 40},
        {"number": 6, "branch": "a/two", "head": "2" * 40},
        {"number": 7, "branch": "a/three", "head": "3" * 40},
    ]
    named = L._named_open_pulls(
        ["lib", "origin/a/two.", "branch:a/two", "origin/a/one"], pulls,
    )
    assert [(row["number"], row["matchedIn"]) for row in named] == [
        (5, "origin/a/one"), (6, "origin/a/two."),
    ]


# --- fail closed: the open pull requests cannot be read -----------------------------------------


def _unread(repo):
    return L._continues_pr_refusal(
        repo, {"surfaces": ["origin/x"], "baseCommit": "a" * 40}, _env(),
    )


def _full_page(page):
    return _answer([_pull(1000 * page + i, "other/%d" % i) for i in range(100)])


_BAD_ROWS = {
    "not-a-dict": 5,
    "number-bool": _pull(number=True),
    "number-zero": _pull(number=0),
    "number-string": _pull(number="7"),
    "head-missing": {"number": 7},
    "head-not-a-dict": {"number": 7, "head": "x"},
    "ref-not-a-string": {"number": 7, "head": {"ref": 3, "sha": PR_HEAD}},
    "sha-short": _pull(head="b" * 39),
    "sha-uppercase": _pull(head="B" * 40),
    "sha-not-a-string": _pull(head=None),
}


@pytest.mark.parametrize("case", [
    "gh-unrunnable", "gh-failed", "gh-failed-page-two", "json-object", "json-garbage",
    "page-cap",
] + ["row-" + name for name in _BAD_ROWS])
def test_an_unreadable_open_pull_list_refuses_unread(tmp_path, monkeypatch, case):
    # axis: every way the open-pull read can fail closed refuses unread with the step named (E6)
    repo = _github_repo(tmp_path)
    expected = {
        "gh-unrunnable": "gh-unrunnable", "gh-failed": "gh-failed",
        "gh-failed-page-two": "gh-failed", "json-object": "json", "json-garbage": "json",
        "page-cap": "page-cap",
    }.get(case, "row-shape")
    if case == "gh-unrunnable":
        asked = _replace_pages(monkeypatch, lambda page: None)
    elif case == "gh-failed":
        asked = _replace_pages(monkeypatch, lambda page: _answer([], code=1))
    elif case == "gh-failed-page-two":
        asked = _replace_pages(
            monkeypatch, lambda page: _full_page(1) if page == 1 else _answer([], code=1),
        )
    elif case == "json-object":
        asked = _replace_pages(monkeypatch, lambda page: _answer({"message": "nope"}))
    elif case == "json-garbage":
        asked = _replace_pages(
            monkeypatch,
            lambda page: types.SimpleNamespace(returncode=0, stdout="<html>", stderr=""),
        )
    elif case == "page-cap":
        asked = _replace_pages(monkeypatch, _full_page)
    else:
        row = _BAD_ROWS[case[len("row-"):]]
        asked = _replace_pages(monkeypatch, lambda page: _answer([_pull(1), row]))
    reason, detail = _unread(repo)
    assert reason == UNREAD
    assert detail == {"failedRead": expected, "remedy": L._CONTINUES_PR_REMEDY_UNREAD}
    if case == "page-cap":
        assert asked == list(range(1, 11))
    if case == "gh-failed-page-two":
        assert asked == [1, 2]


def test_a_git_that_cannot_run_leaves_the_origin_unread(tmp_path, monkeypatch):
    # axis: an origin read git could not run refuses unread with failedRead origin (E6)
    repo = _github_repo(tmp_path)
    calls = _replace_read(monkeypatch, [])
    monkeypatch.setattr(L, "_git_scrubbed", lambda *args, **kwargs: None)
    assert L._origin_github_repo(repo, _env()) == ("unread", None)
    reason, detail = _unread(repo)
    assert reason == UNREAD
    assert detail == {"failedRead": "origin", "remedy": L._CONTINUES_PR_REMEDY_UNREAD}
    assert calls == []


def _stub_origin_read(monkeypatch, returncode):
    """Make `git remote get-url origin` answer `returncode` with no output; every other git call is real."""
    real = L._git_scrubbed

    def stub(repo_root, *args, **kwargs):
        if args[:3] == ("remote", "get-url", "origin"):
            return types.SimpleNamespace(returncode=returncode, stdout="", stderr="")
        return real(repo_root, *args, **kwargs)

    monkeypatch.setattr(L, "_git_scrubbed", stub)


def test_an_origin_read_that_fails_other_than_no_such_remote_refuses_unread(tmp_path, monkeypatch):
    # axis: a git remote get-url origin that exits other than 2 (a missing directory exits 128) refuses unread with failedRead origin (V894-3)
    repo = _github_repo(tmp_path)
    calls = _replace_read(monkeypatch, [])
    _stub_origin_read(monkeypatch, 128)
    assert L._origin_github_repo(repo, _env()) == ("unread", None)
    reason, detail = _unread(repo)
    assert reason == UNREAD
    assert detail["failedRead"] == "origin"
    assert detail == {"failedRead": "origin", "remedy": L._CONTINUES_PR_REMEDY_UNREAD}
    assert calls == []


def test_a_no_such_remote_exit_skips_with_no_read(tmp_path, monkeypatch):
    # axis: git's exit 2 (No such remote 'origin') alone is a skip, so a repository with no origin is not refused (V894-3)
    repo = _github_repo(tmp_path)
    calls = _replace_read(monkeypatch, [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}])
    _stub_origin_read(monkeypatch, 2)
    assert L._origin_github_repo(repo, _env()) == ("skip", None)
    assert L._continues_pr_refusal(
        repo, {"surfaces": ["origin/" + BRANCH], "baseCommit": "a" * 40}, _env(),
    ) is None
    assert calls == []


@pytest.mark.parametrize("url", [
    "https://github.com/o", "https://github.com/", "https://github.com", "https://github.com/o/r/x",
    "git@github.com:o", "git@github.com:o/r/x", "https://github.com/o/r r", "https://github.com/o/..",
    "ssh://git@github.com:o/r.git", "https://github.com//",
])
def test_a_github_origin_without_a_readable_owner_and_repo_refuses_unread(
    tmp_path, monkeypatch, url,
):
    # axis: a github.com origin that is not exactly owner/repo refuses unread, never skips (E7)
    repo = _init_repo(tmp_path / "repo")
    _set_origin(repo, url)
    calls = _replace_read(monkeypatch, [])
    assert L._origin_github_repo(repo, _env()) == ("unread", None)
    reason, detail = _unread(repo)
    assert reason == UNREAD
    assert detail["failedRead"] == "origin"
    assert calls == []


def test_an_unread_origin_refuses_a_launch_before_spend(tmp_path, monkeypatch):
    # axis: the unread refusal lands at the call site before any spawn (E9)
    _replace_pages(monkeypatch, lambda page: _answer([], code=1))
    repo = _github_repo(tmp_path)
    result, spawned = _local_launch(
        repo, tmp_path, _valid_premise(repo, surfaces=["origin/" + BRANCH]),
    )
    assert result["ok"] is False
    assert result["reason"] == UNREAD
    assert result["failedRead"] == "gh-failed"
    assert result["remedy"] == L._CONTINUES_PR_REMEDY_UNREAD
    assert spawned == []


def test_the_open_pull_read_pins_github_com_whatever_gh_host_says(monkeypatch):
    # axis: the real page read names --hostname github.com even when GH_HOST points elsewhere (E8)
    seen = []

    def recorder(argv, **kwargs):
        seen.append((argv, kwargs))
        return types.SimpleNamespace(returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr(
        L, "subprocess",
        types.SimpleNamespace(run=recorder, TimeoutExpired=subprocess.TimeoutExpired),
    )
    env = {"GH_HOST": "example.invalid", "PATH": os.environ.get("PATH", "")}
    got = L._gh_open_pulls_page("o", "r", 3, env, 5)
    assert got.returncode == 0
    argv, kwargs = seen[0]
    assert argv[:4] == ["gh", "api", "--hostname", "github.com"]
    assert argv[4] == "repos/o/r/pulls?state=open&per_page=100&page=3"
    assert kwargs["timeout"] == 5


def test_the_open_pull_read_pages_until_a_short_page(tmp_path, monkeypatch):
    # axis: a full page asks the next one and a short page ends the read
    asked = _replace_pages(
        monkeypatch,
        lambda page: _full_page(1) if page == 1 else _answer([_pull(NUMBER, BRANCH)]),
    )
    rows, failed = L._open_pulls("unused", "o", "r", _env())
    assert failed is None
    assert asked == [1, 2]
    assert len(rows) == 101
    assert rows[-1] == {"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}


# --- healthy siblings ---------------------------------------------------------------------------


def test_a_premise_with_the_pair_naming_the_open_branch_launches(tmp_path, monkeypatch):
    # axis: the adoption pair exempts a leg that names the branch it continues (E10)
    repo = _github_repo(tmp_path)
    base = _head_sha(repo)
    head = _commit_on(repo, base)
    calls = _replace_read(monkeypatch, [{"number": NUMBER, "branch": BRANCH, "head": head}])
    premise = _valid_premise(
        repo, baseCommit=base, surfaces=["origin/" + BRANCH],
        adoptsBranch=BRANCH, adoptsHead=head,
    )
    result, spawned = _local_launch(repo, tmp_path, premise)
    assert result["ok"] is True, result
    assert len(spawned) == 1
    assert calls == []


def test_a_fresh_build_naming_no_existing_branch_launches(tmp_path, monkeypatch):
    # axis: a launch whose surfaces name no open branch is not refused though pull requests are open
    calls = _replace_read(monkeypatch, [
        {"number": NUMBER, "branch": BRANCH, "head": PR_HEAD},
        {"number": 9, "branch": "feature/else", "head": "c" * 40},
    ])
    repo = _github_repo(tmp_path)
    result, spawned = _local_launch(repo, tmp_path, _valid_premise(repo))
    assert result["ok"] is True, result
    assert len(spawned) == 1
    assert calls == [("o", "r")]


def test_a_bare_path_surface_never_names_a_pull_request(tmp_path, monkeypatch):
    # axis: a path spelled like an open branch (docs) does not name it
    calls = _replace_read(monkeypatch, [{"number": 12, "branch": "docs", "head": PR_HEAD}])
    repo = _github_repo(tmp_path)
    result, spawned = _local_launch(repo, tmp_path, _valid_premise(repo, surfaces=["docs"]))
    assert result["ok"] is True, result
    assert len(spawned) == 1
    assert calls == [("o", "r")]
    pulls = [{"number": 12, "branch": "docs", "head": PR_HEAD}]
    assert L._named_open_pulls(["docs", "lib/launcher.py", "docs/guide.md"], pulls) == []


@pytest.mark.parametrize("more", [{}, {"adopts": 4242}])
def test_a_detective_charter_naming_an_open_branch_is_not_refused(tmp_path, monkeypatch, more):
    # axis: a detective never pushes, so it is exempt on both paths (E11)
    calls = _replace_read(monkeypatch, [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}])
    repo = _github_repo(tmp_path)
    stamped = {"charter": "detective", "surfaces": ["origin/" + BRANCH], **more}
    assert L._continues_pr_refusal(repo, stamped, _env()) is None
    assert calls == []
    workhorse = dict(stamped, charter="workhorse")
    assert L._continues_pr_refusal(repo, workhorse, _env())[0] == WITHOUT


def test_the_pair_is_exempt_only_when_both_keys_are_present(tmp_path, monkeypatch):
    # axis: the pair exempts both paths only whole; either key alone does not (E10)
    pair = {"adoptsBranch": BRANCH, "adoptsHead": PR_HEAD}
    calls = _replace_read(monkeypatch, [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}])
    repo = _github_repo(tmp_path)
    surfaces = ["origin/" + BRANCH]
    assert L._continues_pr_refusal(repo, {"surfaces": surfaces, **pair}, _env()) is None
    assert L._continues_pr_refusal(repo, {"surfaces": surfaces, "adopts": 3, **pair}, _env()) is None
    assert calls == []
    for key in pair:
        half = {key: pair[key]}
        assert L._continues_pr_refusal(repo, {"surfaces": surfaces, **half}, _env())[0] == WITHOUT
        got = L._continues_pr_refusal(repo, {"surfaces": ["lib"], "adopts": 3, **half}, _env())
        assert got[0] == WITHOUT


@pytest.mark.parametrize("url", [
    "git@gitlab.example:o/r.git", "https://gitlab.example/o/r.git", "ssh://git@bitbucket.example/o/r",
    "LOCAL", "file:///srv/git/o/r.git", None,
])
def test_a_non_github_or_local_origin_skips_with_no_read(tmp_path, monkeypatch, url):
    # axis: an origin that is not on github.com, a local path or file URL, or no origin skips (E12)
    calls = _replace_read(monkeypatch, [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}])
    repo = _init_repo(tmp_path / "repo")
    if url == "LOCAL":
        url = str(tmp_path / "remote.git")
    if url:
        _set_origin(repo, url)
    assert L._origin_github_repo(repo, _env()) == ("skip", None)
    stamped = {"surfaces": ["origin/" + BRANCH], "baseCommit": "a" * 40}
    assert L._continues_pr_refusal(repo, stamped, _env()) is None
    assert calls == []


@pytest.mark.parametrize("url", [
    "ssh://git@github.com:22/o/r.git", "git@github.com:o/r.git", "https://github.com/o/r",
    "https://GitHub.com/o/r.git/", "https://x@github.com/o/r.git", "ssh://git@GITHUB.COM/o/r.git",
    "git://github.com/o/r.git",
])
def test_a_github_origin_parses_to_its_owner_and_repo(tmp_path, url):
    # axis: every common github.com spelling parses to the same owner and repo (E7)
    repo = _init_repo(tmp_path / "repo")
    _set_origin(repo, url)
    assert L._origin_github_repo(repo, _env()) == ("github", ("o", "r"))


@pytest.mark.parametrize("url", [
    "https://www.github.com/o/r.git", "git@ssh.github.com:o/r.git",
    "ssh://git@ssh.github.com:443/o/r.git",
])
def test_a_www_or_ssh_github_origin_is_read_like_github_com(tmp_path, url):
    # axis: an origin on www.github.com or ssh.github.com is a GitHub origin and parses to its owner and repo (V894-2)
    repo = _init_repo(tmp_path / "repo")
    _set_origin(repo, url)
    assert L._origin_github_repo(repo, _env()) == ("github", ("o", "r"))


def test_an_ssh_host_alias_origin_stays_a_skip(tmp_path):
    # axis: an SSH host alias (git@github-work:o/r.git) cannot be decided without ssh config and stays a skip (V894-2)
    repo = _init_repo(tmp_path / "repo")
    _set_origin(repo, "git@github-work:o/r.git")
    assert L._origin_github_repo(repo, _env()) == ("skip", None)


@pytest.mark.parametrize("marker", ["remotes/origin/", "refs/remotes/origin/", "refs/heads/"])
def test_a_git_ref_spelling_of_the_branch_names_the_pull_request(marker):
    # axis: remotes/origin/<branch>, refs/remotes/origin/<branch> and refs/heads/<branch> name the pull request like origin/<branch> (V894-1)
    pulls = [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}]
    surface = marker + BRANCH
    assert L._named_open_pulls([surface], pulls) == [{**pulls[0], "matchedIn": surface}]


@pytest.mark.parametrize("surface", ["refs/heads/other/branch-x", "remotes/origin/" + BRANCH + "-two"])
def test_a_git_ref_spelling_of_another_branch_names_nothing(surface):
    # axis: a ref spelling of a different or longer branch name names no open pull request (V894-1)
    pulls = [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}]
    assert L._named_open_pulls([surface], pulls) == []


def test_the_layer_below_of_a_stack_layer_is_not_a_continued_branch(tmp_path, monkeypatch):
    # axis: an open pull request at the base of a layer above the bottom is exempt (E13)
    below = "a" * 40
    calls = _replace_read(monkeypatch, [{"number": 1352, "branch": "layer/one", "head": below}])
    repo = _github_repo(tmp_path)
    stamped = {
        "surfaces": ["origin/layer/one"], "baseCommit": below, "stack": 7, "layerPosition": 2,
    }
    assert L._continues_pr_refusal(repo, stamped, _env()) is None
    assert calls == [("o", "r")]
    # the exemption is the layer below's head at a layer above the bottom, and nothing wider
    for wider in (
        dict(stamped, layerPosition=1),
        dict(stamped, layerPosition=True),
        dict(stamped, baseCommit="d" * 40),
    ):
        assert L._continues_pr_refusal(repo, wider, _env())[0] == WITHOUT


def test_a_fork_row_with_a_matching_branch_name_is_skipped(tmp_path, monkeypatch):
    # axis: a pull request headed in a fork or a deleted fork is not this repository's branch (E14)
    repo = _github_repo(tmp_path)
    fork = _pull(1, BRANCH, full_name="someone/r")
    fork["head"]["repo"]["id"] = 2
    fork["base"] = {"repo": {"id": 1, "full_name": "o/r"}}
    rows = [
        fork,
        {"number": 2, "head": {"ref": BRANCH, "sha": PR_HEAD, "repo": None}},
        {"number": 3, "head": {"ref": BRANCH, "sha": PR_HEAD}},
    ]
    _replace_pages(monkeypatch, lambda page: _answer(rows))
    assert L._open_pulls(repo, "o", "r", _env()) == ([], None)
    stamped = {"surfaces": ["origin/" + BRANCH], "baseCommit": "a" * 40}
    assert L._continues_pr_refusal(repo, stamped, _env()) is None
    rows.append(_pull(4, BRANCH, full_name="O/R"))
    got = L._open_pulls(repo, "o", "r", _env())
    assert got == ([{"number": 4, "branch": BRANCH, "head": PR_HEAD}], None)
    assert L._continues_pr_refusal(repo, stamped, _env())[0] == WITHOUT


def test_a_renamed_repository_keeps_its_own_pull_requests_by_repository_id(tmp_path, monkeypatch):
    # axis: the head and base repository ids decide same-repository, so an origin still naming the old slug keeps its pull requests
    repo = _github_repo(tmp_path)
    row = _pull(5, BRANCH, full_name="o/renamed")
    row["head"]["repo"]["id"] = 1
    row["base"] = {"repo": {"id": 1, "full_name": "o/renamed"}}
    _replace_pages(monkeypatch, lambda page: _answer([row]))
    assert L._open_pulls(repo, "o", "r", _env()) == (
        [{"number": 5, "branch": BRANCH, "head": PR_HEAD}], None,
    )
    stamped = {"surfaces": ["origin/" + BRANCH], "baseCommit": "a" * 40}
    assert L._continues_pr_refusal(repo, stamped, _env())[0] == WITHOUT


def test_a_row_naming_another_repository_with_no_ids_leaves_the_list_unread(tmp_path, monkeypatch):
    # axis: with no repository ids a head repository other than the origin's cannot be told from a rename, so the read fails closed
    repo = _github_repo(tmp_path)
    _replace_pages(monkeypatch, lambda page: _answer([_pull(6, BRANCH, full_name="o/renamed")]))
    assert L._open_pulls(repo, "o", "r", _env()) == ([], "row-shape")
    stamped = {"surfaces": ["origin/" + BRANCH], "baseCommit": "a" * 40}
    reason, detail = L._continues_pr_refusal(repo, stamped, _env())
    assert reason == UNREAD and detail["failedRead"] == "row-shape"


@pytest.mark.parametrize("surface", [
    "origin/build/2434-span-tie: finish review fixes",
    "branch build/2434-span-tie: finish fixes",
    "branch:build/2434-span-tie, then review",
    "continue on branch build/2434-span-tie.",
    "(origin/build/2434-span-tie)",
])
def test_prose_punctuation_after_the_branch_does_not_hide_it(surface):
    # axis: a colon, comma, closing period or bracket after the branch name still names the pull request
    pulls = [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}]
    assert L._named_open_pulls([surface], pulls) == [{**pulls[0], "matchedIn": surface}]


@pytest.mark.parametrize("surface", [
    "origin/build/2434-span-tie-two",
    "branch build/2434-span-tie/sub",
    "origin/build/2434-span-tie.bak and more",
    "build/2434-span-tie",
])
def test_a_longer_name_or_a_bare_path_does_not_name_the_branch(surface):
    # axis: the branch is matched whole, so a longer name sharing its prefix, or a bare path, is not it
    pulls = [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}]
    assert L._named_open_pulls([surface], pulls) == []


@pytest.mark.parametrize("surface", [
    "(origin/build/2434-span-tie.)",
    "**origin/build/2434-span-tie**",
    "origin/closed,origin/build/2434-span-tie",
    "see `branch:build/2434-span-tie`.",
    "*branch* build/2434-span-tie;",
])
def test_markup_and_separators_around_the_branch_do_not_hide_it(surface):
    # axis: any neighbour that cannot continue a branch-like name (emphasis, a comma, a period before a bracket) bounds the match
    pulls = [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}]
    assert L._named_open_pulls([surface], pulls) == [{**pulls[0], "matchedIn": surface}]


@pytest.mark.parametrize("surface", [
    "xorigin/build/2434-span-tie",
    "origin/build/2434-span-tie+next",
    "branch build/2434-span-tie@2",
])
def test_a_name_character_beside_the_branch_makes_it_another_name(surface):
    # axis: a neighbouring name character means a longer branch-like name, not this branch
    pulls = [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}]
    assert L._named_open_pulls([surface], pulls) == []


@pytest.mark.parametrize("surface", [
    "origin/build/2434-span-tieé",
    "origin/build/2434-span-tie#2",
    "branch build/2434-span-tie%next",
    "branch:build/2434-span-tie&more",
])
def test_a_git_valid_suffix_beside_the_branch_is_another_branch(surface):
    # axis: only a delimiter git forbids in a name, or a prose mark, bounds the match; any other suffix (non-ASCII, # or %) is a longer branch
    pulls = [{"number": NUMBER, "branch": BRANCH, "head": PR_HEAD}]
    assert L._named_open_pulls([surface], pulls) == []


@pytest.mark.parametrize("branch,remedy", [
    ("feature/fix+followup", "_CONTINUES_PR_REMEDY_RENAME"),
    ("feature/part@2", "_CONTINUES_PR_REMEDY_RENAME"),
    (BRANCH, "_CONTINUES_PR_REMEDY_WITHOUT_ADOPTION"),
])
def test_the_remedy_names_a_rename_when_the_pair_cannot_carry_the_branch(tmp_path, monkeypatch, branch, remedy):
    # axis: a named branch valid_adopts_branch refuses gets the rename remedy, never one telling the advisor to set an adoptsBranch the validator rejects
    repo = _github_repo(tmp_path)
    _replace_pages(monkeypatch, lambda page: _answer([_pull(9, branch)]))
    stamped = {"surfaces": ["origin/" + branch], "baseCommit": "a" * 40}
    reason, detail = L._continues_pr_refusal(repo, stamped, _env())
    assert reason == WITHOUT
    assert detail["remedy"] == getattr(L, remedy)
    assert L.valid_adopts_branch(branch) is (remedy == "_CONTINUES_PR_REMEDY_WITHOUT_ADOPTION")


def test_the_word_branch_inside_the_matched_name_does_not_name_it():
    # axis: the branch keyword is read outside the matched name's span, so docs/branch alone is a bare path
    pulls = [{"number": NUMBER, "branch": "docs/branch", "head": PR_HEAD}]
    assert L._named_open_pulls(["docs/branch"], pulls) == []
    assert L._named_open_pulls(["the branch docs/branch"], pulls) == [{**pulls[0], "matchedIn": "the branch docs/branch"}]


@pytest.mark.parametrize("branch", ["_followup", "a/" + "b" * 199, "feature/x.lock"])
def test_every_name_the_validator_refuses_gets_the_rename_remedy(tmp_path, monkeypatch, branch):
    # axis: the rename remedy follows valid_adopts_branch itself, so a leading underscore, an over-long name or a .lock ending gets it too
    assert L.valid_adopts_branch(branch) is False
    repo = _github_repo(tmp_path)
    _replace_pages(monkeypatch, lambda page: _answer([_pull(9, branch)]))
    stamped = {"surfaces": ["origin/" + branch], "baseCommit": "a" * 40}
    assert L._continues_pr_refusal(repo, stamped, _env())[1]["remedy"] == L._CONTINUES_PR_REMEDY_RENAME


def test_the_rename_remedy_recovers_the_launch(tmp_path, monkeypatch):
    # axis: following the rename remedy (an adoptable branch carried in the pair) clears this check, and the old name refuses no more once its pull request is gone
    repo = _github_repo(tmp_path)
    renamed = "feature/fix-followup"
    assert L.valid_adopts_branch(renamed)
    _replace_pages(monkeypatch, lambda page: _answer([_pull(10, renamed)]))
    stamped = {
        "surfaces": ["origin/" + renamed], "baseCommit": "a" * 40,
        "adoptsBranch": renamed, "adoptsHead": PR_HEAD,
    }
    assert L.adopts_premise_reason(stamped) is None
    assert L._continues_pr_refusal(repo, stamped, _env()) is None


def test_a_stack_adoption_recovers_only_through_a_replacement_pull_request(tmp_path, monkeypatch):
    # axis: the remedies' route works end to end through the stack gate — the old unadoptable name cannot be carried in the pair, while a replacement pull request on an adoptable branch at the same position launches
    from test_launcher import _adoption_members, _launch_adoption

    def members(name, number):
        def build(head):
            rows = _adoption_members(head, occupant_number=number, occupant_head=head)
            rows[1]["headRefName"] = name
            return rows
        return build

    _repo, old = _launch_adoption(
        tmp_path / "old", monkeypatch, members("feature/fix+followup", 4242),
        adopts_the_base_head=True, adopts=4242, adoptsBranch="feature/fix+followup",
    )
    assert old["ok"] is False and old["reason"] == "premise-adopts-branch-invalid"
    _repo, new = _launch_adoption(
        tmp_path / "new", monkeypatch, members("feature/fix-followup", 4243),
        adopts_the_base_head=True, adopts=4243, adoptsBranch="feature/fix-followup",
    )
    assert new["ok"] is True, new.get("reason")


@pytest.mark.parametrize("remedy", ["_CONTINUES_PR_REMEDY_ADOPTS", "_CONTINUES_PR_REMEDY_RENAME"])
def test_the_unadoptable_branch_remedies_never_ask_to_move_a_pull_requests_head(remedy):
    # axis: GitHub cannot change a pull request's head branch, so the remedy routes through a replacement pull request and states the validator's rule
    text = getattr(L, remedy)
    assert "in place of" in text and "cannot be changed" in text
    assert "point the pull request" not in text and "retarget" not in text
    assert L._ADOPTABLE_BRANCH_RULE in text


def test_a_read_past_the_launch_deadline_refuses_unread_before_any_page(tmp_path, monkeypatch):
    # axis: the open-pull read honours the launch deadline: a spent deadline asks no page and refuses unread with failedRead deadline
    repo = _github_repo(tmp_path)
    asked = []
    _replace_pages(monkeypatch, lambda page: asked.append(page) or _answer([]))
    assert L._open_pulls(repo, "o", "r", _env(), deadline=L.time.monotonic() - 1) == ([], "deadline")
    assert asked == []
    stamped = {"surfaces": ["origin/" + BRANCH], "baseCommit": "a" * 40}
    reason, detail = L._continues_pr_refusal(repo, stamped, _env(), deadline=L.time.monotonic() - 1)
    assert reason == UNREAD and detail["failedRead"] == "deadline"


def test_each_page_timeout_is_clipped_to_the_launch_deadline(tmp_path, monkeypatch):
    # axis: a page asked near the deadline gets only the time that is left, never the full per-call timeout
    timeouts = []

    def page(owner, repo, number, env, timeout):
        timeouts.append(timeout)
        return _answer([])

    monkeypatch.setattr(L, "_gh_open_pulls_page", page)
    assert L._open_pulls(str(tmp_path), "o", "r", _env(), deadline=L.time.monotonic() + 5) == ([], None)
    assert len(timeouts) == 1 and 0 < timeouts[0] <= 5
    assert L._open_pulls(str(tmp_path), "o", "r", _env()) == ([], None)
    assert timeouts[1] == L._WORKTREE_GIT_TIMEOUT


@pytest.mark.parametrize("url", ["file://github.com/o/r.git", "FILE://github.com/o/r.git", "file:///srv/github.com/o/r.git"])
def test_a_file_url_naming_github_is_a_local_origin(url):
    # axis: a file:// transport is local whatever host its authority names, so it is skipped, never read as GitHub
    assert L._remote_host_and_path(url) is None


def test_an_empty_branch_on_a_row_leaves_the_list_unread(tmp_path, monkeypatch):
    # axis: a row whose head.ref is empty or blank cannot be matched, so the read fails closed as row-shape
    repo = _github_repo(tmp_path)
    for ref in ("", "   "):
        _replace_pages(monkeypatch, lambda page, ref=ref: _answer([_pull(3, ref)]))
        assert L._open_pulls(repo, "o", "r", _env()) == ([], "row-shape")


@pytest.mark.parametrize("answer", ["empty-last-page", "timed-out"])
def test_a_page_that_ends_past_the_deadline_fails_the_read_as_deadline(tmp_path, monkeypatch, answer):
    # axis: the deadline is read again after each page, so a last page that completes, or a call that times out, past it refuses as deadline, never as a clean read or gh-unrunnable
    clock = [1000.0]
    monkeypatch.setattr(L.time, "monotonic", lambda: clock[0])

    def page(owner, repo, number, env, timeout):
        clock[0] += timeout + 1
        return None if answer == "timed-out" else _answer([])

    monkeypatch.setattr(L, "_gh_open_pulls_page", page)
    assert L._open_pulls(str(tmp_path), "o", "r", _env(), deadline=1005.0) == ([], "deadline")


def test_the_launch_deadline_reaches_the_open_pull_read(tmp_path, monkeypatch):
    # axis: launch_build hands its own deadline to the continued-PR check, so the read is bounded by the launch budget
    seen = []

    def spy(repo_root, stamped, env, deadline=None):
        seen.append(deadline)
        return UNREAD, {"failedRead": "spy", "remedy": "stop here"}

    monkeypatch.setattr(L, "_continues_pr_refusal", spy)
    repo = _init_repo(tmp_path / "repo")
    result = L.launch_build(
        repo, 656, _valid_premise(repo), _all_checks(), str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"), settle_seconds=0.1,
    )
    assert result["reason"] == UNREAD
    assert len(seen) == 1 and isinstance(seen[0], float) and seen[0] > L.time.monotonic()


def test_a_read_whose_decoding_crosses_the_deadline_fails_as_deadline(tmp_path, monkeypatch):
    # axis: the deadline is read again after a page's rows are decoded, so a complete-looking list that finished past it refuses as deadline
    clock = [1000.0]
    monkeypatch.setattr(L.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(L, "_gh_open_pulls_page", lambda *a, **k: _answer([_pull(3, BRANCH)]))
    real_loads = L.json.loads

    def slow_loads(text, *a, **k):
        clock[0] += 10
        return real_loads(text, *a, **k)

    monkeypatch.setattr(L.json, "loads", slow_loads)
    assert L._open_pulls(str(tmp_path), "o", "r", _env(), deadline=1005.0) == ([], "deadline")
    clock[0] = 1000.0
    assert L._open_pulls(str(tmp_path), "o", "r", _env(), deadline=1050.0)[1] is None
