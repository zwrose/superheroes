"""Tests for the cloud builder's terminal comment: one target (the issue), an optional pointer to a pull
request copy, and the two doc pages that say so.

No test touches the network or the real home directory.
"""
import json
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_PLUGIN = os.path.join(_LIB, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder as cb  # noqa: E402

PR_COMMENT = "https://github.com/acme/widgets/pull/42#issuecomment-1234567"
POINTER = "Also posted on the pull request: " + PR_COMMENT


def test_row1_the_comment_without_also_on_is_unchanged_and_targets_the_issue():
    result = cb.terminal_text("handback", "Done.")
    assert result["ok"] is True
    assert result["target"] == "issue"
    assert result["comment"] == cb.HANDBACK_HEADER + "\n\nDone."


def test_row2_a_valid_also_on_appends_one_pointer_line_and_keeps_the_header_first():
    result = cb.terminal_text("handback", "Done.", also_on=PR_COMMENT)
    assert result["ok"] is True
    assert result["target"] == "issue"
    assert result["comment"] == cb.HANDBACK_HEADER + "\n\nDone.\n\n" + POINTER
    assert result["comment"].splitlines()[0] == cb.HANDBACK_HEADER
    assert cb.terminal_kind(result["comment"]) == "handback"


@pytest.mark.parametrize("bad", [
    "https://github.com/acme/widgets/issues/5#issuecomment-1",
    "https://github.com/acme/widgets/pull/42",
    PR_COMMENT + " " + PR_COMMENT,
    PR_COMMENT + "\nand more text",
    "https://example.com/acme/widgets/pull/42#issuecomment-1234567",
    "",
    "https://github.com/acme/../pull/42#issuecomment-1",
    "https://github.com/./widgets/pull/42#issuecomment-1",
    "https://github.com/acme/widgets/pull/42#issuecomment-0",
])
def test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused(bad):
    assert cb.terminal_text("park", "Waiting.", also_on=bad) == {"ok": False, "reason": "also-on-invalid"}


def test_comment_permalink_reads_both_page_kinds_and_refuses_anything_else():
    # axis: the one permalink parser the builder and the watch share names repository, page kind, page and comment
    assert cb.comment_permalink(PR_COMMENT) == ("acme/widgets", "pull", 42, 1234567)
    assert cb.comment_permalink("https://github.com/acme/widgets/issues/5#issuecomment-9") == (
        "acme/widgets", "issues", 5, 9)
    for bad in (None, 7, "", PR_COMMENT + "x", "https://github.com/acme/../pull/42#issuecomment-1",
                "https://github.com/acme/widgets/pulls/42#issuecomment-1"):
        assert cb.comment_permalink(bad) is None


def test_row3_the_kind_and_text_refusals_come_before_the_also_on_check():
    assert cb.terminal_text("nope", "Done.", also_on="bad") == {"ok": False, "reason": "kind-invalid"}
    assert cb.terminal_text("stop", "  ", also_on="bad") == {"ok": False, "reason": "text-empty"}


def test_row3_the_mention_guard_still_reads_the_whole_composed_comment():
    result = cb.terminal_text("park", "Ping @someone now.", also_on=PR_COMMENT)
    assert result["ok"] is False
    assert result["reason"] == "bare-mention"


def test_row4_the_cli_prints_the_comment_with_the_pointer_line(tmp_path, capsys):
    text = tmp_path / "t.txt"
    text.write_text("Parked on a question.\n", encoding="utf-8")
    code = cb.main(["terminal", "--kind", "park", "--text-file", str(text), "--also-on", PR_COMMENT])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["target"] == "issue"
    assert out["comment"] == cb.PARK_HEADER + "\n\nParked on a question.\n\n" + POINTER


def test_row4_the_cli_refuses_a_bad_also_on_with_exit_1(tmp_path, capsys):
    text = tmp_path / "t.txt"
    text.write_text("Parked on a question.\n", encoding="utf-8")
    code = cb.main(["terminal", "--kind", "park", "--text-file", str(text), "--also-on", "https://github.com/acme/widgets/pull/42"])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out == {"ok": False, "reason": "also-on-invalid"}


def test_row4_the_cli_without_also_on_is_the_plain_comment(tmp_path, capsys):
    text = tmp_path / "t.txt"
    text.write_text("Stopped.\n", encoding="utf-8")
    assert cb.main(["terminal", "--kind", "stop", "--text-file", str(text)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": True, "comment": cb.STOP_HEADER + "\n\nStopped.", "target": "issue"}


def _read(*parts):
    with open(os.path.join(_PLUGIN, *parts), encoding="utf-8") as fh:
        return fh.read()


def test_row5_cloud_md_terminal_section_names_also_on():
    text = _read("skills", "workhorse", "reference", "cloud.md")
    start = text.index("## Terminal comments: handback, stop, park")
    end = text.index("\n## ", start + 1)
    assert "--also-on" in text[start:end]


def test_row5_wave_watch_md_names_the_lane_s_own_pull_request_and_pr_in_both_field_lists():
    text = _read("skills", "showrunner", "reference", "wave-watch.md")
    assert "own pull request" in text
    note = text[text.index("When **`builder-note`** fires"):text.index("When **`account-limited`** fires")]
    terminal = text[text.index("When **`lane-terminal`** fires for a cloud lane"):text.index("A terminal cloud lane **sent a fix order")]
    assert re.search(r'"pr"', note)
    assert re.search(r'"pr"', terminal)