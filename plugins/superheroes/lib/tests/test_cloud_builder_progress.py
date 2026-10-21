"""The cloud builder's progress comment (#2018): its text, its parse, and the edit-in-place write.

No test touches the network. `edit_comment` runs through an injected fake `run`.
"""
import json
import os
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder as cb  # noqa: E402

STARTED = "2026-10-21T08:30:00Z"
PLAIN = (
    "Builder progress (cloud build).\n\n"
    "Phase: gate\n"
    "Now running: the full test suite\n"
    "Started: 2026-10-21T08:30:00Z\n"
    "Expected: 60 minutes"
)


def _text(**overrides):
    args = {"phase": "gate", "running": "the full test suite", "started_at": STARTED,
            "expected_minutes": 60}
    args.update(overrides)
    return cb.progress_text(**args)


class _Run:
    """Records every call; answers with one fixed exit code and stdout, or raises."""

    def __init__(self, code=0, out="", raises=None):
        self.calls = []
        self.code, self.out, self.raises = code, out, raises

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        if self.raises is not None:
            raise self.raises
        return SimpleNamespace(returncode=self.code, stdout=self.out, stderr="")


# ---------------------------------------------------------------- the header


def test_the_progress_header_is_pinned_and_distinct_from_every_other_builder_header():
    assert cb.PROGRESS_HEADER == "Builder progress (cloud build)."
    assert cb.PROGRESS_EXPECTED_MAX_MINUTES == 240
    others = [cb.NOTE_HEADER, cb.HANDOVER_HEADER, cb.REFUSAL_HEADER, *cb.TERMINAL_HEADERS.values()]
    assert cb.PROGRESS_HEADER not in others


# ---------------------------------------------------------------- progress_text


def test_progress_text_exact_output_without_lost_work():
    assert _text() == {"ok": True, "comment": PLAIN}


def test_progress_text_exact_output_with_lost_work_and_stripped_fields():
    out = _text(phase=" gate ", running="  the full test suite\t", lost="  the second review  ")
    assert out == {"ok": True, "comment": PLAIN + "\nLost work: the second review"}


@pytest.mark.parametrize("lost", [None, "", "   "])
def test_a_none_or_blank_lost_adds_no_line(lost):
    assert _text(lost=lost) == {"ok": True, "comment": PLAIN}


@pytest.mark.parametrize("phase", [None, 7, "", "  ", "a\nb", "a\rb", "a\n"])
def test_phase_invalid(phase):
    assert _text(phase=phase) == {"ok": False, "reason": "phase-invalid"}


@pytest.mark.parametrize("running", [None, 7, "", "  ", "a\nb", "a\rb"])
def test_running_invalid(running):
    assert _text(running=running) == {"ok": False, "reason": "running-invalid"}


@pytest.mark.parametrize("started", [
    None, 7, "", "2026-10-21 08:30:00", "2026-10-21T08:30:00", "2026-10-21T08:30:00+00:00",
    "2026-13-21T08:30:00Z", "2026-10-32T08:30:00Z", "2026-10-21T25:30:00Z",
    "2026-10-21T08:30:00Z\n", "26-10-21T08:30:00Z",
])
def test_started_invalid(started):
    assert _text(started_at=started) == {"ok": False, "reason": "started-invalid"}


@pytest.mark.parametrize("expected", [None, "60", 60.0, True, False, 0, -1, 241, 10 ** 12])
def test_expected_invalid(expected):
    assert _text(expected_minutes=expected) == {"ok": False, "reason": "expected-invalid"}


@pytest.mark.parametrize("expected", [1, 240])
def test_expected_bounds_are_accepted(expected):
    assert _text(expected_minutes=expected)["ok"] is True


@pytest.mark.parametrize("lost", ["a\nb", "a\rb", "a\n"])
def test_lost_invalid(lost):
    assert _text(lost=lost) == {"ok": False, "reason": "lost-invalid"}


def test_refusals_are_checked_in_order():
    assert cb.progress_text("", "", "x", 0, "a\nb")["reason"] == "phase-invalid"
    assert cb.progress_text("p", "", "x", 0, "a\nb")["reason"] == "running-invalid"
    assert cb.progress_text("p", "r", "x", 0, "a\nb")["reason"] == "started-invalid"
    assert cb.progress_text("p", "r", STARTED, 0, "a\nb")["reason"] == "expected-invalid"
    assert cb.progress_text("p", "r", STARTED, 1, "a\nb")["reason"] == "lost-invalid"


# ---------------------------------------------------------------- parse_progress


def _fields(**overrides):
    fields = {"phase": "gate", "running": "the full test suite", "startedAt": STARTED,
              "expectedSeconds": 3600, "lostWork": None}
    fields.update(overrides)
    return fields


def test_parse_progress_round_trips_progress_text():
    comment = _text(lost="the second review")["comment"]
    assert cb.parse_progress(comment) == _fields(lostWork="the second review")
    assert cb.parse_progress(PLAIN) == _fields()


def test_a_posted_comment_carries_the_cloud_footer_and_still_parses():
    posted = PLAIN + "\n" + cb.CLOUD_FOOTER
    assert cb.parse_progress(posted) == _fields()


def test_an_edited_comment_has_no_footer_and_parses():
    assert cb.parse_progress(PLAIN) == _fields()


def test_leading_whitespace_before_the_header_is_allowed():
    assert cb.parse_progress("\n  " + PLAIN) == _fields()


def test_the_header_may_have_trailing_whitespace_on_its_line():
    assert cb.parse_progress(PLAIN.replace("(cloud build).", "(cloud build).  ", 1)) == _fields()


def test_expected_over_the_cap_reads_as_the_cap():
    body = PLAIN.replace("Expected: 60 minutes", "Expected: 999 minutes")
    assert cb.parse_progress(body)["expectedSeconds"] == 240 * 60


def test_an_absurdly_long_expected_number_reads_as_the_cap_and_never_raises():
    body = PLAIN.replace("Expected: 60 minutes", "Expected: " + "9" * 5000 + " minutes")
    assert cb.parse_progress(body)["expectedSeconds"] == 240 * 60


@pytest.mark.parametrize("line", [
    "Expected: soon", "Expected: 60", "Expected: -5 minutes", "Expected: 6.5 minutes",
    "Expected: 60 minutes please", "Expected:", "expected: 60 minutes", "Expected: 60 hours",
])
def test_a_malformed_expected_line_reads_as_zero(line):
    body = PLAIN.replace("Expected: 60 minutes", line)
    assert cb.parse_progress(body)["expectedSeconds"] == 0


def test_a_missing_expected_line_reads_as_zero():
    body = PLAIN.replace("\nExpected: 60 minutes", "")
    assert cb.parse_progress(body)["expectedSeconds"] == 0


def test_expected_one_minute_and_the_singular_word():
    body = PLAIN.replace("Expected: 60 minutes", "Expected: 1 minute")
    assert cb.parse_progress(body)["expectedSeconds"] == 60


def test_the_first_expected_line_decides_even_when_a_later_one_is_well_formed():
    body = PLAIN.replace("Expected: 60 minutes", "Expected: soon\nExpected: 60 minutes")
    assert cb.parse_progress(body)["expectedSeconds"] == 0


def test_the_first_line_of_each_label_is_taken_and_a_blank_value_is_none():
    body = PLAIN.replace("Phase: gate", "Phase: first\nPhase: second").replace(
        "Now running: the full test suite", "Now running:   ")
    parsed = cb.parse_progress(body)
    assert parsed["phase"] == "first"
    assert parsed["running"] is None


def test_a_header_after_other_text_is_not_a_progress_comment():
    assert cb.parse_progress("Quoting:\n" + PLAIN) is None
    assert cb.parse_progress("Quoting: " + PLAIN) is None


@pytest.mark.parametrize("body", [None, 7, b"x", ["a"], {"body": PLAIN}, "", "   ", "Looks good."])
def test_a_non_string_or_other_body_is_none(body):
    assert cb.parse_progress(body) is None


def test_terminal_kind_is_none_for_a_progress_comment():
    assert cb.terminal_kind(PLAIN) is None
    assert cb.terminal_kind(PLAIN + "\n" + cb.CLOUD_FOOTER) is None
    assert cb.terminal_kind(_text(lost="x")["comment"]) is None


# ---------------------------------------------------------------- edit_comment


def test_edit_comment_runs_exactly_one_patch_and_returns_the_url():
    run = _Run(0, json.dumps({"html_url": "https://github.com/o/r/issues/5#issuecomment-9"}))
    assert cb.edit_comment("o/r", 9, "/tmp/b", run=run, env={}) == {
        "ok": True, "reason": None, "url": "https://github.com/o/r/issues/5#issuecomment-9"}
    assert run.calls == [["gh", "api", "-X", "PATCH", "repos/o/r/issues/comments/9",
                          "-F", "body=@/tmp/b"]]


def test_edit_comment_with_unparseable_success_output_has_no_url():
    assert cb.edit_comment("o/r", 9, "/b", run=_Run(0, "ok"), env={}) == {
        "ok": True, "reason": None, "url": None}


def test_edit_comment_non_zero_exit_is_the_write_failure():
    run = _Run(1, "")
    assert cb.edit_comment("o/r", 9, "/b", run=run, env={}) == {
        "ok": False, "reason": "github-write-failed", "url": None}
    assert len(run.calls) == 1


@pytest.mark.parametrize("raised", [OSError("no gh"), TimeoutError("slow")])
def test_edit_comment_with_a_raising_run_is_the_write_failure(raised):
    assert cb.edit_comment("o/r", 9, "/b", run=_Run(raises=raised), env={})["reason"] == (
        "github-write-failed")


@pytest.mark.parametrize("repo,comment_id,path", [
    ("not a repo", 9, "/b"), ("../x", 9, "/b"), (None, 9, "/b"),
    ("o/r", "9; rm", "/b"), ("o/r", 0, "/b"), ("o/r", -3, "/b"), ("o/r", True, "/b"),
    ("o/r", 9.0, "/b"), ("o/r", None, "/b"), ("o/r", 9, ""), ("o/r", 9, None),
])
def test_edit_comment_refuses_bad_input_without_running_gh(repo, comment_id, path):
    run = _Run()
    assert cb.edit_comment(repo, comment_id, path, run=run, env={}) == {
        "ok": False, "reason": "github-write-failed", "url": None}
    assert run.calls == []


# ---------------------------------------------------------------- the CLI


def test_progress_cli_prints_the_comment(capsys):
    argv = ["progress", "--phase", "gate", "--running", "the full test suite",
            "--started", STARTED, "--expected-minutes", "60"]
    assert cb.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "comment": PLAIN}
    assert cb.main(argv + ["--lost", "the second review"]) == 0
    assert json.loads(capsys.readouterr().out) == _text(lost="the second review")


def test_progress_cli_refusals_exit_one(capsys):
    assert cb.main(["progress", "--phase", "gate", "--running", "x", "--started", STARTED,
                    "--expected-minutes", "241"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "expected-invalid"}
    assert cb.main(["progress", "--phase", "gate", "--running", "x", "--started", STARTED,
                    "--expected-minutes", "soon"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "usage"}


def test_edit_cli_runs_the_patch_through_gh(monkeypatch, capsys):
    run = _Run(0, json.dumps({"html_url": "https://github.com/o/r/issues/5#issuecomment-9"}))
    monkeypatch.setattr(cb.subprocess, "run", run)
    assert cb.main(["edit", "--repo", "o/r", "--comment-id", "9", "--body-file", "/tmp/b"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True, "reason": None, "url": "https://github.com/o/r/issues/5#issuecomment-9"}
    assert run.calls == [["gh", "api", "-X", "PATCH", "repos/o/r/issues/comments/9",
                          "-F", "body=@/tmp/b"]]


def test_edit_cli_refuses_a_bad_id_and_a_failing_exit(monkeypatch, capsys):
    run = _Run(1, "")
    monkeypatch.setattr(cb.subprocess, "run", run)
    assert cb.main(["edit", "--repo", "o/r", "--comment-id", "0", "--body-file", "/b"]) == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "github-write-failed"
    assert run.calls == []
    assert cb.main(["edit", "--repo", "o/r", "--comment-id", "9", "--body-file", "/b"]) == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "github-write-failed"
    assert len(run.calls) == 1
    assert cb.main(["edit", "--repo", "o/r", "--comment-id", "x", "--body-file", "/b"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "usage"}
