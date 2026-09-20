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


def _check(
    register_path,
    body_path,
    child,
    allow_no_required_entries=False,
    register_copy=rc.REGISTER_COPY_AUTO,
):
    return rc.check_body(
        register_path,
        body_path,
        child,
        allow_no_required_entries=allow_no_required_entries,
        register_copy=register_copy,
    )


def _run_cli(*args):
    cmd = [sys.executable, "-B", _MODULE, "check", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _run_raw_cli(*args):
    cmd = [sys.executable, "-B", _MODULE, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _stdout_has_no_json(stdout):
    text = stdout.strip()
    if not text:
        return True
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return True
    return False


def _assert_result_field_keys(result):
    assert set(result.keys()) == set(rc.RESULT_FIELDS)


def _assert_finding_field_keys(finding):
    assert set(finding.keys()) == set(rc.FINDING_FIELDS)


def _minimal_register(tmp_path, body, name="register.md"):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _blockquote_lines(quotable_lines):
    return "\n".join(f"> {line}" for line in quotable_lines)


def _load_live_entries():
    assert os.path.isfile(_LIVE_REGISTER), (
        "live register missing at %s — the register-check real-shape tests "
        "are unproven without it" % _LIVE_REGISTER
    )
    entries, reason, _line, _detail, *_rest = rc.load_register(
        _LIVE_REGISTER,
        register_copy=rc.REGISTER_COPY_WORKTREE,
    )
    if entries is None:
        pytest.fail(f"live register unreadable or malformed: {reason}")
    return entries


def _assert_live_register_quotables_are_single_paragraph():
    with open(_LIVE_REGISTER, encoding="utf-8", newline="") as fh:
        text = fh.read()
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]

    entries, reason, _line, _detail, *_rest = rc.load_register(
        _LIVE_REGISTER,
        register_copy=rc.REGISTER_COPY_WORKTREE,
    )
    assert reason is None
    for entry in entries:
        j = entry["header_line"]
        while j < len(lines):
            line = lines[j]
            if not line.strip():
                pytest.fail(
                    "%s quotable text spans a blank line in the register "
                    "(line %d) — a register entry written as two paragraphs "
                    "needs the parser's stop rule revisited, not this test "
                    "relaxed" % (entry["id"], j + 1)
                )
            if line.startswith("*Consumers:"):
                break
            if line.startswith("*") and not line.startswith("**"):
                break
            if rc.ENTRY_HEADER_RE.match(line):
                break
            j += 1


def _entry_quotable(entry_id, entries):
    for entry in entries:
        if entry["id"] == entry_id:
            return entry["quotable_lines"]
    raise KeyError(entry_id)


# --- live register census ---------------------------------------------------


def test_live_register_census():
    assert os.path.isfile(_LIVE_REGISTER), (
        "live register missing at %s — the register-check real-shape tests "
        "are unproven without it" % _LIVE_REGISTER
    )
    entries, reason, _line, _detail, *_rest = rc.load_register(
        _LIVE_REGISTER,
        register_copy=rc.REGISTER_COPY_WORKTREE,
    )
    assert reason is None
    ids = [entry["id"] for entry in entries]
    assert ids, "live register has no entries"
    assert ids == ["R%d" % i for i in range(1, len(ids) + 1)]
    for entry in entries:
        assert entry["quotable_lines"]
        for line in entry["quotable_lines"]:
            assert not (
                line.startswith("*") and not line.startswith("**")
            ), f"{entry['id']} quotable contains italic metadata line"
        assert entry["consumers_text"] is not None
    _assert_live_register_quotables_are_single_paragraph()


# --- real consumer shapes ---------------------------------------------------


def test_real_consumer_shape_c9(tmp_path):
    entries = _load_live_entries()
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


def test_blockquote_no_space_after_gt_passes(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text(">**R1 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_PASS
    _assert_result_field_keys(result)


def test_blockquote_two_spaces_after_gt_drift(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — Line one.**\n"
        "Second quotable line.\n"
        "*Consumers:* C1\n",
    )
    body = tmp_path / "body.md"
    body.write_text(
        "> **R1 — Line one.**\n"
        ">  Second quotable line.\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    assert result["findings"][0]["kind"] == rc.KIND_TEXT_DRIFT
    _assert_result_field_keys(result)
    _assert_finding_field_keys(result["findings"][0])


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


def test_boundary_child_unrecognized_c1_against_c10_consumers(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — Entry.**\n*Consumers:* C10\n",
    )
    body = tmp_path / "body.md"
    body.write_text("> **R1 — Entry.**\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_CHILD_UNRECOGNIZED


def test_boundary_child_unrecognized_c09(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — One line entry.**\n*Consumers:* C9\n",
    )
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "C09")
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_CHILD_UNRECOGNIZED


def test_boundary_child_unrecognized_c10_against_c1_consumers(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "C10")
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_CHILD_UNRECOGNIZED


def test_boundary_child_unrecognized_detective_child(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "detective child")
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_CHILD_UNRECOGNIZED


# --- fences -----------------------------------------------------------------


def test_blockquote_without_entry_header_not_collected(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text(
        "> Some ordinary quoted prose.\n"
        "> Continuing the paragraph.\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C1")
    assert result["quotedEntries"] == []
    assert result["result"] == rc.RESULT_FAIL
    assert result["findings"][0]["kind"] == rc.KIND_MISSING_QUOTE
    assert result["findings"][0]["entry"] == "R1"
    assert all(f["kind"] != rc.KIND_UNKNOWN_ENTRY for f in result["findings"])


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


def test_fenced_example_does_not_satisfy_required_quote(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text(
        "```\n"
        "> **R1 — One line entry.**\n"
        "```still-code\n"
        "more lines\n"
        "```\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    assert result["quotedEntries"] == []
    assert result["findings"][0]["kind"] == rc.KIND_MISSING_QUOTE


def test_fenced_decoy_unknown_entry_not_reported(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text(
        "~~~\n"
        "> **R99 — Unknown.**\n"
        "~~~\n"
        "> **R1 — One line entry.**\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C1")
    assert all(f["kind"] != rc.KIND_UNKNOWN_ENTRY for f in result["findings"])
    assert result["result"] == rc.RESULT_PASS
    assert result["quotedEntries"] == ["R1"]


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
        "\n"
        "> **R1 — One line entry.X**\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    assert result["duplicateQuoteIds"] == ["R1"]
    assert len(result["findings"]) == 1
    assert result["findings"][0]["kind"] == rc.KIND_TEXT_DRIFT


def test_wrong_id_exact_text(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R2 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_FAIL
    assert len(result["findings"]) == 2
    assert result["findings"][0]["kind"] == rc.KIND_MISSING_QUOTE
    assert result["findings"][0]["entry"] == "R1"
    assert result["findings"][1]["kind"] == rc.KIND_UNKNOWN_ENTRY
    assert result["findings"][1]["entry"] == "R2"


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
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_REGISTER_MALFORMED
    assert "line 4" in result["detail"]


def test_malformed_consumers_before_header(tmp_path):
    register = _minimal_register(tmp_path, "*Consumers:* C1\n")
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["reason"] == rc.UNDECIDED_REGISTER_MALFORMED
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
    assert result["reason"] == rc.UNDECIDED_REGISTER_MALFORMED
    assert "line 3" in result["detail"]


def test_malformed_empty_quotable_text(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — \n*Consumers:* C1\n",
    )
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["reason"] == rc.UNDECIDED_REGISTER_MALFORMED
    assert "empty quotable text" in result["detail"]


def test_malformed_body_unterminated_fence(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text(
        "```\n"
        "fence content\n",
        encoding="utf-8",
    )
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_BODY_MALFORMED
    assert "body line 1:" in result["detail"]
    assert "unterminated code fence" in result["detail"]


def test_malformed_unterminated_fence(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — Entry.**\n"
        "```\n"
        "fence content\n",
    )
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_REGISTER_MALFORMED
    assert "unterminated code fence" in result["detail"]
    assert "register line 2:" in result["detail"]
    _assert_result_field_keys(result)


def test_malformed_four_tick_fence_closed_by_three(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — Entry.**\n"
        "````\n"
        "fence content\n"
        "```\n",
    )
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_REGISTER_MALFORMED
    assert "unterminated code fence" in result["detail"]
    assert "register line 2:" in result["detail"]


def test_terminated_fence_parses_later_entries(tmp_path):
    register = _minimal_register(
        tmp_path,
        "```\n"
        "ignored\n"
        "```\n\n"
        "**R1 — One line entry.**\n"
        "*Consumers:* C1\n",
    )
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["result"] == rc.RESULT_PASS
    _assert_result_field_keys(result)


# --- unreadable / empty -----------------------------------------------------


def test_register_empty(tmp_path):
    register = _minimal_register(tmp_path, "# no entries\n")
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["reason"] == rc.UNDECIDED_REGISTER_EMPTY


def test_register_unreadable(tmp_path):
    register = tmp_path / "register.md"
    register.write_bytes(b"\xff\xfe")
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["reason"] == rc.UNDECIDED_REGISTER_UNREADABLE


def test_body_unreadable(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_bytes(b"\xff\xfe")
    result = _check(register, body, "C1")
    assert result["reason"] == rc.UNDECIDED_BODY_UNREADABLE


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


@pytest.mark.parametrize("child", [None, "", "   ", "\t"])
def test_check_body_blank_child_guard(tmp_path, child):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")
    result = rc.check_body(str(register), str(body), child)
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_USAGE


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
    assert code == rc.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == rc.UNDECIDED_REGISTER_UNREADABLE


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
    assert code == rc.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == rc.UNDECIDED_USAGE


def test_cli_missing_required_flag(tmp_path):
    code, out, _err = _run_cli("--child", "C1")
    assert code == rc.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == rc.UNDECIDED_USAGE
    assert payload["child"] == "C1"
    _assert_result_field_keys(payload)


def test_cli_unknown_subcommand():
    code, out, _err = _run_raw_cli("bogus")
    assert code == rc.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == rc.UNDECIDED_USAGE
    _assert_result_field_keys(payload)


def test_cli_no_subcommand():
    code, out, _err = _run_raw_cli()
    assert code == rc.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == rc.UNDECIDED_USAGE
    _assert_result_field_keys(payload)


def test_cli_help_exits_zero_without_json():
    code, out, _err = _run_raw_cli("--help")
    assert code == rc.EXIT_PASS
    assert out.strip()
    assert _stdout_has_no_json(out)


def test_cli_check_help_exits_zero_without_json():
    code, out, _err = _run_raw_cli("check", "--help")
    assert code == rc.EXIT_PASS
    assert out.strip()
    assert _stdout_has_no_json(out)


def test_internal_error(monkeypatch, tmp_path, capsys):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("x\n", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise RuntimeError("probe")

    monkeypatch.setattr(rc, "check_body", boom)
    code = rc.main([
        "check",
        "--register", str(register),
        "--body-file", str(body),
        "--child", "C1",
    ])
    out = capsys.readouterr().out
    assert code == rc.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == rc.UNDECIDED_INTERNAL_ERROR
    _assert_result_field_keys(payload)


def test_emitted_objects_use_authoritative_field_sets(tmp_path):
    register = _tiny_register(tmp_path)
    pass_body = tmp_path / "pass.md"
    pass_body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    pass_result = _check(register, pass_body, "C1")
    _assert_result_field_keys(pass_result)

    drift_body = tmp_path / "drift.md"
    drift_body.write_text("> **R1 — One line entry.X**\n", encoding="utf-8")
    drift_result = _check(register, drift_body, "C1")
    _assert_result_field_keys(drift_result)
    _assert_finding_field_keys(drift_result["findings"][0])

    missing_body = tmp_path / "missing.md"
    missing_body.write_text("No quotes here.\n", encoding="utf-8")
    missing_result = _check(register, missing_body, "C1")
    _assert_result_field_keys(missing_result)
    _assert_finding_field_keys(missing_result["findings"][0])

    unknown_body = tmp_path / "unknown.md"
    unknown_body.write_text("> **R99 — Unknown entry.**\n", encoding="utf-8")
    unknown_result = _check(
        register, unknown_body, "NOCHILD", allow_no_required_entries=True,
    )
    _assert_result_field_keys(unknown_result)
    _assert_finding_field_keys(unknown_result["findings"][0])

    undecided_body = tmp_path / "undecided.md"
    undecided_body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    undecided_result = _check(register, undecided_body, "C09")
    _assert_result_field_keys(undecided_result)


# --- determinism ------------------------------------------------------------


def test_deterministic_stdout(tmp_path):
    register = _minimal_register(
        tmp_path,
        "**R1 — Required entry.**\n*Consumers:* C1\n"
        "**R2 — Also required.**\n*Consumers:* C1\n",
    )
    body = tmp_path / "body.md"
    body.write_text(
        "> **R1 — Required entry.X**\n"
        "\n"
        "> **R99 — Unknown.**\n",
        encoding="utf-8",
    )
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
    assert code1 == code2 == rc.EXIT_FAIL
    assert out1 == out2
    payload = json.loads(out1.strip())
    findings_seq = [(f["kind"], f["entry"]) for f in payload["findings"]]
    assert findings_seq == [
        (rc.KIND_TEXT_DRIFT, "R1"),
        (rc.KIND_MISSING_QUOTE, "R2"),
        (rc.KIND_UNKNOWN_ENTRY, "R99"),
    ]

    # Entry position and finding-kind rank disagree: R1 missing (kind 1, pos 0)
    # vs R2 drift (kind 0, pos 1) — sort must use both axes, not either alone.
    sort_register = _minimal_register(
        tmp_path,
        "**R1 — Required entry.**\n*Consumers:* C1\n"
        "**R2 — Also required.**\n*Consumers:* C1\n",
        name="sort_register.md",
    )
    sort_body = tmp_path / "sort_body.md"
    sort_body.write_text(
        "> **R2 — Also required.X**\n"
        "\n"
        "> **R99 — Unknown.**\n",
        encoding="utf-8",
    )
    sort_code, sort_out, _sort_err = _run_cli(
        "--register", str(sort_register),
        "--body-file", str(sort_body),
        "--child", "C1",
    )
    assert sort_code == rc.EXIT_FAIL
    sort_payload = json.loads(sort_out.strip())
    sort_seq = [(f["kind"], f["entry"]) for f in sort_payload["findings"]]
    assert sort_seq == [
        (rc.KIND_MISSING_QUOTE, "R1"),
        (rc.KIND_TEXT_DRIFT, "R2"),
        (rc.KIND_UNKNOWN_ENTRY, "R99"),
    ]


def _git_commit_all(repo, message="commit"):
    subprocess.run(
        [
            "git", "-C", str(repo),
            "-c", "user.name=test",
            "-c", "user.email=test@test",
            "add", "-A",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git", "-C", str(repo),
            "-c", "user.name=test",
            "-c", "user.email=test@test",
            "commit", "-m", message,
        ],
        check=True,
        capture_output=True,
    )


def _init_git_repo(path):
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        capture_output=True,
    )


def _tiny_register_text(header_suffix="One line entry."):
    return (
        f"**R1 — {header_suffix}**\n"
        "*Consumers:* C1\n"
    )


# --- register copy selection (#1340) ----------------------------------------


def test_main_copy_used_when_branch_copy_differs(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    register = repo / "register.md"
    register.write_text(_tiny_register_text("Main copy."), encoding="utf-8")
    _git_commit_all(repo, "main copy")
    register.write_text(_tiny_register_text("Stale branch copy."), encoding="utf-8")
    body = repo / "body.md"
    body.write_text("> **R1 — Stale branch copy.**\n", encoding="utf-8")
    result = _check(register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN)
    assert result["result"] == rc.RESULT_FAIL
    assert result["registerCopy"] == rc.REGISTER_COPY_MAIN
    assert result["registerRef"] in rc.MAIN_REFS
    assert result["findings"][0]["kind"] == rc.KIND_TEXT_DRIFT


def test_auto_inside_repo_selects_main(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    register = repo / "register.md"
    register.write_text(_tiny_register_text("Main copy."), encoding="utf-8")
    _git_commit_all(repo, "main copy")
    register.write_text(_tiny_register_text("Stale branch copy."), encoding="utf-8")
    body = repo / "body.md"
    body.write_text("> **R1 — Stale branch copy.**\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["registerCopy"] == rc.REGISTER_COPY_MAIN
    assert result["result"] == rc.RESULT_FAIL


def test_auto_outside_repo_selects_worktree(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "C1")
    assert result["registerCopy"] == rc.REGISTER_COPY_WORKTREE
    assert result["registerRef"] is None
    assert result["result"] == rc.RESULT_PASS


def test_register_copy_worktree_explicit_inside_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    register = repo / "register.md"
    register.write_text(_tiny_register_text("Main copy."), encoding="utf-8")
    _git_commit_all(repo, "main copy")
    register.write_text(_tiny_register_text("Stale branch copy."), encoding="utf-8")
    body = repo / "body.md"
    body.write_text("> **R1 — Stale branch copy.**\n", encoding="utf-8")
    result = _check(register, body, "C1", register_copy=rc.REGISTER_COPY_WORKTREE)
    assert result["registerCopy"] == rc.REGISTER_COPY_WORKTREE
    assert result["registerRef"] is None
    assert result["result"] == rc.RESULT_PASS


def test_origin_main_preferred_over_main(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    register = repo / "register.md"
    register.write_text(_tiny_register_text("Origin main copy."), encoding="utf-8")
    _git_commit_all(repo, "origin snapshot")
    origin_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", origin_sha],
        check=True,
        capture_output=True,
    )
    register.write_text(_tiny_register_text("Local main copy."), encoding="utf-8")
    _git_commit_all(repo, "local main")
    body = repo / "body.md"
    body.write_text("> **R1 — Origin main copy.**\n", encoding="utf-8")
    result = _check(register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN)
    assert result["registerRef"] == "origin/main"
    assert result["result"] == rc.RESULT_PASS


def test_main_selected_no_refs_undecided(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    register = repo / "register.md"
    register.write_text(_tiny_register_text(), encoding="utf-8")
    body = repo / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN)
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_REGISTER_UNREADABLE
    assert result["registerCopy"] == rc.REGISTER_COPY_MAIN
    assert "origin/main" in result["detail"]
    assert "main" in result["detail"]
    code, out, _err = _run_cli(
        "--register", str(register),
        "--body-file", str(body),
        "--child", "C1",
        "--register-copy", "main",
    )
    assert code == rc.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == rc.UNDECIDED_REGISTER_UNREADABLE


def test_main_selected_path_not_tracked_undecided(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    readme = repo / "README.md"
    readme.write_text("seed\n", encoding="utf-8")
    _git_commit_all(repo, "seed")
    register = repo / "register.md"
    register.write_text(_tiny_register_text(), encoding="utf-8")
    body = repo / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    result = _check(register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN)
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_REGISTER_UNREADABLE
    assert result["registerCopy"] == rc.REGISTER_COPY_MAIN
    assert "register.md" in result["detail"]


def test_main_selected_git_unavailable_undecided(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    register = repo / "register.md"
    register.write_text(_tiny_register_text(), encoding="utf-8")
    _git_commit_all(repo, "main")
    body = repo / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")

    def boom(*_args, **_kwargs):
        return rc.store_core.GitResult(
            None,
            rc.store_core.GIT_UNAVAILABLE,
            "git unavailable",
        )

    monkeypatch.setattr(rc.store_core, "run_git_result", boom)
    result = _check(register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN)
    assert result["result"] == rc.RESULT_UNDECIDED
    assert result["reason"] == rc.UNDECIDED_REGISTER_UNREADABLE
    assert result["registerCopy"] == rc.REGISTER_COPY_MAIN


def test_main_copy_symlinked_ancestor_matches_real_path(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    _init_git_repo(real)
    register = real / "register.md"
    register.write_text(_tiny_register_text("Main copy."), encoding="utf-8")
    _git_commit_all(real, "main copy")
    body = real / "body.md"
    body.write_text("> **R1 — Main copy.**\n", encoding="utf-8")
    result_real = _check(
        register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN,
    )
    result_link = _check(
        link / "register.md",
        link / "body.md",
        "C1",
        register_copy=rc.REGISTER_COPY_MAIN,
    )
    assert result_real["result"] == rc.RESULT_PASS
    assert result_link["result"] == result_real["result"]
    assert result_link["registerRef"] == result_real["registerRef"]
    assert result_link["registerCopy"] == rc.REGISTER_COPY_MAIN


def test_main_copy_grades_branch_not_tag_when_both_named_main(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    register = repo / "register.md"
    register.write_text(_tiny_register_text("Tag copy."), encoding="utf-8")
    _git_commit_all(repo, "tag snapshot")
    subprocess.run(
        ["git", "-C", str(repo), "tag", "main"],
        check=True,
        capture_output=True,
    )
    register.write_text(_tiny_register_text("Branch copy."), encoding="utf-8")
    _git_commit_all(repo, "branch snapshot")
    body = repo / "body.md"
    body.write_text("> **R1 — Branch copy.**\n", encoding="utf-8")
    result = _check(register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN)
    assert result["result"] == rc.RESULT_PASS
    assert result["registerRef"] == "main"
    assert result["registerCopy"] == rc.REGISTER_COPY_MAIN


def test_main_copy_unaffected_by_ambient_git_routing(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    register = repo / "register.md"
    register.write_text(_tiny_register_text("Main copy."), encoding="utf-8")
    _git_commit_all(repo, "main copy")
    body = repo / "body.md"
    body.write_text("> **R1 — Main copy.**\n", encoding="utf-8")
    result_clean = _check(
        register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN,
    )
    monkeypatch.setenv("GIT_DIR", "/bogus/nonexistent/.git")
    monkeypatch.setenv("GIT_WORK_TREE", "/bogus/nonexistent")
    result_dirty = _check(
        register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN,
    )
    assert result_clean["result"] == rc.RESULT_PASS
    assert result_dirty == result_clean


def test_register_check_does_not_mutate_os_environ(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    register = repo / "register.md"
    register.write_text(_tiny_register_text("Main copy."), encoding="utf-8")
    _git_commit_all(repo, "main copy")
    body = repo / "body.md"
    body.write_text("> **R1 — Main copy.**\n", encoding="utf-8")
    monkeypatch.setenv("GIT_DIR", "/bogus/nonexistent/.git")
    monkeypatch.setenv("GIT_WORK_TREE", "/bogus/nonexistent")
    before = dict(os.environ)
    _check(register, body, "C1", register_copy=rc.REGISTER_COPY_MAIN)
    assert dict(os.environ) == before


def test_usage_error_without_register_reports_worktree_not_auto():
    code, out, _err = _run_cli("--child", "C1")
    assert code == rc.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["registerCopy"] == rc.REGISTER_COPY_WORKTREE


def test_usage_error_rejects_unknown_register_copy_before_auto_normalization():
    code, out, _err = _run_raw_cli("check", "--register-copy", "bogus")
    assert code == rc.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == rc.UNDECIDED_USAGE
    assert payload["registerCopy"] == rc.REGISTER_COPY_WORKTREE
    assert "bogus" in payload["detail"]
    assert "invalid choice" in payload["detail"]


def test_usage_error_good_register_copy_records_usage_path(tmp_path):
    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    code, out, _err = _run_cli(
        "--register", str(register),
        "--body-file", str(body),
        "--child", "C1",
        "--register-copy", "worktree",
    )
    assert code == rc.EXIT_PASS
    payload = json.loads(out.strip())
    assert payload["registerCopy"] == rc.REGISTER_COPY_WORKTREE


def test_auto_selects_main_when_git_unavailable(tmp_path, monkeypatch):
    import store_core

    register = _tiny_register(tmp_path)
    body = tmp_path / "body.md"
    body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise store_core.RepoRootUnavailable("git down", git_status=store_core.GIT_UNAVAILABLE)

    monkeypatch.setattr(rc.store_core, "repo_root", boom)
    result = _check(register, body, "C1")
    assert result["registerCopy"] == rc.REGISTER_COPY_MAIN


def test_register_copy_fields_on_every_result_path(tmp_path):
    register = _tiny_register(tmp_path)
    pass_body = tmp_path / "pass.md"
    pass_body.write_text("> **R1 — One line entry.**\n", encoding="utf-8")
    pass_result = _check(register, pass_body, "C1")
    assert "registerCopy" in pass_result
    assert "registerRef" in pass_result
    _assert_result_field_keys(pass_result)

    drift_body = tmp_path / "drift.md"
    drift_body.write_text("> **R1 — One line entry.X**\n", encoding="utf-8")
    drift_result = _check(register, drift_body, "C1")
    _assert_result_field_keys(drift_result)

    undecided_result = _check(register, drift_body, "C09")
    _assert_result_field_keys(undecided_result)

    unreadable = tmp_path / "bad.md"
    unreadable.write_bytes(b"\xff\xfe")
    unreadable_result = _check(register, unreadable, "C1")
    _assert_result_field_keys(unreadable_result)


def test_vocabulary_constants():
    assert rc.SCHEMA == "register-check/1"
    assert rc.RESULTS == frozenset({
        rc.RESULT_PASS,
        rc.RESULT_FAIL,
        rc.RESULT_UNDECIDED,
    })
    assert rc.FINDING_KINDS == frozenset({
        rc.KIND_TEXT_DRIFT,
        rc.KIND_MISSING_QUOTE,
        rc.KIND_UNKNOWN_ENTRY,
    })
    assert rc.UNDECIDED_REASONS == frozenset({
        rc.UNDECIDED_REGISTER_UNREADABLE,
        rc.UNDECIDED_BODY_UNREADABLE,
        rc.UNDECIDED_REGISTER_EMPTY,
        rc.UNDECIDED_REGISTER_MALFORMED,
        rc.UNDECIDED_BODY_MALFORMED,
        rc.UNDECIDED_CHILD_UNRECOGNIZED,
        rc.UNDECIDED_USAGE,
        rc.UNDECIDED_INTERNAL_ERROR,
    })
    assert rc.EXIT_PASS == 0
    assert rc.EXIT_FAIL == 1
    assert rc.EXIT_UNDECIDED == 2
