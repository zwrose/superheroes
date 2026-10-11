"""The lapsed reviewer pass, end to end (#1747 C6-WO-D).

A cloud build whose reviewer pass lapsed before its review: the lapse is read without calling the
reviewer, the board's comment says the review did not run, the review record writes the review as
not run (parked), a review that finished before the lapse stays as recorded, and only the owner's
word lets the PR through while the record stays marked.

No test touches the network, the real home directory or the reviewer tool. The record is built with
the `Fake` readers of test_review_record.py, so no `gh` call happens.
"""
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder as cb  # noqa: E402
import cloud_pass  # noqa: E402
import model_registry  # noqa: E402
import review_record as rr  # noqa: E402
# The same fixtures the record writer's own tests use: the readers fake, the reviewer row and the
# account base, and the three-part sign-in token the reviewer-pass tests build.
from test_cloud_pass import NOW, _jwt, _signin  # noqa: E402
from test_review_record import HEAD, Fake, account, reviewer  # noqa: E402

# model_registry spells the Anthropic family "anthropic" (its `_MODELS["claude"]` rows).
ANTHROPIC = model_registry.model_family("claude", "sonnet-5.5")
LAPSE_CHECK = "the reviewer pass lapsed before two reviewers ran"
GO_AHEAD_WORDS = "go ahead without it"
GO_AHEAD_WHERE = "PR comment, fixture"


def _lapsed_env(tmp_path):
    """A cloud session with a sign-in placed at CODEX_HOME whose access token expired before NOW."""
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    signin = _signin(access=_jwt(NOW - 86400, "access"))
    (codex_home / "auth.json").write_text(json.dumps(signin), encoding="utf-8")
    return {"HOME": str(tmp_path), "CLAUDE_CODE_REMOTE": "true", "CODEX_HOME": str(codex_home)}


def _lapsed_account(go_aheads=()):
    """Three planned codex reviewers: one finished before the lapse, two did not run."""
    return account(
        reviewers=[
            reviewer("code-reviewer", ran=True, runDir=None, commit=HEAD),
            reviewer("test-reviewer", ran=False, runDir=None),
            reviewer("security-reviewer", ran=False, runDir=None),
        ],
        makers=[{"family": ANTHROPIC, "source": "implementer"}],
        goAheads=list(go_aheads),
        checked=["read the diff", LAPSE_CHECK],
        findings=[], ci="green", finalCommit=HEAD, lane="full")


def _go_aheads(*names):
    return [{"reviewer": n, "kind": "owner-words", "words": GO_AHEAD_WORDS, "where": GO_AHEAD_WHERE}
            for n in names]


def test_lapse_is_read_without_a_reviewer_call(tmp_path, monkeypatch):
    # axis: reading the lapse from the placed file alone; any subprocess call is a reviewer call
    def refuse(*args, **kwargs):
        pytest.fail("a subprocess ran while reading the lapse: %r" % (args,))

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    state = cb.pass_state(env=_lapsed_env(tmp_path), now=NOW)
    assert state["state"] == "lapsed"
    assert state["cloud"] is True
    assert state["passLapses"] == "2027-01-14"


def test_the_boards_pr_comment_says_the_review_did_not_run():
    # axis: the park comment's opening line and its two promises (pushed; not ready)
    comment = cb.review_lapsed_text()["comment"]
    assert comment.splitlines()[0] == "Parked: the review did not run."
    assert "The work is pushed" in comment
    assert "this PR is not ready" in comment


def test_a_lapsed_review_is_recorded_as_not_run_and_parked():
    # axis: the record of a lapsed pass; a not-run reviewer read as run, or a finished one lost
    rec = rr.build_record(_lapsed_account(), Fake().readers())
    by_name = {v["name"]: v for v in rec["reviewers"]}

    assert rec["status"] == "not-reviewed"
    assert rec["parked"] is True
    assert [m["name"] for m in rec["missingReviews"]] == ["test-reviewer", "security-reviewer"]
    assert all(m["goAhead"] is None for m in rec["missingReviews"])
    assert "test-reviewer did not run" in rec["whatIsMissing"]
    assert "security-reviewer did not run" in rec["whatIsMissing"]
    assert by_name["test-reviewer"]["ran"] == "not-run"
    assert by_name["security-reviewer"]["ran"] == "not-run"

    # The review that finished before the lapse stays as recorded.
    done = by_name["code-reviewer"]
    assert done["ran"] == "reported-by-session"
    assert done["coversFinalCommit"] is True
    assert done["commit"] == HEAD
    assert "code-reviewer did not run" not in rec["whatIsMissing"]

    text = rr.render(rec)
    assert "- test-reviewer: did not run" in text
    assert "- security-reviewer: did not run" in text
    assert "- code-reviewer: ran (reported by the session)" in text
    assert "a review with no go-ahead is parked until the owner decides" in text

    # No reviewer is from a maker's family: the makers are shown as given.
    maker_families = {m["family"] for m in rec["makers"]}
    assert maker_families == {ANTHROPIC}
    assert all(v["family"] not in maker_families for v in rec["reviewers"])


def test_only_the_owners_word_lets_the_pr_through_and_it_stays_marked():
    # axis: the owner's go-ahead path; a go-ahead unparking the PR but also erasing the not-run mark
    names = ["test-reviewer", "security-reviewer"]
    rec = rr.build_record(_lapsed_account(_go_aheads(*names)), Fake().readers())

    assert rec["status"] == "not-reviewed"
    assert rec["parked"] is False
    assert [m["name"] for m in rec["missingReviews"]] == names
    assert all(m["goAhead"] is not None for m in rec["missingReviews"])
    assert [v["ran"] for v in rec["reviewers"] if v["name"] in names] == ["not-run", "not-run"]

    text = rr.render(rec)
    assert "**Review record: not reviewed.**" in text
    assert "- test-reviewer: did not run" in text
    assert "- security-reviewer: did not run" in text
    assert "test-reviewer did not run; go-ahead: owner's words (%s)" % GO_AHEAD_WHERE in text
    assert "security-reviewer did not run; go-ahead: owner's words (%s)" % GO_AHEAD_WHERE in text
    assert "a review with no go-ahead is parked" not in text


def test_a_go_ahead_with_a_blank_part_does_not_count():
    # axis: the go-ahead's completeness; an owner-words go-ahead with empty words letting the PR through
    blank = [{"reviewer": "test-reviewer", "kind": "owner-words", "words": "", "where": GO_AHEAD_WHERE}]
    rec = rr.build_record(_lapsed_account(blank), Fake().readers())
    assert rec["parked"] is True
    assert "the go-ahead for test-reviewer is incomplete" in rec["whatIsMissing"]


def test_the_cloud_builder_names_no_reviewer_dispatch():
    # axis: census of the cloud builder's source; matches dispatch-review, dispatch_review or seat
    # (case-sensitive substrings). It shows the helpers never pick a reviewer, so no maker-family
    # stand-in comes from them. The record shows makers, notIndependent and ownerWord as given and
    # never checks them, so no refusal is asserted here.
    with open(cloud_pass.__file__.replace("cloud_pass.py", "cloud_builder.py"), encoding="utf-8") as fh:
        source = fh.read()
    assert re.findall(r"dispatch-review|dispatch_review|seat", source) == []
