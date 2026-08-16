"""Tests for issue_contract (#932)."""
import json
import os

import pytest

import issue_contract as ic


def _check(body):
    return ic.check_build_ready(body)


def _run_main(body_path):
    return ic.main(["check-build-ready", "--body-file", body_path])


def test_refusal_anchor_slot_missing():
    result = _check("What: scope\nDoD:\n- outcome")
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert result["slots"][ic.SLOT_ANCHOR] == "missing"


def test_refusal_anchor_slot_empty():
    result = _check("Anchor:\nWhat: scope\nDoD:\n- outcome")
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_SLOT_EMPTY
    assert result["slots"][ic.SLOT_ANCHOR] == "empty"


def test_refusal_anchor_kind_unrecognized():
    body = (
        "Anchor: front-half-sdlc-core · The issue contract section\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_UNRECOGNIZED
    assert result["matchedKinds"] == []


def test_refusal_anchor_kind_ambiguous():
    body = (
        "Anchor: 2026-08-07 owner ruling https://example.com/receipt\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is False
    assert result["reason"] == ic.REFUSAL_ANCHOR_KIND_AMBIGUOUS
    assert set(result["matchedKinds"]) == {
        ic.KIND_OWNER_RULING,
        ic.KIND_RECEIPT,
    }


def test_pass_spec_section():
    body = (
        "Anchor: slug · heading · as-of amendment #4\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["reason"] is None
    assert result["anchorKind"] == ic.KIND_SPEC_SECTION
    assert result["matchedKinds"] == [ic.KIND_SPEC_SECTION]


def test_pass_receipt():
    body = (
        "Anchor: https://github.com/zwrose/superheroes/pull/581#issuecomment-1\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_RECEIPT
    assert result["matchedKinds"] == [ic.KIND_RECEIPT]


def test_pass_owner_ruling():
    body = (
        "Anchor: 2026-08-07 · owner ruling · advisor channel\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["anchorKind"] == ic.KIND_OWNER_RULING
    assert result["matchedKinds"] == [ic.KIND_OWNER_RULING]


def test_empty_what_and_dod_do_not_block():
    body = "Anchor: as-of amendment #0\nWhat:\nDoD:\n"
    result = _check(body)
    assert result["ok"] is True
    assert result["slots"][ic.SLOT_WHAT] == "empty"
    assert result["slots"][ic.SLOT_DOD] == "empty"


def test_bold_anchor_header_recognized():
    body = (
        "**Anchor:** as-of amendment #2\n"
        "What: scope\n"
        "DoD:\n"
        "- outcome\n"
    )
    result = _check(body)
    assert result["ok"] is True
    assert result["slots"][ic.SLOT_ANCHOR] == "filled"


def test_exit_zero_on_refusal(tmp_path):
    body_path = tmp_path / "body.md"
    body_path.write_text("What: only\n", encoding="utf-8")
    rc = _run_main(str(body_path))
    assert rc == 0
    result = _check("What: only\n")
    assert result["ok"] is False


def test_missing_body_file(tmp_path, capsys):
    missing = tmp_path / "nope.md"
    rc = _run_main(str(missing))
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is False
    assert out["reason"] == ic.REFUSAL_ANCHOR_SLOT_MISSING
    assert all(v == "missing" for v in out["slots"].values())


def test_realistic_whole_body_fixture():
    body = (
        "Anchor: front-half-sdlc-core-6181ee · The issue contract · as-of amendment #4\n"
        "What: Route the issue-contract build-ready check and its drift guard.\n"
        "DoD:\n"
        "- `pytest` over `plugins/superheroes/lib/tests/test_issue_contract.py` exits 0\n"
    )
    result = _check(body)
    assert result == {
        "ok": True,
        "reason": None,
        "anchorKind": ic.KIND_SPEC_SECTION,
        "matchedKinds": [ic.KIND_SPEC_SECTION],
        "slots": {
            ic.SLOT_ANCHOR: "filled",
            ic.SLOT_WHAT: "filled",
            ic.SLOT_DOD: "filled",
        },
        "advisory": True,
    }


def test_vocabulary_constants():
    assert ic.SLOTS == (ic.SLOT_ANCHOR, ic.SLOT_WHAT, ic.SLOT_DOD)
    assert ic.ANCHOR_KINDS == frozenset({
        ic.KIND_SPEC_SECTION,
        ic.KIND_RECEIPT,
        ic.KIND_OWNER_RULING,
    })
    assert ic.REFUSALS == frozenset({
        ic.REFUSAL_ANCHOR_SLOT_MISSING,
        ic.REFUSAL_ANCHOR_SLOT_EMPTY,
        ic.REFUSAL_ANCHOR_KIND_UNRECOGNIZED,
        ic.REFUSAL_ANCHOR_KIND_AMBIGUOUS,
    })
