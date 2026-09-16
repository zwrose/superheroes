"""C4 accepted-exposure dry-run acceptance for the security lens."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_PLUGIN = os.path.join(_LIB, "..")

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import lens_acceptance as LA


def _read_agent_prompt():
    path = os.path.join(_PLUGIN, "agents", "security-reviewer.md")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_accepted_exposure_fixture_dry_run_returns_no_finding():
    """axis: planted accepted-exposure fixture returns no finding from stub dry run (C4)."""
    profile, diff = LA.load_accepted_exposure_fixture()
    out = LA.dry_run_security_reviewer_stub(_read_agent_prompt(), profile, diff)
    assert out == {"ok": True, "findings": [], "investigated": ["diff.txt"]}


def test_accepted_exposure_stub_requires_prompt_rule():
    profile, diff = LA.load_accepted_exposure_fixture()
    out = LA.dry_run_security_reviewer_stub("review the diff", profile, diff)
    assert out["ok"] is False
    assert out["reason"] == "prompt-missing-rule"
