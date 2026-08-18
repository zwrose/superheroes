"""Drift guard: owner-artifact refusal + policyApplied source vocabulary ↔ round_driver.py.

Copy-holder:
  - plugins/superheroes/skills/review-code/reference/round-driver.md
Authoritative home (module constants — never retyped as literals in this test):
  - round_driver.OWNER_ARTIFACT_*_REFUSAL
  - round_driver.POLICY_APPLIED_SOURCE_*
"""
import os
import re

import round_driver as RD

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_REF = os.path.join(_PLUGIN_ROOT, "skills", "review-code", "reference", "round-driver.md")

_REFUSAL_MARKER = "**Owner-artifact refusal causes**"
_SOURCE_MARKER = "**Policy-applied sources**"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _parse_fenced_text_block(text, after_marker):
    """Return stripped non-empty lines from the first ```text block after *after_marker*."""
    idx = text.index(after_marker)
    chunk = text[idx:]
    match = re.search(r"```text\n(.*?)```", chunk, re.DOTALL)
    if not match:
        raise RuntimeError("no ```text block found after marker %r" % after_marker)
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


def _owner_artifact_refusal_causes():
    return frozenset({
        RD.OWNER_ARTIFACT_TERMINAL_REFUSAL,
        RD.OWNER_ARTIFACT_UNREADABLE_REFUSAL,
        RD.OWNER_ARTIFACT_SHAPE_REFUSAL,
    })


def _policy_applied_sources():
    return frozenset({
        RD.POLICY_APPLIED_SOURCE_GATE_POLICY,
        RD.POLICY_APPLIED_SOURCE_OWNER_SUPPLIED,
    })


def test_owner_artifact_refusal_causes_match_docs():
    """round-driver.md owner-artifact refusal list ↔ OWNER_ARTIFACT_*_REFUSAL (both directions)."""
    text = _read(_REF)
    documented = set(_parse_fenced_text_block(text, _REFUSAL_MARKER))
    coded = set(_owner_artifact_refusal_causes())

    only_docs = documented - coded
    only_code = coded - documented
    assert not only_docs, (
        "round-driver.md lists owner-artifact refusals the driver cannot emit: %s"
        % sorted(only_docs))
    assert not only_code, (
        "driver emits owner-artifact refusals missing from round-driver.md: %s"
        % sorted(only_code))


def test_policy_applied_sources_match_docs():
    """round-driver.md policyApplied.source list ↔ POLICY_APPLIED_SOURCE_* (both directions)."""
    text = _read(_REF)
    documented = set(_parse_fenced_text_block(text, _SOURCE_MARKER))
    coded = set(_policy_applied_sources())

    only_docs = documented - coded
    only_code = coded - documented
    assert not only_docs, (
        "round-driver.md lists policyApplied sources the driver cannot emit: %s"
        % sorted(only_docs))
    assert not only_code, (
        "driver emits policyApplied sources missing from round-driver.md: %s"
        % sorted(only_code))
