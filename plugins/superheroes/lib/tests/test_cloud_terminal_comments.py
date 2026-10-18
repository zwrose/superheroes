"""Tests for the cloud builder's terminal-comment headers (#1936): compose, read back, and the doctrine that names them.

Bites on: `terminal_text` emitting a comment for an unknown kind or empty text; `terminal_kind` accepting a header
that is not the whole first line, or missing a footered, padded or handover body; the CLI printing `ok: true` for
an unreadable or empty file; cloud.md naming a header that `TERMINAL_HEADERS` does not, or missing one it does;
wave-watch.md going back to "never reports `lane-terminal`" for a cloud lane; orchestration.md's recover steps
losing `parked` or `parkComment`.

**Residual blind spots:** the doctrine tests are phrase searches over the collapsed text, so a section that keeps
the phrase but contradicts it in the next sentence passes; `terminal_kind` is tested against the footer shape the
cloud harness was last seen to append, so a harness that changes its footer is not caught here.
"""
import json
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder as cb  # noqa: E402

_PLUGIN = os.path.abspath(os.path.join(_LIB, ".."))
_CLOUD = os.path.join(_PLUGIN, "skills", "workhorse", "reference", "cloud.md")
_WAVE_WATCH = os.path.join(_PLUGIN, "skills", "showrunner", "reference", "wave-watch.md")
_ORCHESTRATION = os.path.join(_PLUGIN, "skills", "showrunner", "reference", "orchestration.md")
_SECTION = "Terminal comments: handback, stop, park"

KINDS = ["handback", "stop", "park"]


def _read(path):
    # Strict decoding on purpose: a file that cannot be read fails the test, never passes it.
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _collapsed(path):
    return " ".join(_read(path).split())


def _section(path, heading):
    match = re.search(
        r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", _read(path), re.MULTILINE | re.DOTALL
    )
    assert match, "the section %r was not found in %s" % (heading, os.path.basename(path))
    return match.group(1)


@pytest.mark.parametrize("kind", KINDS)
def test_terminal_text_is_the_header_a_blank_line_and_the_trimmed_text(kind):
    # axis: the comment's first line is the kind's fixed header and nothing else
    assert cb.terminal_text(kind, "  Done.\nAll of it.\n") == {
        "ok": True, "comment": cb.TERMINAL_HEADERS[kind] + "\n\nDone.\nAll of it."}


@pytest.mark.parametrize("kind", ["handover", "Stop", None, "", "note"])
def test_terminal_text_refuses_an_unknown_kind(kind):
    # axis: no comment is emitted for a kind that has no header
    assert cb.terminal_text(kind, "text") == {"ok": False, "reason": "kind-invalid"}


@pytest.mark.parametrize("text", ["", "  \n", None, 7])
def test_terminal_text_refuses_empty_text(text):
    # axis: no comment is emitted for text with nothing in it
    assert cb.terminal_text("stop", text) == {"ok": False, "reason": "text-empty"}


def _shapes(kind):
    bare = cb.terminal_text(kind, "What happened.")["comment"]
    return {
        "bare": bare,
        "footer": bare + "\n\n" + cb.CLOUD_FOOTER,
        "live-read-back": bare + "\n\n\n" + cb.CLOUD_FOOTER + "\n",
        "leading-whitespace": "\n  " + bare,
        "header-alone": cb.TERMINAL_HEADERS[kind],
        "header-alone-footer": cb.TERMINAL_HEADERS[kind] + "\n\n" + cb.CLOUD_FOOTER,
    }


@pytest.mark.parametrize("shape", ["bare", "footer", "live-read-back", "leading-whitespace",
                                   "header-alone", "header-alone-footer"])
@pytest.mark.parametrize("kind", KINDS)
def test_terminal_kind_accepts_each_kinds_comment_in_every_shape(kind, shape):
    # axis: a builder's terminal comment is recognised with or without the harness footer and padding
    assert cb.terminal_kind(_shapes(kind)[shape]) == kind


@pytest.mark.parametrize("footer", [False, True])
def test_terminal_kind_reads_a_handover_comment(footer):
    # axis: the handover comment keeps being recognised by its whole-body shape
    body = cb.handover_text("a" * 40) + ("\n\n" + cb.CLOUD_FOOTER if footer else "")
    assert cb.terminal_kind(body) == "handover"


@pytest.mark.parametrize("body", [
    pytest.param("I looked first.\n\n" + cb.STOP_HEADER + "\n\nx", id="prose-before-header"),
    pytest.param("Notes.\n" + cb.PARK_HEADER, id="header-not-on-first-line"),
    pytest.param(cb.STOP_HEADER + " now\n\nx", id="extra-words-on-header-line"),
    pytest.param(cb.STOP_HEADER.lower() + "\n\nx", id="lower-cased-header"),
    pytest.param("Builder stop at intake\n\nx", id="free-form-field-comment"),
    pytest.param(cb.NOTE_HEADER + "\n\nQ?", id="note-header"),
    pytest.param(cb.REFUSAL_HEADER + "\n\nx", id="refusal-header"),
    pytest.param("Builder intake (cloud build). Plugin 1.\n\nx", id="intake-header"),
    pytest.param(cb.CLOUD_FOOTER, id="footer-alone"),
    pytest.param(None, id="none"),
    pytest.param(7, id="non-string"),
    pytest.param(cb.STOP_HEADER[:-1] + "\n\nx", id="header-without-final-period"),
])
def test_terminal_kind_refuses_anything_else(body):
    # axis: only a header that is the whole first line counts; every other body is not a terminal comment
    assert cb.terminal_kind(body) is None


def test_strip_cloud_footer_removes_one_footer_on_its_own_line_only():
    # axis: one trailing footer after a newline is dropped; nothing else is
    assert cb.strip_cloud_footer(None) is None
    assert cb.strip_cloud_footer("a\n\n" + cb.CLOUD_FOOTER) == "a"
    assert cb.strip_cloud_footer("a " + cb.CLOUD_FOOTER) == "a " + cb.CLOUD_FOOTER
    assert cb.strip_cloud_footer("a\n" + cb.CLOUD_FOOTER + "\n" + cb.CLOUD_FOOTER) == "a\n" + cb.CLOUD_FOOTER
    assert cb.strip_cloud_footer(cb.CLOUD_FOOTER) == cb.CLOUD_FOOTER


def test_terminal_kind_judges_an_unstripped_footer_body_as_it_is():
    # axis: a footer that is not stripped (two, or a different one) never hides a first-line header, nor makes one
    two = cb.terminal_text("park", "x")["comment"] + "\n\n" + cb.CLOUD_FOOTER + "\n\n" + cb.CLOUD_FOOTER
    assert cb.terminal_kind(two) == "park"
    assert cb.terminal_kind(cb.CLOUD_FOOTER + "\n\n" + cb.STOP_HEADER) is None
    assert cb.terminal_kind(cb.STOP_HEADER + "\n\n---\n_Generated by something else_") == "stop"


@pytest.mark.parametrize("kind", KINDS)
def test_cli_prints_the_terminal_text_result(kind, tmp_path, capsys):
    # axis: the CLI verb returns exactly what terminal_text composes
    path = tmp_path / "text.md"
    path.write_text("Body text.\n", encoding="utf-8")
    assert cb.main(["terminal", "--kind", kind, "--text-file", str(path)]) == 0
    assert json.loads(capsys.readouterr().out) == cb.terminal_text(kind, "Body text.\n")


def test_cli_refuses_an_unreadable_file_an_empty_file_and_an_unknown_kind(tmp_path, capsys):
    # axis: the CLI never prints ok: true for an unreadable or empty file or a kind with no header
    assert cb.main(["terminal", "--kind", "stop", "--text-file", str(tmp_path / "missing.md")]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "text-unreadable"}
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    assert cb.main(["terminal", "--kind", "stop", "--text-file", str(empty)]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "text-empty"}
    assert cb.main(["terminal", "--kind", "handover", "--text-file", str(empty)]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "usage"}


def test_cloud_md_names_exactly_the_terminal_headers():
    # axis: the doctrine names the headers cloud_builder defines, character for character, no more and no fewer
    section = _section(_CLOUD, _SECTION)
    named = {t for t in re.findall(r"`([^`]+)`", section)
             if t.startswith("Builder ") and t.endswith("(cloud build).")}
    assert named == set(cb.TERMINAL_HEADERS.values())
    assert "terminal --kind" in section


def test_wave_watch_reports_lane_terminal_for_a_cloud_lane():
    # axis: the watcher doctrine says a cloud lane's ending reaches it as lane-terminal from its issue comments
    text = _collapsed(_WAVE_WATCH)
    assert "never reports `builder-exited`, `lane-terminal`" not in text
    assert "TERMINAL_HEADERS" in text


def test_orchestration_recover_steps_name_parked_and_its_comment():
    # axis: recovery treats a parked lane as never recovered and names the comment to act on
    text = _collapsed(_ORCHESTRATION)
    assert "`parked`" in text and "`parkComment`" in text


def test_the_cloud_footer_literal_is_the_one_the_harness_appends():
    # axis: the footer the readers strip is exactly the one the cloud harness was observed to append
    assert cb.CLOUD_FOOTER == "---\n_Generated by [Claude Code](https://claude.ai/code)_"
