"""Drift guards for showrunner spec-closure doctrine (issue #938).

Enforces: pinned sentences in both doctrine homes; closure.md structure; R8 element-list
home; vet-receipt and decomposition seam surfaces.
"""
# What this file does and does not guard (issue #938).
#
# Every assertion rests on a MECHANICAL fact: a literal present or absent, a parsed heading, a
# table row, or a count.
#
# The doctrine's MEANING is guarded by review, not by CI. Do not assert whether prose says the
# right thing — no negation regexes, no paragraph heuristics, no substring checks wearing
# structural labels. If a claim can only be checked by judging what a sentence means, it belongs
# to the review panel.
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_SHOWRUNNER_CHARTER = "skills/showrunner/SKILL.md"
_CLOSURE_REF = "skills/showrunner/reference/closure.md"
_VET_RECEIPT_REF = "skills/showrunner/reference/vet-receipt.md"
_DECOMPOSITION_REF = "skills/showrunner/reference/decomposition.md"

_DUTY_1_START = "1. **Think at the project level.**"
_DUTY_2_START = "2. **Board hygiene — file and wire.**"
_DUTY_4_START = "4. **Vet PRs from artifacts, never narratives.**"
_DUTY_5_START = "5. **Decide what reaches the owner before the merge click.**"
_DUTY_6_START = "6. **Coordinate releases and drive the merge train.**"

PIN_PRESENT_TENSE = (
    "The vet that carries the closure receipt is the one whose merge closes the spec's last open "
    "child, and it knows it is the final vet by the present-tense test: every other child is "
    "already merged or closed at the moment of this vet."
)

PIN_SEQUENCING = (
    "Where more than one candidate closure moment is live — concurrent final vets, or a vet racing "
    "a sibling's no-PR close — the advisor sequences them so exactly one carries the receipt."
)

PIN_NO_PR_CLOSE = (
    "Where the last open child closes without a PR — declined scope — the closure receipt is "
    "presented to the owner with that close, in the same sitting, and there is still no separate "
    "closure trigger."
)

PIN_DELIVERY_DECISION = (
    "No spec closes without either full delivery accepted or an explicit owner acceptance of "
    "partial delivery, named as such on the closure receipt with delivered, deferred, and declined "
    "each named; nothing closes silently incomplete."
)

PIN_FAILING_RUN = (
    "A failing end-to-end validation run keeps the spec open by default and mints one repair issue "
    "per failure, each anchored to the failing run's record and naming the unmet acceptance "
    "criterion it restores; the owner may instead explicitly accept delivery with the failing run "
    "disclosed, and either way the cycle ends at an owner decision."
)

PIN_ABANDONED_CHILD = (
    "A spec whose child is abandoned — closed unmerged, orphaned, or displaced — is re-planned or "
    "parked by the advisor rather than left waiting for a closure moment that cannot come; silence "
    "is not a disposition."
)

R8_CLOSURE_RECEIPT_ELEMENTS = (
    "The closure receipt enumerates exactly: coverage map complete; all other children merged "
    "with green vets; amendments reconciled — meaning the Amendments log is valid against R4's "
    "format AND UFR-4's propagation is verified: every affected child carried the amended text "
    "or an explicit notice, and the coverage map still allocates every acceptance criterion; "
    "one end-to-end validation run against the current spec body with its result stated; "
    "aggregated Show-it items; delivered versus deferred/declined named; and NFR conformance "
    "checked across the delivery (owner reading load, plain language, guidelines never hardened "
    "into gates) — an absent element is named with why."
)

_CLOSURE_H2_HEADINGS = [
    "When closure fires",
    "The closure receipt",
    "The validation run",
    "The owner's delivery decision",
    "When the validation run fails",
    "An abandoned child",
    "The single-issue case",
]

_VALIDATION_RUN_FAILS_H3 = [
    "The default — the spec stays open",
    "The alternative — the owner accepts with the failing run disclosed",
]

_SINGLE_ISSUE_FAST_PATH_HEADING = "The single-issue fast path"

_TRIGGERED_FIELDS_HEADING = (
    "## Triggered fields — the artifacts raise them, not your memory"
)

_CONTENTS_ROW_RE = re.compile(r"^- \[(.+?)\]\(#([^)]*)\)\s*$")


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


def _github_anchor(title):
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9 _\-]", "", slug)
    return slug.replace(" ", "-")


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
            f"{label}: start {start_marker!r} found {len(start_indices)} times (expected 1)"
        )
    if len(end_indices) != 1:
        raise RuntimeError(
            f"{label}: end {end_marker!r} found {len(end_indices)} times (expected 1)"
        )
    start = start_indices[0]
    end = end_indices[0]
    if end <= start:
        raise RuntimeError(f"{label}: end precedes start")
    return "\n".join(lines[start:end])


def _assert_pinned_present(text, pin, label):
    if _normalized(pin) not in _normalized(text):
        raise AssertionError(f"{label}: pinned sentence missing after whitespace normalization")


def _assert_pinned_in_both_homes(pin, ref_rel, charter_duty_slice):
    ref_text = _read_plugin(ref_rel)
    _assert_pinned_present(ref_text, pin, ref_rel)
    charter_text = _read_plugin(_SHOWRUNNER_CHARTER)
    duty_text = _extract_duty_slice(
        charter_text,
        charter_duty_slice[0],
        charter_duty_slice[1],
        _SHOWRUNNER_CHARTER,
    )
    _assert_pinned_present(duty_text, pin, f"{_SHOWRUNNER_CHARTER} duty slice")


def _contents_section(text):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "# Contents":
            start = i
            break
    if start is None:
        raise RuntimeError("missing # Contents heading")
    rows = []
    for line in lines[start + 1:]:
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("# Contents"):
            break
        if not stripped:
            continue
        match = _CONTENTS_ROW_RE.match(line)
        if not match:
            raise RuntimeError(f"Contents line not a markdown link row: {line!r}")
        rows.append((match.group(1), match.group(2)))
    if not rows:
        raise RuntimeError("Contents section parsed to zero link rows")
    return rows


def _h2_headings_after_title(text):
    """## headings in the body after the document title line."""
    lines = text.splitlines()
    title_idx = None
    for i, line in enumerate(lines):
        if line.startswith("# ") and line.strip() != "# Contents":
            title_idx = i
            break
    if title_idx is None:
        raise RuntimeError("document title heading not found")
    return [line[3:].strip() for line in lines[title_idx + 1:] if line.startswith("## ")]


def _assert_contents_covers_headings(ref_rel, pinned_headings, read_text=None):
    if read_text is None:
        read_text = _read_plugin
    text = read_text(ref_rel)
    listed_titles = [row[0] for row in _contents_section(text)]
    headings = _h2_headings_after_title(text)
    if headings != pinned_headings:
        raise AssertionError(
            f"{ref_rel}: ## headings {headings!r} do not match pinned list {pinned_headings!r}"
        )
    missing = [h for h in headings if h not in listed_titles]
    if missing:
        raise AssertionError(f"{ref_rel}: Contents missing entries for {missing!r}")
    extra = [t for t in listed_titles if t not in headings]
    if extra:
        raise AssertionError(f"{ref_rel}: Contents entries with no ## heading: {extra!r}")
    duplicates = sorted({t for t in listed_titles if listed_titles.count(t) > 1})
    if duplicates:
        raise AssertionError(f"{ref_rel}: duplicate Contents entries: {duplicates!r}")
    wrong_anchors = []
    for (title, anchor), heading in zip(_contents_section(text), headings):
        expected = _github_anchor(heading)
        if anchor != expected:
            wrong_anchors.append(
                f"{title!r} links to #{anchor}, expected #{expected} from heading {heading!r}"
            )
    if wrong_anchors:
        raise AssertionError(f"{ref_rel}: " + "; ".join(wrong_anchors))


def _assert_literal_count(literal, rel, expected, text=None):
    if text is None:
        text = _read_plugin(rel)
    count = text.count(literal)
    if count != expected:
        raise AssertionError(
            "%s: expected %d occurrence(s) of pinned literal, found %d"
            % (rel, expected, count)
        )


def _h2_section(text, heading_title):
    lines = text.splitlines()
    marker = "## " + heading_title
    start_indices = [i for i, line in enumerate(lines) if line.strip() == marker]
    if len(start_indices) != 1:
        raise RuntimeError(
            f"## {heading_title!r} found {len(start_indices)} times (expected 1)"
        )
    start = start_indices[0]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return "\n".join(lines[start:end])


def _h3_headings_in_section(section_text):
    return [line[4:].strip() for line in section_text.splitlines() if line.startswith("### ")]


def _assert_validation_run_fails_subheadings(text):
    section = _h2_section(text, "When the validation run fails")
    subheadings = _h3_headings_in_section(section)
    if subheadings != _VALIDATION_RUN_FAILS_H3:
        raise AssertionError(
            "When the validation run fails: ### subheadings %r do not match pinned list %r"
            % (subheadings, _VALIDATION_RUN_FAILS_H3)
        )


def _parse_triggered_fields_table(section_text):
    table_lines = []
    in_table = False
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            table_lines.append(stripped)
        elif in_table:
            break
    if len(table_lines) < 3:
        raise RuntimeError("triggered-fields table missing or incomplete")
    rows = []
    for table_line in table_lines[2:]:
        cells = [cell.strip() for cell in table_line.strip("|").split("|")]
        if cells:
            rows.append(cells)
    if not rows:
        raise RuntimeError("triggered-fields table has no data rows")
    return rows


def _triggered_fields_section(text):
    lines = text.splitlines()
    indices = [
        i for i, line in enumerate(lines) if line.strip() == _TRIGGERED_FIELDS_HEADING
    ]
    if len(indices) != 1:
        raise RuntimeError(
            f"{_TRIGGERED_FIELDS_HEADING!r} found {len(indices)} times (expected 1)"
        )
    start = indices[0]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return "\n".join(lines[start:end])


def _assert_closure_trigger_row(text):
    section = _triggered_fields_section(text)
    rows = _parse_triggered_fields_table(section)
    matches = [
        row for row in rows
        if "closure receipt" in _normalized(row[1])
    ]
    if len(matches) != 1:
        raise AssertionError(
            "expected exactly one triggered-fields row naming closure receipt, found %d"
            % len(matches)
        )
    trigger = _normalized(matches[0][0]).lower()
    if "without a pr" not in trigger:
        raise AssertionError(
            "closure trigger row trigger cell does not mention no-PR close"
        )


def _assert_section_names_closure_md(text, heading_title):
    section = _h2_section(text, heading_title)
    if "closure.md" not in section:
        raise AssertionError(
            "%r section does not name closure.md" % heading_title
        )


# --- Pinned sentences in both homes ------------------------------------------


def test_pin_present_tense_in_both_homes():
    _assert_pinned_in_both_homes(
        PIN_PRESENT_TENSE,
        _CLOSURE_REF,
        (_DUTY_4_START, _DUTY_5_START),
    )


def test_pin_sequencing_in_both_homes():
    _assert_pinned_in_both_homes(
        PIN_SEQUENCING,
        _CLOSURE_REF,
        (_DUTY_4_START, _DUTY_5_START),
    )


def test_pin_no_pr_close_in_both_homes():
    _assert_pinned_in_both_homes(
        PIN_NO_PR_CLOSE,
        _CLOSURE_REF,
        (_DUTY_4_START, _DUTY_5_START),
    )


def test_pin_delivery_decision_in_both_homes():
    _assert_pinned_in_both_homes(
        PIN_DELIVERY_DECISION,
        _CLOSURE_REF,
        (_DUTY_5_START, _DUTY_6_START),
    )


def test_pin_failing_run_in_both_homes():
    _assert_pinned_in_both_homes(
        PIN_FAILING_RUN,
        _CLOSURE_REF,
        (_DUTY_5_START, _DUTY_6_START),
    )


def test_pin_abandoned_child_in_both_homes():
    _assert_pinned_in_both_homes(
        PIN_ABANDONED_CHILD,
        _CLOSURE_REF,
        (_DUTY_1_START, _DUTY_2_START),
    )


# --- closure.md structure ----------------------------------------------------


def test_closure_h2_headings_match_pinned_list():
    text = _read_plugin(_CLOSURE_REF)
    _assert_h2_headings_match_pinned(text, _CLOSURE_REF, _CLOSURE_H2_HEADINGS)


def test_closure_contents_covers_headings():
    _assert_contents_covers_headings(_CLOSURE_REF, _CLOSURE_H2_HEADINGS)


def test_closure_validation_run_fails_has_two_h3_subheadings():
    text = _read_plugin(_CLOSURE_REF)
    _assert_validation_run_fails_subheadings(text)


# --- R8 element list home ----------------------------------------------------


def test_r8_element_sentence_has_exactly_one_plugin_home():
    hits = []
    for dirpath, _dirs, files in os.walk(_PLUGIN_ROOT):
        for name in files:
            if not name.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), _PLUGIN_ROOT)
            count = _read_plugin(rel).count(R8_CLOSURE_RECEIPT_ELEMENTS)
            if count:
                hits.append((rel, count))
    assert hits == [(_CLOSURE_REF, 1)], (
        "R8 element list must live in closure.md and nowhere else in the plugin; found %r"
        % (hits,)
    )


# --- Seam surfaces -----------------------------------------------------------


def test_vet_receipt_closure_trigger_row():
    text = _read_plugin(_VET_RECEIPT_REF)
    _assert_closure_trigger_row(text)


def test_decomposition_single_issue_fast_path_names_closure_md():
    text = _read_plugin(_DECOMPOSITION_REF)
    _assert_section_names_closure_md(text, _SINGLE_ISSUE_FAST_PATH_HEADING)


# --- Negative tests (synthetic strings; no repo mutation) --------------------


def test_negative_missing_pinned_sentence():
    synthetic = "Charter without the pinned closure sentence."
    _expect_assertion_error(
        lambda: _assert_pinned_present(synthetic, PIN_PRESENT_TENSE, "synthetic"),
        match="pinned sentence missing",
    )


def test_negative_pinned_sentence_outside_duty_slice():
    synthetic = "\n".join([
        _DUTY_4_START,
        "Duty four without the pin.",
        _DUTY_5_START,
        PIN_PRESENT_TENSE,
        _DUTY_6_START,
    ])
    duty4 = _extract_duty_slice(
        synthetic, _DUTY_4_START, _DUTY_5_START, "synthetic"
    )
    _expect_assertion_error(
        lambda: _assert_pinned_present(duty4, PIN_PRESENT_TENSE, "synthetic duty-4"),
        match="pinned sentence missing",
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


def test_negative_duty_boundary_missing_raises():
    synthetic = "\n".join([
        "Preamble without duty four.",
        _DUTY_5_START,
    ])
    _expect_error(
        lambda: _extract_duty_slice(
            synthetic, _DUTY_4_START, _DUTY_5_START, "synthetic"
        ),
        RuntimeError,
        match="found 0 times",
    )


def _assert_h2_headings_match_pinned(text, ref_rel, pinned_headings):
    headings = _h2_headings_after_title(text)
    if headings != pinned_headings:
        raise AssertionError(
            f"{ref_rel}: ## headings {headings!r} do not match pinned list {pinned_headings!r}"
        )


def test_negative_h2_headings_wrong_order():
    synthetic = "\n".join([
        "# Spec closure",
        "",
        "## When closure fires",
        "## An abandoned child",
    ])
    _expect_assertion_error(
        lambda: _assert_h2_headings_match_pinned(
            synthetic,
            "synthetic/closure.md",
            _CLOSURE_H2_HEADINGS[:2],
        ),
        match="do not match pinned list",
    )


def test_negative_contents_missing_heading_link():
    synthetic = "\n".join([
        "# Contents",
        "",
        "- [When closure fires](#when-closure-fires)",
        "",
        "# Spec closure",
        "",
        "## When closure fires",
        "## The closure receipt",
    ])
    _expect_assertion_error(
        lambda: _assert_contents_covers_headings(
            "synthetic/closure.md",
            ["When closure fires", "The closure receipt"],
            lambda rel: synthetic,
        ),
        match="Contents missing entries",
    )


def test_negative_literal_present_zero_times():
    _expect_assertion_error(
        lambda: _assert_literal_count(
            R8_CLOSURE_RECEIPT_ELEMENTS,
            "synthetic.md",
            1,
            text="no R8 sentence here",
        ),
        match="expected 1 occurrence.*found 0",
    )


def test_negative_literal_present_twice():
    duplicated = R8_CLOSURE_RECEIPT_ELEMENTS + " " + R8_CLOSURE_RECEIPT_ELEMENTS
    _expect_assertion_error(
        lambda: _assert_literal_count(
            R8_CLOSURE_RECEIPT_ELEMENTS,
            "synthetic.md",
            1,
            text=duplicated,
        ),
        match="expected 1 occurrence.*found 2",
    )


def test_negative_vet_receipt_closure_row_field_does_not_name_receipt():
    synthetic = "\n".join([
        _TRIGGERED_FIELDS_HEADING,
        "",
        "| When the artifacts show… | the receipt owes |",
        "| --- | --- |",
        "| last child closes without a PR | unrelated field |",
    ])
    _expect_assertion_error(
        lambda: _assert_closure_trigger_row(synthetic),
        match="expected exactly one triggered-fields row naming closure receipt, found 0",
    )


def test_negative_validation_run_fails_subheadings_wrong_order():
    synthetic = "\n".join([
        "## When the validation run fails",
        "",
        "### The alternative — the owner accepts with the failing run disclosed",
        "### The default — the spec stays open",
    ])
    _expect_assertion_error(
        lambda: _assert_validation_run_fails_subheadings(synthetic),
        match="### subheadings",
    )


def test_negative_single_issue_section_missing_closure_md():
    synthetic = "\n".join([
        "## The single-issue fast path",
        "",
        "Closure folds into that PR's vet without naming the home file.",
    ])
    _expect_assertion_error(
        lambda: _assert_section_names_closure_md(
            synthetic, _SINGLE_ISSUE_FAST_PATH_HEADING
        ),
        match="does not name closure.md",
    )
