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
        "blockers": {
            "checked": False, "open": [], "accepted": [], "held": [],
            "requiredDependency": None, "stack": None, "detail": None,
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


PARENT = "repos/acme/widgets/issues/7/parent"
# Measured in a cloud container: `gh api repos/<o>/<r>/issues/<n>/parent` on an issue with no parent.
NO_PARENT = (
    1,
    '{"message":"No parent issue found","documentation_url":'
    '"https://docs.github.com/rest/issues/sub-issues#get-parent-issue","status":"404"}',
    "gh: No parent issue found (HTTP 404)\n",
)


class _Proc:
    def __init__(self, returncode, stdout, stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakeRun:
    """A subprocess.run-shaped fake: argv[2] (the endpoint) -> (returncode, stdout[, stderr]); unknown -> (1, "").

    A graphql call is answered by the key ("graphql", <n>) when its `-F number=<n>` argument has one, else by
    the key "graphql"."""

    def __init__(self, responses=None, raises=None):
        self.responses = responses or {}
        self.raises = raises
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        if self.raises is not None:
            raise self.raises
        key = argv[2]
        if key == "graphql":
            numbers = [arg for arg in argv if isinstance(arg, str) and arg.startswith("number=")]
            if numbers and ("graphql", int(numbers[0].split("=", 1)[1])) in self.responses:
                key = ("graphql", int(numbers[0].split("=", 1)[1]))
        return _Proc(*self.responses.get(key, (1, "")))


def _row(number, state, repo="acme/widgets", title="t"):
    return {
        "number": number,
        "state": state,
        "title": title,
        "html_url": f"https://github.com/{repo}/issues/{number}",
        "repository_url": f"https://api.github.com/repos/{repo}",
    }


def _page1(rows):
    return _FakeRun({PAGE1: (0, json.dumps(rows)), PARENT: NO_PARENT})


def _good_body_file(tmp_path):
    p = tmp_path / "body.md"
    p.write_text(_minimal_body("Anchor (ruling):", "owner ruling 2026-01-01"), encoding="utf-8")
    return str(p)


def _build_ready(tmp_path, capsys, fake, extra=None, members=None):
    argv = ["check-build-ready", "--body-file", _good_body_file(tmp_path)]
    argv += ["--issue", "7", "--repo", "acme/widgets"] if extra is None else extra
    rc = ic.main(argv, run=fake, membership_reader=members)
    assert rc == 0
    return json.loads(capsys.readouterr().out.strip())


def _check_blockers(capsys, fake, argv=None, members=None):
    argv = ["check-blockers", "--issue", "7", "--repo", "acme/widgets"] if argv is None else argv
    rc = ic.main(argv, run=fake, membership_reader=members)
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
    assert fake.calls == [["gh", "api", PAGE1], ["gh", "api", PARENT]]


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
    assert out["blockers"] == {
        "checked": True, "open": [], "accepted": [], "held": [], "requiredDependency": None, "stack": None,
        "detail": None,
    }


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
    assert out["blockers"]["accepted"] == []
    assert out["blockers"]["held"] == []
    assert out["blockers"]["requiredDependency"] is None
    assert out["blockers"]["stack"] is None
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
    fake = _FakeRun({
        PAGE1: (0, json.dumps(full)), PAGE2: (0, json.dumps([_row(12, "open")])), PARENT: NO_PARENT,
    })
    out = _build_ready(tmp_path, capsys, fake)
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert [b["ref"] for b in out["blockers"]["open"]] == ["acme/widgets#12"]
    assert [c[2] for c in fake.calls] == [PAGE1, PAGE2, PARENT]


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
    assert out["blockers"] == {
        "checked": False, "open": [], "accepted": [], "held": [], "requiredDependency": None, "stack": None,
        "detail": None,
    }
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


# --- 9. An open blocker that is a lower layer of the same stack (#2652) -------
#
# Issue 7 of acme/widgets is a sub-issue of feature #50; its blockers are judged against #50's sub-issue
# list, the open pull requests (the PR GitHub links to the blocker), that PR's vet and its stack.

FEATURE = 50
SUBS = "repos/acme/widgets/issues/50/sub_issues?per_page=100&page=1"
PULLS = "repos/acme/widgets/pulls?state=open&per_page=100&page=1"
REPO_PATH = "repos/acme/widgets"
MARKER = "<!-- superheroes:advisor-vet -->"


def _head(n):
    return "%040x" % n


def _vet(verdict, head):
    """A vet slot at `head`, its token and separator read from rubric/vet-verdict-form.json."""
    with open(ic.stack_check._vet_verdict_form_path(), encoding="utf-8") as fh:
        form = json.load(fh)
    token = next(entry["token"] for entry in form["tokens"] if entry["verdict"] == verdict)
    return "%s\n%s%s%s" % (MARKER, token, form["separator"], head)


def _card(head, parent=FEATURE):
    return "%s %s%d" % (_vet("PARKED", head), ic.STACK_CARD_QUALIFIER, parent)


def _pr_row(number, closes=None, vet=None, draft=False, head=None, body=None, base="layer-base", links=None):
    """An open-PR row. `base` is its base branch (default: a stack layer, so its timeline cross-reference is its
    link). `links` are the issue numbers GitHub links to it (default `[closes]`, or none); the fake world reads
    them off the row's "links" key, and the judge ignores that key."""
    head = head or _head(number)
    if body is None:
        body = "Closes #%d\n\n%s" % (closes, vet if vet is not None else _vet("READY", head))
    if links is None:
        links = [closes] if closes is not None else []
    return {
        "number": number, "state": "open", "draft": draft, "head": {"sha": head}, "base": {"ref": base},
        "body": body, "links": list(links),
    }


def _sub(number, repo="acme/widgets"):
    return {"number": number, "repository_url": "https://api.github.com/repos/" + repo}


def _timeline_path(issue):
    return "repos/acme/widgets/issues/%d/timeline?per_page=100&page=1" % issue


def _cross_ref(pr_number, repo="acme/widgets"):
    """A timeline row: pull request `pr_number` of `repo` cross-references the issue."""
    return {
        "event": "cross-referenced",
        "source": {"type": "issue", "issue": {"number": pr_number, "pull_request": {}, "repository": {"full_name": repo}}},
    }


def _closing_answer(numbers, has_next_page=False):
    """A GraphQL closingIssuesReferences answer naming `numbers` of acme/widgets."""
    nodes = [{"number": n, "repository": {"nameWithOwner": "acme/widgets"}} for n in numbers]
    refs = {"pageInfo": {"hasNextPage": has_next_page}, "nodes": nodes}
    return 0, json.dumps({"data": {"repository": {"pullRequest": {"closingIssuesReferences": refs}}}})


def _world(blocked=(12,), subs=(12, 7), prs=(), parent=FEATURE, responses=None, rows=None):
    """A fake gh for issue 7: its blocked_by rows, parent, the parent's sub-issues, the open PRs, the default
    branch, each blocked issue's timeline (one cross-reference per PR row that links it) and the closing
    references of each PR based on the default branch (the issues the row links)."""
    table = {PAGE1: (0, json.dumps(rows if rows is not None else [_row(n, "open") for n in blocked]))}
    table[PARENT] = NO_PARENT if parent is None else (0, json.dumps({"number": parent}))
    if parent is not None:
        table["repos/acme/widgets/issues/%d/sub_issues?per_page=100&page=1" % parent] = (
            0, json.dumps([_sub(n) for n in subs])
        )
    table[PULLS] = (0, json.dumps(list(prs)))
    table[REPO_PATH] = (0, json.dumps({"default_branch": "main"}))
    issues = set(blocked) | {r["number"] for r in (rows or []) if isinstance(r, dict) and _is_plain_int(r.get("number"))}
    pulls = [pr for pr in prs if isinstance(pr, dict) and isinstance(pr.get("links"), list)]
    for issue in issues:
        table[_timeline_path(issue)] = (0, json.dumps([_cross_ref(pr["number"]) for pr in pulls if issue in pr["links"]]))
    for pr in pulls:
        if isinstance(pr.get("base"), dict) and pr["base"].get("ref") == "main":
            table[("graphql", pr["number"])] = _closing_answer(pr["links"])
    table.update(responses or {})
    return _FakeRun(table)


def _is_plain_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _in_stack(stack, position):
    return {"ok": True, "reason": None, "detail": None, "stack": {"number": stack}, "queried": {"position": position}}


NOT_LINKED = {"ok": False, "reason": ic.stack_check.REASON_NOT_LINKED, "detail": "pull request is not in a stack"}
STACK_UNREADABLE = {"ok": False, "reason": ic.stack_check.REASON_STACK_UNREADABLE, "detail": "stackEntry is missing"}


class _Members:
    """A fake membership reader: PR number -> the read dict; records the numbers it was asked for."""

    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, pr, repo, run):
        assert repo == "acme/widgets"
        self.calls.append(pr)
        result = self.table[pr]
        queried = result.get("queried") if isinstance(result, dict) else None
        # A real ok or not-linked membership read names the head it read; default it to the head the world's
        # open-PR list serves for that PR (the PR row's default head when the world lists none).
        listed = json.loads(run.responses.get(PULLS, (0, "[]"))[1]) if isinstance(run, _FakeRun) else []
        head = next((row["head"]["sha"] for row in listed if isinstance(row, dict) and row.get("number") == pr
                     and isinstance(row.get("head"), dict)), _head(pr))
        if isinstance(result, dict) and result.get("ok") is True and isinstance(queried, dict) \
                and "headRefOid" not in queried:
            result = dict(result, queried=dict(queried, headRefOid=head))
        if isinstance(result, dict) and result.get("reason") == ic.stack_check.REASON_NOT_LINKED and queried is None:
            result = dict(result, queried={"headRefOid": head})
        return result


def _premise_file(tmp_path, content):
    path = tmp_path / "premise.json"
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return str(path)


def _judge_cli(capsys, fake, members, tmp_path=None, premise=None):
    argv = ["check-blockers", "--issue", "7", "--repo", "acme/widgets"]
    if premise is not None:
        argv += ["--premise", _premise_file(tmp_path, premise)]
    return _check_blockers(capsys, fake, argv=argv, members=members)


def _held_refs(out):
    return [h["ref"] for h in out["blockers"]["held"]]


def _accepted_refs(out):
    return [a["ref"] for a in out["blockers"]["accepted"]]


def test_ready_lower_layer_as_only_blocker_passes_with_its_accepted_row(tmp_path, capsys):
    fake = _world(blocked=(12,), subs=(12, 7), prs=[_pr_row(101, closes=12)])
    members = _Members({101: _in_stack(900, 1)})
    out = _build_ready(tmp_path, capsys, fake, members=members)
    assert out["ok"] is True
    assert out["reason"] is None
    blockers = out["blockers"]
    assert blockers["checked"] is True
    assert [r["ref"] for r in blockers["open"]] == ["acme/widgets#12"]
    assert blockers["held"] == []
    assert blockers["accepted"] == [{
        "ref": "acme/widgets#12",
        "title": "t",
        "url": "https://github.com/acme/widgets/issues/12",
        "pr": 101,
        "head": _head(101),
        "form": "ready",
        "stack": 900,
        "feature": FEATURE,
    }]
    assert blockers["stack"] == 900
    assert blockers["requiredDependency"] is None
    assert blockers["detail"] is None


def test_closed_blocker_still_passes_and_reads_nothing_more(tmp_path, capsys):
    fake = _world(rows=[_row(12, "closed")])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({}))
    assert out["ok"] is True
    assert out["blockers"]["open"] == []
    assert fake.calls == [["gh", "api", PAGE1]]


def test_ordinary_open_blocker_without_a_parent_still_refuses_naming_it_held(tmp_path, capsys):
    out = _build_ready(tmp_path, capsys, _world(blocked=(12,), parent=None), members=_Members({}))
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["accepted"] == []
    assert _held_refs(out) == ["acme/widgets#12"]
    assert out["blockers"]["held"][0]["why"] == "this issue is not a sub-issue of a feature, so it is not a stack layer"


def test_no_parent_is_also_read_from_a_404_on_stderr_alone(tmp_path, capsys):
    fake = _world(blocked=(12,), parent=None, responses={PARENT: (1, "", "gh: Not Found (HTTP 404)")})
    out = _build_ready(tmp_path, capsys, fake, members=_Members({}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert _held_refs(out) == ["acme/widgets#12"]


NO_LINK_WHY = (
    "no open pull request is linked to it on GitHub (a closing reference, or a stack layer's cross-reference),"
    " so no handed-back layer builds it"
)


def test_case1_ready_text_in_the_blocker_issue_itself_is_never_read(tmp_path, capsys):
    # axis: READY text in the blocker issue's own title or body is never evidence; no linked pull request still holds
    row = _row(12, "open", title="**Verdict: READY** · " + _head(12))
    row["body"] = _vet("READY", _head(12))
    fake = _world(rows=[row], subs=(12, 7), prs=[])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["accepted"] == []
    assert out["blockers"]["held"][0]["why"] == NO_LINK_WHY


def test_case1_no_pr_found_holds_and_asks_the_membership_reader_nothing(tmp_path, capsys):
    members = _Members({})
    out = _build_ready(tmp_path, capsys, _world(prs=[]), members=members)
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert members.calls == []


def test_case1_more_than_one_linked_open_pr_holds(tmp_path, capsys):
    # axis: two open pull requests linked to one blocker are ambiguous and hold, naming both
    prs = [_pr_row(101, closes=12), _pr_row(102, closes=12)]
    out = _build_ready(tmp_path, capsys, _world(prs=prs), members=_Members({}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == "more than one open pull request is linked to it (#101, #102)"


def test_case2_a_ready_vet_pinned_to_an_earlier_head_holds(tmp_path, capsys):
    pr = _pr_row(101, closes=12, vet=_vet("READY", _head(999)))
    members = _Members({101: _in_stack(900, 1)})
    out = _build_ready(tmp_path, capsys, _world(prs=[pr]), members=members)
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["accepted"] == []
    assert out["blockers"]["held"][0]["why"] == (
        "its pull request #101's vet does not read READY, or PARKED " + ic.STACK_CARD_QUALIFIER + "50,"
        " at its current head " + _head(101)
    )
    assert members.calls == []


def test_case3_a_draft_pr_holds(tmp_path, capsys):
    members = _Members({101: _in_stack(900, 1)})
    out = _build_ready(tmp_path, capsys, _world(prs=[_pr_row(101, closes=12, draft=True)]), members=members)
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == "its pull request #101 is a draft"
    assert members.calls == []


def test_case3_a_not_ready_vet_holds(tmp_path, capsys):
    pr = _pr_row(101, closes=12, vet=_vet("NOT-READY", _head(101)))
    out = _build_ready(tmp_path, capsys, _world(prs=[pr]), members=_Members({101: _in_stack(900, 1)}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert "does not read READY" in out["blockers"]["held"][0]["why"]


def test_case3_a_closed_unmerged_pr_is_not_among_the_open_pulls_so_it_holds(tmp_path, capsys):
    out = _build_ready(tmp_path, capsys, _world(prs=[]), members=_Members({}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == NO_LINK_WHY


def test_case4_a_layer_beside_a_non_layer_blocker_refuses_naming_only_the_non_layer_held(tmp_path, capsys):
    fake = _world(blocked=(12, 13), subs=(12, 7), prs=[_pr_row(101, closes=12)])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert _held_refs(out) == ["acme/widgets#13"]
    assert _accepted_refs(out) == ["acme/widgets#12"]
    assert [r["ref"] for r in out["blockers"]["open"]] == ["acme/widgets#12", "acme/widgets#13"]
    assert out["blockers"]["held"][0]["why"] == "it is not a sub-issue of #50, so it is not a layer of this stack"


def test_case5_two_layers_layer_one_ready_and_layer_two_not_holds_layer_two(tmp_path, capsys):
    prs = [_pr_row(101, closes=11), _pr_row(102, closes=12, vet=_vet("NOT-READY", _head(102)))]
    fake = _world(blocked=(11, 12), subs=(11, 12, 7), prs=prs)
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1), 102: _in_stack(900, 2)}))
    assert out["ok"] is False
    assert _accepted_refs(out) == ["acme/widgets#11"]
    assert _held_refs(out) == ["acme/widgets#12"]


def test_case5_both_layers_ready_passes_in_edge_order(tmp_path, capsys):
    prs = [_pr_row(102, closes=12), _pr_row(101, closes=11)]
    fake = _world(blocked=(12, 11), subs=(11, 12, 7), prs=prs)
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1), 102: _in_stack(900, 2)}))
    assert out["ok"] is True
    assert _accepted_refs(out) == ["acme/widgets#12", "acme/widgets#11"]
    assert out["blockers"]["stack"] == 900
    assert out["blockers"]["requiredDependency"] is None


def test_case6_a_blocker_listed_after_the_issue_holds(tmp_path, capsys):
    members = _Members({101: _in_stack(900, 1)})
    fake = _world(blocked=(12,), subs=(7, 12), prs=[_pr_row(101, closes=12)])
    out = _build_ready(tmp_path, capsys, fake, members=members)
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == "it is listed after this issue under #50, so it is not a lower layer"
    assert members.calls == []


def test_case6_a_blocker_that_is_not_a_sub_issue_of_the_same_parent_holds(tmp_path, capsys):
    fake = _world(blocked=(12,), subs=(7,), prs=[_pr_row(101, closes=12)])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == "it is not a sub-issue of #50, so it is not a layer of this stack"


def test_case6_build_ready_lower_layers_in_two_stacks_are_all_held(tmp_path, capsys):
    prs = [_pr_row(101, closes=11), _pr_row(102, closes=12)]
    fake = _world(blocked=(11, 12), subs=(11, 12, 7), prs=prs)
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1), 102: _in_stack(901, 1)}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["accepted"] == []
    assert _held_refs(out) == ["acme/widgets#11", "acme/widgets#12"]
    assert {h["why"] for h in out["blockers"]["held"]} == {"the lower layers sit in more than one stack (900, 901)"}
    assert out["blockers"]["stack"] is None


def test_case6_one_stack_holds_the_layer_that_is_in_no_stack(tmp_path, capsys):
    prs = [_pr_row(101, closes=11), _pr_row(102, closes=12)]
    fake = _world(blocked=(11, 12), subs=(11, 12, 7), prs=prs)
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1), 102: NOT_LINKED}))
    assert _accepted_refs(out) == ["acme/widgets#11"]
    assert _held_refs(out) == ["acme/widgets#12"]
    assert out["blockers"]["held"][0]["why"] == (
        "its pull request #102 is in no stack, while the other lower layers are in stack 900"
    )
    assert out["blockers"]["stack"] == 900


def test_case6_premise_stack_s_with_the_pr_in_stack_x_holds(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _judge_cli(capsys, fake, _Members({101: _in_stack(901, 1)}), tmp_path, {"stack": 900, "layerPosition": 3})
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == "its pull request #101 is in stack 901, not the launch's stack 900"
    assert out["blockers"]["stack"] == 900


def test_case6_premise_stack_with_the_pr_in_no_stack_holds(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _judge_cli(capsys, fake, _Members({101: NOT_LINKED}), tmp_path, {"stack": 900, "layerPosition": 3})
    assert out["blockers"]["held"][0]["why"] == "its pull request #101 is in no stack"


def test_case6_a_position_not_below_the_launch_position_holds(tmp_path, capsys):
    for position in (3, 4):
        fake = _world(prs=[_pr_row(101, closes=12)])
        out = _judge_cli(
            capsys, fake, _Members({101: _in_stack(900, position)}), tmp_path, {"stack": 900, "layerPosition": 3}
        )
        assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
        assert out["blockers"]["held"][0]["why"] == (
            "its pull request #101 is at position %d, not below the launch's position 3" % position
        )


def test_case6_premise_stack_with_a_lower_layer_in_that_stack_passes(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _judge_cli(capsys, fake, _Members({101: _in_stack(900, 2)}), tmp_path, {"stack": 900, "layerPosition": 3})
    assert out["ok"] is True
    assert out["blockers"]["accepted"][0]["stack"] == 900
    assert out["blockers"]["stack"] == 900
    assert out["blockers"]["requiredDependency"] is None


def test_case6_a_blocker_in_another_repository_holds_without_any_further_read(tmp_path, capsys):
    fake = _world(rows=[_row(5, "open", repo="other/lib")])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["ref"] == "other/lib#5"
    assert out["blockers"]["held"][0]["why"] == "it is in another repository, so it is not a layer of this stack"
    assert fake.calls == [["gh", "api", PAGE1]]


def test_case7_build_ready_one_unstacked_ready_lower_layer_passes_with_required_dependency(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: NOT_LINKED}))
    assert out["ok"] is True
    assert out["blockers"]["requiredDependency"] == 101
    assert out["blockers"]["stack"] is None
    assert out["blockers"]["accepted"][0]["stack"] is None


def test_case7_premise_dependency_equal_passes(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _judge_cli(capsys, fake, _Members({101: NOT_LINKED}), tmp_path, {"dependency": 101})
    assert out["ok"] is True
    assert out["blockers"]["requiredDependency"] == 101


def test_case7_premise_dependency_different_holds(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _judge_cli(capsys, fake, _Members({101: NOT_LINKED}), tmp_path, {"dependency": 102})
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == "its pull request #101 is not the launch's dependency #102"
    assert out["blockers"]["requiredDependency"] is None


def test_case7_premise_dependency_but_the_pr_is_in_a_stack_holds(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _judge_cli(capsys, fake, _Members({101: _in_stack(900, 1)}), tmp_path, {"dependency": 101})
    assert out["blockers"]["held"][0]["why"] == (
        "its pull request #101 is in stack 900; the launch premise must name that stack"
    )


def test_case7_premise_with_neither_key_holds(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _judge_cli(capsys, fake, _Members({101: _in_stack(900, 1)}), tmp_path, {"other": 5})
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == (
        "the launch premise names no stack and no dependency, so this launch is not a stack layer"
    )


def test_case7_two_unstacked_lower_layers_both_hold(tmp_path, capsys):
    prs = [_pr_row(101, closes=11), _pr_row(102, closes=12)]
    fake = _world(blocked=(11, 12), subs=(11, 12, 7), prs=prs)
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: NOT_LINKED, 102: NOT_LINKED}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["accepted"] == []
    assert _held_refs(out) == ["acme/widgets#11", "acme/widgets#12"]
    assert out["blockers"]["requiredDependency"] is None
    assert {h["why"] for h in out["blockers"]["held"]} == {
        "more than one lower layer has a pull request but no stack is linked; a launch can depend on only one"
    }


def test_case8_a_stack_card_mark_for_this_parent_passes_as_stack_card(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12, vet=_card(_head(101)))])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["ok"] is True
    assert out["blockers"]["accepted"][0]["form"] == "stack-card"
    assert out["blockers"]["accepted"][0]["pr"] == 101


def test_case8_a_stack_card_mark_for_another_parent_holds_naming_it(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12, vet=_card(_head(101), parent=77))])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"] == (
        "its pull request #101's vet card mark names feature #77, not this stack's #50"
    )


def test_case8_a_plain_parked_line_holds_with_the_reason(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12, vet=_vet("PARKED", _head(101)))])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert "does not read READY, or PARKED " + ic.STACK_CARD_QUALIFIER + "50" in out["blockers"]["held"][0]["why"]


def test_case8_the_card_mark_at_a_stale_head_holds_with_the_reason(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12, vet=_card(_head(999)))])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert out["blockers"]["held"][0]["why"].endswith("at its current head " + _head(101))


def test_stack_card_parent_reads_only_the_exact_mark(tmp_path):
    head = _head(7)
    with open(ic.stack_check._vet_verdict_form_path(), encoding="utf-8") as fh:
        form = json.load(fh)
    # The qualifier's one home is the verdict form; the module reads it from there.
    assert ic.STACK_CARD_QUALIFIER == form["stackCardQualifier"]
    assert ic.stack_card_parent(_card(head, 50), head) == 50
    assert ic.stack_card_parent(_card(head, 50) + " and a note", head) == 50
    assert ic.stack_card_parent(_card(head, 50) + "x", head) is None
    assert ic.stack_card_parent(_card(head, 0), head) is None
    assert ic.stack_card_parent(_card(head, 50), _head(8)) is None
    assert ic.stack_card_parent(_vet("READY", head), head) is None
    assert ic.stack_card_parent(_vet("PARKED", head), head) is None
    qualifier = ic.STACK_CARD_QUALIFIER
    assert ic.stack_card_parent(_card(head, 50).replace(qualifier + "50", qualifier), head) is None
    assert ic.stack_card_parent(_card(head, 50).replace(qualifier, qualifier[0].swapcase() + qualifier[1:]), head) is None
    assert ic.stack_card_parent("no marker at all", head) is None
    assert ic.stack_card_parent(None, head) is None


def test_stack_card_mark_reads_only_a_line_the_vet_parser_reads_as_parked():
    # axis: a card-shaped line the canonical parser rejects (a second verdict token) is no card mark at any head
    head = _head(7)
    ready = next(entry["token"] for entry in json.load(open(ic.stack_check._vet_verdict_form_path()))["tokens"]
                 if entry["verdict"] == "READY")
    assert ic.stack_card_mark(_card(head, 50)) == (head, 50)
    assert ic.stack_card_mark(_card(head, 50) + " " + ready) is None
    assert ic.stack_card_parent(_card(head, 50) + " " + ready, head) is None


def _assert_unreadable_and_no_pass(out):
    _assert_unreadable(out)
    assert out["ok"] is False


def test_case9_a_parent_read_that_fails_otherwise_is_unreadable(tmp_path, capsys):
    for response in ((1, "", "gh: Server Error (HTTP 500)"), (1, "", ""), (1, "not json", "boom")):
        fake = _world(responses={PARENT: response})
        _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=_Members({})))


def test_case9_a_parent_read_that_times_out_or_cannot_start_is_unreadable(tmp_path, capsys):
    import subprocess

    for error in (subprocess.TimeoutExpired(["gh"], 30), OSError("no gh")):
        fake = _FakeRun({PAGE1: (0, json.dumps([_row(12, "open")]))})
        run_calls = []

        def run(argv, **kw):
            run_calls.append(argv[2])
            if argv[2] == PAGE1:
                return fake(argv, **kw)
            raise error

        _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, run, members=_Members({})))
        assert run_calls == [PAGE1, PARENT]


def test_case9_a_parent_answer_without_an_int_number_is_unreadable(tmp_path, capsys):
    for payload in ("[]", '{"number": "50"}', '{"number": true}', '{"title": "x"}', "not json"):
        fake = _world(responses={PARENT: (0, payload)})
        _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=_Members({})))


def test_case9_a_failed_sub_issue_list_read_is_unreadable(tmp_path, capsys):
    fake = _world(responses={SUBS: (1, "", "boom")})
    _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=_Members({})))


def test_case9_a_bad_sub_issue_row_is_unreadable_even_beside_good_rows(tmp_path, capsys):
    bad_rows = (
        "x", {"number": "12", "repository_url": "https://api.github.com/repos/acme/widgets"},
        {"number": True, "repository_url": "https://api.github.com/repos/acme/widgets"},
        {"number": 5}, {"number": 5, "repository_url": "https://api.github.com/acme/widgets"},
    )
    for bad in bad_rows:
        fake = _world(responses={SUBS: (0, json.dumps([_sub(12), bad, _sub(7)]))})
        _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=_Members({})))


def test_case9_the_issue_missing_from_its_parents_list_is_unreadable(tmp_path, capsys):
    out = _build_ready(tmp_path, capsys, _world(subs=(12,), prs=[_pr_row(101, closes=12)]), members=_Members({}))
    _assert_unreadable_and_no_pass(out)
    assert out["blockers"]["detail"] == "the sub-issue list of #50 does not list #7"


def test_case9_a_failed_open_pr_page_read_is_unreadable(tmp_path, capsys):
    fake = _world(responses={PULLS: (1, "", "boom")})
    _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=_Members({})))


def test_case9_a_bad_pr_row_after_a_matching_one_is_unreadable(tmp_path, capsys):
    good = _pr_row(101, closes=12)
    bad_rows = (
        "x",
        dict(_pr_row(102, closes=99), number="102"),
        dict(_pr_row(102, closes=99), state="closed"),
        dict(_pr_row(102, closes=99), draft="no"),
        dict(_pr_row(102, closes=99), head={"sha": "ABC"}),
        dict(_pr_row(102, closes=99), head=None),
        dict(_pr_row(102, closes=99), body=5),
        # axis: an omitted body key is unreadable, unlike an explicit null body (which reads as empty)
        {key: value for key, value in _pr_row(102, closes=99).items() if key != "body"},
    )
    for bad in bad_rows:
        fake = _world(prs=[good, bad])
        members = _Members({101: _in_stack(900, 1)})
        _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=members))
        assert members.calls == []


def test_case9_a_null_pr_body_reads_as_empty_and_holds(tmp_path, capsys):
    row = dict(_pr_row(101, closes=12), body=None)
    out = _build_ready(tmp_path, capsys, _world(prs=[row]), members=_Members({}))
    assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
    assert "does not read READY" in out["blockers"]["held"][0]["why"]


def test_case9_a_vet_form_refusal_is_unreadable_not_not_ready(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(ic.stack_check, "_load_vet_verdict_form", lambda: (None, "vet-verdict-form.json is missing"))
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    _assert_unreadable_and_no_pass(out)
    assert "vet-verdict-form.json is missing" in out["blockers"]["detail"]


def test_case9_a_membership_refusal_other_than_not_linked_is_unreadable(tmp_path, capsys):
    for result in (STACK_UNREADABLE, {"ok": False, "reason": ic.stack_check.REASON_BAD_ARGUMENT, "detail": "x"}, None, "x",
                   {"ok": True, "stack": None, "queried": None},
                   {"ok": True, "stack": {"number": True}, "queried": {"position": 1}}):
        fake = _world(prs=[_pr_row(101, closes=12)])
        _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=_Members({101: result})))


def test_case9_a_failed_read_beside_a_held_row_is_still_unreadable(tmp_path, capsys):
    prs = [_pr_row(101, closes=11), _pr_row(102, closes=12)]
    fake = _world(blocked=(11, 12), subs=(11, 12, 7), prs=prs)
    members = _Members({101: _in_stack(900, 1), 102: STACK_UNREADABLE})
    _assert_unreadable_and_no_pass(_build_ready(tmp_path, capsys, fake, members=members))


def test_the_judge_with_no_open_rows_reads_nothing():
    def run(argv, **kw):
        raise AssertionError("no gh call expected")

    out = ic.judge_open_blockers([], 7, "acme/widgets", run)
    assert out == {
        "checked": True, "open": [], "accepted": [], "held": [], "requiredDependency": None, "stack": None,
        "detail": None,
    }


def test_the_judge_defaults_its_membership_reader_to_stack_check_read_membership(tmp_path, capsys, monkeypatch):
    seen = []

    def fake_membership(**kwargs):
        seen.append(kwargs)
        result = _in_stack(900, 1)
        result["queried"]["headRefOid"] = _head(kwargs["pr"])
        return result

    monkeypatch.setattr(ic.stack_check, "read_membership", fake_membership)
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _build_ready(tmp_path, capsys, fake)
    assert out["ok"] is True
    assert seen == [{"pr": 101, "repo": "acme/widgets", "run": fake}]


def test_every_gh_call_of_the_judge_is_gh_api_with_a_timeout(tmp_path, capsys):
    kwargs_seen = []
    fake = _world(prs=[_pr_row(101, closes=12)])

    def run(argv, **kw):
        kwargs_seen.append((argv[:2], kw))
        return fake(argv, **kw)

    _build_ready(tmp_path, capsys, run, members=_Members({101: _in_stack(900, 1)}))
    # blocked_by, parent, sub-issues, open PRs, default branch, the blocker's timeline (a stack layer: no closing read)
    assert len(kwargs_seen) == 6
    for argv_head, kw in kwargs_seen:
        assert argv_head == ["gh", "api"]
        assert kw == {"capture_output": True, "text": True, "timeout": ic.GH_TIMEOUT_SECONDS}


def test_premise_refusals_each_refuse_blockers_unreadable_and_call_nothing(tmp_path, capsys):
    cases = {
        "bad json": "{not json",
        "empty file": "",
        "not an object": "[1, 2]",
        "a bare number": "5",
        "duplicate key": '{"dependency": 1, "dependency": 1}',
        "lonely stack": json.dumps({"stack": 900}),
        "lonely layerPosition": json.dumps({"layerPosition": 3}),
        "bool dependency": json.dumps({"dependency": True}),
        "bool stack": json.dumps({"stack": True, "layerPosition": 3}),
        "bool layerPosition": json.dumps({"stack": 900, "layerPosition": False}),
        "zero dependency": json.dumps({"dependency": 0}),
        "string stack": json.dumps({"stack": "900", "layerPosition": 3}),
        "null dependency": json.dumps({"dependency": None}),
        "float layerPosition": json.dumps({"stack": 900, "layerPosition": 3.0}),
        "not utf-8": b"\xff\xfe{",
    }
    for name, content in cases.items():
        fake = _world(prs=[_pr_row(101, closes=12)])
        out = _judge_cli(capsys, fake, _Members({101: NOT_LINKED}), tmp_path, content)
        _assert_unreadable_and_no_pass(out)
        assert "--premise" in out["blockers"]["detail"], name
        assert fake.calls == [], name


def test_premise_file_that_does_not_exist_refuses_and_calls_nothing(tmp_path, capsys):
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _check_blockers(
        capsys, fake, members=_Members({}),
        argv=["check-blockers", "--issue", "7", "--repo", "acme/widgets", "--premise", str(tmp_path / "gone.json")],
    )
    _assert_unreadable_and_no_pass(out)
    assert fake.calls == []


def test_premise_reads_only_its_three_keys_and_ignores_the_rest(tmp_path, capsys):
    content = {"dependency": 101, "iphoneCheck": True, "anything": {"nested": [1]}}
    fake = _world(prs=[_pr_row(101, closes=12)])
    out = _judge_cli(capsys, fake, _Members({101: NOT_LINKED}), tmp_path, content)
    assert out["ok"] is True
    assert out["blockers"]["requiredDependency"] == 101


def test_a_premise_does_not_change_a_check_with_no_open_blocker(tmp_path, capsys):
    fake = _world(rows=[_row(12, "closed")])
    out = _judge_cli(capsys, fake, _Members({}), tmp_path, {"dependency": 101})
    assert out["ok"] is True
    assert out["blockers"]["open"] == []
