"""Pin: the escalation rubric defers whose-call to the owner-vs-craft line and keeps only
the three disclosure modes."""
# Bites on: escalation-base.md pointing whose-call at the owner-vs-craft line and its three modes mapping to craft (veto) / owner calls, with no second sorting rule of its own.
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_RUBRIC = os.path.normpath(os.path.join(_HERE, "..", "..", "rubric", "escalation-base.md"))

_MIN_VERSION = 5

_SECOND_RULE_PHRASES = (
    "this file wins",
    "Reversibility × confidence",
    "owner-weighable",
    "Where does the ground truth live",
    "not eligible for autonomy",
    "lean PROCEED",
    "Probe before GATE",
)


def _text():
    with open(_RUBRIC, encoding="utf-8") as fh:
        return fh.read()


def _bullet(mode):
    """The bullet beginning ``- **MODE**`` up to the next line beginning ``- **`` or the
    first blank line, so the last bullet does not swallow the prose after it.

    Fails closed: a mode whose bullet is not found fails the test rather than passing
    vacuously on an empty string.
    """
    lines = _text().splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(f"- **{mode}**"):
            start = i
            break
    assert start is not None, f"no bullet beginning '- **{mode}**' in {_RUBRIC}"
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("- **") or not lines[j].strip():
            end = j
            break
    return "\n".join(lines[start:end])


def test_pointer_to_the_line():
    assert "owner-vs-craft-line.md#how-a-call-is-sorted" in _text()


def test_proceed_is_a_craft_call_for_veto():
    bullet = _bullet("PROCEED")
    assert "craft call" in bullet
    assert "veto" in bullet


def test_notify_is_a_craft_call_with_undo_path_and_expiry():
    bullet = _bullet("NOTIFY")
    for needle in ("craft call", "veto", "undo path", "expiry"):
        assert needle in bullet, f"NOTIFY bullet lacks {needle!r}"


def test_gate_is_an_owner_call():
    assert "owner call" in _bullet("GATE")


def test_no_second_sorting_rule():
    lowered = _text().lower()
    found = [p for p in _SECOND_RULE_PHRASES if p.lower() in lowered]
    assert not found, f"escalation-base.md states a rule of its own for whose call it is: {found}"


def test_version_header_at_least_five():
    match = re.search(r"<!--\s*escalation-version:\s*(\d+)\s*-->", _text())
    assert match, "escalation-version header missing or unparseable"
    assert int(match.group(1)) >= _MIN_VERSION
