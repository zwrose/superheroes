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
    split = re.compile(r",\s*(?:and|but|or)\s+|;\s*|\s+—\s+")
    for sentence in _sentences(section):
        for clause in split.split(sentence):
            if ask.search(clause) and ident.search(clause) and "never" not in clause.lower():
                raise AssertionError("clause asks for a typed, copied or pasted id without "
                                     "'never': %r" % clause.strip())


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
    # axis: the plain after-read line must name cloud_environment.py, not only end like the read — see bite-proof record wo_b_1771_setup_sitting_text.md
    plain_end = 'pick --cwd . --before <the value step 1 kept>'
    plain_name = 'cloud_environment.py" pick'
    plain_label = 'a plain after-read line naming %r and ending %r' % (plain_name, plain_end)
    plain = next((i for i, line in enumerate(section)
                  if plain_name in line and line.strip().endswith(plain_end)), None)
    found = [('cloud_environment.py" snapshot', _first(section, 'cloud_environment.py" snapshot')),
             ('cloud_check.py" setup-message', _first(section, 'cloud_check.py" setup-message')),
             (plain_label, plain),
             ('cloud_pass.py" make', _first(section, 'cloud_pass.py" make')),
             ('cloud_check.py" start', _first(section, 'cloud_check.py" start'))]
    for needle, index in found:
        assert index is not None, "section 6 has no line containing %r" % needle
    for (earlier, i), (later, j) in zip(found, found[1:]):
        assert i < j, "line %r (%d) does not come before line %r (%d)" % (earlier, i, later, j)
    confirm_needle = '--before <the value step 1 kept> --confirmed <the value step 1 kept>'
    confirm = _first(section, confirm_needle)
    assert confirm is not None, "section 6 has no line containing %r" % confirm_needle
    assert plain < confirm, "the plain after-read (%d) does not come before the confirm-by-name line (%d)" % (
        plain, confirm)
    recovery_needle = ('cloud_environment.py" pick --cwd . --before <the snapshot value> '
                       '--confirmed <the environment now in use>')
    recovery = _first(section, recovery_needle)
    assert recovery is not None, "section 6 has no line containing %r" % recovery_needle
    judge = _first(section, 'cloud_check.py" judge')
    assert judge is not None, "section 6 has no line containing 'cloud_check.py\" judge'"
    assert judge < recovery, "the recovery pick line (%d) does not come after the judge line (%d)" % (
        recovery, judge)
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


def test_first_pick_unchanged_is_confirmed_by_name_in_step_three():
    section = _section_six()
    assert section, "section 6 of set-up.md was not found"
    needle = ('cloud_environment.py" pick --cwd . --before <the value step 1 kept> '
              '--confirmed <the value step 1 kept>')
    confirm = _first(section, needle)
    assert confirm is not None, "section 6 has no line containing %r" % needle
    make = _first(section, 'cloud_pass.py" make')
    assert make is not None, "section 6 has no line containing 'cloud_pass.py\" make'"
    assert confirm < make, "the confirm-by-name line (%d) does not come before the pass command (%d)" % (
        confirm, make)


def test_the_id_is_compared_with_the_picker_before_each_step_that_uses_it():
    section = _section_six()
    assert section, "section 6 of set-up.md was not found"
    needle = 'cloud_environment.py" compare --environment <id>'
    compares = [i for i, line in enumerate(section) if needle in line]
    for step in ('cloud_pass.py" make', 'cloud_check.py" start', 'cloud_check.py" judge'):
        first = _first(section, step)
        assert first is not None, "section 6 has no line containing %r" % step
        assert any(c < first for c in compares), "no %r line comes before the first %r line" % (
            needle, step)
        assert sum(1 for c in compares if c < first) >= 1
    marks = [_first(section, step) for step in
             ('cloud_pass.py" make', 'cloud_check.py" start', 'cloud_check.py" judge')]
    assert len([c for c in compares if c < marks[0]]) >= 1
    assert len([c for c in compares if marks[0] < c < marks[1]]) >= 1, "no compare between pass and start"
    assert len([c for c in compares if marks[1] < c < marks[2]]) >= 1, "no compare between start and judge"


def test_no_compare_line_comes_after_the_last_judge_line():
    section = _section_six()
    assert section, "section 6 of set-up.md was not found"
    judges = [i for i, line in enumerate(section) if 'cloud_check.py" judge' in line]
    assert judges, "section 6 has no line containing 'cloud_check.py\" judge'"
    late = [i for i, line in enumerate(section)
            if 'cloud_environment.py" compare' in line and i > judges[-1]]
    assert not late, "compare line(s) %r come after the last judge line (%d)" % (late, judges[-1])


def test_check_helper_commands_pass_no_relative_working_directory():
    section = _section_six()
    for line in section:
        if 'cloud_check.py"' in line:
            assert "--cwd" not in line, "cloud_check command passes --cwd: %r" % line
