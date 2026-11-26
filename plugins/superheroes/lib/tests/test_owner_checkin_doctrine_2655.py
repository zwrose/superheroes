"""Structure guards for the advisor's owner check-in home.

The check-in's cadence, the note's shape and the watch ceiling live in one home, the
`## Owner check-in while lanes run` section of `skills/showrunner/reference/orchestration.md`.
These tests pin structure only, never the home's sentences (`rubric/review-discipline.md`
§ The pin rule): the home heading exists once as a real heading outside any code fence, the
page's `# Contents` lists it, and the charter's duty 9 and showrunner-resume Step 6 cite it.

Bites on: the home heading renamed, removed, duplicated or hidden in a code fence; the
Contents entry or its anchor dropped; the charter's duty 9 or resume Step 6 losing its
citation of the home.

**Residual blind spots:** the home's own wording is not checked (the vet reads it); a
citation that names the home but no longer says what to do with it passes.
"""
import os
import re

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SKILLS = os.path.join(_PLUGIN, "skills")
_ORCHESTRATION = os.path.join(_SKILLS, "showrunner", "reference", "orchestration.md")
_CHARTER = os.path.join(_SKILLS, "showrunner", "SKILL.md")
_RESUME = os.path.join(_SKILLS, "showrunner-resume", "SKILL.md")

_HOME_TITLE = "Owner check-in while lanes run"
_HOME_ANCHOR = "#owner-check-in-while-lanes-run"
_CITATION = f"skills/showrunner/reference/orchestration.md` § {_HOME_TITLE}"


def _read(path):
    # Strict decoding on purpose: a file that cannot be read fails the test, never passes it.
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _headings_outside_fences(text):
    """(level, title) for every ATX heading line that is not inside a fenced code block."""
    found, fence = [], None
    for line in text.split("\n"):
        stripped = line.lstrip()
        marker = re.match(r"(`{3,}|~{3,})", stripped)
        if marker:
            if fence is None:
                fence = marker.group(1)[0] * 3
            elif stripped.startswith(fence):
                fence = None
            continue
        if fence is None:
            heading = re.match(r"(#{1,6}) +(.*?)\s*$", line)
            if heading:
                found.append((len(heading.group(1)), heading.group(2)))
    return found


def _block(path, start_pattern, end_pattern):
    """The collapsed text from the line matching ``start_pattern`` up to the line matching ``end_pattern``."""
    found = re.findall(start_pattern + r".*?(?=" + end_pattern + r")", _read(path), re.MULTILINE | re.DOTALL)
    assert len(found) == 1, f"{os.path.basename(path)}: block {start_pattern!r} found {len(found)} times"
    return " ".join(found[0].split())


def test_home_heading_exists_once():
    # axis: the one home is a real level-2 heading, once, outside any code fence
    headings = _headings_outside_fences(_read(_ORCHESTRATION))
    assert headings.count((2, _HOME_TITLE)) == 1, f"orchestration.md must carry '## {_HOME_TITLE}' once"


def test_contents_lists_home():
    # axis: the page's Contents block links the home's anchor
    contents = re.findall(r"\A# Contents\n(.*?)(?=^# )", _read(_ORCHESTRATION), re.MULTILINE | re.DOTALL)
    assert len(contents) == 1, "orchestration.md # Contents block not found"
    assert f"[{_HOME_TITLE}]({_HOME_ANCHOR})" in contents[0], "orchestration.md # Contents lacks the home's entry"


def test_charter_duty_9_cites_home():
    # axis: the charter's duty 9 points at the home
    duty_9 = _block(_CHARTER, r"^9\. \*\*Orchestration", r"^10\. ")
    assert _CITATION in duty_9, "showrunner SKILL.md duty 9 does not cite the check-in home"


def test_resume_step_6_cites_home():
    # axis: showrunner-resume Step 6, where watches are re-armed, points at the home
    step_6 = _block(_RESUME, r"^## Step 6", r"^## Step 7")
    assert _CITATION in step_6, "showrunner-resume SKILL.md Step 6 does not cite the check-in home"
