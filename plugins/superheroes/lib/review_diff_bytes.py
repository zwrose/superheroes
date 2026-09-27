#!/usr/bin/env python3
"""Raw-byte producer for ``git diff <base>...<head>`` — single home for the review-diff contract."""
import subprocess


def _require_explicit_commit_sha(sha, label):
    if not isinstance(sha, str) or not sha.strip():
        raise ValueError("%s must be an explicit commit" % label)
    if sha.strip().upper() == "HEAD":
        raise ValueError("%s must be an explicit commit" % label)


def run_git_diff_three_dot(repo_root, base_sha, head_sha, *, timeout):
    """Run ``git diff <base_sha>...<head_sha>`` at ``repo_root``; return the completed process.

    stdout is raw bytes (``text=False``). Callers decode to UTF-8, hash, or map errors."""
    _require_explicit_commit_sha(base_sha, "base_sha")
    _require_explicit_commit_sha(head_sha, "head_sha")
    return subprocess.run(
        ["git", "-C", repo_root, "diff", "%s...%s" % (base_sha, head_sha)],
        capture_output=True,
        text=False,
        timeout=timeout,
    )
