"""C1-L11f (WO-F): a stacked light-lane layer has a moment to run the PR-mode handback check.

Read-only prose guards over the edited docs: a light-lane PR opens ready only when it is not stacked,
and a stacked layer on any lane is opened as a draft and marked ready only after the PR-mode
handback check passes on its pushed head.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN = os.path.dirname(_LIB)

_WORKHORSE = os.path.join(_PLUGIN, "skills", "workhorse", "SKILL.md")
_HANDBACK = os.path.join(_PLUGIN, "skills", "workhorse", "reference", "handback.md")


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _flat(text):
    return " ".join(text.split())


def _slice(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def _section_11():
    return _flat(_slice(_text(_WORKHORSE), "## 11. ", "## 12. "))


def _before_ready_paragraph():
    # the paragraph that opens "Before the ready marking" runs to the next paragraph, "When a PR closes"
    return _flat(_slice(_text(_HANDBACK), "Before the ready marking", "When a PR closes or is superseded"))


def test_workhorse_section_11_opens_a_stacked_light_lane_layer_as_a_draft():
    # axis: § 11 says an unstacked light-lane PR opens ready, a stacked layer opens as a draft, and no stacked layer is ready before the PR-mode handback check passes — see bite-proof record c1l11f_wo_f_light_ready
    section = _section_11()
    assert "A light-lane PR opens ready" in section
    assert "a stacked light-lane layer opens as a draft" in section
    assert "is marked ready only after the PR-mode handback check passes on its pushed head" in section
    assert "no stacked layer, on any lane, is marked or opened ready before that check passes" in section


def test_handback_before_ready_paragraph_names_the_stacked_light_lane_sequence():
    # axis: handback.md's before-ready paragraph gives the stacked light-lane sequence — push, open as a draft, run the PR-mode handback check, fix until ok, mark ready — see bite-proof record c1l11f_wo_f_light_ready
    paragraph = _before_ready_paragraph()
    assert "stacked light-lane layer" in paragraph
    assert "push, open the PR as a draft" in paragraph
    assert "run `vet_slot.py handback --pr <n> --repo <owner/name>` on it" in paragraph
    assert "until it prints `\"ok\": true`" in paragraph
    assert "then mark it ready" in paragraph
    draft = paragraph.index("open the PR as a draft")
    check = paragraph.index("run `vet_slot.py handback --pr <n> --repo <owner/name>` on it")
    assert draft < check < paragraph.index("until it prints") < paragraph.index("then mark it ready")
