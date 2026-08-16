"""Tests for register_check (#940)."""
import json
import os
import subprocess
import sys

import pytest

import register_check as rc

_HERE = os.path.dirname(os.path.abspath(__file__))
_MODULE = os.path.join(os.path.dirname(_HERE), "register_check.py")
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
_LIVE_REGISTER = os.path.join(
    _REPO_ROOT,
    "docs",
    "superheroes",
    "front-half-sdlc-core-6181ee",
    "register.md",
)


def _check(register_path, body_path, child, allow_no_required_entries=False):
    return rc.check_body(
        register_path,
        body_path,
        child,
        allow_no_required_entries=allow_no_required_entries,
    )


def _run_cli(*args):
    cmd = [sys.executable, "-B", _MODULE, "check", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _minimal_register(tmp_path, body, name="register.md"):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _blockquote_lines(quotable_lines):
    return "\n".join(f"> {line}" for line in quotable_lines)


def _load_live_entries():
    if not os.path.isfile(_LIVE_REGISTER):
        return None
    entries, reason, _line, _detail = rc.load_register(_LIVE_REGISTER)
    if entries is None:
        pytest.fail(f"live register unreadable or malformed: {reason}")
    return entries


def _entry_quotable(entry_id, entries):
    for entry in entries:
        if entry["id"] == entry_id:
            return entry["quotable_lines"]
    raise KeyError(entry_id)


# --- live register census ---------------------------------------------------


def test_live_register_census():
    if not os.path.isfile(_LIVE_REGISTER):
        pytest.skip("live register not present in this checkout")
    entries, reason, _line, _detail = rc.load_register(_LIVE_REGISTER)
    assert reason is None
    assert [entry["id"] for entry in entries] == [
        f"R{i}" for i in range(1, 10)
    ]
    for entry in entries:
        assert entry["quotable_lines"]
        for line in entry["quotable_lines"]:
            assert not (
                line.startswith("*") and not line.startswith("**")
            ), f"{entry['id']} quotable contains italic metadata line"
        assert entry["consumers_text"] is not None


# --- real consumer shapes ---------------------------------------------------


def test_real_consumer_shape_c9(tmp_path):
    entries = _load_live_entries()
    if entries is None:
        pytest.skip("live register not present in this checkout")
    r3 = _entry_quotable("R3", entries)
    register = _minimal_register(
        tmp_path,
        open(_LIVE_REGISTER, encoding="utf-8").read(),
        "register.md",
    )
    body = tmp_path / "c9.md"
    body.write_text(
        "Register text consumed (verbatim):\n\n"
        f"{_blockquote_lines(r3)}\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C9")
    assert result["result"] == rc.RESULT_PASS
    assert result["requiredEntries"] == ["R3"]
    assert result["quotedEntries"] == ["R3"]


def test_real_consumer_shape_detective_child(tmp_path):
    entries = _load_live_entries()
    if entries is None:
        pytest.skip("live register not present in this checkout")
    r9 = _entry_quotable("R9", entries)
    register = _minimal_register(
        tmp_path,
        open(_LIVE_REGISTER, encoding="utf-8").read(),
    )
    body = tmp_path / "detective.md"
    body.write_text(
        "This child quotes the epic register front-half-sdlc-core-6181ee.\n\n"
        f"{_blockquote_lines(r9)}\n",
        encoding="utf-8",
    )
    result = _check(register, body, "the detective child")
    assert result["result"] == rc.RESULT_PASS
    assert result["requiredEntries"] == ["R9"]


# --- drift and normalization ------------------------------------------------


def _tiny_register(tmp_path):
    text = (
        "**R1 — One line entry.**\n"
        "*Consumers:* C1\n"
    )
    return _minimal_register(tmp_path, text)


def test_one_byte_drift(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text(
        "> **R1 — One line entry.X**\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["kind"] == rc.KIND_TEXT_DRIFT
    assert finding["line"] == 1
    assert finding["column"] == 23
    assert finding["expected"] == "**R1 — One line entry.**"
    assert finding["actual"] == "**R1 — One line entry.X**"
    assert result["firstDifference"] == finding


def test_extra_quoted_line_prefix_case(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — Line one.**\n"
        "Second quotable line.\n"
        "*Consumers:* C1\n",
    )
    body = tmp_path / "body.md"
    body.write_text(
        "> **R1 — Line one.**\n"
        "> Second quotable line.\n"
        "> Extra line.\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    finding = result["findings"][0]
    assert finding["kind"] == rc.KIND_TEXT_DRIFT
    assert finding["line"] == 3
    assert finding["column"] is None
    assert finding["expected"] is None
    assert finding["actual"] == "Extra line."
    assert "quoted block has 3 lines" in finding["detail"]


def test_dropped_quoted_line_prefix_case(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — Line one.**\n"
        "Second quotable line.\n"
        "*Consumers:* C1\n",
    )
    body = tmp_path / "body.md"
    body.write_text("> **R1 — Line one.**\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    finding = result["findings"][0]
    assert finding["kind"] == rc.KIND_TEXT_DRIFT
    assert finding["line"] == 2
    assert finding["expected"] == "Second quotable line."
    assert finding["actual"] is None
    assert "register entry has 2" in finding["detail"]


def test_trailing_space_drift(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.** \n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    assert result["findings"][0]["kind"] == rc.KIND_TEXT_DRIFT


def test_trailing_tab_drift(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\t\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    assert result["findings"][0]["kind"] == rc.KIND_TEXT_DRIFT


def test_crlf_body_against_lf_register(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_bytes(
        b"> **R1 \xe2\x80\x94 One line entry.**\r\n",
    )
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_PASS


def test_crlf_register_against_lf_body(tmp_path):
    register = tmp_path / "register.md"
    register.write_bytes(
        b"**R1 \xe2\x80\x94 One line entry.**\r\n"
        b"*Consumers:* C1\r\n",
    )
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_PASS


# --- completeness and boundaries --------------------------------------------


def test_missing_required_quote(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("No quotes here.\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    assert result["findings"] == [{
        "kind": rc.KIND_MISSING_QUOTE,
        "entry": "R1",
        "line": None,
        "column": None,
        "expected": None,
        "actual": None,
        "detail": (
            "R1: required by child C1 (named on its Consumers line) "
            "but not quoted in the body"
        ),
    }]
    assert result["firstDifference"] is None


def test_boundary_matching_c10_not_c1(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — Entry.**\n*Consumers:* C10\n",
    )
    body = tmp_path / "body.md"
    body.write_text("> **R1 — Entry.**\n", encoding="utf-8")
    result = _check(register, body, "C1", allow_no_required_entries=True)
    assert result["result"] == rc.RESULT_PASS
    assert result["requiredEntries"] == []


def test_boundary_child_unrecognized_c09(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "C09")
    assert result["result"] == rc.RESULT_UNRUNNABLE
    assert result["reason"] == rc.UNRUNNABLE_CHILD_UNRECOGNIZED


def test_boundary_child_unrecognized_detective_child(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "detective child")
    assert result["result"] == rc.RESULT_UNRUNNABLE
    assert result["reason"] == rc.UNRUNNABLE_CHILD_UNRECOGNIZED


# --- fences -----------------------------------------------------------------


def test_fenced_decoy_missing_quote(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text(
        "```\n"
        "> **R1 — One line entry.**\n"
        "```\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    assert result["findings"][0]["kind"] == rc.KIND_MISSING_QUOTE


def test_fenced_decoy_unknown_entry_not_reported(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text(
        "~~~\n"
        "> **R99 — Unknown.**\n"
        "~~~\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C1")
    assert all(f["kind"] != rc.KIND_UNKNOWN_ENTRY for f in result["findings"])


# --- unknown / duplicate quotes ---------------------------------------------


def test_unknown_entry_outside_fence(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R99 — Unknown entry.**\n", encoding="utf-8")
    result = _check(register, body, "NOCHILD", allow_no_required_entries=True)
    assert result["result"] == rc.RESULT_FAIL
    assert result["findings"][0]["kind"] == rc.KIND_UNKNOWN_ENTRY


def test_duplicate_exact_quotes_pass(tmp_path):
    register = _tiny_register(tmp_path)
    quote = "> **R1 — One line entry.**\n"
    body = tmp_path / "body.md"
    body.write_text(quote + "\n\n" + quote, encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_PASS
    assert result["duplicateQuoteIds"] == ["R1"]


def test_duplicate_one_drifted(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text(
        "> **R1 — One line entry.**\n"
        "> **R1 — One line entry.X**\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    assert result["findings"][0]["kind"] == rc.KIND_TEXT_DRIFT


# --- malformed register -----------------------------------------------------


def test_malformed_duplicate_entry_id(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — First.**\n*Consumers:* C1\n\n"
        "**R1 — Second.**\n*Consumers:* C1\n",
    )
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_UNRUNNABLE
    assert result["reason"] == rc.UNRUNNABLE_REGISTER_MALFORMED
    assert "line 4" in result["detail"]


def test_malformed_consumers_before_header(tmp_path):
    register = _minimal_register(tmp_path, "*Consumers:* C1\n")
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["reason"] == rc.UNRUNNABLE_REGISTER_MALFORMED
    assert "line 1" in result["detail"]


def test_malformed_multiple_consumers_lines(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — Entry.**\n"
        "*Consumers:* C1\n"
        "*Consumers:* C1 again\n",
    )
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["reason"] == rc.UNRUNNABLE_REGISTER_MALFORMED
    assert "line 3" in result["detail"]


def test_malformed_empty_quotable_text(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — \n*Consumers:* C1\n",
    )
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["reason"] == rc.UNRUNNABLE_REGISTER_MALFORMED
    assert "empty quotable text" in result["detail"]


# --- unreadable / empty -----------------------------------------------------


def test_register_empty(tmp_path):
    register = _minimal_register(tmp_path, "# no entries\n")
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["reason"] == rc.UNRUNNABLE_REGISTER_EMPTY


def test_register_unreadable(tmp_path):
    register = tmp_path / "register.md"
    register.write_bytes(b"\xff\xfe")
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["reason"] == rc.UNRUNNABLE_REGISTER_UNREADABLE


def test_body_unreadable(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_bytes(b"\xff\xfe")
    result = _check(register, body, "C1")
    assert result["reason"] == rc.UNRUNNABLE_BODY_UNREADABLE


# --- entry without consumers ------------------------------------------------


def test_entry_without_consumers_not_required(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — Has consumers.**\n*Consumers:* C1\n\n"
        "**R2 — No consumers line.**\n",
    )
    body = tmp_path / "body.md"
    body.write_text("> **R1 — Has consumers.**\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_PASS
    assert result["entriesWithoutConsumers"] == ["R2"]


# --- CLI seam ---------------------------------------------------------------


def test_cli_passing_pair(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    code, out, _err = _run_cli(
        "--register", str(register),
        "--body-file", str(body),
        "--child", "C1",
    )
    assert code == rc.EXIT_PASS
    payload = json.loads(out.strip())
    assert payload["result"] == rc.RESULT_PASS


def test_cli_drifted_pair(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.X**\n", encoding="utf-8")
    code, out, _err = _run_cli(
        "--register", str(register),
        "--body-file", str(body),
        "--child", "C1",
    )
    assert code == rc.EXIT_FAIL
    payload = json.loads(out.strip())
    assert payload["result"] == rc.RESULT_FAIL


def test_cli_unreadable_register(tmp_path):
    register = tmp_path / "register.md"
    register.write_bytes(b"\xff\xfe")
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    code, out, _err = _run_cli(
        "--register", str(register),
        "--body-file", str(body),
        "--child", "C1",
    )
    assert code == rc.EXIT_UNRUNNABLE
    payload = json.loads(out.strip())
    assert payload["reason"] == rc.UNRUNNABLE_REGISTER_UNREADABLE


def test_cli_bad_flag(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    code, out, _err = _run_cli(
        "--register", str(register),
        "--body-file", str(body),
        "--child", "C1",
        "--nope",
    )
    assert code == rc.EXIT_UNRUNNABLE
    payload = json.loads(out.strip())
    assert payload["reason"] == rc.UNRUNNABLE_USAGE


def test_cli_missing_required_flag(tmp_path):
    code, out, _err = _run_cli("--child", "C1")
    assert code == rc.EXIT_UNRUNNABLE
    payload = json.loads(out.strip())
    assert payload["reason"] == rc.UNRUNNABLE_USAGE
    assert payload["child"] == "C1"


# --- determinism ------------------------------------------------------------


def test_deterministic_stdout(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    code1, out1, _err1 = _run_cli(
        "--register", str(register),
        "--body-file", str(body),
        "--child", "C1",
    )
    code2, out2, _err2 = _run_cli(
        "--register", str(register),
        "--body-file", str(body),
        "--child", "C1",
    )
    assert code1 == code2 == rc.EXIT_PASS
    assert out1 == out2


def test_vocabulary_constants():
    assert rc.SCHEMA == "register-check/1"
    assert rc.RESULTS == frozenset({
        rc.RESULT_PASS,
        rc.RESULT_FAIL,
        rc.RESULT_UNRUNNABLE,
    })
    assert rc.FINDING_KINDS == frozenset({
        rc.KIND_TEXT_DRIFT,
        rc.KIND_MISSING_QUOTE,
        rc.KIND_UNKNOWN_ENTRY,
    })
    assert rc.UNRUNNABLE_REASONS == frozenset({
        rc.UNRUNNABLE_REGISTER_UNREADABLE,
        rc.UNRUNNABLE_BODY_UNREADABLE,
        rc.UNRUNNABLE_REGISTER_EMPTY,
        rc.UNRUNNABLE_REGISTER_MALFORMED,
        rc.UNRUNNABLE_CHILD_UNRECOGNIZED,
        rc.UNRUNNABLE_USAGE,
        rc.UNRUNNABLE_INTERNAL_ERROR,
    })
    assert rc.EXIT_PASS == 0
    assert rc.EXIT_FAIL == 1
    assert rc.EXIT_UNRUNNABLE == 2
