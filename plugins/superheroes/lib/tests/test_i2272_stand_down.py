# plugins/superheroes/lib/tests/test_i2272_stand_down.py
"""Conformance (#2272): a cloud builder that wakes after a newer launch took its issue over stands down.

`cloud_builder.superseded` reads the issue's comments whole through `cloud_recover._issue_comments` and
names a newer launch: a later `Builder intake (cloud build).` comment, or a later `Builder superseded (cloud
build).` notice. Only `gh` is faked, through the `run=` injection, the way test_cloud_recover.py fakes it.
Nothing touches the network or the real environment."""
import datetime
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_PLUGIN = os.path.dirname(_LIB)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder as CB  # noqa: E402
import cloud_recover  # noqa: E402

REPO = "owner/repo"
ISSUE = 17
OWN = 100
SHA = "a" * 40
UTC = datetime.timezone.utc


def _at(minute, second=0):
    return datetime.datetime(2026, 10, 12, 10, minute, second, tzinfo=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _comment(cid, body, created):
    return {"id": cid, "html_url": "https://github.com/%s/issues/%d#issuecomment-%d" % (REPO, ISSUE, cid),
            "body": body, "created_at": created, "updated_at": created}


def _intake(cid, minute, second=0):
    return _comment(cid, CB.INTAKE_TEXT.format(v="0.47.0", sha=SHA), _at(minute, second))


def _notice(cid, minute, second=0):
    return _comment(cid, CB.superseded_notice_text("launch-1"), _at(minute, second))


class Gh:
    """Fake `gh api`: the issue's comments are set by the test; `fail` makes every read fail."""

    def __init__(self, comments, fail=False):
        self.comments, self.fail, self.calls = comments, fail, []

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        if self.fail or "/comments?" not in argv[-1]:
            return subprocess.CompletedProcess(argv, 1, "", "boom")
        return subprocess.CompletedProcess(argv, 0, json.dumps(self.comments), "")


def _superseded(comments, own=OWN, **kw):
    return CB.superseded(REPO, ISSUE, own, env={}, run=Gh(comments, **kw))


# 1. a newer builder intake
def test_newer_intake_supersedes_and_stand_down_names_it():
    result = _superseded([_intake(OWN, 0), _intake(101, 1)])
    assert result["ok"] is True and result["superseded"] is True
    url = "https://github.com/%s/issues/%d#issuecomment-101" % (REPO, ISSUE)
    assert result["newerLaunch"] == {"commentId": 101, "url": url, "createdAt": _at(1)}
    assert result["comment"].startswith(CB.STAND_DOWN_HEADER)
    assert url in result["comment"]
    assert result["comment"] == CB.stand_down_text(url)


def test_the_newest_of_several_newer_launches_is_named():
    adopt = _comment(103, CB.INTAKE_ADOPT_TEXT.format(v="0.47.0", sha=SHA, branch="b") + "\n" + CB.CLOUD_FOOTER, _at(5))
    result = _superseded([_intake(OWN, 0), _intake(101, 1), adopt, _intake(102, 3)])
    assert result["superseded"] is True and result["newerLaunch"]["commentId"] == 103


def test_the_whole_issue_is_read_from_epoch_zero():
    gh = Gh([_intake(OWN, 0)])
    CB.superseded(REPO, ISSUE, OWN, env={}, run=gh)
    assert "since=1970-01-01T00:00:00Z" in gh.calls[0][-1]


# 2. nothing newer
def test_only_own_intake_and_other_builder_comments_is_not_superseded():
    others = [_comment(101, CB.PROGRESS_HEADER + "\n\nPhase: build", _at(1)),
              _comment(102, CB.note_text("Which way?")["comment"], _at(2)),
              _comment(103, CB.terminal_text("park", "Parked.")["comment"], _at(3)),
              _comment(104, CB.handover_text(SHA), _at(4)),
              _comment(105, "A human note.", _at(5))]
    result = _superseded([_intake(OWN, 0)] + others)
    assert result == {"ok": True, "superseded": False, "newerLaunch": None, "comment": None}


def test_an_older_intake_is_not_a_newer_launch():
    assert _superseded([_intake(99, 0), _intake(OWN, 4)])["superseded"] is False


# 3. a detective intake, or a quoted header, is not a launch
def test_a_newer_detective_intake_is_not_a_newer_launch():
    detective = _comment(101, CB.DETECTIVE_INTAKE_TEXT.format(v="0.47.0", sha=SHA), _at(1))
    assert _superseded([_intake(OWN, 0), detective])["superseded"] is False


def test_a_header_quoted_mid_body_is_not_a_newer_launch():
    quoting = _comment(101, "I saw the earlier comment:\n" + CB.INTAKE_HEADER + " Plugin 0.47.0. and a notice\n"
                       + CB.SUPERSEDED_HEADER, _at(1))
    assert _superseded([_intake(OWN, 0), quoting])["superseded"] is False


def test_a_footer_and_leading_whitespace_do_not_hide_a_newer_intake():
    padded = _comment(101, "\n  " + CB.INTAKE_TEXT.format(v="0.47.0", sha=SHA) + "\n" + CB.CLOUD_FOOTER, _at(1))
    assert _superseded([_intake(OWN, 0), padded])["newerLaunch"]["commentId"] == 101


# 4. the same second goes to the larger id
def test_same_created_at_with_a_larger_id_is_superseded():
    assert _superseded([_intake(OWN, 0), _intake(OWN + 1, 0)])["superseded"] is True


def test_same_created_at_with_a_smaller_id_is_not_superseded():
    assert _superseded([_intake(OWN, 0), _intake(OWN - 1, 0)])["superseded"] is False


# 5. refusals
def test_comments_not_read_whole_is_a_refusal():
    assert _superseded([_intake(OWN, 0), _intake(101, 1)], fail=True) == {"ok": False, "reason": "comments-unreadable"}


def test_a_page_that_is_not_a_list_of_comments_is_a_refusal():
    assert _superseded(["not a comment"])["reason"] == "comments-unreadable"


def test_own_intake_missing_is_a_refusal():
    assert _superseded([_intake(101, 1)]) == {"ok": False, "reason": "own-intake-not-found"}


def test_a_comment_with_the_own_id_that_is_not_an_intake_is_not_the_own_intake():
    other = _comment(OWN, "Builder progress (cloud build).", _at(0))
    assert _superseded([other, _intake(101, 1)])["reason"] == "own-intake-not-found"


@pytest.mark.parametrize("repo, issue, own", [
    ("nope", ISSUE, OWN), ("../x", ISSUE, OWN), (None, ISSUE, OWN), ("a/b/c", ISSUE, OWN),
    (REPO, 0, OWN), (REPO, -1, OWN), (REPO, True, OWN), (REPO, "17", OWN), (REPO, None, OWN),
    (REPO, ISSUE, 0), (REPO, ISSUE, -5), (REPO, ISSUE, True), (REPO, ISSUE, "100"), (REPO, ISSUE, None),
])
def test_bad_inputs_are_refused_before_any_read(repo, issue, own):
    gh = Gh([_intake(OWN, 0)])
    assert CB.superseded(repo, issue, own, env={}, run=gh) == {"ok": False, "reason": "input-invalid"}
    assert gh.calls == []


# 6. the stand-down is no other builder comment
def test_the_stand_down_is_not_read_as_any_other_builder_comment():
    text = CB.stand_down_text("https://github.com/%s/issues/%d#issuecomment-101" % (REPO, ISSUE))
    for body in (text, text + "\n" + CB.CLOUD_FOOTER):
        assert CB.terminal_kind(body) is None
        assert CB.handover_sha(body) is None
        assert CB.parse_progress(body) is None
        assert not body.startswith(CB.NOTE_HEADER)
    assert CB.STAND_DOWN_HEADER not in CB.TERMINAL_HEADERS.values()


# 7. the CLI
def test_cli_prints_the_same_json_and_exits_zero_when_superseded(monkeypatch, capsys):
    comments = [_intake(OWN, 0), _intake(101, 1)]
    monkeypatch.setattr(cloud_recover, "_issue_comments", lambda repo, issue, since, env, run: comments)
    expected = CB.superseded(REPO, ISSUE, OWN)
    assert expected["superseded"] is True
    code = CB.main(["superseded", "--repo", REPO, "--issue", str(ISSUE), "--own-intake-id", str(OWN)])
    assert code == 0
    assert json.loads(capsys.readouterr().out) == expected


def test_cli_exits_one_only_on_a_refusal(monkeypatch, capsys):
    monkeypatch.setattr(cloud_recover, "_issue_comments", lambda repo, issue, since, env, run: None)
    code = CB.main(["superseded", "--repo", REPO, "--issue", str(ISSUE), "--own-intake-id", str(OWN)])
    assert code == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "comments-unreadable"}


def test_cli_verb_is_listed_in_the_module_docstring():
    assert "cloud_builder.py superseded --repo O/N --issue N --own-intake-id ID" in CB.__doc__
    assert "cloud_builder.py superseded-notice --launch-id L" in CB.__doc__


# 7b. the advisor's supersession notice
def test_a_notice_later_than_the_own_intake_supersedes_and_is_named():
    result = _superseded([_intake(OWN, 0), _notice(101, 2)])
    assert result["superseded"] is True
    assert result["newerLaunch"]["commentId"] == 101
    assert result["comment"].startswith(CB.STAND_DOWN_HEADER)


def test_a_notice_earlier_than_the_own_intake_does_not_supersede():
    assert _superseded([_notice(99, 0), _intake(OWN, 3)])["superseded"] is False


def test_a_successors_intake_after_the_notice_is_the_newest_launch():
    result = _superseded([_intake(OWN, 0), _notice(101, 2), _intake(102, 4)])
    assert result["newerLaunch"]["commentId"] == 102


def test_the_notice_text_and_its_header_are_no_other_builder_comment():
    text = CB.superseded_notice_text("launch-7")
    assert text.startswith(CB.SUPERSEDED_HEADER + "\n\n")
    assert "the earlier lane launch-7 is superseded" in text
    assert "A cloud builder of an earlier lane that wakes stops without pushing." in text
    assert CB.SUPERSEDED_HEADER not in CB.TERMINAL_HEADERS.values()
    for body in (text, text + "\n" + CB.CLOUD_FOOTER):
        assert CB.terminal_kind(body) is None
        assert CB.handover_sha(body) is None
        assert CB.parse_progress(body) is None


@pytest.mark.parametrize("launch_id", ["", "   ", "a\nb", "a\rb", None, 7])
def test_the_notice_refuses_an_empty_or_multi_line_id(launch_id):
    assert CB.superseded_notice_text(launch_id) is None


def test_the_notice_cli_prints_the_comment(capsys):
    assert CB.main(["superseded-notice", "--launch-id", "launch-7"]) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "comment": CB.superseded_notice_text("launch-7")}


def test_the_notice_cli_refuses_an_invalid_id(capsys):
    assert CB.main(["superseded-notice", "--launch-id", "a\nb"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "input-invalid"}


def test_the_intake_texts_still_start_with_the_intake_header():
    for text in (CB.INTAKE_TEXT, CB.INTAKE_ADOPT_TEXT):
        assert text.startswith("Builder intake (cloud build). Plugin {v}. Commits from this build carry the cloud's own ")
        assert text.startswith(CB.INTAKE_HEADER)


# 8. doc pins
def _doc(rel):
    with open(os.path.join(_PLUGIN, rel), encoding="utf-8") as fh:
        return fh.read()


def test_cloud_reference_tells_a_waking_builder_to_check_and_push_nothing():
    text = _doc("skills/workhorse/reference/cloud.md")
    assert "cloud_builder.py superseded" in text
    assert "On `superseded: true`, push nothing" in text


def test_orchestration_no_longer_exempts_a_bound_lane_whose_branch_is_gone():
    text = " ".join(_doc("skills/showrunner/reference/orchestration.md").split())
    assert "A bound lane whose branch is gone from the remote needs no session listing" not in text


def test_orchestration_names_the_helper_read_and_its_four_fields():
    text = " ".join(_doc("skills/showrunner/reference/orchestration.md").split())
    assert "cloud_recover.py helper-read" in text
    assert "`cloud_recover.HELPER_READ_FIELDS`" in text


def test_launch_doctrine_recovery_names_the_usage_limit_recovery():
    text = _doc("rubric/launch-doctrine.md")
    section = text.split("## Recovery — taking over a build that stopped", 1)[1].split("\n## ", 1)[0]
    section = " ".join(section.split())
    assert "usage limit" in section
    assert "`cloud_relay.py limit`" in section
