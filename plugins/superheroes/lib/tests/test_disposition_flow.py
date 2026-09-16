"""Cross-doc disposition-flow structural guards (issue #1113).

Enforces: pinned section headings; retired vocabulary and owner-rejected terms absent;
retired tier vocabulary absent from a closed three-file enumeration of shipped doctrine surfaces;
registry marker home;
discuss-open-decisions cites the owner-decisions canonical home path.
"""
# What this file guards and does not guard (issue #1113).
#
# Every assertion rests on a MECHANICAL fact: a pinned heading string present,
# a literal absent, a file-path citation present, or a registry marker confined
# to its home.
#
# Prose MEANING, Contents parity, table shape, and ordering beyond presence are
# guarded by review, not by CI. No negation heuristics, no paragraph heuristics,
# no structural parsers beyond heading-line membership checks.
# The retired tier vocabulary census uses a closed three-file enumeration — no tree walk.
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_OWNER_DECISIONS = "skills/showrunner/reference/owner-decisions.md"
_SHOWRUNNER_CHARTER = "skills/showrunner/SKILL.md"
_REVIEW_DISCIPLINE = "rubric/review-discipline.md"
_VET_RECEIPT = "skills/showrunner/reference/vet-receipt.md"
_DISCUSS_OPEN = "skills/discuss-open-decisions/SKILL.md"
_ISSUE_CONTRACT = "skills/showrunner/reference/issue-contract.md"

_REGISTRY_MARKER = "<!-- superheroes:revisit-registry -->"

_RETIRED_LITERAL = "Follow-up economics"

_RETIRED_TIER_LITERALS = (
    "Tier 1",
    "Tier 2",
    "Tier-1",
    "Tier-2",
)

_OWNER_REJECTED_LITERALS = ("knob-polish",)

_TOUCHED_FILES = (
    _OWNER_DECISIONS,
    _SHOWRUNNER_CHARTER,
    _REVIEW_DISCIPLINE,
    _VET_RECEIPT,
    _DISCUSS_OPEN,
)

_RETIRED_VOCAB_FILES = (
    _OWNER_DECISIONS,
    _DISCUSS_OPEN,
    _SHOWRUNNER_CHARTER,
    _VET_RECEIPT,
)

# The shipped surfaces whose routing vocabulary this change migrates. Closed by construction:
# a surface joins this tuple in the same change that renames its text, never before.
_RETIRED_TIER_VOCAB_FILES = (
    _ISSUE_CONTRACT,
    _SHOWRUNNER_CHARTER,
    _VET_RECEIPT,
)

_PINNED_OWNER_DECISIONS_HEADINGS = (
    "## The revisit-trigger registry",
)

_PINNED_REVIEW_DISCIPLINE_HEADINGS = (
    "### Continuation and the advisor-resolution valve",
    "### Standing authorization — venue-1 folds",
)


def _read_plugin(rel):
    path = rel if os.path.isabs(rel) else os.path.join(_PLUGIN_ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _expect_error(fn, exc_type, *, match):
    exc_name = exc_type.__name__
    try:
        fn()
    except exc_type as exc:
        if not re.search(match, str(exc)):
            raise AssertionError(
                "detector raised %s but message %r does not match %r"
                % (exc_name, str(exc), match)
            ) from None
        return exc
    except BaseException as exc:  # noqa: BLE001
        raise AssertionError(
            "detector did not bite: expected %s, got %s: %s"
            % (exc_name, type(exc).__name__, exc)
        ) from None
    raise AssertionError("detector did not bite: no exception raised")


def _expect_assertion_error(fn, *, match):
    return _expect_error(fn, AssertionError, match=match)


def _assert_pinned_headings_present(texts=None):
    if texts is None:
        texts = {
            _OWNER_DECISIONS: _read_plugin(_OWNER_DECISIONS),
            _REVIEW_DISCIPLINE: _read_plugin(_REVIEW_DISCIPLINE),
        }
    owner_lines = set(texts[_OWNER_DECISIONS].splitlines())
    for heading in _PINNED_OWNER_DECISIONS_HEADINGS:
        if heading not in owner_lines:
            raise AssertionError(
                "%s: pinned heading missing: %r" % (_OWNER_DECISIONS, heading)
            )
    review_lines = set(texts[_REVIEW_DISCIPLINE].splitlines())
    for heading in _PINNED_REVIEW_DISCIPLINE_HEADINGS:
        if heading not in review_lines:
            raise AssertionError(
                "%s: pinned heading missing: %r" % (_REVIEW_DISCIPLINE, heading)
            )


def _assert_retired_vocabulary_absent(texts=None):
    if texts is None:
        texts = {rel: _read_plugin(rel) for rel in _RETIRED_VOCAB_FILES}
    for rel in _RETIRED_VOCAB_FILES:
        if _RETIRED_LITERAL in texts[rel]:
            raise AssertionError("%s: retired literal %r present" % (rel, _RETIRED_LITERAL))


def _assert_retired_tier_literals_absent(texts=None):
    if texts is None:
        texts = {rel: _read_plugin(rel) for rel in _RETIRED_TIER_VOCAB_FILES}
    for rel in _RETIRED_TIER_VOCAB_FILES:
        text = texts[rel]
        for literal in _RETIRED_TIER_LITERALS:
            if literal in text:
                raise AssertionError(
                    "%s: retired tier literal %r present" % (rel, literal)
                )


def _assert_discuss_open_holder_pins(texts=None):
    if texts is None:
        texts = {_DISCUSS_OPEN: _read_plugin(_DISCUSS_OPEN)}
    text = texts[_DISCUSS_OPEN]
    if _OWNER_DECISIONS not in text:
        raise AssertionError(
            "%s: canonical home %r not cited" % (_DISCUSS_OPEN, _OWNER_DECISIONS)
        )


def _assert_owner_rejected_terms_absent(texts=None):
    if texts is None:
        texts = {rel: _read_plugin(rel) for rel in _TOUCHED_FILES}
    for rel in _TOUCHED_FILES:
        text = texts[rel]
        for literal in _OWNER_REJECTED_LITERALS:
            if literal in text:
                raise AssertionError(
                    "%s: owner-rejected literal %r present" % (rel, literal)
                )


def _assert_registry_marker_home(texts=None):
    if texts is None:
        texts = {rel: _read_plugin(rel) for rel in _TOUCHED_FILES}
    if _REGISTRY_MARKER not in texts[_OWNER_DECISIONS]:
        raise AssertionError(
            "%s: registry marker %r missing from home" % (_OWNER_DECISIONS, _REGISTRY_MARKER)
        )
    for rel in _TOUCHED_FILES:
        if rel == _OWNER_DECISIONS:
            continue
        if _REGISTRY_MARKER in texts[rel]:
            raise AssertionError(
                "%s: registry marker %r present outside home" % (rel, _REGISTRY_MARKER)
            )
    # Owner-ruled fold 2026-08-24 (collector item 72): LEDGERS.md joins the outside-home
    # census. It lives at the repo root (not under the plugin), walks the registry at the
    # orientation review, and must reference — never restate — the marker's home.
    ledgers_path = os.path.normpath(os.path.join(_PLUGIN_ROOT, "..", "..", "LEDGERS.md"))
    if os.path.isfile(ledgers_path):
        with open(ledgers_path, encoding="utf-8") as fh:
            if _REGISTRY_MARKER in fh.read():
                raise AssertionError(
                    "LEDGERS.md: registry marker %r present outside home" % _REGISTRY_MARKER
                )


# --- Primary detectors ---------------------------------------------------------


def test_new_section_headings_present():
    _assert_pinned_headings_present()


def test_retired_vocabulary_is_gone():
    _assert_retired_vocabulary_absent()


def test_retired_tier_literals_absent():
    _assert_retired_tier_literals_absent()


def test_discuss_open_holder_pins():
    _assert_discuss_open_holder_pins()


def test_owner_rejected_terms_absent():
    _assert_owner_rejected_terms_absent()


def test_registry_marker_has_exactly_one_home():
    _assert_registry_marker_home()


# --- Bite-proofs (synthetic strings; no repo mutation) ------------------------


def test_negative_pinned_heading_renamed():
    synthetic = "## The revisit-trigger registry (old)"
    review_disc = "\n".join(_PINNED_REVIEW_DISCIPLINE_HEADINGS)
    texts = {_OWNER_DECISIONS: synthetic, _REVIEW_DISCIPLINE: review_disc}
    _expect_assertion_error(
        lambda: _assert_pinned_headings_present(texts),
        match=r"owner-decisions\.md: pinned heading missing: '## The revisit-trigger registry'",
    )


def test_negative_retired_vocabulary_inserted():
    texts = {rel: "" for rel in _RETIRED_VOCAB_FILES}
    texts[_OWNER_DECISIONS] = _RETIRED_LITERAL
    _expect_assertion_error(
        lambda: _assert_retired_vocabulary_absent(texts),
        match="retired literal",
    )


def test_negative_retired_tier_literal_inserted():
    texts = {rel: "" for rel in _RETIRED_TIER_VOCAB_FILES}
    texts[_VET_RECEIPT] = "Every Tier 2 item is appended to the collector."
    _expect_assertion_error(
        lambda: _assert_retired_tier_literals_absent(texts),
        match=r"vet-receipt\.md: retired tier literal 'Tier 2' present",
    )


def test_negative_owner_rejected_literal_inserted():
    texts = {rel: "" for rel in _TOUCHED_FILES}
    texts[_REVIEW_DISCIPLINE] = "A knob-polish pass."
    _expect_assertion_error(
        lambda: _assert_owner_rejected_terms_absent(texts),
        match="owner-rejected literal 'knob-polish' present",
    )


def test_negative_discuss_open_missing_home():
    texts = {
        _DISCUSS_OPEN: "See skills/showrunner/SKILL.md instead.",
    }
    _expect_assertion_error(
        lambda: _assert_discuss_open_holder_pins(texts),
        match="canonical home .* not cited",
    )


def test_negative_registry_marker_outside_home():
    texts = {rel: "" for rel in _TOUCHED_FILES}
    texts[_OWNER_DECISIONS] = _REGISTRY_MARKER
    texts[_VET_RECEIPT] = _REGISTRY_MARKER
    _expect_assertion_error(
        lambda: _assert_registry_marker_home(texts),
        match="registry marker .* present outside home",
    )
