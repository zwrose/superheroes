"""Cross-doc disposition-flow structural guards (issue #1113).

Enforces: pinned owner-decisions section headings cited by live consumers;
retired vocabulary and owner-rejected terms absent;
retired tier vocabulary absent from shipped doctrine surfaces;
retired gate heading and phrase absent from shipped markdown minus closed exclusions;
registry marker home;
discuss-open-decisions cites the owner-decisions canonical home path and append-before-propose ordering.
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
# The retired tier vocabulary census walks _TIER_VOCAB_CENSUS_SURFACES minus
# _TIER_VOCAB_NOT_YET_MIGRATED (empty — every surface is censused).
# The retired gate census walks every shipped *.md under the plugin root minus
# _RETIRED_GATE_WALK_EXCLUSIONS: lib/tests/ (fixtures and bite-proof records)
# and CHANGELOG.md (generated release history).
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

_RETIRED_GATE_HEADING = "## The worth-it gate and the venue ladder"
_RETIRED_GATE_PHRASE = "worth-it gate"
_RETIRED_GATE_LITERALS = (
    _RETIRED_GATE_HEADING,
    _RETIRED_GATE_PHRASE,
)

_RETIRED_DOOR_GRADING_LITERALS = (
    "gate verdict",
)

_APPEND_BEFORE_PROPOSE_PINNED_CLAUSES = (
    "append it to the collector immediately",
    "every owner call is appended",
)

# Closed exclusion set for the retired-gate markdown walk — nothing else.
_RETIRED_GATE_WALK_EXCLUSIONS = (
    os.path.join("lib", "tests"),  # test fixtures and bite-proof records
    "CHANGELOG.md",  # generated release history
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

# Surfaces the module already reads for disposition-flow guards, plus issue-contract.
_TIER_VOCAB_CENSUS_SURFACES = _TOUCHED_FILES + (_ISSUE_CONTRACT,)

# Surfaces still on the retired tier names; empty — every census surface has migrated.
_TIER_VOCAB_NOT_YET_MIGRATED = ()

# Headings of owner-decisions.md cited by exact text in live shipped consumers.
_PINNED_OWNER_DECISIONS_HEADINGS = (
    "## The filter — what is the owner's, and on what grounds",
    "## The per-item spine",
    "## The front door",
    "## The venue ladder",
    "## The revisit-trigger registry",
    "## Delivery mechanics",
    "## Formatting — one block per spine section",
    "## Where the items come from, and the bound on that sweep",
    "## What batch-1 execution may and may not do",
    "## The collector preamble — canonical snippet",
)

_PINNED_REVIEW_DISCIPLINE_HEADINGS = (
    "### Continuation and the advisor-resolution valve",
    "### Standing authorization — venue-1 folds",
)


def _read_plugin(rel):
    path = rel if os.path.isabs(rel) else os.path.join(_PLUGIN_ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _normalize_prose(text):
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _assert_append_before_propose_ordering(text):
    # axis: each pinned ordering clause — not a document-wide single match.
    normalized = _normalize_prose(text)
    matched = 0
    for marker in _APPEND_BEFORE_PROPOSE_PINNED_CLAUSES:
        idx = normalized.find(marker)
        if idx == -1:
            continue
        proposed = "proposed in this session's delivery message"
        end = normalized.find(proposed, idx)
        if end == -1:
            continue
        end += len(proposed)
        clause = normalized[idx:end]
        if re.search(
            r"append(?:ed)?\b[^.]*?after\b[^.]*?proposed",
            clause,
        ):
            raise AssertionError(
                "%s: append-after-propose in pinned ordering clause"
                % _DISCUSS_OPEN
            )
        if not re.search(
            r"append(?:ed)?\b[^.]*?before\b[^.]*?proposed",
            clause,
        ):
            raise AssertionError(
                "%s: append-before-propose ordering missing in pinned clause"
                % _DISCUSS_OPEN
            )
        matched += 1
    if matched < len(_APPEND_BEFORE_PROPOSE_PINNED_CLAUSES):
        raise AssertionError(
            "%s: expected %d pinned append-before-propose clauses, found %d"
            % (
                _DISCUSS_OPEN,
                len(_APPEND_BEFORE_PROPOSE_PINNED_CLAUSES),
                matched,
            )
        )


def _retired_gate_walk_excluded(rel):
    rel_norm = rel.replace(os.sep, "/")
    if rel_norm == _RETIRED_GATE_WALK_EXCLUSIONS[1]:
        return True
    prefix = _RETIRED_GATE_WALK_EXCLUSIONS[0].replace(os.sep, "/") + "/"
    return rel_norm.startswith(prefix)


def _iter_shipped_markdown_files():
    for dirpath, _dirnames, filenames in os.walk(_PLUGIN_ROOT):
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            full = os.path.join(dirpath, filename)
            yield os.path.relpath(full, _PLUGIN_ROOT)


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
    # axis: presence of each pinned heading line in its own file — structure, never prose.
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
    # axis: presence of a retired tier literal in a census surface — never absence elsewhere;
    # coverage grows by construction as surfaces leave _TIER_VOCAB_NOT_YET_MIGRATED.
    if texts is None:
        texts = {rel: _read_plugin(rel) for rel in _TIER_VOCAB_CENSUS_SURFACES}
    for rel in _TIER_VOCAB_CENSUS_SURFACES:
        if rel in _TIER_VOCAB_NOT_YET_MIGRATED:
            continue
        text = texts[rel]
        for literal in _RETIRED_TIER_LITERALS:
            if literal in text:
                raise AssertionError(
                    "%s: retired tier literal %r present" % (rel, literal)
                )


def _assert_retired_gate_literals_absent(texts=None):
    # axis: presence of a retired gate literal in shipped markdown — tree walk minus exclusions.
    if texts is None:
        texts = {}
        for rel in _iter_shipped_markdown_files():
            if _retired_gate_walk_excluded(rel):
                continue
            texts[rel] = _read_plugin(rel)
    for rel, text in texts.items():
        if _retired_gate_walk_excluded(rel):
            continue
        for literal in _RETIRED_GATE_LITERALS:
            if literal in text:
                raise AssertionError(
                    "%s: retired gate literal %r present" % (rel, literal)
                )


def _assert_retired_door_grading_literals_absent(texts=None):
    if texts is None:
        texts = {rel: _read_plugin(rel) for rel in _TOUCHED_FILES}
    for rel in _TOUCHED_FILES:
        text = texts[rel]
        for literal in _RETIRED_DOOR_GRADING_LITERALS:
            if literal in text:
                raise AssertionError(
                    "%s: retired door-grading literal %r present" % (rel, literal)
                )


def _assert_discuss_open_holder_pins(texts=None):
    if texts is None:
        texts = {
            _DISCUSS_OPEN: _read_plugin(_DISCUSS_OPEN),
            _OWNER_DECISIONS: _read_plugin(_OWNER_DECISIONS),
        }
    # §11.3 anti-tautology: assert the authoritative home FIRST, then the holder's pins
    # (owner-ruled fold 2026-08-24, collector item 72 — the prior order checked the copy
    # before the home).
    owner_lines = set(texts[_OWNER_DECISIONS].splitlines())
    for heading in _PINNED_OWNER_DECISIONS_HEADINGS:
        if heading not in owner_lines:
            raise AssertionError(
                "%s: pinned heading missing: %r" % (_OWNER_DECISIONS, heading)
            )
    text = texts[_DISCUSS_OPEN]
    if _OWNER_DECISIONS not in text:
        raise AssertionError(
            "%s: canonical home %r not cited" % (_DISCUSS_OPEN, _OWNER_DECISIONS)
        )
    _assert_append_before_propose_ordering(text)


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


def test_retired_gate_literals_absent():
    _assert_retired_gate_literals_absent()


def test_retired_door_grading_literals_absent():
    _assert_retired_door_grading_literals_absent()


def test_discuss_open_holder_pins():
    _assert_discuss_open_holder_pins()


def test_owner_rejected_terms_absent():
    _assert_owner_rejected_terms_absent()


def test_registry_marker_has_exactly_one_home():
    _assert_registry_marker_home()


# --- Bite-proofs (synthetic strings; no repo mutation) ------------------------


def test_negative_pinned_heading_renamed():
    synthetic = "\n".join(
        h if h != "## The revisit-trigger registry" else "## The revisit trigger registry"
        for h in _PINNED_OWNER_DECISIONS_HEADINGS
    )
    review_disc = "\n".join(_PINNED_REVIEW_DISCIPLINE_HEADINGS)
    texts = {_OWNER_DECISIONS: synthetic, _REVIEW_DISCIPLINE: review_disc}
    _expect_assertion_error(
        lambda: _assert_pinned_headings_present(texts),
        match=r"pinned heading missing: '## The revisit-trigger registry'",
    )


def test_negative_retired_vocabulary_inserted():
    texts = {rel: "" for rel in _RETIRED_VOCAB_FILES}
    texts[_OWNER_DECISIONS] = _RETIRED_LITERAL
    _expect_assertion_error(
        lambda: _assert_retired_vocabulary_absent(texts),
        match="retired literal",
    )


def test_negative_retired_tier_literal_inserted():
    texts = {rel: "" for rel in _TIER_VOCAB_CENSUS_SURFACES}
    texts[_VET_RECEIPT] = "Every Tier 2 item is appended to the collector."
    _expect_assertion_error(
        lambda: _assert_retired_tier_literals_absent(texts),
        match=r"vet-receipt\.md: retired tier literal 'Tier 2' present",
    )


def test_negative_retired_gate_literal_inserted():
    texts = {"skills/showrunner/SKILL.md": _RETIRED_GATE_HEADING}
    _expect_assertion_error(
        lambda: _assert_retired_gate_literals_absent(texts),
        match=r"retired gate literal .* present",
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
        _OWNER_DECISIONS: "\n".join(_PINNED_OWNER_DECISIONS_HEADINGS),
    }
    _expect_assertion_error(
        lambda: _assert_discuss_open_holder_pins(texts),
        match="canonical home .* not cited",
    )


def test_negative_discuss_open_missing_append_before_propose():
    texts = {
        _DISCUSS_OPEN: (
            "See %s for the front door. Proposed in this session's delivery message, "
            "then appended to the collector."
            % _OWNER_DECISIONS
        ),
        _OWNER_DECISIONS: "\n".join(_PINNED_OWNER_DECISIONS_HEADINGS),
    }
    _expect_assertion_error(
        lambda: _assert_discuss_open_holder_pins(texts),
        match="pinned append-before-propose",
    )


def test_negative_discuss_open_inverted_append_before_propose_one_clause():
    base = _read_plugin(_DISCUSS_OPEN)
    lines = base.splitlines()
    inverted = []
    for i, line in enumerate(lines, 1):
        if i == 47:
            inverted.append(line.replace("**before**", "**after**"))
        else:
            inverted.append(line)
    texts = {
        _DISCUSS_OPEN: "\n".join(inverted),
        _OWNER_DECISIONS: "\n".join(_PINNED_OWNER_DECISIONS_HEADINGS),
    }
    _expect_assertion_error(
        lambda: _assert_discuss_open_holder_pins(texts),
        match="append-after-propose in pinned ordering clause",
    )


def test_negative_discuss_open_append_before_propose_reflowed_passes():
    texts = {
        _DISCUSS_OPEN: (
            "See %s. For each owner call, append it to the collector immediately, "
            "before it is proposed in this session's delivery message. Every owner call is "
            "appended to the collector\n"
            "before it is proposed in this session's delivery message."
            % _OWNER_DECISIONS
        ),
        _OWNER_DECISIONS: "\n".join(_PINNED_OWNER_DECISIONS_HEADINGS),
    }
    _assert_discuss_open_holder_pins(texts)


def test_negative_discuss_open_inverted_append_before_propose():
    texts = {
        _DISCUSS_OPEN: (
            "See %s. Every owner call is appended to the collector "
            "after it is proposed in this session's delivery message."
            % _OWNER_DECISIONS
        ),
        _OWNER_DECISIONS: "\n".join(_PINNED_OWNER_DECISIONS_HEADINGS),
    }
    _expect_assertion_error(
        lambda: _assert_discuss_open_holder_pins(texts),
        match="append-after-propose in pinned ordering clause",
    )


def test_negative_retired_door_grading_literal_inserted():
    texts = {rel: "" for rel in _TOUCHED_FILES}
    texts[_VET_RECEIPT] = "Each append carries its gate verdict and its venue."
    _expect_assertion_error(
        lambda: _assert_retired_door_grading_literals_absent(texts),
        match=r"retired door-grading literal 'gate verdict' present",
    )


def test_negative_registry_marker_outside_home():
    texts = {rel: "" for rel in _TOUCHED_FILES}
    texts[_OWNER_DECISIONS] = _REGISTRY_MARKER
    texts[_VET_RECEIPT] = _REGISTRY_MARKER
    _expect_assertion_error(
        lambda: _assert_registry_marker_home(texts),
        match="registry marker .* present outside home",
    )
