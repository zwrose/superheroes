"""Tests for issue_contract (#932)."""
import json

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
