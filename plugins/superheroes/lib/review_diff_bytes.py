#!/usr/bin/env python3
"""Raw-byte producer for ``git diff <base>...HEAD`` — single home for the review-diff contract."""
import subprocess


def run_git_diff_three_dot_head(repo_root, base_sha, *, timeout):
    """Run ``git diff <base_sha>...HEAD`` at ``repo_root``; return the completed process.

    stdout is raw bytes (``text=False``). Callers decode to UTF-8, hash, or map errors."""
    return subprocess.run(
        ["git", "-C", repo_root, "diff", "%s...HEAD" % base_sha],
        capture_output=True,
        text=False,
        timeout=timeout,
    )
