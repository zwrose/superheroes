"""Guards for issue 2600: a sheet carried across a judged code-conflict fix says so in one line, on the page and in the chat prose.

The carry's optional carriedForward.conflictFix (the vet's one-line reason the fix is immaterial) is kept in prSheet.carriedForward and
drawn from the one words entry pr.conflictFixed; a carry without it still shows no note. The carry fixtures are those of
test_pr_sheet_head_2496.py; the page is driven the way test_review_template_pr.py drives it (the real template under node)."""
import copy

import pytest

import pr_sheet
import sheet_prose
from test_pr_sheet_head_2496 import LAYERS, SMALL, STACK, WORDS, bundle, build, carried, problems_of, sheet_bytes
from test_review_template_pr import PW, SAMPLES, _carried_from, _page, _with
from test_sheet_schema import errors_for

WHY = "the fix only renamed a local variable"
LINE = "A code conflict was fixed when the base was brought in, and it was judged immaterial: " + WHY
NOTE = "carriedForward conflictFix must be a non-empty string"


def carried_with(advisor, heads, **extra):
    """The advisor's input with a carry from `heads`, plus the given extra carriedForward keys."""
    given = carried(advisor, heads)
    given["carriedForward"].update(extra)
    return given


def carried_build(case, **extra):
    """(sheet built with a carry and the extra keys, the heads it carries to)."""
    records, advisor = bundle(case)
    previous = sheet_bytes(build(records, advisor))
    heads = {"211": "1" * 40} if case is SMALL else dict(LAYERS)
    advisor["headNow"] = {n: {"commit": c, "ci": "green"} for n, c in heads.items()}
    return build(records, carried_with(advisor, heads, **extra), previous)


def carried_refusal(case, **extra):
    records, advisor = bundle(case)
    previous = sheet_bytes(build(records, advisor))
    heads = {"211": "1" * 40} if case is SMALL else dict(LAYERS)
    advisor["headNow"] = {n: {"commit": c, "ci": "green"} for n, c in heads.items()}
    return problems_of(records, carried_with(advisor, heads, **extra), previous)


def test_the_words_entry_is_the_one_line():
    # Axis: the one new words entry reads as the order says, so the tests below compare the surfaces to it and not to a copy.
    assert WORDS["conflictFixed"] == "A code conflict was fixed when the base was brought in, and it was judged immaterial: {why}"
    assert WORDS["conflictFixed"].replace("{why}", WHY) == LINE


@pytest.mark.parametrize("case", [SMALL, STACK], ids=["pr", "stack"])
def test_the_builder_keeps_the_conflict_fix_in_the_carry(case):
    # Axis: the built sheet holds the string as prSheet.carriedForward.conflictFix, beside the carry's other fields; without it the key is absent.
    sheet = carried_build(case, conflictFix=WHY)
    assert sheet["prSheet"]["carriedForward"]["conflictFix"] == WHY
    assert set(sheet["prSheet"]["carriedForward"]) == {"sheets", "date", "moved", "whyNotMaterial", "conflictFix"}
    assert "conflictFix" not in carried_build(case)["prSheet"]["carriedForward"]


# Bites on: a conflictFix that is empty, whitespace-only or not a string accepted by the builder (a blank line drawn on the sheet).
@pytest.mark.parametrize("value", ["", "   ", 7, None, ["a reason"]], ids=["empty", "blank", "number", "null", "list"])
def test_a_conflict_fix_that_is_empty_or_not_a_string_is_refused(value):
    # Axis: E-cf-type: the optional key present with no usable text is a Refusal naming it, and no sheet is built.
    found = carried_refusal(SMALL, conflictFix=value)
    assert NOTE in found, found


# Bites on: the optional tuple of the carry's keys widened, so an unknown carriedForward key is no longer refused.
def test_an_unknown_carry_key_is_still_refused_beside_a_conflict_fix():
    # Axis: E-cf-key: the optional tuple names conflictFix alone, so a misspelling of it (or any other key) is refused naming the key.
    found = carried_refusal(SMALL, conflictFix=WHY, conflictfix=WHY)
    assert "carriedForward has an unknown key conflictfix" in found, found
    assert NOTE not in found


# Bites on: the HTML branch dropped or its condition widened (a carried sheet with a conflictFix draws nothing, or an uncarried or fix-less one draws the line).
@pytest.mark.parametrize("kind", ["pr", "stack"])
def test_the_page_draws_the_line_of_a_carried_sheet_with_a_conflict_fix(kind):
    # Axis: E-cf-line-page: a carried sheet with conflictFix draws one pr-conflict-fixed box, directly under What changed, holding the one line.
    def add(clone):
        clone["prSheet"]["carriedForward"]["conflictFix"] = WHY
    sheet = _with(_carried_from(SAMPLES[kind]), add)
    page = _page(sheet, """
      const box = part("pr-conflict-fixed");
      return { order: order(), box: box === undefined ? null : shape(box), className: box === undefined ? null : box.className, texts: t.everyText() };
    """)
    assert page["result"]["order"][:3] == ["pr-what-changed", "pr-conflict-fixed", "pr-walk"]
    assert page["result"]["order"].count("pr-conflict-fixed") == 1
    assert page["result"]["box"] == [LINE] and page["result"]["box"] == [PW["conflictFixed"].replace("{why}", WHY)]
    assert page["result"]["className"] == "sh-box"
    assert "pr-changed" not in page["result"]["order"] and "pr-carried" not in page["result"]["order"]
    assert "\n".join(page["result"]["texts"]).count("A code conflict was fixed") == 1


# Bites on: the prose branch dropped or its condition widened.
@pytest.mark.parametrize("case", [SMALL, STACK], ids=["pr", "stack"])
def test_the_prose_draws_the_line_of_a_carried_sheet_with_a_conflict_fix(case):
    # Axis: E-cf-line-prose: a carried sheet with conflictFix has the one line in its prose, exactly once, between What changed and the rest.
    sheet = carried_build(case, conflictFix=WHY)
    assert sheet_prose.check_sheet(sheet) == []
    prose = sheet_prose.render(sheet)
    assert prose.count(LINE) == 1 and prose.count("A code conflict was fixed") == 1
    assert WORDS["changedHeading"] not in prose and "Carried forward" not in prose


# Bites on: the line drawn for a carry without a conflictFix, or for an uncarried sheet (the E-nonote axis of i2496_wo_c_sheet_head, kept).
@pytest.mark.parametrize("case", [SMALL, STACK], ids=["pr", "stack"])
def test_a_carry_without_a_conflict_fix_and_an_uncarried_sheet_draw_no_line(case):
    # Axis: E-nonote: a carried sheet without conflictFix, and an uncarried one, show no conflict-fix line in the prose or on the page.
    plain = carried_build(case)
    assert "A code conflict was fixed" not in sheet_prose.render(plain)
    records, advisor = bundle(case)
    assert "A code conflict was fixed" not in sheet_prose.render(build(records, advisor))
    kind = "pr" if case is SMALL else "stack"
    page = _page(_carried_from(SAMPLES[kind]), 'return { order: order(), texts: t.everyText() };')
    assert "pr-conflict-fixed" not in page["result"]["order"]
    assert "A code conflict was fixed" not in "\n".join(page["result"]["texts"])
    page = _page(SAMPLES[kind], 'return { order: order(), texts: t.everyText() };')
    assert "pr-conflict-fixed" not in page["result"]["order"]


# Bites on: the schema property's minLength dropped, or the property missing (the built sheet no longer validates).
def test_the_built_sheet_validates_and_an_empty_conflict_fix_does_not():
    # Axis: E-cf-schema: the built sheet with conflictFix validates against sheet.schema.json; the same sheet with conflictFix "" does not.
    sheet = carried_build(SMALL, conflictFix=WHY)
    assert errors_for(sheet) == []
    bad = copy.deepcopy(sheet)
    bad["prSheet"]["carriedForward"]["conflictFix"] = ""
    assert errors_for(bad) != []
    assert any("conflictFix" in "/".join(str(p) for p in e.absolute_path) or "should be non-empty" in e.message for e in errors_for(bad))


def test_the_builder_module_still_refuses_through_the_public_entry():
    # Axis: the refusal is pr_sheet.Refusal, the same entry the other carry refusals use.
    records, advisor = bundle(SMALL)
    previous = sheet_bytes(build(records, advisor))
    advisor["headNow"] = {"211": {"commit": "1" * 40, "ci": "green"}}
    with pytest.raises(pr_sheet.Refusal):
        build(records, carried_with(advisor, {"211": "1" * 40}, conflictFix=""), previous)
