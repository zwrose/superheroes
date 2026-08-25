"""Drift guard for the safety-machinery route doctrine (#1154).

Bites on: the ruled carve-out text in its two prose homes — ``rubric/review-discipline.md``
§ *The safety-machinery route — the guard refuses the fixer* (doctrine home) and
``skills/review-code/reference/auto-fix-loop.md`` (copy-holder pointer). Losing the carve-out or
reintroducing the retired pre-authorization rule must go red.

**Residual blind spots:**

- the clause roster is **hand-maintained**;
- the pin grades the **doctrine text and the gate's wiring**, never whether any build actually
  obeyed the route;
- clause matching is substring-based, so a clause could be present inside prose that negates it.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))

_HOME = "rubric/review-discipline.md"
_COPY_HOLDER = "skills/review-code/reference/auto-fix-loop.md"
_ROUTE_SECTION = "### The safety-machinery route — the guard refuses the fixer"

# Retired pre-authorization rule — absence in both homes (substring 3: copy-holder whole file only).
_RETIRED_BOTH_FILES = (
    "Owner authorization is required when the findings are blocking",
    "owner's word comes **before** the ordered round",
    "When authorization is unavailable, park",
)
_RETIRED_COPY_HOLDER_ONLY = (
    "the owner authorization a blocking finding needs first",
)

_CARVEOUT_CLAUSES = (
    "**Blocking findings go out on advisor or builder authority.**",
    "on the advisor's or the builder's own authority",
    "the owner's mandatory touchpoint is the merge click",
    "loud disclosure",
    "the work order says the round touches safety machinery and names the files",
    "**The one exception — the owner-authority-gate family.**",
    "still needs the owner's word first, per change",
    "**Classification fails closed.**",
    "A surface you cannot confidently classify is treated as gate family",
    "which means it parks",
    "because the guard refuses the fixer at every severity",
    "**When the owner's word is unavailable at the gate family, park.**",
    "Outside the gate family there is nothing to wait for",
    "**This is not the runtime self-modification floor.**",
    "do not overlap",
)

_POINTER_START = "**Where those findings go next.**"
_POINTER_CLAUSES = (
    "ordered implementer work orders on advisor or builder authority",
    "the owner's word required only for the owner-authority-gate family",
    "rubric/review-discipline.md",
    "do not retry the fixer, and never narrow the guard",
)


def _read(rel):
    path = os.path.join(PLUGIN, rel)
    if not os.path.isfile(path):
        raise AssertionError(f"surface file missing or unreadable: {rel}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _collapse_whitespace(text):
    return re.sub(r"\s+", " ", text)


def _heading_level(line):
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    match = re.match(r"^(#+)\s", stripped)
    return len(match.group(1)) if match else None


def _section_span(lines, heading, label):
    indices = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(indices) != 1:
        raise AssertionError(
            f"{label}: expected exactly one {heading!r} line, found {len(indices)}"
        )
    start = indices[0]
    start_level = _heading_level(lines[start])
    end = len(lines)
    for i in range(start + 1, len(lines)):
        level = _heading_level(lines[i])
        if level is not None and level <= start_level:
            end = i
            break
    return start, end


def _route_section_text():
    text = _read(_HOME)
    lines = text.splitlines()
    start, end = _section_span(lines, _ROUTE_SECTION, _HOME)
    section = "\n".join(lines[start:end])
    assert section.strip(), (
        f"{_HOME}: extracted safety-machinery section is empty — "
        "section extractor would vacuously pass absence legs"
    )
    return section


def _pointer_paragraph_text():
    text = _read(_COPY_HOLDER)
    start = text.find(_POINTER_START)
    assert start != -1, (
        f"{_COPY_HOLDER}: pointer paragraph start {_POINTER_START!r} not found"
    )
    rest = text[start:]
    end = rest.find("\n\n")
    paragraph = rest if end == -1 else rest[:end]
    assert paragraph.strip(), f"{_COPY_HOLDER}: extracted pointer paragraph is empty"
    return paragraph


def test_retired_preauthorization_rule_is_absent():
    home_text = _read(_HOME)
    copy_text = _read(_COPY_HOLDER)
    for substring in _RETIRED_BOTH_FILES:
        if substring in home_text:
            raise AssertionError(
                f"{_HOME}: retired rule substring must be absent, found: {substring!r}"
            )
        if substring in copy_text:
            raise AssertionError(
                f"{_COPY_HOLDER}: retired rule substring must be absent, found: {substring!r}"
            )
    for substring in _RETIRED_COPY_HOLDER_ONLY:
        if substring in copy_text:
            raise AssertionError(
                f"{_COPY_HOLDER}: retired rule substring must be absent, found: {substring!r}"
            )


def test_carveout_clauses_present_in_doctrine_home():
    section = _collapse_whitespace(_route_section_text())
    for clause in _CARVEOUT_CLAUSES:
        assert clause in section, (
            f"{_HOME} (section {_ROUTE_SECTION}): missing carve-out clause: {clause!r}"
        )


def test_copyholder_pointer_states_the_new_shape():
    paragraph = _pointer_paragraph_text()
    for clause in _POINTER_CLAUSES:
        assert clause in paragraph, (
            f"{_COPY_HOLDER} (pointer paragraph): missing clause: {clause!r}"
        )
