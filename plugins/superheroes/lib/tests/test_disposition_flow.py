"""Cross-doc disposition-flow pin guards (issue #1113).

Enforces: shared-contract clauses P1–P18 in homes and copy-holders; duty-4 slice
scoping; pinned section headings; retired vocabulary and owner-rejected terms absent;
registry marker home; clause-count floor.
"""
# What this file guards and does not guard (issue #1113).
#
# Every assertion rests on a MECHANICAL fact: a literal present or absent after
# whitespace normalization, a pinned heading string present, a literal absent, a
# cardinality floor, or a duty-slice extractor that bounds a pin to its home block
# (per the byte-literal floor carve-out).
#
# Prose MEANING, Contents parity, table shape, and ordering beyond presence are
# guarded by review, not by CI. No negation heuristics, no paragraph heuristics,
# no structural parsers outside the duty-slice boundary extractor.
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_OWNER_DECISIONS = "skills/showrunner/reference/owner-decisions.md"
_SHOWRUNNER_CHARTER = "skills/showrunner/SKILL.md"
_REVIEW_DISCIPLINE = "rubric/review-discipline.md"
_VET_RECEIPT = "skills/showrunner/reference/vet-receipt.md"
_DISCUSS_OPEN = "skills/discuss-open-decisions/SKILL.md"
_DETECTIVE_CHARTER = "skills/detective/SKILL.md"

_DUTY_4_START = "4. **Vet PRs from artifacts, never narratives.**"
_DUTY_5_START = "5. **Decide what reaches the owner before the merge click.**"

_REGISTRY_MARKER = "<!-- superheroes:revisit-registry -->"

_RETIRED_LITERAL = "Follow-up economics"

_STALE_AVAILABILITY_PHRASE = "Tier-2 proposed to the owner when **attended**"

_OWNER_REJECTED_LITERALS = ("knob-polish",)

_DISCUSS_OPEN_APPEND_BEFORE_PROPOSE = (
    "**before** it is proposed in this session's delivery message"
)

_SHOWRUNNER_P14_HOLDER_SNIPPET = (
    "revisit-trigger registry** is one pinned, always-current comment on the collector issue"
)

_VET_RECEIPT_REGISTRY_SCAN_SNIPPET = (
    "read the project's revisit-trigger registry (the pinned comment on the collector issue)"
)

_DETECTIVE_REGISTRY_SCAN_SNIPPET = (
    "scan the project's revisit-trigger registry per `## The revisit-trigger registry`"
)

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

_PINNED_OWNER_DECISIONS_HEADINGS = (
    "## The worth-it gate and the venue ladder",
    "## The revisit-trigger registry",
)

_PINNED_REVIEW_DISCIPLINE_HEADINGS = (
    "### Continuation and the advisor-resolution valve",
    "### Standing authorization — venue-1 folds",
)

# --- Shared contract clauses P1–P18 (verbatim from WO shared contract) ------------

P1 = (
    "Every residual first passes the worth-it gate: what breaks, for whom, has it ever actually "
    "happened, and what ignoring it costs — weighed against the cost of the cheapest available "
    "venue, with observed-in-the-field evidence outweighing hypotheticals."
)

P2 = (
    "A residual that passes the gate descends the venue ladder: continue the PR, then fold into an "
    "existing issue by editing its body rather than filing a new ticket, then a new issue, bundled "
    "by shared surface before filing."
)

P3 = (
    "A residual that fails the gate at every venue's cost is declined with a revisit trigger — a "
    "named, mechanical re-open condition."
)

P4 = (
    "A residual that passes only at continuation cost is a ride-along — eligible for the continue "
    "and fold venues only, explicitly droppable, and never a ticket."
)

P5 = (
    "No target disposition mix exists: a walk where everything passes the gate, or everything "
    "fails it, is a signal to inspect the interrogation itself rather than a success in either "
    "direction."
)

P6 = (
    "Tier 1 is craft — the resolution follows from already-ratified intent and no plausible product "
    "preference distinguishes the options — and the advisor executes it now and records the "
    "determination dated and reasoned for cheap owner veto; Tier 2 is product — taste, trade, or "
    "commitment — and it is the owner's word, via the collector. Doubt resolves upward."
)

P7 = (
    "Venue-3 filings are always Tier 2 — a new issue spends board attention, a commitment call by "
    "definition, even when its content is craft."
)

P8 = (
    "Every Tier-2 item is appended to the collector at vet time, unconditionally, so the collector "
    "is the complete register by construction; owner attendance governs only when discussion happens "
    "— attended, the item is proposed in the vet-delivery message and may be struck minutes after "
    "it was appended; absent, it awaits the batch."
)

P9 = (
    "Each append carries its gate verdict and its venue recommendation, so the owner's batch is one "
    "word per item."
)

P10 = (
    "Continuation applies when the residual is off any tripwired seam, its fix shape is settled, "
    "and it fits the floor economics of who types it; ambiguity resolves toward continuing."
)

P11 = (
    "The third-rework tripwire's builder stop is untouched and unconditional: the design question it "
    "hands up gets the advisor-resolution valve — craft, and the advisor rules it, records the "
    "determination for veto, and the residual becomes settled-shape; product, and it routes up as "
    "consequences; doubt resolves upward."
)

P12 = (
    "Post-review folds on an open PR need no per-fold owner word when they are micro-sized at "
    "roughly 100 non-test lines or fewer, run under the full micro floor of a cross-vendor seat, "
    "the planted-defect control probe, and the salvage valve, and are disclosed in the PR body and "
    "the owner half; the owner's click remains the gate."
)

P13 = (
    "A residual larger than that bound routes to one bounded builder re-dispatch under the lane's "
    "existing route, and the standalone micro lane's per-change owner word is explicitly unchanged."
)

P14 = (
    "The revisit-trigger registry is one pinned, always-current comment on the project's collector "
    "issue, one line per declined item — what was declined, the worth-it verdict, the revisit "
    "trigger, and the date with a pointer to the full record — archiving declines from both tiers."
)

P15 = (
    "The collector is the pre-ruling queue and the registry is the post-ruling archive."
)

P16 = (
    "Any session processing a field report, and any vet whose evidence includes an "
    "observed-in-the-field failure, reads the registry."
)

P17 = (
    "The registry scan is prose-bound and nothing mechanical enforces it; the registry's floor value "
    "is that whether we already declined something is one comment away."
)

P18 = (
    "Every disposition names its gate verdict and its venue."
)

CLAUSE_HOMES = {
    "P1": (_OWNER_DECISIONS, P1),
    "P2": (_OWNER_DECISIONS, P2),
    "P3": (_OWNER_DECISIONS, P3),
    "P4": (_OWNER_DECISIONS, P4),
    "P5": (_OWNER_DECISIONS, P5),
    "P6": (_OWNER_DECISIONS, P6),
    "P7": (_OWNER_DECISIONS, P7),
    "P8": (_OWNER_DECISIONS, P8),
    "P9": (_OWNER_DECISIONS, P9),
    "P10": (_REVIEW_DISCIPLINE, P10),
    "P11": (_REVIEW_DISCIPLINE, P11),
    "P12": (_REVIEW_DISCIPLINE, P12),
    "P13": (_REVIEW_DISCIPLINE, P13),
    "P14": (_OWNER_DECISIONS, P14),
    "P15": (_OWNER_DECISIONS, P15),
    "P16": (_OWNER_DECISIONS, P16),
    "P17": (_OWNER_DECISIONS, P17),
    "P18": (_VET_RECEIPT, P18),
}

COPY_HOLDERS = {
    "P6": (_SHOWRUNNER_CHARTER,),
    "P7": (_SHOWRUNNER_CHARTER,),
    "P8": (_SHOWRUNNER_CHARTER, _VET_RECEIPT),
    "P9": (_SHOWRUNNER_CHARTER, _VET_RECEIPT),
    "P16": (_SHOWRUNNER_CHARTER,),
}

DUTY_4_CLAUSES = ("P6", "P7", "P8", "P9", "P16")


def _read_plugin(rel):
    path = rel if os.path.isabs(rel) else os.path.join(_PLUGIN_ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _normalized(text):
    return re.sub(r"\s+", " ", text.replace("*", "")).strip()


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


def _extract_duty_slice(text, start_marker, end_marker, label):
    """Slice between numbered duty headings; raises if a boundary is missing or duplicated."""
    lines = text.splitlines()
    start_indices = [
        i for i, line in enumerate(lines) if line.strip().startswith(start_marker)
    ]
    end_indices = [
        i for i, line in enumerate(lines) if line.strip().startswith(end_marker)
    ]
    if len(start_indices) != 1:
        raise RuntimeError(
            "%s: start %r found %d times (expected 1)" % (label, start_marker, len(start_indices))
        )
    if len(end_indices) != 1:
        raise RuntimeError(
            "%s: end %r found %d times (expected 1)" % (label, end_marker, len(end_indices))
        )
    start = start_indices[0]
    end = end_indices[0]
    if end <= start:
        raise RuntimeError("%s: end precedes start" % label)
    return "\n".join(lines[start:end])


def _assert_clause_present(text, clause_text, clause_id, holder_path, *, role):
    if _normalized(clause_text) not in _normalized(text):
        raise AssertionError(
            "%s missing in %s (%s)" % (clause_id, holder_path, role)
        )


def _assert_clause_in_text(clause_id, holder_path, text, *, role):
    _home_path, clause_text = CLAUSE_HOMES[clause_id]
    _assert_clause_present(text, clause_text, clause_id, holder_path, role=role)


def _assert_all_clause_homes(texts=None):
    if texts is None:
        texts = {rel: _read_plugin(rel) for rel in {home for home, _ in CLAUSE_HOMES.values()}}
    for clause_id, (home_path, clause_text) in CLAUSE_HOMES.items():
        home_text = texts.get(home_path)
        if home_text is None:
            home_text = _read_plugin(home_path)
        _assert_clause_present(home_text, clause_text, clause_id, home_path, role="home")


def _assert_copy_holders(texts=None):
    if texts is None:
        needed = set(_TOUCHED_FILES)
        texts = {rel: _read_plugin(rel) for rel in needed}
    for clause_id, copy_paths in COPY_HOLDERS.items():
        home_path, clause_text = CLAUSE_HOMES[clause_id]
        home_text = texts[home_path]
        _assert_clause_present(home_text, clause_text, clause_id, home_path, role="home")
        for copy_path in copy_paths:
            copy_text = texts[copy_path]
            _assert_clause_present(copy_text, clause_text, clause_id, copy_path, role="copy")


def _assert_duty_4_clauses(texts=None):
    if texts is None:
        texts = {
            _OWNER_DECISIONS: _read_plugin(_OWNER_DECISIONS),
            _SHOWRUNNER_CHARTER: _read_plugin(_SHOWRUNNER_CHARTER),
        }
    charter_text = texts[_SHOWRUNNER_CHARTER]
    duty_slice = _extract_duty_slice(
        charter_text,
        _DUTY_4_START,
        _DUTY_5_START,
        _SHOWRUNNER_CHARTER,
    )
    for clause_id in DUTY_4_CLAUSES:
        home_path, clause_text = CLAUSE_HOMES[clause_id]
        home_text = texts[home_path]
        _assert_clause_present(home_text, clause_text, clause_id, home_path, role="home")
        _assert_clause_present(
            duty_slice, clause_text, clause_id, _SHOWRUNNER_CHARTER, role="duty-4 slice"
        )


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


def _assert_stale_availability_branch_absent(texts=None):
    if texts is None:
        texts = {_SHOWRUNNER_CHARTER: _read_plugin(_SHOWRUNNER_CHARTER)}
    if _STALE_AVAILABILITY_PHRASE in texts[_SHOWRUNNER_CHARTER]:
        raise AssertionError(
            "%s: stale availability-branch phrase %r present"
            % (_SHOWRUNNER_CHARTER, _STALE_AVAILABILITY_PHRASE)
        )


def _assert_discuss_open_holder_pins(texts=None):
    if texts is None:
        texts = {
            _DISCUSS_OPEN: _read_plugin(_DISCUSS_OPEN),
            _OWNER_DECISIONS: _read_plugin(_OWNER_DECISIONS),
        }
    text = texts[_DISCUSS_OPEN]
    if _OWNER_DECISIONS not in text:
        raise AssertionError(
            "%s: canonical home %r not cited" % (_DISCUSS_OPEN, _OWNER_DECISIONS)
        )
    if _DISCUSS_OPEN_APPEND_BEFORE_PROPOSE.replace("*", "") not in _normalized(text):
        raise AssertionError(
            "%s: append-before-propose pin %r missing"
            % (_DISCUSS_OPEN, _DISCUSS_OPEN_APPEND_BEFORE_PROPOSE)
        )
    home_path, clause_text = CLAUSE_HOMES["P8"]
    _assert_clause_present(
        texts[home_path], clause_text, "P8", home_path, role="home"
    )


def _assert_registry_holder_pins(texts=None):
    if texts is None:
        texts = {
            _OWNER_DECISIONS: _read_plugin(_OWNER_DECISIONS),
            _SHOWRUNNER_CHARTER: _read_plugin(_SHOWRUNNER_CHARTER),
            _VET_RECEIPT: _read_plugin(_VET_RECEIPT),
            _DETECTIVE_CHARTER: _read_plugin(_DETECTIVE_CHARTER),
        }
    home_path, p14_text = CLAUSE_HOMES["P14"]
    _assert_clause_present(
        texts[home_path], p14_text, "P14", home_path, role="home"
    )
    charter_text = texts[_SHOWRUNNER_CHARTER]
    duty_slice = _extract_duty_slice(
        charter_text,
        _DUTY_4_START,
        _DUTY_5_START,
        _SHOWRUNNER_CHARTER,
    )
    if _SHOWRUNNER_P14_HOLDER_SNIPPET.replace("*", "") not in _normalized(duty_slice):
        raise AssertionError(
            "%s: P14 holder pin %r missing in duty-4 slice"
            % (_SHOWRUNNER_CHARTER, _SHOWRUNNER_P14_HOLDER_SNIPPET)
        )
    home_path, p16_text = CLAUSE_HOMES["P16"]
    _assert_clause_present(
        texts[home_path], p16_text, "P16", home_path, role="home"
    )
    _assert_clause_present(
        duty_slice, p16_text, "P16", _SHOWRUNNER_CHARTER, role="duty-4 slice"
    )
    if _VET_RECEIPT_REGISTRY_SCAN_SNIPPET not in texts[_VET_RECEIPT]:
        raise AssertionError(
            "%s: registry-scan holder pin %r missing"
            % (_VET_RECEIPT, _VET_RECEIPT_REGISTRY_SCAN_SNIPPET)
        )
    if _DETECTIVE_REGISTRY_SCAN_SNIPPET not in texts[_DETECTIVE_CHARTER]:
        raise AssertionError(
            "%s: registry-scan holder pin %r missing"
            % (_DETECTIVE_CHARTER, _DETECTIVE_REGISTRY_SCAN_SNIPPET)
        )


def _assert_retired_vocabulary_absent(texts=None):
    if texts is None:
        texts = {rel: _read_plugin(rel) for rel in _RETIRED_VOCAB_FILES}
    for rel in _RETIRED_VOCAB_FILES:
        if _RETIRED_LITERAL in texts[rel]:
            raise AssertionError("%s: retired literal %r present" % (rel, _RETIRED_LITERAL))


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


def _clause_constant_count():
    return len([name for name in globals() if re.match(r"^P\d+$", name)])


def _assert_clause_count_floor(minimum=18):
    count = _clause_constant_count()
    if count < minimum:
        raise AssertionError(
            "clause constant count %d below floor %d" % (count, minimum)
        )


# --- Primary detectors ---------------------------------------------------------


def test_clause_homes_carry_every_clause():
    _assert_all_clause_homes()


def test_copy_holders_carry_their_clauses():
    _assert_copy_holders()


def test_duty_4_slice_carries_its_clauses():
    _assert_duty_4_clauses()


def test_new_section_headings_present():
    _assert_pinned_headings_present()


def test_retired_vocabulary_is_gone():
    _assert_retired_vocabulary_absent()
    _assert_stale_availability_branch_absent()


def test_discuss_open_holder_pins():
    _assert_discuss_open_holder_pins()


def test_registry_holder_pins():
    _assert_registry_holder_pins()


def test_owner_rejected_terms_absent():
    _assert_owner_rejected_terms_absent()


def test_registry_marker_has_exactly_one_home():
    _assert_registry_marker_home()


def test_clause_count_floor():
    _assert_clause_count_floor(18)


# --- Bite-proofs (synthetic strings; no repo mutation) ------------------------


def test_negative_clause_missing_from_home():
    synthetic = "Owner decisions without the pinned clause."
    _expect_assertion_error(
        lambda: _assert_clause_present(synthetic, P1, "P1", "synthetic.md", role="home"),
        match="P1 missing in synthetic.md \\(home\\)",
    )


def test_negative_copy_holder_missing_while_home_present():
    texts = {
        _OWNER_DECISIONS: P6,
        _SHOWRUNNER_CHARTER: "Charter without the tier principle pin.",
        _VET_RECEIPT: _read_plugin(_VET_RECEIPT),
    }
    _expect_assertion_error(
        lambda: _assert_copy_holders(texts),
        match="P6 missing in .* \\(copy\\)",
    )


def test_negative_clause_outside_duty_4_slice():
    synthetic_charter = "\n".join([
        _DUTY_4_START,
        "Duty four without the pins.",
        _DUTY_5_START,
        P6,
    ])
    texts = {
        _OWNER_DECISIONS: P6,
        _SHOWRUNNER_CHARTER: synthetic_charter,
    }
    _expect_assertion_error(
        lambda: _assert_duty_4_clauses(texts),
        match="P6 missing in .* \\(duty-4 slice\\)",
    )


def test_negative_duty_boundary_duplicate_raises():
    synthetic = "\n".join([
        _DUTY_4_START,
        _DUTY_4_START,
        _DUTY_5_START,
    ])
    _expect_error(
        lambda: _extract_duty_slice(
            synthetic, _DUTY_4_START, _DUTY_5_START, "synthetic"
        ),
        RuntimeError,
        match="found 2 times",
    )


def test_negative_pinned_heading_renamed():
    synthetic = "\n".join([
        "## The worth-it gate and the venue ladder (old)",
        "## The revisit-trigger registry",
    ])
    review_disc = "\n".join(_PINNED_REVIEW_DISCIPLINE_HEADINGS)
    texts = {_OWNER_DECISIONS: synthetic, _REVIEW_DISCIPLINE: review_disc}
    _expect_assertion_error(
        lambda: _assert_pinned_headings_present(texts),
        match=r"owner-decisions\.md: pinned heading missing: '## The worth-it gate and the venue ladder'",
    )


def test_negative_stale_availability_branch_survives():
    texts = {_SHOWRUNNER_CHARTER: "Stale row: " + _STALE_AVAILABILITY_PHRASE}
    _expect_assertion_error(
        lambda: _assert_stale_availability_branch_absent(texts),
        match="stale availability-branch phrase",
    )


def test_negative_retired_vocabulary_inserted():
    texts = {rel: "" for rel in _RETIRED_VOCAB_FILES}
    texts[_OWNER_DECISIONS] = _RETIRED_LITERAL
    _expect_assertion_error(
        lambda: _assert_retired_vocabulary_absent(texts),
        match="retired literal",
    )


def test_negative_owner_rejected_literal_inserted():
    texts = {rel: "" for rel in _TOUCHED_FILES}
    texts[_REVIEW_DISCIPLINE] = "A knob-polish pass."
    _expect_assertion_error(
        lambda: _assert_owner_rejected_terms_absent(texts),
        match="owner-rejected literal 'knob-polish' present",
    )


def test_negative_discuss_open_append_after_propose():
    texts = {
        _DISCUSS_OPEN: (
            "See %s — append after it is proposed in this session's delivery message."
            % _OWNER_DECISIONS
        ),
        _OWNER_DECISIONS: P8,
    }
    _expect_assertion_error(
        lambda: _assert_discuss_open_holder_pins(texts),
        match="append-before-propose pin",
    )


def test_negative_registry_marker_outside_home():
    texts = {rel: "" for rel in _TOUCHED_FILES}
    texts[_OWNER_DECISIONS] = _REGISTRY_MARKER
    texts[_VET_RECEIPT] = _REGISTRY_MARKER
    _expect_assertion_error(
        lambda: _assert_registry_marker_home(texts),
        match="registry marker .* present outside home",
    )


def test_negative_clause_count_below_floor():
    _expect_assertion_error(
        lambda: _assert_clause_count_floor(19),
        match="clause constant count .* below floor 19",
    )
