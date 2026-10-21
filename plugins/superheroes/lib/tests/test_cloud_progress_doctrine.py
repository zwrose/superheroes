"""Tests for the doctrine that names the cloud builder's progress comment (#2018).

Bites on: `PROGRESS_HEADER` changing without cloud.md's section following it, or cloud.md writing the header with a
different character; cloud.md's progress section losing the `progress` / `edit` verbs, `Lost work:` or the
15-minute rule; wave-watch.md's wedge section losing the header constant, `progressAgeSeconds` or the status ping;
TRANSITION.md's 0.45.0 notes (the release it shipped in) losing the progress section's heading.

**Residual blind spots:** the doctrine tests are phrase searches over the collapsed text, so a section that keeps
the phrase but contradicts it in the next sentence passes; nothing here compares the prose with what
`wave_watch.py` does with a progress comment.
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder as cb  # noqa: E402

_PLUGIN = os.path.abspath(os.path.join(_LIB, ".."))
_CLOUD = os.path.join(_PLUGIN, "skills", "workhorse", "reference", "cloud.md")
_WAVE_WATCH = os.path.join(_PLUGIN, "skills", "showrunner", "reference", "wave-watch.md")
_TRANSITION = os.path.join(_PLUGIN, "TRANSITION.md")
_CLOUD_SECTION = "The progress comment"
_WEDGE_SECTION = "Before treating `lane-stale` as a wedge"
_TRANSITION_HEADING = "### Wave watch: a cloud builder's progress comment"


def _read(path):
    # Strict decoding on purpose: a file that cannot be read fails the test, never passes it.
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _section(path, heading):
    match = re.search(
        r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", _read(path), re.MULTILINE | re.DOTALL
    )
    assert match, "the section %r was not found in %s" % (heading, os.path.basename(path))
    return " ".join(match.group(1).split())


def test_cloud_md_names_the_progress_header_character_for_character():
    # axis: the header the builder writes and the header cloud.md tells the builder to expect are the same string
    assert cb.PROGRESS_HEADER == "Builder progress (cloud build)."
    assert "`Builder progress (cloud build).`" in _section(_CLOUD, _CLOUD_SECTION)


def test_cloud_md_progress_section_names_the_verbs_the_lost_work_line_and_the_ping_rule():
    # axis: the builder's page names how to compose and edit the comment, the lost-work line and the 15-minute rule
    section = _section(_CLOUD, _CLOUD_SECTION)
    assert "cloud_builder.py progress" in section
    assert "cloud_builder.py edit" in section
    assert "Lost work:" in section
    assert "about 15 minutes" in section


def test_wave_watch_wedge_section_names_the_header_constant_the_age_key_and_the_status_ping():
    # axis: the advisor's page says the watch reads the progress comment and that a status ping comes first
    section = _section(_WAVE_WATCH, _WEDGE_SECTION)
    assert "PROGRESS_HEADER" in section
    assert "progressAgeSeconds" in section
    assert "status ping" in section


def test_transition_0_45_0_names_the_progress_section():
    # axis: the upgrade notes carry a section for the progress comment, linked from the Before-you-upgrade list
    notes = _section(_TRANSITION, "0.45.0")
    assert _TRANSITION_HEADING in notes
    assert "(#wave-watch-a-cloud-builders-progress-comment)" in notes
