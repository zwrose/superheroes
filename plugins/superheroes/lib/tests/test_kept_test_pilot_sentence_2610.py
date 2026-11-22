"""The kept test-pilot profile sentence (#2610): the leftover notice's wording, word for word in the docs.

Reads two named Markdown files; it never enumerates the plugin tree.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN = os.path.dirname(_LIB)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import leftover_settings as ls  # noqa: E402


def _read(*parts):
    with open(os.path.join(_PLUGIN, *parts), encoding="utf-8") as fh:
        return fh.read()


def test_fix_path_section_5_carries_the_sentence_in_its_opening_and_its_retire_gate():
    # axis: configure's fix path section 5 carries the notice's sentence word for word, once where it says the copy is read until retired and once at the retire gate
    fix = _read("skills", "configure", "reference", "fix.md")
    section5 = fix.split("## 5 — Retire leftover settings copies", 1)[1]
    assert section5.count(ls.KEPT_TEST_PILOT_PROFILE_SENTENCE) == 2


def test_upgrade_note_carries_the_sentence():
    # axis: the 2594 upgrade note carries the notice's sentence word for word
    assert ls.KEPT_TEST_PILOT_PROFILE_SENTENCE in _read("transition-notes", "2594.md")
