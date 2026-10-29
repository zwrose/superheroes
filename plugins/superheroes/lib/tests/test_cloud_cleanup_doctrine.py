"""Doctrine-search guards for the cloud-lane cleanup and the gardening pass's duty 8.

Bites on: any shipped line that reminds the owner about an unanswered archive prompt; any new
reader of the reviewer-pass gardening line beyond the one the gardening pass names; the closed
duties list drifting from eight, or duties 1 to 7 changing; the gardening record losing the
reviewer-pass line; the cleanup procedure, its heading or its distinctive step appearing in a
second shipped document; requirement, Canon, issue or session ids in the prose this change added.

**Residual blind spots:** the reminder search is a word match on lines that name the archive, so a
reminder phrased with none of its words, or split across two lines, passes; the reader search is a
text search for the two names, so a reader that builds the subcommand name at run time passes.
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
# `main` just before the cloud-builders stack merged: this layer's base must stay reachable from
# `main` after the stack's squash merge, which leaves the layer heads it was built on unreachable.
_BASE = "458cc409ac56bcf2b23a04bd8dfe0a33d805deb9"

_REF = "skills/showrunner/reference"
_MERGE_TRAIN = f"{_REF}/merge-train.md"
_SKILL = "skills/showrunner/SKILL.md"
_OWNER_DECISIONS = f"{_REF}/owner-decisions.md"
_WAVE_WATCH = f"{_REF}/wave-watch.md"
_TRANSITION = "TRANSITION.md"
_CLOUD = "skills/workhorse/reference/cloud.md"
_DOCTRINE = (_MERGE_TRAIN, _SKILL, _OWNER_DECISIONS, _WAVE_WATCH, _TRANSITION, _CLOUD)

_HOME_HEADING = "## Cleaning up a finished cloud lane"
# A reminder verb is suppressed only by a negation that directly governs it ("nothing reminds", "never
# remind", "no reminder", "not remind"), not by a negation sitting in an earlier condition.
_NEGATION_BEFORE = re.compile(r"\b(?:nothing|never|no|not)\s+(?:(?:ever|yet|then|again|also)\s+)?$|n't\s+$", re.IGNORECASE)
_REMINDER_VERBS = re.compile(r"\bremind|\bnudge|follow[ -]up|\bchase", re.IGNORECASE)
_WEAK_WORDS = re.compile(r"\bagain\b|still waiting|unanswered", re.IGNORECASE)
_DUTIES_LABEL = "**The eight duties, a closed list.**"
_FIRST_DUTY = "1. **Age the P1s.**"
_MEMORY_PARAGRAPH = "**Memory gardening at the pass.**"
# The label line of the closed list as the base commit had it, before duty 8 was appended.
_BASE_DUTIES_LABEL = "**The seven" + " duties, a closed list.**"  # split: see the old-label test
_ARCHIVE = re.compile(r"archive", re.IGNORECASE)
_NEGATION_WORD = re.compile(r"\b(?:nothing|never|no|not)\b", re.IGNORECASE)
_CLAUSE_BREAK = re.compile(r"[,;.:\u2014]")


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


def _negated_in_clause(line, start):
    """True when a negation word stands earlier in the same clause as the match at ``start``: the text since
    the last comma, semicolon, full stop, colon or em dash before it."""
    clause = _CLAUSE_BREAK.split(line[:start])[-1]
    return bool(_NEGATION_WORD.search(clause))


def _duties_block(text, label=_DUTIES_LABEL):
    """The lines of the closed duties list, from the first duty through the memory paragraph's start."""
    lines = text.split("\n")
    labels = [i for i, line in enumerate(lines) if line.strip() == label]
    assert len(labels) == 1, f"expected exactly one {label!r} line, found {len(labels)}"
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


def _reminder_hits(lines):
    """Lines naming the archive that carry a reminder verb no negation directly governs; a line with no
    reminder verb is a hit on any weak word (again, still waiting, unanswered) with no negation earlier in its clause."""
    hits = []
    for line in lines:
        if not _ARCHIVE.search(line):
            continue
        verbs = list(_REMINDER_VERBS.finditer(line))
        if verbs:
            if any(not _NEGATION_BEFORE.search(line[: m.start()]) for m in verbs):
                hits.append(line.strip())
            continue
        # axis: every weak word is tested for a negation earlier in its own clause, not just the first — see bite-proof record c8a_wo4.md
        if any(not _negated_in_clause(line, m.start()) for m in _WEAK_WORDS.finditer(line)):
            hits.append(line.strip())
    return hits


def test_the_reminder_detector_ties_a_negation_to_the_reminder_verb():
    assert _reminder_hits(["If the owner has not answered the archive prompt, remind them again."])
    assert _reminder_hits(["If no response arrives, remind the owner about the archive prompt."])
    assert not _reminder_hits(["When the archive prompt goes unanswered, the session stays listed and nothing reminds the owner."])
    assert not _reminder_hits(["If the archive prompt is unanswered, never remind the owner."])
    # a negation sitting in an earlier clause does not govern a later weak word
    assert _reminder_hits(["If the owner has not answered the archive prompt, ask again."])
    # two weak words: only the first is negated, so the second still hits
    assert _reminder_hits(["There is no archive prompt still waiting, but the other is unanswered."])
    # a negation in the same clause as the weak word governs it (no reminder verb on these lines)
    assert not _reminder_hits(["There is no archive prompt still waiting."])
    assert not _reminder_hits(["Nothing reminds the owner about an unanswered archive prompt."])


def test_no_reminder_about_an_unanswered_archive_prompt():
    hits = []
    for rel, path in _shipped((".md", ".py")):
        hits.extend((rel, line) for line in _reminder_hits(_read(path).split("\n")))
    assert hits == [], hits


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
    base = subprocess.run(
        ["git", "-C", _REPO, "show", f"{_BASE}:plugins/superheroes/{_OWNER_DECISIONS}"],
        capture_output=True,
        text=True,
    )
    assert base.returncode == 0, f"cannot read {_OWNER_DECISIONS} at {_BASE}: {base.stderr}"
    base_block = _duties_block(base.stdout, _BASE_DUTIES_LABEL)
    # Duty 4 changed once on purpose when the forward-share dial and its folded-in list were retired; it is
    # pinned to that text, and every other duty must still read as it did at the base.
    assert _without_item(first_seven, 4) == _without_item(base_block, 4), "duties 1 to 3 or 5 to 7 changed"
    assert _item(first_seven, 4) == _DUTY_4, "duty 4 changed"


_DUTY_4 = [
    "4. **Record the decisions-asked count** for the window. List the window's declines with their",
    "   triggers, one per line.",
]


def _item(block, number):
    """The lines of top-level numbered item ``number`` in ``block``."""
    spans = _numbered_items(block) + [(None, len(block))]
    for (n, start), (_, end) in zip(spans, spans[1:]):
        if n == number:
            return block[start:end]
    raise AssertionError(f"item {number} not found")


def _without_item(block, number):
    item = _item(block, number)
    start = block.index(item[0])
    return block[:start] + block[start + len(item):]


# A bite-proof record quotes what it neutralized, so it may name the retired label.
_BITE_PROOFS = os.path.join(_TESTS, "bite_proofs")
_SKIPPED_DIRS = ("__pycache__", ".git", "node_modules")


def _scanned_for_the_old_label():
    """Every .md and .py file under the plugins directory that the old-label scan reads."""
    paths = []
    for root, dirs, files in os.walk(_PLUGINS):
        dirs[:] = [
            d
            for d in dirs
            if d not in _SKIPPED_DIRS and os.path.join(root, d) != _BITE_PROOFS
        ]
        paths.extend(os.path.join(root, name) for name in files if name.endswith((".md", ".py")))
    return paths


def test_the_old_label_appears_nowhere_under_plugins():
    old = "The seven" + " duties"  # split so this file does not name it
    paths = _scanned_for_the_old_label()
    named = [os.path.relpath(path, _PLUGINS) for path in paths if old in _read(path)]
    assert paths, "no files scanned; the plugins directory did not resolve"
    assert named == [], named


def test_the_old_label_scan_skips_the_bite_proof_records():
    # axis: the scan's walk leaves out lib/tests/bite_proofs only, by path — see bite-proof record c8c_wo_c.md
    assert any(n.endswith(".md") for n in os.listdir(_BITE_PROOFS)), "no records to skip"
    paths = [os.path.abspath(path) for path in _scanned_for_the_old_label()]
    under = [p for p in paths if os.path.commonpath([p, _BITE_PROOFS]) == _BITE_PROOFS]
    assert under == [], under
    assert os.path.abspath(__file__) in paths, "the scan no longer reads the rest of lib/tests"


def test_gardening_record_lists_the_reviewer_pass_line():
    text = _read(os.path.join(_PLUGIN, _OWNER_DECISIONS))
    match = re.search(r"^## The gardening record\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, "the gardening record section was not found"
    bullets = [line for line in match.group(1).split("\n") if line.startswith("- ")]
    reviewer = [b for b in bullets if "reviewer-pass line" in b]
    assert len(reviewer) == 1, reviewer
    assert "duty 8" in reviewer[0] and "Renew now" in reviewer[0]


_PROCEDURE_STEP = "cloud_cleanup.py plan --repo-root"


def test_cleanup_procedure_has_one_home_and_the_others_point_to_it():
    merge_train = _read(os.path.join(_PLUGIN, _MERGE_TRAIN)).split("\n")
    assert merge_train.count(_HOME_HEADING) == 1
    assert _PROCEDURE_STEP in _collapsed(os.path.join(_PLUGIN, _MERGE_TRAIN))
    pointer = "merge-train.md` § Cleaning up a finished cloud lane"
    for rel in (_SKILL, _WAVE_WATCH):
        assert pointer in _collapsed(os.path.join(_PLUGIN, rel)), rel
    elsewhere = [
        (rel, what)
        for rel, path in _shipped((".md",))
        if rel != _MERGE_TRAIN
        for what, found in (
            ("heading", _HOME_HEADING in _read(path).split("\n")),
            ("procedure step", _PROCEDURE_STEP in _collapsed(path)),
        )
        if found
    ]
    assert elsewhere == [], elsewhere


def test_builder_side_of_the_archive_request():
    text = _read(os.path.join(_PLUGIN, _CLOUD))
    heading = cloud_cleanup.ARCHIVE_HEADING
    for archive_text in (cloud_cleanup.ARCHIVE_TEXT_MERGED, cloud_cleanup.ARCHIVE_TEXT_CLOSED):
        # the request names the builder's section and restates none of its procedure
        assert f'Follow the section "{heading}" in your cloud build reference.' in archive_text
        assert "session tool" not in archive_text
    assert text.split("\n").count(f"## {heading}") == 1
    assert f"- [{heading}](#when-the-advisor-asks-you-to-archive-your-session)" in text.split("# Building")[0]

    match = re.search(r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, "the archive-request section was not found"
    assert match.group(1).strip(), "the archive-request section is empty"


def _added_lines(rel):
    commit = subprocess.run(["git", "-C", _REPO, "cat-file", "-e", f"{_BASE}^{{commit}}"], capture_output=True)
    assert commit.returncode == 0, f"the base commit {_BASE} is not in this repository"
    present = subprocess.run(["git", "-C", _REPO, "cat-file", "-e", f"{_BASE}:plugins/superheroes/{rel}"], capture_output=True)
    if present.returncode != 0:  # the file is new since the base, so every line of it is added
        return _read(os.path.join(_PLUGIN, rel)).split("\n")
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
