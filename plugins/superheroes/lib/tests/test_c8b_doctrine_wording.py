"""Wording guards for the cloud setup sitting, the ledger rows, the launch go-ahead and the transition notes.

Bites on: the step 7 sentence going back to saying a failed check writes nothing; the picker-reader
ledger row going back to a compare after a passed check; the owner-decisions text using the launch
word for the owner's go-ahead; the parked-build ledger row going back to a watch cycle and a claim of
no duplicate; the transition note losing `compare --environment`.

**Residual blind spots:** each guard is a text search for the words it names, so a rewording that keeps
the old meaning in other words passes.
"""
import os
import re

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REPO = os.path.dirname(os.path.dirname(_PLUGIN))
SET_UP = os.path.join(_PLUGIN, "skills", "configure", "reference", "set-up.md")
OWNER_DECISIONS = os.path.join(_PLUGIN, "skills", "showrunner", "reference", "owner-decisions.md")
TRANSITION = os.path.join(_PLUGIN, "TRANSITION.md")
LEDGERS = os.path.join(_REPO, "LEDGERS.md")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _section_six():
    text = _read(SET_UP)
    start = text.index("## 6 — Cloud builds")
    end = text.find("\n## ", start + 1)
    return " ".join(text[start:end if end != -1 else len(text)].split())


def _ledger_row(name):
    rows = [line for line in _read(LEDGERS).splitlines() if line.startswith("| **" + name)]
    assert len(rows) == 1, "LEDGERS.md has %d rows starting with %r" % (len(rows), name)
    return rows[0]


def _transition_section(heading):
    text = _read(TRANSITION)
    match = re.search(r"^### %s\n(.*?)(?=^### |^## |\Z)" % re.escape(heading), text, re.MULTILINE | re.DOTALL)
    assert match, "TRANSITION.md has no section %r" % heading
    return " ".join(match.group(1).split())


def test_step_seven_matches_what_judge_does_on_a_failed_check():
    # axis: step 7 names the failed-check marker and no longer says a failed check wrote nothing
    section = _section_six()
    assert "has written nothing" not in section
    assert "failed-check marker" in section
    assert "A passed check has written the setup record" in section


def test_the_picker_row_compares_before_make_start_and_judge():
    # axis: the picker-reader ledger row says the compare comes before each of the three commands
    row = _ledger_row("Cloud environment picker reader")
    assert "after a passed check" not in row
    assert "before" in row
    for verb in ("`make`", "`start`", "`judge`"):
        assert verb in row, verb


def test_owner_decisions_never_calls_the_go_ahead_a_launch_word():
    # axis: the owner's go-ahead to launch is never called the launch word, which names the place
    assert "launch word" not in _read(OWNER_DECISIONS)
    assert "launch go-ahead" in _read(OWNER_DECISIONS)


def test_the_parked_build_row_names_the_three_runs_and_the_duplicate_window():
    # axis: the parked-build ledger row names where send-back runs and allows one duplicate message
    row = _ledger_row("Parked cloud build recovery")
    assert "watch cycle" not in row
    assert "sent back twice" not in row
    assert "gardening" in row


def test_the_setup_sitting_note_names_the_compare_command():
    # axis: the transition note for the setup sitting names compare --environment
    assert "compare --environment" in _transition_section("Cloud builds: the setup sitting")
