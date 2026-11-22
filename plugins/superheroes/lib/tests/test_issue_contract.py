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
        "blockers": {"checked": False, "open": [], "detail": None},
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
        ic.REFUSAL_BLOCKER_OPEN,
        ic.REFUSAL_BLOCKERS_UNREADABLE,
    })
    assert ic.SLOT_STATUSES == frozenset({
        ic.SLOT_STATUS_MISSING,
        ic.SLOT_STATUS_EMPTY,
        ic.SLOT_STATUS_FILLED,
        ic.SLOT_STATUS_UNKNOWN,
    })


# --- 8. Native blocker edges (#2619): the build-ready check reads blocked_by --


PAGE1 = "repos/acme/widgets/issues/7/dependencies/blocked_by?per_page=100&page=1"
PAGE2 = "repos/acme/widgets/issues/7/dependencies/blocked_by?per_page=100&page=2"


class _Proc:
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout


class _FakeRun:
    """A subprocess.run-shaped fake: argv[2] (the endpoint) -> (returncode, stdout); unknown -> (1, "")."""

    def __init__(self, responses=None, raises=None):
        self.responses = responses or {}
        self.raises = raises
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        if self.raises is not None:
            raise self.raises
        code, out = self.responses.get(argv[2], (1, ""))
        return _Proc(code, out)


def _row(number, state, repo="acme/widgets", title="t"):
    return {
        "number": number,
        "state": state,
        "title": title,
        "html_url": f"https://github.com/{repo}/issues/{number}",
        "repository_url": f"https://api.github.com/repos/{repo}",
    }


def _page1(rows):
    return _FakeRun({PAGE1: (0, json.dumps(rows))})


def _good_body_file(tmp_path):
    p = tmp_path / "body.md"
    p.write_text(_minimal_body("Anchor (ruling):", "owner ruling 2026-01-01"), encoding="utf-8")
    return str(p)


def _build_ready(tmp_path, capsys, fake, extra=None):
    argv = ["check-build-ready", "--body-file", _good_body_file(tmp_path)]
    argv += ["--issue", "7", "--repo", "acme/widgets"] if extra is None else extra
    rc = ic.main(argv, run=fake)
    assert rc == 0
    return json.loads(capsys.readouterr().out.strip())


def _check_blockers(capsys, fake, argv=None):
    argv = ["check-blockers", "--issue", "7", "--repo", "acme/widgets"] if argv is None else argv
    rc = ic.main(argv, run=fake)
    assert rc == 0
    return json.loads(capsys.readouterr().out.strip())


def test_check_build_ready_refuses_open_native_blocker(tmp_path, capsys):
    fake = _page1([_row(12, "open", title="the blocker")])
    out = _build_ready(tmp_path, capsys, fake)
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["checked"] is True
    assert out["blockers"]["open"][0]["ref"] == "acme/widgets#12"
    assert out["blockers"]["open"][0]["title"] == "the blocker"
    assert out["blockers"]["open"][0]["url"] == "https://github.com/acme/widgets/issues/12"
    assert fake.calls == [["gh", "api", PAGE1]]


def test_closed_native_blocker_passes(tmp_path, capsys):
    out = _build_ready(tmp_path, capsys, _page1([_row(12, "closed")]))
    assert out["ok"] is True
    assert out["reason"] is None
    assert out["blockers"]["checked"] is True
    assert out["blockers"]["open"] == []


def test_no_native_blockers_passes(tmp_path, capsys):
    out = _build_ready(tmp_path, capsys, _page1([]))
    assert out["ok"] is True
    assert out["reason"] is None
    assert out["blockers"] == {"checked": True, "open": [], "detail": None}


def test_mixed_open_and_closed_lists_only_open(tmp_path, capsys):
    out = _build_ready(tmp_path, capsys, _page1([_row(3, "closed"), _row(12, "open"), _row(4, "closed")]))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert [b["ref"] for b in out["blockers"]["open"]] == ["acme/widgets#12"]


def test_cross_repo_open_blocker_names_its_own_repo(tmp_path, capsys):
    out = _build_ready(tmp_path, capsys, _page1([_row(5, "open", repo="other/lib")]))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["open"][0]["ref"] == "other/lib#5"


def _assert_unreadable(out):
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_BLOCKERS_UNREADABLE
    assert out["blockers"]["checked"] is False
    assert out["blockers"]["open"] == []
    assert out["blockers"]["detail"]


def test_edge_read_failure_is_unreadable_not_no_blockers(tmp_path, capsys):
    _assert_unreadable(_build_ready(tmp_path, capsys, _FakeRun({PAGE1: (1, "")})))


def test_non_json_page_is_unreadable(tmp_path, capsys):
    _assert_unreadable(_build_ready(tmp_path, capsys, _FakeRun({PAGE1: (0, "not json")})))


def test_object_page_is_unreadable(tmp_path, capsys):
    _assert_unreadable(_build_ready(tmp_path, capsys, _FakeRun({PAGE1: (0, json.dumps({"message": "x"}))})))


def test_unknown_state_beside_valid_closed_row_is_unreadable(tmp_path, capsys):
    out = _build_ready(tmp_path, capsys, _page1([_row(3, "closed"), _row(4, "merged")]))
    _assert_unreadable(out)
    assert "#4" in out["blockers"]["detail"]
    assert "merged" in out["blockers"]["detail"]


def test_non_string_state_is_unreadable(tmp_path, capsys):
    _assert_unreadable(_build_ready(tmp_path, capsys, _page1([_row(4, 1)])))


def test_missing_state_is_unreadable(tmp_path, capsys):
    row = _row(4, "open")
    del row["state"]
    _assert_unreadable(_build_ready(tmp_path, capsys, _page1([row])))


def test_non_dict_row_is_unreadable(tmp_path, capsys):
    _assert_unreadable(_build_ready(tmp_path, capsys, _page1([_row(3, "closed"), "closed"])))


def test_missing_repository_url_on_open_row_is_unreadable(tmp_path, capsys):
    row = _row(4, "open")
    del row["repository_url"]
    _assert_unreadable(_build_ready(tmp_path, capsys, _page1([row])))


def test_repository_url_without_repos_segment_is_unreadable(tmp_path, capsys):
    row = _row(4, "open")
    row["repository_url"] = "https://api.github.com/acme/widgets"
    _assert_unreadable(_build_ready(tmp_path, capsys, _page1([row])))


def test_non_int_number_is_unreadable(tmp_path, capsys):
    _assert_unreadable(_build_ready(tmp_path, capsys, _page1([_row("4", "open")])))


def test_runner_timeout_is_unreadable(tmp_path, capsys):
    import subprocess

    fake = _FakeRun(raises=subprocess.TimeoutExpired(["gh"], 30))
    _assert_unreadable(_build_ready(tmp_path, capsys, fake))


def test_runner_oserror_is_unreadable(tmp_path, capsys):
    _assert_unreadable(_build_ready(tmp_path, capsys, _FakeRun(raises=OSError("no gh"))))


def test_pagination_reads_page_two_and_finds_the_open_blocker(tmp_path, capsys):
    full = [_row(n, "closed") for n in range(100, 200)]
    fake = _FakeRun({PAGE1: (0, json.dumps(full)), PAGE2: (0, json.dumps([_row(12, "open")]))})
    out = _build_ready(tmp_path, capsys, fake)
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert [b["ref"] for b in out["blockers"]["open"]] == ["acme/widgets#12"]
    assert [c[2] for c in fake.calls] == [PAGE1, PAGE2]


def test_pagination_page_two_failure_is_unreadable(tmp_path, capsys):
    full = [_row(n, "closed") for n in range(100, 200)]
    fake = _FakeRun({PAGE1: (0, json.dumps(full)), PAGE2: (1, "")})
    _assert_unreadable(_build_ready(tmp_path, capsys, fake))


def test_body_refusal_keeps_its_reason_but_blockers_still_read(tmp_path, capsys):
    p = tmp_path / "body.md"
    p.write_text("What: scope\nDoD:\n- outcome\n", encoding="utf-8")
    fake = _page1([_row(12, "open")])
    rc = ic.main(
        ["check-build-ready", "--body-file", str(p), "--issue", "7", "--repo", "acme/widgets"], run=fake
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert out["blockers"]["open"]


def test_bad_or_lonely_edge_arguments_refuse_and_call_nothing(tmp_path, capsys):
    cases = [
        ["--issue", "7"],
        ["--repo", "acme/widgets"],
        ["--issue", "abc", "--repo", "acme/widgets"],
        ["--issue", "0", "--repo", "acme/widgets"],
        ["--issue", "-3", "--repo", "acme/widgets"],
        ["--issue", "7", "--repo", "notarepo"],
    ]
    for extra in cases:
        fake = _page1([])
        out = _build_ready(tmp_path, capsys, fake, extra=extra)
        _assert_unreadable(out)
        assert fake.calls == [], extra


def test_body_only_call_reads_no_edges(tmp_path, capsys):
    fake = _page1([_row(12, "open")])
    out = _build_ready(tmp_path, capsys, fake, extra=[])
    assert out["ok"] is True
    assert out["reason"] is None
    assert out["blockers"] == {"checked": False, "open": [], "detail": None}
    assert fake.calls == []


def test_unreadable_body_file_keeps_body_unreadable_with_blockers_unchecked(tmp_path, capsys):
    fake = _page1([])
    rc = ic.main(
        ["check-build-ready", "--body-file", str(tmp_path / "missing.md"),
         "--issue", "7", "--repo", "acme/widgets"],
        run=fake,
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["reason"] == ic.REFUSAL_BODY_UNREADABLE
    assert out["blockers"]["checked"] is False


def test_check_blockers_verb_open(capsys):
    out = _check_blockers(capsys, _page1([_row(12, "open")]))
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["open"][0]["ref"] == "acme/widgets#12"
    assert out["advisory"] is True


def test_check_blockers_verb_closed(capsys):
    out = _check_blockers(capsys, _page1([_row(12, "closed")]))
    assert out["ok"] is True
    assert out["reason"] is None
    assert out["blockers"]["checked"] is True


def test_check_blockers_verb_read_failure(capsys):
    out = _check_blockers(capsys, _FakeRun({PAGE1: (1, "")}))
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_BLOCKERS_UNREADABLE
    assert out["blockers"]["checked"] is False


def test_check_blockers_verb_missing_or_bad_args(capsys):
    for argv in (
        ["check-blockers"],
        ["check-blockers", "--issue", "7"],
        ["check-blockers", "--repo", "acme/widgets"],
        ["check-blockers", "--issue", "abc", "--repo", "acme/widgets"],
        ["check-blockers", "--issue", "7", "--repo", "notarepo"],
    ):
        fake = _page1([])
        out = _check_blockers(capsys, fake, argv=argv)
        assert out["ok"] is False
        assert out["reason"] == ic.REFUSAL_BLOCKERS_UNREADABLE
        assert out["blockers"]["detail"]
        assert fake.calls == [], argv
