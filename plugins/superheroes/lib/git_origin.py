#!/usr/bin/env python3
"""The one reader of a git origin URL: is it a GitHub repository, and what is its ``owner/name``?

This module is the only place that decides whether an origin URL names a GitHub repository and what
its slug is, and the only place that compares two repository slugs. Every launcher, relay, recovery
and release-check site goes through it, so a URL shape is read one way everywhere (issue 2452).

Stdlib-only and free of plugin imports, so ``.github/scripts`` can load it by file path.
"""
import re

# The hosts whose origins are read like github.com.
GITHUB_HOSTS = frozenset({"github.com", "www.github.com", "ssh.github.com"})

_REPO_PART = re.compile(r"[A-Za-z0-9_.-]+")
_URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://(?P<rest>.*)$", re.DOTALL)

GITHUB = "github"
GITHUB_UNREADABLE = "github-unreadable"
NOT_GITHUB = "not-github"


def is_file_url(url):
    """True when ``url`` (stripped) starts with ``file://`` in any case: a local transport."""
    return isinstance(url, str) and url.strip()[:7].lower() == "file://"


def host_and_path(url):
    """The ``(host, path)`` of a git remote URL, or None for a form that is no host (a local path,
    ``file://``). ``path`` is everything after the host, ``""`` when the host has none."""
    # axis: a file:// URL is a local transport whatever its authority names (file://github.com/o/r is a path, not GitHub) — see bite-proof record i2452_git_origin
    if url[:7].lower() == "file://":
        return None
    matched = _URL_RE.match(url)
    if matched is not None:
        rest = matched.group("rest")
        slash = rest.find("/")
        authority = rest if slash < 0 else rest[:slash]
        tail = "" if slash < 0 else rest[slash + 1:]
        host = authority.rsplit("@", 1)[-1]
        if ":" in host:
            host, port = host.split(":", 1)
            if port.isdigit():
                return host, tail
            return host, ""
        return host, tail
    colon = url.find(":")
    slash = url.find("/")
    if colon < 0 or (0 <= slash < colon):
        return None
    return url[:colon].rsplit("@", 1)[-1], url[colon + 1:]


def classify(url):
    """``("github", "owner/name")``, ``("github-unreadable", None)`` or ``("not-github", None)``.

    not-github: not a string, empty, a local path or ``file://`` URL, or a host other than github.com,
    www.github.com or ssh.github.com (an SSH host alias included). github-unreadable: a GitHub host
    whose path is not exactly two parts of ``[A-Za-z0-9_.-]+``, neither made only of dots. The slug
    keeps its case as written."""
    if not isinstance(url, str):
        return (NOT_GITHUB, None)
    text = url.strip()
    # axis: an empty origin names no repository — see bite-proof record i2452_git_origin
    if not text:
        return (NOT_GITHUB, None)
    split = host_and_path(text)
    # axis: a local path or file URL has no host and so is not GitHub — see bite-proof record i2452_git_origin
    if split is None:
        return (NOT_GITHUB, None)
    host, path = split
    # axis: a host other than github.com, www.github.com or ssh.github.com is not GitHub, and the host's case does not matter — see bite-proof record i2452_git_origin
    if host.lower() not in GITHUB_HOSTS:
        return (NOT_GITHUB, None)
    if path.startswith("/"):
        path = path[1:]
    if path.endswith("/"):
        path = path[:-1]
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    # axis: a GitHub host whose path is not exactly owner/name is unreadable, not a repository — see bite-proof record i2452_git_origin
    if len(parts) != 2 or not all(_REPO_PART.fullmatch(part) and part.strip(".") for part in parts):
        return (GITHUB_UNREADABLE, None)
    return (GITHUB, "%s/%s" % (parts[0], parts[1]))


def github_slug(url):
    """The ``owner/name`` slug when ``classify`` says github, else None."""
    kind, slug = classify(url)
    return slug if kind == GITHUB else None


def same_repository(a, b):
    """True only when both are non-empty strings equal ignoring case (GitHub owner and repository
    names are ASCII and case-insensitive)."""
    # axis: an empty or non-string name is no repository, so two empties are not the same one — see bite-proof record i2452_git_origin
    if not (isinstance(a, str) and isinstance(b, str) and a and b):
        return False
    # axis: GitHub names are case-insensitive, so a differently cased slug is the same repository — see bite-proof record i2452_git_origin
    return a.lower() == b.lower()
