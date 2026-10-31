#!/usr/bin/env python3
"""Raw-byte producer for ``git diff <base>...<head>`` — single home for the review-diff contract."""
import subprocess

# The one home of the review diff's shape: no user git setting (copies, context, prefixes, external diff, textconv, color) changes it.
REVIEW_DIFF_ARGS = ("--no-ext-diff", "--no-textconv", "--no-color", "-M", "-U3", "--src-prefix=a/", "--dst-prefix=b/")
REVIEW_NUMSTAT_ARGS = ("--no-ext-diff", "--no-textconv", "-M")


def _require_explicit_commit_sha(sha, label):
    if not isinstance(sha, str):
        raise ValueError("%s must be an explicit commit" % label)
    if len(sha) not in (40, 64):
        raise ValueError("%s must be an explicit commit" % label)
    for ch in sha:
        if ch not in "0123456789abcdefABCDEF":
            raise ValueError("%s must be an explicit commit" % label)


def run_git_diff_three_dot(repo_root, base_sha, head_sha, *, timeout):
    """Run ``git diff <base_sha>...<head_sha>`` at ``repo_root``; return the completed process.

    stdout is raw bytes (``text=False``). Callers decode to UTF-8, hash, or map errors."""
    _require_explicit_commit_sha(base_sha, "base_sha")
    _require_explicit_commit_sha(head_sha, "head_sha")
    return subprocess.run(
        ["git", "-C", repo_root, "diff", *REVIEW_DIFF_ARGS, "%s...%s" % (base_sha, head_sha)],
        capture_output=True,
        text=False,
        timeout=timeout,
    )
