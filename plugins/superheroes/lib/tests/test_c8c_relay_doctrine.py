"""Doctrine guards for acting on the builders' account and the owner's conditional archive prompt.

Bites on: the orchestration section vanishing, moving past the adoption section or losing its
contents entry; the rule sentence, either citation, the helper command's flags or the never-delete
limit going missing; the section restating the relay's own steps; requirement, Canon, issue or
session ids in the section's prose; the cleanup steps going back to promising the owner exactly one
tap.

**Residual blind spots:** the restatement search is a word match on four relay words, so a restated
step phrased with none of them passes; the id search covers the section's own lines, not prose
written elsewhere.
"""
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN = os.path.dirname(os.path.dirname(_HERE))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from test_cloud_cleanup_doctrine import _FORBIDDEN_IDS  # noqa: E402

_REF = os.path.join(_PLUGIN, "skills", "showrunner", "reference")
_ORCHESTRATION = os.path.join(_REF, "orchestration.md")
_MERGE_TRAIN = os.path.join(_REF, "merge-train.md")
_WAVE_WATCH = os.path.join(_REF, "wave-watch.md")

_SECTION = "## Acting on the builders' account"
_NEXT = "## Adoption mechanics"
_CONTENTS_ENTRY = "- [Acting on the builders' account](#acting-on-the-builders-account)"
_RULE = "an action scoped to the builders' account goes through a session on that account"
_CLEANUP = "Cleaning up a finished cloud lane"
_ANSWERING = "Answering a builder note"


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _section_text(path, heading):
    """The lines under ``heading`` (a ``## `` line) up to the next ``## `` line."""
    lines = _read(path).split("\n")
    assert lines.count(heading) == 1, f"expected exactly one {heading!r} line in {path}"
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _section():
    return _section_text(_ORCHESTRATION, _SECTION)


def _collapsed(text):
    return " ".join(text.split())


def test_section_exists_once_before_adoption_and_has_a_contents_entry():
    # axis: the section's presence, position and contents entry — see bite-proof record c8c_wo_c.md
    lines = _read(_ORCHESTRATION).split("\n")
    assert lines.count(_SECTION) == 1
    assert lines.count(_NEXT) == 1
    assert lines.index(_SECTION) < lines.index(_NEXT)
    contents = lines[: lines.index("# Orchestration — launcher, ledger, and wave mechanics")]
    assert contents.count(_CONTENTS_ENTRY) == 1
    entries = [line for line in contents if line.startswith("- [")]
    assert entries.index(_CONTENTS_ENTRY) + 1 == entries.index("- [Adoption mechanics](#adoption-mechanics)")


def test_section_states_the_rule_sentence():
    # axis: the rule an advisor acts on when a step is scoped to the builders' account — see bite-proof record c8c_wo_c.md
    assert _RULE in _collapsed(_section())


def test_section_cites_both_homes_by_their_exact_headings():
    # axis: each citation names a heading that exists in the cited file — see bite-proof record c8c_wo_c.md
    text = _collapsed(_section())
    for path, name, heading in (
        (_WAVE_WATCH, "wave-watch.md", _ANSWERING),
        (_MERGE_TRAIN, "merge-train.md", _CLEANUP),
    ):
        citation = f"`skills/showrunner/reference/{name}` § {heading}"
        assert citation in text, citation
        assert f"## {heading}" in _read(path).split("\n"), f"{heading!r} is not a heading in {name}"


def test_section_carries_the_helper_command():
    # axis: the helper command's pinned account, background flag, name, model and effort — see bite-proof record c8c_wo_c.md
    text = _section()
    for needle in ("CLAUDE_CONFIG_DIR=", "claude --bg -n", "--model haiku", "--effort low"):
        assert needle in text, needle


def test_section_says_the_helper_never_deletes_and_deleting_needs_the_owner():
    # axis: the never-delete limit and the owner's word for a delete — see bite-proof record c8c_wo_c.md
    text = _collapsed(_section())
    assert "that it never deletes a session" in text
    assert "Deleting a session needs the owner's word every time." in text


def test_section_does_not_promise_a_cloud_session_an_archive_tool():
    # axis: the section never promises every cloud session an archive tool — see bite-proof record c8c_wo_d.md
    text = _collapsed(_section())
    assert "A cloud session's own tools include one" not in text
    assert "can include one that archives a session" in text


def test_section_restates_none_of_the_relays_steps():
    # axis: the relay's steps keep one home, in the wave-watch reference — see bite-proof record c8c_wo_c.md
    text = _section()
    found = [word for word in ("compose", "ensure", "cloud_relay", "record --repo-root") if word in text]
    assert found == [], found


def test_section_carries_no_requirement_canon_issue_or_session_ids():
    # axis: the shipped-doctrine rule on the section's own lines — see bite-proof record c8c_wo_c.md
    lines = _section().split("\n")
    assert [line for line in lines if line.strip()], "the section is empty"
    found = [
        (kind, line)
        for line in lines
        for kind, pattern in _FORBIDDEN_IDS.items()
        if pattern.search(line)
    ]
    assert found == [], found


def _cleanup_step(number):
    """The text of numbered step ``number`` of the cleanup procedure, joined into one line."""
    text = _section_text(_MERGE_TRAIN, f"## {_CLEANUP}")
    match = re.search(
        rf"^{number}\. (.*?)(?=^\d+\. |^\S|\Z)", text, re.MULTILINE | re.DOTALL
    )
    assert match, f"step {number} of the cleanup procedure was not found"
    return _collapsed(match.group(1))


def test_cleanup_steps_point_at_the_owner_message_not_one_tap():
    # axis: the owner's step follows the conditional message instead of promising one tap — see bite-proof record c8c_wo_c.md
    section = _collapsed(_section_text(_MERGE_TRAIN, f"## {_CLEANUP}"))
    assert "the only step the owner is ever asked for is the one tap" not in section
    assert "until the owner taps Allow" not in section
    assert "`ownerMessage`" in _cleanup_step(3)
    assert "`ownerMessage`" in _cleanup_step(5)


def _another_account_steps():
    """The relayed-answer steps of wave-watch.md, from "Another account." to "Not delivered", as one line."""
    text = _collapsed(_read(_WAVE_WATCH))
    start, end = text.index("**Another account.**"), text.index("**Not delivered, or `ensure` refused.**")
    return text[start:end]


@pytest.mark.parametrize("rule", [
    "never carries a shell-evaluated value you have not seen expanded",
    "print the whole composed `relayMessage`, never a truncated view",
    "Send exactly the `relayMessage` you printed",
    "never retyped from your own draft",
    "composing a new message; never edit a composed one",
    "a mismatch does not say which step changed it",
], ids=["no-unseen-shell-value", "print-whole", "send-printed", "no-retype", "recompose", "no-blame"])
def test_the_relayed_answer_steps_carry_the_advisor_send_rule(rule):
    # axis: the advisor sends exactly the composed text it read and recomposes on a change — see bite-proof record wo_2124_relay_say.md
    assert rule in _another_account_steps()
