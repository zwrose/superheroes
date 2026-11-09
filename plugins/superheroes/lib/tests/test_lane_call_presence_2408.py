"""Tests for the doctrine that the lane call needs no owner present (#2408).

Bites on: showrunner duty 3 losing the downgrade gate ("per change", "Disclosure alone never authorizes a
downgrade"), the micro section losing its per-change authorization, duty 9 losing the owner-capability
precondition at dispatch, duty 3 losing the "at any hour" lane call or the sentence naming the three things that
keep the owner's word, the single reviewer's availability check going back to waiting for the owner,
review-discipline.md losing the advisor's own kickoff check or the same-family reviewer's owner word; and any
shipped doctrine page (every `*.md` under the plugin except `eval/`, `evals/`, `lib/tests/`, CHANGELOG.md and
TRANSITION.md) that puts an owner-presence phrase and a lane-call phrase in one paragraph.

**Residual blind spots:** the census is a phrase-pairing search per paragraph, so a presence requirement worded
without any of the presence phrases (for example "wait until the owner returns") passes, and a paragraph that says
presence is *not* needed while using a presence phrase is flagged (doctrine should avoid that wording). A new
genuine owner-presence rule in lane-call context needs an `_EXEMPT_PHRASES` entry with its reason. The gate tests
are phrase searches over the collapsed text, so a section that keeps the phrase but contradicts it in the next
sentence passes.
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN = os.path.abspath(os.path.join(_HERE, "..", ".."))
_SHOWRUNNER = os.path.join(_PLUGIN, "skills", "showrunner", "SKILL.md")
_REVIEW_DISCIPLINE = os.path.join(_PLUGIN, "rubric", "review-discipline.md")

_PRESENCE = re.compile(r"owner(?:-| is | )present|owner's presence", re.I)
_LANE_CONTEXT = re.compile(
    r"lane call|call the lane|calls? full or light|kickoff|reviewer's availability|presentation call", re.I
)
# The micro route's test: micro authorization is the owner's per change, so its presence is genuinely the owner's
# (showrunner duty 3, the four-routes paragraph).
_EXEMPT_PHRASES = ("a tiny owner-present item",)
_EXCLUDED_TOP = {"eval", "evals"}
# Historical notes; TRANSITION quotes the retired clause on purpose.
_EXCLUDED_FILES = {"CHANGELOG.md", "TRANSITION.md"}
_EXCLUDED_TESTS_DIR = os.path.join("lib", "tests")


def _read(path):
    # Strict decoding on purpose: a file that cannot be read fails the test, never passes it.
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _norm(text):
    return " ".join(text.replace("**", "").split())


def _duty(n):
    text = _read(_SHOWRUNNER)
    start = re.search(r"^\s{0,1}%d\. \*\*" % n, text, re.MULTILINE)
    assert start, "duty %d was not found in showrunner SKILL.md" % n
    end = re.search(r"^\s{0,1}%d\. \*\*" % (n + 1), text[start.end():], re.MULTILINE)
    assert end, "duty %d has no following duty %d in showrunner SKILL.md" % (n, n + 1)
    return _norm(text[start.start(): start.end() + end.start()])


def _section(path, heading):
    match = re.search(
        r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", _read(path), re.MULTILINE | re.DOTALL
    )
    assert match, "the section %r was not found in %s" % (heading, os.path.basename(path))
    return _norm(match.group(1))


def _offending_paragraphs(text):
    found = []
    for paragraph in re.split(r"\n\s*\n", text):
        flat = _norm(paragraph)
        for phrase in _EXEMPT_PHRASES:
            flat = re.sub(re.escape(phrase), "", flat, flags=re.I)
        if _PRESENCE.search(flat) and _LANE_CONTEXT.search(flat):
            found.append(flat)
    return found


def _doctrine_pages():
    pages = []
    for root, dirs, files in os.walk(_PLUGIN):
        rel_root = os.path.relpath(root, _PLUGIN)
        if rel_root == ".":
            dirs[:] = [d for d in dirs if d not in _EXCLUDED_TOP]
        if rel_root == "lib":
            dirs[:] = [d for d in dirs if d != "tests"]
        if os.path.normpath(rel_root).startswith(_EXCLUDED_TESTS_DIR):
            continue
        for name in files:
            if not name.endswith(".md") or name in _EXCLUDED_FILES:
                continue
            pages.append(os.path.relpath(os.path.join(root, name), _PLUGIN))
    return sorted(pages)


def test_duty3_keeps_the_downgrade_gate_word_for_word():
    # axis: moving down a lane stays the owner's word, per change, and disclosure alone never authorizes it
    duty = _duty(3)
    assert "moving down a lane is never your call — it requires the owner, per change." in duty
    assert "Disclosure alone never authorizes a downgrade." in duty


def test_micro_keeps_its_per_change_owner_authorization():
    # axis: every micro change stays authorized by the owner on its own, with no standing grant
    section = _section(_SHOWRUNNER, "Micro — hard-line edit")
    assert "no standing grants; every micro change is authorized on its own" in section
    assert "owner-only, per change, never a standing grant" in section
    assert "every micro change (§ Micro — hard-line edit)" in _duty(3)


def test_owner_capability_stays_at_dispatch():
    # axis: owner-capability preconditions are still cleared with the owner at dispatch, and duty 3 names them
    assert (
        "Clear owner-capability preconditions at dispatch time — with the owner, before the session goes autonomous"
        in _duty(9)
    )
    assert "the owner-capability preconditions cleared at dispatch, such as sign-ins (duty 9)" in _duty(3)


def test_duty3_lane_call_is_made_at_any_hour_and_recorded_for_veto():
    # axis: the lane call and the presentation call are made without the owner and recorded for the owner's veto
    duty = _duty(3)
    assert "Call the lane when you mark the issue build-ready, at any hour, attended or not." in duty
    assert "record them for the owner's veto" in duty
    assert "None of these holds a lane call for the owner" in duty
    assert "with the owner present" not in duty


def test_reviewer_availability_is_the_advisors_check_at_kickoff():
    # axis: the single reviewer's availability is the advisor's own check, and a same-family reviewer keeps the owner's word
    duty = _duty(3)
    assert "Check the single reviewer's availability yourself at kickoff" in duty
    assert "never a wait for the owner" in duty
    discipline = _norm(_read(_REVIEW_DISCIPLINE))
    assert (
        "The advisor checks availability itself at kickoff, at any hour, and never holds the change waiting for the owner."
        in discipline
    )
    assert (
        "The owner's word comes first: when given, it admits the same-family reviewer for that change instead."
        in discipline
    )


def test_census_no_doctrine_page_ties_the_lane_call_to_owner_presence():
    # axis: no shipped doctrine page pairs an owner-presence phrase with lane-call context in one paragraph
    offenders = []
    for rel in _doctrine_pages():
        for paragraph in _offending_paragraphs(_read(os.path.join(_PLUGIN, rel))):
            offenders.append((rel, paragraph[:200]))
    assert not offenders, "owner presence tied to the lane call in:\n" + "\n".join(
        "%s: %s" % item for item in offenders
    )


def test_census_is_not_vacuous():
    # axis: the census walks the pages that carry the lane call and the theme, host and template pages
    pages = _doctrine_pages()
    for needed in (
        os.path.join("skills", "showrunner", "SKILL.md"),
        os.path.join("skills", "workhorse", "SKILL.md"),
        os.path.join("rubric", "review-discipline.md"),
        os.path.join("skills", "workhorse", "reference", "excuses.md"),
        os.path.join("skills", "showrunner", "reference", "routing.md"),
    ):
        assert needed in pages, "%s is missing from the census" % needed
    for top in ("theme", "hosts", "templates"):
        assert any(p.startswith(top + os.sep) for p in pages), "no page under %s/ in the census" % top
    assert len(pages) > 50, "only %d pages in the census" % len(pages)


def test_census_detector_fixtures():
    # axis: the paragraph detector flags the retired clause and split requirements, and spares the micro test and separate paragraphs
    assert _offending_paragraphs(
        "   **Call the lane when you mark the issue build-ready, with the owner present at kickoff.**"
    )
    assert _offending_paragraphs("Call the lane at kickoff.\nDo this with the owner present.")
    assert _offending_paragraphs("Check the single reviewer's availability while the owner is present.")
    assert not _offending_paragraphs(
        "a tiny owner-present item → `micro`, and the lane call attaches to the build-ready marking."
    )
    assert not _offending_paragraphs("The lane call is the advisor's.\n\nMicro runs with the owner present.")
