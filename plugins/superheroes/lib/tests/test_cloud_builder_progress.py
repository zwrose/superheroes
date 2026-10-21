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
    # axis: the progress header and cap are pinned and differ from every other builder header; a collision would make another comment read as progress
    assert cb.PROGRESS_HEADER == "Builder progress (cloud build)."
    assert cb.PROGRESS_EXPECTED_MAX_MINUTES == 240
    others = [cb.NOTE_HEADER, cb.HANDOVER_HEADER, cb.REFUSAL_HEADER, *cb.TERMINAL_HEADERS.values()]
    assert cb.PROGRESS_HEADER not in others


# ---------------------------------------------------------------- progress_text


def test_progress_text_exact_output_without_lost_work():
    # axis: the comment text is exactly the header and four fields; a reworded or reordered field breaks the parse the watch relies on
    assert _text() == {"ok": True, "comment": PLAIN}


def test_progress_text_exact_output_with_lost_work_and_stripped_fields():
    # axis: field values are stripped and a lost-work line is appended last; unstripped padding or a missing line would reach the comment
    out = _text(phase=" gate ", running="  the full test suite\t", lost="  the second review  ")
    assert out == {"ok": True, "comment": PLAIN + "\nLost work: the second review"}


@pytest.mark.parametrize("lost", [None, "", "   "])
def test_a_none_or_blank_lost_adds_no_line(lost):
    # axis: a None or blank lost adds no Lost work line; an empty line would parse as a lost-work value
    assert _text(lost=lost) == {"ok": True, "comment": PLAIN}


@pytest.mark.parametrize("phase", [None, 7, "", "  ", "a\nb", "a\rb", "a\n"])
def test_phase_invalid(phase):
    # axis: a missing, non-string, blank or multi-line phase is refused as phase-invalid; a newline would forge extra fields
    assert _text(phase=phase) == {"ok": False, "reason": "phase-invalid"}


@pytest.mark.parametrize("running", [None, 7, "", "  ", "a\nb", "a\rb"])
def test_running_invalid(running):
    # axis: a missing, non-string, blank or multi-line running is refused as running-invalid; a newline would forge extra fields
    assert _text(running=running) == {"ok": False, "reason": "running-invalid"}


@pytest.mark.parametrize("started", [
    None, 7, "", "2026-10-21 08:30:00", "2026-10-21T08:30:00", "2026-10-21T08:30:00+00:00",
    "2026-13-21T08:30:00Z", "2026-10-32T08:30:00Z", "2026-10-21T25:30:00Z",
    "2026-10-21T08:30:00Z\n", "26-10-21T08:30:00Z",
])
def test_started_invalid(started):
    # axis: only a UTC Z timestamp that is a real date is accepted as started; another shape would break the age arithmetic
    assert _text(started_at=started) == {"ok": False, "reason": "started-invalid"}


@pytest.mark.parametrize("expected", [None, "60", 60.0, True, False, 0, -1, 241, 10 ** 12])
def test_expected_invalid(expected):
    # axis: expected minutes outside the integer range 1 to the cap, or a bool, float or string, is refused; a larger value would stretch the stale limit
    assert _text(expected_minutes=expected) == {"ok": False, "reason": "expected-invalid"}


@pytest.mark.parametrize("expected", [1, 240])
def test_expected_bounds_are_accepted(expected):
    # axis: the bounds 1 and the cap are accepted; an off-by-one would refuse a legitimate wait
    assert _text(expected_minutes=expected)["ok"] is True


@pytest.mark.parametrize("lost", ["a\nb", "a\rb", "a\n"])
def test_lost_invalid(lost):
    # axis: a multi-line lost is refused as lost-invalid; a newline would forge extra fields
    assert _text(lost=lost) == {"ok": False, "reason": "lost-invalid"}


def test_refusals_are_checked_in_order():
    # axis: refusals come in phase, running, started, expected, lost order; a reordered check would change the reason the builder is told
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
    # axis: what progress_text writes parse_progress reads back field for field; drift between the two would blind the watch
    comment = _text(lost="the second review")["comment"]
    assert cb.parse_progress(comment) == _fields(lostWork="the second review")
    assert cb.parse_progress(PLAIN) == _fields()


def test_a_posted_comment_carries_the_cloud_footer_and_still_parses():
    # axis: a comment with the cloud footer still parses; a footer-intolerant parse would never see a posted comment
    posted = PLAIN + "\n" + cb.CLOUD_FOOTER
    assert cb.parse_progress(posted) == _fields()


def test_an_edited_comment_has_no_footer_and_parses():
    # axis: an edited comment without a footer parses; requiring the footer would drop every edited comment
    assert cb.parse_progress(PLAIN) == _fields()


def test_leading_whitespace_before_the_header_is_allowed():
    # axis: leading whitespace before the header is tolerated; a strict start would miss a padded comment
    assert cb.parse_progress("\n  " + PLAIN) == _fields()


def test_the_header_may_have_trailing_whitespace_on_its_line():
    # axis: trailing whitespace on the header line is tolerated; a strict line match would miss it
    assert cb.parse_progress(PLAIN.replace("(cloud build).", "(cloud build).  ", 1)) == _fields()


def test_expected_over_the_cap_reads_as_the_cap():
    # axis: an Expected over the cap reads as the cap in seconds; an uncapped value would stretch the stale limit
    body = PLAIN.replace("Expected: 60 minutes", "Expected: 999 minutes")
    assert cb.parse_progress(body)["expectedSeconds"] == 240 * 60


def test_an_absurdly_long_expected_number_reads_as_the_cap_and_never_raises():
    # axis: a 5000-digit Expected reads as the cap and does not raise; int() of it would raise or take unbounded time
    body = PLAIN.replace("Expected: 60 minutes", "Expected: " + "9" * 5000 + " minutes")
    assert cb.parse_progress(body)["expectedSeconds"] == 240 * 60


@pytest.mark.parametrize("digits,seconds", [
    ("0000000001", 60), ("0000", 0), ("000000000000000240", 240 * 60), ("1" + "0" * 5000, 240 * 60),
])
def test_expected_digits_read_by_numeric_value_never_by_length(digits, seconds):
    # axis: ZERO-PAD — leading zeros do not make a small number read as the cap, all-zero reads 0, a huge number is the cap and never raises
    body = PLAIN.replace("Expected: 60 minutes", "Expected: " + digits + " minutes")
    assert cb.parse_progress(body)["expectedSeconds"] == seconds


@pytest.mark.parametrize("line", [
    "Expected: soon", "Expected: 60", "Expected: -5 minutes", "Expected: 6.5 minutes",
    "Expected: 60 minutes please", "Expected:", "expected: 60 minutes", "Expected: 60 hours",
])
def test_a_malformed_expected_line_reads_as_zero(line):
    # axis: a malformed Expected line reads as 0 seconds; reading it as anything more would add unstated time
    body = PLAIN.replace("Expected: 60 minutes", line)
    assert cb.parse_progress(body)["expectedSeconds"] == 0


def test_a_missing_expected_line_reads_as_zero():
    # axis: a missing Expected line reads as 0 seconds; a default wait would add unstated time
    body = PLAIN.replace("\nExpected: 60 minutes", "")
    assert cb.parse_progress(body)["expectedSeconds"] == 0


def test_expected_one_minute_and_the_singular_word():
    # axis: Expected: 1 minute (singular) reads as 60 seconds; a plural-only match would read it as 0
    body = PLAIN.replace("Expected: 60 minutes", "Expected: 1 minute")
    assert cb.parse_progress(body)["expectedSeconds"] == 60


def test_the_first_expected_line_decides_even_when_a_later_one_is_well_formed():
    # axis: the first Expected line decides; a later well-formed line must not rescue a malformed first one
    body = PLAIN.replace("Expected: 60 minutes", "Expected: soon\nExpected: 60 minutes")
    assert cb.parse_progress(body)["expectedSeconds"] == 0


def test_the_first_line_of_each_label_is_taken_and_a_blank_value_is_none():
    # axis: the first line of each label wins and a blank value is None; a last-wins or blank-string read would misreport the phase
    body = PLAIN.replace("Phase: gate", "Phase: first\nPhase: second").replace(
        "Now running: the full test suite", "Now running:   ")
    parsed = cb.parse_progress(body)
    assert parsed["phase"] == "first"
    assert parsed["running"] is None


def test_a_header_after_other_text_is_not_a_progress_comment():
    # axis: a comment quoting the header after other text is not progress; a substring match would let a quote decide the lane
    assert cb.parse_progress("Quoting:\n" + PLAIN) is None
    assert cb.parse_progress("Quoting: " + PLAIN) is None


@pytest.mark.parametrize("body", [None, 7, b"x", ["a"], {"body": PLAIN}, "", "   ", "Looks good."])
def test_a_non_string_or_other_body_is_none(body):
    # axis: a non-string or non-progress body parses to None; a raise or a fabricated dict would crash or mislead the watch
    assert cb.parse_progress(body) is None


def test_terminal_kind_is_none_for_a_progress_comment():
    # axis: a progress comment is never read as a terminal comment; a clash would end the lane early
    assert cb.terminal_kind(PLAIN) is None
    assert cb.terminal_kind(PLAIN + "\n" + cb.CLOUD_FOOTER) is None
    assert cb.terminal_kind(_text(lost="x")["comment"]) is None


# ---------------------------------------------------------------- edit_comment


def test_edit_comment_runs_exactly_one_patch_and_returns_the_url():
    # axis: edit_comment makes exactly one gh PATCH of the body file and returns the url; a second call or other verb would post or duplicate
    run = _Run(0, json.dumps({"html_url": "https://github.com/o/r/issues/5#issuecomment-9"}))
    assert cb.edit_comment("o/r", 9, "/tmp/b", run=run, env={}) == {
        "ok": True, "reason": None, "url": "https://github.com/o/r/issues/5#issuecomment-9"}
    assert run.calls == [["gh", "api", "-X", "PATCH", "repos/o/r/issues/comments/9",
                          "-F", "body=@/tmp/b"]]


def test_edit_comment_with_unparseable_success_output_has_no_url():
    # axis: a successful write with unparseable output is ok with no url; claiming a url would invent a link
    assert cb.edit_comment("o/r", 9, "/b", run=_Run(0, "ok"), env={}) == {
        "ok": True, "reason": None, "url": None}


def test_edit_comment_non_zero_exit_is_the_write_failure():
    # axis: a non-zero gh exit is github-write-failed after one call; reporting success would hide a lost edit
    run = _Run(1, "")
    assert cb.edit_comment("o/r", 9, "/b", run=run, env={}) == {
        "ok": False, "reason": "github-write-failed", "url": None}
    assert len(run.calls) == 1


@pytest.mark.parametrize("raised", [OSError("no gh"), TimeoutError("slow")])
def test_edit_comment_with_a_raising_run_is_the_write_failure(raised):
    # axis: a raising run is github-write-failed, not an exception; a raise would crash the builder mid-build
    assert cb.edit_comment("o/r", 9, "/b", run=_Run(raises=raised), env={})["reason"] == (
        "github-write-failed")


@pytest.mark.parametrize("repo,comment_id,path", [
    ("not a repo", 9, "/b"), ("../x", 9, "/b"), (None, 9, "/b"),
    ("o/r", "9; rm", "/b"), ("o/r", 0, "/b"), ("o/r", -3, "/b"), ("o/r", True, "/b"),
    ("o/r", 9.0, "/b"), ("o/r", None, "/b"), ("o/r", 9, ""), ("o/r", 9, None),
])
def test_edit_comment_refuses_bad_input_without_running_gh(repo, comment_id, path):
    # axis: a bad repo, comment id or path is refused without running gh; a call with it could patch the wrong comment
    run = _Run()
    assert cb.edit_comment(repo, comment_id, path, run=run, env={}) == {
        "ok": False, "reason": "github-write-failed", "url": None}
    assert run.calls == []


# ---------------------------------------------------------------- the CLI


def test_progress_cli_prints_the_comment(capsys):
    # axis: the progress CLI prints the composed comment as JSON and exits 0, with and without --lost
    argv = ["progress", "--phase", "gate", "--running", "the full test suite",
            "--started", STARTED, "--expected-minutes", "60"]
    assert cb.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "comment": PLAIN}
    assert cb.main(argv + ["--lost", "the second review"]) == 0
    assert json.loads(capsys.readouterr().out) == _text(lost="the second review")


def test_progress_cli_refusals_exit_one(capsys):
    # axis: the progress CLI exits 1 with the refusal reason, and a non-integer argument is usage; exiting 0 would read as a written comment
    assert cb.main(["progress", "--phase", "gate", "--running", "x", "--started", STARTED,
                    "--expected-minutes", "241"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "expected-invalid"}
    assert cb.main(["progress", "--phase", "gate", "--running", "x", "--started", STARTED,
                    "--expected-minutes", "soon"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "usage"}


def test_edit_cli_runs_the_patch_through_gh(monkeypatch, capsys):
    # axis: the edit CLI patches through gh and prints the url; a CLI that skipped the patch would report a write it never made
    run = _Run(0, json.dumps({"html_url": "https://github.com/o/r/issues/5#issuecomment-9"}))
    monkeypatch.setattr(cb.subprocess, "run", run)
    assert cb.main(["edit", "--repo", "o/r", "--comment-id", "9", "--body-file", "/tmp/b"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True, "reason": None, "url": "https://github.com/o/r/issues/5#issuecomment-9"}
    assert run.calls == [["gh", "api", "-X", "PATCH", "repos/o/r/issues/comments/9",
                          "-F", "body=@/tmp/b"]]


def test_edit_cli_refuses_a_bad_id_and_a_failing_exit(monkeypatch, capsys):
    # axis: the edit CLI exits 1 on a bad id (no gh call), a failing gh exit, or a non-integer id (usage); exiting 0 would hide a lost edit
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
