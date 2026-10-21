"""Tests for issue_contract (#932)."""
import json

import pytest

import issue_contract as ic


def _check(body):
    return ic.check_build_ready(body)


def _run_main(body_path):
    return ic.main(["check-build-ready", "--body-file", body_path])


def _minimal_body(anchor_header, anchor_body):
    return (
        f"{anchor_header}\n"
        f"{anchor_body}\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )


# --- 1. Every kind × every carrier parses (six cases) -----------------------


def test_pass_spec_section_plain_header():
    body = _minimal_body(
        "Anchor (spec-section):",
        "front-half-sdlc-core-6181ee · § The issue contract · as-of amendment #4",
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_SPEC_SECTION
    assert result["declaredKinds"] == [ic.KIND_SPEC_SECTION]


def test_pass_spec_section_bold_header():
    body = _minimal_body(
        "**Anchor (spec-section):**",
        "front-half-sdlc-core-6181ee · § The issue contract · as-of amendment #4",
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_SPEC_SECTION
    assert result["declaredKinds"] == [ic.KIND_SPEC_SECTION]


def test_pass_receipt_plain_header():
    body = _minimal_body(
        "Anchor (receipt):",
        "https://github.com/zwrose/superheroes/pull/581#issuecomment-1",
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_RECEIPT
    assert result["declaredKinds"] == [ic.KIND_RECEIPT]


def test_pass_receipt_bold_header():
    body = _minimal_body(
        "**Anchor (receipt):**",
        "https://github.com/zwrose/superheroes/pull/581#issuecomment-1",
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_RECEIPT
    assert result["declaredKinds"] == [ic.KIND_RECEIPT]


def test_pass_ruling_plain_header():
    body = _minimal_body(
        "Anchor (ruling):",
        "2026-08-07 · owner ruling · advisor channel",
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_RULING
    assert result["declaredKinds"] == [ic.KIND_RULING]


def test_pass_ruling_bold_header():
    body = _minimal_body(
        "**Anchor (ruling):**",
        "2026-08-07 · owner ruling · advisor channel",
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_RULING
    assert result["declaredKinds"] == [ic.KIND_RULING]


# --- 2. Each refusal token, once each way -----------------------------------


def test_refusal_anchor_slot_missing():
    result = _check("What: scope\nDoD:\n- outcome")
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_MISSING
    assert result["declaredKinds"] == []


def test_refusal_anchor_kind_missing_bare_anchor():
    result = _check(_minimal_body("Anchor:", "some citation text"))
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_MISSING
    assert result["declaredKinds"] == []


def test_refusal_anchor_kind_missing_empty_parens():
    result = _check(_minimal_body("Anchor ():", "some citation text"))
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_MISSING
    assert result["declaredKinds"] == []


def test_refusal_anchor_kind_multiple_comma_form():
    result = _check(_minimal_body("Anchor (spec-section, receipt):", "citation"))
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_MULTIPLE
    assert result["declaredKinds"] == [ic.KIND_SPEC_SECTION, ic.KIND_RECEIPT]


def test_refusal_anchor_kind_multiple_separate_groups():
    result = _check(_minimal_body("Anchor (spec-section) (receipt):", "citation"))
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_MULTIPLE
    assert result["declaredKinds"] == [ic.KIND_SPEC_SECTION, ic.KIND_RECEIPT]


def test_refusal_anchor_kind_unrecognized_literal_template():
    result = _check(_minimal_body("Anchor (<kind>):", "citation text"))
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_UNRECOGNIZED
    assert result["declaredKinds"] == ["<kind>"]


def test_refusal_anchor_slot_empty():
    body = (
        "Anchor (spec-section):\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_EMPTY
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_EMPTY
    assert result["declaredKinds"] == [ic.KIND_SPEC_SECTION]


def test_refusal_body_unreadable(tmp_path, capsys):
    missing = tmp_path / "nope.md"
    rc = _run_main(str(missing))
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_BODY_UNREADABLE
    assert all(v == ic.SLOT_STATUS_UNKNOWN for v in out["slots"].values())
    assert out["declaredKinds"] == []


# --- 3. Round-3 finding: receipt URL path text must not be classified ---------


def test_pass_receipt_url_path_contains_ruling_word():
    """Round-3 finding: path text containing 'ruling' is not classified — kind is declared."""
    body = _minimal_body(
        "Anchor (receipt):",
        "https://example.com/advisor-ruling-thread/2026-08-07",
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_RECEIPT
    assert result["declaredKinds"] == [ic.KIND_RECEIPT]


def test_pass_receipt_url_path_contains_iso_date():
    """Round-3 finding: path text containing an ISO date is not classified — kind is declared."""
    body = _minimal_body(
        "Anchor (receipt):",
        "https://example.com/archive/2026-08-07/decision",
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_RECEIPT
    assert result["declaredKinds"] == [ic.KIND_RECEIPT]


# --- 4. Precedence: header-form refusals before emptiness -------------------


def test_precedence_bare_anchor_empty_body_reports_kind_missing():
    body = (
        "Anchor:\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_MISSING
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_EMPTY


def test_precedence_multiple_kinds_empty_body_reports_kind_multiple():
    body = (
        "Anchor (spec-section, receipt):\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_MULTIPLE
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_EMPTY


def test_precedence_unrecognized_kind_empty_body_reports_kind_unrecognized():
    body = (
        "Anchor (nonsense):\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_UNRECOGNIZED
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_EMPTY


# --- 5. Citation body is not classified -------------------------------------


def test_receipt_header_spec_section_prose_body_still_receipt():
    body = _minimal_body(
        "Anchor (receipt):",
        "front-half-sdlc-core-6181ee · § The issue contract · as-of amendment #4",
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_RECEIPT
    assert result["declaredKinds"] == [ic.KIND_RECEIPT]


# --- 6. Fenced-code immunity ------------------------------------------------


def test_fenced_code_decoy_reports_anchor_slot_missing():
    body = (
        "```\n"
        "Anchor (spec-section): decoy inside fence\n"
        "```\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert result["declaredKinds"] == []


def test_fenced_code_decoy_ignored_real_header_parsed():
    body = (
        "Anchor (receipt): https://example.com/live\n"
        "```\n"
        "Anchor (spec-section): decoy inside fence\n"
        "```\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_RECEIPT
    assert result["declaredKinds"] == [ic.KIND_RECEIPT]


def test_fence_four_backticks_nested_three_backtick_decoy_reports_anchor_slot_missing():
    body = (
        "````markdown\n"
        "```\n"
        "Anchor (receipt): https://example.com/decoy\n"
        "```\n"
        "````\n"
        "What: real\n"
        "DoD:\n"
        "- x\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert result["declaredKinds"] == []


def test_fence_tilde_inside_backtick_fence_decoy_reports_anchor_slot_missing():
    body = (
        "```markdown\n"
        "~~~\n"
        "Anchor (receipt): https://example.com/decoy\n"
        "~~~\n"
        "```\n"
        "What: real\n"
        "DoD:\n"
        "- x\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert result["declaredKinds"] == []


def test_fenced_trailing_text_closer_decoy_slot_header_stays_missing():
    body = (
        "```\n"
        "```still-code\n"
        "Anchor (spec-section): decoy after fake closer\n"
        "```\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_MISSING
    assert result["declaredKinds"] == []


def test_fence_empty_markdown_fence_reports_anchor_slot_empty():
    body = (
        "Anchor (receipt):\n"
        "```markdown\n"
        "```\n"
        "What: real\n"
        "DoD:\n"
        "- x\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_EMPTY
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_EMPTY
    assert result["declaredKinds"] == [ic.KIND_RECEIPT]


def test_refusal_anchor_kind_unrecognized_uppercase_receipt():
    result = _check(_minimal_body("Anchor (RECEIPT):", "https://example.com/x"))
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_UNRECOGNIZED
    assert result["declaredKinds"] == ["RECEIPT"]


def test_refusal_anchor_kind_unrecognized_mixed_case_spec_section():
    result = _check(_minimal_body("Anchor (Spec-Section):", "citation text"))
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_UNRECOGNIZED
    assert result["declaredKinds"] == ["Spec-Section"]


# --- preserved: slot parsing, CLI, advisory exit ----------------------------


def test_empty_what_and_dod_do_not_block():
    body = (
        "Anchor (spec-section): front-half-sdlc-core-6181ee · section · as-of amendment #0\n"
        "What:\n"
        "DoD:\n"
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["slots"][ic.SLOT_WHAT] == ic.SLOT_STATUS_EMPTY
    assert result["slots"][ic.SLOT_DOD] == ic.SLOT_STATUS_EMPTY


def test_exit_zero_on_refusal(tmp_path):
    body_path = tmp_path / "body.md"
    body_path.write_text("What: only\n", encoding="utf-8")
    rc = _run_main(str(body_path))
    assert rc == 0
    result = _check("What: only\n")
    assert result["ok"] is False


def test_non_utf8_body_file(tmp_path, capsys):
    body_path = tmp_path / "body.md"
    body_path.write_bytes(b"\xff\xfe Anchor: bad\n")
    rc = _run_main(str(body_path))
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_BODY_UNREADABLE
    assert all(v == ic.SLOT_STATUS_UNKNOWN for v in out["slots"].values())


def test_main_happy_path(tmp_path, capsys):
    body = (
        "Anchor (spec-section): front-half-sdlc-core-6181ee · § The issue contract · "
        "as-of amendment #4\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    body_path = tmp_path / "body.md"
    body_path.write_text(body, encoding="utf-8")
    rc = _run_main(str(body_path))
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is True
    assert out["anchorKind"] == ic.KIND_SPEC_SECTION
    assert out["declaredKinds"] == [ic.KIND_SPEC_SECTION]


def test_realistic_whole_body_fixture():
    body = (
        "Anchor (spec-section): front-half-sdlc-core-6181ee · § The issue contract · "
        "as-of amendment #4\n"
        "What: Route the issue-contract build-ready check and its drift guard.\n"
        "DoD:\n"
        "- `pytest` over `plugins/superheroes/lib/tests/test_issue_contract.py` exits 0\n"
    )
    result = _check(body)
    assert result == {
        "ok": True,
        "reason": None,
        "anchorKind": ic.KIND_SPEC_SECTION,
        "declaredKinds": [ic.KIND_SPEC_SECTION],
        "slots": {
            ic.SLOT_ANCHOR: ic.SLOT_STATUS_FILLED,
            ic.SLOT_WHAT: ic.SLOT_STATUS_FILLED,
            ic.SLOT_DOD: ic.SLOT_STATUS_FILLED,
        },
        "advisory": True,
    }


# --- 7. Indented-code-block header guard (WO-940-R2-E1) ---------------------


def test_indent4_fence_around_indent4_anchor_header_reports_anchor_slot_missing():
    body = (
        "    ```\n"
        "    Anchor (spec-section): decoy inside indent-4 fence\n"
        "    ```\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_MISSING


def test_bare_indent4_anchor_header_reports_anchor_slot_missing():
    body = (
        "    Anchor (spec-section): not a live header\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_MISSING


def test_indent3_anchor_header_still_filled_indent4_anchor_header_missing():
    body_indent3 = (
        "   Anchor (spec-section): front-half-sdlc-core-6181ee · section · as-of #0\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result3 = _check(body_indent3)
    assert result3["ok"] is True
    assert result3["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_FILLED

    body_indent4 = (
        "    Anchor (spec-section): not a live header\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result4 = _check(body_indent4)
    assert result4["ok"] is False
    assert result4["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert result4["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_MISSING


def test_tab_indented_anchor_header_reports_anchor_slot_missing():
    body = (
        "\tAnchor (spec-section): not a live header\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_MISSING


def test_indent4_slot_content_preserves_filled_anchor():
    body = (
        "Anchor (spec-section): live header\n"
        "    nested list item under anchor\n"
        "    second indented content line\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_FILLED
    assert result["anchorKind"] == ic.KIND_SPEC_SECTION


def test_unterminated_fence_before_anchor_header_reports_anchor_slot_missing():
    body = (
        "```\n"
        "still inside fence\n"
        "Anchor (spec-section): swallowed header\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert result["slots"][ic.SLOT_ANCHOR] == ic.SLOT_STATUS_MISSING


def test_vocabulary_constants():
    assert ic.SLOTS == (ic.SLOT_ANCHOR, ic.SLOT_WHAT, ic.SLOT_DOD)
    assert ic.ANCHOR_HEADER_FORM == "Anchor (<kind>):"
    assert ic.ANCHOR_KINDS == frozenset({
        ic.KIND_SPEC_SECTION,
        ic.KIND_RECEIPT,
        ic.KIND_RULING,
    })
    assert ic.REFUSALS == frozenset({
        ic.REFUSAL_ANCHOR_SLOT_MISSING,
        ic.REFUSAL_ANCHOR_SLOT_EMPTY,
        ic.REFUSAL_ANCHOR_KIND_MISSING,
        ic.REFUSAL_ANCHOR_KIND_UNRECOGNIZED,
        ic.REFUSAL_ANCHOR_KIND_MULTIPLE,
        ic.REFUSAL_BODY_UNREADABLE,
    })
    assert ic.SLOT_STATUSES == frozenset({
        ic.SLOT_STATUS_MISSING,
        ic.SLOT_STATUS_EMPTY,
        ic.SLOT_STATUS_FILLED,
        ic.SLOT_STATUS_UNKNOWN,
    })


# --- 8. The extra-repositories line (#1948) ---------------------------------
# bite-proof record wo_a_1948_add_repo_grant


def _extras(body):
    return ic.extra_repositories(body)


def _refused(reason):
    return {"ok": False, "reason": reason, "repositories": []}


def test_extras_vocabulary_constants():
    # axis: the line's prefix and the refusal tokens are the contract the docs and the advisor read — pinned as literals — see bite-proof record wo_a_1948_add_repo_grant
    assert ic.EXTRA_REPOSITORIES_LINE == "Extra repositories:"
    assert ic.EXTRA_REPOSITORIES_REFUSALS == frozenset({
        "extra-repositories-line-repeated",
        "extra-repositories-empty",
        "extra-repositories-name-invalid",
        "extra-repositories-name-repeated",
    })


def test_extras_no_line_is_an_ok_empty_list():
    # axis: a body with no extra-repositories line is ok with no repositories — never a refusal — see bite-proof record wo_a_1948_add_repo_grant
    body = _minimal_body("Anchor (receipt):", "https://example.com/x")
    assert _extras(body) == {"ok": True, "reason": None, "repositories": []}


def test_extras_one_line_gives_its_names_in_order_with_whitespace_stripped():
    # axis: one live line yields its comma-separated names in written order, each stripped — see bite-proof record wo_a_1948_add_repo_grant
    body = (
        "Anchor (receipt): https://example.com/x\n"
        "Extra repositories:   zwrose/superheroes ,weekly-eats-hq/weekly-eats  \n"
        "What: scope\n"
    )
    assert _extras(body) == {
        "ok": True,
        "reason": None,
        "repositories": ["zwrose/superheroes", "weekly-eats-hq/weekly-eats"],
    }


def test_extras_one_name_and_an_indent_three_line_are_live():
    # axis: a line indented fewer than 4 columns is still live — the indent gate bites at 4, not earlier — see bite-proof record wo_a_1948_add_repo_grant
    assert _extras("   Extra repositories: a/b\n") == {
        "ok": True, "reason": None, "repositories": ["a/b"],
    }


def test_extras_two_live_lines_are_refused_as_repeated():
    # axis: the line may appear once — two live lines are refused as extra-repositories-line-repeated, never merged — see bite-proof record wo_a_1948_add_repo_grant
    body = "Extra repositories: a/b\nWhat: scope\nExtra repositories: c/d\n"
    assert _extras(body) == _refused(ic.REFUSAL_EXTRA_REPOSITORIES_LINE_REPEATED)


@pytest.mark.parametrize("line", [
    "Extra repositories:",
    "Extra repositories:    ",
    "Extra repositories: a/b,,c/d",
    "Extra repositories: a/b,",
    "Extra repositories: ,a/b",
], ids=["no-value", "blank-value", "empty-item", "trailing-comma", "leading-comma"])
def test_extras_an_empty_value_or_an_empty_item_is_refused_as_empty(line):
    # axis: a line with no value, or an empty item between commas, is refused as extra-repositories-empty — never read as a shorter list — see bite-proof record wo_a_1948_add_repo_grant
    assert _extras(line + "\n") == _refused(ic.REFUSAL_EXTRA_REPOSITORIES_EMPTY)


@pytest.mark.parametrize("name", [
    "a",
    "a/b/c",
    "-a/b",
    "a_b/c",
    "a/",
    "/b",
    "a/..",
    "a/.",
    "a/b c",
    "o" * 40 + "/r",
    "o/" + "r" * 101,
], ids=["no-slash", "three-parts", "leading-hyphen", "underscore-owner", "no-repo", "no-owner",
        "dot-dot", "dot", "inner-space", "owner-40", "repo-101"])
def test_extras_an_invalid_name_is_refused_as_name_invalid(name):
    # axis: every item must be a valid owner/repo name — one bad item refuses the whole line, beside good ones — see bite-proof record wo_a_1948_add_repo_grant
    assert _extras("Extra repositories: zwrose/ok, %s\n" % name) == _refused(
        ic.REFUSAL_EXTRA_REPOSITORIES_NAME_INVALID)


@pytest.mark.parametrize("name", ["o" * 39 + "/" + "r" * 100, "a/.hidden", "A1/b.c_d-e"])
def test_extras_names_at_the_shape_limits_are_accepted(name):
    # axis: the name shape admits GitHub's longest owner (39) and repo (100) and the repo characters . _ - — see bite-proof record wo_a_1948_add_repo_grant
    assert _extras("Extra repositories: %s\n" % name)["repositories"] == [name]


def test_extras_a_name_repeated_in_different_case_is_refused_as_name_repeated():
    # axis: GitHub names are case-insensitive — the same name twice, in any case, is refused as extra-repositories-name-repeated — see bite-proof record wo_a_1948_add_repo_grant
    body = "Extra repositories: Weekly-Eats-HQ/weekly-eats, weekly-eats-hq/WEEKLY-EATS\n"
    assert _extras(body) == _refused(ic.REFUSAL_EXTRA_REPOSITORIES_NAME_REPEATED)


def test_extras_a_fenced_only_example_line_is_no_line():
    # axis: a line inside a fenced block is an example, never live — an example-only body is ok with no repositories — see bite-proof record wo_a_1948_add_repo_grant
    body = (
        "Write it like this:\n"
        "```\n"
        "Extra repositories: owner/repo, owner/other\n"
        "```\n"
    )
    assert _extras(body) == {"ok": True, "reason": None, "repositories": []}


def test_extras_a_fenced_example_beside_a_real_line_leaves_only_the_real_line():
    # axis: a fenced example beside a real line is neither a second live line nor a replacement for it — see bite-proof record wo_a_1948_add_repo_grant
    body = (
        "Extra repositories: zwrose/superheroes\n"
        "```\n"
        "Extra repositories: owner/repo, owner/other\n"
        "```\n"
    )
    assert _extras(body) == {"ok": True, "reason": None, "repositories": ["zwrose/superheroes"]}


def test_extras_an_unterminated_fence_swallows_a_later_line_and_grants_nothing():
    # axis: an unterminated fence swallows every later line — the line after it is not live, so the list is empty and no grant follows — see bite-proof record wo_a_1948_add_repo_grant
    body = (
        "```\n"
        "still inside the fence\n"
        "Extra repositories: zwrose/superheroes\n"
    )
    assert _extras(body) == {"ok": True, "reason": None, "repositories": []}


@pytest.mark.parametrize("prefix", ["    ", "\t", "     "], ids=["four-spaces", "tab", "five-spaces"])
def test_extras_a_line_indented_four_columns_is_not_live(prefix):
    # axis: an indented code block (4+ columns) is never a live extra-repositories line — see bite-proof record wo_a_1948_add_repo_grant
    assert _extras(prefix + "Extra repositories: zwrose/superheroes\n") == {
        "ok": True, "reason": None, "repositories": [],
    }


def test_extras_an_indented_example_beside_a_real_line_is_not_a_second_line():
    # axis: an indented code-block example beside a real line is not counted as a second live line — see bite-proof record wo_a_1948_add_repo_grant
    body = "    Extra repositories: owner/repo\nExtra repositories: zwrose/superheroes\n"
    assert _extras(body) == {"ok": True, "reason": None, "repositories": ["zwrose/superheroes"]}


def _run_extras(body_path):
    return ic.main(["extras", "--body-file", body_path])


def test_extras_cli_prints_one_json_line_and_exits_zero(tmp_path, capsys):
    # axis: the extras verb prints the parser's result as one JSON line and exits 0 — see bite-proof record wo_a_1948_add_repo_grant
    body_path = tmp_path / "body.md"
    body_path.write_text("Extra repositories: zwrose/superheroes, a/b\n", encoding="utf-8")
    rc = _run_extras(str(body_path))
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert json.loads(out) == {
        "ok": True, "reason": None, "repositories": ["zwrose/superheroes", "a/b"],
    }


def test_extras_cli_prints_a_refusal_and_still_exits_zero(tmp_path, capsys):
    # axis: a refusal is the JSON result, never a non-zero exit — see bite-proof record wo_a_1948_add_repo_grant
    body_path = tmp_path / "body.md"
    body_path.write_text("Extra repositories: nope\n", encoding="utf-8")
    rc = _run_extras(str(body_path))
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == _refused(ic.REFUSAL_EXTRA_REPOSITORIES_NAME_INVALID)


def test_extras_cli_on_a_missing_file_is_body_unreadable(tmp_path, capsys):
    # axis: an unreadable body file fails closed as body-unreadable with no repositories, and exits 0 — see bite-proof record wo_a_1948_add_repo_grant
    rc = _run_extras(str(tmp_path / "nope.md"))
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": False, "reason": "body-unreadable", "repositories": [],
    }
