#!/usr/bin/env python3
"""Deterministic dry-run stubs for lens prompt acceptance fixtures (C4).

The security-reviewer accepted-exposure fixture plants a diff hunk that would otherwise
read as a missing-auth exposure; calibration declares it accepted. A stub dry-run honors
the prompt rule without invoking a model."""
from __future__ import annotations

import os
import re

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FIXTURES = os.path.join(_PLUGIN_ROOT, "eval", "fixtures")

ACCEPTED_EXPOSURE_FIXTURE = "accepted-exposure"

_ACCEPTED_EXPOSURE_DECL_RE = re.compile(
    r"Unauthenticated read of `GET /api/health`",
    re.IGNORECASE,
)


def fixture_dir(name: str) -> str:
    return os.path.join(_FIXTURES, name)


def load_accepted_exposure_fixture() -> tuple[str, str]:
    root = fixture_dir(ACCEPTED_EXPOSURE_FIXTURE)
    with open(os.path.join(root, "profile.md"), encoding="utf-8") as fh:
        profile = fh.read()
    with open(os.path.join(root, "diff.txt"), encoding="utf-8") as fh:
        diff = fh.read()
    return profile, diff


def dry_run_security_reviewer_stub(agent_prompt: str, profile_text: str, diff_text: str) -> dict:
    """Stub dry-run: a declared accepted exposure yields no finding."""
    if "accepted exposure is not a finding" not in agent_prompt:
        return {"ok": False, "reason": "prompt-missing-rule"}
    if not _ACCEPTED_EXPOSURE_DECL_RE.search(profile_text):
        return {"ok": False, "reason": "calibration-missing-declaration"}
    if "getHealth" not in diff_text:
        return {"ok": False, "reason": "fixture-missing-planted-hunk"}
    return {"ok": True, "findings": [], "investigated": ["diff.txt"]}
