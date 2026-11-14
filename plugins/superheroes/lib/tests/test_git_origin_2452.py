"""One git-origin classifier (issue 2452).

``git_origin`` is the only place that decides whether a git origin URL is a GitHub repository, what its
``owner/name`` slug is, and whether two slugs name the same repository. Every launcher, relay, recovery
and store site goes through it, so a URL shape reads one way everywhere. Nothing here touches the
network: the repositories are throwaway, the origin is a URL string only, and every gh call is replaced.
"""
import json
import os
import subprocess
import types

import pytest

import cloud_recover
import cloud_relay as cr
import git_origin
import store_core as sc

from test_launcher import L, _init_repo

NOT_GITHUB = ("not-github", None)
UNREADABLE = ("github-unreadable", None)

# O1: a file:// transport is local whatever its authority names.
FILE_URLS = [
    "file://github.com/o/r.git",
    "FILE://www.github.com/o/r",
    "file:///srv/github.com/o/r.git",
]
# O2: the GitHub hosts and forms, with the slug each reads as.
GITHUB_URLS = [
    ("https://www.github.com/o/r.git", "o/r"),
    ("git@ssh.github.com:o/r.git", "o/r"),
    ("ssh://git@ssh.github.com:443/o/r.git", "o/r"),
    ("https://GitHub.com/O/R", "O/R"),
    ("git@github.com:o/r.git", "o/r"),
    ("ssh://git@github.com/o/r", "o/r"),
    ("https://github.com/o/r/", "o/r"),
]
# O3: a GitHub host with a path that is not exactly owner/name.
UNREADABLE_URLS = [
    "https://github.com/o",
    "https://github.com/o/r/extra",
    "https://github.com/../r",
    "https://github.com/o/..",
    "https://github.com/o r/x",
    "https://github.com",
]
# O4: an SSH host alias and other hosts (a disclosed boundary).
OTHER_URLS = [
    "git@github-work:o/r.git",
    "https://gitlab.com/o/r",
    "/srv/git/o/r.git",
    "",
    "   ",
]


def _env():
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _origin(tmp_path, url):
    """A throwaway repository whose origin is the URL string `url`."""
    repo = _init_repo(tmp_path / "repo")
    subprocess.run(["git", "-C", repo, "remote", "add", "origin", url], check=True, env=_env())
    return repo


def _done(code, out="", err=""):
    return subprocess.CompletedProcess([], code, stdout=out, stderr=err)


# ---- the classifier itself ----

@pytest.mark.parametrize("url", FILE_URLS)
def test_a_file_url_is_not_github_whatever_its_authority_names(url):
    # axis: a file:// URL is a local transport whatever its authority names, so it is never GitHub
    assert git_origin.is_file_url(url) is True
    assert git_origin.classify(url) == NOT_GITHUB
    assert git_origin.github_slug(url) is None


@pytest.mark.parametrize("url,slug", GITHUB_URLS)
def test_every_github_host_and_form_reads_as_its_slug(url, slug):
    # axis: github.com, www.github.com and ssh.github.com in every address form, in any case, read as github with the slug as written
    assert git_origin.is_file_url(url) is False
    assert git_origin.classify(url) == ("github", slug)
    assert git_origin.github_slug(url) == slug


def test_the_www_host_is_a_github_host():
    # axis: www.github.com is in the host set
    assert git_origin.classify("https://www.github.com/o/r") == ("github", "o/r")


def test_the_host_case_does_not_matter():
    # axis: the host is folded to lower case before the host set is asked
    assert git_origin.classify("https://GitHub.com/O/R") == ("github", "O/R")


@pytest.mark.parametrize("url", UNREADABLE_URLS)
def test_a_github_host_with_a_path_that_is_not_owner_and_name_is_unreadable(url):
    # axis: a GitHub host whose path is not exactly owner/name is github-unreadable, never a slug
    assert git_origin.classify(url) == UNREADABLE
    assert git_origin.github_slug(url) is None


@pytest.mark.parametrize("url", OTHER_URLS)
def test_an_alias_and_other_hosts_are_not_github(url):
    # axis: an SSH host alias and a host other than GitHub's are not GitHub (a disclosed boundary)
    assert git_origin.classify(url) == NOT_GITHUB
    assert git_origin.github_slug(url) is None


@pytest.mark.parametrize("value", [None, 5, b"https://github.com/o/r", ["https://github.com/o/r"]])
def test_a_value_that_is_not_a_string_is_not_github(value):
    # axis: only a string can name a repository
    assert git_origin.classify(value) == NOT_GITHUB
    assert git_origin.is_file_url(value) is False


@pytest.mark.parametrize("a,b,expected", [
    ("O/R", "o/r", True),
    ("o/r", "o/r", True),
    ("", "", False),
    (None, "o/r", False),
    ("o/r", None, False),
    ("o/r", "o/s", False),
    ("o", "", False),
])
def test_same_repository_compares_slugs_ignoring_case_and_refuses_empty(a, b, expected):
    # axis: slugs compare case-insensitively, and an empty or non-string name is no repository
    assert git_origin.same_repository(a, b) is expected


# ---- normalize_remote keeps its own parser (O7) ----

@pytest.mark.parametrize("url,expected", [
    ("github.com:o/r.git", None),
    ("https://github.com", None),
    ("https://github.com:abc/o/r", None),
    ("git@github-work:O/R.git", "github-work/O/R"),
    ("https://gitlab.com/o/r", "gitlab.com/o/r"),
    ("https://www.github.com/o/r.git", "www.github.com/o/r"),
    ("git@ssh.github.com:o/r.git", "ssh.github.com/o/r"),
    ("ssh://git@ssh.github.com:443/o/r.git", "ssh.github.com/o/r"),
    ("https://GitHub.com/O/R", "github.com/O/R"),
])
def test_normalize_remote_keeps_its_output_for_every_other_url(url, expected):
    # axis: the store and review-base key is unchanged for every URL that is not a file:// URL
    assert sc.normalize_remote(url) == expected


@pytest.mark.parametrize("url", FILE_URLS + ["file:///repo.git", "File://host/x"])
def test_normalize_remote_reads_a_file_url_as_no_key(url):
    # axis: a file:// URL is a local transport, so it has no host/path key
    assert sc.normalize_remote(url) is None


# ---- each rewired site ----

@pytest.mark.parametrize("url", FILE_URLS + OTHER_URLS[:3])
def test_origin_github_repo_skips_a_local_or_other_origin(tmp_path, url):
    # axis: a file:// URL, an alias and another host are skipped, not read
    repo = _origin(tmp_path, url)
    assert L._origin_github_repo(repo, _env()) == ("skip", None)


@pytest.mark.parametrize("url,slug", GITHUB_URLS)
def test_origin_github_repo_reads_every_github_form(tmp_path, url, slug):
    # axis: every GitHub host and form reads as (owner, name), the case kept as written
    repo = _origin(tmp_path, url)
    assert L._origin_github_repo(repo, _env()) == ("github", tuple(slug.split("/")))


@pytest.mark.parametrize("url", UNREADABLE_URLS[:5])
def test_origin_github_repo_leaves_a_malformed_github_path_unread(tmp_path, url):
    # axis: a GitHub host whose path is not exactly owner/name is unread, not skipped
    repo = _origin(tmp_path, url)
    assert L._origin_github_repo(repo, _env()) == ("unread", None)


def _lookup_recorder(monkeypatch, answer):
    seen = []

    def run(owner, repo, sha, env, timeout):
        seen.append((owner, repo, sha))
        return answer

    monkeypatch.setattr(L, "_gh_commit_lookup", run)
    return seen


SHA = "a" * 40


@pytest.mark.parametrize("url,slug", GITHUB_URLS)
def test_base_on_remote_asks_github_about_every_github_form(tmp_path, monkeypatch, url, slug):
    # axis: the base check reads the owner and repository from every GitHub host and form
    repo = _origin(tmp_path, url)
    seen = _lookup_recorder(monkeypatch, _done(0, SHA + "\n"))
    assert L._base_on_remote(repo, SHA, _env()) is True
    assert seen == [tuple(slug.split("/")) + (SHA,)]


@pytest.mark.parametrize("url", FILE_URLS + UNREADABLE_URLS[:5] + OTHER_URLS[:3])
def test_base_on_remote_does_not_ask_github_about_any_other_origin(tmp_path, monkeypatch, url):
    # axis: a file:// URL, an alias, another host or a malformed GitHub path is never asked of GitHub
    repo = _origin(tmp_path, url)
    seen = _lookup_recorder(monkeypatch, _done(0, SHA + "\n"))
    assert L._base_on_remote(repo, SHA, _env()) is None
    assert seen == []


@pytest.mark.parametrize("url,slug", GITHUB_URLS)
def test_adopted_branch_first_pr_asks_github_about_every_github_form(tmp_path, monkeypatch, url, slug):
    # axis: the first-pull-request read takes the owner and repository from every GitHub host and form
    repo = _origin(tmp_path, url)
    seen = []

    def pulls(owner, name, branch, env, timeout):
        seen.append((owner, name))
        return _done(0, "[]")

    monkeypatch.setattr(L, "_gh_branch_pulls", pulls)
    assert L._adopted_branch_first_pr(repo, "feature/x", _env()) is None
    assert seen == [tuple(slug.split("/"))]


@pytest.mark.parametrize("url", FILE_URLS)
def test_adopted_branch_first_pr_does_not_ask_about_a_file_origin(tmp_path, monkeypatch, url):
    # axis: a file:// origin is never asked of GitHub
    repo = _origin(tmp_path, url)
    seen = []
    monkeypatch.setattr(L, "_gh_branch_pulls", lambda *a: seen.append(a))
    assert L._adopted_branch_first_pr(repo, "feature/x", _env()) is None
    assert seen == []


def test_adopted_branch_first_pr_reads_a_differently_cased_head_repository_as_its_own(tmp_path, monkeypatch):
    # axis: the head repository is compared with the origin's slug ignoring case
    repo = _origin(tmp_path, "https://github.com/o/r.git")
    row = {"head": {"ref": "feature/x", "repo": {"full_name": "O/R"}}, "created_at": "2026-10-20T10:00:00Z"}
    monkeypatch.setattr(L, "_gh_branch_pulls", lambda *a: _done(0, json.dumps([row])))
    assert L._adopted_branch_first_pr(repo, "feature/x", _env()) is not None


@pytest.mark.parametrize("url,slug", GITHUB_URLS)
def test_issue_comments_reads_the_repository_of_every_github_form(tmp_path, monkeypatch, url, slug):
    # axis: the comments read takes the owner and repository from every GitHub host and form
    repo = _origin(tmp_path, url)
    seen = []

    def comments(name, number, since, env, run):
        seen.append((name, number))
        return []

    monkeypatch.setattr(cloud_recover, "_issue_comments", comments)
    assert L._issue_comments(repo, 7, _env()) == []
    assert seen == [(slug, 7)]


@pytest.mark.parametrize("url", FILE_URLS)
def test_issue_comments_does_not_read_a_file_origin(tmp_path, monkeypatch, url):
    # axis: a file:// origin has no GitHub issue to read
    repo = _origin(tmp_path, url)
    seen = []
    monkeypatch.setattr(cloud_recover, "_issue_comments", lambda *a: seen.append(a))
    assert L._issue_comments(repo, 7, _env()) is None
    assert seen == []


def test_issue_comments_passes_no_gh_host(tmp_path, monkeypatch):
    # axis: the comments read is on github.com whatever GH_HOST says, so GH_HOST is not passed on
    repo = _origin(tmp_path, "https://github.com/o/r.git")
    seen = []

    def comments(name, number, since, env, run):
        seen.append(dict(env))
        return []

    monkeypatch.setattr(cloud_recover, "_issue_comments", comments)
    env = _env()
    env["GH_HOST"] = "ghe.example.com"
    assert L._issue_comments(repo, 7, env) == []
    assert len(seen) == 1 and "GH_HOST" not in seen[0]


def _recorder(monkeypatch):
    argvs = []

    def run(argv, **kwargs):
        argvs.append(argv)
        return _done(0, "[]")

    monkeypatch.setattr(L.subprocess, "run", run)
    return argvs


def test_the_commit_lookup_is_pinned_to_github_com_whatever_gh_host_says(monkeypatch):
    # axis: the commits read is on github.com whatever GH_HOST says
    argvs = _recorder(monkeypatch)
    env = _env()
    env["GH_HOST"] = "ghe.example.com"
    L._gh_commit_lookup("o", "r", SHA, env, 5)
    assert argvs == [["gh", "api", "--hostname", "github.com", "repos/o/r/commits/" + SHA, "--jq", ".sha"]]


def test_the_branch_pulls_read_is_pinned_to_github_com_whatever_gh_host_says(monkeypatch):
    # axis: the branch pull-request read is on github.com whatever GH_HOST says
    argvs = _recorder(monkeypatch)
    env = _env()
    env["GH_HOST"] = "ghe.example.com"
    L._gh_branch_pulls("o", "r", "feat/x", env, 5)
    assert argvs == [[
        "gh", "api", "--hostname", "github.com",
        "repos/o/r/pulls?state=all&head=o:feat%2Fx&per_page=100",
    ]]


def _remote(url):
    def run(argv, **kwargs):
        return types.SimpleNamespace(returncode=0, stdout=url + "\n", stderr="")
    return run


@pytest.mark.parametrize("url,slug", GITHUB_URLS)
def test_lane_repo_reads_every_github_host_and_form(url, slug):
    # axis: the lane repository reads www.github.com, ssh.github.com and any-case hosts, not only github.com
    assert cr.lane_repo("/x", run=_remote(url)) == (slug, None)


@pytest.mark.parametrize("url", FILE_URLS + UNREADABLE_URLS + OTHER_URLS)
def test_lane_repo_is_unreadable_for_a_file_origin_a_malformed_path_and_other_hosts(url):
    # axis: a file:// URL, a malformed GitHub path, an alias and another host name no lane repository
    assert cr.lane_repo("/x", run=_remote(url)) == (None, "lane-repo-unreadable")


def _pull(full_name):
    return {"head": {"ref": "b", "repo": {"full_name": full_name}}}


def test_from_elsewhere_reads_a_differently_cased_same_repository_as_its_own():
    # axis: the head repository is compared with the lane's ignoring case
    assert cloud_recover._from_elsewhere(_pull("Acme/Widgets"), "acme/widgets") is False
    assert cloud_recover._from_elsewhere(_pull("acme/widgets"), "Acme/Widgets") is False


def test_from_elsewhere_keeps_a_fork_elsewhere():
    # axis: a head repository that is another repository is a fork
    assert cloud_recover._from_elsewhere(_pull("fork/widgets"), "acme/widgets") is True


def test_from_elsewhere_keeps_an_empty_name_elsewhere_and_a_missing_one_not():
    # axis: an empty full_name is no repository so it stays elsewhere; a head with no repository is not elsewhere
    assert cloud_recover._from_elsewhere(_pull(""), "acme/widgets") is True
    assert cloud_recover._from_elsewhere({"head": {"repo": None}}, "acme/widgets") is False
    assert cloud_recover._from_elsewhere({"head": {"repo": {"full_name": 5}}}, "acme/widgets") is False
