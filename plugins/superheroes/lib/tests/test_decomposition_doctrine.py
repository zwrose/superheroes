"""Drift guards for showrunner decomposition doctrine (issue #937).

Enforces: pinned sentences in both doctrine homes; reference-file structure and vocabulary
agreement with package_read_audit; vet-receipt register-row trigger; section-scoped copies in
the showrunner charter duties 3 and 4.
"""
# What this file does and does not guard (issue #937).
#
# Every assertion rests on a MECHANICAL fact: a literal present or absent, a parsed heading, a
# table row, a backticked token set, a constant imported from package_read_audit.py.
#
# The doctrine's MEANING is guarded by review, not by CI. Do not assert whether prose says the
# right thing — no negation regexes, no paragraph heuristics, no substring checks wearing
# structural labels. If a claim can only be checked by judging what a sentence means, it belongs
# to the review panel.
import importlib.util
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.normpath(os.path.join(_HERE, ".."))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_SHOWRUNNER_CHARTER = "skills/showrunner/SKILL.md"
_DECOMPOSITION_REF = "skills/showrunner/reference/decomposition.md"
_AMENDMENTS_REF = "skills/showrunner/reference/amendments.md"
_VET_RECEIPT_REF = "skills/showrunner/reference/vet-receipt.md"

_DUTY_3_START = "3. **Size, decompose, route.**"
_DUTY_4_START = "4. **Vet PRs from artifacts, never narratives.**"
_DUTY_5_START = "5. **Decide what reaches the owner before the merge click.**"

PIN_POST_APPROVAL = (
    "Decomposition begins only after the spec is owner-approved: no coverage map, no register, "
    "and no child body is drafted against an unapproved spec, and a decomposition artifact dated "
    "before its spec's approval is a routing defect."
)

PIN_AMENDMENT_CLASSES = (
    "Every post-approval spec amendment is classified `wording` — it changes phrasing and decides "
    "nothing a builder could build differently against — or `substantive`, which is everything "
    "else and the default whenever the call is ambiguous."
)

PIN_REGISTER_ROW = (
    "A child PR in a package that has a contract register is vetted against one added row: the "
    "change conforms to the epic's register, or the drift is disclosed — and undisclosed drift "
    "is a blocker, held until it is disclosed or repaired."
)

_DECOMPOSITION_H2_HEADINGS = [
    "When epic machinery fires",
    "The coverage map",
    "The contract register",
    "Seam-first sequencing",
    "Verbatim injection into child bodies",
    "The adversarial package read",
    "Re-entry after a substantive amendment",
    "Reciprocal cross-epic seams",
    "The child-PR register vet row",
    "The single-issue fast path",
    "Vocabulary (drift-tested)",
]

_AMENDMENTS_H2_HEADINGS = [
    "What an amendment is, and when this fires",
    "Classifying the amendment",
    "The log entry",
    "The wording path",
    "The substantive path",
    "Propagation — reaching work already in flight",
    "Reciprocal seams — one contract, two homes",
]

_AUDIT_TRAIL_ELEMENTS = [
    "The weight call (its measurables and ceiling)",
    "Each re-read invocation's cause and ceiling",
    "Any override sentence",
    "The seats",
    "The lenses run per round",
    "The parts each round read with their unreviewed-at-entry status",
    "The findings declined further extension under the unchanged-text rule",
    "Each fix's verification outcome",
    "A recorded verification pass (an invocation with rounds and none is nonconforming)",
]

_LEDGER_READING_SENTENCE = (
    "Convergence and the park call are the advisor's recorded judgment — the tool records them "
    "and checks nothing was left unrecorded; it never re-decides them."
)

_WORKED_EXAMPLE_HEADING = (
    "### Worked example — splitting a criterion that spans two children"
)

_VOCAB_DRIFT_HEADING = "## Vocabulary (drift-tested)"
_TRIGGERED_FIELDS_HEADING = (
    "## Triggered fields — the artifacts raise them, not your memory"
)

_CONTENTS_ROW_RE = re.compile(r"^- \[(.+?)\]\(#([^)]*)\)\s*$")


def _load_package_read_audit():
    path = os.path.join(_LIB, "package_read_audit.py")
    spec = importlib.util.spec_from_file_location(
        "package_read_audit_decomposition_test", path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PRA = _load_package_read_audit()


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


def _vocabulary_section_text(text):
    lines = text.splitlines()
    indices = [
        i for i, line in enumerate(lines) if line.strip() == _VOCAB_DRIFT_HEADING
    ]
    if len(indices) != 1:
        raise RuntimeError(
            f"{_VOCAB_DRIFT_HEADING!r} found {len(indices)} times (expected 1)"
        )
    start = indices[0] + 1
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    section = "\n".join(lines[start:end])
    if not section.strip():
        raise RuntimeError("vocabulary section is empty")
    return section


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
    start_level = 2
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return "\n".join(lines[start:end])


def _assert_register_trigger_row(text):
    section = _triggered_fields_section(text)
    rows = _parse_triggered_fields_table(section)
    matches = [
        row for row in rows
        if "contract register" in _normalized(row[0])
    ]
    if not matches:
        raise AssertionError("no triggered-fields row names contract register")


# --- Pinned sentences in both homes ----------------------------------------


def test_pin_post_approval_in_both_homes():
    _assert_pinned_in_both_homes(
        PIN_POST_APPROVAL,
        _DECOMPOSITION_REF,
        (_DUTY_3_START, _DUTY_4_START),
    )


def test_pin_amendment_classes_in_both_homes():
    _assert_pinned_in_both_homes(
        PIN_AMENDMENT_CLASSES,
        _AMENDMENTS_REF,
        (_DUTY_3_START, _DUTY_4_START),
    )


def test_pin_register_row_in_both_homes():
    _assert_pinned_in_both_homes(
        PIN_REGISTER_ROW,
        _DECOMPOSITION_REF,
        (_DUTY_4_START, _DUTY_5_START),
    )


# --- Reference file structure ------------------------------------------------


def test_decomposition_contents_and_headings():
    _assert_contents_covers_headings(_DECOMPOSITION_REF, _DECOMPOSITION_H2_HEADINGS)


def test_amendments_contents_and_headings():
    _assert_contents_covers_headings(_AMENDMENTS_REF, _AMENDMENTS_H2_HEADINGS)


def test_decomposition_lens_tokens_present():
    text = _read_plugin(_DECOMPOSITION_REF)
    for token in PRA.LENSES:
        if f"`{token}`" not in text:
            raise AssertionError(f"{_DECOMPOSITION_REF}: lens token {token!r} missing")


def test_decomposition_audit_trail_elements_present():
    text = _read_plugin(_DECOMPOSITION_REF)
    for element in _AUDIT_TRAIL_ELEMENTS:
        if element not in text:
            raise AssertionError(
                f"{_DECOMPOSITION_REF}: audit-trail element missing: {element!r}"
            )


def test_decomposition_audit_trail_ledger_reading_not_judge():
    text = _read_plugin(_DECOMPOSITION_REF)
    for token in ("parkOwed", "ceilingReached"):
        if token in text:
            raise AssertionError(
                f"{_DECOMPOSITION_REF}: judge-reading token {token!r} must not appear"
            )
    if _LEDGER_READING_SENTENCE not in text:
        raise AssertionError(
            f"{_DECOMPOSITION_REF}: ledger-reading sentence missing"
        )


def test_decomposition_worked_example_subsection_present():
    text = _read_plugin(_DECOMPOSITION_REF)
    if _WORKED_EXAMPLE_HEADING not in text:
        raise AssertionError(
            f"{_DECOMPOSITION_REF}: missing subsection {_WORKED_EXAMPLE_HEADING!r}"
        )


def test_vocabulary_section_exists():
    # Token-level vocabulary guard: test_ssot_drift.py::test_package_read_audit_vocabulary_in_decomposition_doc
    text = _read_plugin(_DECOMPOSITION_REF)
    _vocabulary_section_text(text)


def test_vet_receipt_register_trigger_row():
    text = _read_plugin(_VET_RECEIPT_REF)
    _assert_register_trigger_row(text)


# --- Negative tests (synthetic strings; no repo mutation) --------------------


def test_negative_missing_pinned_sentence():
    synthetic = "Charter without the pinned decomposition gate sentence."
    _expect_assertion_error(
        lambda: _assert_pinned_present(synthetic, PIN_POST_APPROVAL, "synthetic"),
        match="pinned sentence missing",
    )


def test_negative_pinned_sentence_outside_duty_slice():
    synthetic = "\n".join([
        _DUTY_3_START,
        "Duty three without the pin.",
        _DUTY_4_START,
        PIN_POST_APPROVAL,
        _DUTY_5_START,
    ])
    duty3 = _extract_duty_slice(
        synthetic, _DUTY_3_START, _DUTY_4_START, "synthetic"
    )
    _expect_assertion_error(
        lambda: _assert_pinned_present(duty3, PIN_POST_APPROVAL, "synthetic duty-3"),
        match="pinned sentence missing",
    )


def test_negative_duty_boundary_duplicate_raises():
    synthetic = "\n".join([
        _DUTY_3_START,
        _DUTY_3_START,
        _DUTY_4_START,
    ])
    _expect_error(
        lambda: _extract_duty_slice(
            synthetic, _DUTY_3_START, _DUTY_4_START, "synthetic"
        ),
        RuntimeError,
        match="found 2 times",
    )


def test_negative_duty_boundary_missing_raises():
    synthetic = "\n".join([
        "Preamble without duty three.",
        _DUTY_4_START,
    ])
    _expect_error(
        lambda: _extract_duty_slice(
            synthetic, _DUTY_3_START, _DUTY_4_START, "synthetic"
        ),
        RuntimeError,
        match="found 0 times",
    )


def test_negative_contents_missing_heading_link():
    synthetic = "\n".join([
        "# Contents",
        "",
        "- [When epic machinery fires](#when-epic-machinery-fires)",
        "",
        "# Epic decomposition",
        "",
        "## When epic machinery fires",
        "## The coverage map",
    ])
    _expect_assertion_error(
        lambda: _assert_contents_covers_headings(
            "synthetic/decomposition.md",
            ["When epic machinery fires", "The coverage map"],
            lambda rel: synthetic,
        ),
        match="Contents missing entries",
    )


def test_negative_vet_receipt_missing_register_row():
    synthetic = "\n".join([
        _TRIGGERED_FIELDS_HEADING,
        "",
        "| When the artifacts show… | the receipt owes |",
        "| --- | --- |",
        "| unrelated trigger | some field |",
    ])
    _expect_assertion_error(
        lambda: _assert_register_trigger_row(synthetic),
        match="no triggered-fields row names contract register",
    )
