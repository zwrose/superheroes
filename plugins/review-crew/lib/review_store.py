#!/usr/bin/env python3
"""Resolve where a project's review-crew profile/decisions live.

Two locations, checked in order: in-repo (./.claude/) then a global per-repo
store at ~/.claude/review-crew/ keyed by BOTH the normalized origin URL and the
git-common-dir path (per-key pointer files, self-healing). See
docs/superpowers/specs/2026-06-07-review-crew-profile-storage-design.md.

All git calls use argv arrays with a timeout — never shell=True.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

FILENAMES = {"profile": "review-profile.md", "decisions": "review-decisions.json"}


def normalize_remote(url):
    """Normalize a remote URL to host/path: lowercase host, drop scheme/userinfo/
    port, strip trailing .git and slashes. Return None for empty/None."""
    if not url:
        return None
    s = url.strip()
    if not s:
        return None
    # scp-like: git@host:org/repo.git
    m = re.match(r"^[^@/]+@([^:/]+):(.+)$", s)
    if m:
        host, path = m.group(1), m.group(2)
    else:
        # scheme://[user@]host[:port]/path
        m = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://(?:[^@/]+@)?([^:/]+)(?::\d+)?/(.+)$", s)
        if m:
            host, path = m.group(1), m.group(2)
        else:
            return None
    host = host.lower()
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    path = path.strip("/")
    return f"{host}/{path}"


def short_hash(s):
    """First 16 hex chars of sha256(s)."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
