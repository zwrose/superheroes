"""The release check reads the origin URL and the release PR's head repository through git_origin (issue 2452)."""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_M = os.path.join(_HERE, "..", "check_release_bump.py")
_spec = importlib.util.spec_from_file_location("check_release_bump", _M)
RB = importlib.util.module_from_spec(_spec)
sys.modules["check_release_bump"] = RB
_spec.loader.exec_module(RB)

_REF = "release-please--branches--main--components--superheroes"


@pytest.mark.parametrize("url", [
    "file://github.com/o/r.git",
    "FILE://www.github.com/o/r",
    "file:///srv/github.com/o/r.git",
    "git@github-work:o/r.git",
    "https://gitlab.com/o/r",
    "https://github.com/o",
    "https://github.com/o/r/extra",
    "https://github.com/../r",
    "",
])
def test_parse_remote_repo_refuses_a_local_other_or_malformed_origin(url):
    # axis: a file:// URL, another host and a malformed GitHub path name no repository
    assert RB._parse_remote_repo(url) is None


@pytest.mark.parametrize("url,slug", [
    ("https://www.github.com/o/r.git", "o/r"),
    ("git@ssh.github.com:o/r.git", "o/r"),
    ("ssh://git@ssh.github.com:443/o/r.git", "o/r"),
    ("https://GitHub.com/O/R", "O/R"),
    ("git@github.com:o/r.git\n", "o/r"),
    ("https://github.com/o/r/", "o/r"),
])
def test_parse_remote_repo_reads_every_github_host_and_form(url, slug):
    # axis: every GitHub host and form reads as its slug, in any case
    assert RB._parse_remote_repo(url) == slug


def _pull(full_name):
    return {
        "number": 7,
        "head": {"ref": _REF, "sha": "abc", "repo": {"full_name": full_name}},
        "base": {"ref": "main"},
    }


def _find(monkeypatch, full_name, repo="zwrose/superheroes"):
    monkeypatch.setattr(RB, "_run_gh", lambda args: [_pull(full_name)])
    return RB._find_release_pr(repo, "superheroes", retries=1)


def test_find_release_pr_finds_a_pr_whose_head_repository_differs_only_in_case(monkeypatch):
    # axis: the head repository is compared with the repo ignoring case, so GitHub's own spelling still finds the release PR
    assert _find(monkeypatch, "ZWrose/Superheroes") == {"number": 7, "head_ref": _REF, "head_sha": "abc"}


def test_find_release_pr_still_rejects_a_fork_pr(monkeypatch):
    # axis: a head repository that is another repository is a fork, not the release PR
    assert _find(monkeypatch, "attacker/fork") is None


def test_find_release_pr_does_not_match_an_empty_head_repository(monkeypatch):
    # axis: an empty head repository name is no repository, so it never matches
    assert _find(monkeypatch, "") is None
