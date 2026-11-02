"""The `--ignore-launch` caveat keeps its fresh-launch exception (#2323, vet 793).

Read-only prose guards over the edited docs: wherever the doctrine tells the advisor not to carry
`--ignore-launch` for a recorded cloud lane, it also keeps the one exception, a not-ready lane whose fix
went to a fresh launch, whose ignore stays until its vet is recorded `ready` or `parked-blocker`.
Without the exception the advisor drops that ignore and the abandoned lane's open fix-order window is
watched again for an ending that never comes.
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN = os.path.dirname(os.path.dirname(_HERE))
_WAVE_WATCH = os.path.join(_PLUGIN, "skills", "showrunner", "reference", "wave-watch.md")
_TRANSITION = os.path.join(_PLUGIN, "TRANSITION.md")


def _flat(path):
    with open(path, encoding="utf-8") as fh:
        return " ".join(fh.read().split())


def _section(text, heading):
    start = text.index(heading)
    end = text.find(" ## ", start + len(heading))
    return text[start:] if end < 0 else text[start:end]


def test_the_re_arm_sentence_keeps_the_fresh_launch_exception():
    text = _flat(_WAVE_WATCH)
    sentence = re.search(r"On \*\*re-arm\*\* after you act on an event, repeat .*?\*\*not\*\* ignored", text)
    assert sentence, "the re-arm sentence is gone"
    assert "fresh launch" in sentence.group(0)


def test_the_ignore_launch_section_keeps_the_fresh_launch_exception():
    section = _section(_flat(_WAVE_WATCH), "## `--ignore-launch` and re-arming")
    assert "takes a lane out of every path" in section
    assert re.search(r"exception is a not-ready lane whose fix went to a fresh launch.*?keep its ignore until "
                     r"you record its vet `ready` or `parked-blocker`", section)


def test_the_transition_bullet_and_note_keep_the_fresh_launch_exception():
    section = _section(_flat(_TRANSITION), "## Unreleased")
    drops = [m.start() for m in re.finditer(r"Drop any `--ignore-launch` you carry", section)]
    assert len(drops) == 2, "the bullet and the note each say to drop the ignore"
    for at in drops:
        assert "a not-ready lane whose fix went to a fresh launch" in section[at:at + 500]
