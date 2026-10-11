"""Census of the cloud setup sitting's skill text.

The sitting's text never tells the advisor to ask the owner to type, copy or paste an environment
id, and it never starts a check session, makes a pass block or judges a check without naming the id
that the reader's picked result returned.
"""
import os
import re

PLUGIN_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SET_UP = os.path.join("skills", "configure", "reference", "set-up.md")
CONFIGURE_SKILL = os.path.join("skills", "configure", "SKILL.md")
SHOWRUNNER_SKILL = os.path.join("skills", "showrunner", "SKILL.md")

ROUTE_LINE = ("`${CLAUDE_PLUGIN_ROOT}/skills/configure/reference/set-up.md` § 6, "
              "whichever path the project routed to.")
POINTER = "skills/configure/reference/set-up.md` § 6"


def _read(rel):
    with open(os.path.join(PLUGIN_ROOT, rel), encoding="utf-8") as handle:
        return handle.read()


def _section_six():
    lines = _read(SET_UP).splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("## 6 — Cloud builds")), None)
    if start is None:
        return []
    out = [lines[start]]
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        out.append(line)
    return out


def _first(lines, needle):
    for i, line in enumerate(lines):
        if needle in line:
            return i
    return None


def _sentences(lines):
    text = "\n".join(lines)
    return [s for s in re.split(r"\. |\.\n|:\s|\n\s*\n", text) if s.strip()]


def test_section_six_exists():
    section = _section_six()
    assert section, "set-up.md has no line starting '## 6 — Cloud builds'"
    assert any(line.strip() for line in section[1:]), "section 6 of set-up.md is empty"


def test_section_never_asks_for_a_typed_or_pasted_id():
    section = _section_six()
    assert section, "section 6 of set-up.md was not found"
    ask = re.compile(r"\b(type|typed|paste|pasted|copy|copied)\b", re.IGNORECASE)
    ident = re.compile(r"\bids?\b", re.IGNORECASE)
    for sentence in _sentences(section):
        if ask.search(sentence) and ident.search(sentence) and "never" not in sentence.lower():
            raise AssertionError("sentence asks for a typed, copied or pasted id without "
                                 "'never': %r" % sentence.strip())


def test_every_check_command_names_the_picked_id():
    section = _section_six()
    assert section, "section 6 of set-up.md was not found"
    needles = ('cloud_check.py" start', 'cloud_check.py" judge', 'cloud_pass.py" make')
    seen = {needle: 0 for needle in needles}
    for line in section:
        for needle in needles:
            if needle in line:
                seen[needle] += 1
                assert "--environment <id>" in line, (
                    "command line does not name '--environment <id>': %r" % line)
    for needle, count in seen.items():
        assert count >= 1, "section 6 has no line containing %r" % needle


def test_the_pick_is_read_before_and_after_and_before_the_check():
    section = _section_six()
    assert section, "section 6 of set-up.md was not found"
    order = ['cloud_environment.py" snapshot', 'cloud_check.py" setup-message',
             'cloud_environment.py" pick --cwd . --before', 'cloud_pass.py" make',
             'cloud_check.py" start']
    found = [(needle, _first(section, needle)) for needle in order]
    for needle, index in found:
        assert index is not None, "section 6 has no line containing %r" % needle
    for (earlier, i), (later, j) in zip(found, found[1:]):
        assert i < j, "line %r (%d) does not come before line %r (%d)" % (earlier, i, later, j)
    retry = [line for line in section
             if 'cloud_environment.py" pick' in line and "--before" in line and "--confirmed" in line]
    assert retry, "section 6 has no retry pick line carrying --before and --confirmed"
    sign_in = _first(section, 'cloud_check.py" sign-in')
    assert sign_in is not None, "section 6 has no line containing 'cloud_check.py\" sign-in'"
    make = _first(section, 'cloud_pass.py" make')
    assert sign_in < make, "the sign-in line (%d) does not come before the pass command (%d)" % (
        sign_in, make)


def test_configure_routes_cloud_setup_to_section_six():
    lines = _read(CONFIGURE_SKILL).splitlines()
    assert ROUTE_LINE in lines, "configure/SKILL.md has no line %r" % ROUTE_LINE


def test_showrunner_has_one_pointer_to_section_six():
    hits = [line for line in _read(SHOWRUNNER_SKILL).splitlines() if POINTER in line]
    assert len(hits) == 1, "showrunner/SKILL.md has %d lines pointing to set-up.md § 6: %r" % (
        len(hits), hits)
