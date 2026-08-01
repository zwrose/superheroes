"""CONVENTIONS §15 heartbeat contract drift guard.

Module constants in heartbeat.py are authoritative; prose copies in CONVENTIONS §15
and the workhorse/showrunner charters must stay pinned to them.
"""
import os
import re

import heartbeat as hb

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN = os.path.abspath(os.path.join(_HERE, "..", ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_PLUGIN, "..", ".."))


def _read_repo(rel):
    with open(os.path.join(_REPO_ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def _read_plugin(rel):
    with open(os.path.join(_PLUGIN, rel), encoding="utf-8") as fh:
        return fh.read()


def _conventions_section_15():
    text = _read_repo("CONVENTIONS.md")
    m = re.search(r"## 15\. Builder liveness heartbeat.*?(?=\n## 16\.|\Z)", text, re.DOTALL)
    assert m, "CONVENTIONS §15 not found (renumbered or moved?)"
    return m.group(0)


def _assert_tokens_present(text, label, tokens):
    missing = [tok for tok in tokens if tok not in text]
    assert not missing, "%s missing token(s): %r" % (label, missing)


def _launch_id_grammar_token():
    return "`%s`" % hb._LAUNCH_ID_RE.pattern


def test_conventions_section_15_matches_heartbeat_constants():
    section = _conventions_section_15()
    tokens = (
        sorted(hb.STATES)
        + sorted(hb.TERMINAL_STATES)
        + sorted(hb.SWEEP_CLASSES)
        + [hb.HEARTBEAT_ROOT_ENV, hb.LAUNCH_ID_ENV, _launch_id_grammar_token()]
    )
    _assert_tokens_present(section, "CONVENTIONS.md §15", tokens)


def test_workhorse_charter_matches_heartbeat_constants():
    text = _read_plugin("skills/workhorse/SKILL.md")
    tokens = [
        hb.LAUNCH_ID_ENV,
        "CONVENTIONS §15",
    ] + sorted(hb.TERMINAL_STATES)
    _assert_tokens_present(text, "skills/workhorse/SKILL.md", tokens)


def test_showrunner_charter_matches_heartbeat_constants():
    text = _read_plugin("skills/showrunner/SKILL.md")
    m = re.search(
        r"\*\*Scheduled heartbeat sweep.*?(?=\n\s*\*\*Wave-preflight)",
        text,
        re.DOTALL,
    )
    assert m, "showrunner duty-9 heartbeat sweep paragraph not found"
    duty = m.group(0)
    tokens = (
        sorted(cls for cls in hb.SWEEP_CLASSES if cls != "fresh")
        + ["staleAfterSeconds", "heartbeat.py sweep", "record-outcome"]
    )
    _assert_tokens_present(duty, "skills/showrunner/SKILL.md duty-9", tokens)
