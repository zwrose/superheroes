"""Detector for the `--review-only` headless stall shape (#1133).

The shape this pins: a headless `claude -p` run reaches the `--review-only`
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
_SETUP_MD = os.path.join(_REVIEW_CODE, "reference", "setup.md")
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


# axis: reachability of an interactive question from a headless run — a question present in the
# `--review-only` section with no interactivity gate ahead of it. Not phrasing, not flag presence
# anywhere in the file: the gate must sit upstream of the first question in that section.
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


# axis: the gated-away branch has somewhere to go and something to write — a named contract that
# resolves on disk, and a durable artifact path inside it. Not the contract's wording.
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


# axis: drift between the path table and the section — the table's `--review-only` row silent on a
# headless behavior the section defines. Not the row's wording.
def test_invocation_table_states_the_headless_behavior():
    """DoD row 3: the chosen disposition is stated in the skill's own path table."""
    rows = [
        line for line in _read(_SKILL_MD).splitlines()
        if line.startswith("|") and "--review-only`" in line
    ]
    assert rows, "no `--review-only` row found in review-code's invocation table"
    # The row must state the behavior, not merely say the word: it names the artifact the
    # degradation writes. "Headless: refuses" or "not supported headless" cannot satisfy this.
    stating = [row for row in rows if "eadless" in row and _ARTIFACT in row]
    assert stating, (
        "the invocation table's `--review-only` row does not state the headless behavior "
        "concretely — it must name the artifact `%s` the degradation writes, so the table "
        "cannot drift into describing some other disposition (#1133 DoD). Rows seen: %r"
        % (_ARTIFACT, rows)
    )


# axis: the flag the gate reads is resolved fail-closed at Setup — the executable assignment in
# setup.md, not the prose around it. A `true` literal there is a headless run that copies its way
# back into the stall, which is where this defect actually lived (#1133 review round 1).
def test_setup_resolves_the_flag_fail_closed():
    setup = _read(_SETUP_MD)
    assignments = re.findall(r"^\s*INTERACTIVE=(\S+)", setup, re.MULTILINE)
    assert assignments, (
        "reference/setup.md contains no `INTERACTIVE=` assignment — the gate in SKILL.md reads a "
        "flag nothing sets, and an unset flag is decided by whatever the orchestrator improvises (#1133)"
    )
    assert all(value == "false" for value in assignments), (
        "reference/setup.md assigns INTERACTIVE=%r — every shipped literal must be `false`, the "
        "fail-closed rung, promoted to true only on positive evidence a human is present. A `true` "
        "literal copied verbatim into a headless run walks it straight into the stall (#1133)"
        % assignments
    )


# axis: the resolved flag survives compaction — the presentation gate routes *unknown* to the
# degradation, so a cold-resumed interactive run that cannot recover the flag silently loses its
# questions. Pins the persisted field, not the prose describing it.
def test_interactivity_survives_compaction():
    skill = _read(_SKILL_MD)
    assert "interactive:$interactive" in skill, (
        "meta.json's writer does not persist an `interactive` field — after compaction the "
        "channel is unknown, unknown takes the degradation, and an interactive run loses its "
        "tiered presentation (#1133 review round 1)"
    )
    review_only = _section(skill, "\n### `--review-only`\n")
    compaction = [
        para for para in review_only.split("\n\n")
        if "compacted between dispatch and presentation" in para
    ]
    assert compaction, "the `--review-only` compaction-recovery paragraph is gone"
    assert "$INTERACTIVE" in compaction[0], (
        "the compaction-recovery step does not restore `$INTERACTIVE` — it restores everything "
        "the gate needs except the flag the gate branches on (#1133 review round 1)"
    )


# axis: regression in the interactive path — a question tier or the review gate's partition lost
# while adding the headless branch. Not the headless branch itself.
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
