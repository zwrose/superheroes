"""Doctrine guards for the advisor's 30-minute owner check-in.

Bites on: the one home (`## Owner check-in while lanes run` in orchestration.md) losing its cadence, the
note's shape, the every-wake rule, either ceiling bound (`--max-seconds`, `--max-total-seconds`, each
parsed as a number and held to 1500 or less), the override of wave-watch.md's example values, or the
not-held report; the charter's duty 9 or showrunner-resume Step 6 losing its pointer to that home; and
the charter or the resume skill restating the ceiling number or the note's shape (one home).

**Residual blind spots:** these are phrase searches over the collapsed text, so a home that keeps a phrase
in a sentence that no longer says what it did passes; the ceiling is read from the prose, so it is not
compared with the values a live `loop` run receives (wave-watch.md and lib/wave_watch.py belong to another
change); a sixth place that tells the advisor to arm a watch is not covered.
"""
import os
import re

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SKILLS = os.path.join(_PLUGIN, "skills")
_ORCHESTRATION = os.path.join(_SKILLS, "showrunner", "reference", "orchestration.md")
_CHARTER = os.path.join(_SKILLS, "showrunner", "SKILL.md")
_RESUME = os.path.join(_SKILLS, "showrunner-resume", "SKILL.md")

_HOME_HEADING = "## Owner check-in while lanes run"
_POINTER = "skills/showrunner/reference/orchestration.md` § Owner check-in while lanes run"
_CEILING_LIMIT = 1500


def _read(path):
    # Strict decoding on purpose: a file that cannot be read fails the test, never passes it.
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _collapse(text):
    return " ".join(text.split())


def _home():
    """The collapsed text of the home section, from its heading up to the next `## ` heading."""
    text = _collapse(_read(_ORCHESTRATION))
    assert text.count(_HOME_HEADING) == 1, f"{_HOME_HEADING!r} must occur once in orchestration.md"
    first = text.index(_HOME_HEADING)
    following = text.find("## ", first + len(_HOME_HEADING))
    assert following > first, "no heading follows the home section in orchestration.md"
    return text[first:following]


def _duty_9():
    """The collapsed text of the charter's duty 9, up to the line starting `10. `."""
    text = _read(_CHARTER)
    found = re.findall(r"^9\. \*\*Orchestration.*?(?=^10\. )", text, re.MULTILINE | re.DOTALL)
    assert len(found) == 1, f"duty 9 must be found once in the charter, found {len(found)}"
    return _collapse(found[0])


def _resume_step_6():
    """The collapsed text of showrunner-resume Step 6, up to `## Step 7`."""
    text = _read(_RESUME)
    found = re.findall(r"^## Step 6.*?(?=^## Step 7)", text, re.MULTILINE | re.DOTALL)
    assert len(found) == 1, f"Step 6 must be found once in showrunner-resume, found {len(found)}"
    return _collapse(found[0])


def _assert_contains(text, needles, element, name):
    for needle in needles:
        assert needle in text, f"{element}: {name} lacks {needle!r}"


def _assert_bound(flag, element):
    home = _home()
    found = re.findall(r"`" + re.escape(flag) + r"` at most (\d+)", home)
    assert len(found) == 1, f"{element}: orchestration.md home must state `{flag}` at most N once, found {found}"
    assert int(found[0]) <= _CEILING_LIMIT, (
        f"{element}: orchestration.md home states `{flag}` at most {found[0]}, over {_CEILING_LIMIT}"
    )


def test_e1_cadence():
    # axis: the home states the 30-minute floor for a note, counted from the last note, even when nothing changed
    _assert_contains(
        _home(),
        [
            "While any lane is live, send the owner a status note at least every 30 minutes, even when nothing changed.",
            "count from the last note you sent, not from the last wake",
        ],
        "E1 cadence",
        "orchestration.md home",
    )


def test_e2_shape():
    # axis: the home states what a note carries: a line per lane with phase and age, what was answered, what waits on the owner
    _assert_contains(
        _home(),
        ["its phase and its age", "anything answered since the last note", "anything waiting on the owner"],
        "E2 shape",
        "orchestration.md home",
    )


def test_e3_every_wake():
    # axis: every wake, an event or the loop's own timer, sends the note
    _assert_contains(
        _home(),
        ["Every wake sends the note.", "whether an event or the loop's own `timer`"],
        "E3 every wake",
        "orchestration.md home",
    )


def test_e4_max_seconds_bound():
    # axis: the stated per-arm bound is a number no larger than 1500, so a loosened number goes red
    _assert_bound("--max-seconds", "E4 max-seconds bound")


def test_e5_max_total_seconds_bound():
    # axis: the stated total bound is a number no larger than 1500, and the home says only it ends the loop
    _assert_bound("--max-total-seconds", "E5 max-total-seconds bound")
    _assert_contains(
        _home(), ["only `--max-total-seconds` ends the loop"], "E5 max-total-seconds bound", "orchestration.md home"
    )


def test_e6_override():
    # axis: the home overrides wave-watch.md's example values on every host
    _assert_contains(
        _home(),
        ["These values replace the example values in `wave-watch.md`", "on every host"],
        "E6 override",
        "orchestration.md home",
    )


def test_e7_not_held_report():
    # axis: the home tells the advisor to report that the check-in is not held, why, and what clears it
    _assert_contains(
        _home(),
        ["the 30-minute check-in is not held, why, and what clears it"],
        "E7 not-held report",
        "orchestration.md home",
    )


def test_e8_charter_pointer():
    # axis: the charter's duty 9 carries the cadence in brief, the resume-first rule and the pointer to the home
    _assert_contains(
        _duty_9(),
        [
            "at least every 30 minutes, even when nothing changed",
            "runs `showrunner-resume` first, resume point or not",
            _POINTER,
        ],
        "E8 charter pointer",
        "SKILL.md duty 9",
    )


def test_e9_resume_rearm_and_note():
    # axis: resume Step 6 arms with the home's ceiling, sends the note after the Step 7 report, and carries the not-held report on line 3
    _assert_contains(
        _resume_step_6(),
        [
            "carries the ceiling in",
            _POINTER,
            "right after the Step 7 report",
            "line 3 of the report carries that section's not-held report",
        ],
        "E9 resume re-arm and note",
        "showrunner-resume SKILL.md Step 6",
    )


def test_e10_one_home():
    # axis: neither the charter nor the resume skill restates the ceiling number or the note's shape; the home is listed in the contents
    restated = ["1500", "25 minutes", "its phase and its age", "anything answered since the last note"]
    for path, name in ((_CHARTER, "showrunner SKILL.md"), (_RESUME, "showrunner-resume SKILL.md")):
        text = _collapse(_read(path))
        for needle in restated:
            assert needle not in text, f"E10 one home: {name} restates {needle!r}"
    text = _read(_ORCHESTRATION)
    contents = re.findall(r"\A# Contents\n(.*?)(?=^# )", text, re.MULTILINE | re.DOTALL)
    assert len(contents) == 1, "E10 one home: orchestration.md # Contents block not found"
    assert "[Owner check-in while lanes run](#owner-check-in-while-lanes-run)" in contents[0], (
        "E10 one home: orchestration.md # Contents lacks the home's entry"
    )
