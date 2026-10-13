"""Doctrine-search guards for the cloud-lane cleanup and the gardening pass's duty 8.

Bites on: any shipped line that reminds the owner about an unanswered archive prompt; any new
reader of the reviewer-pass gardening line beyond the one the gardening pass names; the closed
duties list drifting from eight, or duties 1 to 7 changing; the gardening record losing the
reviewer-pass line; the cleanup procedure leaving its one home; requirement, Canon, issue or
session ids in the prose this change added.

**Residual blind spots:** the reminder search is a word match on lines that name the archive, so a
reminder phrased with none of its words, or split across two lines, passes; the reader search is a
text search for the two names, so a reader that builds the subcommand name at run time passes.
"""
import difflib
import hashlib
import os
import re
import subprocess

import pytest

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PLUGINS = os.path.dirname(_PLUGIN)
_REPO = os.path.dirname(_PLUGINS)
_TESTS = os.path.join(_PLUGIN, "lib", "tests")
_BASE = "b300a85d64b4f339900509800ee6d9f60485c0f2"

_REF = "skills/showrunner/reference"
_MERGE_TRAIN = f"{_REF}/merge-train.md"
_SKILL = "skills/showrunner/SKILL.md"
_OWNER_DECISIONS = f"{_REF}/owner-decisions.md"
_WAVE_WATCH = f"{_REF}/wave-watch.md"
_TRANSITION = "TRANSITION.md"
_DOCTRINE = (_MERGE_TRAIN, _SKILL, _OWNER_DECISIONS, _WAVE_WATCH, _TRANSITION)

_HOME_HEADING = "## Cleaning up a finished cloud lane"
_DUTIES_LABEL = "**The eight duties, a closed list.**"
_FIRST_DUTY = "1. **Age the P1s.**"
_MEMORY_PARAGRAPH = "**Memory gardening at the pass.**"
# sha256 of duties 1 to 7 (from the first duty's line through the end of item 7), read from the
# base commit before duty 8 was appended; lines joined with newlines, trailing blanks dropped.
_DUTIES_1_TO_7_SHA256 = "07aeae8f5e1c4c0f877818e17b02451c2495fb29b03bc56242dc0d23bcc1fe98"

_ABSENCE_SENTENCE = (
    "If the owner never answers the archive prompt, the session stays listed and the advisor "
    "carries on; nothing reminds the owner."
)
# (file, line text) pairs that state the absence of a reminder; every other hit is a reminder.
_REMINDER_ALLOWLIST = {
    (_MERGE_TRAIN, _ABSENCE_SENTENCE),
    (
        _TRANSITION,
        "- The advisor cleans up a cloud lane only after its pull request merges or closes, the "
        "same way for both. While the pull request is open, handed back or parked, nothing is "
        "cleaned up. The only step it asks of the owner is the archive prompt, and on a request "
        "that could not be confirmed it asks nothing; nothing reminds the owner about an "
        "unanswered prompt.",
    ),
}
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


def _duties_block(text):
    """The lines of the closed duties list, from the first duty through the memory paragraph's start."""
    lines = text.split("\n")
    labels = [i for i, line in enumerate(lines) if line.strip() == _DUTIES_LABEL]
    assert len(labels) == 1, f"expected exactly one {_DUTIES_LABEL!r} line, found {len(labels)}"
    start = next(
        (i for i in range(labels[0], len(lines)) if lines[i].startswith(_FIRST_DUTY)), None
    )
    assert start is not None, "the first duty's line was not found after the label"
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith(_MEMORY_PARAGRAPH)), None
    )
    assert end is not None, "the memory-gardening paragraph was not found after the duties"
    block = lines[start:end]
    while block and not block[-1].strip():
        block.pop()
    return block


def _numbered_items(block):
    """(number, first line index) of each top-level numbered item in ``block``."""
    return [(int(m.group(1)), i) for i, line in enumerate(block) if (m := re.match(r"(\d+)\. ", line))]


def test_no_reminder_about_an_unanswered_archive_prompt():
    hits = set()
    for rel, path in _shipped((".md", ".py")):
        for line in _read(path).split("\n"):
            if _ARCHIVE.search(line) and _REMINDER_WORDS.search(line):
                hits.add((rel, line.strip()))
    assert hits == _REMINDER_ALLOWLIST, (
        f"unexpected: {sorted(hits - _REMINDER_ALLOWLIST)}; missing: "
        f"{sorted(_REMINDER_ALLOWLIST - hits)}"
    )


def test_reviewer_pass_gardening_line_has_no_new_reader():
    py_readers = []
    for rel, path in _shipped((".py",)):
        if rel == "lib/cloud_setup.py":
            continue
        for line in _read(path).split("\n"):
            if "gardening_lines" in line or re.search(
                r"cloud_setup\S*.*\bgardening\b|\bgardening\b.*cloud_setup", line
            ):
                py_readers.append((rel, line.strip()))
    assert py_readers == [], f"shipped callers of the gardening line: {py_readers}"

    md_readers = sorted(
        rel
        for rel, path in _shipped((".md",))
        if re.search(r"cloud_setup\.py gardening", _collapsed(path))
    )
    assert md_readers == sorted([_OWNER_DECISIONS, _TRANSITION]), md_readers


def test_duty_8_closes_the_list_and_duties_1_to_7_are_unchanged():
    block = _duties_block(_read(os.path.join(_PLUGIN, _OWNER_DECISIONS)))
    items = _numbered_items(block)
    assert [n for n, _ in items] == list(range(1, 9)), f"duties are numbered {[n for n, _ in items]}"
    item_8 = "\n".join(block[items[7][1]:])
    assert item_8.startswith("8. **Read the reviewer pass"), item_8[:80]
    assert "cloud_setup.py gardening" in " ".join(item_8.split())

    first_seven = block[: items[7][1]]
    while first_seven and not first_seven[-1].strip():
        first_seven.pop()
    digest = hashlib.sha256("\n".join(first_seven).encode()).hexdigest()
    assert digest == _DUTIES_1_TO_7_SHA256, "duties 1 to 7 changed"


def test_the_old_label_appears_nowhere_under_plugins():
    old = "The seven" + " duties"  # split so this file does not name it
    named = []
    scanned = 0
    for root, dirs, files in os.walk(_PLUGINS):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", "node_modules"}]
        for name in files:
            if name.endswith((".md", ".py")):
                scanned += 1
                path = os.path.join(root, name)
                if old in _read(path):
                    named.append(os.path.relpath(path, _PLUGINS))
    assert scanned, "no files scanned; the plugins directory did not resolve"
    assert named == [], named


def test_gardening_record_lists_the_reviewer_pass_line():
    text = _read(os.path.join(_PLUGIN, _OWNER_DECISIONS))
    match = re.search(r"^## The gardening record\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, "the gardening record section was not found"
    bullets = [line for line in match.group(1).split("\n") if line.startswith("- ")]
    reviewer = [b for b in bullets if "reviewer-pass line" in b]
    assert len(reviewer) == 1, reviewer
    assert "duty 8" in reviewer[0] and "Renew now" in reviewer[0]


def test_cleanup_procedure_has_one_home_and_the_others_point_to_it():
    merge_train = _read(os.path.join(_PLUGIN, _MERGE_TRAIN)).split("\n")
    assert merge_train.count(_HOME_HEADING) == 1
    pointer = "merge-train.md` § Cleaning up a finished cloud lane"
    for rel in (_SKILL, _WAVE_WATCH):
        assert pointer in _collapsed(os.path.join(_PLUGIN, rel)), rel


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
