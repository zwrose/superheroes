"""Detector for the `--review-only` headless stall shape (#1133).

The shape this pins: a headless `claude -f`-style run reaches the `--review-only`
tiered presentation, opens an ``AskUserQuestion`` nobody can answer, and stalls
until its harness kills it (observed live on PR #1130). The disposition ratified
for #1133 is a **prose degradation** — the presentation is written to a durable
artifact and the run exits cleanly.

Each test names one guarded element, and each is red against the pre-#1133
surface:

1. every question on the ``--review-only`` path is gated on the interactivity
   flag, and the gate precedes the first question;
2. the path names a reachable headless contract, and that contract names the
   durable artifact;
3. the invocation table's ``--review-only`` row states the headless behavior
   (drift-consistency with 1 and 2);
4. the interactive presentation is intact (the regression guard for #1133's
   "interactive behavior unchanged").
"""
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_REVIEW_CODE = os.path.join(_PLUGIN_ROOT, "skills", "review-code")
_SKILL_MD = os.path.join(_REVIEW_CODE, "SKILL.md")
_HEADLESS_MD = os.path.join(_REVIEW_CODE, "reference", "headless-presentation.md")

# The interactive question tool, and the flag any question on this path must be gated on.
_QUESTION = "AskUserQuestion"
_GATE_FLAG = "$INTERACTIVE"

# The durable artifact the degradation writes. One literal, quoted from the contract.
_ARTIFACT = "$SESSION_DIR/round-1/presentation.md"

# The headless contract's plugin-relative citation, as SKILL.md must spell it.
_CONTRACT_CITATION = "skills/review-code/reference/headless-presentation.md"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _section(text, heading):
    """The body of a markdown section: from `heading` to the next same-level heading."""
    marker = heading.strip()
    level = len(marker) - len(marker.lstrip("#"))
    start = text.index(heading)
    body_start = start + len(heading)
    nxt = re.compile(r"^#{1,%d} " % level, re.MULTILINE)
    m = nxt.search(text, body_start)
    return text[body_start:m.start()] if m else text[body_start:]


@pytest.fixture(scope="module")
def review_only():
    """The shipped `### --review-only` section of review-code's SKILL.md."""
    return _section(_read(_SKILL_MD), "\n### `--review-only`\n")


def test_every_question_on_the_review_only_path_is_interactivity_gated(review_only):
    """The stall shape: a question reached with nothing gating it on interactivity.

    Not merely "the flag is mentioned somewhere" — the gate must come *before* the
    first question, so a headless run has branched away before one is ever formed.
    """
    first_question = review_only.find(_QUESTION)
    assert first_question != -1, (
        "the `--review-only` section no longer mentions %s at all — if the interactive "
        "presentation moved, re-point this detector at its new home rather than deleting it"
        % _QUESTION
    )
    first_gate = review_only.find(_GATE_FLAG)
    assert first_gate != -1, (
        "`--review-only` reaches %s with no `%s` gate in the section: a headless run has "
        "nothing telling it to branch away, so it stalls on a question nobody can answer (#1133)"
        % (_QUESTION, _GATE_FLAG)
    )
    assert first_gate < first_question, (
        "the `%s` gate appears at offset %d but the first %s is at offset %d — a gate "
        "downstream of the question it guards does not prevent the stall (#1133)"
        % (_GATE_FLAG, first_gate, _QUESTION, first_question)
    )


def test_review_only_names_a_reachable_headless_contract(review_only):
    """The disposition is a degradation: a named contract, and a durable artifact."""
    assert _CONTRACT_CITATION in review_only, (
        "`--review-only` names no headless contract — the gate has nowhere to send a "
        "headless run (#1133). Expected a citation of %s" % _CONTRACT_CITATION
    )
    assert os.path.isfile(_HEADLESS_MD), (
        "the headless contract %s is cited but does not exist — a dangling pointer is not "
        "a disposition (#1133)" % _HEADLESS_MD
    )
    contract = _read(_HEADLESS_MD)
    assert _ARTIFACT in contract, (
        "the headless contract does not name the durable artifact `%s` — a degradation that "
        "writes nowhere is indistinguishable from a review that never ran (#1133)" % _ARTIFACT
    )


def test_invocation_table_states_the_headless_behavior():
    """DoD row 3: the chosen disposition is stated in the skill's own path table."""
    rows = [
        line for line in _read(_SKILL_MD).splitlines()
        if line.startswith("|") and "--review-only`" in line
    ]
    assert rows, "no `--review-only` row found in review-code's invocation table"
    assert any("eadless" in row for row in rows), (
        "the invocation table's `--review-only` row does not state the headless behavior — "
        "the path table and the section would drift (#1133 DoD). Rows seen: %r" % rows
    )


def test_interactive_presentation_is_intact(review_only):
    """DoD row 2: interactive behavior unchanged — the tiered presentation still stands.

    Both tiers ask, and the review gate still partitions into auto-include vs ask-set.
    """
    assert "Critical and Important findings (ask-set) — individually" in review_only
    assert "Minor and Nit findings (ask-set) — batched, multi-select" in review_only
    assert review_only.count(_QUESTION) >= 2, (
        "the interactive tiered presentation lost a question tier — the headless "
        "degradation must not change what an interactive run does (#1133)"
    )
    assert "`auto-include` = `recommendation == Fix`" in review_only
