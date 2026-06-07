import json
import os
import subprocess
import sys

import pytest

import review_store as rs


@pytest.mark.parametrize("url,expected", [
    ("git@github.com:org/repo.git", "github.com/org/repo"),
    ("https://github.com/org/repo.git", "github.com/org/repo"),
    ("https://user@github.com/org/repo/", "github.com/org/repo"),
    ("ssh://git@github.com:22/org/repo.git", "github.com/org/repo"),
    ("https://GitHub.com/Org/Repo.git", "github.com/Org/Repo"),
    ("", None),
    (None, None),
])
def test_normalize_remote(url, expected):
    assert rs.normalize_remote(url) == expected


def test_short_hash_is_stable_16_hex():
    h = rs.short_hash("github.com/org/repo")
    assert h == rs.short_hash("github.com/org/repo")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)
    assert rs.short_hash("a") != rs.short_hash("b")
