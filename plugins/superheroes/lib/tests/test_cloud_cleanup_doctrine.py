"""Doctrine-search guards for the cloud-lane cleanup.

Bites on: any shipped line that reminds the owner about an unanswered archive prompt; the cleanup
procedure leaving its one home; requirement, Canon, issue or session ids in the prose this change
added.

**Residual blind spots:** the reminder search is a word match on lines that name the archive, so a
reminder phrased with none of its words, or split across two lines, passes.
"""
import difflib
import os
import re
import subprocess
import sys

import pytest

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PLUGINS = os.path.dirname(_PLUGIN)
_REPO = os.path.dirname(_PLUGINS)
_TESTS = os.path.join(_PLUGIN, "lib", "tests")
_LIB = os.path.join(_PLUGIN, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_cleanup  # noqa: E402
_BASE = "b300a85d64b4f339900509800ee6d9f60485c0f2"

_REF = "skills/showrunner/reference"
_MERGE_TRAIN = f"{_REF}/merge-train.md"
_SKILL = "skills/showrunner/SKILL.md"
_WAVE_WATCH = f"{_REF}/wave-watch.md"
_TRANSITION = "TRANSITION.md"
_CLOUD = "skills/workhorse/reference/cloud.md"
_DOCTRINE = (_MERGE_TRAIN, _SKILL, _WAVE_WATCH, _TRANSITION, _CLOUD)

_HOME_HEADING = "## Cleaning up a finished cloud lane"
# A line states the absence of a reminder when a negation comes before its first reminder word.
_NEGATION = re.compile(r"\b(nothing|never|no|not)\b", re.IGNORECASE)
_REMINDER_WORDS = re.compile(
    r"\bremind|\bnudge|follow[ -]up|\bchase|\bagain\b|still waiting|unanswered", re.IGNORECASE
)
_ARCHIVE = re.compile(r"archive", re.IGNORECASE)


def _read(path):
    # Strict decoding on purpose: a file that cannot be read fails the test, never passes it.
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _shipped(extensions, *, skip_tests=True):
    """Every shipped file under the plugin root with one of ``extensions``, as (relpath, abspath)."""
    found = []
    for root, dirs, files in os.walk(_PLUGIN):
        dirs[:] = sorted(d for d in dirs if d not in {"__pycache__", ".git", "node_modules"})
        if skip_tests and os.path.abspath(root) == _TESTS:
            dirs[:] = []
            continue
        for name in sorted(files):
            if name.endswith(extensions):
                path = os.path.join(root, name)
                found.append((os.path.relpath(path, _PLUGIN).replace(os.sep, "/"), path))
    assert found, "no shipped files found; the plugin root did not resolve"
    return found


def _collapsed(path):
    return " ".join(_read(path).split())


def _reminder_hits(lines):
    """Lines naming the archive and a reminder word with no negation ahead of the first such word."""
    hits = []
    for line in lines:
        if not _ARCHIVE.search(line):
            continue
        trigger = _REMINDER_WORDS.search(line)
        if trigger and not _NEGATION.search(line[: trigger.start()]):
            hits.append(line.strip())
    return hits


def test_no_reminder_about_an_unanswered_archive_prompt():
    hits = []
    for rel, path in _shipped((".md", ".py")):
        hits.extend((rel, line) for line in _reminder_hits(_read(path).split("\n")))
    assert hits == [], hits


def test_cleanup_procedure_has_one_home_and_the_others_point_to_it():
    merge_train = _read(os.path.join(_PLUGIN, _MERGE_TRAIN)).split("\n")
    assert merge_train.count(_HOME_HEADING) == 1
    pointer = "merge-train.md` § Cleaning up a finished cloud lane"
    for rel in (_SKILL, _WAVE_WATCH):
        assert pointer in _collapsed(os.path.join(_PLUGIN, rel)), rel


def test_builder_side_of_the_archive_request():
    text = _read(os.path.join(_PLUGIN, _CLOUD))
    heading = "When the advisor asks you to archive your session"
    assert text.split("\n").count(f"## {heading}") == 1
    assert f"- [{heading}](#when-the-advisor-asks-you-to-archive-your-session)" in text.split("# Building")[0]

    match = re.search(r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, "the archive-request section was not found"
    section = " ".join(match.group(1).split())
    assert "act only after its `state` is `closed`" in section
    assert "post one line on your issue naming the session tools you do have, and stop" in section
    assert "Never delete a session" in section

    for advisor_text in (cloud_cleanup.ARCHIVE_TEXT_MERGED, cloud_cleanup.ARCHIVE_TEXT_CLOSED):
        assert "Archive your own session" in advisor_text
        assert "post one line on your issue naming the session tools you do have" in advisor_text


def _added_lines(rel):
    base = subprocess.run(
        ["git", "-C", _REPO, "show", f"{_BASE}:plugins/superheroes/{rel}"],
        capture_output=True,
        text=True,
    )
    assert base.returncode == 0, f"cannot read {rel} at {_BASE}: {base.stderr}"
    before = base.stdout.split("\n")
    now = _read(os.path.join(_PLUGIN, rel)).split("\n")
    return [
        line
        for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, before, now, autojunk=False).get_opcodes()
        if tag in ("insert", "replace")
        for line in now[j1:j2]
    ]


_FORBIDDEN_IDS = {
    "requirement id": re.compile(r"\b(?:U?FR-\d+|R\d+)\b"),
    "Canon id": re.compile(r"\d{4}-\d{2}-\d{2}-[0-9a-f]{8}"),
    "issue number": re.compile(r"#\d+"),
    "session id": re.compile(r"session_"),
}


@pytest.mark.parametrize("rel", _DOCTRINE)
def test_added_lines_carry_no_requirement_canon_issue_or_session_ids(rel):
    added = _added_lines(rel)
    assert added, f"{rel} has no lines added since {_BASE}"
    found = [
        (kind, line)
        for line in added
        for kind, pattern in _FORBIDDEN_IDS.items()
        if pattern.search(line)
    ]
    assert found == [], found
